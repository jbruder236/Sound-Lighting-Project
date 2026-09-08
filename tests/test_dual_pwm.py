"""Exercise the installed wrapper without mapping GPIO or starting DMA."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'RpiLightStripCodes'))


@unittest.skipUnless(importlib.util.find_spec('rpi_ws281x'), 'Pi driver not installed')
class DualPWMTests(unittest.TestCase):
    def test_shared_controller_addressing_brightness_and_cleanup(self):
        from dual_pwm import DualPWMStrip, ws
        strip = DualPWMStrip(100, 102)
        try:
            channels = [ws.ws2811_channel_get(strip._leds, i) for i in range(2)]
            self.assertEqual([ws.ws2811_channel_t_gpionum_get(c) for c in channels], [18, 13])
            self.assertEqual([ws.ws2811_channel_t_count_get(c) for c in channels], [100, 100])
            strip.setBrightness(40)
            self.assertEqual([ws.ws2811_channel_t_brightness_get(c) for c in channels], [40, 40])
            with patch.object(ws, 'ws2811_init', return_value=0):
                strip.begin()
            with patch.object(ws, 'ws2811_led_set') as write:
                for index in (0, 99, 100, 199):
                    strip.setPixelColor(index, 0x123456)
                self.assertEqual([c.args[1] for c in write.call_args_list], [0, 99, 0, 99])
                self.assertEqual(write.call_args_list[0].args[0], strip.channels[0])
                self.assertEqual(write.call_args_list[2].args[0], strip.channels[1])
                for index in (-1, 200):
                    with self.assertRaises(IndexError):
                        strip.setPixelColor(index, 0)
            with patch.object(ws, 'ws2811_render', return_value=0) as render:
                strip.show()
                render.assert_called_once_with(strip._leds)
        finally:
            with patch.object(ws, 'ws2811_fini') as finish:
                strip._cleanup()
                strip._cleanup()
                self.assertEqual(finish.call_count, 1)

    def test_cleanup_before_init_and_after_failed_init_never_calls_fini(self):
        from dual_pwm import DualPWMStrip, ws
        for fail in (False, True):
            strip = DualPWMStrip(100, 25)
            with patch.object(ws, 'ws2811_fini') as finish:
                if fail:
                    with patch.object(ws, 'ws2811_init', return_value=-1):
                        with self.assertRaises(RuntimeError):
                            strip.begin()
                strip._cleanup()
                strip._cleanup()
                finish.assert_not_called()
                self.assertIsNone(strip._leds)
