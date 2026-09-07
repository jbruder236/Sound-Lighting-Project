#!/usr/bin/env python3
"""Restore the paired Pi + wired-speaker output for this desktop session."""
import argparse
import json
import subprocess
import time

WIRED = 'alsa_output.pci-0000_00_1f.3.analog-stereo'


def call(*args):
    return subprocess.check_output(args, text=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pi-address', required=True, help='Paired Pi Bluetooth MAC address')
    args = parser.parse_args()
    prefix = 'bluez_output.' + args.pi_address.upper().replace(':', '_') + '.'
    subprocess.run(['bluetoothctl', '--timeout', '15', 'connect', args.pi_address], check=True)
    deadline = time.monotonic() + 15
    while True:
        sinks = json.loads(call('pactl', '-f', 'json', 'list', 'sinks'))
        names = {s['name'] for s in sinks}
        bt = next((name for name in names if name.startswith(prefix)), None)
        if bt is not None:
            break
        if time.monotonic() > deadline:
            raise SystemExit('Pi Bluetooth audio output missing; check Pi login/audio session.')
        time.sleep(0.5)
    if WIRED not in names:
        raise SystemExit('Dell analog output missing.')
    if 'garage_dual' not in names:
        module = call('pactl', 'load-module', 'module-combine-sink',
                      'sink_name=garage_dual', f'slaves={WIRED},{bt}',
                      'sink_properties=device.description=Garage-AUX-and-Pi')
        print('Combined-output module:', module.strip())
    call('pactl', 'set-sink-port', WIRED, 'analog-output-headphones')
    call('pactl', 'set-sink-volume', bt, '100%')
    call('pactl', 'set-default-sink', 'garage_dual')
    for stream in json.loads(call('pactl', '-f', 'json', 'list', 'sink-inputs')):
        if stream.get('properties', {}).get('application.name') == 'Google Chrome':
            call('pactl', 'move-sink-input', str(stream['index']), 'garage_dual')
    print('Garage audio ready: wired speaker + Bluetooth Pi. Wired volume preserved.')


if __name__ == '__main__':
    main()
