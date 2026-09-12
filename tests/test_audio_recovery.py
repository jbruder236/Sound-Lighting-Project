import os
from pathlib import Path
import sys
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'RpiLightStripCodes'))
from addy_bluetooth import AudioReader


class AudioRecoveryTests(unittest.TestCase):
    def test_recorder_death_retries_and_releases_children(self):
        reader = AudioReader('test', 'pi')
        reader.command = [sys.executable, '-c',
                          'import sys,time; sys.stdout.buffer.write(b"\\x00\\x10"*4096); sys.stdout.buffer.flush(); time.sleep(30)']
        children = []
        try:
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                rms = reader.poll(time.monotonic())
                if rms:
                    break
                time.sleep(0.02)
            self.assertGreater(rms, 0.1)
            self.assertEqual(reader.status(time.monotonic())['capture_retries'], 0)
            first = reader.process
            children.append(first.pid)
            first.kill()
            first.wait()
            self.assertEqual(reader.poll(time.monotonic()), 0)
            self.assertIsNone(reader.process)
            reader.next_retry = 0
            reader.poll(time.monotonic())
            self.assertIsNotNone(reader.process)
            children.append(reader.process.pid)
            self.assertNotEqual(children[0], children[1])
            self.assertEqual(reader.status(time.monotonic())['capture_retries'], 1)
        finally:
            reader.close()
        for pid in children:
            with self.assertRaises(ProcessLookupError):
                os.kill(pid, 0)
