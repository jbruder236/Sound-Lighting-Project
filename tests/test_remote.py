"""Exercise the real JSON agent and transport with local child processes."""
import asyncio
from dataclasses import asdict
from pathlib import Path
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from dashboard_data import atomic_json, Settings, read_settings
from remote_backend import RemoteBackend


class RemoteTests(unittest.IsolatedAsyncioTestCase):
    async def test_offline_reconnect_save_and_process_cleanup(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / 'settings.json'
            flag = Path(folder) / 'attempted'
            atomic_json(config, asdict(Settings(scene='aurora')))
            script = '''
import asyncio, sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from remote_agent import serve
from dashboard_data import Backend
flag = Path(sys.argv[3])
if not flag.exists():
    flag.touch()
    raise SystemExit('Pi is powered off')
class TestBackend(Backend):
    def status(self):
        return {'updated_at': time.time(), 'stale': False, 'scene': self.settings().scene}
    async def audio(self, target=None):
        return {'sink': True}
asyncio.run(serve(TestBackend(sys.argv[2])))
'''
            backend = RemoteBackend()
            backend.command = [sys.executable, '-u', '-c', script,
                               str(Path(__file__).resolve().parents[1] / 'tools'), str(config), str(flag)]
            with self.assertRaises(ConnectionError):
                await backend.apply(brightness=10)
            task = asyncio.create_task(backend.run())
            children = []
            async def connected():
                async with asyncio.timeout(9):
                    while not backend.available:
                        await asyncio.sleep(.05)
            try:
                await connected()
                self.assertGreaterEqual(backend.attempts, 2)
                self.assertEqual(backend.settings().scene, 'aurora')
                self.assertEqual(backend.pending, {})
                await backend.apply(brightness=178, color='#00ddff', scene='custom')
                self.assertEqual(read_settings(config).brightness, 178)
                children.append(backend.process.pid)
                backend.process.kill()
                async with asyncio.timeout(2):
                    while backend.connected:
                        await asyncio.sleep(.05)
                self.assertTrue(backend.status()['stale'])
                with self.assertRaises(ConnectionError):
                    await backend.apply(brightness=1)
                await connected()
                children.append(backend.process.pid)
                self.assertEqual(backend.settings().brightness, 178)
                self.assertNotEqual(children[0], children[1])
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            for pid in children:
                with self.assertRaises(ProcessLookupError):
                    os.kill(pid, 0)

    async def test_rejects_ssh_options_as_hostname(self):
        for host in ('-oProxyCommand=bad', 'rpi;bad', 'rpi bad'):
            with self.assertRaises(ValueError):
                RemoteBackend(host)
