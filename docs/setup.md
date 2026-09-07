# Setup & daily use

## The working arrangement

The Dell runs PipeWire and sends audio to its headphone jack and the paired Pi
Bluetooth receiver. On the Pi, WirePlumber routes incoming Bluetooth playback to
the USB audio output. Python captures that output's monitor with `pw-record`.
It does not read the USB microphone: no splitter or second aux cable is needed.

This documents the working installation. Device names and the `pi` username are
specific to it; this is not a universal installer.

## Hardware

Current installation: Raspberry Pi 4, a 32-foot WS2811 span, 100 addressable groups.
Check the actual IC/group count for another strip; several LEDs may form one group.

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
the strip externally. Never feed 12V into the Pi. Wire with power disconnected;
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

The current Pi uses its existing logged-in user audio session. No lingering,
headless audio-policy override, or boot service has been installed.

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
alsa_output.usb-C-Media_Electronics_Inc._USB_Audio_Device-00.analog-stereo
```

Override with `--target NODE_NAME` after inspecting `wpctl status` or `pw-dump`.
The target must be the sink receiving Bluetooth playback.

Create the temporary background service if it is not already loaded:

```sh
sudo systemd-run --unit=addy-bluetooth \
  --property=KillSignal=SIGTERM --property=TimeoutStopSec=8 \
  /usr/bin/python3 /home/pi/Sound-Lighting-Project/RpiLightStripCodes/addy_bluetooth.py \
  --seconds 0
```

This does not enable boot startup. Once created:

```sh
sudo systemctl restart addy-bluetooth.service
sudo systemctl stop addy-bluetooth.service
sudo journalctl -u addy-bluetooth.service -n 15 --no-pager
```

If systemd has unloaded the stopped transient unit, create it again with
`systemd-run` rather than `restart`.

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
| Missing monitor | Keep the USB card connected and Pi user audio session active. Inspect `wpctl status`. |
| Stops after disconnection | Reconnect audio, then restart. Automatic reconnect is not implemented. |
| Wrong colors | Current strip is GBR. Use demo red/green/blue modes to identify another strip. |
| Lights trail speaker | Bluetooth buffering; AUX synchronization is not calibrated. |
| Too bright | Lower `--brightness` (0–255). It caps brightness, not measured power. |

Use your own repository-local Git identity. No credentials or SSH keys are
stored in this repository.
