"""Beam Lab drawing: the structure sketch, cross-sections, property lists,
diagrams and dialogs. Functions draw into the back buffer; the app swaps
once per frame.
"""
from math import cos, sin, pi, sqrt
from picoware.system.font import FONT_XTRA_SMALL as XS, FONT_SMALL as SM
from engtools import units
from engtools.ui import theme
from . import model as bm
from . import items
from engtools.ui.viewport import Viewport
from engtools.ui.lab import (mix, text, right_text, centre_text, wrap, panel, chrome, menu, form, popup, prompt,
                              help_capacity, help_box, results, tabs as model_tabs)

LEFT, RIGHT = 20, 300
BEAM_Y = 136
ROW = 15
CASE_COLORS = (None, theme.AMBER, 0xF81F, 0x07E0, 0xFFE0, 0xA51F)
# Fixed calculator-style preview above a scrolling property panel. The
# section editor keeps the original split; the model page gives the sketch
# more room and lists three properties at a time.
PREVIEW_RECT = (8, 43, 304, 142)
PROPERTIES_TOP = 191
MODEL_PREVIEW = (8, 43, 304, 184)
MODEL_PROPERTIES_TOP = 230
CURSOR_Y = BEAM_Y + 36  # a straight beam's dimension line
BEAM_LAYOUT = {'box': (32, BEAM_Y, 288, BEAM_Y), 'bottom': 224, 'list': 255}
FRAME_LAYOUT = {'box': (42, 98, 278, 194), 'bottom': 224, 'list': 255}


def layout(model):
    return BEAM_LAYOUT if bm.is_straight_beam(model) else FRAME_LAYOUT


def head(draw, tx, ty, ux, uy, color, size=4):
    """A filled arrowhead with its tip at (tx, ty), pointing along (ux, uy)."""
    bx, by = tx - ux * size, ty - uy * size
    vx, vy = -uy * (size - 1), ux * (size - 1)
    draw._fill_triangle(int(tx), int(ty), int(bx + vx), int(by + vy), int(bx - vx), int(by - vy), color)


def dashed(draw, x, y1, y2, color, gap=3):
    for y in range(y1, y2, gap * 2):
        draw._line(x, y, x, min(y + gap - 1, y2), color)


def hatch(draw, x1, x2, y, color):
    draw._line(x1, y, x2, y, color)
    for x in range(x1 + 2, x2 + 1, 4):
        draw._line(x, y + 1, x - 3, y + 4, color)


def case_color(p, model, case):
    if len(model['cases']) < 2 or case == 0:
        return p.TEXT
    return CASE_COLORS[case % len(CASE_COLORS)] or p.TEXT


class View:
    """World (m, y up) to screen (px, y down) at one scale for both axes."""

    def __init__(self, model, box, zoom=1.0, focus=None):
        left, top, right, bottom = box
        x0, y0, x1, y1 = bm.bounds(model)
        w, h = right - left, bottom - top
        dx, dy = max(x1 - x0, 1e-6), max(y1 - y0, 1e-6)
        scale = w / dx if h <= 0 or y1 - y0 < 1e-9 else min(w / dx, h / dy)
        self.scale = scale * zoom
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        if zoom > 1 and focus is not None:
            cx, cy = focus
        self.ox = (left + right) / 2 - cx * self.scale
        self.oy = (top + bottom) / 2 + cy * self.scale

    def p(self, X, Y):
        return int(self.ox + X * self.scale + 0.5), int(self.oy - Y * self.scale + 0.5)


def clip(draw, x1, y1, x2, y2, color, top=24, bottom=320):
    """A line clipped to the screen columns and the rows top..bottom."""
    dx, dy, t0, t1 = x2 - x1, y2 - y1, 0.0, 1.0
    for pp, qq in ((-dx, x1), (dx, 319 - x1), (-dy, y1 - top), (dy, bottom - y1)):
        if pp == 0:
            if qq < 0:
                return
        else:
            t = qq / pp
            if pp < 0:
                t0 = max(t0, t)
            else:
                t1 = min(t1, t)
            if t0 > t1:
                return
    draw._line(int(x1 + t0 * dx), int(y1 + t0 * dy), int(x1 + t1 * dx), int(y1 + t1 * dy), color)


def thick(draw, a, b, color, top=24, bottom=320):
    (x1, y1), (x2, y2) = a, b
    offsets = ((0, -1), (0, 0), (0, 1)) if abs(x2 - x1) >= abs(y2 - y1) else ((-1, 0), (0, 0), (1, 0))
    for ox, oy in offsets:
        clip(draw, x1 + ox, y1 + oy, x2 + ox, y2 + oy, color, top, bottom)


# ---------------------------------------------------------------- supports

def support_shape(draw, x, y, kind, color, wall=0):
    """A support at screen point (x, y), drawn upright. wall: -1 or 1 draws a
    fixed end as a wall on that side (a horizontal member's free end)."""
    y += 2
    if kind in ('Pin', 'Roller'):
        draw._fill_triangle(x, y, x - 6, y + 10, x + 6, y + 10, color)
        if kind == 'Roller':
            draw._circle(x - 3, y + 13, 2, color)
            draw._circle(x + 3, y + 13, 2, color)
            hatch(draw, x - 8, x + 8, y + 16, color)
        else:
            hatch(draw, x - 8, x + 8, y + 11, color)
    elif kind == 'Roller x':
        y -= 2
        draw._fill_triangle(x - 2, y, x - 12, y - 6, x - 12, y + 6, color)
        draw._circle(x - 15, y - 3, 2, color)
        draw._circle(x - 15, y + 3, 2, color)
        draw._line(x - 18, y - 8, x - 18, y + 8, color)
        for yy in range(y - 7, y + 9, 4):
            draw._line(x - 19, yy, x - 22, yy + 3, color)
    elif kind == 'Fixed':
        if wall:
            y -= 2
            draw._line(x, y - 12, x, y + 12, color)
            for yy in range(y - 11, y + 13, 4):
                draw._line(x + wall, yy, x + 4 * wall, yy + 3, color)
        else:
            draw._fill_rectangle(x - 8, y - 1, 17, 3, color)
            hatch(draw, x - 8, x + 8, y + 3, color)
    elif kind == 'Guide':
        draw._rectangle(x - 6, y + 1, 13, 7, color)
        draw._circle(x - 3, y + 11, 2, color)
        draw._circle(x + 3, y + 11, 2, color)
        hatch(draw, x - 8, x + 8, y + 14, color)
    else:
        top, step = y, 3
        for i in range(5):
            dx = 4 if i % 2 == 0 else -4
            draw._line(x - (dx if i else 0), top, x + dx, top + step, color)
            top += step
        draw._line(x + 4, top - step, x, top, color)
        hatch(draw, x - 8, x + 8, top + 1, color)


def moment_shape(draw, x, y, value, color):
    r = 9
    start, end = -2.4, 2.4  # radians, open toward the right
    previous = None
    for i in range(13):
        a = start + (end - start) * i / 12
        point = (int(x + r * cos(a + pi)), int(y - r * sin(a + pi)))
        if previous:
            draw._line(previous[0], previous[1], point[0], point[1], color)
        previous = point
    a = (end if value >= 0 else start) + pi
    hx, hy = x + r * cos(a), y - r * sin(a)
    tx, ty = -sin(a), -cos(a)  # counterclockwise tangent on screen
    if value < 0:
        tx, ty = -tx, -ty
    head(draw, hx + tx, hy + ty, tx, ty, color, 5)


def dist_levels(model):
    """Stack overlapping distributed loads on each member: {id(load): level}."""
    placed, levels = [], {}
    for load in model['loads']:
        if load['kind'] != 'dist':
            continue
        level = 0
        while any(m == load['m'] and l == level and not (load['x2'] <= a or load['x'] >= b) for m, a, b, l in placed):
            level += 1
        placed.append((load['m'], load['x'], load['x2'], level))
        levels[id(load)] = level
    return levels


def screen_direction(model, load):
    dx, dy = bm.load_vector(model, load)
    return dx, -dy


# ---------------------------------------------------------------- the sketch

def sketch(draw, p, model, view, selected, cursor, problem, shape, line_members, bottom, active_member=None):
    """The structure with its supports, hinges and loads. cursor is
    ((X, Y), distance along the line), or None."""
    accent = p.ACCENT
    straight = bm.is_straight_beam(model)

    def pick(ref, color):
        return accent if items.same(ref, selected) else color
    if cursor is not None and straight:
        cx = view.p(*cursor[0])[0]
        dashed(draw, cx, 64, CURSOR_Y, p.SELECT if p.SELECT != p.BG else p.GRID)
    # Deflected shape of the current view.
    for points in shape or ():
        previous = None
        for point in points:
            if previous is not None and point != previous:
                clip(draw, previous[0], previous[1], point[0], point[1], p.MUTED, 64, bottom)
            previous = point
    # Members, the current line brighter, with section names when there are several.
    several = len(model['sections']) > 1
    for m in range(len(model['members'])):
        member = model['members'][m]
        a, b = view.p(*model['joints'][member['a']]), view.p(*model['joints'][member['b']])
        color = p.TEXT if straight or m in line_members else p.MUTED
        color = (accent if m == active_member else color) if active_member is not None else pick(('member', m), color)
        thick(draw, a, b, color, 64, bottom)
        if several:
            X0, Y0, c, s, L = bm.member_axis(model, m)
            mx, my = (a[0] + b[0]) // 2, (a[1] + b[1]) // 2
            name = model['sections'][member['section']]['name']
            if straight:
                centre_text(draw, mx, BEAM_Y + 5, name, pick(('member', m), p.MUTED))
            elif 64 < my < bottom - 8:
                text(draw, mx + int(7 * s) - 4, my + int(7 * c) - 3, name, pick(('member', m), p.MUTED))
    if straight and several:
        for m in range(1, len(model['members'])):
            x = view.p(*model['joints'][model['members'][m]['a']])[0]
            draw._line(x, BEAM_Y - 6, x, BEAM_Y + 6, p.MUTED)
    # Supports, upright; a fixed free end of a horizontal member is a wall.
    for s in model['supports']:
        X, Y = bm.point(model, s['m'], s['x'])
        x, y = view.p(X, Y)
        wall = 0
        if s['kind'] == 'Fixed':
            X0, Y0, c, s_, L = bm.member_axis(model, s['m'])
            if abs(s_) < 0.5 and (s['x'] < 1e-9 or s['x'] > L - 1e-9):
                attached = [o for o in range(len(model['members'])) if o != s['m'] and
                            any(items.same_point(model['joints'][model['members'][o][k]], (X, Y)) for k in ('a', 'b'))]
                if not attached:
                    outward = -c if s['x'] < 1e-9 else c
                    wall = -1 if outward < 0 else 1
        if 64 < y < bottom:
            support_shape(draw, x, y, s['kind'], pick(('support', s), p.MUTED if s['kind'] == 'Spring' else p.TEXT), wall)
    # Hinges: open circles, pulled into their member at a joint.
    for h in model['hinges']:
        X0, Y0, c, s_, L = bm.member_axis(model, h['m'])
        inset = 5 if h['x'] < 1e-9 else -5 if h['x'] > L - 1e-9 else 0
        x, y = view.p(*bm.point(model, h['m'], h['x']))
        x, y = int(x + inset * c), int(y - inset * s_)
        if 64 < y < bottom:
            draw._fill_circle(x, y, 3, p.BG)
            draw._circle(x, y, 3, pick(('hinge', h), p.TEXT))
    # Loads, coming onto their member along their direction.
    loads = model['loads']
    wmax = max([abs(l['w1']) for l in loads if l['kind'] == 'dist'] +
               [abs(l['w2']) for l in loads if l['kind'] == 'dist'] + [1e-9])
    levels = dist_levels(model)
    for load in loads:
        color = pick(('load', load), case_color(p, model, load['case']))
        x, y = view.p(*bm.point(model, load['m'], load['x']))
        if load['kind'] == 'moment':
            if 64 < y < bottom:
                moment_shape(draw, x, y, load['M'], color)
                text(draw, x + 6, y - 21, units.number(units.from_si(load['M'], 'kNm'), 3), color)
            continue
        ux, uy = screen_direction(model, load)
        if load['kind'] == 'point':
            near, far = (x - ux * 3, y - uy * 3), (x - ux * 30, y - uy * 30)
            if load['P'] >= 0:
                clip(draw, far[0], far[1], near[0], near[1], color, 64, bottom)
                if 64 < near[1] < bottom:
                    head(draw, near[0], near[1], ux, uy, color)
            else:
                clip(draw, near[0], near[1], far[0], far[1], color, 64, bottom)
                if 64 < far[1] < bottom:
                    head(draw, far[0], far[1], -ux, -uy, color)
            lx, ly = x - ux * 38, y - uy * 38
            if 64 < ly < bottom - 8:
                centre_text(draw, lx, ly - 4, units.number(units.from_si(load['P'], 'kN'), 3), color)
            continue
        x2, y2 = view.p(*bm.point(model, load['m'], load['x2']))
        lift = 3 + 17 * levels[id(load)]
        h1 = 4 + int(9 * abs(load['w1']) / wmax)
        h2 = 4 + int(9 * abs(load['w2']) / wmax)
        a0, b0 = (x - ux * lift, y - uy * lift), (x2 - ux * lift, y2 - uy * lift)
        a1, b1 = (a0[0] - ux * h1, a0[1] - uy * h1), (b0[0] - ux * h2, b0[1] - uy * h2)
        clip(draw, a1[0], a1[1], b1[0], b1[1], color, 64, bottom)
        clip(draw, a1[0], a1[1], a0[0], a0[1], color, 64, bottom)
        clip(draw, b1[0], b1[1], b0[0], b0[1], color, 64, bottom)
        span = sqrt((b0[0] - a0[0]) ** 2 + (b0[1] - a0[1]) ** 2)
        count = max(1, int(span // 12))
        for i in range(count + 1):
            t = i / count
            bx, by = a0[0] + (b0[0] - a0[0]) * t, a0[1] + (b0[1] - a0[1]) * t
            hh = h1 + (h2 - h1) * t
            w = load['w1'] + (load['w2'] - load['w1']) * t
            if not 64 < by < bottom:
                continue
            if w >= 0:
                head(draw, bx, by, ux, uy, color, 3)
            elif hh > 4:
                head(draw, bx - ux * hh, by - uy * hh, -ux, -uy, color, 3)
        label = units.number(units.from_si(load['w1'], 'kN/m'), 3)
        if load['w2'] != load['w1']:
            label += '..' + units.number(units.from_si(load['w2'], 'kN/m'), 3)
        mx, my = (a1[0] + b1[0]) / 2 - ux * 6, (a1[1] + b1[1]) / 2 - uy * 6
        if 64 < (a0[1]+b0[1])/2 < bottom - 8:
            centre_text(draw, mx, max(60,my-4), label, color)
    # Cursor: a dimension line for a straight beam, a marker on a frame.
    if cursor is not None:
        cx, cy = view.p(*cursor[0])
        if straight:
            y = CURSOR_Y
            draw._line(LEFT, y, RIGHT, y, p.GRID)
            for s in items.stops(model, 0):
                x = view.p(*items.cursor_point(model, 0, s))[0]
                draw._line(x, y - 2, x, y + 2, p.MUTED)
            draw._fill_triangle(cx, y + 1, cx - 3, y + 5, cx + 3, y + 5, accent)
            label = 'x = ' + units.show(cursor[1], 'm')
            centre_text(draw, cx, y + 6, label, accent)
            total = bm.line_offsets(model, bm.lines(model)[0])[1]
            length = 'L ' + units.show(total, 'm')
            lw = draw.len(length, XS)
            if abs(cx - (RIGHT - lw // 2)) > (draw.len(label, XS) + lw) // 2 + 6:
                right_text(draw, 304, y + 6, length, p.MUTED)
        elif 64 < cy < bottom:
            for (ax, ay), (bx, by) in (((-5, 0), (0, -5)), ((0, -5), (5, 0)), ((5, 0), (0, 5)), ((0, 5), (-5, 0))):
                draw._line(cx + ax, cy + ay, cx + bx, cy + by, accent)
    if problem is not None and problem.where is not None:
        ex, ey = view.p(*problem.where)
        if 64 < ey < bottom:
            draw._line(ex - 5, ey - 5, ex + 5, ey + 5, p.ERROR)
            draw._line(ex - 5, ey + 5, ex + 5, ey - 5, p.ERROR)


def deflected(model, sol, view, case_view, target_px=10.0):
    """Screen polylines of the deflected shape, one per line, or None."""
    data = [sol.samples(line, case_view) for line in range(len(sol.lines))]
    peak = 0.0
    for d in data:
        W, U = d[4], d[6]
        for i in range(len(W)):
            peak = max(peak, abs(W[i]), abs(U[i]))
    if peak <= 0:
        return None
    k = target_px / peak / view.scale
    out = []
    for line, d in enumerate(data):
        S, W, U = d[0], d[4], d[6]
        points = []
        for i in range(len(S)):
            m, x = sol.locate(line, S[i])
            X0, Y0, c, s, L = bm.member_axis(model, m)
            dx, dy = U[i] * c - W[i] * s, U[i] * s + W[i] * c
            points.append(view.p(X0 + c * x + dx * k, Y0 + s * x + dy * k))
        out.append(points)
    return out


def status(draw, p, lines, colors, top):
    for i, (line, color) in enumerate(zip(lines[:3], colors)):
        text(draw, 16, top + 9 * i, line[:48], color)


def summary_box(draw, p, lines, bad, rect):
    """The result summary (or the model's problem) in a box over the
    bottom of the preview."""
    x, y, w, h = rect
    lines = lines[:2]
    height = 10 * len(lines) + 7
    top = y + h - height - 4
    draw._fill_rectangle(x + 5, top, w - 10, height, p.BG)
    draw._rectangle(x + 5, top, w - 10, height, p.ERROR if bad else p.GRID)
    for i, line in enumerate(lines):
        text(draw, x + 10, top + 4 + 10 * i, line[:48], p.ERROR if bad else p.TEXT)


# ---------------------------------------------------------------- cross-sections

def section_parts(shape, dims):
    """Rectangles (x, y, w, h, part) in metres from the top left, or circles
    ('circle', radius, part) about the centre; part 'hole' is cut out."""
    if shape == 'Rectangle':
        return [(0, 0, dims['b'], dims['h'], 'all')], dims['b'], dims['h']
    if shape == 'I-section':
        h, b, tw, tf = dims['h'], dims['b'], dims['tw'], dims['tf']
        return [(0, 0, b, tf, 'tf'), (0, h - tf, b, tf, 'tf'), ((b - tw) / 2, tf, tw, h - 2 * tf, 'tw')], b, h
    if shape == 'T-section':
        h, b, tw, tf = dims['h'], dims['b'], dims['tw'], dims['tf']
        return [(0, 0, b, tf, 'tf'), ((b - tw) / 2, tf, tw, h - tf, 'tw')], b, h
    if shape == 'Hollow rect':
        h, b, t = dims['h'], dims['b'], dims['t']
        return [(0, 0, b, h, 't'), (t, t, b - 2 * t, h - 2 * t, 'hole')], b, h
    if shape == 'Circle':
        return [('circle', dims['d'] / 2, 'all')], dims['d'], dims['d']
    if shape == 'Tube':
        return [('circle', dims['d'] / 2, 't'), ('circle', dims['d'] / 2 - dims['t'], 'hole')], dims['d'], dims['d']
    return [], 0, 0


def cross_section(draw, p, section, field, box, border=True):
    """The section to scale in box, the size being edited highlighted."""
    left, top, right, bottom = box
    if border:draw._rectangle(left, top, right - left, bottom - top, p.GRID)
    shape = section['shape']
    if shape == 'Direct':
        centre_text(draw, (left + right) // 2, (top + bottom) // 2 - 8, 'Direct values:', p.MUTED, XS, left, right)
        centre_text(draw, (left + right) // 2, (top + bottom) // 2 + 2, 'no shape to draw', p.MUTED, XS, left, right)
        return
    try:
        bm.properties(shape, section['dims'])
    except ValueError as exc:
        for i, line in enumerate(wrap(str(exc), (right - left) // 6 - 1)[:5]):
            text(draw, left + 4, top + 6 + 10 * i, line, p.ERROR)
        return
    parts, width, height = section_parts(shape, section['dims'])
    room_w, room_h = right - left - 34, bottom - top - 30
    scale = min(room_w / width, room_h / height)
    w_px, h_px = width * scale, height * scale
    ox = left + 22 + (room_w - w_px) / 2
    oy = top + 8 + (room_h - h_px) / 2
    base = mix(p.BG, p.TEXT, 2, 5)
    part = field[4:] if field and field.startswith('dim:') else None
    for item in parts:
        name = item[-1]
        color = p.BG if name == 'hole' else (p.ACCENT if part == name else base)
        if item[0] == 'circle':
            draw._fill_circle(int(ox + w_px / 2), int(oy + h_px / 2), max(1, int(item[1] * scale + 0.5)), color)
        else:
            x, y, w, h = item[:4]
            draw._fill_rectangle(int(ox + x * scale + 0.5), int(oy + y * scale + 0.5),
                                 max(2, int(w * scale + 0.5)), max(2, int(h * scale + 0.5)), color)
    # Neutral axis through the centroid.
    centroid = bm.centroid_from_top(shape, section['dims'])
    ny = int(oy + (centroid if centroid is not None else height / 2) * scale)
    for x in range(int(ox) - 6, int(ox + w_px) + 7, 4):
        draw._line(x, ny, x + 1, ny, theme.AMBER)
    # Dimension lines: depth on the left, width (or diameter) below.
    depth_color = p.ACCENT if part in ('h', 'd') else p.MUTED
    width_color = p.ACCENT if part in ('b', 'd') else p.MUTED
    dx = int(ox) - 8
    draw._line(dx, int(oy), dx, int(oy + h_px), depth_color)
    draw._line(dx - 2, int(oy), dx + 2, int(oy), depth_color)
    draw._line(dx - 2, int(oy + h_px), dx + 2, int(oy + h_px), depth_color)
    label = units.number(units.from_si(height, 'mm'), 3)[:5]
    for i, ch in enumerate(label):
        text(draw, left + 3, int(oy + h_px / 2) - len(label) * 4 + 8 * i, ch, depth_color)
    dy = int(oy + h_px) + 6
    draw._line(int(ox), dy, int(ox + w_px), dy, width_color)
    draw._line(int(ox), dy - 2, int(ox), dy + 2, width_color)
    draw._line(int(ox + w_px), dy - 2, int(ox + w_px), dy + 2, width_color)
    centre_text(draw, ox + w_px / 2, dy + 3, units.number(units.from_si(width, 'mm'), 3) + ' mm', width_color, XS,
                left + 2, right - 2)


def section_panel(draw, p, model, section, x, top):
    """Section properties beside the drawing."""
    try:
        v = bm.section_values(section)
    except ValueError as exc:
        for i, line in enumerate(wrap(str(exc), 22)[:4]):
            text(draw, x, top + 10 * i, line, p.ERROR)
        return
    rows = (('A', units.show(v['A'], 'cm2')), ('I', units.show(v['I'], 'cm4')), ('W', units.show(v['W'], 'cm3')),
            ('Mass', units.number(v['rho'] * v['A'], 3) + ' kg/m'), ('E', units.show(v['E'], 'GPa')),
            ('EI', units.show(v['E'] * v['I'], 'kNm2')))
    for i, (label, value) in enumerate(rows):
        text(draw, x, top + 12 * i, label, p.MUTED)
        right_text(draw, 304, top + 12 * i, value, p.TEXT)
    users = [str(m + 1) for m, member in enumerate(model['members']) if model['sections'][member['section']] is section]
    if users:
        text(draw, x, top + 12 * len(rows) + 4, ('Members ' + ', '.join(users))[:23], p.MUTED)


# ---------------------------------------------------------------- lists

# ---------------------------------------------------------------- diagrams

# title, unit, index in the at() results (samples() arrays are offset by one)
QUANTITIES = {'V': ('Shear', 'kN', 0), 'M': ('Moment', 'kNm', 1), 'T': ('Slope', 'mrad', 2),
              'W': ('Deflection', 'mm', 3), 'N': ('Normal force', 'kN', 4),
              'U': ('Axial displacement', 'mm', 5)}
PANEL_TOP, PANEL_H, PANEL_GAP = 78, 72, 4


def panel_bounds(index,bottom=302):
    h=max(30,(bottom-PANEL_TOP-2*PANEL_GAP)//3)
    top=PANEL_TOP+index*(h+PANEL_GAP)
    return top,top+11,top+h-2


def diagram_cache(solution, line, view, panels, bottom=302, member=None):
    """Pixel polylines and scales for each panel, computed once per view."""
    data = solution.samples(line, view, member=member)
    S = data[0]
    start, total = diagram_range(solution,line,member)
    xs = [int(LEFT + (RIGHT - LEFT) * (S[i]-start) / total + 0.5) for i in range(len(S))]
    out = []
    for slot, name in enumerate(panels):
        values = data[1 + QUANTITIES[name][2]]
        lo = hi = 0.0
        for i in range(len(values)):
            v = values[i]
            if v < lo:
                lo = v
            if v > hi:
                hi = v
        span = hi - lo
        if span < 1e-9 * max(1.0, abs(hi), abs(lo)) or span == 0:
            span, lo, hi = 1.0, lo - 0.5, hi + 0.5
        top, plot_top, plot_bottom = panel_bounds(slot,bottom)
        scale = (plot_bottom - plot_top) / span
        ys = [int(plot_bottom - (values[i] - lo) * scale + 0.5) for i in range(len(values))]
        zero = int(plot_bottom - (0 - lo) * scale + 0.5)
        out.append((xs, ys, zero, lo, hi))
    return out


COLORS = {'V': None, 'M': theme.AMBER, 'W': 0xF81F, 'T': 0x07E0, 'N': 0xFFE0, 'U': 0x07FF}


def diagram_range(solution,line,member=None):
    run=solution.lines[line]
    offsets,total=bm.line_offsets(solution.model,run)
    if member is None:return 0.0,total
    return offsets[run.index(member)],bm.member_length(solution.model,member)


def diagram_header(draw,p,title,view_name,readout):
    width=int(draw.size.x)
    text(draw,16,47,title,p.TEXT,SM)
    available=width-40-draw.len(title,SM)
    while view_name and draw.len(view_name,SM)>available:view_name=view_name[:-1]
    right_text(draw,width-16,47,view_name,p.ACCENT,SM)
    text(draw,16,60,readout[:52],p.TEXT)


def diagrams(draw, p, solution, line, view, panels, cache, cursor_s, readout, note, marks, title, bottom=302, member=None):
    width = int(draw.size.x)
    start,total = diagram_range(solution,line,member)
    cx = int(LEFT + (RIGHT - LEFT) * (cursor_s-start) / total + 0.5)
    diagram_header(draw,p,title,solution.view_names()[view],readout)
    if note:
        text(draw, 16, 69, note[:52], theme.AMBER)
    run = solution.lines[line]
    offsets = dict(zip(run, bm.line_offsets(solution.model, run)[0]))
    supports = [int(LEFT + (RIGHT - LEFT) * (offsets[s['m']] + s['x']-start) / total + 0.5)
                for s in solution.model['supports'] if s['m'] in offsets
                and start <= offsets[s['m']]+s['x'] <= start+total]
    for slot, name in enumerate(panels):
        xs, ys, zero, lo, hi = cache[slot]
        title_text, unit, q = QUANTITIES[name]
        top, plot_top, plot_bottom = panel_bounds(slot,bottom)
        color = COLORS[name] or p.ACCENT
        shade = mix(p.BG, color, 1, 3)
        draw._rectangle(LEFT - 2, top, RIGHT - LEFT + 5, plot_bottom-top+2, p.GRID)
        text(draw, LEFT + 1, top + 2, '%s %s' % (title_text, unit), color)
        peak = units.number(units.from_si(hi, unit), 3) + ' / ' + units.number(units.from_si(lo, unit), 3)
        right_text(draw, RIGHT, top + 2, peak, p.MUTED)
        for x in supports:
            dashed(draw, x, plot_top, plot_bottom, p.GRID, 2)
        if plot_top <= zero <= plot_bottom:
            draw._line(LEFT, zero, RIGHT, zero, p.AXIS)
        last = -1
        for i in range(len(xs)):
            if xs[i] != last and xs[i] % 2 == 0 and plot_top <= zero <= plot_bottom + 1:
                draw._line(xs[i], zero, xs[i], ys[i], shade)
            last = xs[i]
        for i in range(1, len(xs)):
            draw._line(xs[i - 1], ys[i - 1], xs[i], ys[i], color)
        for mark_s, mark_q in marks:
            if mark_q == name:
                mx = int(LEFT + (RIGHT - LEFT) * (mark_s-start) / total + 0.5)
                draw._circle(mx, plot_top - 3, 2, theme.AMBER)
        draw._line(cx, plot_top - 1, cx, plot_bottom + 1, p.TEXT)


OVERVIEW = ('M', 'V', 'N', 'W')


def overview(draw, p, model, solution, view, quantity, cursor, current_line, box, active_member=None):
    """The whole structure with one quantity drawn along every member:
    moment on the tension side, shear and normal force on the member's left
    when positive, the deflected shape exaggerated."""
    v = View(model, box)
    title, unit, q = QUANTITIES[quantity]
    color = COLORS[quantity] or p.ACCENT
    shade = mix(p.BG, color, 1, 3)
    for m, member in enumerate(model['members']):
        a, b = v.p(*model['joints'][member['a']]), v.p(*model['joints'][member['b']])
        color = p.ACCENT if m == active_member else p.TEXT if active_member is None and m in solution.lines[current_line] else p.MUTED
        thick(draw, a, b, color, 24, 284)
    for s in model['supports']:
        x, y = v.p(*bm.point(model, s['m'], s['x']))
        support_shape(draw, x, y, s['kind'], p.MUTED)
    data = [solution.samples(line, view) for line in range(len(solution.lines))]
    peak = 0.0
    for d in data:
        values = d[1 + q]
        for i in range(len(values)):
            peak = max(peak, abs(values[i]))
            if quantity == 'W':
                peak = max(peak, abs(d[6][i]))
    caption = title + ' ' + unit + (', tension side' if quantity == 'M' else '')
    text(draw, 16, 78, caption, color)
    if peak <= 1e-12:
        centre_text(draw, 160, 270, 'No %s in this view' % title.lower(), p.MUTED, SM)
        return
    k = 22.0 / peak
    for line, d in enumerate(data):
        S, values = d[0], d[1 + q]
        previous, best = None, (0.0, None)
        for i in range(len(S)):
            m, x = solution.locate(line, S[i])
            X0, Y0, c, s, L = bm.member_axis(model, m)
            base = v.p(X0 + c * x, Y0 + s * x)
            if quantity == 'W':
                dx, dy = d[6][i] * c - values[i] * s, d[6][i] * s + values[i] * c
                tip = (base[0] + dx * k, base[1] - dy * k)
            else:
                # Local y on screen is (-s, -c); moment goes to the tension side.
                size = -values[i] * k if quantity == 'M' else values[i] * k
                tip = (base[0] - s * size, base[1] - c * size)
                if i % 3 == 0:
                    clip(draw, base[0], base[1], tip[0], tip[1], shade, 24, 284)
            if previous is not None:
                clip(draw, previous[0], previous[1], tip[0], tip[1], color, 24, 284)
            previous = tip
            if abs(values[i]) > abs(best[0]):
                best = (values[i], tip)
        if best[1] is not None:
            label = units.number(units.from_si(best[0], unit), 3)
            centre_text(draw, best[1][0], best[1][1] + (-10 if best[1][1] < 170 else 3), label, color)
    if cursor is not None:
        cx, cy = v.p(*cursor)
        draw._circle(cx, cy, 3, p.TEXT)
