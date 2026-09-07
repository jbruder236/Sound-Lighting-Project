from dataclasses import asdict
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'RpiLightStripCodes'))
from settings import Settings, SettingsWatcher, atomic_json, read_settings


class SettingsTests(unittest.TestCase):
    def test_rejects_unsafe_and_mistyped_values(self):
        for values in ({'brightness': -1}, {'brightness': 256}, {'brightness': True},
                       {'quiet_seconds': float('nan')}, {'threshold': 0},
                       {'scene': 'strobe'}, {'behavior': 'unknown'}, {'pin': 18}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                Settings.parse(values)

    def test_bad_update_keeps_last_good_and_recovers(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'settings.json'
            original = Settings(scene='aurora')
            atomic_json(path, asdict(original))
            watcher = SettingsWatcher(path, original)
            self.assertEqual(watcher.reload(), original)
            path.write_text('{broken')
            self.assertEqual(watcher.reload(), original)
            self.assertIsNotNone(watcher.error)
            atomic_json(path, asdict(Settings(scene='workshop', brightness=100)))
            self.assertEqual(watcher.reload().scene, 'workshop')
            self.assertIsNone(watcher.error)

    def test_missing_then_restored_identical_config_clears_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'settings.json'
            atomic_json(path, asdict(Settings()))
            watcher = SettingsWatcher(path, Settings())
            watcher.reload()
            path.unlink()
            watcher.reload()
            self.assertIsNotNone(watcher.error)
            atomic_json(path, asdict(Settings()))
            watcher.reload()
            self.assertIsNone(watcher.error)

    def test_atomic_write_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'settings.json'
            expected = Settings(brightness=128, quiet_seconds=30)
            atomic_json(path, asdict(expected))
            self.assertEqual(read_settings(path), expected)
            self.assertEqual(list(Path(directory).iterdir()), [path])
