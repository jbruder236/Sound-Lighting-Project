"""A fixed-scale sound trace with fine dotted columns and a vertical theme gradient."""
import math
from rich.text import Text
from textual.widgets import Sparkline
from microchart import column, gradient


class SoundHistory(Sparkline):
    def render(self):
        width, height = max(1, self.content_size.width), max(1, self.content_size.height)
        data = list(self.data or [0.])
        _, background = self.background_colors
        low = background + self.get_component_styles('sparkline--min-color').color
        high = background + self.get_component_styles('sparkline--max-color').color
        levels = []
        for x in range(width * 2):
            start = min(len(data)-1, x * len(data) // (width * 2))
            end = max(start+1, (x+1) * len(data) // (width * 2))
            bucket = data[start:end]
            rms = sum(bucket) / len(bucket)
            db = 20 * math.log10(max(1e-9, rms))
            levels.append(max(0, min(1, (db + 54) / 48)))
        text = Text(no_wrap=True)
        shades = gradient(low.hex, high.hex, height)
        for row in reversed(range(height)):
            for x in range(width):
                text.append(column(levels[x*2], levels[x*2+1], row, height), style=shades[row])
            if row:
                text.append('\n')
        return text
