"""Two PWM channels sharing one driver, DMA allocation, render, and cleanup."""
import atexit
from rpi_ws281x import ws


class DualPWMStrip:
    """GPIO18 then GPIO13 form one continuous span of logical pixels.

    Use the pinned rpi_ws281x 5.0.0 C bindings: the Python PixelStrip wrapper
    exposes only one channel per controller. Gamma tables are allocated by C
    initialization, avoiding allocations before hardware is initialized.
    """
    def __init__(self, count, brightness):
        self.per_strip = count
        self._begun = False
        self._leds = ws.new_ws2811_t()
        self.channels = [ws.ws2811_channel_get(self._leds, i) for i in range(2)]
        atexit.register(self._cleanup)
        for channel, pin in zip(self.channels, (18, 13)):
            ws.ws2811_channel_t_count_set(channel, count)
            ws.ws2811_channel_t_gpionum_set(channel, pin)
            ws.ws2811_channel_t_invert_set(channel, 0)
            ws.ws2811_channel_t_brightness_set(channel, brightness)
            ws.ws2811_channel_t_strip_type_set(channel, ws.WS2811_STRIP_GBR)
        ws.ws2811_t_freq_set(self._leds, 800000)
        ws.ws2811_t_dmanum_set(self._leds, 10)

    def begin(self):
        if self._leds is None or self._begun:
            raise RuntimeError('Controller is closed or already initialized')
        result = ws.ws2811_init(self._leds)
        if result:
            raise RuntimeError(f'Dual PWM initialization failed: {ws.ws2811_get_return_t_str(result)}')
        self._begun = True

    def show(self):
        if not self._begun:
            raise RuntimeError('Controller is not initialized')
        result = ws.ws2811_render(self._leds)
        if result:
            raise RuntimeError(f'Dual PWM render failed: {ws.ws2811_get_return_t_str(result)}')

    def setPixelColor(self, index, color):
        if not self._begun:
            raise RuntimeError('Controller is not initialized')
        if not 0 <= index < self.per_strip * 2:
            raise IndexError(index)
        channel, offset = divmod(index, self.per_strip)
        ws.ws2811_led_set(self.channels[channel], offset, color)

    def setBrightness(self, brightness):
        for channel in self.channels:
            ws.ws2811_channel_t_brightness_set(channel, brightness)

    def _cleanup(self):
        if self._leds is not None:
            # C fini dereferences the hardware context; never call before a
            # successful init. Failed C init unwinds its own hardware resources.
            if self._begun:
                ws.ws2811_fini(self._leds)
            ws.delete_ws2811_t(self._leds)
            self._leds = None
            self.channels = []
            self._begun = False
            atexit.unregister(self._cleanup)
