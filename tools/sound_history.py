"""A fixed-scale sound trace with fine bar tops and subtle column ridges."""
import math
from rich.style import Style
from rich.text import Text
from textual.widgets import Sparkline


class SoundHistory(Sparkline):
    def render(self):
        width, height = max(1, self.content_size.width), max(1, self.content_size.height)
        data = list(self.data or [0.])
        _, background = self.background_colors
        low = background + self.get_component_styles('sparkline--min-color').color
        high = background + self.get_component_styles('sparkline--max-color').color
        levels = []
        for x in range(width):
            start = min(len(data)-1, x * len(data) // width)
            end = max(start+1, (x+1) * len(data) // width)
            bucket = data[start:end]
            rms = sum(bucket) / len(bucket)
            db = 20 * math.log10(max(1e-9, rms))
            levels.append(max(0, min(1, (db + 54) / 48)))
        text = Text(no_wrap=True)
        for row in reversed(range(height)):
            for x, level in enumerate(levels):
                fill = max(0, min(8, round(level * height * 8 - row * 8)))
                color = low.blend(high, level)
                if x % 2:
                    color = color.blend(background, .12)
                text.append(' ▁▂▃▄▅▆▇█'[fill], style=Style(color=color.rich_color))
            if row:
                text.append('\n')
        return text
