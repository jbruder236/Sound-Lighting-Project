#!/usr/bin/env python3
"""A terminal remote for the single running Sound Lighting service."""
import argparse
from collections import deque
import math
import re
from pathlib import Path
import tomllib
import time

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.theme import Theme
from textual.widgets import Button, Footer, Input, Label, ProgressBar, Select, Sparkline, Static

from dashboard_data import Backend
from settings import SCENES, VERSION, Settings
from slider import Slider
from palette_preview import scene_label
from spectrum_pane import SpectrumPane


class ColorPicker(ModalScreen[str | None]):
    """A separate window: editing never touches the running lights."""
    BINDINGS = [('escape', 'cancel', 'Cancel')]

    def __init__(self, color):
        super().__init__()
        self.color = color

    def compose(self) -> ComposeResult:
        with Vertical(id='picker'):
            yield Label('color', classes='eyebrow')
            yield Static(id='swatch')
            yield Label('Hex · #RRGGBB')
            yield Input(self.color, id='hex', max_length=7)
            with Horizontal(classes='row'):
                for name, color in [('Amber', 'ff9646'), ('Rose', 'ff2870'), ('Ice', '00dcca'), ('Violet', '8040ff')]:
                    yield Button(name, id='preset-' + color, compact=True)
            with Horizontal(classes='row'):
                for name, color in [('Gold', 'ffd040'), ('Mint', '46ffb0'), ('Coral', 'ff6046'), ('Blue', '3070ff')]:
                    yield Button(name, id='preset-' + color, compact=True)
            yield Static('', id='color-error')
            with Horizontal(classes='row'):
                yield Button('Cancel', compact=True, id='cancel')
                yield Button('Apply', compact=True, id='save-color', variant='primary')

    def on_mount(self):
        self.preview(self.color)
        self.query_one('#hex', Input).focus()

    def preview(self, value):
        try:
            color = Settings.parse({'color': value}).color
        except ValueError:
            self.query_one('#color-error', Static).update('Enter six hex digits, e.g. #ff9646')
            self.query_one('#save-color', Button).disabled = True
            return
        self.color = color
        self.query_one('#swatch', Static).styles.background = color
        self.query_one('#color-error', Static).update(f'{color.upper()} · Custom scene')
        self.query_one('#save-color', Button).disabled = False

    @on(Input.Changed, '#hex')
    def changed(self, event):
        self.preview(event.value)

    def on_button_pressed(self, event):
        event.stop()
        name = event.button.id
        if name.startswith('preset-'):
            self.query_one('#hex', Input).value = '#' + name.removeprefix('preset-')
        elif name == 'save-color':
            self.dismiss(self.color)
        elif name == 'cancel':
            self.action_cancel()

    def action_cancel(self):
        self.dismiss(None)


class Dashboard(App):
    TITLE = 'Sound Lighting'
    CSS_PATH = 'dashboard.tcss'
    BINDINGS = [('q', 'quit', 'Quit'), ('c', 'color', 'Color'),
                ('a', 'auto', 'Auto'), ('s', 'idle', 'Standby'),
                ('r', 'sound', 'Sound'), ('f', 'frequency', 'Frequency')]

    def __init__(self, backend=None):
        super().__init__()
        self.backend = backend or Backend()
        self.displayed = None
        self.slider_pending = {}
        self.slider_saving = False
        self.slider_timer = None
        self.load_omarchy_theme()
        self.history_at = 0
        self.history = deque([0.0] * 60, maxlen=60)
        self.data = {}
        self.graph = {}
        try:
            self.initial = self.backend.settings()
        except (OSError, ValueError):
            self.initial = Settings()

    def load_omarchy_theme(self):
        directory = Path.home() / '.local/state/omarchy/current/theme'
        colors = dict(accent='#7aa2f7', cyan='#449dab', background='#1a1b26',
                      foreground='#a9b1d6', lighter_background='#292e42',
                      yellow='#e0af68', green='#9ece6a', red='#f7768e', magenta='#ad8ee6')
        try:
            colors.update(tomllib.loads((directory / 'colors.toml').read_text()))
        except (OSError, ValueError):
            pass
        try:
            btop = dict(re.findall(r'theme\[([a-z_]+)\]="(#[0-9a-fA-F]{6})"',
                                   (directory / 'btop.theme').read_text()))
        except OSError:
            btop = {}
        self.register_theme(Theme(name='omarchy', primary=btop.get('hi_fg', colors['accent']),
            secondary=colors['cyan'], accent=colors['magenta'],
            background=btop.get('main_bg', colors['background']),
            foreground=btop.get('main_fg', colors['foreground']),
            surface=btop.get('selected_bg', colors['lighter_background']),
            panel=colors['background'], warning=colors['yellow'], success=colors['green'],
            error=colors['red'], dark=colors.get('mode') != 'light', variables={
                'light-border': btop.get('cpu_box', colors['magenta']),
                'sound-border': btop.get('mem_box', colors['green']),
                'link-border': btop.get('net_box', colors['red']),
            }))
        self.theme = 'omarchy'

    def compose(self) -> ComposeResult:
        with VerticalScroll(id='page'):
            yield Static(f'sound lighting  ·  {VERSION}', id='brand')
            yield Static(self.backend.connection_text, id='link', markup=False)
            yield Static('Connecting…', id='health')
            with Horizontal(id='panels'):
                with Vertical(id='controls', classes='panel'):
                    yield Label('light', classes='eyebrow')
                    yield Label('Mode')
                    with Horizontal(classes='row'):
                        yield Button('Standby', compact=True, id='mode-idle')
                        yield Button('Sound', compact=True, id='mode-sound')
                        yield Button('Auto', compact=True, id='mode-auto')
                    yield Label('Color follows')
                    with Horizontal(classes='row'):
                        yield Button('Palette', compact=True, id='source-palette')
                        yield Button('Frequency', compact=True, id='source-spectrum')
                    yield Label('Palette', id='palette-label')
                    yield Select([(scene_label(s, self.initial), s) for s in SCENES if s != 'spectrum'],
                                 allow_blank=False, value=self.initial.scene, compact=True, id='scene')
                    yield Label('Brightness')
                    yield Slider(round(self.initial.brightness / 255 * 100), id='brightness-slider',
                                 tooltip='Drag and release · arrows ±1 · PgUp/PgDn ±10 · Home/End')
                    yield Label('White · warm ↔ cool')
                    yield Slider(self.initial.white, id='white-slider',
                                 tooltip='Moving this selects steady White. RGB tint, not calibrated Kelvin.')
                    with Horizontal(classes='row'):
                        yield Input(str(round(self.initial.brightness / 255 * 100)), type='integer',
                                    id='brightness', max_length=3, compact=True,
                                    tooltip='Exact brightness % · Enter to apply')
                        yield Button('Apply %', compact=True, id='set-brightness')
                        yield Button('Color…', compact=True, id='pick-color')
                    yield Static('', id='saved', markup=False)
                with Vertical(id='monitor', classes='panel'):
                    yield Label('sound', classes='eyebrow')
                    yield Static('—', id='mode')
                    yield Static('Waiting for telemetry', id='level')
                    yield ProgressBar(total=60, show_eta=False, show_percentage=False, id='meter')
                    yield Sparkline(list(self.history), summary_function=max, id='wave')
                    yield Static('RMS · 60s', classes='muted')
                    yield Static('', id='capture', markup=False)
                    yield Static('', id='timing', markup=False)
            yield SpectrumPane(id='spectrum-pane', classes='panel')
            with Vertical(classes='panel', id='connection'):
                yield Label('link', classes='eyebrow')
                yield Static('Checking audio…', id='route', markup=False)
                yield Static('', id='runtime', markup=False)
        yield Footer()

    def on_mount(self):
        self.query_one('#spectrum').tooltip = ('Laptop FFT: 2,048 samples at 48 kHz (42.67 ms), up to 20 Hz. '
            'SSH RTT and feature freshness are not sound-to-light latency.')
        self.query_one('#timing').tooltip = ('Analysis window and requested PipeWire buffer only. '
            'Bluetooth transport and LED smoothing add delay; these figures are not a total.')
        if hasattr(self.backend, 'run'):
            self.run_worker(self.backend.run(), name='Pi connection')
        self.sync_controls()
        self.refresh_status()
        self.refresh_audio()
        self.set_interval(.2, self.refresh_status)
        self.set_interval(5, self.refresh_audio)
        self.query_one('#scene').focus()

    def on_resize(self, event):
        self.query_one('#panels').set_class(event.size.width < 80, 'narrow')

    async def on_unmount(self):
        if hasattr(self.backend, 'close'):
            await self.backend.close()

    def sync_controls(self, keep_draft=False):
        if not self.is_running:
            return
        try:
            config = self.backend.settings()
        except (OSError, ValueError) as error:
            self.message(str(error))
            return
        brightness_input = self.query_one('#brightness', Input)
        old_value = str(round(self.displayed.brightness / 255 * 100)) if self.displayed else None
        dirty = brightness_input.value != old_value
        previous = self.displayed
        self.displayed = config
        if previous is None or previous.color != config.color:
            picker = self.query_one('#scene', Select)
            with picker.prevent(Select.Changed):
                picker.set_options([(scene_label(s, config), s) for s in SCENES if s != 'spectrum'])
        for name, value in [('scene', config.scene)]:
            widget = self.query_one('#' + name, Select)
            with widget.prevent(Select.Changed):
                widget.value = value
        if not keep_draft or not dirty:
            brightness_input.value = str(round(config.brightness / 255 * 100))
        for widget in self.query('#controls Button, #controls Input, #controls Select, #controls Slider'):
            widget.disabled = not self.backend.controls_available
        if not self.slider_pending and not self.slider_saving:
            for name, value in [('brightness', round(config.brightness / 255 * 100)), ('white', config.white)]:
                slider = self.query_one('#' + name + '-slider', Slider)
                if not slider.dragging:
                    slider.value = value
        self.show_choices(config)
        if self.backend.readonly:
            self.message('Read-only')

    def show_choices(self, config):
        for value in ('idle', 'sound', 'auto'):
            self.query_one('#mode-' + value, Button).variant = 'primary' if config.behavior == value else 'default'
        for value in ('palette', 'spectrum'):
            self.query_one('#source-' + value, Button).variant = 'primary' if config.color_source == value else 'default'
        self.query_one('#palette-label', Label).update('Standby palette' if config.color_source == 'spectrum' else 'Palette')
        self.query_one('#spectrum-pane').display = config.color_source == 'spectrum'

    def message(self, text):
        self.query_one('#saved', Static).update(text)

    @work(group='controls')
    async def save(self, **values):
        try:
            await self.backend.apply(**values)
        except (OSError, ValueError) as error:
            self.message(str(error))
            return
        self.sync_controls()
        self.message('Saved')

    @on(Select.Changed)
    def select_changed(self, event):
        if event.value is Select.NULL or event.value != event.select.value:
            return
        try:
            if getattr(self.backend.settings(), event.select.id) == event.value:
                return
        except (OSError, ValueError) as error:
            self.message(str(error))
            return
        self.save(**{event.select.id: event.value})

    @on(Slider.Changed)
    def slider_changed(self, event):
        if not self.backend.controls_available:
            return
        if event.slider.id == 'brightness-slider':
            self.slider_pending['brightness'] = round(event.value * 255 / 100)
            self.query_one('#brightness', Input).value = str(event.value)
        else:
            self.slider_pending.update(white=event.value, scene='workshop', color_source='palette')
        if self.slider_timer:
            self.slider_timer.stop()
        self.slider_timer = self.set_timer(.25, self.save_sliders)

    @work(group='sliders')
    async def save_sliders(self):
        # One in-flight write; fast keyboard changes collapse to the newest value.
        if self.slider_saving:
            return
        self.slider_saving = True
        try:
            while self.slider_pending:
                values, self.slider_pending = self.slider_pending, {}
                await self.backend.apply(**values)
            self.message('Saved')
        except (OSError, ValueError) as error:
            self.slider_pending.clear()  # Never replay a disconnected edit later.
            self.message(str(error))
        finally:
            self.slider_saving = False
            self.sync_controls()

    @on(Input.Submitted, '#brightness')
    def brightness_enter(self):
        self.set_brightness()

    def set_brightness(self, delta=0):
        try:
            value = int(self.query_one('#brightness', Input).value)
            value = max(0, min(100, value + delta)) if delta else value
            if not 0 <= value <= 100:
                raise ValueError
        except ValueError:
            self.message('Enter 0–100.')
            return
        self.save(brightness=round(value * 255 / 100))

    def on_button_pressed(self, event):
        actions = {'set-brightness': self.set_brightness, 'pick-color': self.action_color}
        name = event.button.id or ''
        if name.startswith('mode-'):
            self.save(behavior=name.removeprefix('mode-'))
        elif name.startswith('source-'):
            self.save(color_source=name.removeprefix('source-'))
        elif name in actions:
            actions[name]()

    def action_auto(self):
        if not isinstance(self.screen, ColorPicker):
            self.save(behavior='auto')

    def action_idle(self):
        if not isinstance(self.screen, ColorPicker):
            self.save(behavior='idle')

    def action_sound(self):
        if not isinstance(self.screen, ColorPicker):
            self.save(behavior='sound')

    def action_frequency(self):
        if not isinstance(self.screen, ColorPicker):
            self.save(color_source='spectrum')

    def action_color(self):
        if not self.backend.controls_available or isinstance(self.screen, ColorPicker):
            return
        try:
            color = self.backend.settings().color
        except (OSError, ValueError) as error:
            self.message(str(error))
            return
        self.push_screen(ColorPicker(color), self.color_chosen)

    def color_chosen(self, color):
        if color is not None:
            self.save(scene='custom', color=color, color_source='palette')

    def refresh_status(self):
        if not self.is_running or not self.query('#page'):
            return
        self.data = d = self.backend.status()
        stale = d['stale']
        self.query_one('#link', Static).update(self.backend.connection_text)
        if hasattr(self.backend, 'available') and not self.backend.available:
            self.query_one('#route', Static).update(self.backend.error)
        elif hasattr(self.backend, 'graph') and self.backend.graph != self.graph:
            self.refresh_audio()
        for widget in self.query('#controls Button, #controls Input, #controls Select, #controls Slider'):
            widget.disabled = not self.backend.controls_available
        if not isinstance(self.screen, ColorPicker) and not isinstance(self.focused, Input):
            try:
                if self.backend.settings() != self.displayed:
                    self.sync_controls(keep_draft=True)
            except (OSError, ValueError):
                pass
        self.query_one('#health', Static).update(Text(
            '● OFFLINE · awaiting telemetry' if stale else
            f"● LIVE   {'FREQUENCY' if d.get('spectrum_active') else d.get('scene', '?').upper()}  · {d.get('brightness_percent', '?')}%",
            style=(self.current_theme.warning or '#ffbf69') if stale else
                  (self.current_theme.success or '#6ee7c4')))
        mode = ('No signal data' if stale else ('Sound · waiting for audio' if d.get('behavior') == 'sound' else 'Quiet → standby') if d.get('mode') == 'quiet'
                else 'Reactive' if d.get('mode') == 'sound' else 'Standby')
        self.query_one('#mode', Static).update(mode)
        rms = 0 if stale else d.get('rms', 0)
        db = max(-60, 20 * math.log10(max(rms, 0.000001)))
        self.query_one('#meter', ProgressBar).update(progress=db + 60)
        self.query_one('#level', Static).update('— dBFS' if stale else f'{db:5.1f} dBFS   /   RMS {rms:.4f}')
        if time.monotonic() >= self.history_at:
            self.history.append(rms)
            self.history_at = time.monotonic() + 1
        self.query_one('#wave', Sparkline).data = list(self.history)
        age = d.get('sound_age_seconds')
        quiet = d.get('quiet_seconds', 10)
        timing = ('No sound yet' if age is None else f'Silent {age:.0f}s')
        if d.get('mode') in ('sound', 'quiet') and d.get('behavior') == 'auto' and not stale:
            timing = f'Standby in {max(0, quiet - (age or 0)):.0f}s'
        self.query_one('#capture', Static).update('Capture —' if stale else
            f"Capture {d.get('audio', '?')} · {d.get('sample_rate', 48000) / 1000:g} kHz · {d.get('sample_bits', 16)}-bit mono\n"
            f"{timing} · glow {d.get('output_gain_percent', 100)}%\n"
            f"Retries {d.get('capture_retries', 0)} · windows {d.get('audio_blocks', 0):,}\n"
            f"Peak {d.get('peak', 0):.3f} · clipped {d.get('clipped_blocks', 0)}")
        window, request = d.get('analysis_window_ms'), d.get('capture_requested_ms')
        self.query_one('#timing', Static).update('Timing —' if stale else
            f"Window {window:g} ms · request {request:g} ms\nLatency · end-to-end unmeasured"
            if window is not None and request is not None else 'Latency · end-to-end unmeasured')
        self.query_one(SpectrumPane).show_status(d)
        frame_age = d.get('audio_age_seconds')
        age_text = 'no frames yet' if frame_age is None else f'frame {frame_age}s'
        self.query_one('#runtime', Static).update('Engine —' if stale else
            f"Up {d.get('uptime_seconds', 0) / 3600:.1f}h · PID {d.get('pid', '?')} · "
            f"recorder {d.get('recorder_pid') or 'waiting'} · {age_text}")
        if d.get('settings_error'):
            self.message('Engine rejected settings: ' + d['settings_error'])

    @work(exclusive=True, group='audio')
    async def refresh_audio(self):
        graph = await self.backend.audio(self.data.get('target', 'lighting_audio'))
        self.graph = graph
        text = graph.get('error')
        if not text:
            text = (f"BT  {', '.join(graph['peers']) or 'disconnected'}\n"
                    f"Route  {', '.join(graph['routed']) or 'idle'} · "
                    f"sink {'ready' if graph['sink'] else 'missing'}\n"
                    f"USB  {', '.join(graph['usb']) or 'absent'} · {graph['inputs']} inputs"
                    )
        if self.is_running and self.query('#route'):
            self.query_one('#route', Static).update(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='/etc/sound-lighting.json')
    parser.add_argument('--status-file', default='/run/sound-lighting/status.json')
    parser.add_argument('--audio-user', default='pi')
    parser.add_argument('--read-only', action='store_true')
    parser.add_argument('--host', help='Run locally and reconnect to this Pi SSH alias automatically')
    parser.add_argument('--remote-repo', default='/home/pi/Sound-Lighting-Project')
    args = parser.parse_args()
    if args.host:
        from remote_backend import RemoteBackend
        backend = RemoteBackend(args.host, args.remote_repo, args.read_only)
    else:
        backend = Backend(args.config, args.status_file, args.audio_user, args.read_only)
    Dashboard(backend).run()


if __name__ == '__main__':
    main()
