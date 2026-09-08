#!/usr/bin/env python3
"""Control Sound Lighting without restarting its service."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'RpiLightStripCodes'))
from settings import CONFIG_PATH, STATUS_PATH, SCENES, VERSION, Settings, atomic_json, read_settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', action='version', version=VERSION)
    parser.add_argument('--config', default=CONFIG_PATH)
    parser.add_argument('--status-file', default=STATUS_PATH)
    commands = parser.add_subparsers(dest='command', required=True)
    status = commands.add_parser('status', help='Show live scene, input health, and settings errors')
    status.add_argument('--json', action='store_true')
    commands.add_parser('config', help='Show saved settings')
    scene = commands.add_parser('scene', help='Crossfade to a scene')
    scene.add_argument('value', choices=SCENES)
    color = commands.add_parser('color', help='Set a hex color and crossfade to the custom scene')
    color.add_argument('value')
    white = commands.add_parser('white', help='Steady white tint: 0 warm, 50 original Workshop, 100 cool')
    white.add_argument('value', type=int)
    brightness = commands.add_parser('brightness', help='Set brightness percentage (0..100)')
    brightness.add_argument('value', type=int)
    behavior = commands.add_parser('mode', help='Standby, forced sound, or automatic sound/standby')
    behavior.add_argument('value', choices=('auto', 'standby', 'idle', 'sound'))
    source = commands.add_parser('source', help='Palette colors or frequency-driven colors')
    source.add_argument('value', choices=('palette', 'spectrum'))
    quiet = commands.add_parser('quiet', help='Seconds of silence before returning to idle')
    quiet.add_argument('value', type=float)
    threshold = commands.add_parser('threshold', help='Normalized RMS sound threshold')
    threshold.add_argument('value', type=float)
    args = parser.parse_args()
    try:
        if args.command == 'status':
            data = json.loads(Path(args.status_file).read_text())
            stale = time.time() - data['updated_at'] > 5
            if args.json:
                print(json.dumps(data | {'stale': stale}, indent=2))
            else:
                print(f"Sound Lighting {data['version']} | {'STALE' if stale else data['state']} | {data['scene']}")
                print(f"Brightness {data['brightness_percent']}% | input {data['audio']} | RMS {data['rms']:.4f}")
                print(f"Mode {data['mode']} | quiet timeout {data['quiet_seconds']:g}s | uptime {data['uptime_seconds']:.0f}s")
                if data.get('settings_error'):
                    print('Settings error: ' + data['settings_error'])
            return 1 if stale or data['state'] != 'running' else 0
        current = read_settings(args.config)
        if args.command == 'config':
            print(json.dumps(asdict(current), indent=2))
            return 0
        values = asdict(current)
        if args.command == 'brightness':
            if not 0 <= args.value <= 100:
                parser.error('Brightness must be 0..100 percent')
            values['brightness'] = round(args.value * 255 / 100)
        elif args.command == 'color':
            values.update(color=args.value, scene='custom', color_source='palette')
        elif args.command == 'white':
            values.update(white=args.value, scene='workshop', color_source='palette')
        elif args.command == 'mode':
            values['behavior'] = 'idle' if args.value == 'standby' else args.value
        elif args.command == 'source':
            values['color_source'] = args.value
        else:
            key = {'scene': 'scene', 'mode': 'behavior', 'quiet': 'quiet_seconds', 'threshold': 'threshold'}[args.command]
            values[key] = args.value
        result = Settings.parse(values)
        atomic_json(args.config, asdict(result))
        print('Saved. Running lights apply this within one second, with a smooth transition.')
        return 0
    except (OSError, ValueError, KeyError) as error:
        print(f'{error}. For changes, use sudo; for missing status, check addy-bluetooth.service.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
