"""Live percentage slider with a generous hit area and precise dragging."""
from rich.text import Text
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget


class Slider(Widget, can_focus=True):
    DEFAULT_CSS = '''
    Slider { height: 3; padding: 1 0; color: $primary; }
    Slider:hover { background: $surface; }
    Slider:focus { background: $surface; color: $accent; }
    Slider:disabled { opacity: 40%; }
    '''
    value = reactive(0)
    dragging = False

    class Changed(Message):
        def __init__(self, slider, final=False):
            super().__init__()
            self.slider, self.value, self.final = slider, slider.value, final

        @property
        def control(self):
            return self.slider

    def __init__(self, value=0, tooltip=None, gradient=None, **kwargs):
        super().__init__(**kwargs)
        self.value = value
        self.tooltip = tooltip
        self.gradient = gradient
        self.drag_origin = self.drag_value = self.drag_start = 0

    def validate_value(self, value):
        return max(0, min(100, round(value)))

    @property
    def track_width(self):
        return max(2, self.content_size.width - 6)

    def render(self):
        width = self.track_width
        thumb = round(self.value / 100 * (width - 1))
        text = Text(no_wrap=True)
        for x in range(width):
            style = 'bold' if x == thumb else '' if x < thumb else 'dim'
            if self.gradient:
                a, b = self.gradient
                rgb = [round(int(a[j:j+2],16) * (1-x/(width-1)) +
                             int(b[j:j+2],16) * x/(width-1)) for j in (1,3,5)]
                style += ' #' + ''.join(f'{c:02x}' for c in rgb)
            text.append('◆' if x == thumb else '━' if x < thumb else '─', style=style)
        text.append(f' {self.value:3d}%', style='bold' if self.has_focus else '')
        return text

    def change(self, value, final=False):
        before = self.value
        self.value = value
        if self.value != before or final:
            self.post_message(self.Changed(self, final))

    def move_to(self, x, fine=False):
        scale = .2 if fine else 1
        self.drag_value = max(0, min(100, self.drag_value +
                              (x-self.drag_origin) / (self.track_width-1) * 100 * scale))
        self.drag_origin = x
        self.change(self.drag_value)

    def on_mouse_down(self, event):
        if self.disabled or event.button != 1:
            return
        event.stop()
        self.focus()
        x = event.x - self.gutter.left
        if not 0 <= x < self.track_width:
            return
        self.drag_start = self.value
        thumb = round(self.value / 100 * (self.track_width-1))
        # Grabbing the thumb keeps its exact value instead of snapping to a cell.
        if abs(x-thumb) > 1 and not event.shift:
            self.change(x / (self.track_width-1) * 100)
        self.drag_origin, self.drag_value = event.x, self.value
        self.dragging = True
        self.capture_mouse()

    def on_mouse_move(self, event):
        if self.dragging and not self.disabled:
            self.move_to(event.x, event.shift)
            event.stop()

    def on_mouse_up(self, event):
        if self.dragging and event.button == 1:
            self.dragging = False
            self.release_mouse()
            event.stop()
            if not self.disabled:
                self.move_to(event.x, event.shift)
                self.post_message(self.Changed(self, final=True))

    def on_mouse_release(self, event):
        self.dragging = False

    def watch_disabled(self, disabled):
        if disabled and self.dragging:
            self.dragging = False
            self.release_mouse()

    def on_key(self, event):
        if self.disabled:
            return
        if event.key == 'escape' and self.dragging:
            self.dragging = False
            self.release_mouse()
            self.change(self.drag_start, final=True)
        else:
            values = {'left': self.value - 1, 'down': self.value - 1,
                      'right': self.value + 1, 'up': self.value + 1,
                      'shift+left': self.value - 5, 'shift+right': self.value + 5,
                      'pageup': self.value + 10, 'pagedown': self.value - 10,
                      'home': 0, 'end': 100}
            if event.key not in values:
                return
            self.change(values[event.key])
        event.stop()
        event.prevent_default()

    def wheel(self, event, direction):
        # Unfocused sliders let the surrounding dashboard scroll normally.
        if self.has_focus and not self.disabled:
            self.change(self.value + direction * (1 if event.shift else 2))
            event.stop()
            event.prevent_default()

    def on_mouse_scroll_up(self, event):
        self.wheel(event, 1)

    def on_mouse_scroll_down(self, event):
        self.wheel(event, -1)
