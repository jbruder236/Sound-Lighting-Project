#!/usr/bin/env python3
"""Bluetooth-reactive WS2811 lights, inspired by AddyLED_10_24 and freqdomain.

Captures the PipeWire monitor receiving the Dell's A2DP stream. No mic cable.
Run with sudo; recording runs as pi in the existing pi audio session.
"""
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

TARGET = 'alsa_output.usb-C-Media_Electronics_Inc._USB_Audio_Device-00.analog-stereo'
RATE, CHUNK = 48000, 1024


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--seconds', type=float, default=10, help='0 means continuous')
    ap.add_argument('--count', type=int, default=100)
    ap.add_argument('--brightness', type=int, default=255)
    ap.add_argument('--target', default=TARGET)
    ap.add_argument('--audio-only', action='store_true', help='Measure without accessing LEDs')
    args = ap.parse_args()
    if not math.isfinite(args.seconds) or args.seconds < 0:
        ap.error('Duration must be finite and nonnegative')
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
    cmd = ['pw-record', '--target', args.target,
           '--properties=stream.capture.sink=true', '--latency=20ms',
           '--rate', str(RATE), '--channels', '1', '--format', 's16', '--raw', '-']
    if os.geteuid() == 0:
        uid = pwd.getpwnam('pi').pw_uid
        cmd = ['runuser', '-u', 'pi', '--', 'env', f'XDG_RUNTIME_DIR=/run/user/{uid}'] + cmd
    recorder = None
    strip = None
    initialized = False
    selector = selectors.DefaultSelector()
    blocks, max_rms, peak = 0, 0.0, 0.0
    try:
        recorder = subprocess.Popen(cmd, stdout=subprocess.PIPE, start_new_session=True)
        os.set_blocking(recorder.stdout.fileno(), False)
        selector.register(recorder.stdout, selectors.EVENT_READ)
        if not args.audio_only:
            from rpi_ws281x import PixelStrip, Color, ws
            strip = PixelStrip(args.count, 21, 800000, 10, False,
                              args.brightness, 0, ws.WS2811_STRIP_GBR)
            strip.begin()
            initialized = True
        print('Saturated flowing Bluetooth lighting started.', flush=True)
        start = last_audio = time.monotonic()
        data = bytearray()
        envelope, reference = 0.0, 0.08
        smooth_bass = smooth_high = 0.0
        last_frame = start
        window = np.hanning(CHUNK)
        frequencies = np.fft.rfftfreq(CHUNK, 1 / RATE)
        bass_mask = (frequencies >= 45) & (frequencies < 250)
        high_mask = (frequencies >= 2000) & (frequencies < 10000)
        while not stopping:
            now = time.monotonic()
            if args.seconds and now - start >= args.seconds:
                break
            if recorder.poll() is not None:
                raise RuntimeError('Audio recorder exited unexpectedly')
            if not selector.select(0.1):
                if now - last_audio > 3:
                    raise RuntimeError('No audio frames for 3 seconds; check Bluetooth routing')
                continue
            incoming = os.read(recorder.stdout.fileno(), 65536)
            if not incoming:
                raise RuntimeError('Audio stream ended')
            data.extend(incoming)
            if len(data) < CHUNK * 2:
                continue
            # Drop old complete blocks to prevent visible lag if rendering falls behind.
            complete = len(data) // (CHUNK * 2)
            offset = (complete - 1) * CHUNK * 2
            samples = np.frombuffer(bytes(data[offset:offset + CHUNK * 2]), dtype='<i2').astype(float) / 32768
            del data[:complete * CHUNK * 2]
            dt = min(0.25, max(0.001, now - last_frame))
            last_frame = now
            last_audio = now
            rms = float(np.sqrt(np.mean(samples * samples)))
            max_rms = max(max_rms, rms)
            peak = max(peak, float(np.max(np.abs(samples))))
            blocks += 1
            reference = max(0.025, rms, reference * math.exp(-dt / 6))
            level = min(1.0, rms / reference) if rms > 0.001 else 0.0
            envelope += (level - envelope) * (1 - math.exp(-dt / (0.45 if level > envelope else 1.6)))
            spectrum = np.abs(np.fft.rfft(samples * window)) ** 2
            total = float(spectrum.sum()) + 1e-12
            bass = min(1.0, float(spectrum[bass_mask].sum()) / total * 2)
            high = min(1.0, float(spectrum[high_mask].sum()) / total * 4)
            smooth_bass += (bass - smooth_bass) * (1 - math.exp(-dt / 1.8))
            smooth_high += (high - smooth_high) * (1 - math.exp(-dt / 2.5))
            if strip is not None:
                elapsed = now - start
                # Saturated, slow-moving color bands; music affects brightness only.
                for i in range(args.count):
                    position = i / max(1, args.count - 1)
                    hue = (position * 0.95 - elapsed / 70
                           + 0.035 * math.sin(position * math.tau * 2 - elapsed / 9)) % 1
                    ribbon = 0.5 + 0.5 * math.cos(position * math.tau * 2 - elapsed / 4)
                    brightness = (0.72 + 0.28 * envelope) * (0.78 + 0.22 * ribbon)
                    rgb = colorsys.hsv_to_rgb(hue, 1.0, brightness)
                    strip.setPixelColor(i, Color(*(round(c * 255) for c in rgb)))
                strip.show()
        print(f'Audio blocks={blocks}, max RMS={max_rms:.3f}, peak={peak:.3f}', flush=True)
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
            selector.close()
            if recorder is not None:
                if recorder.poll() is None:
                    os.killpg(recorder.pid, signal.SIGTERM)
                    try:
                        recorder.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        os.killpg(recorder.pid, signal.SIGKILL)
                        recorder.wait()
                recorder.stdout.close()
            print('Audio and LED resources released.', flush=True)


if __name__ == '__main__':
    main()
