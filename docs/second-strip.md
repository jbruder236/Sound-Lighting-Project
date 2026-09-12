# Two spans

Dual-strip output uses **GPIO18 / physical pin12** and **GPIO13 / physical pin33**.
Each identical ALITOVE reel is 24V, 10m, 600 physical LEDs in 100 six-LED groups;
see the [verified label and hardware details](setup.md#hardware).
Both channels share one PWM driver and update together. The animation treats the
spans as one continuous 200-pixel canvas: GPIO18 first, then GPIO13.

| Output | BCM GPIO | Physical header pin |
| --- | --- | --- |
| Strip 1 DIN | 18 (PWM0) | 12 |
| Strip 2 DIN | 13 (PWM1) | 33 |
| Common signal ground | GND | 39 (or another GND) |

```text
Pi GPIO18 / pin12 ── level shifter ── 330–470Ω ── strip 1 DIN
Pi GPIO13 / pin33 ── level shifter ── 330–470Ω ── strip 2 DIN

Supply 1 + ───────────────────────────────────── strip 1 +
Supply 2 + ───────────────────────────────────── strip 2 +
               Keep these positive rails separate.

Supply 1 − ─── strip 1 GND ──┐
Supply 2 − ─── strip 2 GND ──┼── common DC ground
Pi GND / pin39 ──────────────┘
```

Power down before rewiring. Bond both DC negatives/strip grounds and Pi GND.
Return each strip's power current directly to its own supply, not through the
Pi header. Use the voltage specified on each strip; do not connect strip supply
positive to a GPIO or the Pi's power pins. A 74AHCT125 powered from 5V can shift
the Pi's 3.3V data to 5V; its ground joins the common ground. Put each data resistor
near its strip input. DIN is the input end indicated by the strip arrows.

## Enable on the Pi

The single-strip default remains GPIO21. After wiring the two outputs above:

```sh
cd /home/pi/Sound-Lighting-Project
sudo python3 install/enable_dual_strip.py
sudo reboot
```

The setup command stops the old service, backs up affected files under
`/var/backups/sound-lighting/dual-<timestamp>`, disables onboard analog audio, and
installs a persistent systemd override with `--outputs dual-pwm --count 100`.
The count is **per strip**, not the total number of physical LEDs. Bluetooth and
USB audio remain available. The engine refuses dual PWM while `snd_bcm2835` is
loaded, preventing it from competing with onboard analog audio.

Normal startup resumes the saved palette, brightness, and sound mode. One
controller owns both channels and DMA10; normal shutdown clears all 200 groups,
then releases the controller and audio capture. The TUI preview samples the
combined span; telemetry reports `pixel_count: 200` and `output_gpios: [18, 13]`.
The two strips retain the calibrated GBR channel order and share master brightness.

Check after reboot:

```sh
systemctl is-active addy-bluetooth.service
cat /run/sound-lighting/status.json
```

To return to one strip, stop the service and power down before moving its data
back to GPIO21 / pin40. Remove
`/etc/systemd/system/addy-bluetooth.service.d/dual-strip.conf`; the base service
then uses PCM again. If restoring analog audio, also remove the application-owned
`/etc/modprobe.d/sound-lighting-pwm.conf` and restore the backed-up boot config
(or remove its final Sound Lighting `dtparam=audio=off` block). Reload systemd and
reboot after those configuration changes. Preserve unrelated subsequent edits.

Sources: [driver GPIOs and audio conflict](https://github.com/jgarff/rpi_ws281x),
[separate supplies and common grounds](https://learn.adafruit.com/adafruit-neopixel-uberguide/powering-neopixels),
[data wiring](https://learn.adafruit.com/adafruit-neopixel-uberguide/best-practices).
