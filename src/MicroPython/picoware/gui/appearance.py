"""Shared RGB565 appearance roles. No framebuffer or colour lookup tables."""

DEFAULTS = {'theme_color': 0x001F, 'background_color': 0,
            'text_on_dark': 0xFFFF, 'text_on_light': 0}
_dark, _light = 0xFFFF, 0


def valid_color(value, fallback):
    return value if type(value) is int and 0 <= value <= 0xFFFF else fallback


def values(settings):
    return {key: valid_color(settings.get(key), default)
            for key, default in DEFAULTS.items()}


def display_color(color):
    """RGB565 after the screen's RGB332 framebuffer quantization."""
    r = ((color >> 13) & 7) * 255 // 7
    g = ((color >> 8) & 7) * 255 // 7
    b = ((color >> 3) & 3) * 255 // 3
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


def is_light(color):
    color = display_color(color)
    r, g, b = ((color >> 11) & 31) * 255 // 31, ((color >> 5) & 63) * 255 // 63, (color & 31) * 255 // 31
    return r * 299 + g * 587 + b * 114 >= 145000


def configure(dark, light):
    global _dark, _light
    _dark, _light = dark, light


def text_on(background, dark=None, light=None):
    return (_light if light is None else light) if is_light(background) else (_dark if dark is None else dark)


def luminance(color):
    # WCAG relative luminance, evaluated only by the settings preview.
    channels = (((color >> 11) & 31) / 31, ((color >> 5) & 63) / 63, (color & 31) / 31)
    linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in channels]
    return linear[0] * .2126 + linear[1] * .7152 + linear[2] * .0722


def contrast(a, b):
    x, y = luminance(display_color(a)), luminance(display_color(b))
    return (max(x, y) + .05) / (min(x, y) + .05)
