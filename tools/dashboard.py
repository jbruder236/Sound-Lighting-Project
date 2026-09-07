#!/usr/bin/env python3
"""A terminal remote for the single running Sound Lighting service."""
import argparse
from collections import deque
import math
from pathlib import Path
import tomllib

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.theme import Theme
from textual.widgets import Button, Footer, Input, Label, ProgressBar, Select, Sparkline, Static

from dashboard_data import Backend
from settings import SCENES, VERSION, Settings


class ColorPicker(ModalScreen[str | None]):
    """A separate window: editing never touches the running lights."""
    BINDINGS = [('escape', 'cancel', 'Cancel')]

    def __init__(self, color):
        super().__init__()
        self.color = color

    def compose(self) -> ComposeResult:
        with Vertical(id='picker'):
            yield Label('MAKE IT YOUR COLOR', classes='eyebrow')
            yield Static('A single hue, with the same slow motion and soft music response.')
            yield Static(id='swatch')
            yield Label('Hex color · #RRGGBB')
            yield Input(self.color, id='hex', max_length=7)
            with Horizontal(classes='row'):
                for name, color in [('Amber', 'ff9646'), ('Rose', 'ff2870'), ('Ice', '00dcca'), ('Violet', '8040ff')]:
                    yield Button(name, id='preset-' + color)
            yield Static('', id='color-error')
            with Horizontal(classes='row'):
                yield Button('Cancel', id='cancel')
                yield Button('Save color', id='save-color', variant='primary')

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
        self.query_one('#color-error', Static).update(f'Preview {color.upper()} · Save selects the Custom scene')
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
    BINDINGS = [('q', 'quit', 'Close dashboard'), ('c', 'color', 'Color picker'),
                ('a', 'auto', 'Auto'), ('s', 'idle', 'Screensaver')]

    def __init__(self, backend=None):
        super().__init__()
        self.backend = backend or Backend()
        self.displayed = None
        self.load_omarchy_theme()
        self.history = deque([0.0] * 60, maxlen=60)
        self.data = {}
        self.graph = {}
        try:
            self.initial = self.backend.settings()
        except (OSError, ValueError):
            self.initial = Settings()

    def load_omarchy_theme(self):
        path = Path.home() / '.local/state/omarchy/current/theme/colors.toml'
        try:
            colors = tomllib.loads(path.read_text())
            self.register_theme(Theme(name='omarchy', primary=colors['accent'],
                secondary=colors['cyan'], accent=colors['accent'], background=colors['background'],
                foreground=colors['foreground'], surface=colors['lighter_background'],
                panel=colors['dark_background'], warning=colors['yellow'], success=colors['green'],
                error=colors['red'], dark=colors.get('mode') != 'light'))
            self.theme = 'omarchy'
        except (OSError, ValueError, KeyError):
            self.theme = 'textual-dark'

    def compose(self) -> ComposeResult:
        with VerticalScroll(id='page'):
            yield Static('S O U N D   L I G H T I N G', id='brand')
            yield Static(f'The garage, in good light.  /  {VERSION} · TUI', id='subtitle')
            yield Static(self.backend.connection_text, id='link', markup=False)
            yield Static('Connecting to the light engine…', id='health')
            with Horizontal(id='panels'):
                with Vertical(id='controls', classes='panel'):
                    yield Label('01 / THE LIGHT', classes='eyebrow')
                    yield Label('Scene')
                    yield Select([(s.title(), s) for s in SCENES], allow_blank=False,
                                 value=self.initial.scene, compact=True, id='scene')
                    yield Label('Behavior')
                    yield Select([('Auto · follow sound', 'auto'), ('Screensaver · always animate', 'idle')],
                                 allow_blank=False, value=self.initial.behavior, compact=True, id='behavior')
                    yield Label('Brightness · percent')
                    with Horizontal(classes='row'):
                        yield Button('−10', id='dimmer')
                        yield Input('100', type='integer', id='brightness', max_length=3)
                        yield Button('+10', id='brighter')
                    with Horizontal(classes='row'):
                        yield Button('Set brightness', id='set-brightness')
                        yield Button('Pick color…', id='pick-color')
                    yield Static('Changes fade in and survive reboot.', id='saved', markup=False)
                with Vertical(id='monitor', classes='panel'):
                    yield Label('02 / THE SOUND', classes='eyebrow')
                    yield Static('—', id='mode')
                    yield Static('Waiting for telemetry', id='level')
                    yield ProgressBar(total=60, show_eta=False, show_percentage=False, id='meter')
                    yield Sparkline(list(self.history), summary_function=max, id='wave')
                    yield Static('Last 60 seconds · relative RMS history', classes='muted')
                    yield Static('', id='capture', markup=False)
            with Vertical(classes='panel', id='connection'):
                yield Label('03 / THE CONNECTION', classes='eyebrow')
                yield Static('Inspecting PipeWire…', id='route', markup=False)
                yield Static('', id='runtime', markup=False)
            yield Static('Tab to move · Enter to choose · Closing this dashboard leaves the lights running.', classes='muted')
        yield Footer()

    def on_mount(self):
        if hasattr(self.backend, 'run'):
            self.run_worker(self.backend.run(), name='Pi connection')
        self.sync_controls()
        self.refresh_status()
        self.refresh_audio()
        self.set_interval(1, self.refresh_status)
        self.set_interval(5, self.refresh_audio)
        self.query_one('#scene').focus()

    def on_resize(self, event):
        self.query_one('#panels').set_class(event.size.width < 90, 'narrow')

    def sync_controls(self, keep_draft=False):
        try:
            config = self.backend.settings()
        except (OSError, ValueError) as error:
            self.message(str(error))
            return
        brightness_input = self.query_one('#brightness', Input)
        old_value = str(round(self.displayed.brightness / 255 * 100)) if self.displayed else None
        dirty = brightness_input.value != old_value
        self.displayed = config
        for name, value in [('scene', config.scene), ('behavior', config.behavior)]:
            widget = self.query_one('#' + name, Select)
            with widget.prevent(Select.Changed):
                widget.value = value
        if not keep_draft or not dirty:
            brightness_input.value = str(round(config.brightness / 255 * 100))
        for widget in self.query('#controls Button, #controls Input, #controls Select'):
            widget.disabled = not self.backend.controls_available
        if self.backend.readonly:
            self.message('Read-only · launch sudo lights tui to change settings.')

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
        self.message('Saved · the engine applies changes within a second.')

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
            self.message('Brightness must be a whole number from 0 to 100.')
            return
        self.save(brightness=round(value * 255 / 100))

    def on_button_pressed(self, event):
        actions = {'dimmer': lambda: self.set_brightness(-10), 'brighter': lambda: self.set_brightness(10),
                   'set-brightness': self.set_brightness, 'pick-color': self.action_color}
        if event.button.id in actions:
            actions[event.button.id]()

    def action_auto(self):
        if not isinstance(self.screen, ColorPicker):
            self.save(behavior='auto')

    def action_idle(self):
        if not isinstance(self.screen, ColorPicker):
            self.save(behavior='idle')

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
            self.save(scene='custom', color=color)

    def refresh_status(self):
        self.data = d = self.backend.status()
        stale = d['stale']
        self.query_one('#link', Static).update(self.backend.connection_text)
        for widget in self.query('#controls Button, #controls Input, #controls Select'):
            widget.disabled = not self.backend.controls_available
        if not isinstance(self.screen, ColorPicker) and not isinstance(self.focused, Input):
            try:
                if self.backend.settings() != self.displayed:
                    self.sync_controls(keep_draft=True)
            except (OSError, ValueError):
                pass
        self.query_one('#health', Static).update(Text(
            '● ENGINE OFFLINE / STALE · waiting for live telemetry' if stale else
            f"● LIVE   {d.get('scene', '?').upper()}  /  {d.get('brightness_percent', '?')}% brightness",
            style='yellow' if stale else 'green'))
        mode = ('TELEMETRY UNAVAILABLE' if stale else 'WORKSHOP · steady light' if d.get('scene') == 'workshop'
                else 'QUIET · dimmed, standby soon' if d.get('mode') == 'quiet'
                else 'SOUND REACTIVE' if d.get('mode') == 'sound' else 'SCREENSAVER · slow color')
        self.query_one('#mode', Static).update(mode)
        rms = 0 if stale else d.get('rms', 0)
        db = max(-60, 20 * math.log10(max(rms, 0.000001)))
        self.query_one('#meter', ProgressBar).update(progress=db + 60)
        self.query_one('#level', Static).update('Signal unavailable' if stale else f'{db:5.1f} dBFS   /   RMS {rms:.4f}')
        self.history.append(rms)
        self.query_one('#wave', Sparkline).data = list(self.history)
        age = d.get('sound_age_seconds')
        quiet = d.get('quiet_seconds', 4)
        timing = ('Waiting for sound' if age is None else f'Last sound {age:.0f}s ago')
        if d.get('mode') in ('sound', 'quiet') and d.get('behavior') == 'auto' and not stale:
            timing = f'Screensaver in {max(0, quiet - (age or 0)):.0f}s of quiet'
        self.query_one('#capture', Static).update('Capture health unavailable' if stale else
            f"Capture {d.get('audio', '?')} · {d.get('sample_rate', 48000) // 1000} kHz mono\n"
            f"{timing} · glow {d.get('output_gain_percent', 100)}%\n"
            f"Retries {d.get('capture_retries', 0)} · analyzed windows {d.get('audio_blocks', 0):,}\n"
            f"Peak {d.get('peak', 0):.3f} · clipped windows {d.get('clipped_blocks', 0)}")
        frame_age = d.get('audio_age_seconds')
        age_text = 'no frames yet' if frame_age is None else f'frame age {frame_age}s'
        self.query_one('#runtime', Static).update('Engine status unavailable' if stale else
            f"Engine up {d.get('uptime_seconds', 0) / 3600:.1f}h · PID {d.get('pid', '?')} · "
            f"recorder {d.get('recorder_pid') or 'waiting'} · {age_text}")
        if d.get('settings_error'):
            self.message('Engine rejected settings: ' + d['settings_error'])

    @work(exclusive=True, group='audio')
    async def refresh_audio(self):
        graph = await self.backend.audio(self.data.get('target', 'lighting_audio'))
        self.graph = graph
        text = graph.get('error')
        if not text:
            text = (f"Bluetooth: {', '.join(graph['peers']) or 'no connected audio peer'}\n"
                    f"Route to lights: {', '.join(graph['routed']) or 'no active Bluetooth route'} · "
                    f"capture sink {'available' if graph['sink'] else 'missing'}\n"
                    f"USB: {', '.join(graph['usb']) or 'not detected'} · {graph['inputs']} input node(s)\n"
                    'Device present ≠ audible signal. Connection poll: 5s. AUX/BT delay is unmeasured.')
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
