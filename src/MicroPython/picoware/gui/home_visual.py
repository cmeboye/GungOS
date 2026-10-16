"""Static pixel-art logo and a clock that changes once per minute."""


class HomeVisual:
    def __init__(self):
        self._logo = None
        self._background = None
        self._foreground = None

    def draw(self, draw, current, foreground, background):
        if (draw.size.x, draw.size.y) != (320, 320):
            draw._text((draw.size.x - draw.len("Picoware")) // 2,
                       draw.size.y // 2, "Picoware", foreground)
            return
        from picoware.assets import boot_logo
        from math import sin, cos, pi

        if self._logo is None or self._background != background or self._foreground != foreground:
            rgb332 = ((background & 0xE000) >> 8) | ((background & 0x0700) >> 6) | ((background & 0x0018) >> 3)
            text332 = ((foreground & 0xE000) >> 8) | ((foreground & 0x0700) >> 6) | ((foreground & 0x0018) >> 3)
            self._logo = boot_logo.decode(rgb332, text332)
            self._background = background
            self._foreground = foreground
        draw._bytearray(boot_logo.X, boot_logo.Y, boot_logo.WIDTH, boot_logo.HEIGHT, self._logo)

        cx, cy, radius = 160, 219, 49
        draw._circle(cx, cy, radius, foreground)
        for hour in range(12):
            angle = hour * pi / 6
            length = 7 if hour % 3 == 0 else 4
            x1, y1 = cx + int(sin(angle) * (radius - length)), cy - int(cos(angle) * (radius - length))
            x2, y2 = cx + int(sin(angle) * (radius - 2)), cy - int(cos(angle) * (radius - 2))
            draw._line(x1, y1, x2, y2, foreground)
        if current is not None:
            year, month, day, _, hour, minute = current[:6]
            hour_angle = ((hour % 12) + minute / 60) * pi / 6
            minute_angle = minute * pi / 30
            hx, hy = cx + int(sin(hour_angle) * 26), cy - int(cos(hour_angle) * 26)
            mx, my = cx + int(sin(minute_angle) * 39), cy - int(cos(minute_angle) * 39)
            draw._line(cx, cy, hx, hy, foreground)
            draw._line(cx + 1, cy, hx + 1, hy, foreground)
            draw._line(cx, cy, mx, my, foreground)
            draw._fill_circle(cx, cy, 2, foreground)
            months = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")
            date = "%02d %s %04d" % (day, months[month - 1], year)
        else:
            date = "Set date & time"
            draw._text(cx - draw.len("Time not set") // 2, cy - 4, "Time not set", foreground)
        draw._text((320 - draw.len(date, 1)) // 2, 286, date, foreground, 1)
