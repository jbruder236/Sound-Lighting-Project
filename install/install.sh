#!/usr/bin/env bash
# Install on the supported Pi layout. Run: sudo bash install/install.sh
set -euo pipefail
repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
if [[ $EUID -ne 0 || "$repo_root" != /home/pi/Sound-Lighting-Project ]]; then
  echo 'Run with sudo from the repository at /home/pi/Sound-Lighting-Project.' >&2
  exit 1
fi
pi_uid=$(id -u pi)
if [[ "$pi_uid" != 1000 ]]; then
  echo 'This service template expects pi with UID 1000; adjust the template first.' >&2
  exit 1
fi
/usr/bin/python3 -c 'import numpy, rpi_ws281x'
command -v pw-record >/dev/null
command -v wireplumber >/dev/null
backup_dir="/var/backups/sound-lighting/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$backup_dir"
for config_path in /etc/systemd/system/addy-bluetooth.service \
  /home/pi/.config/pipewire/pipewire.conf.d/30-lighting-audio.conf \
  /home/pi/.config/wireplumber/wireplumber.conf.d/51-lighting-bluetooth.conf; do
  if [[ -f "$config_path" ]]; then cp --parents -a "$config_path" "$backup_dir/"; fi
done
loginctl show-user pi -p Linger > "$backup_dir/previous-linger.txt"
systemctl stop addy-bluetooth.service 2>/dev/null || true
install -d -o pi -g pi /home/pi/.config/pipewire/pipewire.conf.d \
  /home/pi/.config/wireplumber/wireplumber.conf.d
install -o pi -g pi -m 644 "$repo_root/install/30-lighting-audio.conf" \
  /home/pi/.config/pipewire/pipewire.conf.d/30-lighting-audio.conf
install -o pi -g pi -m 644 "$repo_root/install/51-lighting-bluetooth.conf" \
  /home/pi/.config/wireplumber/wireplumber.conf.d/51-lighting-bluetooth.conf
install -m 644 "$repo_root/install/addy-bluetooth.service" /etc/systemd/system/addy-bluetooth.service
loginctl enable-linger pi
systemctl enable --now bluetooth.service
rfkill unblock bluetooth
runuser -u pi -- env XDG_RUNTIME_DIR=/run/user/1000 \
  systemctl --user enable pipewire.service pipewire-pulse.service wireplumber.service
runuser -u pi -- env XDG_RUNTIME_DIR=/run/user/1000 \
  systemctl --user restart pipewire.service pipewire-pulse.service wireplumber.service
systemctl daemon-reload
systemctl enable --now addy-bluetooth.service
printf 'Installed. Backups: %s\n' "$backup_dir"
systemctl is-active addy-bluetooth.service
