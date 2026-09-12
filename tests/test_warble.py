"""Ripple direction, per-strip geometry, and output limits without GPIO."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'RpiLightStripCodes'))
from warble import Warble


class WarbleTests(unittest.TestCase):
    def test_wave_moves_from_center_toward_ends(self):
        wave = Warble()
        wave.depth = .18
        pixels = [(200, 100, 50)] * 401
        first = wave.frame(pixels, 401)
        wave.phase = .25
        later = wave.frame(pixels, 401)
        self.assertLess(first[225][0], later[225][0])
        self.assertLess(later[250][0], first[250][0])
        self.assertEqual(first, first[::-1])

    def test_each_strip_has_its_own_center_and_never_borrows_its_neighbors_color(self):
        wave = Warble()
        wave.depth = .18
        pixels = [(200, 0, 0)]*100 + [(0, 0, 200)]*100
        result = wave.frame(pixels, 100)
        self.assertEqual(len(result), 200)
        self.assertEqual(result[:100], result[:100][::-1])
        self.assertTrue(all(g == b == 0 and 164 <= r <= 200 for r,g,b in result[:100]))
        self.assertTrue(all(r == g == 0 and 164 <= b <= 200 for r,g,b in result[100:]))

    def test_continuous_motion_and_silence_release_respect_existing_brightness(self):
        wave = Warble()
        for _ in range(60):
            wave.update(1/60, 1, [1,0,0,0,0,0])
        self.assertTrue(0 < wave.depth < .18)
        self.assertTrue(0 < wave.phase < 1)
        pixels = [(i%255, (i*2)%255, (i*3)%255) for i in range(200)]
        result = wave.frame(pixels, 100)
        self.assertTrue(all(0 <= c <= 255 for p in result for c in p))
        self.assertEqual(wave.frame([(0,0,0)]*200,100), [(0,0,0)]*200)
        for _ in range(120):
            wave.update(1/60, 0, None)
        self.assertLess(wave.depth, .001)
