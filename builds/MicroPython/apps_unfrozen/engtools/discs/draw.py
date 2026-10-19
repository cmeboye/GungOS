"""Pictures for the disc tool: the axial cross-section, a wireframe of the
stack, and stress plots through the radius."""
from math import cos, sin, radians
from picoware.system.font import FONT_XTRA_SMALL as XS, FONT_SMALL as SM
from engtools.ui import theme
from engtools.ui.lab import mix, text, right_text, centre_text
from engtools.units import number

LEFT, RIGHT = 22, 298
SEGMENTS = 36
_ring = [(cos(6.283185307 * i / SEGMENTS), sin(6.283185307 * i / SEGMENTS)) for i in range(SEGMENTS + 1)]


def body_color(p, k, chosen):
    if chosen:
        return p.ACCENT
    return p.TEXT if k % 2 == 0 else mix(p.TEXT, theme.AMBER, 1, 2)


def _arrow(draw, x1, y1, x2, y2, color):
    draw._line(int(x1), int(y1), int(x2), int(y2), color)
    ux = (x2 > x1) - (x2 < x1)
    draw._fill_triangle(int(x2), int(y2), int(x2 - 4 * ux), int(y2 - 3), int(x2 - 4 * ux), int(y2 + 3), color)


def _hatch(draw, x0, y0, x1, y1, color, flip, gap=5):
    """45 degree hatching clipped to a rectangle."""
    if x1 - x0 < 2 or y1 - y0 < 2:
        return
    if not flip:  # x - y = d
        d = x0 - y1
        while d <= x1 - y0:
            ya, yb = max(y0, x0 - d), min(y1, x1 - d)
            if ya <= yb:
                draw._line(ya + d, ya, yb + d, yb, color)
            d += gap
    else:  # x + y = d
        d = x0 + y0
        while d <= x1 + y1:
            ya, yb = max(y0, d - x1), min(y1, d - x0)
            if ya <= yb:
                draw._line(d - ya, ya, d - yb, yb, color)
            d += gap


def section(draw, p, model, box, selected, zoom=1.0):
    """The stack cut through its axis: material hatched, the bore empty,
    the axis dash-dotted, with pressures and speed marked."""
    left, top, right, bottom = box
    R = model['radii']
    bodies = model['bodies']
    tmax = max(b['t'] for b in bodies)
    s = min((right - left - 24) / (2 * R[-1]), (bottom - top - 30) / tmax) * zoom
    cx, cy = (left + right) // 2, (top + bottom) // 2 - 4
    chosen_body = selected[1] if selected and selected[0] == 'body' else None
    chosen_fit = selected[1] if selected and selected[0] == 'fit' else None
    for k, b in enumerate(bodies):
        a, c = R[k] * s, R[k + 1] * s
        h = b['t'] * s / 2
        y0, y1 = int(cy - h), int(cy + h)
        color = body_color(p, k, chosen_body == k)
        shade = mix(p.BG, color, 1, 4)
        for x0, x1 in ((int(cx + a), int(cx + c)), (int(cx - c), int(cx - a))):
            draw._fill_rectangle(x0, y0, max(1, x1 - x0), max(1, y1 - y0), shade)
            _hatch(draw, x0, y0, x1, y1, mix(p.BG, color, 1, 2), k % 2 == 1)
            draw._rectangle(x0, y0, max(1, x1 - x0 + 1), max(1, y1 - y0 + 1), color)
    for j in range(len(bodies) - 1):
        if chosen_fit == j:
            x = int(R[j + 1] * s)
            h = int(max(bodies[j]['t'], bodies[j + 1]['t']) * s / 2) + 4
            for xx in (cx + x, cx - x):
                draw._line(xx, cy - h, xx, cy + h, p.ACCENT)
                draw._line(xx + 1, cy - h, xx + 1, cy + h, p.ACCENT)
    # Axis of rotation, dash-dot.
    y = top
    while y < bottom - 12:
        draw._line(cx, y, cx, min(y + 6, bottom - 12), p.MUTED)
        y += 10
    # Pressures and speed.
    h0 = bodies[0]['t'] * s / 2
    if model['Pi']['v'] or model['Pi']['find']:
        if R[0] > 0:
            x = R[0] * s
            for sign in (1, -1):
                _arrow(draw, cx + sign * (x - 12), cy, cx + sign * (x - 2), cy, theme.AMBER)
            if x > 22:
                centre_text(draw, cx, cy - 12, 'Pi', theme.AMBER, XS, left, right)
    hN = bodies[-1]['t'] * s / 2
    if model['Po']['v'] or model['Po']['find']:
        x = R[-1] * s
        for sign in (1, -1):
            _arrow(draw, cx + sign * (x + 12), cy, cx + sign * (x + 2), cy, theme.AMBER)
    if model['speed']['v'] or model['speed']['find']:
        y = int(cy - tmax * s / 2) - 8
        draw._line(cx - 12, y, cx + 12, y, p.ACCENT)
        draw._fill_triangle(cx + 14, y, cx + 9, y - 3, cx + 9, y + 3, p.ACCENT)
    # Diameters along the bottom, where they do not crowd each other.
    y = int(cy + tmax * s / 2) + 4
    last = -99
    for r in R:
        x = int(cx + r * s)
        if r <= 0 or x - last < 26:
            continue
        draw._line(x, y, x, y + 3, p.MUTED)
        centre_text(draw, x, y + 5, number(2 * r * 1e3, 3), p.MUTED, XS, left, right)
        last = x
    text(draw, left + 2, y + 5, 'dia mm', p.MUTED)


def wireframe(draw, p, model, box, yaw, pitch, zoom, selected):
    """The stack as a wireframe, turned by yaw about its axis and tilted by
    pitch (0 side on, 90 face on)."""
    left, top, right, bottom = box
    R = model['radii']
    bodies = model['bodies']
    tmax = max(b['t'] for b in bodies)
    cy_, sy_ = cos(radians(yaw)), sin(radians(yaw))
    cp, sp = cos(radians(pitch)), sin(radians(pitch))
    size = max(2 * R[-1], tmax)
    s = min(right - left, bottom - top) / (1.15 * size) * zoom
    cx, cy = (left + right) / 2, (top + bottom) / 2
    chosen_body = selected[1] if selected and selected[0] == 'body' else None
    chosen_fit = selected[1] if selected and selected[0] == 'fit' else None

    def P(x, y, z):
        x1 = x * cy_ - y * sy_
        y1 = x * sy_ + y * cy_
        return int(cx + s * x1), int(cy - s * (z * cp - y1 * sp))

    def circle(r, z, color):
        prev = None
        for c, sn in _ring:
            q = P(r * c, r * sn, z)
            if prev is not None:
                draw._line(prev[0], prev[1], q[0], q[1], color)
            prev = q
    # Axis.
    a, b = P(0, 0, -tmax * 0.75), P(0, 0, tmax * 0.75)
    draw._line(a[0], a[1], b[0], b[1], p.MUTED)
    for k, body in enumerate(bodies):
        color = body_color(p, k, chosen_body == k)
        h = body['t'] / 2
        radii = [R[k + 1]] + ([R[k]] if R[k] > 0 else [])
        for r in radii:
            fit_edge = chosen_fit is not None and r == R[chosen_fit + 1]
            col = p.ACCENT if fit_edge else color
            circle(r, h, col)
            circle(r, -h, col)
            for i in range(0, SEGMENTS, SEGMENTS // 8):
                c, sn = _ring[i]
                q1, q2 = P(r * c, r * sn, h), P(r * c, r * sn, -h)
                draw._line(q1[0], q1[1], q2[0], q2[1], col)
        if R[k] == 0:
            # A solid centre: show its face with a few spokes.
            for i in range(0, SEGMENTS, SEGMENTS // 4):
                c, sn = _ring[i]
                q1, q2 = P(0, 0, h), P(R[k + 1] * c, R[k + 1] * sn, h)
                draw._line(q1[0], q1[1], q2[0], q2[1], mix(p.BG, color, 1, 2))


# ---------------------------------------------------------------- plots

QUANTITIES = {'sr': ('Radial stress', 'MPa', 1), 'st': ('Hoop stress', 'MPa', 2), 'sz': ('Axial stress', 'MPa', 3),
              'u': ('Radial displacement', 'um', 4), 'vm': ('von Mises', 'MPa', 5)}
COLORS = {'sr': None, 'st': theme.AMBER, 'sz': 0xFFE0, 'u': 0x07FF, 'vm': 0xF81F}
PANEL_TOP = 78


def panel_bounds(index, bottom):
    h = max(30, (bottom - PANEL_TOP - 8) // 3)
    top = PANEL_TOP + index * (h + 4)
    return top, top + 11, top + h - 2


def plots(draw, p, sol, panels, cursor, bottom):
    """Three panels of a quantity against radius, every body sampled, with
    the interfaces dashed and the cursor radius marked."""
    R = sol.R
    r0, r1 = R[0], R[-1]
    span = r1 - r0

    def X(r):
        return int(LEFT + (RIGHT - LEFT) * (r - r0) / span + 0.5)
    data = [sol.samples(k) for k in range(sol.N)]
    for slot, name in enumerate(panels):
        title, unit, q = QUANTITIES[name]
        scale_u = 1e3 if name == 'u' else 1.0
        lo = hi = 0.0
        for S in data:
            for row in S:
                v = row[q] * scale_u
                lo, hi = min(lo, v), max(hi, v)
        rng = hi - lo
        if rng < 1e-9 * max(1.0, abs(hi), abs(lo)):
            rng, lo, hi = 1.0, lo - 0.5, hi + 0.5
        top, ptop, pbottom = panel_bounds(slot, bottom)
        color = COLORS[name] or p.ACCENT
        shade = mix(p.BG, color, 1, 3)
        draw._rectangle(LEFT - 2, top, RIGHT - LEFT + 5, pbottom - top + 2, p.GRID)
        text(draw, LEFT + 1, top + 2, title + ' ' + unit, color)
        right_text(draw, RIGHT, top + 2, number(hi, 3) + ' / ' + number(lo, 3), p.MUTED)

        def Y(v):
            return int(pbottom - (v - lo) * (pbottom - ptop) / rng + 0.5)
        zero = Y(0.0)
        if ptop <= zero <= pbottom:
            draw._line(LEFT, zero, RIGHT, zero, p.AXIS)
        for k, S in enumerate(data):
            prev = None
            for row in S:
                x, y = X(row[0]), Y(row[q] * scale_u)
                if x % 2 == 0 and ptop <= zero <= pbottom:
                    draw._line(x, zero, x, y, shade)
                if prev is not None:
                    draw._line(prev[0], prev[1], x, y, color)
                prev = (x, y)
        for r in R[1:-1]:
            x = X(r)
            for y in range(ptop, pbottom, 4):
                draw._line(x, y, x, min(y + 1, pbottom), p.GRID)
        cx = X(cursor)
        draw._line(cx, ptop - 1, cx, pbottom + 1, p.TEXT)
