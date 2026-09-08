"""Shared RGB white tint; terminal swatches remain approximate."""
def white_rgb(tint):
    """RGB tint, not calibrated Kelvin; midpoint preserves the original Workshop."""
    warm, neutral, cool = (255, 120, 40), (255, 205, 145), (190, 220, 255)
    a, b = (warm, neutral) if tint <= 50 else (neutral, cool)
    mix = tint / 50 if tint <= 50 else (tint - 50) / 50
    return tuple(round(x + (y - x) * mix) for x, y in zip(a, b))

