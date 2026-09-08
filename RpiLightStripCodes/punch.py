"""Fast musical color and contrast, using laptop features without another FFT."""
import colorsys
import math
from spectrum import PUNCH_HUES


class Punch:
    def __init__(self, now):
        self.updated = now
        self.reference = .08
        self.level = 0.0

    def update(self, now, features, threshold=.003):
        dt = max(0, min(.25, now - self.updated))
        self.updated = now
        rms = features['rms'] if features else 0
        self.reference = max(.025, rms, self.reference * math.exp(-dt / 6))
        target = min(1, rms / self.reference) if rms >= threshold else 0
        tau = .025 if target > self.level else .12
        self.level += (target - self.level) * (1 - math.exp(-dt / tau))

    def frame(self, count, features, gain):
        # Squaring reverses the analyzer's compression: strong notes claim more
        # space. Each band has a colored region, with a weaker full-span wash.
        bands = [b * b for b in features['bands']]
        peak = max(max(bands), 1e-9)
        palette = [colorsys.hsv_to_rgb(h, 1, 1) for h in PUNCH_HUES]
        result = []
        for i in range(count):
            position = i / max(1, count - 1)
            weights = [b * (.15 + .85 * math.exp(-((position - j / 5) / .19) ** 2))
                       for j, b in enumerate(bands)]
            rgb = [sum(w * c[k] for w, c in zip(weights, palette)) for k in range(3)]
            hue, _, _ = colorsys.rgb_to_hsv(*rgb)
            # Slight tonal variation keeps long single-note spans colorful.
            hue = (hue + .08 * (position - .5) * self.level) % 1
            strength = max(weights) / peak
            value = (.025 + .975 * self.level ** 1.6 * strength) * gain
            result.append(tuple(round(c * 255) for c in colorsys.hsv_to_rgb(hue, 1, value)))
        return result


def smooth_pixels(previous, desired, dt, fast=False, quiet=False):
    """Time-based filters keep motion smooth even when render ticks vary."""
    import numpy as np
    if previous is None:
        return desired.copy()
    tau = np.where(desired > previous, .035, .09) if fast else (.15 if quiet else .65)
    return previous + (desired - previous) * (1 - np.exp(-dt / tau))
