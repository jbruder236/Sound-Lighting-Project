"""Small, hardware-free bridge from the dashboard to settings and PipeWire."""
from dataclasses import asdict
import asyncio
import json
import os
from pathlib import Path
import pwd
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'RpiLightStripCodes'))
from settings import CONFIG_PATH, STATUS_PATH, Settings, atomic_json, read_settings


class Backend:
    def __init__(self, config=CONFIG_PATH, status=STATUS_PATH, audio_user='pi', readonly=False):
        self.config, self.status_path = Path(config), Path(status)
        self.audio_user, self.readonly = audio_user, readonly

    @property
    def controls_available(self):
        return not self.readonly

    @property
    def connection_text(self):
        return 'On this Pi · live updates every second'

    async def apply(self, **changes):
        return self.save(**changes)

    def settings(self):
        return read_settings(self.config)

    def save(self, **changes):
        if self.readonly:
            raise PermissionError('Read-only dashboard; use sudo lights tui for controls')
        # Read at the moment of the change so unrelated CLI edits are retained.
        updated = Settings.parse(asdict(self.settings()) | changes)
        atomic_json(self.config, asdict(updated))
        return updated

    def status(self):
        try:
            data = json.loads(self.status_path.read_text())
            if not isinstance(data, dict) or not isinstance(data.get('updated_at'), (int, float)):
                raise ValueError('Invalid status document')
            data['stale'] = not -2 <= time.time() - data['updated_at'] <= 5
            return data
        except (OSError, ValueError) as error:
            return {'stale': True, 'error': str(error)}

    async def audio(self, target='lighting_audio'):
        try:
            account = pwd.getpwnam(self.audio_user)
            options = {'env': os.environ | {'XDG_RUNTIME_DIR': f'/run/user/{account.pw_uid}'}}
            if os.geteuid() == 0:
                options.update(user=account.pw_uid, group=account.pw_gid,
                               extra_groups=os.getgrouplist(self.audio_user, account.pw_gid))
            process = await asyncio.create_subprocess_exec(
                'pw-dump', stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL, **options)
            try:
                output, _ = await asyncio.wait_for(process.communicate(), timeout=3)
            finally:
                if process.returncode is None:
                    process.kill()
                await process.wait()
            if process.returncode:
                raise OSError(f'pw-dump exited with status {process.returncode}')
            return audio_graph(json.loads(output), target)
        except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
            return {'error': f'Audio inspection unavailable: {error}'}


def audio_graph(objects, target):
    """Report a connected peer separately from a live route into our sink."""
    nodes, devices, links = {}, [], []
    for item in objects:
        info = item.get('info', {})
        props = info.get('props', {})
        kind = item.get('type', '').rsplit(':', 1)[-1]
        if kind == 'Node':
            nodes[item['id']] = props | {'state': info.get('state', 'unknown')}
        elif kind == 'Device':
            devices.append(props)
        elif kind == 'Link' and info.get('state') == 'active':
            links.append((props.get('link.output.node'), props.get('link.input.node')))
    sinks = {key for key, p in nodes.items() if p.get('node.name') == target}
    sources = {a for a, b in links if b in sinks}
    peers = [p.get('device.description', 'Bluetooth peer') for p in devices
             if p.get('device.api') == 'bluez5' and p.get('api.bluez5.connection') == 'connected']
    routed = [p.get('node.description', p.get('node.name', '?')) for key, p in nodes.items()
              if key in sources and p.get('node.name', '').startswith('bluez_input.')]
    usb = [p.get('device.description', 'USB audio') for p in devices
           if p.get('device.bus') == 'usb' and p.get('media.class') == 'Audio/Device']
    return {'peers': peers, 'routed': routed, 'usb': usb, 'sink': bool(sinks),
            'inputs': sum(p.get('media.class') == 'Audio/Source' for p in nodes.values())}
