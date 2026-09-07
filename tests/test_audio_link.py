import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('audio_link', Path(__file__).resolve().parents[1] / 'tools/connect_garage_audio.py')
link = importlib.util.module_from_spec(spec)
spec.loader.exec_module(link)


class AudioLinkTests(unittest.TestCase):
    def test_rebuilds_when_bluetooth_endpoint_changes(self):
        module = {'argument': 'sink_name=garage_dual slaves=wired,bluez.1'}
        self.assertTrue(link.module_matches(module, 'wired', 'bluez.1'))
        self.assertFalse(link.module_matches(module, 'wired', 'bluez.2'))

    def test_only_owns_named_combined_sink(self):
        unrelated = {'name': 'module-combine-sink', 'argument': 'sink_name=another slaves=a,b'}
        own = {'name': 'module-combine-sink', 'argument': 'sink_name=garage_dual slaves=a,b'}
        self.assertEqual(link.combined_module([unrelated, own]), own)
        self.assertIsNone(link.combined_module([unrelated]))
