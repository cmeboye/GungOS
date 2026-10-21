"""Transactional appearance draft and shared colour picker."""
from picoware.gui import appearance, style
from picoware.gui.theme_picker import ThemePicker, to_hex
from picoware.system import buttons as key
from picoware.system.font import FONT_SMALL as SM, FONT_XTRA_SMALL as XS

FIELDS = (('Accent color', 'theme_color'), ('Background color', 'background_color'),
          ('Text on dark', 'text_on_dark'), ('Text on light', 'text_on_light'))


class AppearanceEditor:
    def __init__(self, vm, values):
        self.vm, self.values = vm, dict(values)
        self.index, self.picker, self.error = 0, None, ''

    def handle(self, button):
        if button == key.BUTTON_NONE:
            return None
        if self.picker is not None:
            result = self.picker.handle(button)
            if result == 'save':
                self.values[FIELDS[self.index][1]] = self.picker.colour
            if result in ('save', 'cancel'):
                self.picker = None
                self.draw()
            return None
        if button == key.BUTTON_ESCAPE:
            return 'cancel'
        if button == key.BUTTON_F1:
            return 'save'
        if button == key.BUTTON_F2:
            self.values = dict(appearance.DEFAULTS)
            self.error = ''
        elif button in (key.BUTTON_UP, key.BUTTON_DOWN):
            self.index = (self.index + (1 if button == key.BUTTON_DOWN else -1)) % 5
        elif button in (key.BUTTON_CENTER, key.BUTTON_ENTER):
            if self.index == 4:
                self.values = dict(appearance.DEFAULTS)
                self.error = ''
            else:
                label, field = FIELDS[self.index]
                self.picker = ThemePicker(self.vm, self.values[field], field, self.values, label)
                self.picker.draw()
                return None
        self.draw()
        return None

    def draw(self):
        from picoware.gui.theme_picker import preview
        d = self.vm.draw
        # Editing controls retain a readable palette even with invisible draft text.
        p = style.colors(0, 0xFFFF, self.vm.selected_color)
        d.fill_screen(p.BG)
        style.header(d, 'Settings / Appearance', palette=p, height=24)
        for i in range(5):
            y = 34 + i * 30
            if i == self.index:
                d._fill_rectangle(6, y - 4, 308, 27, p.SELECT)
                d._rectangle(6, y - 4, 308, 27, p.ACCENT)
            label = FIELDS[i][0] if i < 4 else 'Reset appearance'
            d._text(13, y, label, p.TEXT, SM)
            if i < 4:
                color = self.values[FIELDS[i][1]]
                d._fill_rectangle(225, y, 16, 14, color)
                d._rectangle(225, y, 16, 14, p.MUTED)
                d._text(247, y + 3, '#' + to_hex(color), p.TEXT, XS)
        d._text(10, 190, 'ENTER edits  /  changes preview until saved', p.MUTED, XS)
        preview(d, self.values, 207, 77)
        style.footer(d, self.error, bool(self.error), p)
        d.swap()
