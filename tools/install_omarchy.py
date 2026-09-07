#!/usr/bin/env python3
"""Install Sound Lighting in Omarchy's application launcher for the current user."""
import argparse
from datetime import datetime
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

from remote_backend import RemoteBackend


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='rpi4', help='Existing SSH alias; uses its key and known-host entry')
    args = parser.parse_args()
    RemoteBackend(args.host)  # Validate before writing the launcher.
    if not shutil.which('omarchy'):
        parser.error('Run this installer on the Omarchy laptop')
    home = Path.home()
    repo = Path(__file__).resolve().parents[1]
    environment = home / '.local/share/sound-lighting/tui-venv'
    subprocess.run([sys.executable, '-m', 'venv', str(environment)], check=True)
    subprocess.run([str(environment / 'bin/pip'), 'install', '-r', str(repo / 'requirements-tui.txt')], check=True)
    launcher = home / '.local/bin/sound-lighting'
    desktop = home / '.local/share/applications/org.omarchy.SoundLighting.desktop'
    icon = home / '.local/share/icons/hicolor/scalable/apps/sound-lighting.svg'
    window_rules = home / '.config/hypr/sound_lighting.lua'
    hypr_config = home / '.config/hypr/hyprland.lua'
    previous_config = hypr_config.read_text()
    previous_rules = window_rules.read_text() if window_rules.exists() else None
    backup = home / '.local/state/sound-lighting/install-backup' / datetime.now().strftime('%Y%m%d-%H%M%S')
    for path in (launcher, desktop, icon, window_rules, hypr_config):
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            backup.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backup / path.name)
    launcher.write_text('#!/bin/sh\n# Sound Lighting · local reconnecting dashboard\nexec ' +
                        shlex.join([str(environment / 'bin/python'), str(repo / 'tools/dashboard.py'),
                                    '--host', args.host]) + ' "$@"\n')
    launcher.chmod(0o755)
    escaped = str(launcher)
    for char in ('\\', '"', '`', '$'):
        escaped = escaped.replace(char, '\\' + char)
    desktop.write_text('[Desktop Entry]\nType=Application\nVersion=1.0\nName=Sound Lighting\n'
        'Comment=Garage lights, sound, and Raspberry Pi connection\n'
        f'Exec=setsid uwsm-app -- xdg-terminal-exec --app-id=org.omarchy.SoundLighting --title="Sound Lighting" -e "{escaped}"\n'
        'Icon=sound-lighting\nTerminal=false\nStartupNotify=true\n'
        'StartupWMClass=org.omarchy.SoundLighting\nCategories=AudioVideo;\n'
        'Keywords=Garage;LED;Raspberry;Pi;Sound;Lighting;\n')
    shutil.copy2(repo / 'install/sound-lighting.svg', icon)
    window_rules.write_text('-- Sound Lighting: a comfortable app window, using the default terminal.\n'
        'o.window("^org[.]omarchy[.]SoundLighting$", { float = true, center = true, size = { 1100, 880 } })\n')
    include = 'require("hypr.sound_lighting")'
    if include not in previous_config:
        hypr_config.write_text(previous_config.rstrip() + '\n\n-- Sound Lighting app window.\n' + include + '\n')
    try:
        subprocess.run(['hyprctl', 'reload'], check=True, stdout=subprocess.DEVNULL)
        errors = subprocess.check_output(['hyprctl', 'configerrors'], text=True).strip()
        if errors:
            raise RuntimeError('Hyprland configuration rejected: ' + errors)
    except (OSError, RuntimeError, subprocess.SubprocessError):
        hypr_config.write_text(previous_config)
        if previous_rules is None:
            window_rules.unlink(missing_ok=True)
        else:
            window_rules.write_text(previous_rules)
        subprocess.run(['hyprctl', 'reload'], check=False)
        raise
    for command in (['desktop-file-validate', str(desktop)],
                    ['update-desktop-database', str(desktop.parent)]):
        if shutil.which(command[0]):
            subprocess.run(command, check=True)
    print('Installed. SUPER+SPACE → Sound Lighting. The Pi may be powered off when you open it.')


if __name__ == '__main__':
    main()
