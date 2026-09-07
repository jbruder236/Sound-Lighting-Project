# Sound Lighting

**A garage light with a little life in it.**

Rich color rolls along a 32-foot WS2811 strip. Music gently lifts the glow.
The colors take their time. The room stays lit.

Built for a Raspberry Pi 4, with a Python program small enough to understand
and change in one sitting.

```text
                         ┌── AUX ──────────► Speaker
Laptop audio ────────────┤
                         └── Bluetooth ────► Pi ────► Addressable lights
```

## Light it up

**On the `TUI` branch:** a small terminal dashboard for the whole room.
Scenes, brightness, a separate color-picker window, and live sound/connection health.

```sh
# On the Pi, after the core installation below:
bash install/install-tui.sh
sudo lights tui
# Or open it directly from your laptop:
ssh -t rpi4 'sudo lights tui'
```

Closing the dashboard leaves the lights running. [Dashboard guide →](docs/dashboard.md)

Want it to run whenever the Pi is powered? [Install boot startup](docs/installation.md).

```sh
sudo bash install/install.sh
```

It starts in colorful idle mode, follows music when it arrives, and returns to idle
after **15 seconds of quiet**. No desktop login or USB sound card needed.

After installation, make changes while the lights keep running:

```sh
lights status
sudo lights scene aurora
sudo lights scene workshop
sudo lights scene rainbow
sudo lights brightness 80
```

**Rainbow** is saturated and flowing. **Aurora** is cyan, blue, and violet in broad
moving curtains. **Workshop** is steady warm-white utility light. Changes fade in
without restarting, and your choices survive reboot.
**Custom**, on this branch, carries your chosen hue through slow motion and soft
sound response. Choose it in the picker, or run `sudo lights color '#ff2870'`.

Read the [daily controls and recovery guide](docs/operations.md), or the
[hardware/audio setup](docs/setup.md) for a fresh machine. Always stop the service
before starting a separate manual LED test. Normal shutdown clears the strip;
forced kills and power loss cannot guarantee clearing.

## What it feels like

- **Color that stays colorful.** Fully saturated bands, slowly drifting along the strip.
- **Music without the flicker.** Fast changes in sound soften into a gentle glow.
- **Light between songs.** A colorful idle animation takes over after 15 seconds of quiet.
- **A cord less.** AUX feeds the speaker while Bluetooth carries the same audio to the Pi.
- **No-fuss controls.** Change scenes, brightness, and sound behavior without a restart.

## Ready for the garage · 1.0.0

`master` remains the tagged 1.0 release. `TUI` is the **1.1.0-dev** dashboard branch.

| | Notes |
| --- | --- |
| Features | Boot startup, three scenes, live controls, saved settings, readable health status, automatic laptop reconnection. |
| Fixed during tuning | Capture recovery; stale Bluetooth endpoints; invalid live settings; orderly recorder and LED cleanup. |
| Known limitations | Tested Pi 4 layout only. Bluetooth/AUX timing is uncalibrated. Power/current limiting is external; no multi-day endurance claim. |

Current wiring: **GPIO21 / physical pin 40**, **GBR**, **100 addressable groups**.
Group count is not necessarily the number of physical LEDs. Brightness is capped
at 255; the animation varies individual channel levels below that ceiling.

See [version notes](CHANGELOG.md) for the concise release history.

## Small by design

| File | Purpose |
| --- | --- |
| [addy_bluetooth.py](RpiLightStripCodes/addy_bluetooth.py) | The live, sound-reactive lighting program. |
| [settings.py](RpiLightStripCodes/settings.py) | Shared validation and atomic settings updates. |
| [lights.py](tools/lights.py) | Scene controls and live health status. |
| [dashboard.py](tools/dashboard.py) · [style](tools/dashboard.tcss) | Optional Textual dashboard and color dialog. |
| [dashboard_data.py](tools/dashboard_data.py) | Settings and audio inspection, with no LED driver. |
| [addy_demo.py](RpiLightStripCodes/addy_demo.py) | Utility light, color checks, and sound-free patterns. |
| [connect_garage_audio.py](tools/connect_garage_audio.py) | Restore or continuously maintain AUX/Bluetooth output. |
| [legacy/](legacy/) | Earlier experiments, images, and iterations. Deprecated, preserved, visible. |

Python **3.13.5**, NumPy **2.2.4**, and `rpi_ws281x` **5.0.0** are the verified combination.
The existing `RpiLightStripCodes/` path stays stable for the running service.

Made by James Bruder.
