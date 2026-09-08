# Setup & daily use

## The working arrangement

The Dell sends audio to its headphone jack and the paired Pi Bluetooth receiver.
The Pi routes incoming Bluetooth playback to `lighting_audio`, a virtual sink.
Python captures its monitor with `pw-record`. No USB card or aux cable is required.

For automatic startup and sound/idle transitions, follow [installation](installation.md).
This setup targets user `pi` and the existing repository path on the Pi.

## Hardware

Current installation: Raspberry Pi 4 and an ALITOVE WS2811 strip. The supplied
reel label confirms **24V DC, 10m (32.8ft), 60 LEDs/m, IP67, and 14.4W/m**.
That is **600 physical RGB LEDs**, but the matching
[manufacturer specification](https://alitove.com/products/alitove-ws2811-addressable-rgb-led-strip-light)
uses **100 WS2811 ICs, each controlling six LEDs together**. The existing
`--count 100` already addresses the full strip at its native resolution: one
independent color every 10cm (about 4 inches). A count of 600 would not unlock
individual control of those six LEDs. Two identical spans provide 200 independent
groups / 1,200 physical LEDs once the second output is implemented.

The reel label specifies **red = +24V, green = DIN, black = GND**; confirm the
input end using the strip arrows. Rated power totals **144W / 6A at 24V per reel**,
not a measured draw at the current animation/brightness. Each reel retains its
own 24V supply, with common DC grounds and separate positive rails. See the
[second-strip plan](second-strip.md).

```text
Pi breakout                      3.3V → 5V logic buffer
GPIO21 / physical 40 ───────────► input
                                 output ── 330Ω ──► Strip DIN
5V     / physical 2 ────────────► VCC
GND    / physical 39 ────┬──────► GND
                        ├─────────────────────────► Strip GND
LED supply negative ────┘
LED supply positive ──────────────────────────────► Strip V+
```

Use a non-inverting 5V buffer such as a properly enabled 74AHCT125. Match the LED
supply to the strip's printed voltage; WS2811 alone does not establish it. Power
the strip externally. Never feed the strip's 24V into the Pi. Wire with power disconnected;
connect DIN following the arrows. Size the supply and power wiring for the span.
Software brightness is not a current limiter.

The code uses GPIO21 PCM, DMA 10, 800 kHz, and GBR. Do not share PCM hardware with
an I2S device. See the [driver notes](https://github.com/jgarff/rpi_ws281x) and
[LED wiring guidance](https://learn.adafruit.com/adafruit-neopixel-uberguide/best-practices).

## Python

The configured Pi already has the packages. Check without initializing LEDs:

```sh
python3 --version
python3 -c 'import numpy, rpi_ws281x; print(numpy.__version__)'
command -v pw-record
```

A fresh installation needs PipeWire, WirePlumber, BlueZ, the PipeWire Bluetooth
plugin, and `pw-record`. Python dependencies are in `requirements.txt`. Use a
virtual environment instead of overriding distribution package management:

```sh
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install -r requirements.txt
```

If using that environment, substitute its absolute Python path in service commands.
The current service uses `/usr/bin/python3` and already-installed packages.

## Audio link

Enable Bluetooth on the Pi and pair the laptop using `bluetoothctl` on both ends.
Verify matching pairing codes and trust the intended device. Turn discoverability
off afterward. The Pi must offer A2DP Audio Sink. The
[WirePlumber docs](https://pipewire.pages.freedesktop.org/wireplumber/daemon/configuration/bluetooth.html)
explain roles and active-session ownership.

The boot installer enables the Pi user audio session through lingering and
configures Bluetooth audio for headless use. No desktop login is required.

On the laptop, get the paired Pi address with `bluetoothctl devices`, then:

```sh
python3 tools/connect_garage_audio.py --pi-address YOUR_PI_BLUETOOTH_ADDRESS
```

This creates `garage_dual`, selects it as default, and moves Chrome audio there.
It preserves wired volume and sets the Bluetooth branch to 100% for capture.
Other existing apps may need manual routing. The combined sink lasts for the
current PipeWire session; re-run the helper after an audio-server restart.
It installs no persistent desktop configuration.

Return the default to wired only with:

```sh
pactl set-default-sink alsa_output.pci-0000_00_1f.3.analog-stereo
```

Move existing application streams to that output too if needed.

## Run & stop

Stop any existing LED service before a manual LED test. Never run two GPIO drivers.

```sh
sudo systemctl stop addy-bluetooth.service
python3 RpiLightStripCodes/addy_bluetooth.py --audio-only --seconds 3
sudo python3 RpiLightStripCodes/addy_bluetooth.py --seconds 10
```

Use `--seconds 0` for continuous operation. GPIO access runs as root; recording
runs as `pi` against that user's PipeWire session. The default monitor target is:

```text
lighting_audio
```

Override with `--target NODE_NAME` after inspecting `wpctl status` or `pw-dump`.
The target must be the sink receiving Bluetooth playback.

Install the permanent boot service with `sudo bash install/install.sh`.
Then use:

```sh
sudo systemctl restart addy-bluetooth.service
sudo systemctl stop addy-bluetooth.service
sudo journalctl -u addy-bluetooth.service -n 15 --no-pager
```

It starts automatically at boot, displays idle color without audio, and switches
between sound and idle modes with a 15-second quiet timeout. See the
[installation guide](installation.md) for tuning and removal.

## Fast iteration

Keep changes in `RpiLightStripCodes/addy_bluetooth.py`. Validate syntax and audio
without GPIO while the old version runs. Replace the file atomically, then restart
the service. The old process clears and exits before its replacement starts.
Leave each version running until the next change.

Keep features, bug fixes, and documentation in focused commits. Update
`CHANGELOG.md` when behavior changes. Use `git revert` and restart the service to
return to a committed version without rewriting history. `legacy/` is reference
material, not a supported rollback target.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| No reaction | Music routed to `garage_dual`? Pi connected? Nonzero RMS in audio-only check? |
| Missing monitor | Check the Lighting Audio virtual sink and Pi user audio services. Inspect `wpctl status`. |
| No sound after reconnect | Re-run the laptop helper. Capture retries automatically; idle lights keep running. |
| Wrong colors | Current strip is GBR. Use demo red/green/blue modes to identify another strip. |
| Lights trail speaker | Bluetooth buffering; AUX synchronization is not calibrated. |
| Too bright | Lower `--brightness` (0–255). It caps brightness, not measured power. |

Use your own repository-local Git identity. No credentials or SSH keys are
stored in this repository.
