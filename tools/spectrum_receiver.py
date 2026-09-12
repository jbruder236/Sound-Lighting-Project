#!/usr/bin/env python3
"""SSH-only feature receiver. Short-lived challenges reject delayed TCP backlog."""
import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'RpiLightStripCodes'))
from settings import atomic_json
from spectrum import PATH, validate


def receive(path=PATH):
    sequence = 0
    accepted = None
    while True:
        issued = time.monotonic()
        print(json.dumps({'seq': sequence, 'accepted': accepted}), flush=True)
        line = sys.stdin.buffer.readline(4097)
        if not line:
            return
        if len(line) > 4096 or not line.endswith(b'\n'):
            raise ValueError('Oversized feature packet')
        request = json.loads(line)
        if not isinstance(request, dict) or request.get('seq') != sequence:
            raise ValueError('Unexpected feature sequence')
        packet = validate(request.get('features'))
        now = time.monotonic()
        accepted = now - issued < .5
        if accepted:
            atomic_json(path, packet | {'received_at': now})
        sequence += 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default=PATH)
    args = parser.parse_args()
    try:
        receive(args.output)
    except (BrokenPipeError, ConnectionError):
        pass
    except (OSError, ValueError, TypeError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
