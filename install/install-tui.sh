#!/usr/bin/env bash
# Optional dashboard; run as pi after installing the core service.
set -euo pipefail
repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
if [[ $(id -un) != pi || "$repo_root" != /home/pi/Sound-Lighting-Project ]]; then
  echo 'Run as pi from /home/pi/Sound-Lighting-Project (without sudo).' >&2
  exit 1
fi
tui_env=/home/pi/.local/share/sound-lighting/tui-venv
/usr/bin/python3 -m venv "$tui_env"
"$tui_env/bin/pip" install -r "$repo_root/requirements-tui.txt"
"$tui_env/bin/python" -m unittest discover -s "$repo_root/tests" -p test_dashboard.py
if [[ -e /usr/local/bin/lights ]] && ! grep -q 'Sound Lighting' /usr/local/bin/lights; then
  echo '/usr/local/bin/lights belongs to another program; refusing to overwrite it.' >&2
  exit 1
fi
sudo install -m 755 "$repo_root/install/lights" /usr/local/bin/lights
echo 'Ready: sudo lights tui. Closing the dashboard leaves the light service running.'
