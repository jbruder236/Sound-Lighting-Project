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
    backup = home / '.local/state/sound-lighting/install-backup' / datetime.now().strftime('%Y%m%d-%H%M%S')
    for path in (launcher, desktop, icon):
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
        f'Exec=omarchy launch tui --app-id=org.omarchy.SoundLighting "{escaped}"\n'
        'Icon=sound-lighting\nTerminal=false\nStartupNotify=true\n'
        'StartupWMClass=org.omarchy.SoundLighting\nCategories=AudioVideo;\n'
        'Keywords=Garage;LED;Raspberry;Pi;Sound;Lighting;\n')
    shutil.copy2(repo / 'install/sound-lighting.svg', icon)
    for command in (['desktop-file-validate', str(desktop)],
                    ['update-desktop-database', str(desktop.parent)]):
        if shutil.which(command[0]):
            subprocess.run(command, check=True)
    print('Installed. SUPER+SPACE → Sound Lighting. The Pi may be powered off when you open it.')


if __name__ == '__main__':
    main()
