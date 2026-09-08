"""Dashboard behavior against temporary files; no GPIO or real audio changes."""
from dataclasses import asdict
import asyncio
import importlib.util
import json
import os
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
    from slider import Slider
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
            app.refresh_status()  # External telemetry must not discard a typed draft.
            await pilot.click('#set-brightness')
            await pilot.pause()
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
            await pilot.pause()
            self.assertEqual(self.backend.settings().behavior, 'idle')

    async def test_readonly_and_offline_at_small_size(self):
        self.backend.readonly = True
        self.status.unlink()
        app = Dashboard(self.backend)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            self.assertTrue(app.query_one('#scene').disabled)
            self.assertTrue(app.query_one('#brightness-slider').disabled)
            self.assertTrue(app.query_one('#white-slider').disabled)
            self.assertTrue(app.query_one('#frequency-punch').disabled)
            self.assertTrue(app.query_one('#punch-slider').disabled)
            app.action_idle()
            await pilot.pause()
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
            self.assertEqual(app.query_one('#brightness-slider', Slider).value, 27)

    async def test_sliders_live_drag_keyboard_coalesce_and_white_scene(self):
        calls = []
        active = maximum = 0
        async def apply(**values):
            nonlocal active, maximum
            active += 1
            maximum = max(maximum, active)
            calls.append(values)
            await asyncio.sleep(.1)
            self.backend.save(**values)
            active -= 1
        self.backend.apply = apply
        app = Dashboard(self.backend)
        async with app.run_test(size=(100, 32)) as pilot:
            await pilot.pause()
            slider = app.query_one('#brightness-slider', Slider)
            await pilot.mouse_down(slider, offset=(0, 0))
            await pilot.hover(slider, offset=(10, 0))
            await pilot.pause(.3)
            self.assertTrue(calls)  # Drag now reaches the engine before release.
            await pilot.mouse_up(slider, offset=(10, 0))
            await pilot.pause(.5)
            self.assertEqual(maximum, 1)
            self.assertLessEqual(len(calls), 3)
            self.assertEqual(self.backend.settings().brightness, round(slider.value * 255 / 100))
            slider.focus()
            await pilot.press('home', 'right', 'right', 'pageup')
            await pilot.pause(.5)
            self.assertEqual(slider.value, 12)
            self.assertEqual(self.backend.settings().brightness, 31)
            self.backend.save(brightness=128, scene='workshop')
            app.sync_controls(keep_draft=True)
            self.assertEqual(slider.value, 12)  # An old ACK must not interrupt keys.
            app.query_one('#white-slider').focus()
            await pilot.pause()
            self.assertEqual(slider.value, 50)  # Catch up after leaving the slider.
            self.backend.save(brightness=31)
            await pilot.press('end')
            await pilot.pause(.5)
            self.assertEqual(self.backend.settings().scene, 'workshop')
            self.assertEqual(self.backend.settings().white, 100)
            self.assertEqual(self.backend.settings().brightness, 31)
            atomic_json(self.status, {'updated_at': time.time(), 'analysis_window_ms': 21.33,
                                     'capture_requested_ms': 20})
            app.refresh_status()
            self.assertIn('unmeasured', str(app.query_one('#timing', Static).render()))
            self.assertIn('21.33 ms', str(app.query_one('#timing', Static).render()))

    async def test_mode_buttons_frequency_pane_and_stale_visuals(self):
        from spectrum_pane import BandChart, StripPreview
        from textual.widgets import Button
        app = Dashboard(self.backend)
        async with app.run_test(size=(100, 48)) as pilot:
            await pilot.pause()
            self.assertFalse(app.query_one('#spectrum-pane').display)
            await pilot.click('#mode-sound')
            await pilot.pause()
            self.assertEqual(self.backend.settings().behavior, 'sound')
            await pilot.click('#frequency-warble')
            await pilot.pause()
            self.assertEqual(self.backend.settings().frequency_style, 'warble')
            self.assertEqual(self.backend.settings().behavior, 'sound')
            await pilot.click('#frequency-flow')
            await pilot.pause()
            self.assertEqual(self.backend.settings().color_source, 'spectrum')
            self.assertTrue(app.query_one('#spectrum-pane').display)
            self.assertEqual(self.backend.settings().scene, 'rainbow')
            self.assertEqual(app.query_one('#frequency-flow', Button).variant, 'primary')
            await pilot.click('#frequency-warble')
            await pilot.pause()
            self.assertEqual(self.backend.settings().frequency_style, 'warble')
            self.assertEqual(app.query_one('#frequency-warble', Button).variant, 'primary')
            self.assertFalse(app.query_one('#punch-control').display)
            await pilot.click('#frequency-punch')
            await pilot.pause()
            self.assertEqual(self.backend.settings().frequency_style, 'punch')
            self.assertEqual(app.query_one('#frequency-punch', Button).variant, 'primary')
            self.assertTrue(app.query_one('#punch-control').display)
            app.query_one('#punch-slider').focus()
            await pilot.press('end')
            await pilot.pause(.4)
            self.assertEqual(self.backend.settings().punch, 100)
            self.assertEqual(self.backend.settings().scene, 'rainbow')
            self.assertEqual(self.backend.settings().brightness, 255)
            self.assertEqual(self.backend.settings().behavior, 'sound')
            atomic_json(self.status, dict(updated_at=time.time(), color_source='spectrum',
                frequency_style='punch',
                scene='rainbow', spectrum='receiving', spectrum_bands=[.8, .1, .1, 0, 0, 0],
                spectrum_active=True, strip_preview=['#ff8000', '#ff3000']))
            app.refresh_status()
            self.assertEqual(app.query_one(BandChart).levels[0], .8)
            self.assertEqual(app.query_one(StripPreview).colors[0], '#ff8000')
            self.assertEqual(app.query_one(BandChart).band_colors[2], '#14ff00')
            self.assertIn('Punch', str(app.query_one('#spectrum-control', Static).render()))
            self.status.unlink()
            app.refresh_status()
            self.assertEqual(app.query_one(BandChart).levels, [0.] * 6)
            self.assertFalse(app.query_one(StripPreview).colors)
            await pilot.click('#mode-idle')
            await pilot.pause()
            self.assertEqual(self.backend.settings().behavior, 'idle')
            await pilot.click('#mode-auto')
            await pilot.pause()
            self.assertEqual(self.backend.settings().behavior, 'auto')
            await pilot.resize_terminal(54, 38)
            await pilot.click('#source-palette')
            await pilot.pause()
            self.assertFalse(app.query_one('#spectrum-pane').display)

    async def test_slider_thumb_fine_drag_escape_and_disabled_capture(self):
        self.backend.save(brightness=128, scene='workshop')
        app = Dashboard(self.backend)
        async with app.run_test(size=(100, 48)) as pilot:
            await pilot.pause()
            slider = app.query_one('#brightness-slider', Slider)
            thumb = round(slider.value / 100 * (slider.track_width-1))
            await pilot.mouse_down(slider, offset=(thumb, 1), shift=True)
            self.assertEqual(slider.value, 50)  # Grab without a jump.
            await pilot.mouse_up(slider, offset=(thumb+5, 1), shift=True)
            await pilot.pause(.4)
            self.assertTrue(50 < slider.value < 55)
            original = slider.value
            await pilot.mouse_down(slider, offset=(0, 1))
            await pilot.hover(slider, offset=(8, 1))
            await pilot.pause(.4)
            self.assertNotEqual(slider.value, original)
            await pilot.press('escape')
            await pilot.pause(.4)
            self.assertFalse(slider.dragging)
            self.assertEqual(slider.value, original)
            self.assertEqual(self.backend.settings().brightness, round(original*255/100))
            await pilot.mouse_down(slider, offset=(thumb, 1))
            slider.disabled = True
            await pilot.pause()
            self.assertFalse(slider.dragging)

    def test_frequency_meter_has_fast_attack_short_release_and_clears_offline(self):
        from spectrum_pane import BandChart
        chart = BandChart()
        chart.updated = 0
        chart.update_levels([.5, 0, 0, 0, 0, 0], True, now=.05)
        self.assertEqual(chart.levels[0], .5)  # Percentages remain measured shares.
        self.assertGreater(chart.shown[0], .5)
        chart.update_levels([0]*6, True, now=.10)
        self.assertTrue(0 < chart.shown[0] < chart.peaks[0])
        chart.update_levels([0]*6, True, now=.35)
        self.assertLess(chart.shown[0], .08)
        chart.update_levels([1]*6, False, now=.4)
        self.assertEqual(chart.shown, [0]*6)
        self.assertEqual(chart.peaks, [0]*6)

    async def test_sound_history_fixed_scale_fine_bars_and_fast_sampling(self):
        from sound_history import SoundHistory
        from unittest.mock import patch
        app = Dashboard(self.backend)
        async with app.run_test(size=(100, 48)) as pilot:
            await pilot.pause()
            chart = app.query_one('#wave', SoundHistory)
            chart.data = [.02] * 60
            before = chart.render().plain.splitlines()
            self.assertEqual(len(before), 4)
            self.assertTrue(any(c in '▁▂▃▄▅▆▇' for c in ''.join(before)))
            chart.data = [1.] + [.02] * 59
            after = chart.render().plain.splitlines()
            self.assertEqual([row[-1] for row in before], [row[-1] for row in after])
            chart.data = [0.] * 60
            self.assertFalse(chart.render().plain.strip())
            app.history.clear()
            app.history_at = 500
            for now in (100.21, 100.41, 100.61, 100.81, 101.01):
                with patch('dashboard.time.monotonic', return_value=now):
                    app.refresh_status()
            self.assertEqual(len(app.history), 5)
            with patch('dashboard.time.monotonic', return_value=101.05):
                app.refresh_status()
            self.assertEqual(len(app.history), 5)  # No duplicate within a tick.

    async def test_remote_dashboard_exit_reaps_ssh_child(self):
        from remote_backend import RemoteBackend
        backend = RemoteBackend()
        snapshot = json.dumps({'type': 'snapshot', 'protocol': 1, 'settings': asdict(Settings()),
                               'status': {'stale': False}, 'audio': {'error': 'Test fixture'}})
        backend.command = [sys.executable, '-u', '-c',
                           f'import time; print({snapshot!r}, flush=True); time.sleep(60)']
        app = Dashboard(backend)
        async with app.run_test(size=(110, 44)):
            async with asyncio.timeout(5):
                while not backend.available:
                    await asyncio.sleep(.05)
            child = backend.process.pid
        self.assertIsNone(backend.process)
        with self.assertRaises(ProcessLookupError):
            os.kill(child, 0)
