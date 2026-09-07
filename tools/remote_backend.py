"""Reconnecting SSH transport. Cached reads keep the UI responsive while offline."""
import asyncio
from dataclasses import asdict
import json
import re
import shlex
import time

from dashboard_data import Settings


class RemoteBackend:
    def __init__(self, host='rpi4', repo='/home/pi/Sound-Lighting-Project', readonly=False):
        if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.@:-]*', host):
            raise ValueError('Use an SSH hostname or configured alias')
        self.host, self.readonly = host, readonly
        self.command = ['ssh', '-T', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=3',
                        '-o', 'ConnectionAttempts=1', '-o', 'ServerAliveInterval=2',
                        '-o', 'ServerAliveCountMax=2', host,
                        'sudo -n /usr/bin/python3 -u ' + shlex.quote(repo + '/tools/remote_agent.py')]
        self.current = Settings()
        self.data = {'stale': True}
        self.graph = {'error': 'Waiting for the Pi'}
        self.connected = False
        self.config_valid = False
        self.process = None
        self.cleanup = None
        self.pending = {}
        self.lock = asyncio.Lock()
        self.serial = self.attempts = 0
        self.received = self.retry_at = 0
        self.error = 'Looking for the Pi'

    @property
    def available(self):
        return self.connected and time.monotonic() - self.received < 4

    @property
    def controls_available(self):
        return self.available and self.config_valid and not self.readonly

    @property
    def connection_text(self):
        if self.available:
            return f'{self.host} · SSH connected'
        left = max(0, self.retry_at - time.monotonic())
        phase = f'Retrying in {left:.0f}s' if left else 'Connecting…'
        return f'{self.host} · OFFLINE · {phase} · #{self.attempts}'

    def settings(self):
        return self.current

    def status(self):
        return self.data | {'stale': self.data.get('stale', True) or not self.available}

    async def audio(self, target=None):
        return self.graph if self.available else {'error': self.error}

    async def apply(self, **changes):
        async with self.lock:
            if not self.controls_available:
                raise ConnectionError('Pi unavailable or read-only; change not sent. Nothing is queued.')
            Settings.parse(asdict(self.current) | changes)
            self.serial += 1
            request_id = self.serial
            future = asyncio.get_running_loop().create_future()
            self.pending[request_id] = future
            try:
                self.process.stdin.write((json.dumps({'type': 'save', 'id': request_id,
                                                     'changes': changes}) + '\n').encode())
                await self.process.stdin.drain()
                result = await asyncio.wait_for(future, timeout=5)
                if result.get('error'):
                    raise ValueError(result['error'])
                self.current = Settings.parse(result['settings'])
                return self.current
            except TimeoutError:
                raise ConnectionError('Save acknowledgement timed out; check live state before retrying.') from None
            finally:
                self.pending.pop(request_id, None)

    async def run(self):
        while True:
            self.attempts += 1
            self.retry_at = 0
            try:
                self.process = await asyncio.create_subprocess_exec(
                    *self.command, stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
                while True:
                    line = await asyncio.wait_for(self.process.stdout.readline(), timeout=6)
                    if not line:
                        raise ConnectionError('SSH connection closed')
                    try:
                        message = json.loads(line)
                    except ValueError:
                        raise ConnectionError(line.decode(errors='replace').strip()) from None
                    if message.get('type') == 'snapshot':
                        if message.get('protocol') != 1:
                            raise ValueError('Update the Pi checkout to the TUI branch')
                        self.data, self.graph = message['status'], message['audio']
                        if message.get('settings_error'):
                            self.data['settings_error'] = message['settings_error']
                        self.config_valid = message.get('settings') is not None
                        if self.config_valid:
                            self.current = Settings.parse(message['settings'])
                        self.connected = True
                        self.received = time.monotonic()
                    elif message.get('type') == 'reply':
                        future = self.pending.get(message.get('id'))
                        if future is not None and not future.done():
                            future.set_result(message)
            except (OSError, ValueError, KeyError, TimeoutError) as error:
                self.error = str(error) or 'Connection timed out'
            finally:
                self.connected = False
                for future in self.pending.values():
                    if not future.done():
                        future.set_exception(ConnectionError('Connection lost; check saved state after reconnecting.'))
                await self.close()
            self.retry_at = time.monotonic() + 5
            await asyncio.sleep(5)

    async def close(self):
        """Share one cleanup task so app shutdown can wait for worker cancellation."""
        async def reap(process):
            if process.returncode is None:
                try:
                    process.terminate()
                except ProcessLookupError:
                    pass
            try:
                await asyncio.wait_for(process.wait(), timeout=2)
            except TimeoutError:
                process.kill()
                await process.wait()
        if self.process is not None:
            process, self.process = self.process, None
            self.cleanup = asyncio.create_task(reap(process))
        if self.cleanup is not None:
            await asyncio.shield(self.cleanup)
