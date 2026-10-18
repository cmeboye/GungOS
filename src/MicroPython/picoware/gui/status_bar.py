"""Sixteen-pixel status bar with radio artwork and a text battery percentage."""
from time import ticks_ms, ticks_diff
from picoware.system.font import FONT_XTRA_SMALL
from picoware.assets.status_icons import ICONS, PALETTE

HEIGHT = 16


def foreground(background):
    """Choose readable text on the RGB565 theme colour."""
    red = ((background >> 11) & 31) * 255 // 31
    green = ((background >> 5) & 63) * 255 // 63
    blue = (background & 31) * 255 // 31
    return 0 if red * 299 + green * 587 + blue * 114 >= 145000 else 0xFFFF


def bitmap(name, background):
    """Composite the unscaled RGBA artwork into an RGB565 blit buffer.

    A one-pixel charcoal edge on bright themes keeps white outlines visible.
    The source pixels keep their supplied colours. Padding fits within the bar.
    """
    width, height, indices = ICONS[name]
    out_width, out_height = width + 2, height + 2
    raw = bytearray(bytes((background & 255, background >> 8)) * (out_width * out_height))
    if foreground(background) == 0:
        # Only the shadow is added; the source PNGs remain untouched.
        for y in range(height):
            for x in range(width):
                if PALETTE[indices[y * width + x]][3] >= 128:
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            offset = ((y + 1 + dy) * out_width + x + 1 + dx) * 2
                            raw[offset] = 0x82
                            raw[offset + 1] = 0x10
    for y in range(height):
        for x in range(width):
            red, green, blue, alpha = PALETTE[indices[y * width + x]]
            if not alpha:
                continue
            offset = ((y + 1) * out_width + x + 1) * 2
            if alpha != 255:
                under = raw[offset] | (raw[offset + 1] << 8)
                red = (red * alpha + ((under >> 11) & 31) * 255 // 31 * (255 - alpha) + 127) // 255
                green = (green * alpha + ((under >> 5) & 63) * 255 // 63 * (255 - alpha) + 127) // 255
                blue = (blue * alpha + (under & 31) * 255 // 31 * (255 - alpha) + 127) // 255
            colour = ((red >> 3) << 11) | ((green >> 2) << 5) | (blue >> 3)
            raw[offset] = colour & 255
            raw[offset + 1] = colour >> 8
    return out_width, out_height, raw


class StatusBar:
    def __init__(self, vm):
        self.vm = vm
        self._battery_at = None
        self._battery = (None, False)
        self._icons = {}

    def sample(self, force=False):
        vm = self.vm
        current = vm.time.rtc.datetime() if vm.time.is_set else None
        now = ticks_ms()
        if force or self._battery_at is None or ticks_diff(now, self._battery_at) >= 1000:
            self._battery_at = now
            try:
                percentage = max(0, min(100, int(vm.battery.percentage)))
                charging = bool(getattr(vm.battery, 'is_charging', False))
                self._battery = (percentage, charging)
            except (OSError, ValueError, TypeError):
                pass
        from picoware.system.bluetooth import connection_active
        wifi = bool(vm.has_wifi and vm.wifi.is_connected())
        bluetooth = bool(vm.has_bluetooth and connection_active())
        # Keep the existing Dashboard tuple prefix stable.
        return (current[:6] if current else None, self._battery[0], wifi,
                vm.foreground_color, vm.background_color, vm.selected_color,
                self._battery[1], bluetooth)

    def _icon(self, kind, name, x, background):
        cached = self._icons.get(kind)
        if cached is None or cached[0] != name or cached[1] != background:
            cached = (name, background, bitmap(name, background))
            self._icons[kind] = cached
        width, height, raw = cached[2]
        self.vm.draw._bytearray(x, (HEIGHT - height) // 2, width, height, raw)

    def draw(self, state):
        draw = self.vm.draw
        background = 0
        colour = 0xFFFF
        draw._fill_rectangle(0, 0, 320, HEIGHT, background)
        y = (HEIGHT - draw.get_font(FONT_XTRA_SMALL).height) // 2
        current = state[0]
        clock = '%02d:%02d' % (current[4], current[5]) if current else '--:--'
        draw._text(8, y, clock, colour, FONT_XTRA_SMALL)
        percentage = state[1]
        label = '%d%%' % percentage if percentage is not None else '--%'
        label_x = 320 - 8 - draw.len('100%', FONT_XTRA_SMALL)
        draw._text(320 - 8 - draw.len(label, FONT_XTRA_SMALL), y, label, colour, FONT_XTRA_SMALL)
        bluetooth_x = label_x - 8 - 14
        wifi_x = bluetooth_x - 8 - 14
        self._icon('wifi', 'wifi_connected' if state[2] else 'wifi_disconnected', wifi_x, background)
        self._icon('bluetooth', 'bluetooth_connected' if state[7] else 'bluetooth_disconnected', bluetooth_x, background)
