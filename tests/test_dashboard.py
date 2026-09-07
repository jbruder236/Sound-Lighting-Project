"""Dashboard behavior against temporary files; no GPIO or real audio changes."""
from dataclasses import asdict
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from dashboard_data import Backend, audio_graph
from settings import Settings, atomic_json


class BackendTests(unittest.TestCase):
    def test_connected_peer_is_not_a_route(self):
        def obj(kind, key, props, state=None):
            return {'id': key, 'type': 'PipeWire:Interface:' + kind,
                    'info': {'props': props, 'state': state}}
        objects = [obj('Device', 1, {'device.api': 'bluez5', 'api.bluez5.connection': 'connected',
                                     'device.description': 'Laptop'}),
                   obj('Node', 2, {'node.name': 'lighting_audio'}),
                   obj('Node', 3, {'node.name': 'bluez_input.test', 'node.description': 'Laptop'})]
        self.assertEqual(audio_graph(objects, 'lighting_audio')['peers'], ['Laptop'])
        self.assertEqual(audio_graph(objects, 'lighting_audio')['routed'], [])
        objects.append(obj('Link', 4, {'link.input.node': 2, 'link.output.node': 3}, 'active'))
        self.assertEqual(audio_graph(objects, 'lighting_audio')['routed'], ['Laptop'])

    def test_stale_and_malformed_status(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'status.json'
            backend = Backend(status=path)
            self.assertTrue(backend.status()['stale'])
            for value in ({'updated_at': time.time() - 10}, [], {'updated_at': 'bad'}):
                path.write_text(json.dumps(value))
                self.assertTrue(backend.status()['stale'])
            path.write_text(json.dumps({'updated_at': time.time()}))
            self.assertFalse(backend.status()['stale'])


if importlib.util.find_spec('textual'):
    from dashboard import ColorPicker, Dashboard
    from textual.widgets import Input, Select, Static
else:
    Dashboard = None


@unittest.skipIf(Dashboard is None, 'Optional Textual environment not installed')
class DashboardTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.folder = tempfile.TemporaryDirectory()
        config = Path(self.folder.name) / 'settings.json'
        self.status = Path(self.folder.name) / 'status.json'
        atomic_json(config, asdict(Settings()))
        atomic_json(self.status, {'updated_at': time.time(), 'scene': 'rainbow', 'mode': 'sound',
                                'audio': 'receiving', 'brightness_percent': 100, 'rms': .025})
        self.backend = Backend(config, self.status)
        async def audio(target):
            return {'peers': ['Laptop'], 'routed': ['Laptop'],
                    'usb': ['USB audio'], 'sink': True, 'inputs': 1}
        self.backend.audio = audio

    async def asyncTearDown(self):
        self.folder.cleanup()

    async def test_controls_modal_cancel_and_save(self):
        app = Dashboard(self.backend)
        async with app.run_test(size=(110, 40)) as pilot:
            await pilot.pause()
            app.query_one('#scene', Select).value = 'aurora'
            await pilot.pause()
            self.assertEqual(self.backend.settings().scene, 'aurora')
            # A separate CLI writer changed the timeout; the UI must preserve it.
            self.backend.save(quiet_seconds=30)
            app.query_one('#brightness', Input).value = '70'
            await pilot.click('#set-brightness')
            self.assertEqual(self.backend.settings().brightness, 178)
            self.assertEqual(self.backend.settings().quiet_seconds, 30)
            app.query_one('#brightness', Input).value = '101'
            await pilot.click('#set-brightness')
            self.assertEqual(self.backend.settings().brightness, 178)
            await pilot.click('#pick-color')
            await pilot.pause()
            self.assertIsInstance(app.screen, ColorPicker)
            app.screen.query_one('#hex', Input).value = '#00ddff'
            app.refresh_status()  # Live polling must work with the dialog open.
            await pilot.press('escape')
            await pilot.pause()
            self.assertEqual(self.backend.settings().scene, 'aurora')
            await pilot.click('#pick-color')
            app.screen.query_one('#hex', Input).value = '#zzzzzz'
            await pilot.pause()
            self.assertTrue(app.screen.query_one('#save-color').disabled)
            app.screen.query_one('#hex', Input).value = '#00ddff'
            await pilot.pause()
            await pilot.click('#save-color')
            await pilot.pause()
            self.assertEqual(self.backend.settings().color, '#00ddff')
            self.assertEqual(self.backend.settings().scene, 'custom')
            app.action_idle()
            self.assertEqual(self.backend.settings().behavior, 'idle')

    async def test_readonly_and_offline_at_small_size(self):
        self.backend.readonly = True
        self.status.unlink()
        app = Dashboard(self.backend)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            self.assertTrue(app.query_one('#scene').disabled)
            app.action_idle()
            self.assertEqual(self.backend.settings().behavior, 'auto')
            self.assertIn('OFFLINE', str(app.query_one('#health', Static).render()))

    async def test_opening_preserves_existing_preferences(self):
        self.backend.save(scene='aurora', behavior='idle', brightness=70)
        before = self.backend.config.read_bytes()
        app = Dashboard(self.backend)
        async with app.run_test(size=(110, 40)) as pilot:
            await pilot.pause()
            self.assertEqual(self.backend.config.read_bytes(), before)
            self.assertEqual(app.query_one('#scene', Select).value, 'aurora')
            self.assertEqual(app.query_one('#brightness', Input).value, '27')
