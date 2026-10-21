"""Shared colour swatches, hex editing and a local appearance preview."""
from picoware.system import buttons as key
from picoware.system.font import FONT_SMALL, FONT_MEDIUM, FONT_XTRA_SMALL
from picoware.gui.appearance import is_light


def from_hex(value):
    """Convert six RGB888 hex digits to the nearest RGB565 colour."""
    value = value.strip()
    if value.startswith('#'):
        value = value[1:]
    if len(value) != 6 or any(c not in '0123456789abcdefABCDEF' for c in value):
        raise ValueError('Enter six hex digits: 0-9, A-F')
    rgb = int(value, 16)
    r, g, b = rgb >> 16, (rgb >> 8) & 255, rgb & 255
    return (((r * 31 + 127) // 255) << 11 |
            ((g * 63 + 127) // 255) << 5 | (b * 31 + 127) // 255)


def to_hex(colour):
    """Show the actual display colour, expanded back to RGB888."""
    return '%02X%02X%02X' % ((((colour >> 11) & 31) * 255 + 15) // 31,
                           (((colour >> 5) & 63) * 255 + 31) // 63,
                           ((colour & 31) * 255 + 15) // 31)


# Original presets keep their exact values for existing saved preferences.
PRESETS = (
    ('Red', 0xF800), ('Green', 0x07E0), ('Blue', 0x001F),
    ('Yellow', 0xFFE0), ('Violet', 0x915C), ('Cyan', 0x07FF),
    ('Orange', 0xFDA0), ('Pink', 0xFE19), ('Sky Blue', 0x867D),
    ('Light Grey', 0xD69A), ('Dark Grey', 0x7BEF), ('Dark Cyan', 0x03EF),
    ('Dark Green', 0x03E0), ('Brown', 0x9A60),
    ('Amber', from_hex('FFBF00')), ('Coral', from_hex('FF7F66')),
    ('Peach', from_hex('FFB38A')), ('Rose', from_hex('E878A0')),
    ('Lavender', from_hex('BFA0EF')), ('Lilac', from_hex('DBB8ED')),
    ('Indigo', from_hex('7464CF')), ('Steel Blue', from_hex('6096BA')),
    ('Ocean', from_hex('168AAD')), ('Teal', from_hex('20B2AA')),
    ('Mint', from_hex('98E0BA')), ('Sage', from_hex('9EB89B')),
    ('Olive', from_hex('B0B85D')), ('Sand', from_hex('D9BF8F')),
    ('Copper', from_hex('C88455')), ('Ice', from_hex('CEEAF0')),
    ('Black', 0), ('White', 0xFFFF),
)


class ThemePicker:
    COLUMNS = 5

    def __init__(self, vm, colour, field='theme_color', values=None, label='Theme colour'):
        self.vm = vm
        self.colour = colour
        from picoware.gui import appearance
        self.values = dict(values) if values is not None else appearance.values({
            'theme_color': vm.selected_color, 'background_color': vm.background_color,
            'text_on_dark': getattr(vm, 'text_on_dark', 0xFFFF),
            'text_on_light': getattr(vm, 'text_on_light', 0)})
        self.field, self.label = field, label
        self.index = next((i for i, item in enumerate(PRESETS) if item[1] == colour), -1)
        self.editing = False
        self.draft = ''
        self.cursor = 0
        self.replace = False
        self.error = ''
        self._edit_colour = colour
        self._edit_index = self.index

    def _select(self, index):
        self.index = index % len(PRESETS)
        self.colour = PRESETS[self.index][1]
        self.error = ''

    def _begin_edit(self):
        self._edit_colour, self._edit_index = self.colour, self.index
        self.draft = to_hex(self.colour)
        self.cursor = len(self.draft)
        self.replace = True
        self.error = ''
        self.editing = True

    def _update_draft(self):
        self.error = ''
        if len(self.draft) == 6:
            self.colour = from_hex(self.draft)
            self.index = -1

    def handle(self, button):
        """Return save/cancel, or None while browsing; never write settings here."""
        if button == key.BUTTON_NONE:
            return None
        if self.editing:
            if button == key.BUTTON_ESCAPE:
                self.colour, self.index = self._edit_colour, self._edit_index
                self.editing, self.error = False, ''
            elif button in (key.BUTTON_CENTER, key.BUTTON_ENTER):
                if len(self.draft) != 6:
                    self.error = 'Enter all six hex digits.'
                else:
                    self.colour, self.index = from_hex(self.draft), -1
                    self.editing, self.error = False, ''
            elif button in (key.BUTTON_BACK, key.BUTTON_DELETE, key.BUTTON_BACKSPACE):
                if self.cursor:
                    self.draft = self.draft[:self.cursor - 1] + self.draft[self.cursor:]
                    self.cursor -= 1
                self.replace = False
                self._update_draft()
            elif button in (key.BUTTON_LEFT, key.BUTTON_RIGHT, key.BUTTON_HOME, key.BUTTON_END):
                if button == key.BUTTON_HOME:
                    self.cursor = 0
                elif button == key.BUTTON_END:
                    self.cursor = len(self.draft)
                else:
                    self.cursor = max(0, min(len(self.draft), self.cursor + (1 if button == key.BUTTON_RIGHT else -1)))
                self.replace = False
            else:
                char = self.vm.input_manager.button_to_char(button).upper()
                if len(char) == 1 and char in '0123456789ABCDEF':
                    if self.replace:
                        self.draft, self.cursor, self.replace = '', 0, False
                    if len(self.draft) < 6:
                        self.draft = self.draft[:self.cursor] + char + self.draft[self.cursor:]
                        self.cursor += 1
                        self._update_draft()
                elif char == '#' and self.replace:
                    self.draft, self.cursor, self.replace = '', 0, False
        elif button == key.BUTTON_ESCAPE:
            return 'cancel'
        elif button in (key.BUTTON_CENTER, key.BUTTON_ENTER):
            return 'save'
        elif button == key.BUTTON_F2:
            self._begin_edit()
        elif button in (key.BUTTON_LEFT, key.BUTTON_RIGHT, key.BUTTON_UP, key.BUTTON_DOWN):
            if self.index < 0:
                self._select(0)
            else:
                step = {key.BUTTON_LEFT: -1, key.BUTTON_RIGHT: 1,
                        key.BUTTON_UP: -self.COLUMNS, key.BUTTON_DOWN: self.COLUMNS}[button]
                self._select(self.index + step)
        else:
            return None
        self.draw()
        return None

    def draw(self):
        draw = self.vm.draw
        bg, text, muted = 0, 0xFFFF, 0xAD55
        colour = self.colour
        draw.fill_screen(bg)
        from picoware.gui import style
        label='Appearance / '+self.label+(' / Custom' if self.editing else '')
        style.header(draw,label,palette=style.colors(bg,text,colour),height=24)
        if self.editing:
            draw._text(16, 43, 'Enter RGB hex: #RRGGBB', text, FONT_SMALL)
            draw._fill_rectangle(16, 70, 288, 44, 0x18C3)
            draw._rectangle(16, 70, 288, 44, text)
            display = '#' + self.draft + '_' * (6 - len(self.draft))
            draw._text(30, 83, display, text, FONT_MEDIUM)
            cursor_x = 30 + draw.len('#' + self.draft[:self.cursor], FONT_MEDIUM)
            draw._fill_rectangle(cursor_x, 106, max(2, draw.len('0', FONT_MEDIUM)), 2, text)
            draw._text(16, 130, 'BACK / DEL erase before the cursor', muted, FONT_XTRA_SMALL)
            draw._text(16, 146, 'LEFT / RIGHT move the cursor', muted, FONT_XTRA_SMALL)
            draw._text(16, 168, 'Screen uses a 256-colour palette.', muted, FONT_XTRA_SMALL)
            label = 'Display colour'
        else:
            draw._text(8, 32, 'Choose a colour; F2 enters #RRGGBB.', muted, FONT_XTRA_SMALL)
            for index, (name, swatch) in enumerate(PRESETS):
                x, y = 8 + (index % self.COLUMNS) * 62, 47 + (index // self.COLUMNS) * 22
                draw._fill_rectangle(x, y, 56, 18, swatch)
                if index == self.index:
                    draw._rectangle(x - 2, y - 2, 60, 21, text)
                    draw._rectangle(x, y, 56, 18, 0)
                    draw._text(x + 22, y + 5, '*', (0 if is_light(swatch) else 0xFFFF), FONT_SMALL)
            label = PRESETS[self.index][0] if self.index >= 0 else 'Custom'
        draw._text(8, 208, label, text, FONT_SMALL)
        hex_label = '#' + to_hex(colour)
        draw._text(312 - draw.len(hex_label, FONT_SMALL), 208, hex_label, text, FONT_SMALL)
        values = dict(self.values)
        values[self.field] = colour
        preview(draw, values, 229, 67)
        style.footer(draw, self.error, bool(self.error), style.colors(bg, text, colour))
        draw.swap()


def preview(draw, values, y, height):
    """Composite all four draft roles without mutating the system palette."""
    from picoware.gui.appearance import text_on, contrast
    bg, accent = values['background_color'], values['theme_color']
    dark, light = values['text_on_dark'], values['text_on_light']
    fg, ink = text_on(bg, dark, light), text_on(accent, dark, light)
    draw._fill_rectangle(8, y, 304, height - 14, bg)
    draw._rectangle(8, y, 304, height - 14, 0x8410)
    from picoware.assets.logos import paint
    # Explicit ink keeps this preview independent of the active appearance.
    paint(draw, 'gungOS_small', 16, y + 7, bg, accent, fg)
    draw._text(16, y + 27, 'Normal text', fg, FONT_SMALL)
    draw._fill_rectangle(183, y + 9, 117, 30, accent)
    draw._text(194, y + 19, 'Selected', ink, FONT_SMALL)
    # Both text roles remain visible while editing, even when the canvas and
    # accent currently use the same brightness class.
    draw._fill_rectangle(16, y + 40, 138, 12, 0)
    draw._text(20, y + 42, 'Text on dark', dark, FONT_XTRA_SMALL)
    draw._fill_rectangle(162, y + 40, 138, 12, 0xFFFF)
    draw._text(166, y + 42, 'Text on light', light, FONT_XTRA_SMALL)
    normal, selected = contrast(bg, fg), contrast(accent, ink)
    label = 'Contrast %.1f / %.1f' % (normal, selected)
    if min(normal, selected) < 4.5:
        label += '  Low contrast'
    # The indicator is outside the draft, always on an opaque safe surface.
    draw._fill_rectangle(8, y + height - 14, 304, 14, 0x1082)
    draw._text(12, y + height - 11, label, 0xFFE0 if min(normal, selected) < 4.5 else 0xFFFF, FONT_XTRA_SMALL)
