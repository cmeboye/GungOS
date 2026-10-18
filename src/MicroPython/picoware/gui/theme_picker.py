"""Accent swatches and a bounded hex editor with an unsaved live preview."""
from picoware.system import buttons as key
from picoware.system.font import FONT_SMALL, FONT_MEDIUM, FONT_XTRA_SMALL
from picoware.gui.status_bar import foreground


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
)


class ThemePicker:
    COLUMNS = 5

    def __init__(self, vm, colour):
        self.vm = vm
        self.colour = colour
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
        colour, ink = self.colour, foreground(self.colour)
        draw.fill_screen(bg)
        draw._fill_rectangle(0, 0, 320, 24, colour)
        draw._text(8, 6, 'Custom colour' if self.editing else 'Theme colour', ink, FONT_SMALL)
        draw._text(253, 8, 'PREVIEW', ink, FONT_XTRA_SMALL)
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
            draw._text(16, 168, 'Matched to the nearest display colour.', muted, FONT_XTRA_SMALL)
            label = 'Display colour'
        else:
            draw._text(8, 32, 'Choose an accent for the dark interface.', muted, FONT_XTRA_SMALL)
            for index, (name, swatch) in enumerate(PRESETS):
                x, y = 8 + (index % self.COLUMNS) * 62, 49 + (index // self.COLUMNS) * 24
                draw._fill_rectangle(x, y, 56, 18, swatch)
                if index == self.index:
                    draw._rectangle(x - 2, y - 2, 60, 22, text)
                    draw._rectangle(x, y, 56, 18, 0)
                    draw._text(x + 22, y + 5, '*', foreground(swatch), FONT_SMALL)
            label = PRESETS[self.index][0] if self.index >= 0 else 'Custom'
        draw._text(8, 200, label, text, FONT_SMALL)
        hex_label = '#' + to_hex(colour)
        draw._text(312 - draw.len(hex_label, FONT_SMALL), 200, hex_label, text, FONT_SMALL)
        # Preview both ordinary text and a selected control on the dark surface.
        draw._rectangle(8, 223, 304, 57, colour if colour else muted)
        draw._text(18, 233, 'Live preview', text, FONT_SMALL)
        draw._text(18, 254, 'GungOS / dark', muted, FONT_XTRA_SMALL)
        draw._fill_rectangle(183, 235, 117, 30, colour)
        draw._text(194, 245, 'Selected', ink, FONT_SMALL)
        if self.error:
            draw._fill_rectangle(4, 282, 312, 16, 0x5800)
            draw._text(8, 286, self.error, text, FONT_XTRA_SMALL)
        draw._fill_rectangle(0, 300, 320, 20, colour)
        hint = 'ENTER preview   ESC discard edit' if self.editing else 'Arrows browse  F2 custom  ENTER save  ESC cancel'
        draw._text(6, 306, hint, ink, FONT_XTRA_SMALL)
        draw.swap()
