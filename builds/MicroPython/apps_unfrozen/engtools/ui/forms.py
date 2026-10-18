"""Single-line input for engineering forms: numbers (with arithmetic) and names."""
from picoware.system import buttons as keys


def parse_number(text):
    """A real number from typed text; arithmetic such as 6/4 or 2*pi is allowed."""
    text = text.strip()
    if not text:
        raise ValueError('Type a number')
    from engtools.calculator.evaluate import calculate
    value, assignment = calculate(text, {'Ans': 0}, 'RAD')
    if assignment is not None or isinstance(value, complex):
        raise ValueError('Type a number')
    return float(value)


def erase_key(vm, button):
    return button in (keys.BUTTON_BACKSPACE, keys.BUTTON_DELETE, vm.input_manager._key_back)


class LineEdit:
    """Edits one line of text. key() returns 'commit', 'cancel', 'up',
    'down' or None; the caller decides what a commit means."""

    def __init__(self, text='', limit=24):
        self.text, self.limit = text, limit
        self.cursor = len(text)

    def key(self, vm, button):
        if button == vm.input_manager._key_esc:
            return 'cancel'
        if button in (keys.BUTTON_CENTER, keys.BUTTON_TAB):
            return 'commit'
        if button in (keys.BUTTON_UP, keys.BUTTON_DOWN):
            return 'up' if button == keys.BUTTON_UP else 'down'
        if button == keys.BUTTON_LEFT:
            self.cursor = max(0, self.cursor - 1)
        elif button == keys.BUTTON_RIGHT:
            self.cursor = min(len(self.text), self.cursor + 1)
        elif button == keys.BUTTON_HOME:
            self.cursor = 0
        elif button == keys.BUTTON_END:
            self.cursor = len(self.text)
        elif erase_key(vm, button):
            if self.cursor:
                self.text = self.text[:self.cursor - 1] + self.text[self.cursor:]
                self.cursor -= 1
        else:
            char = vm.input_manager.button_to_char(button)
            if char and char not in ('\n', '\t') and len(self.text) < self.limit:
                self.text = self.text[:self.cursor] + char + self.text[self.cursor:]
                self.cursor += 1
        return None

    def draw(self, draw, x, y, width, color, cursor_color, font):
        """Draw the text in `width` pixels, scrolled to keep the cursor visible."""
        size = max(1, draw.len('M', font))
        room = max(1, width // size)
        first = max(0, self.cursor - room + 1)
        shown = self.text[first:first + room]
        draw._text(int(x), int(y), shown, color, font)
        cx = int(x + (self.cursor - first) * size)
        height = draw.get_font(font).height
        draw._fill_rectangle(cx, int(y) - 1, 2, height + 1, cursor_color)
