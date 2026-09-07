"""Small, validated spectral feature packets; no FFT runs in the LED process."""
import json
import math
from pathlib import Path

PATH = '/run/sound-lighting/spectrum.json'
BANDS = ('bass', 'body', 'mids', 'lead', 'air', 'shine')
EDGES = (40, 160, 400, 1000, 2500, 6000, 12000)
HUES = (0.07, 0.02, 0.94, 0.77, 0.62, 0.49)
TTL = .75


def validate(packet):
    if not isinstance(packet, dict) or packet.get('version') != 1:
        raise ValueError('Expected spectrum protocol 1')
    bands = packet.get('bands')
    if not isinstance(bands, list) or len(bands) != len(BANDS):
        raise ValueError('Expected six frequency bands')
    def number(value, high):
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= high:
            raise ValueError('Invalid spectrum value')
        return value
    bands = [number(v, 1) for v in bands]
    if type(packet.get('capture_active')) is not bool:
        raise ValueError('Expected capture state')
    return dict(version=1, bands=bands, capture_active=packet['capture_active'],
                rms=number(packet.get('rms'), 1),
                centroid_hz=number(packet.get('centroid_hz'), 24000),
                fft_ms=number(packet.get('fft_ms'), 1000),
                ssh_rtt_ms=number(packet.get('ssh_rtt_ms'), 1000))


class SpectrumReader:
    def __init__(self, path=PATH):
        self.path = Path(path)
        self.next_read = 0
        self.packet = None
        self.received = None

    def poll(self, now):
        if now >= self.next_read:
            self.next_read = now + .05
            try:
                with self.path.open('rb') as source:
                    raw = source.read(4097)
                if len(raw) > 4096:
                    raise ValueError('Oversized spectrum file')
                data = json.loads(raw)
                received = data['received_at']
                if type(received) not in (int, float) or not math.isfinite(received):
                    raise ValueError('Invalid receipt time')
                self.packet, self.received = validate(data), received
            except (OSError, ValueError, KeyError, TypeError):
                self.packet, self.received = None, None
        fresh = self.received is not None and 0 <= now - self.received < TTL
        return self.packet if fresh and self.packet['capture_active'] else None

    def status(self, now):
        packet = self.poll(now)
        return {'spectrum': 'receiving' if packet else 'waiting',
                'spectrum_band': BANDS[max(range(6), key=lambda i: packet['bands'][i])]
                    if packet and max(packet['bands']) > 0 else None,
                'spectrum_age_ms': round((now - self.received) * 1000) if packet else None,
                'spectrum_fft_ms': packet['fft_ms'] if packet else None,
                'spectrum_ssh_rtt_ms': packet['ssh_rtt_ms'] if packet else None}
