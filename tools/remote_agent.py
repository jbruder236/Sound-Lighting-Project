#!/usr/bin/env python3
"""Private JSON-lines control channel over SSH; no listener or new network port."""
import asyncio
from dataclasses import asdict
import json
import sys

from dashboard_data import Backend


async def serve(backend=None):
    backend = backend or Backend()
    graph = {'error': 'Inspecting Pi audio…'}

    def send(value):
        print(json.dumps(value, allow_nan=False), flush=True)

    async def audio():
        nonlocal graph
        while True:
            graph = await backend.audio()
            await asyncio.sleep(5)

    async def snapshots():
        while True:
            try:
                config = asdict(backend.settings())
                error = None
            except (OSError, ValueError) as problem:
                config, error = None, str(problem)
            send({'type': 'snapshot', 'protocol': 1, 'settings': config,
                  'settings_error': error, 'status': backend.status(), 'audio': graph})
            await asyncio.sleep(.2)

    async def commands():
        reader = asyncio.StreamReader(limit=8192)
        protocol = asyncio.StreamReaderProtocol(reader)
        transport, _ = await asyncio.get_running_loop().connect_read_pipe(lambda: protocol, sys.stdin)
        try:
            while line := await reader.readline():
                request = {}
                try:
                    request = json.loads(line)
                    if not isinstance(request, dict) or request.get('type') != 'save':
                        raise ValueError('Expected a save request')
                    changes = request.get('changes')
                    if not isinstance(changes, dict):
                        raise ValueError('Expected settings changes')
                    updated = backend.save(**changes)
                    send({'type': 'reply', 'id': request.get('id'), 'settings': asdict(updated)})
                except (OSError, ValueError, TypeError) as error:
                    send({'type': 'reply', 'id': request.get('id') if isinstance(request, dict) else None,
                          'error': str(error)})
        finally:
            transport.close()

    tasks = [asyncio.create_task(job()) for job in (commands, snapshots, audio)]
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == '__main__':
    try:
        asyncio.run(serve())
    except (BrokenPipeError, ConnectionError):
        pass
