"""A gentle center-out ripple over Flow's existing musical color field."""
import math


class Warble:
    def __init__(self):
        self.phase = 0.
        self.depth = 0.
        self.speed = .8

    def update(self, dt, level, bands):
        # Low notes give broader, slower movement; brighter notes quicken it.
        tone = sum(i * b for i, b in enumerate(bands or ())) / max(1e-9, 5 * sum(bands or ()))
        blend = 1 - math.exp(-max(0, dt) / .35)
        self.speed += (.65 + .65 * tone - self.speed) * blend
        self.depth += (.18 * level - self.depth) * blend
        self.phase = (self.phase + dt * self.speed) % 1

    def frame(self, pixels, span):
        result = []
        # Each physical strip has its own center. The underlying color canvas
        # remains continuous across both outputs, with synchronized ripples.
        for start in range(0, len(pixels), span):
            count = min(span, len(pixels) - start)
            for i in range(count):
                radius = abs(2 * i / max(1, count - 1) - 1)
                wave = math.sin(math.tau * (2 * radius - self.phase))
                direction = 1 if i >= count / 2 else -1
                source = max(0, min(count - 1, i + direction * wave * self.depth * 10))
                left = int(source)
                right = min(count - 1, left + 1)
                mix = source - left
                gain = 1 - self.depth * (.5 + .5 * wave)
                result.append(tuple(round(((1-mix)*a + mix*b) * gain)
                                    for a, b in zip(pixels[start+left], pixels[start+right])))
        return result
