# Version notes

## Experimental · feature/spectral-color

**Two strips:** GPIO18 + GPIO13, 100 addressable groups each, one continuous
200-pixel canvas. Shared PWM driver, brightness, and shutdown cleanup. Opt-in
setup backs up system files and reserves PWM by disabling onboard analog audio;
Bluetooth/USB remain available. Reboot required; single-strip PCM stays the default.
Pi core checks passed (42 tests, six optional UI tests skipped). A 10-second live
test addressed each channel separately, exchanged colors, cleared both spans,
and released the controller before restarting the service. Failed initialization
never calls C hardware cleanup on an uninitialized controller.

**Punch:** Flow / Punch buttons in the Frequency pane. Punch adds six vivid hues,
strong musical contrast, 35/90 ms pixel smoothing, and up to 60 fps rendering.
Master brightness still caps output. Quiet feature frames stay dark; Flow remains
available. Band visualization follows the selected style. No additional Pi FFT.

**Checks:** 46 tests across core and optional UI environments on laptop and Pi;
10-second live Punch test saw all six bands and changing RGB output at the existing
40% cap. Clean service shutdown cleared LEDs and released capture resources.

**Wiring:** [Dual-strip setup](docs/second-strip.md), including common grounds,
separate positive rails, and the move from PCM to dual PWM.

**Controls:** Visible Standby / Sound / Auto buttons and Palette / Frequency color
selection. Auto uses ten seconds since last audio; Sound stays dim while silent.
White follows mode brightness and remains steady in Standby.

**Earlier checks:** 41 automated tests across core and optional UI environments; live pane,
mode controls, output preview, and preference restoration with one unchanged LED
PID. Auto correctly stayed reactive with ongoing audio; the 10-second silence
boundary is covered by the state-machine test.

**Visualization:** A dedicated conditional Frequency pane, six color-coded bands,
Hz ranges, smoothed Pi output preview, and 5 Hz telemetry. Palette dropdowns show
color swatches. Standby uses the chosen palette. Old Spectrum scenes migrate safely.


**Feature:** Spectrum scene; six musical frequency bands drive saturated color.
FFT runs on Omarchy, independently of the dashboard, with a small SSH feature feed.

**Resilience:** One packet in flight, expiring receiver challenges, 0.75-second
feature expiry, automatic capture/link retry, and rainbow fallback. Pi loudness
continues to control quiet dimming and standby. Existing scenes remain available.

**Capture fix:** Use the combine sink’s explicit Pulse monitor; direct PipeWire
capture failed to attach to the virtual node on this laptop.

**Timing:** 0.08 ms median laptop FFT benchmark; 42.67 ms windows, up to 20 Hz updates.
The TUI separates FFT cost, SSH RTT, and feature freshness. Sound/light alignment
remains uncalibrated. [Assessment, installation, and rollback →](docs/spectrum.md)

## 1.1.0-dev · TUI branch

**Color & feel:** Sunset, Ocean, Ember, and Candy palettes; eight picker presets;
mouse/keyboard brightness and warm/cool sliders. White stays steady, its midpoint
preserves Workshop, and rapid slider edits are coalesced. CLI: `lights white 0..100`.

**Audio timing:** 48 kHz / 16-bit mono, 21.33 ms analysis window, and a clearly
labeled 20 ms capture request. End-to-end latency remains explicitly unmeasured.

**Dashboard refinement:** Shorter labels, compact controls, btop panel colors and
graph gradient. All controls and statistics remain. Hyprland tiles the app normally
instead of forcing a floating window; narrow tiles stack the panels.

**Omarchy app:** SUPER+SPACE → Sound Lighting; app icon, native terminal window,
active theme colors, local dashboard, bounded SSH reconnects, offline countdown,
and acknowledged controls. Disconnected changes are not queued.

**Mute fix:** AUX, combined output, and the Pi feed now share mute/unmute without
changing volume levels. Silence dims the strip quickly, then standby returns after
four seconds. Workshop and forced Screensaver retain their ambient behavior.

**Fixed:** Status refresh preserves brightness drafts; dashboard exit waits for its
SSH child to be reaped. Launcher installation backs up and validates its window rule.

**Checks:** 31 tests across core and optional UI environments; actual SSH drop and
reconnection with controls restored; real mute → dim (~2s) → standby (~5s), then
unmute → sound reaction, all with one unchanged lighting PID.

**Features:** Live terminal dashboard; scene and screensaver controls; brightness;
separate color dialog with swatch and presets; animated Custom hue; signal history,
capture retries, peak/clipping counters, and Bluetooth route/USB detection.

**Behavior:** Controls update the existing service and persist across reboot.
Closing or canceling the dashboard leaves lighting alone. Textual is optional and
isolated from the LED engine. Narrow terminals scroll through stacked panels.

**Verified on the Pi:** 20 core/backend tests plus 3 optional UI interaction tests;
live Custom color at 70%, screensaver override, and preference restoration without
an engine PID change; real SSH terminal open/exit with lights and recorder still running.

**Limits:** Signal history samples at 1 Hz; audio routes at 5 seconds. Radio packet
loss and AUX/Bluetooth latency remain unmeasured. This branch is not a tagged
stable release. See the [dashboard guide](docs/dashboard.md), including rollback.

## 1.0.0 · 2026-09-07

### Features

- Three scenes: saturated Rainbow, drifting Aurora, and steady warm-white Workshop.
- `lights` CLI: scene, brightness, auto/idle mode, timeout, threshold, and live status.
- Validated settings persist across reboot and apply without restarting the driver.
- Smooth crossfades between scenes and brightness settings.
- Health status includes input availability, RMS, scene, mode, and settings errors.
- Optional laptop service keeps the paired AUX/Bluetooth audio route repaired.
- Upgrade preflight checks, configuration backups, and a documented rollback path.

### Fixes

- Rebuild stale combined audio routes when the Pi's Bluetooth endpoint changes.
- Select the music profile when a paired link returns without its playback sink.
- Invalid live settings keep the last good values; missing/restored settings recover.
- Installer refuses to ignore a failed service stop or overwrite an unrelated command.
- Installer preserves existing scene/brightness preferences.

### Verified for this release

- All 16 automated tests on the Pi, including settings rejection and recorder death/retry.
- Live scene and brightness changes with no lighting-process restart.
- Actual reboot: saved scene restored and laptop audio reconnected automatically.
- Live recorder termination: capture recovered while the same lighting PID stayed up.

### Supported scope

- The documented Pi 4, user `pi` / UID 1000, GBR WS2811 installation and PipeWire laptop.
- No claim of Bluetooth/AUX latency calibration, automatic current limiting, or
  multi-day endurance validation. Other hardware and layouts require adaptation.


## 0.2.0 · 2026-09-07

### Features

- Lights start at boot without a desktop login or connected audio source.
- Saturated idle animation starts immediately; music smoothly takes over.
- Fifteen seconds of quiet returns to idle; sound resumes reaction automatically.
- Dedicated virtual Bluetooth input removes the USB sound-card dependency.
- Versioned service/audio configuration, installer backups, and installation guide.

### Fixes

- Missing or disconnected audio no longer exits the LED program or freezes animation.
- Restart failed/stalled capture with a five-second retry interval.
- Refuse fallback to an unrelated capture device when the intended target is absent.
- Use a music-only Bluetooth receiver role to avoid headset-profile reconnections.
- Stop the recorder directly as the Pi user and preserve orderly service shutdown.

### Known limitations

- Bluetooth/AUX timing remains uncalibrated; the laptop helper may be needed after reboot.
- Installer targets the documented pi/UID 1000/repository layout.
- Very quiet audio may need a lower `--threshold`; persistent noise may need a higher one.
- No software current limiting. Power loss/SIGKILL cannot guarantee clearing.


### Verified

- Six automated tests on the Pi's Python 3.13 runtime.
- Real Bluetooth silence: idle after 15 seconds, sound mode restored automatically.
- Real reboot: service started in idle, recovered audio, and remained active with zero restarts.

## 0.1.0 · 2026-09-07

### Features

- Bluetooth audio from the laptop alongside wired speaker playback.
- Saturated bands with a slow, roughly 70-second color cycle.
- Smoothed music-driven brightness and a steady light floor between songs.
- Ten-second tests or continuous operation with `--seconds 0`.
- Warm white, garage gradients, chase, rainbow, and channel-check demos.
- One maintained live script; earlier experiments archived under `legacy/`.

### Fixes made during development

- Corrected the installed strip's color order to GBR.
- Used GPIO21 PCM to avoid GPIO18's onboard-audio conflict.
- Removed sudden bass-driven hue shifts and restored full saturation.
- Clear LEDs and release the native driver and recorder on normal shutdown.

### Known limitations

- Bluetooth introduces latency; synchronization with AUX is not calibrated.
- Capture uses the USB output monitor, not the microphone. Keep the USB card
  connected, even though it needs no aux cable.
- PipeWire/WirePlumber must run for user `pi`. Unattended boot startup and
  automatic Bluetooth reconnect are not configured.
- Loss of audio frames for three seconds stops the program and clears LEDs.
  Silence containing valid frames continues at the light floor.
- The laptop's combined output is temporary. Recreate it after an audio-server
  restart. The helper moves Chrome; other existing apps may need manual routing.
- Power loss, SIGKILL, or hardware/driver failure can prevent clearing.
- No automatic current limiting or power-supply sizing is provided.

### Verified

- Pi 4, Python 3.13.5, NumPy 2.2.4, rpi_ws281x 5.0.0.
- Live Bluetooth capture, repeated short LED tests, and continuous playback.
- Clean service stop and recorder/driver cleanup.

Earlier versions were experiments rather than releases. Their files and Git
history remain available in the [legacy archive](legacy/).
