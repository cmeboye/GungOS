"""Textbook math layout using native fonts and a handful of vector glyphs."""
from picoware.system.font import FONT_XTRA_SMALL, FONT_SMALL, FONT_MEDIUM
from engtools.ui import theme
from .editor import Node


class Box:
    def __init__(self, kind, width, height, baseline, font, value=None, children=None):
        self.kind, self.w, self.h, self.base, self.font = kind, width, height, baseline, font
        self.value, self.children = value, children or []


class Renderer:
    def __init__(self, draw, clip, accent=theme.ACCENT, palette=None):
        self.draw, self.clip = draw, clip
        self.accent = accent
        self.palette = palette or theme.colors(getattr(draw, 'background', theme.BG), getattr(draw, 'foreground', theme.TEXT), accent)
        self.metrics = {}
        for size in (0, 1, 2, 3, 4):
            font = draw.get_font(size)
            self.metrics[size] = (font.width+font.spacing, font.height)
        self.cursor = None

    def text(self, x, y, text, color=None, font=FONT_SMALL):
        if color is None: color = self.palette.TEXT
        cw, ch = self.metrics[font]
        left, top, right, bottom = self.clip
        for char in str(text):
            if x >= left and y >= top and x+cw <= right and y+ch <= bottom:
                self.draw._text(int(x), int(y), char, color, font)
            x += cw

    def fill(self, x, y, w, h, color):
        left, top, right, bottom = self.clip
        endx, endy = min(right, x+w), min(bottom, y+h)
        x, y = max(left, x), max(top, y)
        if endx > x and endy > y:
            self.draw._fill_rectangle(int(x), int(y), int(endx-x), int(endy-y), color)

    def line(self, x1, y1, x2, y2, color=None):
        if color is None: color = self.palette.TEXT
        # Liang-Barsky clipping keeps radicals/fraction bars inside their panel.
        left, top, right, bottom = self.clip
        dx, dy, first, last = x2-x1, y2-y1, 0, 1
        for p, q in ((-dx, x1-left), (dx, right-1-x1), (-dy, y1-top), (dy, bottom-1-y1)):
            if p == 0:
                if q < 0: return
            else:
                t = q/p
                if p < 0: first = max(first, t)
                else: last = min(last, t)
                if first > last: return
        self.draw._line(int(x1+first*dx), int(y1+first*dy), int(x1+last*dx), int(y1+last*dy), color)

    def rect(self, x, y, w, h, color):
        self.line(x, y, x+w-1, y, color)
        self.line(x, y+h-1, x+w-1, y+h-1, color)
        self.line(x, y, x, y+h-1, color)
        self.line(x+w-1, y, x+w-1, y+h-1, color)

    def glyph(self, kind, x, y, w, h, color=None):
        if color is None: color = self.palette.TEXT
        if kind == 'pi':
            self.line(x, y+2, x+w-1, y+2, color)
            self.line(x+3, y+2, x+2, y+h-1, color)
            self.line(x+w-4, y+2, x+w-4, y+h-2, color)
            self.line(x+w-4, y+h-2, x+w-2, y+h-1, color)
        elif kind == 'int':
            cx = x+w//2
            self.line(cx+3, y+1, cx+1, y, color)
            self.line(cx+1, y, cx-1, y+3, color)
            self.line(cx-1, y+3, cx-2, y+h-4, color)
            self.line(cx-2, y+h-4, cx-4, y+h-1, color)
            self.line(cx-4, y+h-1, cx-6, y+h-2, color)
        elif kind == 'sum':
            self.line(x+w-1, y+2, x+w-1, y, color)
            self.line(x+w-1, y, x, y, color)
            self.line(x, y, x+w//2, y+h//2, color)
            self.line(x+w//2, y+h//2, x, y+h-1, color)
            self.line(x, y+h-1, x+w-1, y+h-1, color)
            self.line(x+w-1, y+h-1, x+w-1, y+h-3, color)
        elif kind == 'prod':
            self.line(x, y, x+w-1, y, color)
            self.line(x+3, y, x+3, y+h-1, color)
            self.line(x+w-4, y, x+w-4, y+h-1, color)
            self.line(x+1, y+h-1, x+5, y+h-1, color)
            self.line(x+w-6, y+h-1, x+w-2, y+h-1, color)

    def layout(self, row, font=FONT_MEDIUM):
        cw, ch = self.metrics[font]
        script = max(0, font-1)
        sw, sh = self.metrics[script]
        if not row:
            return Box('row', max(10, cw+3), ch+4, ch+2, font, row)
        children, width, above, below = [], 0, ch, 0
        for item in row:
            if isinstance(item, str): box = Box('char', cw, ch, ch, font, item)
            elif item.kind in ('pow', 'sub'):
                child = self.layout(item.rows[0], script)
                if item.kind == 'pow':
                    box = Box('pow', child.w+2, child.h+ch//2, child.h+ch//2, font, children=[(child, 1, 0)])
                else:
                    box = Box('sub', child.w+2, ch+child.h-3, ch, font, children=[(child, 1, ch-3)])
            elif item.kind == 'pi': box = Box('pi', cw+3, ch, ch, font)
            elif item.kind == 'sqrt':
                child = self.layout(item.rows[0], font)
                box = Box('sqrt', child.w+13, child.h+5, child.base+5, font, children=[(child, 12, 5)])
            elif item.kind == 'frac':
                a, b = [self.layout(r, script) for r in item.rows]
                w = max(a.w, b.w)+8
                box = Box('frac', w, a.h+b.h+7, a.h+4+b.h//2, font,
                          children=[(a, (w-a.w)//2, 0), (b, (w-b.w)//2, a.h+7)])
            elif item.kind == 'int':
                a, b = [self.layout(r, FONT_XTRA_SMALL) for r in item.rows[:2]]
                expr = self.layout(item.rows[2], font)
                boundw, h = max(a.w, b.w)+4, max(44, expr.h+8, a.h+b.h+18)
                box = Box('int', 15+boundw+expr.w+3+2*cw, h, (h-expr.h)//2+expr.base, font,
                          children=[(a, 14, h-a.h), (b, 14, 0), (expr, 15+boundw, (h-expr.h)//2)])
            elif item.kind in ('sum','prod'):
                index, lower, upper = [self.layout(r, FONT_XTRA_SMALL) for r in item.rows[:3]]
                expr = self.layout(item.rows[3], font)
                tinyw = self.metrics[FONT_XTRA_SMALL][0]
                lowerw = index.w+tinyw+lower.w
                lowerbase = max(index.base, lower.base)
                lowerh = lowerbase+max(index.h-index.base, lower.h-lower.base)
                symbolw, symbolh = 20, max(24, ch+8)
                leftw = max(symbolw+4, lowerw+2, upper.w+2)
                top = upper.h+3
                base = top+(symbolh-ch)//2+ch
                # Move the whole operator down if a tall operand needs extra ascent.
                offset = max(0, expr.base-base)
                top, base = top+offset, base+offset
                lowery = top+symbolh+3
                h = max(lowery+lowerh, base+expr.h-expr.base)
                box = Box(item.kind, leftw+6+expr.w, h, base, font,
                          value=((leftw-symbolw)//2, top, symbolw, symbolh,
                                 (leftw-lowerw)//2+index.w, lowery+lowerbase-8),
                          children=[(index, (leftw-lowerw)//2, lowery+lowerbase-index.base),
                                    (lower, (leftw-lowerw)//2+index.w+tinyw, lowery+lowerbase-lower.base),
                                    (upper, (leftw-upper.w)//2, offset),
                                    (expr, leftw+6, base-expr.base)])
            elif item.kind == 'logb':
                base, arg = self.layout(item.rows[0], script), self.layout(item.rows[1], font)
                h = max(arg.h, ch+base.h//2)+4
                box = Box('logb', cw*3+base.w+arg.w+cw*2+2, h, max(ch, arg.base), font,
                          children=[(base, 3*cw, ch-3), (arg, cw*4+base.w, max(0,ch-arg.base))])
            else:
                arg = self.layout(item.rows[0], font)
                box = Box('function', (len(item.kind)+2)*cw+arg.w, arg.h, arg.base, font, item.kind,
                          [(arg, (len(item.kind)+1)*cw, 0)])
            children.append((box, width, 0))
            width += box.w
            above, below = max(above, box.base), max(below, box.h-box.base)
        children = [(box, x, above-box.base) for box, x, _ in children]
        return Box('row', width+2, above+below, above, font, row, children)

    def locate(self, box, x, y, editor):
        if box.kind == 'row' and box.value is editor.row:
            offset = box.children[editor.index][1] if editor.index < len(box.children) else box.w-2
            self.cursor = (x+offset, y+box.base-self.metrics[box.font][1], self.metrics[box.font][1])
        for child, dx, dy in box.children:
            self.locate(child, x+dx, y+dy, editor)

    def paint(self, box, x, y, color=None, editor=None):
        if color is None: color = self.palette.TEXT
        kind = box.kind
        cw, ch = self.metrics[box.font]
        if kind == 'char': self.text(x, y, box.value, color, box.font)
        elif kind == 'row' and not box.children:
            selected = editor is not None and box.value is editor.row
            self.rect(x+1, y+1, box.w-2, box.h-2, self.accent if selected else self.palette.MUTED)
        elif kind == 'pi': self.glyph('pi', x, y, box.w-2, box.h-1, color)
        elif kind == 'sqrt':
            mid = y+box.h//2
            self.line(x+1, mid, x+4, mid+3, color)
            self.line(x+4, mid+3, x+7, y+box.h-2, color)
            self.line(x+7, y+box.h-2, x+11, y+2, color)
            self.line(x+11, y+2, x+box.w-1, y+2, color)
        elif kind == 'frac': self.line(x, y+box.children[0][0].h+3, x+box.w-1, y+box.children[0][0].h+3, color)
        elif kind == 'int':
            self.glyph('int', x+1, y+4, 12, box.h-8, color)
            self.text(x+box.w-2*cw, y+box.base-ch, 'dx', self.palette.MUTED, box.font)
        elif kind in ('sum','prod'):
            sx, sy, sw, sh, ex, ey = box.value
            self.glyph(kind, x+sx, y+sy, sw, sh, color)
            self.text(x+ex, y+ey, '=', color, FONT_XTRA_SMALL)
        elif kind == 'logb':
            self.text(x, y+box.base-ch, 'log', color, box.font)
            arg, ax, ay = box.children[1]
            self.text(x+ax-cw, y+ay+arg.base-ch, '(', color, box.font)
            self.text(x+ax+arg.w, y+ay+arg.base-ch, ')', color, box.font)
        elif kind == 'function':
            self.text(x, y+box.base-ch, box.value+'(', color, box.font)
            self.text(x+box.w-cw, y+box.base-ch, ')', color, box.font)
        for child, dx, dy in box.children:
            self.paint(child, x+dx, y+dy, color, editor)

    def expression(self, row, x, y, font=FONT_MEDIUM, color=None, editor=None, follow=False):
        if color is None: color = self.palette.TEXT
        box = self.layout(row, font)
        if editor is not None:
            self.locate(box, x, y, editor)
            if follow and self.cursor:
                cx, cy, h = self.cursor
                left, top, right, bottom = self.clip
                dx = min(0, right-5-cx) if cx > right-5 else max(0, left+2-cx)
                dy = min(0, bottom-3-cy-h) if cy+h > bottom-3 else max(0, top+2-cy)
                x, y = x+dx, y+dy
                self.locate(box, x, y, editor)
        self.paint(box, x, y, color, editor)
        if editor is not None and self.cursor:
            cx, cy, h = self.cursor
            self.line(cx, cy, cx, cy+h, self.accent)
        return box
