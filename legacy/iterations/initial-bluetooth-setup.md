# Garage audio and lights

Verified 2026-09-07: Chrome -> garage_dual -> Dell headphone jack and Pi Bluetooth A2DP.
The Pi captures the monitor of its USB audio output, where WirePlumber routes incoming
Bluetooth playback. This needs no aux cable or microphone input. The USB card must
remain connected for this specific monitor target. Pi's existing graphical user audio
session supplies PipeWire/WirePlumber; no lingering or unattended-startup policy added.

## Run

On the Dell, reconnect/recreate the temporary combined audio output if needed:

```sh
python3 /home/gbot/Work/rpi-lighting/connect_garage_audio.py
```

Run a 10-second sound-reactive test:

```sh
ssh rpi4 'sudo -n python3 /home/pi/Sound-Lighting-Project/RpiLightStripCodes/addy_bluetooth.py --seconds 10'
```

Use --seconds 0 only when continuous operation is intended. Default LED count 100,
GPIO21 (physical 40), GBR, brightness 255. Captures mono 48 kHz signed 16-bit PCM.
Normal completion, Ctrl-C, SIGTERM and SIGHUP clear LEDs and release DMA and the
recorder process. Forced kill/power loss cannot guarantee LED clearing.

The new script takes inspiration from the repository's amplitude smoothing and FFT
examples. Original scripts were preserved; they still select their original audio
devices/pins and should not be run unchanged for this setup.

## Connection

- Dell Bluetooth: 20:79:18:B9:36:32
- Pi Bluetooth: DC:A6:32:04:6E:C9
- Paired and trusted; discoverability turned off after pairing.
- Pi Bluetooth service re-enabled; disable-bt boot overlay removed.
- Desktop combined sink is temporary (recreate after PipeWire restart).
- Bluetooth adds latency relative to aux; synchronization has not been calibrated.

The ten-second LED test received 233 audio blocks, peak 0.380 of full scale,
cleared LEDs, and left no pw-record or addy_bluetooth process running.

References: https://pipewire.pages.freedesktop.org/wireplumber/daemon/configuration/bluetooth.html
and https://pipewire.pages.freedesktop.org/pipewire/page_pulse_modules.html
