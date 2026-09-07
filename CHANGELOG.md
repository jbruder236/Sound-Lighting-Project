# Version notes

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
