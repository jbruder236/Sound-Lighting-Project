"""Hann-windowed FFT mapped to six broad bands, not polyphonic MIDI transcription."""
from pathlib import Path
import sys
import time

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'RpiLightStripCodes'))
from spectrum import EDGES

RATE, WINDOW, INTERVAL = 48000, 2048, .05


class Analyzer:
    def __init__(self):
        self.window = np.hanning(WINDOW)
        self.frequencies = np.fft.rfftfreq(WINDOW, 1 / RATE)
        self.masks = [(self.frequencies >= lo) & (self.frequencies < hi)
                      for lo, hi in zip(EDGES, EDGES[1:])]

    def analyze(self, samples):
        start = time.perf_counter()
        samples = np.asarray(samples, dtype=float)
        if samples.shape != (WINDOW,) or not np.isfinite(samples).all():
            raise ValueError('Expected one finite mono analysis window')
        samples = samples - samples.mean()  # Ignore DC offset.
        rms = min(1., float(np.sqrt(np.mean(samples ** 2))))
        power = np.abs(np.fft.rfft(samples * self.window)) ** 2
        energy = np.array([power[mask].sum() for mask in self.masks])
        total = energy.sum()
        # Square-root compression lets quieter instruments share the palette.
        levels = np.sqrt(energy / total) if total > 1e-12 and rms >= .003 else np.zeros(6)
        levels /= max(1., float(levels.sum()))
        valid = (self.frequencies >= EDGES[0]) & (self.frequencies < EDGES[-1])
        centroid = float(np.sum(power[valid] * self.frequencies[valid]) / total) if total > 1e-12 else 0.
        return dict(version=1, capture_active=True, bands=np.round(levels, 5).tolist(),
                    rms=round(rms, 5), centroid_hz=round(centroid, 1),
                    fft_ms=round((time.perf_counter() - start) * 1000, 3), ssh_rtt_ms=0.)


def waiting():
    return dict(version=1, capture_active=False, bands=[0.] * 6, rms=0.,
                centroid_hz=0., fft_ms=0., ssh_rtt_ms=0.)
