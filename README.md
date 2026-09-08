# Sound Lighting

**A garage light with a little life in it.**

Rich color rolls along 32-foot WS2811 strips. Music gently lifts the glow.
The colors take their time. The room stays lit.

Built for a Raspberry Pi 4, with a Python program small enough to understand
and change in one sitting.

```text
                         ┌── AUX ──────────► Speaker
Laptop audio ────────────┤
                         └── Bluetooth ────► Pi ────► Addressable lights
```

**Experimental:** [Frequency-driven color](docs/spectrum.md) on `feature/spectral-color`.
A laptop FFT gives bass, mids, and highs their own colors; the Pi keeps its quiet
and standby behavior. Choose **Frequency + Auto** in the dashboard. A dedicated pane shows the frequency
balance and outgoing colors; palette options have swatches. Standby, Sound, and
Auto are visible buttons. Choose **Flow** for gentle ribbons or **Punch** for fast,
vivid musical contrast. Auto uses a **10-second** quiet window.
Adding another span? See the [dual-strip setup](docs/second-strip.md).

## Light it up

**On the `TUI` branch:** an Omarchy app for the whole room.
Press **SUPER+SPACE**, search **Sound Lighting**, and open it. Eight scenes, brightness and warm/cool sliders,
a separate color-picker window, and live sound/connection health follow your Pi.
If it is powered off, the app stays open and retries automatically.

```sh
# Install the app on Omarchy, using your existing SSH alias:
python3 tools/install_omarchy.py --host rpi4
```

Closing the dashboard leaves the lights running. [Dashboard guide →](docs/dashboard.md)

![Frequency controls on Omarchy](docs/images/spectrum.png)

Want it to run whenever the Pi is powered? [Install boot startup](docs/installation.md).

```sh
sudo bash install/install.sh
```

It starts in colorful standby and follows music when it arrives. Silence dims the
glow quickly, then colorful standby returns after **ten seconds of quiet**.
No desktop login or USB sound card needed. Existing installations retain their
saved timeout; use `sudo lights quiet 10` for this branch’s default.

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
**Sunset**, **Ocean**, **Ember**, and **Candy** add slow, saturated colorways on
this branch. The White slider tunes Workshop from warm to cool; its midpoint
preserves the original tint. Try `sudo lights white 25`.
**Custom**, on this branch, carries your chosen hue through slow motion and soft
sound response. Choose it in the picker, or run `sudo lights color '#ff2870'`.

Read the [daily controls and recovery guide](docs/operations.md), or the
[hardware/audio setup](docs/setup.md) for a fresh machine. Always stop the service
before starting a separate manual LED test. Normal shutdown clears the strip;
forced kills and power loss cannot guarantee clearing.

## What it feels like

- **Color that stays colorful.** Fully saturated bands, slowly drifting along the strip.
- **Music without the flicker.** Fast changes in sound soften into a gentle glow.
- **Light between songs.** A brief dim settles into colorful standby after ten seconds.
- **At home on Omarchy.** Launcher icon, your active theme, and automatic Pi reconnection.
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
| [remote_backend.py](tools/remote_backend.py) · [remote_agent.py](tools/remote_agent.py) | Reconnecting SSH control; no extra server port. |
| [legacy/](legacy/) | Earlier experiments, images, and iterations. Deprecated, preserved, visible. |

Python **3.13.5**, NumPy **2.2.4**, and `rpi_ws281x` **5.0.0** are the verified combination.
The existing `RpiLightStripCodes/` path stays stable for the running service.

Made by James Bruder.
