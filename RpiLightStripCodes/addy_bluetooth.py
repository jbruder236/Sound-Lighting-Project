#!/usr/bin/env python3
"""Always-on WS2811 lighting: smooth sound reaction or a colorful idle animation."""
import argparse
import colorsys
import math
import os
import pwd
import selectors
import signal
import subprocess
import time

import numpy as np

TARGET = 'lighting_audio'
RATE, CHUNK = 48000, 1024


class LightState:
    """Use actual sound, not merely an open audio device, to select the mode."""
    def __init__(self, now, quiet_seconds=15, threshold=0.003):
        self.quiet_seconds, self.threshold = quiet_seconds, threshold
        self.last_sound = None
        self.last_update = now
        self.reference = 0.08
        self.envelope = self.mix = 0.0
        self.mode = 'idle'

    def update(self, now, rms):
        dt = max(0.0, min(0.25, now - self.last_update))
        self.last_update = now
        if rms >= self.threshold:
            self.last_sound = now
        self.mode = ('sound' if self.last_sound is not None and
                     now - self.last_sound < self.quiet_seconds else 'idle')
        self.reference = max(0.025, rms, self.reference * math.exp(-dt / 6))
        level = min(1.0, rms / self.reference) if rms >= self.threshold else 0.0
        tau = 0.45 if level > self.envelope else 1.6
        self.envelope += (level - self.envelope) * (1 - math.exp(-dt / tau))
        target = float(self.mode == 'sound')
        self.mix += (target - self.mix) * (1 - math.exp(-dt / 1.2))


def frame(count, elapsed, state):
    """Keep the approved saturated palette; crossfade only motion and glow."""
    pixels = []
    for i in range(count):
        position = i / max(1, count - 1)
        hue = (position * 0.95 - elapsed / 70 +
               0.035 * math.sin(position * math.tau * 2 - elapsed / 9)) % 1
        ribbon = 0.5 + 0.5 * math.cos(position * math.tau * 2 - elapsed / 4)
        sound_value = (0.72 + 0.28 * state.envelope) * (0.78 + 0.22 * ribbon)
        idle_wave = 0.5 + 0.5 * math.sin(position * math.tau - elapsed / 7)
        idle_value = 0.76 + 0.18 * idle_wave
        value = idle_value * (1 - state.mix) + sound_value * state.mix
        rgb = colorsys.hsv_to_rgb(hue, 1.0, value)
        pixels.append(tuple(round(c * 255) for c in rgb))
    return pixels


class AudioReader:
    """Recover from missing devices/server restarts without blocking animation."""
    def __init__(self, target, user):
        self.command = ['pw-record', '--target', target,
                        '--properties=stream.capture.sink=true node.dont-fallback=true', '--latency=20ms',
                        '--rate', str(RATE), '--channels', '1', '--format', 's16', '--raw', '-']
        self.options = {}
        if os.geteuid() == 0:
            account = pwd.getpwnam(user)
            env = os.environ.copy()
            env['XDG_RUNTIME_DIR'] = f'/run/user/{account.pw_uid}'
            self.options = dict(user=account.pw_uid, group=account.pw_gid,
                                extra_groups=os.getgrouplist(user, account.pw_gid), env=env)
        self.process = None
        self.selector = selectors.DefaultSelector()
        self.data = bytearray()
        self.next_retry = self.last_frame = self.rms = self.peak = 0.0
        self.blocks = 0

    def disconnect(self):
        if self.process is not None:
            process, self.process = self.process, None
            self.selector.unregister(process.stdout)
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            process.stdout.close()
        self.data.clear()
        self.rms = 0.0

    def poll(self, now):
        if self.process is None:
            if now < self.next_retry:
                return 0.0
            self.next_retry = now + 5
            try:
                self.process = subprocess.Popen(self.command, stdout=subprocess.PIPE,
                                                stderr=subprocess.DEVNULL,
                                                start_new_session=True, **self.options)
            except OSError as error:
                print(f'Audio unavailable ({error}); idle lights continue. Retry in 5s.', flush=True)
                return 0.0
            os.set_blocking(self.process.stdout.fileno(), False)
            self.selector.register(self.process.stdout, selectors.EVENT_READ)
            self.last_frame = now
        if self.process.poll() is not None:
            self.disconnect()
            self.next_retry = now + 5
            print('Audio recorder ended; idle fallback available. Retry in 5s.', flush=True)
            return 0.0
        # Bound work per render tick and keep only the latest block to avoid lag.
        for _ in range(4):
            if not self.selector.select(0):
                break
            try:
                incoming = os.read(self.process.stdout.fileno(), 65536)
            except BlockingIOError:
                break
            if not incoming:
                self.disconnect()
                self.next_retry = now + 5
                return 0.0
            self.data.extend(incoming)
        complete = len(self.data) // (CHUNK * 2)
        if complete:
            offset = (complete - 1) * CHUNK * 2
            samples = np.frombuffer(bytes(self.data[offset:offset + CHUNK * 2]), dtype='<i2').astype(float) / 32768
            del self.data[:complete * CHUNK * 2]
            self.rms = float(np.sqrt(np.mean(samples * samples)))
            self.peak = max(self.peak, float(np.max(np.abs(samples))))
            self.blocks += 1
            self.last_frame = now
        if now - self.last_frame > 3:
            self.disconnect()
            self.next_retry = now + 5
            print('No audio frames; animation continues. Retrying capture in 5s.', flush=True)
            return 0.0
        # Never keep stale loudness after disconnect or a stalled stream.
        return self.rms if now - self.last_frame < 0.2 else 0.0

    def close(self):
        try:
            self.disconnect()
        finally:
            self.selector.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--seconds', type=float, default=10, help='0 means continuous')
    ap.add_argument('--count', type=int, default=100)
    ap.add_argument('--brightness', type=int, default=255)
    ap.add_argument('--target', default=TARGET, help='PipeWire sink monitor to capture')
    ap.add_argument('--audio-user', default='pi', help='User owning the PipeWire session')
    ap.add_argument('--quiet-seconds', type=float, default=15)
    ap.add_argument('--threshold', type=float, default=0.003, help='Sound threshold as normalized RMS (0..1)')
    ap.add_argument('--audio-only', action='store_true', help='Test audio and mode transitions without GPIO')
    args = ap.parse_args()
    if not math.isfinite(args.seconds) or args.seconds < 0:
        ap.error('Duration must be finite and nonnegative')
    if not math.isfinite(args.quiet_seconds) or args.quiet_seconds <= 0:
        ap.error('Quiet timeout must be finite and positive')
    if not math.isfinite(args.threshold) or not 0 < args.threshold <= 1:
        ap.error('Threshold must be greater than 0 and at most 1')
    if not 1 <= args.count <= 2000 or not 0 <= args.brightness <= 255:
        ap.error('Count must be 1..2000 and brightness 0..255')
    if not args.audio_only and os.geteuid() != 0:
        ap.error('Use sudo for GPIO21 PCM output')
    stopping = False

    def stop(*_):
        nonlocal stopping
        stopping = True

    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, stop)
    reader = AudioReader(args.target, args.audio_user)
    strip = None
    initialized = False
    max_rms = 0.0
    try:
        if not args.audio_only:
            from rpi_ws281x import PixelStrip, Color, ws
            strip = PixelStrip(args.count, 21, 800000, 10, False,
                              args.brightness, 0, ws.WS2811_STRIP_GBR)
            strip.begin()
            initialized = True
        start = time.monotonic()
        state = LightState(start, args.quiet_seconds, args.threshold)
        print(f'Mode: idle. Sound returns automatically; quiet timeout {args.quiet_seconds:g}s.', flush=True)
        while not stopping:
            now = time.monotonic()
            if args.seconds and now - start >= args.seconds:
                break
            rms = reader.poll(now)
            max_rms = max(max_rms, rms)
            previous_mode = state.mode
            state.update(now, rms)
            if state.mode != previous_mode:
                print(f'Mode: {state.mode} (RMS={rms:.4f}).', flush=True)
            if strip is not None:
                for i, rgb in enumerate(frame(args.count, now - start, state)):
                    strip.setPixelColor(i, Color(*rgb))
                strip.show()
            time.sleep(max(0, 1 / 30 - (time.monotonic() - now)))
        print(f'Audio blocks={reader.blocks}, max RMS={max_rms:.3f}, peak={reader.peak:.3f}', flush=True)
    finally:
        try:
            if strip is not None:
                try:
                    if initialized:
                        for i in range(args.count):
                            strip.setPixelColor(i, 0)
                        strip.show()
                        time.sleep(0.05)
                        print('LEDs cleared.', flush=True)
                finally:
                    strip._cleanup()
        finally:
            reader.close()
            print('Audio and LED resources released.', flush=True)


if __name__ == '__main__':
    main()
