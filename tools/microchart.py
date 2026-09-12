"""Fine two-column terminal dots and cached, restrained chart gradients."""
from functools import lru_cache
from rich.style import Style
from textual.color import Color

# Braille cells give two independent samples across and four dots vertically.
DOTS = ((0x40, 0x04, 0x02, 0x01), (0x80, 0x20, 0x10, 0x08))


def column(left, right, row, height, peak=None):
    mask = 0
    for side, level in enumerate((left, right)):
        fill = max(0, min(4, round(level * height * 4) - row * 4))
        for bit in DOTS[side][:fill]:
            mask |= bit
        if peak is not None and peak > .03:
            tip = max(0, min(height*4-1, round(peak*height*4)-1))
            if tip // 4 == row:
                mask |= DOTS[side][tip % 4]
    return chr(0x2800 + mask) if mask else ' '


def meter(fill):
    fill = max(0, min(8, fill))
    bits = DOTS[0] + DOTS[1]
    return chr(0x2800 + sum(bits[:fill])) if fill else ' '


@lru_cache(maxsize=128)
def gradient(start, end, steps):
    low, high = Color.parse(start), Color.parse(end)
    return tuple(Style(color=low.blend(high, i/max(1, steps-1)).rich_color)
                 for i in range(steps))
