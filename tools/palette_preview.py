"""Recognizable color swatches for scene selection; no hardware dependencies."""
import colorsys
from rich.text import Text
from colors import white_rgb


def scene_label(scene, config):
    label = Text(('White' if scene == 'workshop' else scene.title()).ljust(9) + ' ')
    if scene == 'custom':
        swatches = [config.color] * 6
    elif scene == 'workshop':
        swatches = ['#' + ''.join(f'{c:02x}' for c in white_rgb(tint)) for tint in (0, 20, 40, 60, 80, 100)]
    else:
        low, high = {'rainbow': (0, .83), 'aurora': (.40, .82), 'sunset': (.88, 1.08),
                     'ocean': (.41, .61), 'ember': (0, .08), 'candy': (.76, .96)}[scene]
        swatches = ['#' + ''.join(f'{round(c * 255):02x}' for c in colorsys.hsv_to_rgb((low + (high-low)*i/5) % 1, 1, 1)) for i in range(6)]
    for color in swatches:
        label.append('██', style=color)
    return label
