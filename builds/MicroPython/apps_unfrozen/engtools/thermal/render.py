"""Heat transfer 2D drawing: the plate to scale with its sides and patches,
the temperature field, the colour bar and the line plots. Functions draw
into the back buffer; the app swaps once per frame.
"""
from engtools.ui import theme
from engtools.ui.lab import mix, text, right_text, centre_text
from engtools.units import number
from . import model as tm

PREVIEW = (8, 43, 304, 184)
PLATE_BOX = (64, 77, 256, 185)    # the plate is fitted and centred here
PROPERTIES_TOP = 230
TAB_HEIGHT = 14
ROW_HEIGHT = 12
PLOT_FIELD = (44, 84, 276, 266)
PLOT_BAR_Y = 280
LEFT, RIGHT = 24, 300
LEVELS = 60
BAND = 6
STOPS = ((0.0, (24, 32, 150)), (0.25, (30, 140, 230)), (0.5, (60, 200, 110)),
         (0.75, (245, 220, 60)), (1.0, (225, 45, 30)))
HOT, COLD = 0xF8A0, 0x2D7F

_lut = None


def palette_lut():
    """LEVELS colours from cold to hot as RGB565."""
    global _lut
    if _lut is None:
        table = []
        for n in range(LEVELS):
            t = n / (LEVELS - 1)
            for k in range(1, len(STOPS)):
                if t <= STOPS[k][0] or k == len(STOPS) - 1:
                    (t0, a), (t1, b) = STOPS[k - 1], STOPS[k]
                    f = (t - t0) / (t1 - t0)
                    r, g, bl = (int(a[c] + (b[c] - a[c]) * f) for c in range(3))
                    table.append(((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (bl >> 3))
                    break
        _lut = table
    return _lut


def shade(p, kind):
    return {tm.INSULATED: p.GRID, tm.TEMPERATURE: theme.AMBER, tm.CONVECTION: p.ACCENT, tm.FLUX: p.TEXT}[kind]


class Fit:
    """The plate (mm, y up) on screen (px, y down), at one scale for both
    axes unless one side would be thinner than 8 px."""

    def __init__(self, state, box):
        left, top, right, bottom = box
        width, height = right - left, bottom - top
        s = min(width / state['W'], height / state['H'])
        self.w = max(8, min(width, int(state['W'] * s + 0.5)))
        self.h = max(8, min(height, int(state['H'] * s + 0.5)))
        self.ox = left + (width - self.w) // 2
        self.oy = top + (height - self.h) // 2
        self.sx, self.sy = self.w / state['W'], self.h / state['H']

    def x(self, mm):
        return self.ox + int(mm * self.sx + 0.5)

    def y(self, mm):
        return self.oy + self.h - int(mm * self.sy + 0.5)

    def cell(self, plate, j, i):
        """Screen rectangle (x, y, w, h) of a cell."""
        left = self.ox + int(i * self.w / plate.nx + 0.5)
        right = self.ox + int((i + 1) * self.w / plate.nx + 0.5)
        top = self.oy + self.h - int((j + 1) * self.h / plate.ny + 0.5)
        bottom = self.oy + self.h - int(j * self.h / plate.ny + 0.5)
        return left, top, right - left, bottom - top


def span(low, high):
    if high - low < 1e-6:
        return low - 0.5, high + 0.5
    return low, high


def field(draw, plate, fit, low, high, bands):
    """The temperature of every cell as a colour between low and high."""
    nx, ny = plate.nx, plate.ny
    k = (LEVELS - 0.001) / (high - low)
    colours = palette_lut()
    ref = plate.ref - low
    rows = plate.T.tolist()
    xs = [fit.ox + int(i * fit.w / nx + 0.5) for i in range(nx + 1)]
    for j in range(ny):
        top = fit.oy + fit.h - int((j + 1) * fit.h / ny + 0.5)
        height = fit.oy + fit.h - int(j * fit.h / ny + 0.5) - top
        row = rows[j]
        for i in range(nx):
            index = int((row[i] + ref) * k)
            if bands:
                index = index // BAND * BAND + BAND // 2
            draw._fill_rectangle(xs[i], top, xs[i + 1] - xs[i], height, colours[min(LEVELS - 1, max(0, index))])


def blank(draw, p, fit):
    """The plate before it is evaluated: a tint with faint cell lines."""
    draw._fill_rectangle(fit.ox, fit.oy, fit.w, fit.h, mix(p.PANEL, p.GRID, 1, 3))
    draw._rectangle(fit.ox, fit.oy, fit.w, fit.h, p.GRID)


def edges(draw, p, state, fit, chosen=None):
    """Each side in its condition's colour, thicker when chosen."""
    ox, oy, w, h = fit.ox, fit.oy, fit.w, fit.h
    for index, side in enumerate(state['sides']):
        colour, thick = shade(p, side['kind']), 4 if index == chosen else 2
        if side['kind'] == tm.INSULATED:
            dashes(draw, index, fit, p.MUTED if index == chosen else p.GRID, thick)
            continue
        if index == 0:
            draw._fill_rectangle(ox - 1 - thick, oy, thick, h, colour)
        elif index == 1:
            draw._fill_rectangle(ox + w + 1, oy, thick, h, colour)
        elif index == 2:
            draw._fill_rectangle(ox, oy + h + 1, w, thick, colour)
        else:
            draw._fill_rectangle(ox, oy - 1 - thick, w, thick, colour)


def dashes(draw, index, fit, colour, thick):
    """An insulated side: short dashes just outside the plate."""
    ox, oy, w, h = fit.ox, fit.oy, fit.w, fit.h
    if index < 2:
        x = ox - 1 - thick if index == 0 else ox + w + 1
        for y in range(oy, oy + h, 6):
            draw._fill_rectangle(x, y, thick, min(3, oy + h - y), colour)
    else:
        y = oy + h + 1 if index == 2 else oy - 1 - thick
        for x in range(ox, ox + w, 6):
            draw._fill_rectangle(x, y, min(3, ox + w - x), thick, colour)


def side_lines(side):
    kind = side['kind']
    if kind == tm.TEMPERATURE:
        return (number(side['T'], 4) + ' C',)
    if kind == tm.CONVECTION:
        return (number(side['T'], 4) + ' C', 'h ' + number(side['h'], 3))
    if kind == tm.FLUX:
        return ('q in', number(side['q'], 3))
    return ('insul.',)


def side_labels(draw, p, state, fit, chosen=None):
    """The condition of each side, written beside it."""
    ox, oy, w, h = fit.ox, fit.oy, fit.w, fit.h
    for index, side in enumerate(state['sides']):
        lines = side_lines(side)
        colour = p.TEXT if index == chosen else p.MUTED
        if index < 2:
            top = oy + h // 2 - 5 * len(lines)
            for n, line in enumerate(lines):
                if index == 0:
                    right_text(draw, ox - 8, top + 10 * n, line, colour)
                else:
                    text(draw, ox + w + 8, top + 10 * n, line, colour)
        else:
            line = '  '.join(lines) if side['kind'] != tm.FLUX else 'q in ' + lines[1] + ' W/m2'
            centre_text(draw, ox + w // 2, oy + h + 6 if index == 2 else oy - 14, line, colour)
        if index == chosen:
            # A small pointer at the middle of the chosen side.
            mx, my = ox + w // 2, oy + h // 2
            if index == 0:
                draw._fill_triangle(ox + 2, my - 3, ox + 2, my + 3, ox + 6, my, p.TEXT)
            elif index == 1:
                draw._fill_triangle(ox + w - 3, my - 3, ox + w - 3, my + 3, ox + w - 7, my, p.TEXT)
            elif index == 2:
                draw._fill_triangle(mx - 3, oy + h - 3, mx + 3, oy + h - 3, mx, oy + h - 7, p.TEXT)
            else:
                draw._fill_triangle(mx - 3, oy + 2, mx + 3, oy + 2, mx, oy + 6, p.TEXT)


def patches(draw, p, state, fit, chosen=None, labels=True):
    """Each heat patch outlined, numbered and, when it fits, with its power."""
    for index, patch in enumerate(state['patches']):
        left, right = fit.x(patch['x']), fit.x(patch['x'] + patch['w'])
        top, bottom = fit.y(patch['y'] + patch['h']), fit.y(patch['y'])
        w, h = max(3, right - left), max(3, bottom - top)
        colour = p.TEXT if index == chosen else theme.AMBER
        draw._rectangle(left, top, w, h, colour)
        if index == chosen:
            draw._rectangle(left - 1, top - 1, w + 2, h + 2, colour)
        if labels:
            label = 'P%d' % (index + 1)
            power = number(patch['P'], 3) + ' W'
            if w >= draw.len(power, 0) + 4 and h >= 20:
                centre_text(draw, left + w // 2, top + h // 2 - 9, label, colour)
                centre_text(draw, left + w // 2, top + h // 2 + 1, power, colour)
            elif left + w + 3 + draw.len(label, 0) <= fit.ox + fit.w:
                text(draw, left + w + 3, top + h // 2 - 4, label, colour)
            else:
                right_text(draw, left - 3, top + h // 2 - 4, label, colour)


def marker(draw, plate, fit, j, i, colour, outline):
    x, y, w, h = fit.cell(plate, j, i)
    w, h = max(3, w), max(3, h)
    draw._rectangle(x - 1, y - 1, w + 2, h + 2, outline)
    draw._rectangle(x, y, w, h, colour)


def crosshair(draw, p, plate, fit, j, i):
    """Dotted lines through the cursor cell, then the cell itself."""
    x, y, w, h = fit.cell(plate, j, i)
    cx, cy = x + w // 2, y + h // 2
    for px in range(fit.ox, fit.ox + fit.w, 3):
        draw._fill_rectangle(px, cy, 1, 1, p.TEXT)
    for py in range(fit.oy, fit.oy + fit.h, 3):
        draw._fill_rectangle(cx, py, 1, 1, p.TEXT)
    marker(draw, plate, fit, j, i, p.TEXT, p.BG)


def colour_bar(draw, p, left, right, y, low, high, bands):
    """A horizontal bar from cold to hot with its end temperatures."""
    colours = palette_lut()
    width = right - left
    for n in range(width):
        index = int(n * LEVELS / width)
        if bands:
            index = index // BAND * BAND + BAND // 2
        draw._fill_rectangle(left + n, y, 1, 5, colours[min(LEVELS - 1, index)])
    right_text(draw, left - 4, y - 2, number(low, 4), p.TEXT)
    text(draw, right + 4, y - 2, number(high, 4), p.TEXT)


def plot(draw, p, rect, title, xs, series, cursor=None, unit='C', xlabel='', bounds=None):
    """Line plot of one or more (values, colour) series against xs, with
    the range of the values and an optional cursor at an x value. bounds
    gives the x range when it is wider than xs (a plate's edges)."""
    left, top, right, bottom = rect
    plot_top, plot_bottom = top + 12, bottom - 10
    lo = min(min(values) for values, _ in series)
    hi = max(max(values) for values, _ in series)
    lo, hi = span(lo, hi)
    x0, x1 = bounds or (xs[0], xs[-1])
    if x1 - x0 <= 0:
        x1 = x0 + 1.0
    draw._rectangle(left - 2, top, right - left + 5, bottom - top, p.GRID)
    text(draw, left + 1, top + 2, title, p.ACCENT)
    right_text(draw, right, top + 2, number(hi, 4) + ' / ' + number(lo, 4) + ' ' + unit, p.MUTED)
    text(draw, left + 1, bottom - 9, number(x0, 4), p.MUTED)
    right_text(draw, right, bottom - 9, number(x1, 4) + (' ' + xlabel if xlabel else ''), p.MUTED)
    scale_x = (right - left) / (x1 - x0)
    scale_y = (plot_bottom - plot_top) / (hi - lo)
    px = [int(left + (x - x0) * scale_x + 0.5) for x in xs]
    for values, colour in series:
        last = None
        for n in range(len(values)):
            point = (px[n], int(plot_bottom - (values[n] - lo) * scale_y + 0.5))
            if last is not None:
                draw._line(last[0], last[1], point[0], point[1], colour)
            last = point
    if cursor is not None:
        cx = int(left + (cursor - x0) * scale_x + 0.5)
        draw._line(cx, plot_top - 1, cx, plot_bottom + 1, p.TEXT)
