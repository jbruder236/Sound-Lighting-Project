import importlib.util
from pathlib import Path
import unittest
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "RpiLightStripCodes"))

spec = importlib.util.spec_from_file_location('lighting', Path(__file__).resolve().parents[1] / 'RpiLightStripCodes/addy_bluetooth.py')
lighting = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lighting)


class ModeTests(unittest.TestCase):
    def test_starts_in_idle_without_audio(self):
        state = lighting.LightState(0)
        state.update(60, 0)
        self.assertEqual(state.mode, 'idle')
        self.assertEqual(state.mix, 0)

    def test_quiet_timeout_and_immediate_return(self):
        state = lighting.LightState(0, quiet_seconds=15)
        state.update(1, 0.1)
        self.assertEqual(state.mode, 'sound')
        state.update(15.99, 0)
        self.assertEqual(state.mode, 'quiet')
        state.update(16, 0)
        self.assertEqual(state.mode, 'idle')
        state.update(16.1, 0.1)
        self.assertEqual(state.mode, 'sound')

    def test_noise_does_not_reset_timeout(self):
        state = lighting.LightState(0)
        state.update(1, 0.1)
        for i in range(2, 17):
            state.update(i, 0.002)
        self.assertEqual(state.mode, 'idle')

    def test_crossfade_is_gradual_and_reversible(self):
        state = lighting.LightState(0, quiet_seconds=1)
        state.update(0.03, 0.1)
        self.assertGreater(state.mix, 0)
        self.assertLess(state.mix, 0.05)
        for i in range(2, 100):
            state.update(i * 0.03, 0.1)
        before = state.mix
        state.update(4, 0)
        self.assertEqual(state.mode, 'idle')
        self.assertGreater(state.mix, 0)
        self.assertLess(state.mix, before)

    def test_render_stays_colorful_lit_and_bounded(self):
        state = lighting.LightState(0)
        for count in (1, 100):
            for t in (0, 15, 70, 1000):
                for mix in (0, 0.5, 1):
                    state.mix = mix
                    pixels = lighting.frame(count, t, state)
                    self.assertEqual(len(pixels), count)
                    for rgb in pixels:
                        self.assertTrue(all(0 <= c <= 255 for c in rgb))
                        self.assertGreater(max(rgb), 100)
                        self.assertEqual(min(rgb), 0)

    def test_music_does_not_jump_hue(self):
        state = lighting.LightState(0)
        state.mix = 1
        a = lighting.frame(100, 5, state)
        state.envelope = 1
        b = lighting.frame(100, 5, state)
        for x, y in zip(a, b):
            self.assertEqual(x.index(min(x)), y.index(min(y)))

    def test_silence_dims_quickly_then_standby_recovers(self):
        state = lighting.LightState(0)
        for i in range(1, 31):
            state.update(i / 30, 0.1)
        for i in range(31, 61):
            state.update(i / 30, 0)
        self.assertEqual(state.mode, 'quiet')
        self.assertLess(state.gain, 0.13)
        for i in range(61, 241):
            state.update(i / 30, 0)
        self.assertEqual(state.mode, 'idle')
        self.assertGreater(state.gain, 0.95)
        state.update(8.1, 0.1)
        self.assertEqual(state.mode, 'sound')


class SceneTests(unittest.TestCase):
    def test_custom_color_keeps_hue_and_moves(self):
        state = lighting.LightState(0)
        a = lighting.frame(100, 0, state, 'custom', '#ff0080')
        b = lighting.frame(100, 15, state, 'custom', '#ff0080')
        self.assertNotEqual(a, b)
        self.assertTrue(all(g == 0 and 0 < blue < r <= 255 for r, g, blue in a + b))
        self.assertEqual(lighting.frame(2, 0, state, 'custom', '#000000'), [(0, 0, 0)] * 2)

    def test_workshop_is_steady_regardless_of_audio(self):
        state = lighting.LightState(0)
        first = lighting.frame(100, 0, state, 'workshop')
        state.envelope = state.mix = 1
        self.assertEqual(first, lighting.frame(100, 100, state, 'workshop'))
        self.assertTrue(all(r > g > b for r, g, b in first))

    def test_aurora_is_colored_and_moves(self):
        state = lighting.LightState(0)
        a = lighting.frame(100, 0, state, 'aurora')
        b = lighting.frame(100, 15, state, 'aurora')
        self.assertNotEqual(a, b)
        self.assertTrue(all(min(rgb) == 0 and max(rgb) > 100 for rgb in a + b))

    def test_idle_override_does_not_react_to_loud_audio(self):
        state = lighting.LightState(0)
        state.update(1, 1.0, reactive=False)
        self.assertEqual(state.mode, 'idle')
        self.assertEqual(state.mix, 0)


if __name__ == '__main__':
    unittest.main()
