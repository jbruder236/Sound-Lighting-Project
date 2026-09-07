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

On the configured Pi, from this repository:

```sh
# Listen to incoming audio without driving LEDs.
python3 RpiLightStripCodes/addy_bluetooth.py --audio-only --seconds 3

# Run until Ctrl-C.
sudo python3 RpiLightStripCodes/addy_bluetooth.py --seconds 0
```

**Only one lighting process at a time.** If the background service is running,
stop it before a manual LED test:

```sh
sudo systemctl stop addy-bluetooth.service
```

The default test lasts 10 seconds. Normal shutdown clears the strip and releases
its recorder and driver. Forced kills and power loss cannot guarantee clearing.

New machine? Start with the [setup guide](docs/setup.md). For sound-free lighting,
try `sudo python3 RpiLightStripCodes/addy_demo.py --mode garage` after stopping the service.

## What it feels like

- **Color that stays colorful.** Fully saturated bands, slowly drifting along the strip.
- **Music without the flicker.** Fast changes in sound soften into a gentle glow.
- **Light between songs.** A brightness floor keeps silent audio from blacking out the room.
- **A cord less.** AUX feeds the speaker while Bluetooth carries the same audio to the Pi.
- **Quick experiments.** One live file, a short restart, and each version stays on until replaced.

## On the bench · 0.1.0

| | Notes |
| --- | --- |
| Features | Bluetooth input, smooth rainbow flow, continuous operation, standalone utility-light demos. |
| Fixed during tuning | Wrong color order; washed-out colors; abrupt audio-driven hue changes; explicit shutdown cleanup. |
| Known limitations | Bluetooth timing is not calibrated to AUX. Requires the Pi's active user audio session and connected USB card. No automatic reconnect or boot startup. |

Current wiring: **GPIO21 / physical pin 40**, **GBR**, **100 addressable groups**.
Group count is not necessarily the number of physical LEDs. Brightness is capped
at 255; the animation varies individual channel levels below that ceiling.

See [version notes](CHANGELOG.md) for the concise release history.

## Small by design

| File | Purpose |
| --- | --- |
| [addy_bluetooth.py](RpiLightStripCodes/addy_bluetooth.py) | The live, sound-reactive lighting program. |
| [addy_demo.py](RpiLightStripCodes/addy_demo.py) | Utility light, color checks, and sound-free patterns. |
| [connect_garage_audio.py](tools/connect_garage_audio.py) | Restore the laptop's combined AUX/Bluetooth output. |
| [legacy/](legacy/) | Earlier experiments, images, and iterations. Deprecated, preserved, visible. |

Python **3.13.5**, NumPy **2.2.4**, and `rpi_ws281x` **5.0.0** are the verified combination.
The existing `RpiLightStripCodes/` path stays stable for the running service.

Made by James Bruder.
