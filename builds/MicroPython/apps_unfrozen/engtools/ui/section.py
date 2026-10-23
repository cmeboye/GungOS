"""Shared Beam view cross-section preview, dimension highlighting and layout.

Callers supply their own property validator and details renderer, so opening
this view from another tool does not load Beam view's model or controller.
"""
from engtools import units
from . import theme
from .lab import mix, text, right_text, centre_text, wrap, panel, Viewport
from picoware.system.font import FONT_XTRA_SMALL as XS


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


def cross_section(draw, p, section, field, box, border=True, validate=None, centroid_from_top=None, axes=None):
    """The section to scale in box, the size being edited highlighted."""
    left, top, right, bottom = box
    if border:draw._rectangle(left, top, right - left, bottom - top, p.GRID)
    shape = section['shape']
    if shape == 'Direct':
        centre_text(draw, (left + right) // 2, (top + bottom) // 2 - 8, 'Direct values:', p.MUTED, XS, left, right)
        centre_text(draw, (left + right) // 2, (top + bottom) // 2 + 2, 'no shape to draw', p.MUTED, XS, left, right)
        return
    try:
        if validate is not None:
            validate(shape, section['dims'])
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
            if item[1] <= 0:
                continue
            draw._fill_circle(int(ox + w_px / 2), int(oy + h_px / 2), max(1, int(item[1] * scale + 0.5)), color)
        else:
            x, y, w, h = item[:4]
            draw._fill_rectangle(int(ox + x * scale + 0.5), int(oy + y * scale + 0.5),
                                 max(2, int(w * scale + 0.5)), max(2, int(h * scale + 0.5)), color)
    # Neutral axis through the centroid.
    centroid = centroid_from_top(shape, section['dims']) if centroid_from_top is not None else None
    ny = int(oy + (centroid if centroid is not None else height / 2) * scale)
    if axes is not False:  # None preserves the original Beam view neutral axis.
        for x in range(int(ox) - 6, int(ox + w_px) + 7, 4):
            draw._line(x, ny, x + 1, ny, theme.AMBER)
    if axes:
        nx = int(ox+w_px/2)
        for y in range(int(oy)-3, int(oy+h_px)+4, 4):
            draw._line(nx, y, nx, y+1, p.ACCENT)
        draw._fill_circle(nx, ny, 2, p.ACCENT)
        text(draw, min(right-9, ox+w_px+8), ny-10, 'y', theme.AMBER)
        text(draw, nx+4, max(top+1, oy-7), 'z', p.ACCENT)
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


def preview(draw, p, section, field, rect, details, footer='', validate=None, centroid_from_top=None, axes=None):
    """The same split section/derived-property preview used in Beam view."""
    x, y, w, h = rect
    panel(draw, p, rect, 'SECTION PREVIEW', section.get('name', ''), p.PANEL)
    top, image_bottom = y+21, y+h-28
    bounded = Viewport(draw, (x+6, top, x+w-6, image_bottom))
    pp = theme.colors(p.PANEL, p.TEXT, p.ACCENT)
    cross_section(bounded, pp, section, field, (x+8, top, x+157, image_bottom), False,
                  validate=validate, centroid_from_top=centroid_from_top, axes=axes)
    draw._line(x+163, top+1, x+163, image_bottom-1, p.GRID)
    details(bounded, pp, x+172, top+1)
    caption = Viewport(draw, (x+8, y+h-21, x+w-8, y+h-3))
    text(caption, x+8, y+h-20, footer, p.MUTED)
