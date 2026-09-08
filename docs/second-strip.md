# Two spans

The current service drives one 100-pixel WS2811 span on **GPIO21 / physical pin40**.
The following is the planned dual-PWM wiring, **not an enabled second output**.

| Output | BCM GPIO | Physical header pin |
| --- | --- | --- |
| Strip 1 DIN, after moving its wire | 18 (PWM0) | 12 |
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

The installed driver supports **one PCM channel** (current GPIO21) or **two PWM
channels**. GPIO13 cannot simply be added as a second channel to the current PCM
instance. Activation therefore requires a dual-channel driver change, moving the
first data wire, disabling the Pi's onboard analog audio (`snd_bcm2835`, currently
enabled), and a reboot. USB and Bluetooth audio do not require that analog driver.
Do not expect either planned PWM pin to animate with today's GPIO21 service.

Sources: [driver GPIOs and audio conflict](https://github.com/jgarff/rpi_ws281x),
[separate supplies and common grounds](https://learn.adafruit.com/adafruit-neopixel-uberguide/powering-neopixels),
[data wiring](https://learn.adafruit.com/adafruit-neopixel-uberguide/best-practices).
