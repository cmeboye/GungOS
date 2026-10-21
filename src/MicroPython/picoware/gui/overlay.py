"""Overlay - the one box drawn over a screen: F9 help, alerts and info pages.

A help line is either a heading ending in ':', a key and its meaning
separated by a tab ('F9\\tshow or close this help'), or plain text. Long
lines wrap inside the box.

The box keeps the screen rows it covers and puts them back when it closes,
so the view behind it keeps its state and needs no redraw.
"""
from picoware.system.font import FONT_XTRA_SMALL as XS

RECT = (8, 26, 304, 279)  # below a header, above the one-line footer
HINT = 'UP/DOWN scroll   F9 / ESC close'
PITCH = 11
CHAR = 6  # extra-small font advance
KEY_CHARS = 13  # key column of 'key<TAB>meaning' lines


def capacity(height):
    return max(1, (height - 52) // PITCH)


def wrap(text, width):
    words, out, line = str(text).split(), [], ''
    for word in words:
        while len(word) > width:
            if line:
                out.append(line)
                line = ''
            out.append(word[:width])
            word = word[width:]
        if line and len(line) + 1 + len(word) > width:
            out.append(line)
            line = word
        else:
            line = line + ' ' + word if line else word
    out.append(line)
    return out


def layout(lines, width):
    """Wrap lines to fit `width` pixels of box; meanings stay in their column."""
    chars = max(8, (width - 28) // CHAR)
    out = []
    for line in lines:
        if '\t' in line:
            key, meaning = line.split('\t', 1)
            for i, part in enumerate(wrap(meaning, chars - KEY_CHARS)):
                out.append((key if i == 0 else '') + '\t' + part)
        elif line.endswith(':') or len(line) < chars:
            out.append(line)  # short lines keep their spacing (tables)
        else:
            out.extend(wrap(line, chars - 1))
    return out


def paint(draw, p, rect, title, lines, first, hint=HINT):
    """Draw laid-out lines in a titled box; nothing is presented."""
    x, y, w, h = rect
    count = capacity(h)
    shown = lines[first:first + count]
    draw._fill_rectangle(x, y, w, h, p.BG)
    draw._rectangle(x, y, w, h, p.ACCENT)
    draw._text(x + 8, y + 7, title, p.ACCENT, XS)
    if len(lines) > count:
        status = '%d-%d / %d' % (first + 1, first + len(shown), len(lines))
        draw._text(x + w - 8 - draw.len(status, XS), y + 7, status, p.MUTED, XS)
        track = h - 49
        thumb = max(8, track * count // len(lines))
        top = y + 23 + (track - thumb) * first // max(1, len(lines) - count)
        draw._line(x + w - 6, y + 23, x + w - 6, y + 23 + track, p.GRID)
        draw._fill_rectangle(x + w - 7, top, 3, thumb, p.ACCENT)
    text(draw, p, x + 10, y + 24, w - 28, shown)
    if hint:
        draw._text(x + 10, y + h - 14, hint[:(w - 20) // CHAR], p.MUTED, XS)


def text(draw, p, x, y, width, lines):
    """Draw laid-out lines from (x, y): headings in the accent colour at x,
    keys in the accent colour and everything else indented under them."""
    limit = max(1, (width - 4) // CHAR)
    for i, line in enumerate(lines):
        ty = y + PITCH * i
        if '\t' in line:
            key, meaning = line.split('\t', 1)
            draw._text(x + 4, ty, key[:KEY_CHARS - 1], p.ACCENT, XS)
            draw._text(x + 4 + KEY_CHARS * CHAR, ty, meaning[:limit - KEY_CHARS], p.TEXT, XS)
        elif line.endswith(':'):
            draw._text(x, ty, line[:limit], p.ACCENT, XS)
        else:
            draw._text(x + 4, ty, line[:limit], p.TEXT, XS)


class Overlay:
    """A box over the current screen; key() returns False once it has closed."""

    def __init__(self, vm, title, lines, rect=None, hint=HINT, any_key=False):
        from picoware.gui.style import system_palette
        self.vm, self.title, self.hint, self.any_key = vm, title, hint, any_key
        self.rect = rect or RECT
        self.lines = layout(lines, self.rect[2])
        self.palette = system_palette(vm)
        self.first = 0
        self.saved = None
        self.shown = False

    @property
    def limit(self):
        return max(0, len(self.lines) - capacity(self.rect[3]))

    def open(self):
        draw = self.vm.draw
        x, y, w, h = self.rect
        self.shown = True
        from gc import collect
        collect()
        try:
            self.saved = [draw._read_row(row) for row in range(y, y + h)]
        except (MemoryError, AttributeError):
            self.saved = None  # close() reports that the view must redraw
        self.paint()

    def paint(self):
        paint(self.vm.draw, self.palette, self.rect, self.title, self.lines, self.first, self.hint)
        self.vm.draw.swap()

    def key(self, button):
        from picoware.system import buttons as k
        step = {k.BUTTON_UP: -1, k.BUTTON_DOWN: 1}.get(button, 0)
        page = capacity(self.rect[3])
        step = step or {k.BUTTON_LEFT: -page, k.BUTTON_RIGHT: page}.get(button, 0)
        if step and self.limit:
            self.first = max(0, min(self.limit, self.first + step))
            self.paint()
            return True
        if self.any_key or button in (k.BUTTON_F9, k.BUTTON_ESCAPE, k.BUTTON_BACK):
            return False
        return True

    def close(self):
        """Put back the covered rows; False if they were not kept."""
        rows, self.saved = self.saved, None
        if rows is None:
            return False
        draw = self.vm.draw
        width, y = int(draw.size.x), self.rect[1]
        for i, row in enumerate(rows):
            draw._bytearray(0, y + i, width, 1, row)
        draw.swap()
        return True


def modal(vm, title, lines, rect=None, hint=HINT, any_key=False):
    """Show a box and wait until it closes, for code that owns the input
    loop (alerts, the PicoIDE editor). Returns the key that closed it."""
    from time import sleep_ms
    box = Overlay(vm, title, lines, rect, hint, any_key)
    box.open()
    inp = vm.input_manager
    inp.reset()
    while True:
        button = inp.button
        if button == -1:
            sleep_ms(10)  # wait without spinning the CPU
            continue
        inp.reset()
        button = inp.normalize_button(button)
        if not box.key(button):
            box.close()
            return button


def fitted(lines, width=RECT[2]):
    """A rect centred on the screen, just tall enough for the lines."""
    count = len(layout(lines, width))
    height = min(RECT[3], 52 + PITCH * max(1, count))
    return (RECT[0], RECT[1] + (RECT[3] - height) // 2, width, height)


class Popup(Overlay):
    """A list of options in the box; key() returns None while it stays open,
    then the chosen index, or -1 for ESC."""

    PITCH = 17

    def __init__(self, vm, title, options, selected=0):
        height = min(RECT[3], 44 + self.PITCH * max(1, len(options)))
        rect = (RECT[0], RECT[1] + (RECT[3] - height) // 2, RECT[2], height)
        super().__init__(vm, title, (), rect, 'ENTER choose   ESC cancel')
        self.options = [str(option) for option in options]
        self.selected = max(0, min(selected, len(self.options) - 1))

    def paint(self):
        from picoware.system.font import FONT_SMALL
        draw, p = self.vm.draw, self.palette
        x, y, w, h = self.rect
        draw._fill_rectangle(x, y, w, h, p.BG)
        draw._rectangle(x, y, w, h, p.ACCENT)
        draw._text(x + 8, y + 7, self.title[:(w - 16) // CHAR], p.ACCENT, XS)
        count = max(1, (h - 44) // self.PITCH)
        first = min(max(0, self.selected - count // 2), max(0, len(self.options) - count))
        limit = (w - 24) // max(1, draw.len('M', FONT_SMALL))
        for i in range(first, min(len(self.options), first + count)):
            ty = y + 24 + (i - first) * self.PITCH
            if i == self.selected:
                draw._fill_rectangle(x + 5, ty - 2, w - 10, self.PITCH - 1, p.SELECT)
                draw._rectangle(x + 5, ty - 2, w - 10, self.PITCH - 1, p.ACCENT)
            draw._text(x + 12, ty + 1, self.options[i][:limit], p.TEXT, FONT_SMALL)
        draw._text(x + 10, y + h - 14, self.hint, p.MUTED, XS)
        draw.swap()

    def key(self, button):
        from picoware.system import buttons as k
        if button in (k.BUTTON_UP, k.BUTTON_LEFT, k.BUTTON_DOWN, k.BUTTON_RIGHT) and self.options:
            step = -1 if button in (k.BUTTON_UP, k.BUTTON_LEFT) else 1
            self.selected = (self.selected + step) % len(self.options)
            self.paint()
            return None
        if button in (k.BUTTON_CENTER, k.BUTTON_ENTER):
            return self.selected
        if button in (k.BUTTON_ESCAPE, k.BUTTON_BACK):
            return -1
        return None
