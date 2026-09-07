#!/usr/bin/env python3
"""No-audio WS2811 demo. GPIO21 / physical pin 40; run only after wiring.

Uses the Pi's system Python and existing rpi_ws281x package.
Count means addressable ICs/groups, not necessarily individual LED packages.
--dry-run validates arguments and renders frames without accessing GPIO.
"""
import argparse
import colorsys
import math
import os
import signal
import time


def frame(count, elapsed, mode):
    pixels = []
    for i in range(count):
        hue = (i / count + elapsed / 10) % 1
        value = 1.0
        if mode == 'pulse':
            value = 0.1 + 0.9 * (0.5 - 0.5 * math.cos(elapsed * math.tau / 3))
        elif mode == 'chase':
            distance = (elapsed * 12 - i) % count
            value = max(0.0, 1 - distance / min(8, count))
        if mode in ('spectrum-garage', 'living-garage'):
            # Static colored accents framing a broad utility-light center.
            stops = [(0.0, (35, 55, 255)), (0.12, (0, 210, 175)),
                     (0.25, (255, 165, 60)), (0.35, (255, 215, 170)),
                     (0.65, (255, 215, 170)), (0.75, (255, 165, 60)),
                     (0.88, (0, 210, 175)), (1.0, (35, 55, 255))]
            position = i / max(1, count - 1)
            if mode == 'living-garage':
                # Gentle traveling motion concentrated toward the colored ends.
                edge = 1 - math.exp(-((position - 0.5) / 0.24) ** 4)
                position += 0.055 * edge * math.sin(math.tau * (elapsed / 12 - position))
                position = min(1.0, max(0.0, position))
            for (left, a), (right, b) in zip(stops, stops[1:]):
                if left <= position <= right:
                    blend = (position - left) / (right - left)
                    blend = blend * blend * (3 - 2 * blend)
                    pixels.append(tuple(round(x + (y - x) * blend) for x, y in zip(a, b)))
                    break
            continue
        if mode == 'garage':
            # Broad neutral-warm center, gently amber ends; entirely static.
            center = math.sin(math.pi * i / max(1, count - 1)) ** 2
            pixels.append((255, round(165 + 40 * center), round(90 + 65 * center)))
            continue
        if mode in ('red', 'green', 'blue', 'warm-white'):
            rgb = {'red': (255, 0, 0), 'green': (0, 255, 0), 'blue': (0, 0, 255), 'warm-white': (255, 150, 70)}[mode]
        else:
            rgb = tuple(round(c * 255) for c in colorsys.hsv_to_rgb(hue, 1, value))
        pixels.append(rgb)
    return pixels


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--count', type=int, default=100, help='Addressable groups; default from old script: 100')
    parser.add_argument('--brightness', type=int, default=20, help='0..255; default 20 (~8%%)')
    parser.add_argument('--seconds', type=float, default=10, help='Duration, 0 for continuous')
    parser.add_argument('--mode', choices=['rainbow', 'pulse', 'chase', 'red', 'green', 'blue', 'warm-white', 'garage', 'spectrum-garage', 'living-garage'], default='rainbow')
    parser.add_argument('--order', choices=['RGB', 'RBG', 'GRB', 'GBR', 'BRG', 'BGR'], default='GBR')
    parser.add_argument('--frequency', type=int, choices=[400000, 800000], default=800000)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.count <= 2000:
        parser.error('--count must be 1..2000')
    if not 0 <= args.brightness <= 255:
        parser.error('--brightness must be 0..255')
    if not math.isfinite(args.seconds) or args.seconds < 0:
        parser.error('--seconds must be finite and nonnegative')
    if args.dry_run:
        for mode in ('rainbow', 'pulse', 'chase', 'red', 'green', 'blue', 'warm-white', 'garage', 'spectrum-garage', 'living-garage'):
            for elapsed in (0, 0.5, 5, 19.9):
                pixels = frame(args.count, elapsed, mode)
                assert len(pixels) == args.count
                assert all(0 <= c <= 255 for rgb in pixels for c in rgb)
        print(f'Dry run OK: {args.count} groups, GPIO21 (pin 40), brightness {args.brightness}/255. No GPIO accessed.')
        return
    if os.geteuid() != 0:
        parser.error('PCM output requires sudo; use --dry-run for software-only validation')
    from rpi_ws281x import PixelStrip, Color, ws
    strip = PixelStrip(args.count, 21, args.frequency, 10, False,
                      args.brightness, 0, getattr(ws, 'WS2811_STRIP_' + args.order))
    stopped = False

    def stop(signum, context):
        nonlocal stopped
        stopped = True

    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, stop)
    strip.begin()
    print(f'{args.mode}: {args.count} groups on GPIO21; Ctrl-C to stop and clear.', flush=True)
    start = time.monotonic()
    try:
        while not stopped:
            elapsed = time.monotonic() - start
            if args.seconds and elapsed >= args.seconds:
                break
            for i, rgb in enumerate(frame(args.count, elapsed, args.mode)):
                strip.setPixelColor(i, Color(*rgb))
            strip.show()
            time.sleep(1 / 30)
    finally:
        try:
            for i in range(args.count):
                strip.setPixelColor(i, 0)
            strip.show()
            time.sleep(0.05)
            print('LEDs cleared.', flush=True)
        finally:
            # Installed rpi_ws281x 5.0.0 also registers this idempotent cleanup at exit.
            strip._cleanup()


if __name__ == '__main__':
    main()
