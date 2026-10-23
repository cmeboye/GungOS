"""PicoSpice drawing: the schematic on its grid, probe marks and the
waveform panes. Functions draw into the back buffer; the app swaps once per
frame.
"""
from array import array
from engtools.ui import theme
from engtools.ui.lab import text, right_text, centre_text, mix
from . import model as sm
from . import symbols

PREVIEW = (8, 43, 304, 184)
AREA = (12, 58, 308, 225)          # where the schematic draws, inside the preview
PROPERTIES_TOP = 230
TAB_HEIGHT = 14
ROW_HEIGHT = 12
ZOOMS = ((8, 5), (12, 5), (16, 7), (24, 7))   # grid pitch and symbol size, px
LABELS = 2                          # zoom from which element names are drawn
VALUES = 3                          # ... and their values
PROBE_COLORS = (0xFD20, 0x07FF, 0xF81F, 0x07E0, 0xFFE0, 0x5D1F, 0xFB56, 0xBDF7)
PLOT_LEFT, PLOT_RIGHT = 22, 298


class Grid:
    """Grid points to screen pixels at one zoom, centred on (cx, cy)."""

    def __init__(self, center, zoom):
        self.pitch, self.size = ZOOMS[zoom]
        self.zoom = zoom
        self.cx, self.cy = center
        left, top, right, bottom = AREA
        self.mx, self.my = (left + right) // 2, (top + bottom) // 2

    def p(self, x, y):
        return int(self.mx + (x - self.cx) * self.pitch), int(self.my + (y - self.cy) * self.pitch)

    def span(self):
        """The grid points inside the drawing area, as x0, y0, x1, y1."""
        left, top, right, bottom = AREA
        return (int((left - self.mx) / self.pitch + self.cx) - 1, int((top - self.my) / self.pitch + self.cy) - 1,
                int((right - self.mx) / self.pitch + self.cx) + 1, int((bottom - self.my) / self.pitch + self.cy) + 1)

    def inside(self, x, y, margin):
        px, py = self.p(x, y)
        left, top, right, bottom = AREA
        return left + margin <= px <= right - margin and top + margin <= py <= bottom - margin


def fit_zoom(c):
    """The largest zoom at which the whole circuit fits, and its centre."""
    x0, y0, x1, y1 = sm.bounds(c)
    left, top, right, bottom = AREA
    for zoom in range(len(ZOOMS) - 1, -1, -1):
        pitch = ZOOMS[zoom][0]
        if (x1 - x0 + 2) * pitch <= right - left and (y1 - y0 + 2) * pitch <= bottom - top:
            return zoom, [(x0 + x1) / 2, (y0 + y1) / 2]
    return 0, [(x0 + x1) / 2, (y0 + y1) / 2]


# ---------------------------------------------------------------- schematic

def element_anchor(c, e, grid):
    """Screen centre of an element's symbol, and the axis of a two-pin one."""
    pts = [grid.p(*c['nodes'][n][:2]) for n in e['nodes']]
    if symbols.two_pin(e['kind']) or e['kind'] == 'W':
        (ax, ay), (bx, by) = pts
        if abs(bx - ax) >= abs(by - ay):
            axis = (1, 0) if bx >= ax else (-1, 0)
        else:
            axis = (0, 1) if by >= ay else (0, -1)
        return ((ax + bx) // 2, (ay + by) // 2), axis, pts
    cx = sum(x for x, y in pts) // len(pts)
    cy = sum(y for x, y in pts) // len(pts)
    return (cx, cy), None, pts


def draw_element(draw, c, e, grid, color):
    (cx, cy), axis, pts = element_anchor(c, e, grid)
    kind, size = e['kind'], grid.size
    h = size // 2
    if kind == 'W':
        draw._line(pts[0][0], pts[0][1], pts[1][0], pts[1][1], color)
        return
    if axis is not None:
        ux, uy = axis
        a = (cx - (h + 1) * ux, cy - (h + 1) * uy)
        b = (cx + (h + 1) * ux, cy + (h + 1) * uy)
        draw._line(pts[0][0], pts[0][1], a[0], a[1], color)
        draw._line(b[0], b[1], pts[1][0], pts[1][1], color)
        if kind in symbols.CIRCLE:
            draw._circle(cx, cy, h, color)
    else:
        ux, uy = 1, 0
        for (px, py), (dx, dy) in zip(pts, symbols.PINS[size][kind]):
            draw._line(px, py, cx + dx, cy + dy, color)
    for x0, y0, x1, y1 in symbols.segments(kind, size, ux, uy):
        draw._line(cx + x0, cy + y0, cx + x1, cy + y1, color)


def label_point(c, e, grid):
    (cx, cy), axis, pts = element_anchor(c, e, grid)
    h = grid.size // 2
    if axis is None:
        return cx + h + 2, cy - h - 9
    if axis[1] != 0:
        return cx + h + 3, cy - 4
    return cx - 6, cy - h - 10


def ground(draw, x, y, size, color):
    """Three bars under a grounded node, narrowing downwards."""
    w = size // 2 + 1
    draw._line(x, y, x, y + 2, color)
    for row in range(3):
        draw._line(x - w + row, y + 3 + 2 * row, x + w - row, y + 3 + 2 * row, color)


def schematic(draw, p, c, grid, chosen, cursor, focus_view, result, problem):
    """The whole circuit: grid dots, elements, nodes, probes and cursor.
    chosen: the selected reference; problem: (node, element) to show red."""
    x0, y0, x1, y1 = grid.span()
    dot = mix(p.PANEL, p.GRID, 1, 2) if grid.pitch < 12 else p.GRID
    for gy in range(y0, y1 + 1):
        for gx in range(x0, x1 + 1):
            px, py = grid.p(gx, gy)
            draw._fill_rectangle(px, py, 1, 1, dot)
    bad_node, bad_element = problem if problem else (None, None)
    for i, e in enumerate(c['elements']):
        color = p.ERROR if i == bad_element else p.ACCENT if chosen == ('element', i) else p.TEXT
        draw_element(draw, c, e, grid, color)
    linked = [0] * len(c['nodes'])
    for e in c['elements']:
        for n in e['nodes']:
            linked[n] += 1
    op = result.op if result is not None and result.op is not None else None
    for i, (x, y, grounded) in enumerate(c['nodes']):
        px, py = grid.p(x, y)
        color = p.ERROR if i == bad_node else p.ACCENT if chosen == ('node', i) else p.TEXT
        if grounded:
            ground(draw, px, py, grid.size, color)
        if chosen == ('node', i):
            draw._rectangle(px - 2, py - 2, 5, 5, color)
        elif not linked[i]:
            draw._rectangle(px - 1, py - 1, 3, 3, color)
        elif linked[i] > 2 or grounded and linked[i] > 1:
            draw._fill_rectangle(px - 1, py - 1, 3, 3, color)
        if grid.zoom >= VALUES or chosen == ('node', i):
            text(draw, px + 3, py + 2, sm.node_label(c, i), p.MUTED)
        if op is not None and op['nodes'][i] is not None and (grid.zoom >= LABELS or chosen == ('node', i)):
            text(draw, px + 7, py - 10, sm.eng(op['nodes'][i], 'V', 3), theme.AMBER)
    if grid.zoom >= LABELS:
        for i, e in enumerate(c['elements']):
            if e['kind'] == 'W':
                continue
            lx, ly = label_point(c, e, grid)
            name = e['name']
            if grid.zoom >= VALUES:
                summary = sm.element_summary(c, e)
                name += ' ' + summary if summary else ''
            text(draw, lx, ly, name, p.ACCENT if chosen == ('element', i) else p.MUTED)
    elif chosen and chosen[0] == 'element':
        e = c['elements'][chosen[1]]
        lx, ly = label_point(c, e, grid)
        text(draw, lx, ly, e['name'], p.ACCENT)
    for k, probe in enumerate(c['probes']):
        probe_mark(draw, c, probe, grid, PROBE_COLORS[k % len(PROBE_COLORS)], chosen == ('probe', k))
    if focus_view:
        px, py = grid.p(*cursor)
        r = grid.size // 2 + 2
        draw._rectangle(px - r, py - r, 2 * r + 1, 2 * r + 1, p.ACCENT)


def probe_mark(draw, c, probe, grid, color, chosen):
    """A voltage probe is a flag on its node (hollow on the minus node); a
    current probe an arrow on the lead into its element."""
    if probe['kind'] == 'V':
        for key, filled in (('a', True), ('b', False)):
            n = probe[key]
            if n < 0:
                continue
            px, py = grid.p(*c['nodes'][n][:2])
            if filled:
                draw._fill_triangle(px, py - 2, px + 5, py - 5, px, py - 8, color)
            else:
                draw._line(px, py - 2, px + 5, py - 5, color)
                draw._line(px + 5, py - 5, px, py - 8, color)
            draw._line(px, py - 1, px, py - 8, color)
            if chosen:
                draw._rectangle(px - 2, py - 10, 9, 11, color)
        return
    e = probe['element']
    if not 0 <= e < len(c['elements']) or probe['node'] not in c['elements'][e]['nodes']:
        return
    el = c['elements'][e]
    (cx, cy), axis, pts = element_anchor(c, el, grid)
    px, py = pts[el['nodes'].index(probe['node'])]
    dx, dy = cx - px, cy - py
    length = max(abs(dx), abs(dy), 1)
    ux, uy = dx / length, dy / length
    tip = (px + ux * min(8, length - 1), py + uy * min(8, length - 1))
    base = (px + ux * min(3, length - 1), py + uy * min(3, length - 1))
    draw._fill_triangle(int(tip[0]), int(tip[1]), int(base[0] - uy * 3), int(base[1] + ux * 3),
                        int(base[0] + uy * 3), int(base[1] - ux * 3), color)
    if chosen:
        draw._rectangle(int(base[0]) - 4, int(base[1]) - 4, 9, 9, color)


# ---------------------------------------------------------------- waveforms

def pane_layout(groups, top, bottom):
    """Stacked panes, one per unit present."""
    out = []
    count = len(groups)
    height = (bottom - top - 6 * (count - 1)) // max(1, count)
    for n, unit in enumerate(groups):
        y = top + n * (height + 6)
        out.append((unit, y, y + height))
    return out


def columns(trace, count, points, lo, hi, top, bottom):
    """Screen polyline of a trace, packed five shorts per pixel column:
    x, first, lowest, highest and last y. A long trace costs one column
    per pixel, and the packing keeps it to ten bytes each."""
    width = PLOT_RIGHT - PLOT_LEFT
    scale = (bottom - top) / (hi - lo)
    out = array('h')
    last = -1
    for i in range(count):
        x = PLOT_LEFT + width * i // max(1, points - 1)
        y = min(max(int(bottom - (trace[i] - lo) * scale + 0.5), -999), 999)
        if x != last:
            out.extend((x, y, y, y, y))
            last = x
        else:
            n = len(out)
            out[n - 1] = y
            if y < out[n - 3]:
                out[n - 3] = y
            if y > out[n - 2]:
                out[n - 2] = y
    return out


def value_range(sim, ks):
    """The traces' lowest and highest values, and the axis around them."""
    lo = hi = None
    for k in ks:
        st = sim.stats(k)
        if st is None:
            continue
        lo = st['min'] if lo is None else min(lo, st['min'])
        hi = st['max'] if hi is None else max(hi, st['max'])
    if lo is None:
        lo = hi = 0.0
    bottom, top = lo, hi
    if top - bottom < 1e-12 * max(1.0, abs(top)):
        pad = max(abs(top) * 0.1, 1e-9)
        bottom, top = bottom - pad, top + pad
    pad = (top - bottom) * 0.05
    return lo, hi, bottom - pad, top + pad


def build_panes(c, sim, top, bottom):
    """(unit, top, bottom, axis lo, axis hi, lowest, highest, [(k, columns)])
    per pane."""
    groups = []
    for p in c['probes']:
        unit = sm.probe_unit(p)
        if unit not in groups:
            groups.append(unit)
    panes = []
    for unit, y0, y1 in pane_layout(groups, top, bottom):
        ks = [k for k, p in enumerate(c['probes']) if sm.probe_unit(p) == unit]
        low, high, lo, hi = value_range(sim, ks)
        plot_top, plot_bottom = y0 + 11, y1 - 10
        lines = [(k, columns(sim.traces[k], sim.count, sim.points, lo, hi, plot_top, plot_bottom)) for k in ks]
        panes.append((unit, y0, y1, lo, hi, low, high, lines))
    return panes


def waveforms(draw, p, c, sim, panes, cursor, active):
    width = PLOT_RIGHT - PLOT_LEFT
    cx = PLOT_LEFT + width * cursor // max(1, sim.points - 1)
    for unit, y0, y1, lo, hi, low, high, lines in panes:
        plot_top, plot_bottom = y0 + 11, y1 - 10
        draw._rectangle(PLOT_LEFT - 2, y0, width + 5, y1 - y0, p.GRID)
        text(draw, PLOT_LEFT + 1, y0 + 2, unit, p.ACCENT)
        right_text(draw, PLOT_RIGHT, y0 + 2, '%s / %s' % (sm.eng(high, unit, 3), sm.eng(low, unit, 3)), p.MUTED)
        if lo < 0 < hi:
            zero = int(plot_bottom - (0 - lo) * (plot_bottom - plot_top) / (hi - lo) + 0.5)
            draw._line(PLOT_LEFT, zero, PLOT_RIGHT, zero, p.AXIS)
        for k, cols in sorted(lines, key=lambda item: item[0] == active):
            color = PROBE_COLORS[k % len(PROBE_COLORS)]
            if k != active and active is not None:
                color = mix(p.BG, color, 2, 3)
            for n in range(0, len(cols), 5):
                x, low, high = cols[n], cols[n + 2], cols[n + 3]
                if n:
                    draw._line(cols[n - 5], cols[n - 1], x, cols[n + 1], color)
                if high > low:
                    draw._line(x, low, x, high, color)
        draw._line(cx, plot_top - 1, cx, plot_bottom + 1, p.TEXT)
        text(draw, PLOT_LEFT + 1, y1 - 9, sm.eng(sim.x(0), '', 3), p.MUTED)
        right_text(draw, PLOT_RIGHT, y1 - 9, sm.eng(sim.x(sim.points - 1), sim.x_unit(), 3), p.MUTED)


def legend(draw, p, c, active, y):
    """Probe names in their colours, wrapping; the active one boxed."""
    x = 16
    for k, probe in enumerate(c['probes']):
        label = sm.probe_label(c, probe)
        w = draw.len(label, 0) + 8
        if x + w > 304:
            x, y = 16, y + 10
        color = PROBE_COLORS[k % len(PROBE_COLORS)]
        text(draw, x, y, label, color)
        if k == active:
            draw._line(x, y + 9, x + w - 9, y + 9, color)
        x += w
    return y + 12
