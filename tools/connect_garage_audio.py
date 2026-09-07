#!/usr/bin/env python3
"""Restore AUX + a paired Pi; optionally keep the link repaired in the background."""
import argparse
import json
import re
import shlex
import signal
import subprocess
import time

WIRED = 'alsa_output.pci-0000_00_1f.3.analog-stereo'
COMBINED = 'garage_dual'


def call(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT, timeout=20)


def listing(kind):
    return json.loads(call('pactl', '-f', 'json', 'list', kind))


def module_matches(module, wired, bt):
    options = dict(token.split('=', 1) for token in shlex.split(module.get('argument', '')) if '=' in token)
    return options.get('slaves') == f'{wired},{bt}'


def combined_module(modules):
    for module in modules:
        if module.get('name') != 'module-combine-sink':
            continue
        options = dict(token.split('=', 1) for token in shlex.split(module.get('argument', '')) if '=' in token)
        if options.get('sink_name') == COMBINED:
            return module
    return None


def ensure_audio(address, wired):
    prefix = 'bluez_output.' + address.replace(':', '_') + '.'
    card_name = 'bluez_card.' + address.replace(':', '_')
    sinks = listing('sinks')
    bt = next((s['name'] for s in sinks if s['name'].startswith(prefix)), None)
    if bt is None:
        call('bluetoothctl', '--timeout', '15', 'connect', address)
        deadline = time.monotonic() + 15
        selected = False
        while bt is None and time.monotonic() < deadline:
            cards = listing('cards')
            card = next((c for c in cards if c['name'] == card_name), None)
            if card and not selected:
                profiles = card.get('profiles', {})
                profile = next((p for p in ('a2dp-sink', 'a2dp-sink-sbc') if p in profiles), None)
                if profile:
                    call('pactl', 'set-card-profile', card_name, profile)
                    selected = True
            sinks = listing('sinks')
            bt = next((s['name'] for s in sinks if s['name'].startswith(prefix)), None)
            if bt is None:
                time.sleep(0.5)
        if bt is None:
            raise RuntimeError('Paired Pi playback endpoint is unavailable; will retry in watch mode')
    if not any(s['name'] == wired for s in sinks):
        raise RuntimeError('Wired output is unavailable')
    module = combined_module(listing('modules'))
    if module and not module_matches(module, wired, bt):
        call('pactl', 'set-default-sink', wired)
        call('pactl', 'unload-module', str(module['index']))
        module = None
    if module is None:
        call('pactl', 'load-module', 'module-combine-sink', f'sink_name={COMBINED}',
             f'slaves={wired},{bt}', 'sink_properties=device.description=Garage-AUX-and-Pi')
        call('pactl', 'set-sink-volume', bt, '100%')
    sinks = listing('sinks')
    combined = next(s for s in sinks if s['name'] == COMBINED)
    # Don't change the physical speaker's volume or mute state.
    call('pactl', 'set-default-sink', COMBINED)
    for stream in listing('sink-inputs'):
        props = stream.get('properties', {})
        # Real application streams only; never feed the combine sink into itself.
        if props.get('application.process.id') and str(stream.get('sink')) != str(combined['index']):
            call('pactl', 'move-sink-input', str(stream['index']), COMBINED)
    return 'Connected: AUX + Pi. Speaker volume preserved.'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pi-address', required=True)
    parser.add_argument('--wired', default=WIRED)
    parser.add_argument('--watch', action='store_true', help='Repair routing every 15 seconds until stopped')
    args = parser.parse_args()
    address = args.pi_address.upper()
    if not re.fullmatch(r'(?:[0-9A-F]{2}:){5}[0-9A-F]{2}', address):
        parser.error('Use a Bluetooth address such as AA:BB:CC:DD:EE:FF')
    stopped = False

    def stop(*_):
        nonlocal stopped
        stopped = True

    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, stop)
    previous = None
    while not stopped:
        try:
            message = ensure_audio(address, args.wired)
            failed = False
        except (OSError, RuntimeError, ValueError, subprocess.SubprocessError, StopIteration) as error:
            message = 'Audio link unavailable: ' + str(error)
            failed = True
        if message != previous:
            print(message, flush=True)
            previous = message
        if not args.watch:
            return int(failed)
        deadline = time.monotonic() + 15
        while not stopped and time.monotonic() < deadline:
            time.sleep(0.25)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
