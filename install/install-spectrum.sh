#!/usr/bin/env bash
# Optional laptop component. Pi must already have the feature branch deployed.
set -euo pipefail
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
venv="$HOME/.local/share/sound-lighting/spectrum-venv"
config="$HOME/.config/sound-lighting/spectrum.env"
unit="$HOME/.config/systemd/user/sound-lighting-spectrum.service"
mkdir -p "$(dirname "$venv")" "$(dirname "$config")" "$(dirname "$unit")"
python3 -m venv "$venv"
"$venv/bin/pip" install -r "$repo/requirements-spectrum.txt"
# Quote EnvironmentFile values and preserve explicitly customized endpoints.
"$venv/bin/python" - "$repo" "$config" <<'PY'
from pathlib import Path
import sys
repo, config = sys.argv[1], Path(sys.argv[2])
if '\n' in repo or '\r' in repo:
    raise SystemExit('Unsupported newline in repository path')
escaped = repo.replace('\\', '\\\\').replace('"', '\\"')
lines = config.read_text().splitlines() if config.exists() else [
    'PI_HOST=rpi4', 'PI_REPO=/home/pi/Sound-Lighting-Project', 'AUDIO_TARGET=garage_dual']
lines = [line for line in lines if not line.startswith('LIGHTING_REPO=')]
config.write_text('\n'.join(lines + [f'LIGHTING_REPO="{escaped}"']) + '\n')
PY
if [[ -f "$unit" ]]; then cp -- "$unit" "$unit.backup"; fi
cp -- "$repo/install/sound-lighting-spectrum.service" "$unit"
systemctl --user daemon-reload
systemctl --user enable --now sound-lighting-spectrum.service
systemctl --user restart sound-lighting-spectrum.service
systemctl --user is-active sound-lighting-spectrum.service
