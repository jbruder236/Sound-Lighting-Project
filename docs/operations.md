# A light you can live with

v1.0 supports the documented Pi 4 installation, its GBR WS2811 strip, and the
PipeWire laptop-to-Pi audio link. The defaults keep the approved saturated Rainbow
scene. The `TUI` branch adds a quick dim followed by standby after four seconds
of silence; the tagged v1.0 default remains 15 seconds.

## Change the mood

On the Pi, after installation:

```sh
lights status
sudo lights scene rainbow
sudo lights scene aurora
sudo lights scene workshop
sudo lights brightness 80
sudo lights mode idle
sudo lights mode auto
sudo lights quiet 4
sudo lights threshold 0.003
```

| Scene | Feel |
| --- | --- |
| Rainbow | The original saturated bands, slowly moving along the full span. |
| Aurora | Broad cyan, blue, and violet curtains, drifting at different speeds. |
| Workshop | Steady warm-white utility light, unaffected by the music. |

Changes apply within a second and fade over roughly two seconds. Brightness is a
percentage here; the engine's `--brightness` argument remains 0–255. Settings are
saved in `/etc/sound-lighting.json` and survive restarts, upgrades, and reboots.
Installer defaults never overwrite an existing settings file.

`mode idle` keeps animation but ignores audio. `mode auto` returns to automatic
sound detection. Workshop remains steady in either mode. Brightness 0 intentionally
turns output dark; it is saved too. To stop the process and clear the strip, use
`sudo systemctl stop addy-bluetooth.service`.

Manual LED tests still require stopping the background service first. The `lights`
commands change settings in the single running process; they never start a second
driver.

## Know what is happening

`lights status` reports the running version, scene, brightness, audio availability,
RMS level, mode, timeout, and uptime. `lights status --json` is available for tools.
A status older than five seconds is marked **STALE** and returns a nonzero exit code.
No status file means the service is stopped, starting, or not installed.

`input receiving` means audio frames are arriving; they may contain silence.
`mode sound` means recent samples crossed the loudness threshold. `input waiting`
means capture has not yet established a healthy stream. Idle animation continues.

Useful diagnostics:

```sh
lights config
lights status --json
sudo systemctl status addy-bluetooth.service
sudo journalctl -u addy-bluetooth.service -n 30 --no-pager
wpctl status
```

Settings are strictly validated. Malformed live edits retain the last good in-memory
settings and report the error in status. Use the CLI for atomic, validated writes.
An invalid file at startup is rejected; repair it before restarting. A settings
error is not a reason to keep blindly restarting the service.

## Automatic laptop reconnection

The helper can repair the existing paired link and combined AUX/Bluetooth sink:

```sh
python3 tools/connect_garage_audio.py --pi-address YOUR_PI_BLUETOOTH_ADDRESS --watch
```

It checks every 15 seconds, reconnects when the Pi returns, selects A2DP when
needed, and rebuilds the combined sink if the Bluetooth endpoint changes.
It preserves the physical speaker’s volume. The `TUI` helper synchronizes mute
and unmute across AUX, the combined sink, and the Pi feed every half-second, so
Omarchy’s physical-output mute also silences the light input. It routes real
application playback streams into `garage_dual` while active, including new apps.
It does not pair unknown devices or enable discovery.

To run it automatically in the laptop's user session, create
`~/.config/sound-lighting/audio-link.env`:

```ini
LIGHTING_REPO=/absolute/path/to/Sound-Lighting-Project
PI_BLUETOOTH_ADDRESS=AA:BB:CC:DD:EE:FF
```

Then, on that laptop, from the repository:

```sh
mkdir -p ~/.config/systemd/user
cp install/garage-audio-link.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now garage-audio-link.service
```

Create `~/.config/sound-lighting/` before writing the environment file. The helper
defaults to the Dell's analog sink; use `--wired` for another device in a custom unit.
The installed Omarchy instance uses `/home/gbot/Work/sound-lighting` and the paired Pi.

To stop enforcing this audio route:

```sh
systemctl --user disable --now garage-audio-link.service
```

Stopping the watcher leaves the current audio route in place. Select another output
normally or run the wired-only command in the setup guide. Bluetooth/AUX latency
is still not calibrated; reconnection is not a promise of sample-accurate sync.

## Upgrade without losing your choices

On the Pi:

```sh
cd /home/pi/Sound-Lighting-Project
git status --short
git pull --ff-only
sudo bash install/install.sh
lights status
```

Resolve local changes before pulling. The installer runs tests and validates the
service and existing settings before stopping the lights. It checks the `lights`
command is not owned by another program, preserves existing settings, and backs
up replaced configuration under `/var/backups/sound-lighting/DATE-TIME/`.
Audio and lights briefly restart during installation. Use `lights` for everyday
adjustments; reinstall only for code/service upgrades.

For a code-only change, validate it, replace files, and use
`sudo systemctl restart addy-bluetooth.service`. For changing settings, no restart.

## Roll back

For a bug in a new commit, use `git revert` to preserve history, then reinstall if
service files changed. To temporarily return this installation to the previous
release, first ensure the working tree is clean:

```sh
sudo systemctl stop addy-bluetooth.service
git switch --detach v0.2.0
sudo bash install/install.sh
```

v0.2.0 does not have the `lights` CLI or scene settings; use `systemctl` controls.
The v1.0 settings file can remain for a future upgrade. To return, switch back to
`master` and rerun the installer. Older legacy experiments are not a supported
rollback target.

## Release standard

A release must pass automated tests, live controls without a PID change, safe
recorder shutdown/recovery, sound-to-idle switching, and reboot startup. The repo
keeps focused feature/fix/docs commits and tagged versions. A short release test
is not a multi-day endurance test; hardware power and signal quality still matter.
