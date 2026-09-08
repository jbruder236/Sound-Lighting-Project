# Color that listens

`feature/spectral-color` builds on `TUI`. Select **Frequency** under **Color follows** in the dashboard,
with **Auto** or **Sound** enabled, to let musical frequency balance shape the strip’s color.
Choose **Flow** for the existing gentle look or **Punch** for faster, stronger musical contrast.
The master brightness slider caps both styles.

## Is it viable?

Yes. On this XPS, a 2,048-sample Hann-windowed FFT benchmark measured **0.08 ms
median, 0.15 ms p95** over 2,000 windows. At 20 updates per second, FFT work alone
uses roughly 0.2% of one core. Capture, Python scheduling, and SSH cost extra.
The same benchmark on this Pi 4 measured **0.54 ms median, 0.60 ms p95**
(about 1.1% of one core for FFT work at 20 Hz). Both machines can handle it;
offloading leaves the renderer simpler, but the FFT itself was not a major
latency risk. These are short synthetic compute benchmarks, not endurance tests.

The laptop uses `parec` (from `libpulse` on Omarchy) to capture the explicit
`garage_dual.monitor` through PipeWire’s PulseAudio compatibility server at
**48 kHz / 16-bit mono**. Direct `pw-record` capture could not attach to this
virtual combine sink during the live check.
A window covers **42.67 ms**, with **23.44 Hz bin spacing**, and updates arrive at
most every **50 ms**. The [NumPy real FFT](https://numpy.org/doc/stable/reference/generated/numpy.fft.rfft.html)
provides the spectrum; a Hann window reduces leakage between neighboring bins.
These windows are separate from the Pi’s existing 21.33 ms loudness analysis.

Six broad bands handle mixed music better than assigning the loudest FFT bin a
MIDI note. Harmonics, chords, and percussion make that bin an unreliable estimate
of the fundamental. This mode represents tonal balance; it does not identify
notes, instruments, key, or emotion. Colors are an artistic mapping:

| Band | Frequencies | Color |
| --- | --- | --- |
| Bass | 40–160 Hz | Amber |
| Body | 160–400 Hz | Orange |
| Mids | 400 Hz–1 kHz | Pink |
| Lead | 1–2.5 kHz | Violet |
| Air | 2.5–6 kHz | Blue |
| Shine | 6–12 kHz | Cyan |

Energy is summed per band and square-root compressed so quieter parts can share
the palette. Broad regions of the strip favor neighboring bands; stronger bands
spread farther across it. Saturation stays high, and the existing 0.65-second
pixel smoothing softens changes. This describes **Flow**, the default style. DC and very quiet input do not steer the color.

## Flow / Punch

The Frequency pane has two style buttons and a **Punch** amount slider; Standby / Sound / Auto remain the three
operating modes. **Punch** maps bass → red, body → gold, mids → green, lead → cyan,
air → blue, and shine → magenta. Strong bands claim colored regions across the
span. Broader overlapping regions and gentler band emphasis reduce abrupt color
takeovers. Reduced hue variation and a softer brightness curve calm the movement
without slowing the attack; there is no timed strobe.

At the default **50% Punch**, laptop RMS controls a fast adaptive envelope
(25 ms attack, 160 ms release), with
stronger contrast from roughly 2.5% to 100% of the master cap. Per-pixel smoothing
uses 35 ms on rising channels and 90 ms on falling channels, versus Flow's 650 ms.
These are filter time constants, **not measured end-to-end latency**. Punch renders
at up to 60 fps; the existing FFT feed remains up to 20 Hz with 42.67 ms windows.
No extra FFT runs on the Pi. Timing still includes capture, SSH, and Bluetooth.

**Punch amount** ranges from **0 (gentle)** through **50 (balanced)** to **100 (most vivid)**. It changes band emphasis, region
width, hue variation, brightness contrast, and release (200–120 ms). Low amounts now also smooth the frequency bands and
limit color speed separately from brightness: near 0, colors move at about 36°
of hue per second with a 700 ms band filter; near 100, color response is much
faster. Near-neutral mixtures keep their previous hue instead of amplifying tiny
spectrum changes into saturated color jumps. Low amounts compress brightness
swings and keep the spatial glow more even. Silent input still dims normally.
The 25 ms
brightness attack and 35/90 ms pixel filters stay constant. Zero is gentle reactive lighting,
not off; master brightness remains the output cap. Amount changes glide over a
120 ms time constant. The saved integer `punch` defaults to 50 in older configs.

Sliders send coalesced live updates during dragging and persist the final value.
The Pi checks settings every 100 ms; SSH and existing brightness fades still add
delay. Adjusting Punch preserves Flow/Punch selection, operating mode, and brightness.

Quiet feature frames remain dark instead of briefly flashing the standby palette.
Missing/expired features fade back to the selected palette; Pi audio still controls
mute dimming and the Auto timeout. Switching styles preserves mode, palette, and
brightness. `frequency_style` persists as `flow` or `punch`; older settings default
to Flow. Standby remains the selected ambient palette in either style.

## Three modes, one visible control row

- **Standby:** the selected palette keeps moving; White stays steady.
- **Sound:** reacts to audio and stays in sound mode. Silence dims to the existing
  low glow; it does not automatically return to standby.
- **Auto:** sound heard within the last **10 seconds** keeps sound mode selected.
  Silence dims quickly, then the chosen standby palette returns at the timeout.
  New audio switches back immediately. `lights quiet` can customize the timeout.

**Color follows: Palette / Frequency** is separate from operating mode. Frequency
opens its own pane, showing six colored band shares and Hz ranges, the actual
sampled Pi color commands, and whether audio or the standby palette is controlling
output. These are up to **5 Hz snapshots** of a 20 Hz feature feed and 30 Hz (Flow) / 60 Hz (Punch)
renderer. RGB preview includes smoothing and master brightness; terminal color
is approximate and does not measure the strip. Stale telemetry clears the preview.

The palette picker displays a row of color swatches for every option. Picking
another standby palette while Frequency is enabled does not disable Frequency;
choosing a custom color or moving the white slider explicitly selects Palette.

![Frequency pane preview](images/spectrum.png)

## The path

```text
                     ┌─ AUX → speaker
Laptop garage_dual ──┼─ Bluetooth → Pi loudness → brightness / quiet / standby
                     └─ monitor → laptop FFT → six band weights over SSH
                                                   ↓
                                          Pi color blend → LEDs
```

The FFT runs in a separate laptop user service, independent of the dashboard.
Only small feature packets cross SSH, up to 20 per second. The Pi receiver writes
a bounded JSON document to `/run/sound-lighting/spectrum.json` (RAM), and the LED
process reads at most 20 times per second. No FFT, GPIO access, new listening
port, or per-frame persistent-settings write occurs in the receiver.

Only one packet is in flight. Each needs a fresh receiver challenge, which expires
after 0.5 seconds; buffered packets arriving after a stall are rejected. Received
features expire after 0.75 seconds using the **Pi’s monotonic clock**, so laptop
clock differences cannot make them appear fresh. Missing capture, SSH loss, or
an absent laptop yields a smooth fallback to the selected palette. Capture and SSH retry after
five seconds; normal shutdown terminates and reaps both children.

The Pi’s local audio signal continues to decide dimming and standby. **Auto** and **Sound**
allow spectral colors while sound is present; standby and missing features use
the selected palette. White stays uniform and follows mode brightness like other palettes. Changing scenes
does not stop the optional laptop publisher; disable its service if unwanted.

## Timing is not synchronization

The dashboard reports FFT compute time, recent **SSH request/acknowledgement RTT**,
and age since the Pi received the features. These are not sound-to-light latency.
SSH RTT includes receiver processing. The laptop’s `parec --latency-msec=20` capture request
is not a measurement of the entire route either.

Local features bypass Bluetooth buffering and may precede the Pi’s audio signal.
The analysis window, 20 Hz cadence, network jitter, and deliberately slow visual
smoothing all affect the result. We have not calibrated AUX/audio/light alignment.
Offloading avoids adding FFT work to the LED loop, but cannot guarantee lower
end-to-end latency. A future synchronized test could inform an optional color delay.

## Install and try it

First update the Pi checkout to `feature/spectral-color`. Deploy the new engine
and receiver together, then restart the single driver once:

```sh
cd /home/pi/Sound-Lighting-Project
git fetch origin
git switch feature/spectral-color
git pull --ff-only
sudo systemctl restart addy-bluetooth.service
```

On the laptop, from the matching checkout:

```sh
bash install/install-spectrum.sh
systemctl --user status sound-lighting-spectrum.service
```

This installs NumPy into `~/.local/share/sound-lighting/spectrum-venv`; the Pi keeps
its existing Python and dependencies. Endpoints live in
`~/.config/sound-lighting/spectrum.env` (default `rpi4`, the existing Pi checkout,
and `garage_dual`). Existing endpoint customizations survive reinstallation.
The enabled user unit starts with the laptop session and reconnects when the Pi
returns. It does not select a scene or alter laptop routing/volume/mute.

Reopen **SUPER+SPACE → Sound Lighting**, select **Frequency**, and choose **Auto**.
Alternatively, on the Pi:

```sh
sudo lights source spectrum
sudo lights mode auto
sudo lights quiet 10
```

Play music. The Frequency pane shows the band balance, a strip preview, local FFT duration,
SSH RTT, and feature freshness. If the feed is unavailable it explicitly shows fallback.
For logs: `journalctl --user -u sound-lighting-spectrum.service -n 30`.

## Return to TUI

```sh
# Laptop
systemctl --user disable --now sound-lighting-spectrum.service
# Pi: migrate settings before returning to the older TUI code.
cd /home/pi/Sound-Lighting-Project
sudo cp /etc/sound-lighting.json /etc/sound-lighting.frequency-backup.json
sudo env PYTHONPATH=RpiLightStripCodes python3 - <<'PY'
import json
from pathlib import Path
from settings import atomic_json
p = Path('/etc/sound-lighting.json')
settings = json.loads(p.read_text())
settings.pop('color_source', None)
settings.pop('frequency_style', None)
settings.pop('punch', None)
if settings.get('behavior') == 'sound':
    settings['behavior'] = 'auto'
if settings.get('scene') == 'spectrum':
    settings['scene'] = 'rainbow'
atomic_json(p, settings)
PY
git switch TUI
sudo systemctl restart addy-bluetooth.service
# Laptop checkout, then reopen the app:
git switch TUI
```

This branch adds `color_source`, `frequency_style`, `punch`, and the `sound` behavior. Legacy `scene: spectrum`
settings migrate to a Rainbow standby palette with Frequency enabled.
The expired feature file is harmless on TUI. The optional environment may remain.

## Live check on this setup

A 12-second sequence of 90 Hz, 700 Hz, and 4 kHz tones arrived as Bass, Mids,
and Air. Observed FFT compute time was 0.15–0.23 ms; sampled SSH RTT ranged
from 5.7–110.8 ms. Stopping the publisher expired the feature feed; restarting
it recovered, with the same LED process. The prior scene/mode was restored.
These are short-run observations, not a latency guarantee.

## Check it without hardware

```sh
# Environment with NumPy (Pi system Python or the laptop spectrum venv)
python -m unittest discover -s tests -p test_spectrum.py
```

Known tones and mixtures verify band mapping, volume/DC invariance, and silence.
Tests also cover bad packets, clock/TTL handling, warm/cool output, idle fallback,
expired network challenges, capture recovery, and child-process cleanup.
