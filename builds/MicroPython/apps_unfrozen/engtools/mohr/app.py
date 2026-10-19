"""Mohr circle in PicoLAB: a 2D or 3D stress state, its circles and the
element turned by an angle, with principal stresses and yield checks.

The state stays in RAM while PicoLAB runs. Stresses are in MPa.
"""
from math import sin, cos, radians, sqrt
from picoware.system import buttons as keys
from picoware.system.font import FONT_XTRA_SMALL as XS
from engtools.ui import theme
from engtools.ui.forms import LineEdit, parse_number, erase_key
from engtools.ui.lab import (mix, text, right_text, centre_text, panel, chrome, form, popup,
                             help_capacity, help_box, Viewport, HEAD, FOOT)
from engtools.units import number
from . import stress

TITLE = 'MOHR CIRCLE'
PATH = ('modules', 'structural', 'Mohr circle')
PREVIEW = (8, HEAD + 5, 304, 142)
CIRCLE_BOX = (14, 64, 168, 157)
ELEMENT_BOX = (172, 64, 306, 157)
PROPERTIES_TOP = 191
NAMES = ('sx', 'sy', 'sz', 'txy', 'tyz', 'tzx')
LABELS = {'sx': 'Normal sx', 'sy': 'Normal sy', 'sz': 'Normal sz',
          'txy': 'Shear txy', 'tyz': 'Shear tyz', 'tzx': 'Shear tzx'}
MODES = ('2D', '3D')
MODE_NAMES = ('2D plane stress', '3D general')
EXAMPLES = (
    ('Pure shear', {'mode': '2D', 's': [0.0, 0.0, 0.0, 50.0, 0.0, 0.0]}),
    ('Uniaxial tension', {'mode': '2D', 's': [100.0, 0.0, 0.0, 0.0, 0.0, 0.0]}),
    ('Shaft: bending + torsion', {'mode': '2D', 's': [120.0, 0.0, 0.0, 60.0, 0.0, 0.0]}),
    ('Thin pressure vessel', {'mode': '2D', 's': [50.0, 100.0, 0.0, 0.0, 0.0, 0.0]}),
    ('3D general state', {'mode': '3D', 's': [60.0, 20.0, -30.0, 25.0, 10.0, -15.0]}),
    ('Hydrostatic', {'mode': '3D', 's': [-50.0, -50.0, -50.0, 0.0, 0.0, 0.0]}),
    ('Clear stresses', {'s': [0.0] * 6}),
)
HELP = (
    'Moving and editing:',
    'UP/DOWN choose a value',
    'ENTER edit or choose; type to replace',
    'ENTER/TAB apply  ESC cancel',
    'UP/DOWN apply and move on',
    'Arithmetic works: 120*0.8, 50/2',
    'Rotating the element:',
    'LEFT/RIGHT turn by 1 deg',
    '[ / ] turn by 15 deg',
    'P principal axes (again: swap s1/s2)',
    'S maximum shear axes (again: other)',
    'R back to 0 deg',
    'A next rotation axis (3D)',
    'M switch 2D / 3D',
    'Other keys:',
    'F3 examples  F9 or ? help',
    'ESC leaves Mohr circle',
    'The circle:',
    'tau is drawn positive DOWN, so the',
    'point turns 2*theta the same way',
    'as the element turns theta',
    'X\' point (sx\', txy\') accent colour',
    'Y\' point (sy\', -txy\') amber',
    '3D: shaded band holds every plane;',
    'outlined circle: planes about the axis',
    'Signs and units:',
    'Tension +; shear + on the + face',
    'acting in the + direction',
    'theta counterclockwise looking down',
    'the rotation axis (z in 2D)',
    'Stresses in MPa, angles in degrees',
    'Safety factor = yield / equivalent',
    'Yield 0 hides the safety factors',
)

_active = None


def _axis_names(state):
    i, j = stress.plane(state)
    return stress.AXES[i], stress.AXES[j]


class Mohr:
    def __init__(self, vm):
        self.vm = vm
        from engtools import session
        self.state = session.kept.get('mohr') or stress.new_state()
        self.row = 2
        self.edit = None
        self.popup = None
        self.message, self.error = '', False
        self.help_open, self.help_first = False, 0
        self.last_jump = None
        self.result = stress.results(self.state)

    def keep(self):
        from engtools import session
        session.kept['mohr'] = self.state

    def palette(self):
        return theme.system_palette(self.vm)

    def say(self, message, error=False):
        self.message, self.error = message, error

    def solve(self):
        self.result = stress.results(self.state)

    # ------------------------------------------------------------ rows

    def rows(self):
        """(kind, label, value text, editable, key, unit)"""
        st, r = self.state, self.result
        three = st['mode'] == '3D'
        a, b = _axis_names(st)

        def mpa(v):
            return number(v, 4) + ' MPa'
        out = [('head', 'Stress state', '', False, None, ''),
               ('field', 'Mode', MODE_NAMES[MODES.index(st['mode'])], True, 'mode', 'choice')]
        for index, name in enumerate(NAMES):
            if three or name in ('sx', 'sy', 'txy'):
                out.append(('field', LABELS[name], mpa(st['s'][index]), True, name, 'MPa'))
        out.append(('head', 'Rotation', '', False, None, ''))
        out.append(('field', 'Angle theta', number(st['theta'], 4) + ' deg', True, 'theta', 'deg'))
        if three:
            out.append(('field', 'About axis', st['axis'], True, 'axis', 'choice'))
        out.append(('field', "Rotated s%s'" % a, mpa(r['si']), False, None, ''))
        out.append(('field', "Rotated s%s'" % b, mpa(r['sj']), False, None, ''))
        out.append(('field', "Rotated t%s%s'" % (a, b), mpa(r['tij']), False, None, ''))
        out.append(('head', 'Principal', '', False, None, ''))
        if three:
            out += [('field', 'Principal s1', mpa(r['s1']), False, None, ''),
                    ('field', 'Principal s2', mpa(r['s2']), False, None, ''),
                    ('field', 'Principal s3', mpa(r['s3']), False, None, ''),
                    ('field', 'Max shear', mpa(r['tmax']), False, None, ''),
                    ('field', 'In-plane radius', mpa(r['radius']), False, None, '')]
        else:
            out += [('field', 'Principal s1', mpa(r['p1']), False, None, ''),
                    ('field', 'Principal s2', mpa(r['p2']), False, None, ''),
                    ('field', 'Max in-plane shear', mpa(r['radius']), False, None, ''),
                    ('field', 'Max shear (with sz=0)', mpa(r['tmax']), False, None, '')]
        out.append(('field', 'Principal angle', number(r['angle'], 4) + ' deg', False, None, ''))
        out.append(('head', 'Yield check', '', False, None, ''))
        out.append(('field', 'von Mises', mpa(r['mises']), False, None, ''))
        out.append(('field', 'Tresca (s1-s3)', mpa(r['tresca']), False, None, ''))
        out.append(('field', 'Yield strength', mpa(st['yield']) if st['yield'] > 0 else 'off', True, 'yield', 'MPa'))
        if st['yield'] > 0:
            for key, label in (('n_mises', 'Safety, von Mises'), ('n_tresca', 'Safety, Tresca')):
                value = r.get(key)
                out.append(('field', label, '--' if value is None else number(value, 3), False, None, ''))
        return out

    def current(self):
        rows = self.rows()
        self.row = min(max(self.row, 0), len(rows) - 1)
        return rows[self.row]

    def move(self, step):
        rows = self.rows()
        index = self.row + step
        while 0 <= index < len(rows) and rows[index][0] == 'head':
            index += step
        if 0 <= index < len(rows):
            self.row = index

    def focus(self, key):
        for index, row in enumerate(self.rows()):
            if row[4] == key:
                self.row = index
                return

    # ------------------------------------------------------------ changes

    def get(self, key):
        if key in NAMES:
            return self.state['s'][NAMES.index(key)]
        return self.state[key]

    def set(self, key, value):
        if key in NAMES:
            self.state['s'][NAMES.index(key)] = value
        elif key == 'theta':
            self.state['theta'] = stress.wrap(value)
        elif key == 'yield':
            if value < 0:
                raise ValueError('Yield strength is 0 (off) or positive')
            self.state['yield'] = value
        self.last_jump = None
        self.solve()

    def turn(self, step):
        self.state['theta'] = stress.wrap(round(self.state['theta'] + step, 6))
        self.last_jump = None
        self.solve()

    def jump(self, kind):
        st = self.state
        second = self.last_jump == kind
        if kind == 'p':
            st['theta'] = stress.principal_angle(st, second)
            a, b = _axis_names(st)
            if self.result['radius'] < 1e-9:
                self.say('Every direction is principal here')
            else:
                self.say("%s' on the %s principal axis" % (a, 'smaller' if second else 'larger'))
        else:
            st['theta'] = stress.shear_angle(st, second)
            self.say('Maximum in-plane shear axes')
        self.last_jump = None if second else kind
        self.solve()

    def set_mode(self, mode):
        self.state['mode'] = mode
        self.solve()
        self.focus('mode')
        self.say('3D: six stresses and a rotation axis' if mode == '3D' else '2D: plane stress, sz = 0')

    def next_axis(self):
        if self.state['mode'] != '3D':
            raise ValueError('2D turns about z: M switches to 3D')
        st = self.state
        st['axis'] = stress.AXES[(stress.AXES.index(st['axis']) + 1) % 3]
        st['theta'] = 0.0
        self.solve()
        self.say('Turning about ' + st['axis'])

    def example(self, index):
        name, values = EXAMPLES[index]
        for key in values:
            self.state[key] = list(values[key]) if key == 's' else values[key]
        self.state['theta'] = 0.0
        self.last_jump = None
        self.solve()
        self.say(name)

    def begin_edit(self, button=None):
        kind, label, value, editable, key, unit = self.current()
        if kind == 'head':
            return
        if not editable:
            raise ValueError('Worked out from the stresses')
        if key == 'mode':
            self.popup = ['Mode', MODE_NAMES, MODES.index(self.state['mode']), lambda i: self.set_mode(MODES[i])]
            return
        if key == 'axis':
            def choose(i):
                self.state['axis'] = stress.AXES[i]
                self.state['theta'] = 0.0
                self.solve()
            self.popup = ['Rotation axis', ('x', 'y', 'z'), stress.AXES.index(self.state['axis']), choose]
            return
        if button is None or erase_key(self.vm, button):
            self.edit = LineEdit(number(self.get(key), 7), 16)
            if button is not None:
                self.edit.key(self.vm, button)
        else:
            self.edit = LineEdit('', 16)
            self.edit.key(self.vm, button)

    def commit(self):
        key = self.current()[4]
        value = parse_number(self.edit.text)
        if abs(value) > 1e7:
            raise ValueError('Keep stresses under 1e7 MPa')
        self.set(key, value)
        self.edit = None

    # ------------------------------------------------------------ keys

    def run(self, button):
        if button == keys.BUTTON_NONE:
            return False
        try:
            self.handle(button)
        except (ValueError, TypeError, ZeroDivisionError, OverflowError) as exc:
            self.say(str(exc) or 'Not possible here', True)
        return True

    def handle(self, button):
        if button == keys.BUTTON_F9:
            self.help_open, self.help_first = not self.help_open, 0
            return
        esc = button == self.vm.input_manager._key_esc
        if self.help_open:
            self.key_help(button, esc)
            return
        if self.popup is not None:
            title, options, index, apply = self.popup
            if esc:
                self.popup = None
            elif button in (keys.BUTTON_UP, keys.BUTTON_DOWN):
                self.popup[2] = (index + (1 if button == keys.BUTTON_DOWN else -1)) % len(options)
            elif button == keys.BUTTON_CENTER:
                self.popup = None
                apply(index)
            return
        if self.edit is not None:
            result = self.edit.key(self.vm, button)
            if result == 'cancel':
                self.edit = None
            elif result is not None:
                self.commit()
                if result in ('up', 'down'):
                    self.move(-1 if result == 'up' else 1)
            return
        self.message, self.error = '', False
        if esc:
            self.vm.back()
            return
        c = self.vm.input_manager.button_to_char(button)
        c = c.lower() if c else ''
        row = self.current()
        typing = row[5] in ('MPa', 'deg')
        if button in (keys.BUTTON_UP, keys.BUTTON_DOWN):
            self.move(-1 if button == keys.BUTTON_UP else 1)
        elif button in (keys.BUTTON_LEFT, keys.BUTTON_RIGHT):
            self.turn(1.0 if button == keys.BUTTON_RIGHT else -1.0)
        elif button == keys.BUTTON_CENTER:
            self.begin_edit()
        elif button == keys.BUTTON_F3:
            self.popup = ['Examples', tuple(name for name, _ in EXAMPLES), 0, self.example]
        elif c == '?':
            self.help_open, self.help_first = True, 0
        elif c in ('[', ']'):
            self.turn(15.0 if c == ']' else -15.0)
        elif c in ('p', 's'):
            self.jump(c)
        elif c == 'r':
            self.state['theta'] = 0.0
            self.last_jump = None
            self.solve()
        elif c == 'm':
            self.set_mode('2D' if self.state['mode'] == '3D' else '3D')
        elif c == 'a':
            self.next_axis()
        elif typing and ((c and (c.isdigit() or c in '-.(')) or erase_key(self.vm, button)):
            self.begin_edit(button)

    def key_help(self, button, esc):
        if esc or button == keys.BUTTON_CENTER:
            self.help_open = False
            return
        capacity = help_capacity(int(self.vm.draw.size.y) - FOOT)
        last = max(0, len(HELP) - capacity)
        if button in (keys.BUTTON_UP, keys.BUTTON_DOWN):
            self.help_first += 1 if button == keys.BUTTON_DOWN else -1
        elif button in (keys.BUTTON_LEFT, keys.BUTTON_RIGHT):
            self.help_first += capacity if button == keys.BUTTON_RIGHT else -capacity
        self.help_first = min(max(self.help_first, 0), last)

    # ------------------------------------------------------------ drawing

    def properties_rect(self):
        size = self.vm.draw.size
        return (8, PROPERTIES_TOP, int(size.x) - 16, int(size.y) - FOOT - PROPERTIES_TOP - 3)

    def draw(self):
        draw = self.vm.draw
        p = self.palette()
        bottom = int(draw.size.y) - FOOT
        draw.fill_screen(p.BG)
        if self.help_open:
            chrome(draw, p, 'Help', title=TITLE, fallback=PATH)
            help_box(draw, p, HELP, self.help_first, bottom)
            draw.swap()
            return
        st, r = self.state, self.result
        a, b = _axis_names(st)
        status = '%s  theta %s deg' % (st['mode'], number(st['theta'], 4))
        panel(draw, p, PREVIEW, 'STRESS AT A POINT', status, p.PANEL)
        pp = theme.colors(p.PANEL, p.TEXT, p.ACCENT)
        circles(Viewport(draw, CIRCLE_BOX), pp, st, r)
        draw._line(170, 65, 170, 156, p.GRID)
        element(Viewport(draw, ELEMENT_BOX), pp, st, r)
        line = Viewport(draw, (16, 160, 304, 182))
        if st['mode'] == '3D':
            summary = 's1 %s  s2 %s  s3 %s  tmax %s' % (number(r['s1'], 3), number(r['s2'], 3),
                                                      number(r['s3'], 3), number(r['tmax'], 3))
        else:
            summary = 's1 %s  s2 %s  tmax %s  thp %s' % (number(r['p1'], 3), number(r['p2'], 3),
                                                       number(r['radius'], 3), number(r['angle'], 3))
        text(line, 16, 165, summary + '  MPa', p.MUTED)
        rect = self.properties_rect()
        rows = self.rows()
        self.row = min(self.row, len(rows) - 1)
        panel(draw, p, rect, 'PROPERTIES', '%d/%d' % (self.row + 1, len(rows)))
        form(draw, p, [row[:4] for row in rows], self.row, self.edit, PROPERTIES_TOP + 26, rect[1] + rect[3] - 5)
        chrome(draw, p, st['mode'] + ' about ' + stress.axis(st), self.message, self.error, title=TITLE,
               fallback=PATH)
        if self.popup is not None:
            title, options, index, apply = self.popup
            popup(draw, p, title, options, index, rect)
        draw.swap()


# ---------------------------------------------------------------- pictures

def _arrow(draw, x1, y1, x2, y2, color):
    draw._line(int(x1), int(y1), int(x2), int(y2), color)
    dx, dy = x2 - x1, y2 - y1
    length = sqrt(dx * dx + dy * dy)
    if length < 1:
        return
    ux, uy = dx / length, dy / length
    size = 4
    bx, by = x2 - ux * size, y2 - uy * size
    vx, vy = -uy * (size - 1), ux * (size - 1)
    draw._fill_triangle(int(x2), int(y2), int(bx + vx), int(by + vy), int(bx - vx), int(by - vy), color)


def circles(draw, p, state, r):
    """Mohr's circles to scale, sigma to the right and tau positive down."""
    left, top, right, bottom = CIRCLE_BOX
    left, right, top, bottom = left + 4, right - 6, top + 4, bottom - 10
    if state['mode'] == '3D':
        s1, s2, s3 = r['s1'], r['s2'], r['s3']
        rings = (((s1 + s3) / 2, (s1 - s3) / 2), ((s1 + s2) / 2, (s1 - s2) / 2), ((s2 + s3) / 2, (s2 - s3) / 2))
    else:
        rings = ()
    centre, radius = r['centre'], r['radius']
    lo = min([0.0, centre - radius] + [c - q for c, q in rings])
    hi = max([0.0, centre + radius] + [c + q for c, q in rings])
    tau = max([radius] + [q for c, q in rings])
    span = hi - lo
    if span < 1e-9:
        lo, hi, span, tau = -1.0, 1.0, 2.0, 1.0
    scale = min((right - left) / span, (bottom - top) / (2 * tau if tau > 1e-9 else span))
    cx = (left + right) / 2 - (lo + hi) / 2 * scale
    cy = (top + bottom) / 2

    def X(s):
        return int(cx + s * scale + 0.5)

    def Y(t):
        return int(cy + t * scale + 0.5)
    if rings:
        # Every plane's (sigma, tau) lies in the band inside the big circle
        # and outside the two small ones.
        band = mix(p.BG, p.TEXT, 1, 5)
        big, one, two = rings
        draw._fill_circle(X(big[0]), Y(0), max(1, int(big[1] * scale + 0.5)), band)
        for c, q in (one, two):
            if q * scale >= 1:
                draw._fill_circle(X(c), Y(0), int(q * scale + 0.5), p.BG)
    draw._line(left - 4, Y(0), right + 4, Y(0), p.GRID)
    draw._line(X(0), top - 4, X(0), bottom + 4, p.GRID)
    text(draw, right - 2, Y(0) - 9, 's', p.MUTED)
    text(draw, X(0) + 3, bottom - 2, 't', p.MUTED)
    for c, q in rings:
        if q * scale >= 1:
            draw._circle(X(c), Y(0), int(q * scale + 0.5), p.TEXT)
    if radius * scale >= 1:
        draw._circle(X(centre), Y(0), int(radius * scale + 0.5), p.ACCENT)
    # Rotated faces: X' (si, tij) and Y' (sj, -tij) on a diameter.
    xi, yi = X(r['si']), Y(r['tij'])
    xj, yj = X(r['sj']), Y(-r['tij'])
    draw._line(xi, yi, xj, yj, p.MUTED)
    draw._fill_circle(X(centre), Y(0), 1, p.MUTED)
    draw._fill_circle(xj, yj, 3, theme.AMBER)
    draw._fill_circle(xi, yi, 3, p.ACCENT)
    a, b = _axis_names(state)
    # Labels sit outside the circle, away from the centre.
    for x, y, label, color in ((xi, yi, a.upper() + "'", p.ACCENT), (xj, yj, b.upper() + "'", theme.AMBER)):
        lx = x + 5 if x >= X(centre) else x - 5 - draw.len(label, XS)
        text(draw, lx, y - 9 if y <= cy else y + 1, label, color)
    # Principal stresses on the sigma axis.
    marks = (r['s1'], r['s2'], r['s3']) if rings else (r['p1'], r['p2'])
    for s in marks:
        draw._line(X(s), Y(0) - 2, X(s), Y(0) + 2, p.TEXT)


def element(draw, p, state, r):
    """The element turned by theta, looking down the rotation axis, with
    normal and shear stress arrows scaled to the largest stress."""
    left, top, right, bottom = ELEMENT_BOX
    cx, cy = (left + right) // 2, (top + bottom) // 2 + 2
    a, b = _axis_names(state)
    # Fixed axes, dim.
    draw._line(cx, cy, cx + 44, cy, p.GRID)
    draw._line(cx, cy, cx, cy - 36, p.GRID)
    text(draw, cx + 39, cy + 2, a, p.MUTED)
    text(draw, cx + 4, cy - 36, b, p.MUTED)
    text(draw, left + 4, top + 1, 'along ' + stress.axis(state), p.MUTED)
    t = radians(state['theta'])
    c, s = cos(t), sin(t)
    half = 14

    def at(u, v):
        return cx + u * c - v * s, cy - (u * s + v * c)
    corners = [at(-half, -half), at(half, -half), at(half, half), at(-half, half)]
    fill = mix(p.PANEL, p.TEXT, 1, 5)
    x0, y0 = corners[0]
    for k in (1, 2):
        x1, y1 = corners[k]
        x2, y2 = corners[k + 1]
        draw._fill_triangle(int(x0), int(y0), int(x1), int(y1), int(x2), int(y2), fill)
    for k in range(4):
        x1, y1 = corners[k]
        x2, y2 = corners[(k + 1) % 4]
        draw._line(int(x1), int(y1), int(x2), int(y2), p.TEXT)
    peak = max(abs(r['si']), abs(r['sj']), abs(r['tij']))
    if peak < 1e-9:
        centre_text(draw, cx, bottom - 12, 'no stress', p.MUTED, XS, left, right)
        return

    def size(v):
        return 4 + 14 * abs(v) / peak
    # Faces +u (X', accent) and +v (Y', amber) and their opposites.
    for (nu, nv), sigma, color in (((1, 0), r['si'], p.ACCENT), ((0, 1), r['sj'], theme.AMBER)):
        for sign in (1, -1):
            mu, mv = nu * sign * half, nv * sign * half
            fx, fy = at(mu, mv)
            ux, uy = at(mu + nu * sign, mv + nv * sign)
            ux, uy = ux - fx, uy - fy
            if abs(sigma) > 1e-9 * peak:
                L = size(sigma)
                if sigma > 0:
                    _arrow(draw, fx + ux * 2, fy + uy * 2, fx + ux * (2 + L), fy + uy * (2 + L), color)
                else:
                    _arrow(draw, fx + ux * (2 + L), fy + uy * (2 + L), fx + ux * 2, fy + uy * 2, color)
            tau = r['tij']
            if abs(tau) > 1e-9 * peak:
                # Shear on the +u face acts along +v when positive; on the
                # +v face along +u; opposite faces reverse.
                tu, tv = (nv, nu)
                L = size(tau) * 0.8
                d = sign * (1 if tau > 0 else -1)
                gx, gy = at(mu + nu * sign * 4, mv + nv * sign * 4)
                ex, ey = at(mu + nu * sign * 4 + tu * d * L / 2, mv + nv * sign * 4 + tv * d * L / 2)
                sx, sy = 2 * gx - ex, 2 * gy - ey
                _arrow(draw, sx, sy, ex, ey, p.TEXT)
    text(draw, left + 4, bottom - 9, "%s' %s" % (a, number(r['si'], 3)), p.ACCENT)
    right_text(draw, right - 4, bottom - 9, "%s' %s" % (b, number(r['sj'], 3)), theme.AMBER)


class MohrView:
    def __init__(self):
        self.app = None

    def start(self, vm):
        global _active
        self.app = _active = Mohr(vm)
        vm.input_manager.reset()
        self.app.draw()
        return True

    def run(self, vm):
        if self.app is not None and self.app.run(vm.button) and self.app is not None:
            self.app.draw()

    def stop(self, vm):
        global _active
        if self.app is not None:
            self.app.keep()
        self.app = _active = None
        from gc import collect
        collect()


def show(vm):
    from engtools.plots.view import open_view
    return open_view(vm, 'mohr_view', MohrView())
