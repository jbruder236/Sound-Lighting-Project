"""Frequency → color → Pi output, drawn from measured engine telemetry."""
import colorsys
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Label, Static
from spectrum import BANDS, HUES, PUNCH_HUES
from slider import Slider

COLORS = ['#' + ''.join(f'{round(c*255):02x}' for c in colorsys.hsv_to_rgb(h, 1, 1)) for h in HUES]
RANGES = ('40–160', '160–400', '400–1k', '1k–2.5k', '2.5k–6k', '6k–12k')


class BandChart(Static):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.levels = [0.] * 6
        self.band_colors = COLORS

    def render(self):
        width = self.content_size.width
        text = Text(no_wrap=True)
        if width >= 60:
            cell = width // 6
            for row in range(4, 0, -1):
                for level, color in zip(self.levels, self.band_colors):
                    fill = max(0, min(8, round((level * 4 - (row - 1)) * 8)))
                    text.append((' ▁▂▃▄▅▆▇█'[fill] * (cell-2)).center(cell), style=color)
                text.append('\n')
            for words in (BANDS, RANGES):
                for label, color in zip(words, self.band_colors):
                    text.append(label.center(cell), style=color)
                text.append('\n')
        else:
            bar = max(2, width - 24)
            for name, hz, level, color in zip(BANDS, RANGES, self.levels, self.band_colors):
                text.append(f'{name:5} {hz:7} ', style=color)
                fill = round(level * bar)
                text.append('━' * fill, style=color)
                text.append('─' * (bar-fill), style='dim')
                text.append(f' {level:4.0%}\n', style=color)
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
        yield Label('frequency → color', classes='eyebrow')
        with Horizontal(classes='row'):
            yield Button('Flow', compact=True, id='frequency-flow')
            yield Button('Punch', compact=True, id='frequency-punch')
        with Vertical(id='punch-control'):
            yield Label('Punch · gentle ↔ vivid')
            yield Slider(50, id='punch-slider',
                         tooltip='Live intensity · 50 = balanced · 100 = most vivid · fast attack at every setting')
        yield Static('', id='spectrum-control', markup=False)
        yield BandChart(id='bands')
        yield Static('Pi output · sampled commands', classes='muted')
        yield StripPreview(id='strip-preview')
        yield Static('', id='spectrum', classes='muted', markup=False)

    def on_mount(self):
        self.query_one('#frequency-flow').tooltip = 'Punch response fixed at 45%'
        self.query_one('#frequency-punch').tooltip = 'Fast notes, six vivid hues, deep-to-bright contrast · master brightness still limits output'
        self.query_one(BandChart).tooltip = 'Compressed energy share per band · frequencies in Hz · up to 5 updates/s'
        self.query_one(StripPreview).tooltip = 'Sampled smoothed RGB commands, including brightness. Screen colors approximate the LEDs.'

    def show_status(self, data):
        stale = data.get('stale', True)
        receiving = not stale and data.get('spectrum') == 'receiving'
        chart = self.query_one(BandChart)
        hues = PUNCH_HUES
        chart.band_colors = ['#' + ''.join(f'{round(c*255):02x}' for c in colorsys.hsv_to_rgb(h, 1, 1)) for h in hues]
        chart.levels = data.get('spectrum_bands', [0.] * 6) if receiving else [0.] * 6
        chart.refresh()
        preview = self.query_one(StripPreview)
        preview.colors = data.get('strip_preview', []) if not stale else []
        preview.refresh()
        palette = 'White' if data.get('scene') == 'workshop' else data.get('scene', 'palette').title()
        state = ('Offline · waiting for Pi' if stale else
                 ('Punch · notes → color · level → contrast' if data.get('frequency_style') == 'punch'
                  else 'Flow · frequency → hue · audio → glow') if data.get('spectrum_active') else
                 f'{palette} · standby' if data.get('mode') == 'idle' else
                 f'{palette} · quiet glow' if data.get('mode') == 'quiet' else
                 f'{palette} fallback · laptop unavailable' if not receiving else
                 f'{palette} fallback · no tonal signal')
        self.query_one('#spectrum-control', Static).update(state)
        self.query_one('#spectrum', Static).update('FFT — · feed unavailable' if not receiving else
            f"FFT {data.get('spectrum_fft_ms', 0):g} ms · SSH {data.get('spectrum_ssh_rtt_ms', 0):g} ms RTT · age {data.get('spectrum_age_ms', 0)} ms")
