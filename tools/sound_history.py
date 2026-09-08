"""A relative sound trace with fine dotted columns and a vertical theme gradient."""
from rich.text import Text
from textual.widgets import Sparkline
from microchart import column, gradient


def relative_level(rms, average):
    """Mean volume is halfway; twice the mean fills the graph; silence is zero."""
    return max(0, min(1, rms / (2 * max(average, 1e-6))))


class SoundHistory(Sparkline):
    def render(self):
        width, height = max(1, self.content_size.width), max(1, self.content_size.height)
        samples = list(self.data or [])[-100:]
        average = sum(samples) / len(samples) if samples else 0.
        data = [0.] * (100-len(samples)) + samples
        _, background = self.background_colors
        low = background + self.get_component_styles('sparkline--min-color').color
        high = background + self.get_component_styles('sparkline--max-color').color
        levels = []
        for x in range(width * 2):
            start = min(len(data)-1, x * len(data) // (width * 2))
            end = max(start+1, (x+1) * len(data) // (width * 2))
            bucket = data[start:end]
            rms = max(bucket)  # Preserve brief peaks when several samples share a dot.
            levels.append(relative_level(rms, average))
        text = Text(no_wrap=True)
        shades = gradient(low.hex, high.hex, height)
        for row in reversed(range(height)):
            for x in range(width):
                text.append(column(levels[x*2], levels[x*2+1], row, height), style=shades[row])
            if row:
                text.append('\n')
        return text
