import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

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

    def test_mute_and_unmute_follow_physical_output_without_volume_changes(self):
        states = {'wired': False, link.COMBINED: False, 'bluez_output.AA_BB_CC_DD_EE_FF.1': False}
        calls = []
        def command(*args):
            calls.append(args)
            self.assertEqual(args[:2], ('pactl', 'set-sink-mute'))
            states[args[2]] = args[3] == '1'
        def sinks(kind):
            return [{'name': name, 'mute': mute} for name, mute in states.items()]
        with patch.object(link, 'listing', sinks), patch.object(link, 'call', command):
            previous = dict(states)
            states['wired'] = True
            previous = link.sync_mute('AA:BB:CC:DD:EE:FF', 'wired', previous)
            self.assertTrue(all(states.values()))
            states[link.COMBINED] = False
            previous = link.sync_mute('AA:BB:CC:DD:EE:FF', 'wired', previous)
            self.assertFalse(any(states.values()))
            link.sync_mute('AA:BB:CC:DD:EE:FF', 'wired', previous)
            self.assertEqual(len(calls), 4)
