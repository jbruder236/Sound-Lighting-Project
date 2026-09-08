"""Validated, atomic settings shared by the light engine and CLI."""
from dataclasses import asdict, dataclass
import json
import math
import os
from pathlib import Path
import tempfile

VERSION = '1.1.0-dev'
CONFIG_PATH = '/etc/sound-lighting.json'
STATUS_PATH = '/run/sound-lighting/status.json'
SCENES = ('rainbow', 'spectrum', 'aurora', 'sunset', 'ocean', 'ember', 'candy', 'workshop', 'custom')


@dataclass(frozen=True)
class Settings:
    scene: str = 'rainbow'
    brightness: int = 255
    behavior: str = 'auto'
    quiet_seconds: float = 10
    threshold: float = 0.003
    color: str = '#ff9646'
    white: int = 50
    color_source: str = 'palette'

    @classmethod
    def parse(cls, values):
        if not isinstance(values, dict):
            raise ValueError('Settings must be a JSON object')
        unknown = set(values) - set(asdict(cls()))
        if unknown:
            raise ValueError('Unknown settings: ' + ', '.join(sorted(unknown)))
        merged = asdict(cls()) | values
        if merged['scene'] not in SCENES:
            raise ValueError('scene must be one of: ' + ', '.join(SCENES))
        if merged['scene'] == 'spectrum':
            merged.update(scene='rainbow', color_source='spectrum')
        if merged['color_source'] not in ('palette', 'spectrum'):
            raise ValueError('color_source must be palette or spectrum')
        color = merged['color']
        if (not isinstance(color, str) or len(color) != 7 or color[0] != '#'
                or any(c not in '0123456789abcdefABCDEF' for c in color[1:])):
            raise ValueError('color must be a six-digit hex color, e.g. #ff9646')
        merged['color'] = color.lower()
        if merged['behavior'] not in ('auto', 'idle', 'sound'):
            raise ValueError('behavior must be auto, idle (standby), or sound')
        if type(merged['brightness']) is not int or not 0 <= merged['brightness'] <= 255:
            raise ValueError('brightness must be an integer from 0 to 255')
        if type(merged['white']) is not int or not 0 <= merged['white'] <= 100:
            raise ValueError('white must be an integer from 0 (warm) to 100 (cool)')
        for key, low, high in [('quiet_seconds', 0.1, 3600), ('threshold', 0.000001, 1)]:
            value = merged[key]
            if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
                raise ValueError(f'{key} must be a finite number from {low} to {high}')
        return cls(**merged)


def read_settings(path):
    return Settings.parse(json.loads(Path(path).read_text()))


def atomic_json(path, values):
    """Readers see either the old complete document or the new complete document."""
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as output:
            json.dump(values, output, indent=2, allow_nan=False)
            output.write('\n')
            output.flush()
            os.fchmod(output.fileno(), 0o644)
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class SettingsWatcher:
    def __init__(self, path, initial):
        self.path = Path(path) if path else None
        self.current = initial
        self.seen = None
        self.error = None

    def reload(self):
        if self.path is None:
            return self.current
        try:
            raw = self.path.read_text()
            if raw == self.seen and self.error is None:
                return self.current
            self.seen = raw
            candidate = Settings.parse(json.loads(raw))
        except (OSError, ValueError) as error:
            message = str(error)
            if message != self.error:
                print(f'Settings rejected; retaining last good settings: {message}', flush=True)
            self.error = message
            return self.current
        self.error = None
        if candidate != self.current:
            self.current = candidate
            print(f'Settings applied: {candidate.scene}, brightness {candidate.brightness}/255, {candidate.behavior}.', flush=True)
        return self.current
