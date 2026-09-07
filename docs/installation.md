# Power on. Lights on.

From **0.2.0**, the Pi starts colorful, moving light at boot, even without a laptop,
Bluetooth connection, USB sound card, or desktop login.

When audio arrives, brightness smoothly starts following the music. On `TUI`, silence quickly dims the glow, then after **four seconds below the
sound threshold**, it blends back into the idle animation.
The colors keep flowing throughout. A connection opening by itself does not count
as sound.

## Install on this Pi

Supported layout: user `pi`, UID `1000`, repository at
`/home/pi/Sound-Lighting-Project`, system Python `/usr/bin/python3`.
GPIO21 / pin 40, GBR, 100 groups; confirm wiring and supply before enabling startup.
The existing paired laptop remains trusted; discoverability need not be enabled.

```sh
cd /home/pi/Sound-Lighting-Project
sudo bash install/install.sh
```

The installer checks dependencies, runs the test suite, validates existing settings, backs up files it replaces,
stops the old lighting process, and installs:

| Installed item | Purpose |
| --- | --- |
| `/etc/systemd/system/addy-bluetooth.service` | Starts continuous lighting at boot; restarts after unexpected failure. |
| `~pi/.config/pipewire/pipewire.conf.d/30-lighting-audio.conf` | Creates `lighting_audio`, a virtual sink independent of USB/HDMI devices. |
| `~pi/.config/wireplumber/wireplumber.conf.d/51-lighting-bluetooth.conf` | Enables headless A2DP receiving and routes Bluetooth playback to the virtual sink. |
| `/etc/sound-lighting.json` | Saved scene, brightness, behavior, timeout, and threshold; preserved on reinstall. |
| `/usr/local/bin/lights` | Live control and status command. |
| `loginctl enable-linger pi` | Starts and retains the Pi user's audio services without a desktop login. |

It enables Bluetooth and Pi user audio services, restarts audio, and enables the
lighting service. This briefly interrupts lights and the Bluetooth link. Existing
configuration is backed up under `/var/backups/sound-lighting/DATE-TIME/`.

This is deliberately a Pi-specific installer. For another username, UID, repository
path, or Python environment, adapt the service and installer first. Install the
requirements described in [setup](setup.md) on a fresh OS. If Bluetooth was disabled
with a `disable-bt` boot overlay, remove that setting and reboot before using audio.

## What happens when sound disappears?

```text
Boot ──► colorful idle animation
               │
          sound detected
               ▼
         music-reactive glow
               │
         quick dim
               │
        4 seconds of quiet
               └──────────────► colorful idle animation
```

Transitions blend over roughly a few seconds. Sound can return at any point.
The LED render loop runs independently at about 30 frames/second. Missing devices,
audio-server restarts, stalled capture, and silent streams never intentionally
black out the strip. Capture retries every five seconds when unavailable.

Only **actual sampled loudness** above the configured RMS threshold resets the
quiet timer. The default `0.003` is about −50 dBFS. Raise it if background noise
keeps triggering sound mode; lower it for quieter source audio.

## Laptop playback

Keep the AUX speaker connected. After pairing, run on the laptop:

```sh
python3 tools/connect_garage_audio.py --pi-address YOUR_PI_BLUETOOTH_ADDRESS
```

This restores AUX plus Bluetooth output. Add `--watch` for automatic repair, or
install the user service described in [operations](operations.md). Otherwise re-run after a laptop audio restart or
if the link does not reconnect following a Pi reboot. The lights do not depend on
this reconnect succeeding: they remain in idle mode until sound actually arrives.
The Pi records `lighting_audio`; the USB card is no longer required.

## Daily controls

```sh
sudo systemctl status addy-bluetooth.service
sudo systemctl restart addy-bluetooth.service
sudo systemctl stop addy-bluetooth.service
sudo journalctl -u addy-bluetooth.service -n 20 --no-pager
```

Logs say `Mode: idle` or `Mode: sound` at each transition. Stop clears the LEDs and
releases capture and driver resources. The service uses `KillMode=mixed` so its
main process can finish cleanup before systemd resorts to killing children.

A normal `stop` leaves boot startup enabled. To keep it off across reboots:

```sh
sudo systemctl disable --now addy-bluetooth.service
```

To restore startup:

```sh
sudo systemctl enable --now addy-bluetooth.service
```

## Tune without restarting

```sh
sudo lights scene rainbow
sudo lights brightness 80
sudo lights quiet 4
sudo lights threshold 0.003
lights status
```

Settings are validated, written atomically, and applied live from
`/etc/sound-lighting.json`. Do not add a second process or a service override for
these everyday controls. For different hardware count or capture target, update
the service deliberately. See [operations](operations.md) for scenes, recovery,
laptop reconnect automation, and upgrade/rollback instructions.

## Remove the startup setup

Disable and stop the service; remove `/etc/systemd/system/addy-bluetooth.service`
and the two specifically named user audio configuration files above, then run
`sudo systemctl daemon-reload` and restart the Pi user's audio services. Restore
previous files from the installer backup if they existed. If lingering was
previously off and nothing else needs it, run `sudo loginctl disable-linger pi`.
Remove `/usr/local/bin/lights` if no longer needed. Preserve or remove
`/etc/sound-lighting.json` according to whether you want to keep your preferences.
Pairing records and other audio settings are retained.

## Validation

```sh
python3 -m unittest discover -s tests -v
python3 RpiLightStripCodes/addy_bluetooth.py --audio-only --seconds 10
systemctl is-enabled addy-bluetooth.service
loginctl show-user pi -p Linger
```

The tests cover the exact quiet boundary, sound return, noise rejection, gradual
crossfade, and colorful, bounded output. Hardware checks should also include
silencing/restoring the Bluetooth feed and a real reboot. Do not use forced power
removal to test shutdown; loss of power or SIGKILL cannot guarantee clearing.
