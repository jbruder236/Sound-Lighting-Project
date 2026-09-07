# The room, at a glance

The `TUI` branch adds a terminal remote to the existing light service. One process
still owns GPIO. Opening a dashboard starts no recorder, changing a control needs
no restart, and closing it leaves the lights on.

## Open it

On this Omarchy laptop:

```sh
ssh -t rpi4 'sudo lights tui'
```

On the Pi: `sudo lights tui`. For observation only: `lights tui --read-only`.
Use a terminal around **110 columns × 40 rows** for the full view. Narrower windows
stack the panels; scroll or Tab to reach the remaining controls.

| Control | What happens |
| --- | --- |
| Scene | Rainbow, Aurora, steady Workshop, or your Custom hue. |
| Behavior / A / S | Auto follows sound; Screensaver keeps the idle animation. Workshop stays steady. |
| Brightness | Enter 0–100 and press Enter or Set; −10/+10 makes quick adjustments. Zero stays dark, including after reboot. |
| Pick color / C | A separate dialog with a hex field, live swatch, and four presets. Save selects Custom. Cancel or Escape changes nothing. |
| Q | Close only the dashboard. |

The custom scene uses the existing slow waves and gentle sound response. It holds
the hue you picked; brightness still varies across the span. Workshop is the
constant utility-light option. The terminal swatch is an approximation of the LEDs.
Saved settings apply within a second and fade smoothly. The top strip shows what
the engine has actually applied; form fields are loaded when the dashboard opens
and after its own changes. CLI changes appear in live status too.

## Read the room

- **Sound reactive / Screensaver:** actual engine state, with the remaining quiet
  timeout. The existing default is 15 seconds.
- **Signal:** RMS level in dBFS, a −60 to 0 dBFS meter, and 60 seconds of relative
  history sampled once per second. Fast transients between status updates may be missed.
- **Capture:** frames arriving, configured 48 kHz mono, retry count, analyzed
  windows, largest observed sample peak, and windows containing near-clipping samples.
  These counters start over with the engine. Windows are sampled for analysis;
  they are not a packet count or a guarantee of detecting every clipped sample.
- **Connection:** connected Bluetooth audio peers and the active PipeWire route
  into the lighting sink, checked every five seconds. USB presence is reported
  separately; the dashboard does not route USB audio.
- **Runtime:** engine/recorder PIDs, uptime, and last captured frame age. Missing
  or more than five-second-old status is marked offline/stale. Saved controls can
  still be changed while offline, but take effect only when the engine returns.

An open capture sink can produce silent frames without a connected laptop.
Bluetooth connected, routed audio, and audible signal are separate observations.
End-to-end latency, radio packet loss, and the AUX/Bluetooth timing offset are not
measured. Audio inspection failures appear on the dashboard and retry automatically.

## Install the optional interface

From a clean checkout on the supported Pi layout:

```sh
cd /home/pi/Sound-Lighting-Project
git fetch origin
git switch TUI
git pull --ff-only
sudo bash install/install.sh
bash install/install-tui.sh
sudo lights tui
```

The core install briefly restarts audio and lighting. The optional installer does
not interrupt either. It pins Textual in
`/home/pi/.local/share/sound-lighting/tui-venv`, runs the dashboard tests, and installs
the `lights tui` launcher. The LED service keeps its existing system Python,
NumPy, and WS2811 library. `python3-venv` is required to create the environment.

The UI consists of `tools/dashboard.py`, `tools/dashboard.tcss`, and
`tools/dashboard_data.py`. It imports shared settings validation and reads the
engine's status JSON. PipeWire inspection runs as `pi`, even when the dashboard
runs under sudo, and its short-lived subprocess is reaped on timeout or exit.

## Test without touching the strip

```sh
python3 -m unittest discover -s tests
~/.local/share/sound-lighting/tui-venv/bin/python -m unittest discover -s tests -p test_dashboard.py
```

The core suite skips optional UI interactions when Textual is absent; the second
command runs those interactions in a headless terminal against temporary settings.
The suite checks preserved preferences, brightness validation, color save/cancel,
read-only behavior, stale status, connection-versus-route detection, custom hue
rendering, and recorder cleanup/retry.

## Return to 1.0

The new `color` setting and Custom scene are specific to this branch. Back up your
settings and remove that field before returning to `master`:

```sh
cd /home/pi/Sound-Lighting-Project
sudo cp /etc/sound-lighting.json /etc/sound-lighting.tui-backup.json
sudo env PYTHONPATH=RpiLightStripCodes python3 - <<'PY'
import json
from pathlib import Path
from settings import atomic_json
path = Path('/etc/sound-lighting.json')
settings = json.loads(path.read_text())
settings.pop('color', None)
if settings.get('scene') == 'custom':
    settings['scene'] = 'rainbow'
atomic_json(path, settings)
PY
sudo systemctl stop addy-bluetooth.service
git switch master
sudo bash install/install.sh
```

The dashboard environment can remain installed for your next visit to `TUI`.
