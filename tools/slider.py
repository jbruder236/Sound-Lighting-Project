"""Small percentage slider; dragging previews locally, release commits once."""
from rich.text import Text
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget


class Slider(Widget, can_focus=True):
    DEFAULT_CSS = '''
    Slider { height: 1; color: $primary; margin-bottom: 1; }
    Slider:focus { background: $surface; color: $accent; }
    Slider:disabled { opacity: 40%; }
    '''
    value = reactive(0)
    dragging = False

    class Changed(Message):
        def __init__(self, slider):
            super().__init__()
            self.slider, self.value = slider, slider.value

        @property
        def control(self):
            return self.slider

    def __init__(self, value=0, tooltip=None, **kwargs):
        super().__init__(**kwargs)
        self.value = value
        self.tooltip = tooltip

    def validate_value(self, value):
        return max(0, min(100, round(value)))

    @property
    def track_width(self):
        return max(2, self.content_size.width - 6)

    def render(self):
        width = self.track_width
        thumb = round(self.value / 100 * (width - 1))
        text = Text('━' * thumb + '●', no_wrap=True)
        text.append('─' * (width - thumb - 1), style='dim')
        text.append(f' {self.value:3d}%')
        return text

    def move_to(self, x):
        self.value = (x - self.gutter.left) / (self.track_width - 1) * 100

    def on_mouse_down(self, event):
        if self.disabled or event.button != 1:
            return
        event.stop()
        self.focus()
        self.dragging = True
        self.capture_mouse()
        self.move_to(event.x)

    def on_mouse_move(self, event):
        if self.dragging:
            self.move_to(event.x)
            event.stop()

    def on_mouse_up(self, event):
        if self.dragging and event.button == 1:
            self.dragging = False
            self.release_mouse()
            event.stop()
            if not self.disabled:
                self.move_to(event.x)
                self.post_message(self.Changed(self))

    def on_key(self, event):
        if self.disabled:
            return
        values = {'left': self.value - 1, 'down': self.value - 1,
                  'right': self.value + 1, 'up': self.value + 1,
                  'pageup': self.value + 10, 'pagedown': self.value - 10,
                  'home': 0, 'end': 100}
        if event.key in values:
            self.value = values[event.key]
            self.post_message(self.Changed(self))
            event.stop()
            event.prevent_default()
