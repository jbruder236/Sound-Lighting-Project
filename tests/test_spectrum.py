"""Known signals, bounded transport, expiry and process cleanup; no real audio/GPIO."""
import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest

import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'RpiLightStripCodes')]
from spectral_analysis import Analyzer, RATE, WINDOW, waiting
from spectrum import SpectrumReader, validate
from settings import atomic_json
from addy_bluetooth import LightState, frame
from stream_spectrum import Publisher


class AnalysisTests(unittest.TestCase):
    def test_tones_land_in_correct_bands_and_ignore_volume_and_dc(self):
        analyzer = Analyzer()
        t = np.arange(WINDOW) / RATE
        for index, hz in enumerate((90, 260, 700, 1700, 4000, 9000)):
            for amplitude in (.02, .4):
                packet = analyzer.analyze(amplitude * np.sin(2 * np.pi * hz * t) + .05)
                self.assertEqual(np.argmax(packet['bands']), index)
                self.assertGreater(packet['bands'][index], .8)
                self.assertAlmostEqual(packet['centroid_hz'], hz, delta=10)
                validate(packet)
        packet = analyzer.analyze(.1 * np.sin(2 * np.pi * 90 * t) + .1 * np.sin(2 * np.pi * 4000 * t))
        self.assertGreater(packet['bands'][0], .4)
        self.assertGreater(packet['bands'][4], .4)

    def test_silence_noise_and_invalid_windows(self):
        analyzer = Analyzer()
        for samples in (np.zeros(WINDOW), np.ones(WINDOW), np.random.default_rng(42).normal(0, .0001, WINDOW)):
            self.assertEqual(analyzer.analyze(samples)['bands'], [0] * 6)
        for samples in ([0], np.full(WINDOW, np.nan)):
            with self.assertRaises(ValueError):
                analyzer.analyze(samples)

    def test_bad_packets_and_expiry_do_not_hold_a_color(self):
        packet = waiting() | {'capture_active': True, 'bands': [1, 0, 0, 0, 0, 0]}
        for changes in ({'bands': [1]}, {'bands': [float('nan')] * 6}, {'rms': -1},
                        {'fft_ms': float('inf')}, {'capture_active': 'yes'}):
            with self.assertRaises(ValueError):
                validate(packet | changes)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'spectrum.json'
            atomic_json(path, packet | {'received_at': 10})
            reader = SpectrumReader(path)
            self.assertIsNotNone(reader.poll(10.1))
            self.assertIsNone(reader.poll(10.8))
            atomic_json(path, packet | {'received_at': 12})
            self.assertIsNone(reader.poll(11))  # Wrong/future monotonic epoch.
            path.write_text('{broken')
            self.assertIsNone(reader.poll(12))

    def test_spectral_color_follows_tone_and_falls_back_without_signal(self):
        state = LightState(0)
        state.mode = 'sound'
        packet = waiting() | {'capture_active': True, 'rms': .1, 'bands': [1, 0, 0, 0, 0, 0]}
        warm = frame(100, 10, state, 'spectrum', spectrum=packet)
        packet['bands'] = [0, 0, 0, 0, 1, 0]
        cool = frame(100, 10, state, 'spectrum', spectrum=packet)
        self.assertTrue(all(r > b for r, g, b in warm))
        self.assertTrue(all(b > r for r, g, b in cool))
        for pixel in warm + cool:
            self.assertTrue(all(0 <= c <= 255 for c in pixel))
        fallback = frame(100, 10, state, 'rainbow')
        self.assertEqual(frame(100, 10, state, 'spectrum'), fallback)
        state.mode = 'idle'
        self.assertEqual(frame(100, 10, state, 'spectrum', spectrum=packet), fallback)


class TransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_publisher_keeps_connection_after_delayed_rejection(self):
        with tempfile.TemporaryDirectory() as folder:
            marker = Path(folder) / 'recovered'
            publisher = Publisher('rpi4', '/unused', 'unused')
            # A delayed rejection supplies a new challenge on the same link.
            publisher.command = [sys.executable, '-u', '-c',
                'import json,sys,time,pathlib\n'
                'print(json.dumps({"seq": 0, "accepted": None}), flush=True)\n'
                'json.loads(sys.stdin.readline())\n'
                'time.sleep(.6)\n'
                'print(json.dumps({"seq": 1, "accepted": False}), flush=True)\n'
                'packet = json.loads(sys.stdin.readline())\n'
                'assert packet["seq"] == 1\n'
                'pathlib.Path(sys.argv[1]).touch()\n'
                'time.sleep(10)\n', str(marker)]
            task = asyncio.create_task(publisher.publish())
            try:
                async with asyncio.timeout(2):
                    while not marker.exists():
                        await asyncio.sleep(.02)
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    async def test_receiver_rejects_delayed_packets_and_exits_on_eof(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'features.json'
            process = await asyncio.create_subprocess_exec(sys.executable, str(ROOT / 'tools/spectrum_receiver.py'),
                '--output', str(path), stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE)
            try:
                ready = json.loads(await process.stdout.readline())
                await asyncio.sleep(.55)
                process.stdin.write((json.dumps({'seq': ready['seq'], 'features': waiting()}) + '\n').encode())
                await process.stdin.drain()
                reply = json.loads(await process.stdout.readline())
                self.assertFalse(reply['accepted'])
                self.assertFalse(path.exists())
                process.stdin.write((json.dumps({'seq': reply['seq'], 'features': waiting()}) + '\n').encode())
                await process.stdin.drain()
                reply = json.loads(await process.stdout.readline())
                self.assertTrue(reply['accepted'])
                self.assertEqual(validate(json.loads(path.read_text())), waiting())
                process.stdin.close()
                await asyncio.wait_for(process.wait(), 2)
                self.assertEqual(process.returncode, 0)
            finally:
                if process.returncode is None:
                    process.kill()
                    await process.wait()

    async def test_publisher_recovers_capture_and_reaps_children(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'features.json'
            publisher = Publisher('rpi4', '/unused', 'unused')
            publisher.command = [sys.executable, str(ROOT / 'tools/spectrum_receiver.py'), '--output', str(path)]
            publisher.capture_command = [sys.executable, '-u', '-c',
                'import sys,time;\nwhile True:\n sys.stdout.buffer.write(b"\\x00\\x20\\x00\\xe0"*256); sys.stdout.buffer.flush(); time.sleep(.01)']
            task = asyncio.create_task(publisher.run())
            try:
                async with asyncio.timeout(5):
                    while not path.exists() or not json.loads(path.read_text())['capture_active']:
                        await asyncio.sleep(.05)
                self.assertGreater(json.loads(path.read_text())['rms'], .1)
                # Stop the capture subprocess without touching the receiver.
                children = Path(f'/proc/{os.getpid()}/task/{os.getpid()}/children').read_text().split()
                capture = next(int(pid) for pid in children if b'while True' in Path(f'/proc/{pid}/cmdline').read_bytes())
                os.kill(capture, 15)
                async with asyncio.timeout(2):
                    while json.loads(path.read_text())['capture_active']:
                        await asyncio.sleep(.05)
                async with asyncio.timeout(8):
                    while not json.loads(path.read_text())['capture_active']:
                        await asyncio.sleep(.05)
                self.assertNotIn(str(capture), Path(f'/proc/{os.getpid()}/task/{os.getpid()}/children').read_text().split())
                children = Path(f'/proc/{os.getpid()}/task/{os.getpid()}/children').read_text().split()
                receiver = next(int(pid) for pid in children if b'spectrum_receiver.py' in Path(f'/proc/{pid}/cmdline').read_bytes())
                os.kill(receiver, 15)
                await asyncio.sleep(1)
                self.assertIsNone(SpectrumReader(path).poll(time.monotonic()))
                async with asyncio.timeout(8):
                    while SpectrumReader(path).poll(time.monotonic()) is None:
                        await asyncio.sleep(.05)
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            self.assertEqual(Path(f'/proc/{os.getpid()}/task/{os.getpid()}/children').read_text().strip(), '')


if __name__ == '__main__':
    unittest.main()
