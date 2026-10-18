"""Read the native RGB332 image in display regression checks."""


def colour(value):
    """RGB565 input after the device's RGB332 storage and panel conversion."""
    return expand(((value & 0xE000) >> 8) | ((value & 0x0700) >> 6) | ((value & 0x18) >> 3))


def expand(value):
    red = ((value >> 5) & 7) * 255 // 7
    green = ((value >> 2) & 7) * 255 // 7
    blue = (value & 3) * 255 // 3
    return ((red & 0xF8) << 8) | ((green & 0xFC) << 3) | (blue >> 3)


class Pixels:
    def __init__(self, draw):
        self.draw = draw

    def pixel(self, x, y):
        return expand(self.draw._read_row(y)[x])
