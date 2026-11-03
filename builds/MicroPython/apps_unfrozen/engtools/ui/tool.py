"""Beam-style tool tabs and calculator-rendered equations/help.

No firmware changes: the app owns the help screen, preserving edits and
selections while it is open. Calculator math layout is imported lazily.
"""
from picoware.system import buttons as k
from picoware.system.font import FONT_SMALL as SM, FONT_XTRA_SMALL as XS
from .lab import panel, text, wrap, Viewport


class Tabs:
    def __init__(self, labels):
        self.labels, self.index, self.kept = tuple(labels), 0, {}

    @property
    def label(self):
        return self.labels[self.index]

    def configure(self, labels):
        label = self.label
        self.labels = tuple(labels)
        self.index = self.labels.index(label) if label in self.labels else 0

    def select(self, label, selection=None):
        self.kept[self.label] = selection
        self.index = self.labels.index(label)
        return self.kept.get(label)

    def switch(self, step, selection=None):
        return self.select(self.labels[(self.index+step)%len(self.labels)], selection)


def row(*parts):
    out = []
    for part in parts:
        out.extend(part if isinstance(part, (str, list, tuple)) else [part])
    return out


def node(kind, *rows):
    from engtools.calculator.editor import Node
    return Node(kind, [row(r) for r in rows])


def sub(name, suffix):
    return row(name, node('sub', suffix))


def power(base, exponent='2'):
    return row(base, node('pow', exponent))


def fraction(a, b):
    return node('frac', a, b)


def radical(a):
    return node('sqrt', a)


def equation(draw, p, expression, rect):
    """Fit the calculator's actual expression layout within a tool panel."""
    from engtools.calculator.render import Renderer
    x, y, w, h = rect
    renderer = Renderer(draw, (x, y, x+w, y+h), p.ACCENT, p)
    box = renderer.layout(expression, SM)
    if box.w > w or box.h > h:
        box = renderer.layout(expression, XS)
    renderer.paint(box, x+max(0, (w-box.w)//2), y+max(0, (h-box.h)//2))
    return box.h


def formulas(kind):
    """Read-only calculator trees, shared between help and preview panels."""
    pi = node('pi')
    if kind == 'sectionprops':
        return (
            ('Area centroid (each direction)', row(sub('z', 'c'), '=', fraction(row('sum(', sub('A', 'i'), sub('z', 'i'), ')'), row('sum(', sub('A', 'i'), ')')))),
            ('Parallel-axis theorem', row(sub('I', 'y'), '=sum(', sub('I', 'yi'), '+', sub('A', 'i'), power(sub('d', 'zi')), ')')),
            ('Elastic section modulus', row(sub('W', 'y'), '=', fraction(sub('I', 'y'), sub('c', 'z')))),
            ('Radius of gyration', row(sub('r', 'y'), '=', radical(fraction(sub('I', 'y'), 'A')))),
            ('Polar area moment', row(sub('I', 'p'), '=', sub('I', 'y'), '+', sub('I', 'z'))),
            ('Mass per unit length', row('m/L=rho A')))
    if kind == 'buckling':
        return (
            ('Euler critical load', row(sub('P', 'cr'), '=', fraction(row(power(pi), 'EI'), power('(KL)')))),
            ('Critical stress', row(sub('s', 'cr'), '=', fraction(sub('P', 'cr'), 'A'), '=', fraction(row(power(node('pi')), 'E'), power('lambda')))),
            ('Radius / slenderness', row('r=', radical(fraction('I', 'A')), '  lambda=', fraction('KL', 'r'))),
            ('Load factors', row(sub('n', 'E'), '=', fraction(sub('P', 'cr'), 'P'), '  ', sub('n', 'Y'), '=', fraction(sub('P', 'Y'), 'P'))),
            ('Axial yield', row(sub('P', 'Y'), '=', sub('s', 'Y'), 'A')),
            ('Yield transition slenderness', row(sub('lambda', 'Y'), '=', node('pi'), radical(fraction('E', sub('s', 'Y'))))))
    if kind == 'section':
        return (
            ('Combined normal stress', row(sub('s', 'x'), '=', fraction('N', 'A'), '+', fraction(row(sub('M', 'y'), 'z'), sub('I', 'y')), '-', fraction(row(sub('M', 'z'), 'y'), sub('I', 'z')))),
            ('Circular torsion', row(sub('t', 'xy'), '=-', fraction('Tz', 'J'), '  ', sub('t', 'zx'), '=', fraction('Ty', 'J'))),
            ('Rectangle shear (z analogously)', row(sub('t', 'xy'), '=', fraction(row('3', sub('V', 'y')), '2A'), '(1-', power(row('(', fraction('2y', 'b'), ')')), ')')),
            ('Section resultant shear', row('|tau|=', radical(row(power(sub('t', 'xy')), '+', power(sub('t', 'zx')))))),
            ('Section von Mises stress', row(sub('s', 'VM'), '=', radical(row(power(sub('s', 'x')), '+3(', power(sub('t', 'xy')), '+', power(sub('t', 'zx')), ')')))),
            ('Engineering shear strain', row(sub('g', 'ij'), '=', fraction(sub('t', 'ij'), 'G'), '=2', sub('e', 'ij'))),
            ('Isotropic shear modulus', row('G=', fraction('E', '2(1+nu)'))))
    if kind == 'constitutive':
        return (
            ('Normal strain (cyclic x/y/z)', row(sub('e', 'x'), '=', fraction(row(sub('s', 'x'), '-nu(', sub('s', 'y'), '+', sub('s', 'z'), ')'), 'E'), '+alpha dT')),
            ('Engineering shear strain', row(sub('g', 'xy'), '=', fraction(sub('t', 'xy'), 'G'), '=2', sub('e', 'xy'))),
            ('Isotropic shear modulus', row('G=', fraction('E', '2(1+nu)'))),
            ('Free thermal strain', row(sub('e', 'th'), '=alpha dT')))
    return (
        ('Convert through the base unit', row(sub('q', 'SI'), '=', sub('a', 'in'), sub('q', 'in'), '+', sub('b', 'in'))),
        ('Convert to the target unit', row(sub('q', 'out'), '=', fraction(row(sub('q', 'SI'), '-', sub('b', 'out')), sub('a', 'out')))),
        ('Reciprocal units (fuel economy)', row(sub('q', 'SI'), '=', fraction('c', sub('q', 'in')))))


class EquationHelp:
    def __init__(self):
        self.opened, self.first, self.blocks = False, 0, []
        self.visible = 1

    def open(self, kind, lines):
        self.blocks = [('formula', label, expression) for label, expression in formulas(kind)]
        from picoware.system.view_manager import SYSTEM_HELP
        for line in tuple(lines)+SYSTEM_HELP:
            self.blocks.extend(('text', part, None) for part in wrap(line, 43))
        self.opened, self.first = True, 0

    def key(self, button):
        if button in (k.BUTTON_F9, k.BUTTON_ESCAPE, k.BUTTON_BACK):
            self.opened = False
        else:
            step = {k.BUTTON_UP: -1, k.BUTTON_DOWN: 1, k.BUTTON_LEFT: -self.visible, k.BUTTON_RIGHT: self.visible}.get(button, 0)
            self.first = min(max(0, self.first+step), max(0, len(self.blocks)-1))

    def draw(self, draw, p):
        from engtools.calculator.render import Renderer
        bottom = int(draw.size.y)-16
        panel(draw, p, (8, 43, int(draw.size.x)-16, bottom-43), 'EQUATIONS / HELP', '%d/%d' % (self.first+1, len(self.blocks)))
        bounded = Viewport(draw, (17, 65, int(draw.size.x)-20, bottom-22))
        renderer = Renderer(draw, bounded.box, p.ACCENT, p)
        y = 68
        self.visible = 0
        for kind, label, expression in self.blocks[self.first:]:
            if kind == 'formula':
                box = renderer.layout(expression, SM)
                if box.w > bounded.box[2]-bounded.box[0]:
                    box = renderer.layout(expression, XS)
                height = box.h+21
                if y+height > bottom-22:
                    break
                text(bounded, 19, y, label, p.ACCENT)
                renderer.paint(box, 21, y+14)
            else:
                height = 12
                if y+height > bottom-22:
                    break
                text(bounded, 19, y, label, p.ACCENT if label.endswith(':') else p.TEXT)
            y += height
            self.visible += 1
        text(draw, 18, bottom-14, 'UP/DOWN scroll  F9 / ESC close', p.MUTED)
