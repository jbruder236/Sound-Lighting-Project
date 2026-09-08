import colorsys
from pathlib import Path
import sys
import unittest
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'RpiLightStripCodes'))
from punch import Punch, smooth_pixels
from addy_bluetooth import LightState, output_preview


class PunchTests(unittest.TestCase):
    def test_amount_changes_contrast_without_slowing_attack_or_exceeding_cap(self):
        features = {'rms': .08, 'bands': [1, 0, 0, 0, 0, 0]}
        frames = []
        for amount in (0, 50, 100):
            punch = Punch(0)
            punch.amount = amount
            for i in range(1, 7):
                punch.update(i/60, features, amount=amount)
            self.assertGreater(punch.level, .98)
            pixels = punch.frame(200, features, 1)
            self.assertTrue(all(0 <= c <= 255 for rgb in pixels for c in rgb))
            frames.append(pixels)
        # Gentle spreads light into the tail; vivid keeps its narrower regions.
        self.assertGreater(max(frames[0][-1]), max(frames[1][-1]))
        self.assertGreater(max(frames[1][-1]), max(frames[2][-1]))
        punch.update(.2, features, amount=0)
        self.assertTrue(0 < punch.amount < 100)  # Slider edits glide, not jump.

    def test_fast_steps_are_smoothed_but_arrive_much_sooner(self):
        fast = flow = np.zeros((100, 3))
        desired = np.full((100, 3), 255.)
        first = smooth_pixels(fast, desired, 1/60, fast=True)
        self.assertTrue(0 < first[0, 0] < 255)
        for _ in range(6):
            fast = smooth_pixels(fast, desired, 1/60, fast=True)
            flow = smooth_pixels(flow, desired, 1/60)
        self.assertGreater(fast[0, 0], 235)
        self.assertLess(flow[0, 0], 40)
        for _ in range(18):
            fast = smooth_pixels(fast, np.zeros_like(fast), 1/60, fast=True)
        self.assertLess(fast[0, 0], 10)

    def test_loudness_changes_have_large_contrast_and_release(self):
        punch = Punch(0)
        for i in range(1, 7):
            punch.update(i/60, {'rms': .08})
        self.assertGreater(punch.level, .98)
        loud = punch.frame(100, {'bands': [1, 0, 0, 0, 0, 0]}, 1)
        for i in range(7, 37):
            punch.update(i/60, {'rms': .006})
        quiet = punch.frame(100, {'bands': [1, 0, 0, 0, 0, 0]}, 1)
        self.assertGreater(max(map(max, loud)), 240)
        self.assertLess(max(map(max, quiet)), 30)
        punch.update(1, None)
        self.assertLess(punch.level, .04)

    def test_all_bands_are_distinct_bounded_and_master_still_limits(self):
        punch = Punch(0)
        punch.level = 1
        hues = []
        for band in range(6):
            features = {'bands': [int(i == band) for i in range(6)]}
            pixels = punch.frame(101, features, 1)
            self.assertTrue(all(0 <= c <= 255 for rgb in pixels for c in rgb))
            r, g, b = pixels[band * 20]
            hues.append(round(colorsys.rgb_to_hsv(r, g, b)[0], 1))
            self.assertTrue(all(c == '#000000' for c in output_preview(pixels, 0)))
            preview = output_preview(pixels, 143)
            self.assertTrue(all(int(c[j:j+2], 16) <= 143 for c in preview for j in (1,3,5)))
        self.assertEqual(len(set(hues)), 6)
        self.assertLess(max(map(max, punch.frame(100, {'bands': [0]*6}, 1))), 10)

    def test_fast_return_preserves_quiet_and_auto_timeout(self):
        state = LightState(0)
        for i in range(1, 61):
            state.update(i/60, .1, fast=True)
        for i in range(61, 121):
            state.update(i/60, 0, fast=True)
        self.assertEqual(state.mode, 'quiet')
        self.assertLess(state.gain, .09)
        for i in range(121, 671):
            state.update(i/60, 0, fast=True)
        self.assertEqual(state.mode, 'idle')
        state.update(11.2, .1, fast=True)
        self.assertEqual(state.mode, 'sound')
