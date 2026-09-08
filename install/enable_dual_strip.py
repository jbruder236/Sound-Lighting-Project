#!/usr/bin/env python3
"""Opt into GPIO18 + GPIO13 on the supported Pi; reboot separately afterward."""
import datetime
import os
from pathlib import Path
import shutil
import subprocess


def main():
    repo = Path(__file__).resolve().parents[1]
    if os.geteuid() != 0 or repo != Path('/home/pi/Sound-Lighting-Project'):
        raise SystemExit('Run with sudo from /home/pi/Sound-Lighting-Project on the Pi.')
    boot = Path('/boot/firmware/config.txt')
    text = boot.read_text()
    dropin = Path('/etc/systemd/system/addy-bluetooth.service.d/dual-strip.conf')
    blacklist = Path('/etc/modprobe.d/sound-lighting-pwm.conf')
    backup = Path('/var/backups/sound-lighting') / datetime.datetime.now().strftime('dual-%Y%m%d-%H%M%S')
    backup.mkdir(parents=True)
    for path in (boot, dropin, blacklist):
        if path.exists():
            destination = backup / path.relative_to('/')
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
    subprocess.run(['systemctl', 'stop', 'addy-bluetooth.service'], check=True)
    marker = '# Sound Lighting dual PWM: reserve PWM for GPIO18 and GPIO13'
    if marker not in text:
        boot.write_text(text.rstrip() + '\n\n[all]\n' + marker + '\ndtparam=audio=off\n')
    blacklist.write_text('# PWM is owned by the LED service. USB/Bluetooth audio remain available.\nblacklist snd_bcm2835\n')
    dropin.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(repo / 'install/dual-strip.conf', dropin)
    subprocess.run(['systemctl', 'daemon-reload'], check=True)
    subprocess.run(['systemctl', 'enable', 'addy-bluetooth.service'], check=True)
    print(f'Dual PWM configured; reboot required. Backups: {backup}')


if __name__ == '__main__':
    main()
