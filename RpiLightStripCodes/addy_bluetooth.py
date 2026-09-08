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

from pathlib import Path

import numpy as np
from settings import VERSION, SCENES, Settings, SettingsWatcher, atomic_json, read_settings

from spectrum import SpectrumReader, HUES
from colors import white_rgb
from punch import Punch, smooth_pixels

TARGET = 'lighting_audio'
RATE, CHUNK = 48000, 1024
CAPTURE_LATENCY_MS = 20
PALETTES = {'sunset': (0.98, 0.10), 'ocean': (0.51, 0.10),
            'ember': (0.04, 0.04), 'candy': (0.86, 0.10)}


class LightState:
    """Use actual sound, not merely an open audio device, to select the mode."""
    def __init__(self, now, quiet_seconds=10, threshold=0.003):
        self.quiet_seconds, self.threshold = quiet_seconds, threshold
        self.last_sound = None
        self.last_update = now
        self.reference = 0.08
        self.envelope = self.mix = 0.0
        self.mode = 'idle'
        self.gain = 1.0

    def update(self, now, rms, reactive=True, behavior='auto', fast=False):
        dt = max(0.0, min(0.25, now - self.last_update))
        self.last_update = now
        if rms >= self.threshold:
            self.last_sound = now
        self.mode = ('sound' if self.last_sound is not None and
                     now - self.last_sound < self.quiet_seconds else 'idle')
        if behavior == 'sound':
            self.mode = 'sound'
        if self.mode == 'sound' and (self.last_sound is None or now - self.last_sound > 0.25):
            self.mode = 'quiet'
        self.reference = max(0.025, rms, self.reference * math.exp(-dt / 6))
        level = min(1.0, rms / self.reference) if rms >= self.threshold else 0.0
        tau = 0.45 if level > self.envelope else 1.6
        self.envelope += (level - self.envelope) * (1 - math.exp(-dt / tau))
        if not reactive or behavior == 'idle':
            self.mode = 'idle'
        gain = 0.08 if self.mode == 'quiet' else 1.0
        gain_tau = 0.22 if gain < self.gain else 1.0
        if fast:
            gain_tau = .1 if gain < self.gain else .06
        self.gain += (gain - self.gain) * (1 - math.exp(-dt / gain_tau))
        target = float(self.mode == 'sound')
        self.mix += (target - self.mix) * (1 - math.exp(-dt / 1.2))


def frame(count, elapsed, state, scene='rainbow', color='#ff9646', white=50, spectrum=None):
    """Keep the approved saturated palette; crossfade only motion and glow."""
    if scene == 'workshop':
        level = (1 - .28 * (1 - state.envelope) * state.mix) * state.gain
        return [tuple(round(c * level) for c in white_rgb(white))] * count
    pixels = []
    spectral = (scene == 'spectrum' and spectrum and spectrum['rms'] >= state.threshold and
                max(spectrum['bands']) > 0 and state.mode == 'sound')
    palette = [colorsys.hsv_to_rgb(h, 1, 1) for h in HUES] if spectral else None
    for i in range(count):
        position = i / max(1, count - 1)
        hue = (position * 0.95 - elapsed / 70 +
               0.035 * math.sin(position * math.tau * 2 - elapsed / 9)) % 1
        if scene == 'aurora':
            hue = (0.61 + 0.17 * math.sin(position * math.tau - elapsed / 22)
                   + 0.04 * math.sin(position * math.tau * 2 + elapsed / 17)) % 1
        elif scene in PALETTES:
            center, spread = PALETTES[scene]
            hue = (center + spread * math.sin(position * math.tau - elapsed / 22)) % 1
        ribbon = 0.5 + 0.5 * math.cos(position * math.tau * 2 - elapsed / 4)
        sound_value = (0.72 + 0.28 * state.envelope) * (0.78 + 0.22 * ribbon)
        idle_wave = 0.5 + 0.5 * math.sin(position * math.tau - elapsed / 7)
        idle_value = 0.76 + 0.18 * idle_wave
        value = (idle_value * (1 - state.mix) + sound_value * state.mix) * state.gain
        if scene == 'spectrum' and spectral:
            weights = [energy * (.08 + math.exp(-((position - j / 5) / .3) ** 2))
                       for j, energy in enumerate(spectrum['bands'])]
            mixed = [sum(w * rgb[c] for w, rgb in zip(weights, palette)) for c in range(3)]
            h, saturation, _ = colorsys.rgb_to_hsv(*mixed)
            rgb = colorsys.hsv_to_rgb(h, max(.85, saturation), value)
        elif scene == 'custom':
            rgb = tuple(int(color[j:j + 2], 16) / 255 * value for j in (1, 3, 5))
        else:
            rgb = colorsys.hsv_to_rgb(hue, 1.0, value)
        pixels.append(tuple(round(c * 255) for c in rgb))
    return pixels


def output_preview(pixels, brightness):
    """Sample actual smoothed commands after master brightness, not LED measurements."""
    if pixels is None or len(pixels) == 0:
        return []
    return ['#' + ''.join(f'{round(round(c) * round(brightness) / 255):02x}' for c in pixels[i])
            for i in np.linspace(0, len(pixels) - 1, min(24, len(pixels)), dtype=int)]


class AudioReader:
    """Recover from missing devices/server restarts without blocking animation."""
    def __init__(self, target, user):
        self.command = ['pw-record', '--target', target,
                        '--properties=stream.capture.sink=true node.dont-fallback=true',
                        f'--latency={CAPTURE_LATENCY_MS}ms',
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
        self.attempts = self.clipped_blocks = 0
        self.last_sample = None

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
            self.attempts += 1
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
            self.clipped_blocks += int(np.max(np.abs(samples)) >= 0.999)
            self.blocks += 1
            self.last_frame = now
            self.last_sample = now
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

    def status(self, now):
        age = None if self.last_sample is None else max(0, now - self.last_sample)
        return {
            'audio': 'receiving' if self.process is not None and age is not None and age < 0.3 else 'waiting',
            'audio_blocks': self.blocks, 'capture_retries': max(0, self.attempts - 1),
            'peak': round(self.peak, 5), 'clipped_blocks': self.clipped_blocks,
            'audio_age_seconds': None if age is None else round(age, 2),
            'recorder_pid': self.process.pid if self.process is not None else None,
            'sample_rate': RATE,
            'sample_bits': 16, 'channels': 1,
            'analysis_window_ms': round(CHUNK / RATE * 1000, 2),
            'capture_requested_ms': CAPTURE_LATENCY_MS,
            'end_to_end_latency_ms': None,
        }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--version', action='version', version=VERSION)
    ap.add_argument('--config', help='Validated settings JSON; hot-reloaded')
    ap.add_argument('--status-file', help='Write live health JSON here once per second')
    ap.add_argument('--scene', choices=SCENES, default='rainbow')
    ap.add_argument('--seconds', type=float, default=10, help='0 means continuous')
    ap.add_argument('--count', type=int, default=100, help='Addressable groups per strip')
    ap.add_argument('--outputs', choices=('pcm', 'dual-pwm'), default='pcm',
                    help='One strip on GPIO21, or two on GPIO18 and GPIO13')
    ap.add_argument('--brightness', type=int, default=255)
    ap.add_argument('--target', default=TARGET, help='PipeWire sink monitor to capture')
    ap.add_argument('--audio-user', default='pi', help='User owning the PipeWire session')
    ap.add_argument('--quiet-seconds', type=float, default=10)
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
        ap.error('Use sudo for GPIO output')
    pixel_count = args.count * (2 if args.outputs == 'dual-pwm' else 1)
    try:
        initial = read_settings(args.config) if args.config else Settings.parse({
            'scene': args.scene, 'brightness': args.brightness,
            'quiet_seconds': args.quiet_seconds, 'threshold': args.threshold})
    except (OSError, ValueError) as error:
        ap.error(str(error))
    watcher = SettingsWatcher(args.config, initial)
    stopping = False

    def stop(*_):
        nonlocal stopping
        stopping = True

    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, stop)
    reader = AudioReader(args.target, args.audio_user)
    spectrum_reader = SpectrumReader()
    strip = None
    initialized = False
    max_rms = 0.0
    try:
        if not args.audio_only:
            from rpi_ws281x import PixelStrip, Color, ws
            if args.outputs == 'dual-pwm':
                if Path('/sys/module/snd_bcm2835').exists():
                    raise RuntimeError('Dual PWM requires onboard analog audio disabled; reboot after configuring it')
                from dual_pwm import DualPWMStrip
                strip = DualPWMStrip(args.count, initial.brightness)
            else:
                strip = PixelStrip(args.count, 21, 800000, 10, False,
                                  initial.brightness, 0, ws.WS2811_STRIP_GBR)
            strip.begin()
            initialized = True
        start = time.monotonic()
        state = LightState(start, initial.quiet_seconds, initial.threshold)
        punch = Punch(start)
        config = initial
        next_settings = next_status = start
        last_render = start
        brightness = float(initial.brightness)
        previous_pixels = None
        last_status_error = None
        print(f'Mode: idle. Sound returns automatically; quiet timeout {initial.quiet_seconds:g}s.', flush=True)
        while not stopping:
            now = time.monotonic()
            if args.seconds and now - start >= args.seconds:
                break
            dt = min(0.25, max(0.001, now - last_render))
            last_render = now
            if now >= next_settings:
                config = watcher.reload()
                state.quiet_seconds, state.threshold = config.quiet_seconds, config.threshold
                next_settings = now + .1
            rms = reader.poll(now)
            max_rms = max(max_rms, rms)
            previous_mode = state.mode
            fast = config.color_source == 'spectrum' and config.frequency_style == 'punch'
            state.update(now, rms, behavior=config.behavior, fast=fast)
            if state.mode != previous_mode:
                print(f'Mode: {state.mode} (RMS={rms:.4f}).', flush=True)
            features = spectrum_reader.poll(now)
            punch.update(now, features, config.threshold, config.punch)
            spectral_active = bool(config.color_source == 'spectrum' and state.mode == 'sound'
                                   and features and features['rms'] >= config.threshold
                                   and max(features['bands']) > 0)
            render_scene = 'spectrum' if spectral_active else config.scene
            if strip is not None:
                pixels = (punch.frame(pixel_count, features, state.gain)
                          if fast and features and state.mode != 'idle' else
                          frame(pixel_count, now - start, state, render_scene,
                                config.color, config.white, features))
                desired = np.array(pixels, dtype=float)
                previous_pixels = smooth_pixels(previous_pixels, desired, dt,
                    fast=bool(fast and features and state.mode != 'idle'), quiet=state.mode == 'quiet')
                brightness += (config.brightness - brightness) * (1 - math.exp(-dt / 0.65))
                strip.setBrightness(round(brightness))
                for i, rgb in enumerate(previous_pixels):
                    strip.setPixelColor(i, Color(*(round(c) for c in rgb)))
                strip.show()
            if args.status_file and now >= next_status:
                try:
                    atomic_json(args.status_file, {
                        **reader.status(now), **spectrum_reader.status(now),
                        'version': VERSION, 'state': 'running', 'updated_at': time.time(),
                        'pid': os.getpid(), 'target': args.target,
                        'output_gpios': [18, 13] if args.outputs == 'dual-pwm' else [21],
                        'pixel_count': pixel_count,
                        'uptime_seconds': round(now - start, 1), 'scene': config.scene,
                        'brightness_percent': round(config.brightness / 255 * 100),
                        'mode': state.mode, 'behavior': config.behavior, 'color': config.color,
                        'white': config.white, 'color_source': config.color_source,
                        'frequency_style': config.frequency_style,
                        'punch': config.punch,
                        'spectrum_active': spectral_active,
                        'strip_preview': output_preview(previous_pixels, brightness),
                        'output_gain_percent': round(state.gain * 100),
                        'rms': round(rms, 5),
                        'sound_age_seconds': None if state.last_sound is None else round(now - state.last_sound, 1),
                        'quiet_seconds': config.quiet_seconds,
                        'settings_error': watcher.error,
                    })
                    last_status_error = None
                except OSError as error:
                    if str(error) != last_status_error:
                        print(f'Status write failed: {error}', flush=True)
                        last_status_error = str(error)
                next_status = now + (.2 if config.color_source == 'spectrum' else 1)
            time.sleep(max(0, 1 / (60 if fast else 30) - (time.monotonic() - now)))
        print(f'Audio blocks={reader.blocks}, max RMS={max_rms:.3f}, peak={reader.peak:.3f}', flush=True)
    finally:
        try:
            if strip is not None:
                try:
                    if initialized:
                        for i in range(pixel_count):
                            strip.setPixelColor(i, 0)
                        strip.show()
                        time.sleep(0.05)
                        print('LEDs cleared.', flush=True)
                finally:
                    strip._cleanup()
        finally:
            reader.close()
            if args.status_file:
                try:
                    Path(args.status_file).unlink(missing_ok=True)
                except OSError:
                    pass
            print('Audio and LED resources released.', flush=True)


if __name__ == '__main__':
    main()
