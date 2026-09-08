"""Frequency → color → Pi output, drawn from measured engine telemetry."""
import colorsys
import math
import time
from rich.text import Text
from textual.color import Color
from microchart import gradient
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Label, Static
from spectrum import BANDS, HUES, PUNCH_HUES

COLORS = ['#' + ''.join(f'{round(c*255):02x}' for c in colorsys.hsv_to_rgb(h, 1, 1)) for h in HUES]
RANGES = ('40–160', '160–400', '400–1k', '1k–2.5k', '2.5k–6k', '6k–12k')


class BandChart(Static):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.levels = [0.] * 6
        self.shown = [0.] * 6
        self.peaks = [0.] * 6
        self.band_colors = COLORS
        self.updated = time.monotonic()

    def update_levels(self, levels, receiving, now=None):
        now = time.monotonic() if now is None else now
        dt = max(0, min(.25, now - self.updated))
        self.updated = now
        self.levels = list(levels) if receiving else [0.] * 6
        if not receiving:
            self.shown = self.peaks = [0.] * 6
        else:
            for i, value in enumerate(self.levels):
                # Expand small shares on a fixed visual scale, without changing
                # the measured percentages or the LED color calculation.
                target = value ** .65
                tau = .015 if target > self.shown[i] else .09
                self.shown[i] += (target-self.shown[i]) * (1-math.exp(-dt/tau))
                self.peaks[i] = max(self.shown[i], self.peaks[i] - dt * 1.1)
        self.refresh()

    def render(self):
        width = self.content_size.width
        text = Text(no_wrap=True)
        colors = getattr(self.app, 'music_colors', self.band_colors)
        _, background = self.background_colors
        if width >= 60:
            cell = width // 6
            ramps = [gradient(background.blend(Color.parse(c), .75).hex, c, 4) for c in colors]
            for row in range(3, -1, -1):
                for level, peak, ramp in zip(self.shown, self.peaks, ramps):
                    fill = max(0, min(8, round((level * 4 - row) * 8)))
                    glyph = ' ▁▂▃▄▅▆▇█'[fill]
                    if not fill and peak > .03 and math.ceil(peak*4)-1 == row:
                        glyph = '─'
                    text.append(' ' + glyph * (cell-2) + ' ', style=ramp[row])
                text.append('\n')
            for words in (BANDS, RANGES):
                for label, color in zip(words, colors):
                    text.append(label.center(cell), style=color)
                text.append('\n')
        else:
            bar = max(2, width - 24)
            for name, hz, raw, level, peak, color in zip(BANDS, RANGES, self.levels, self.shown, self.peaks, colors):
                text.append(f'{name:5} ', style=color)
                text.append(f'{hz:7} ', style='dim')
                ramp = gradient(background.blend(Color.parse(color), .75).hex, color, bar)
                for x in range(bar):
                    fill = max(0, min(8, round((level * bar - x) * 8)))
                    glyph = ' ▏▎▍▌▋▊▉█'[fill]
                    if not fill and peak > .03 and x == min(bar-1, int(peak*bar)):
                        glyph = '│'
                    text.append(glyph, style=ramp[x])
                text.append(f' {raw:4.0%}\n', style=color)
        return text


class StripPreview(Static):
    colors = ()

    def render(self):
        text = Text(no_wrap=True)
        width = self.content_size.width
        if self.colors:
            for x in range(width):
                text.append('█', style=self.colors[min(len(self.colors)-1, x * len(self.colors) // max(1, width))])
        else:
            text.append('Output unavailable', style='dim')
        return text


class SpectrumPane(Vertical):
    def compose(self) -> ComposeResult:
        yield Label('music · live', classes='eyebrow')
        yield Static('', id='spectrum-control', markup=False)
        yield BandChart(id='bands')
        yield Static('strip · live output', classes='muted')
        yield StripPreview(id='strip-preview')
        yield Static('', id='spectrum', classes='muted', markup=False)

    def on_mount(self):
        self.query_one(BandChart).tooltip = 'Measured energy shares · fixed expanded bar scale · fast attack, 90 ms release · falling peak marks · live feed up to 20 Hz'
        self.query_one(StripPreview).tooltip = 'Sampled smoothed RGB commands, including brightness. Screen colors approximate the LEDs.'

    def show_status(self, data):
        stale = data.get('stale', True)
        receiving = not stale and data.get('spectrum') == 'receiving'
        chart = self.query_one(BandChart)
        hues = PUNCH_HUES
        chart.band_colors = ['#' + ''.join(f'{round(c*255):02x}' for c in colorsys.hsv_to_rgb(h, 1, 1)) for h in hues]
        chart.update_levels(data.get('spectrum_bands', [0.] * 6), receiving)
        preview = self.query_one(StripPreview)
        preview.colors = data.get('strip_preview', []) if not stale else []
        preview.refresh()
        palette = 'White' if data.get('scene') == 'workshop' else data.get('scene', 'palette').title()
        state = ('Offline · waiting for Pi' if stale else
                 ('Punch · notes → color · level → contrast' if data.get('frequency_style') == 'punch'
                  else 'Warble · center → ends · musical ripples' if data.get('frequency_style') == 'warble'
                  else 'Flow · musical color · smooth glow') if data.get('spectrum_active') else
                 f'{palette} · standby' if data.get('mode') == 'idle' else
                 f'{palette} · quiet glow' if data.get('mode') == 'quiet' else
                 f'{palette} fallback · laptop unavailable' if not receiving else
                 f'{palette} fallback · no tonal signal')
        self.query_one('#spectrum-control', Static).update(state)
        self.query_one('#spectrum', Static).update('FFT — · feed unavailable' if not receiving else
            f"FFT {data.get('spectrum_fft_ms', 0):g} ms · SSH {data.get('spectrum_ssh_rtt_ms', 0):g} ms RTT · age {data.get('spectrum_age_ms', 0)} ms")
