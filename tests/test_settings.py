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
                       {'white': -1}, {'white': 101}, {'white': True}, {'white': 50.5},
                       {'color_source': 'bad'}, {'scene': 'strobe'}, {'behavior': 'unknown'}, {'pin': 18}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                Settings.parse(values)

    def test_frequency_style_defaults_and_validation(self):
        self.assertEqual(Settings.parse({}).frequency_style, 'flow')
        self.assertEqual(Settings.parse({'frequency_style': 'punch'}).frequency_style, 'punch')
        with self.assertRaises(ValueError):
            Settings.parse({'frequency_style': 'strobe'})

    def test_custom_color_validation_and_old_config_defaults(self):
        self.assertEqual(Settings.parse({}).color, '#ff9646')
        self.assertEqual(Settings.parse({}).white, 50)
        self.assertEqual(Settings.parse({'color': '#ABCDEF'}).color, '#abcdef')
        for value in ('red', '#fff', '#gg0000', '#00000000', 123, None):
            with self.subTest(color=value), self.assertRaises(ValueError):
                Settings.parse({'color': value})

    def test_legacy_spectrum_migrates_and_new_modes_validate(self):
        migrated = Settings.parse({'scene': 'spectrum'})
        self.assertEqual((migrated.scene, migrated.color_source), ('rainbow', 'spectrum'))
        self.assertEqual(migrated.quiet_seconds, 10)
        self.assertEqual(Settings.parse({'behavior': 'sound'}).behavior, 'sound')

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
