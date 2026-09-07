#!/usr/bin/env python3
"""Analyze the laptop sink monitor and send latest features over one SSH session."""
import argparse
import asyncio
import json
import re
import shlex
import signal
import time

import numpy as np
from spectral_analysis import Analyzer, RATE, WINDOW, INTERVAL, waiting


async def reap(process):
    if process and process.returncode is None:
        try:
            process.terminate()
        except ProcessLookupError:
            pass
        try:
            await asyncio.wait_for(process.wait(), 2)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()


class Publisher:
    def __init__(self, host, repo, target):
        if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.@-]*', host):
            raise ValueError('Use a hostname or SSH alias')
        self.command = ['ssh', '-T', '-oBatchMode=yes', '-oConnectTimeout=3',
                        '-oServerAliveInterval=2', '-oServerAliveCountMax=2', host,
                        'sudo -n /usr/bin/python3 -u ' + shlex.quote(repo + '/tools/spectrum_receiver.py')]
        self.capture_command = ['pw-record', '--target', target,
            '--properties=stream.capture.sink=true node.dont-fallback=true',
            '--latency=20ms', '--rate', str(RATE), '--channels', '1', '--format', 's16', '--raw', '-']
        self.pcm = bytearray()
        self.updated = 0.
        self.analyzer = Analyzer()

    async def capture(self):
        while True:
            process = None
            try:
                process = await asyncio.create_subprocess_exec(*self.capture_command,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
                while True:
                    chunk = await asyncio.wait_for(process.stdout.readexactly(1024), 3)
                    self.pcm.extend(chunk)
                    del self.pcm[:-WINDOW * 2]
                    self.updated = time.monotonic()
            except (OSError, asyncio.IncompleteReadError, asyncio.TimeoutError) as error:
                print(f'Capture waiting: {type(error).__name__}; retry in 5s', flush=True)
            finally:
                self.updated = 0.
                self.pcm.clear()
                await reap(process)
            await asyncio.sleep(5)

    def features(self):
        if time.monotonic() - self.updated > .15 or len(self.pcm) < WINDOW * 2:
            return waiting()
        samples = np.frombuffer(bytes(self.pcm), dtype='<i2').astype(float) / 32768
        return self.analyzer.analyze(samples)

    async def publish(self):
        while True:
            process = None
            try:
                process = await asyncio.create_subprocess_exec(*self.command,
                    stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL, limit=4096)
                reply = json.loads(await asyncio.wait_for(process.stdout.readline(), 5))
                rtt = 0.
                print('Spectrum SSH connected', flush=True)
                while True:
                    start = time.monotonic()
                    packet = self.features()
                    packet['ssh_rtt_ms'] = round(rtt, 2)
                    sent = time.monotonic()
                    process.stdin.write((json.dumps({'seq': reply['seq'], 'features': packet},
                                                    allow_nan=False) + '\n').encode())
                    await asyncio.wait_for(process.stdin.drain(), .5)
                    reply = json.loads(await asyncio.wait_for(process.stdout.readline(), .5))
                    rtt = (time.monotonic() - sent) * 1000
                    if reply.get('accepted') is not True:
                        raise ValueError('Expired feature challenge')
                    # No packet queue: sample again only after acknowledging this write.
                    await asyncio.sleep(max(0., INTERVAL - (time.monotonic() - start)))
            except (OSError, ValueError, KeyError, asyncio.TimeoutError) as error:
                print(f'Spectrum link waiting: {type(error).__name__}; retry in 5s', flush=True)
            finally:
                await reap(process)
            await asyncio.sleep(5)

    async def run(self):
        tasks = [asyncio.create_task(self.capture()), asyncio.create_task(self.publish())]
        try:
            await asyncio.gather(*tasks)
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='rpi4')
    parser.add_argument('--repo', default='/home/pi/Sound-Lighting-Project')
    parser.add_argument('--target', default='garage_dual')
    args = parser.parse_args()
    publisher = Publisher(args.host, args.repo, args.target)
    task = asyncio.create_task(publisher.run())
    for sig in (signal.SIGINT, signal.SIGTERM):
        asyncio.get_running_loop().add_signal_handler(sig, task.cancel)
    try:
        await task
    except asyncio.CancelledError:
        pass


if __name__ == '__main__':
    asyncio.run(main())
