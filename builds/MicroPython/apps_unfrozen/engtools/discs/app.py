"""Shrink fit in PicoLAB: rotating discs, thick cylinders and interference
fits between concentric bodies.

The keys follow Beam view: F1 Add, F2 Remove, F3 Options, F4 Plot,
F5 Results, and F6 moves to the preview (orbit, zoom, change view). Any
N-1 of the speed, pressures, interferences and contact pressures can be
marked Find (SPACE); the rest are given. The model stays in RAM while
PicoLAB runs; saving to the SD card is explicit.
"""
from math import pi
from picoware.system import buttons as keys
from picoware.system.font import FONT_SMALL as SM
from engtools.ui import theme
from engtools.ui.forms import LineEdit, parse_number, erase_key
from engtools.ui.lab import (text, right_text, panel, chrome, form, popup, prompt, menu, results, tabs,
                             help_capacity, help_box, wrap, Viewport, FOOT)
from engtools import units, cases
from . import model as dm
from . import draw as dd

TITLE = 'SHRINK FIT'
PATH = ('modules', 'structural', 'Shrink fit')
PREVIEW = (8, 43, 304, 184)
LIST_TOP = 230
SKETCH = (14, 60, 306, 224)
TABS = ('Bodies', 'Loads', 'Fits')
UNDO_LIMIT = 12
OPTIONS = tuple('New: ' + name for name, _ in dm.TEMPLATES) + ('Save', 'Open', 'Conventions and keys')
UNITS = {'r': 'mm', 't': 'mm', 'E': 'GPa', 'nu': '', 'rho': 'kg/m3', 'alpha': 'um/mK', 'Sy': 'MPa', 'mu': ''}
LABELS = {'t': 'Thickness', 'E': "Young's modulus", 'nu': 'Poisson ratio', 'rho': 'Density',
          'alpha': 'Expansion coeff.', 'Sy': 'Yield strength', 'mu': 'Friction coeff.'}
PLANES = ('stress', 'strain')
PLANE_NAMES = ('Thin discs (plane stress)', 'Long cylinders (plane strain)')
HELP = (
    'Values: given or found:',
    'Speed, pressures, interferences and',
    'contact pressures are each Given or',
    'Find. SPACE switches the selected one.',
    'With N bodies mark N-1 of them Find:',
    '1 body: none; 2 bodies: one; ...',
    'Examples with a shaft in a hub:',
    '  interference given -> find contact',
    '  contact given -> find interference',
    '  contact 0 given -> find the speed',
    '    at which the fit comes loose',
    'Main keys:',
    'F1 Add  F2 Remove  F3 Options',
    'F4 Plot  F5 Results  F6 Refresh',
    'F9 help  Z undo (12 steps)',
    'I shows/hides the result summary',
    'V switches section / 3D view',
    'TAB preview / list; SPACE Move / Orbit',
    'Section preview: arrows move the view',
    'ESC returns; from the list leaves',
    'Lists:',
    'LEFT/RIGHT Bodies / Loads / Fits',
    'UP/DOWN choose  ENTER edit or choose',
    'Type a number to replace a value',
    'Arithmetic works: 50/2, 3000*1.1',
    'ENTER/TAB apply  ESC cancel',
    'Bodies:',
    'Listed from the centre outward',
    'Inner radius 0 makes body 1 solid',
    'Each outer radius is the next inner',
    'Editing E, nu, ... sets Custom',
    'F1 adds a ring outside or a shaft',
    'or ring inside; F2 removes a body',
    'Preview (TAB):',
    'Outline turns accent while active',
    'LEFT/RIGHT turn, UP/DOWN tilt (3D)',
    'Section arrows move the view',
    '+/- zoom  V or ENTER switch view',
    'R resets the view  TAB/ESC back',
    'Plot (F4):',
    'LEFT/RIGHT move  , / . to boundaries',
    'D third panel: von Mises, u, sz',
    'ESC returns',
    'Results (F5):',
    'UP/DOWN browse  ENTER plots a body',
    'Conventions:',
    'Tension +; pressures act inward on',
    'their surface; contact pressure +',
    'Interference on the diameter, um',
    'u radial displacement, + outward',
    'Thin discs: sz = 0 (plane stress)',
    'Long cylinders: ends held, sz =',
    '  nu (sr + st) (plane strain)',
    'Same speed for every body',
    'Torque/axial force: friction x',
    '  contact over the shorter body',
    'Heating: outer part warmed to open',
    '  the interference (no clearance)',
    'Lame thick-cylinder theory',
)

_active = None


def _fmt(value, unit, digits=4):
    return units.number(units.from_si(value, unit), digits) + (' ' + unit if unit else '')


class Discs:
    def __init__(self, vm):
        self.vm = vm
        from engtools import session
        kept = session.kept.get('discs') or {}
        self.model = kept.get('model') or dm.template(0)
        self.view = kept.get('view', 'section')
        self.yaw, self.pitch, self.zoom = kept.get('orbit', (30.0, 35.0, 1.0))
        self.page = 'model'
        self.tab = 0
        self.rows_at = [0, 0, 0]
        self.edit = None
        self.popup = None
        self.prompt = None
        self.message, self.error = '', False
        self.focus = 'list'
        self.navigation, self.pan = 'Orbit', [0, 0]
        self.info = False
        self.help_open, self.help_first = False, 0
        self.undo = []
        self.menu_index = 0
        self.files = []
        self.confirm = None
        self.third = 'vm'
        self.cursor = 0.0
        self.solution, self.problem = None, None
        self.resolve()

    # ------------------------------------------------------------ state

    def keep(self):
        from engtools import session
        session.kept['discs'] = {'model': self.model, 'view': self.view,
                                 'orbit': (self.yaw, self.pitch, self.zoom)}

    def palette(self):
        return theme.system_palette(self.vm)

    def say(self, message, error=False):
        self.message, self.error = message, error

    def snapshot(self):
        self.undo.append(dm.copy(self.model))
        if len(self.undo) > UNDO_LIMIT:
            del self.undo[0]

    def resolve(self):
        self.solution, self.problem = None, None
        try:
            self.solution = dm.Solution(self.model)
        except dm.ModelError as exc:
            self.problem = str(exc)
        except (ZeroDivisionError, OverflowError, ValueError):
            self.problem = 'These values have no solution'
        r = self.model['radii']
        self.cursor = min(max(self.cursor, r[0] * 1e3), r[-1] * 1e3)

    def replace_model(self, model):
        self.model = model
        self.rows_at = [0, 0, 0]
        self.resolve()

    # ------------------------------------------------------------ rows

    def var_text(self, key, unit):
        v = dm.get_var(self.model, key)
        if not v['find']:
            return _fmt(v['v'], unit)
        if self.solution is None:
            return '? (find)'
        return _fmt(self.solution.value(key), unit) + ' (find)'

    def speed_unit(self):
        return 'rpm' if self.model.get('rpm', True) else 'rad/s'

    def rows(self, tab=None):
        """(kind, label, value text, editable, key, unit)"""
        m = self.model
        tab = self.tab if tab is None else tab
        out = []
        if tab == 0:
            R = m['radii']
            for k, b in enumerate(m['bodies']):
                name = dm.MATERIALS[b['material']][0]
                out.append(('head', 'Body %d  %s' % (k + 1, name), '', False, ('body', k), None))
                if k == 0:
                    out.append(('field', 'Inner radius' + (' (solid)' if R[0] == 0 else ''), _fmt(R[0], 'mm'),
                                True, ('r', 0), 'mm'))
                out.append(('field', 'Outer radius', _fmt(R[k + 1], 'mm'), True, ('r', k + 1), 'mm'))
                out.append(('field', 'Thickness', _fmt(b['t'], 'mm'), True, ('t', k), 'mm'))
                out.append(('field', 'Material', name, True, ('mat', k), 'choice'))
                for prop in dm.PROPS:
                    unit = UNITS[prop]
                    value = units.number(b[prop], 3) if prop == 'nu' else _fmt(b[prop], unit, 4)
                    out.append(('field', LABELS[prop], value, True, (prop, k), unit))
        elif tab == 1:
            out.append(('head', 'Rotation and pressures', '', False, ('loads',), None))
            out.append(('field', 'Speed', self.var_text('speed', self.speed_unit()), True, ('var', 'speed'),
                        self.speed_unit()))
            out.append(('field', 'Inner pressure Pi', self.var_text('Pi', 'MPa') if m['radii'][0] > 0 else 'none (solid)',
                        m['radii'][0] > 0, ('var', 'Pi'), 'MPa'))
            out.append(('field', 'Outer pressure Po', self.var_text('Po', 'MPa'), True, ('var', 'Po'), 'MPa'))
            out.append(('head', 'Analysis', '', False, ('analysis',), None))
            out.append(('field', 'Model', PLANE_NAMES[PLANES.index(m['plane'])], True, ('plane',), 'choice'))
            out.append(('field', 'Speed unit', self.speed_unit(), True, ('rpm',), 'choice'))
        else:
            sol = self.solution
            for j, f in enumerate(m['fits']):
                r = m['radii'][j + 1]
                out.append(('head', 'Fit %d  B%d/B%d  d %s mm' % (j + 1, j + 1, j + 2, units.number(2e3 * r, 4)), '',
                            False, ('fit', j), None))
                out.append(('field', 'Interference (dia.)', self.var_text(('delta', j), 'um'), True,
                            ('var', ('delta', j)), 'um'))
                out.append(('field', 'Contact pressure', self.var_text(('pc', j), 'MPa'), True, ('var', ('pc', j)),
                            'MPa'))
                out.append(('field', 'Friction coeff.', units.number(f['mu'], 3), True, ('mu', j), ''))
                if sol is not None:
                    T, F = sol.torque(j)
                    out.append(('field', 'Holding torque', _fmt(max(T, 0.0), 'Nm', 3), False, None, ''))
                    out.append(('field', 'Axial holding force', _fmt(max(F, 0.0), 'kN', 3), False, None, ''))
                    heat = sol.heating(j)
                    out.append(('field', 'Heat outer part by', '--' if heat is None else _fmt(heat, 'K', 3), False,
                                None, ''))
        return out

    def row(self):
        rows = self.rows()
        if not rows:
            return None
        i = min(max(self.rows_at[self.tab], 0), len(rows) - 1)
        self.rows_at[self.tab] = i
        return rows[i]

    def selected(self):
        """('body', k), ('fit', j) or None for the current row."""
        rows = self.rows()
        i = self.rows_at[self.tab]
        for index in range(min(i, len(rows) - 1), -1, -1):
            key = rows[index][4]
            if rows[index][0] == 'head' and key and key[0] in ('body', 'fit'):
                return key
        return None

    def move(self, step):
        rows = self.rows()
        if rows:
            self.rows_at[self.tab] = min(max(self.rows_at[self.tab] + step, 0), len(rows) - 1)

    def focus_key(self, key):
        for i, row in enumerate(self.rows()):
            if row[4] == key:
                self.rows_at[self.tab] = i
                return

    # ------------------------------------------------------------ changes

    def number_of(self, key):
        m = self.model
        kind = key[0]
        if kind == 'r':
            return m['radii'][key[1]]
        if kind == 'var':
            v = dm.get_var(m, key[1])
            if v['find'] and self.solution is not None:
                return self.solution.value(key[1])
            return v['v']
        if kind == 'mu':
            return m['fits'][key[1]]['mu']
        return m['bodies'][key[1]][kind]

    def set_number(self, key, unit, value):
        m = self.model
        kind = key[0]
        si = value if unit in ('', 'choice') else units.to_si(value, unit)
        if kind == 'r':
            if si < 0:
                raise ValueError('Radius cannot be negative')
            m['radii'][key[1]] = si
        elif kind == 'var':
            v = dm.get_var(m, key[1])
            if key[1] == 'speed' and si < 0:
                raise ValueError('Speed is a magnitude: type a positive value')
            v['v'], v['find'] = si, False
        elif kind == 'mu':
            if si < 0:
                raise ValueError('Friction cannot be negative')
            m['fits'][key[1]]['mu'] = si
        else:
            b = m['bodies'][key[1]]
            b[kind] = si
            if kind in dm.PROPS:
                b['material'] = len(dm.MATERIALS) - 1

    def toggle_find(self):
        row = self.row()
        if row is None or row[4] is None or row[4][0] != 'var':
            raise ValueError('SPACE switches Given/Find on speed, pressures and fits')
        if not row[3]:
            raise ValueError('A solid centre has no inner pressure')
        self.snapshot()
        v = dm.get_var(self.model, row[4][1])
        if not v['find']:
            v['find'] = True
        else:
            # Keep the found value as the given one.
            if self.solution is not None:
                v['v'] = self.solution.value(row[4][1])
            v['find'] = False
        self.resolve()
        self.say('Find: solved from the rest' if v['find'] else 'Given')

    def begin_edit(self, button=None):
        row = self.row()
        if row is None:
            raise ValueError('Nothing here: F1 adds')
        kind, label, value, editable, key, unit = row
        if kind == 'head':
            rows = self.rows()
            i = self.rows_at[self.tab]
            if i + 1 < len(rows) and rows[i + 1][0] == 'field':
                self.rows_at[self.tab] = i + 1
            return
        if not editable:
            raise ValueError('Worked out for you' if key is None else 'Not used here')
        if unit == 'choice':
            self.choose(key)
            return
        shown = units.from_si(self.number_of(key), unit) if unit else self.number_of(key)
        if button is None or erase_key(self.vm, button):
            self.edit = LineEdit(units.number(shown, 7), 16)
            if button is not None:
                self.edit.key(self.vm, button)
        else:
            self.edit = LineEdit('', 16)
            self.edit.key(self.vm, button)

    def choose(self, key):
        m = self.model
        if key[0] == 'mat':
            b = m['bodies'][key[1]]

            def apply(i):
                self.snapshot()
                dm.set_material(b, i)
                self.resolve()
            self.popup = ['Material', tuple(row[0] for row in dm.MATERIALS), b['material'], apply]
        elif key[0] == 'plane':
            def apply(i):
                self.snapshot()
                m['plane'] = PLANES[i]
                self.resolve()
            self.popup = ['Model', PLANE_NAMES, PLANES.index(m['plane']), apply]
        else:
            def apply(i):
                m['rpm'] = i == 0
            self.popup = ['Speed unit', ('rpm', 'rad/s'), 0 if m.get('rpm', True) else 1, apply]

    def commit(self):
        row = self.row()
        value = parse_number(self.edit.text)
        self.snapshot()
        try:
            self.set_number(row[4], row[5], value)
        except ValueError:
            self.undo.pop()
            raise
        self.edit = None
        self.resolve()

    def add(self):
        m = self.model
        if self.tab != 0:
            raise ValueError('Loads and fits are always listed: F1 adds bodies (Bodies tab)')
        if len(m['bodies']) >= dm.MAX_BODIES:
            raise ValueError('Up to %d bodies' % dm.MAX_BODIES)
        R = m['radii']
        options = ['Ring outside']
        if R[0] > 0:
            options += ['Solid shaft inside', 'Ring inside']

        def apply(i):
            self.snapshot()
            name = options[i]
            if name == 'Ring outside':
                step = max(R[-1] - R[-2], 0.005)
                R.append(R[-1] + step)
                m['bodies'].append(dm.body(m['bodies'][-1]['t'], m['bodies'][-1]['material']))
                m['fits'].append(dm.fit())
                k = len(m['bodies']) - 1
            else:
                R.insert(0, 0.0 if name == 'Solid shaft inside' else R[0] / 2)
                m['bodies'].insert(0, dm.body(m['bodies'][0]['t'], m['bodies'][0]['material']))
                m['fits'].insert(0, dm.fit())
                if R[0] == 0:
                    m['Pi'] = dm.var()
                k = 0
            self.resolve()
            self.focus_key(('body', k))
            self.say('Added: the new fit finds its contact pressure')
        self.popup = ['Add body', tuple(options), 0, apply]

    def remove(self):
        m = self.model
        sel = self.selected()
        if self.tab != 0 or sel is None or sel[0] != 'body':
            raise ValueError('Select a body (Bodies tab) to remove it')
        if len(m['bodies']) == 1:
            raise ValueError('The last body stays: F3 starts a new model')
        k = sel[1]
        self.snapshot()
        N = len(m['bodies'])
        del m['bodies'][k]
        if k == N - 1:
            del m['radii'][N]
            del m['fits'][N - 2]
        elif k == 0:
            del m['radii'][0]
            del m['fits'][0]
        else:
            del m['radii'][k + 1]
            del m['fits'][k]
        self.resolve()
        self.rows_at[0] = 0
        self.say('Removed body %d: Z undoes' % (k + 1))

    def undo_last(self):
        if not self.undo:
            raise ValueError('Nothing to undo')
        self.model = self.undo.pop()
        self.resolve()
        self.say('Undone')

    # ------------------------------------------------------------ keys

    def run(self, button):
        if button == keys.BUTTON_NONE:
            return False
        try:
            self.handle(button)
        except (ValueError, TypeError, ZeroDivisionError, OverflowError, RuntimeError, OSError, MemoryError) as exc:
            self.say(str(exc) or 'Not possible here', True)
        return True

    def char(self, button):
        c = self.vm.input_manager.button_to_char(button)
        return c.lower() if c else ''

    def handle(self, button):
        if button == keys.BUTTON_F9:
            self.help_open, self.help_first = not self.help_open, 0
            return
        esc = button == self.vm.input_manager._key_esc
        if self.help_open:
            self.key_help(button, esc)
            return
        if self.prompt is not None:
            result = self.prompt['edit'].key(self.vm, button)
            if result == 'cancel':
                self.prompt = None
            elif result == 'commit':
                try:
                    self.prompt['apply'](self.prompt['edit'].text)
                    self.prompt = None
                except ValueError as exc:
                    self.prompt['message'] = str(exc)
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
        page = {keys.BUTTON_F3: 'options', keys.BUTTON_F4: 'plot', keys.BUTTON_F5: 'results'}.get(button)
        if page:
            self.page, self.focus, self.menu_index = page, 'list', 0
            if page == 'plot' and self.solution is None:
                self.page = 'model'
                raise ValueError(self.problem or 'Nothing to plot')
            return
        if button == keys.BUTTON_F6:
            self.resolve()
            self.say('Refreshed')
            return
        if self.page == 'model' and button == keys.BUTTON_TAB:
            self.focus = 'list' if self.focus == 'preview' else 'preview'
            return
        if self.page == 'model' and button in (keys.BUTTON_F1, keys.BUTTON_F2):
            self.focus = 'list'
            self.add() if button == keys.BUTTON_F1 else self.remove()
            return
        getattr(self, 'key_' + self.page)(button, esc)

    def key_model(self, button, esc):
        c = self.char(button)
        if self.focus == 'preview':
            self.key_preview(button, esc, c)
            return
        if esc:
            self.vm.back()
            return
        row = self.row()
        if button in (keys.BUTTON_LEFT, keys.BUTTON_RIGHT):
            self.tab = (self.tab + (1 if button == keys.BUTTON_RIGHT else -1)) % len(TABS)
        elif button in (keys.BUTTON_UP, keys.BUTTON_DOWN):
            self.move(-1 if button == keys.BUTTON_UP else 1)
        elif button == keys.BUTTON_CENTER:
            self.begin_edit()
        elif button == keys.BUTTON_SPACE or c == ' ':
            self.toggle_find()
        elif c == 'z':
            self.undo_last()
        elif c == 'i':
            self.info = not self.info
        elif c == 'v':
            self.view = '3d' if self.view == 'section' else 'section'
        elif row is not None and row[0] == 'field' and row[5] not in ('choice', None) and row[3] and \
                ((c and (c.isdigit() or c in '-.(')) or erase_key(self.vm, button)):
            self.begin_edit(button)

    def key_preview(self, button, esc, c):
        if esc:
            self.focus = 'list'
        elif button == keys.BUTTON_CENTER or c == 'v':
            self.view = '3d' if self.view == 'section' else 'section'
        elif c in ('+', '='):
            self.zoom = min(self.zoom * 1.25, 4.0)
        elif c == '-':
            self.zoom = max(self.zoom / 1.25, 0.5)
        elif c == 'r':
            self.yaw, self.pitch, self.zoom = 30.0, 35.0, 1.0
            self.pan = [0, 0]
        elif button == keys.BUTTON_SPACE:
            if self.view == '3d':
                self.navigation = 'Move' if self.navigation == 'Orbit' else 'Orbit'
        elif (self.view == 'section' or self.navigation == 'Move') and button in (keys.BUTTON_LEFT, keys.BUTTON_RIGHT, keys.BUTTON_UP, keys.BUTTON_DOWN):
            self.pan[0] += 8*((button == keys.BUTTON_RIGHT)-(button == keys.BUTTON_LEFT))
            self.pan[1] += 8*((button == keys.BUTTON_DOWN)-(button == keys.BUTTON_UP))
        elif self.view == '3d' and button in (keys.BUTTON_LEFT, keys.BUTTON_RIGHT):
            self.yaw = (self.yaw + (15 if button == keys.BUTTON_RIGHT else -15)) % 360
        elif self.view == '3d' and button in (keys.BUTTON_UP, keys.BUTTON_DOWN):
            self.pitch = min(max(self.pitch + (10 if button == keys.BUTTON_UP else -10), -90), 90)

    def key_plot(self, button, esc):
        if esc:
            self.page = 'model'
            return
        c = self.char(button)
        R = [r * 1e3 for r in self.model['radii']]
        if button in (keys.BUTTON_LEFT, keys.BUTTON_RIGHT):
            step = (R[-1] - R[0]) / 100
            self.cursor = min(max(self.cursor + (step if button == keys.BUTTON_RIGHT else -step), R[0]), R[-1])
        elif c in (',', '.', '<', '>'):
            if c in ('.', '>'):
                later = [r for r in R if r > self.cursor + 1e-6]
                self.cursor = later[0] if later else R[-1]
            else:
                earlier = [r for r in R if r < self.cursor - 1e-6]
                self.cursor = earlier[-1] if earlier else R[0]
        elif c == 'd':
            order = ('vm', 'u', 'sz') if self.model['plane'] == 'strain' else ('vm', 'u')
            self.third = order[(order.index(self.third) + 1) % len(order)] if self.third in order else 'vm'

    def key_results(self, button, esc):
        if esc:
            self.page = 'model'
            return
        rows = self.result_rows()
        if button in (keys.BUTTON_UP, keys.BUTTON_DOWN):
            step = -1 if button == keys.BUTTON_UP else 1
            i = self.menu_index + step
            while 0 <= i < len(rows) and rows[i][1] is None and not rows[i][2]:
                i += step
            if 0 <= i < len(rows):
                self.menu_index = i
        elif button == keys.BUTTON_CENTER and rows:
            action = rows[min(self.menu_index, len(rows) - 1)][4]
            if action:
                self.cursor = action
                self.page = 'plot'

    def key_options(self, button, esc):
        if esc:
            self.page = 'model'
            return
        if button in (keys.BUTTON_UP, keys.BUTTON_DOWN):
            self.menu_index = (self.menu_index + (-1 if button == keys.BUTTON_UP else 1)) % len(OPTIONS)
        elif button == keys.BUTTON_CENTER:
            choice = OPTIONS[self.menu_index]
            if choice.startswith('New: '):
                self.snapshot()
                self.replace_model(dm.template(self.menu_index))
                self.page, self.tab = 'model', 0
                self.say(dm.TEMPLATES[self.menu_index][1] + ': Z undoes')
            elif choice == 'Save':
                self.ask_save()
            elif choice == 'Open':
                self.files = cases.list_cases(self.vm.storage)
                self.page, self.menu_index = 'open', 0
            else:
                self.help_open, self.help_first = True, 0

    def key_open(self, button, esc):
        if esc:
            self.page = 'options'
            return
        if button in (keys.BUTTON_UP, keys.BUTTON_DOWN) and self.files:
            self.menu_index = (self.menu_index + (-1 if button == keys.BUTTON_UP else 1)) % len(self.files)
        elif button == keys.BUTTON_CENTER and self.files:
            name = self.files[self.menu_index]
            model = cases.load_case(self.vm.storage, name, 'discs')
            model['name'] = name
            self.snapshot()
            self.replace_model(model)
            self.page = 'model'
            self.say('Opened ' + name)

    def ask_save(self):
        def apply(value):
            name = cases.clean_name(value)
            if name != self.model.get('name') and cases.exists(self.vm.storage, name) and self.confirm != name:
                self.confirm = name
                raise ValueError(name + ' exists: ENTER again replaces it')
            self.model['name'] = name
            cases.save_case(self.vm.storage, name, self.model)
            self.confirm = None
            self.say('Saved ' + name)
        self.confirm = None
        self.prompt = {'title': 'Save model as', 'detail': 'Saved to ' + cases.CASE_DIRECTORY + '.',
                       'edit': LineEdit(self.model.get('name') or 'fit-1', cases.NAME_LIMIT), 'apply': apply,
                       'message': ''}

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

    # ------------------------------------------------------------ results

    def summary(self):
        """Up to two lines over the preview: the problem, or the main results."""
        if self.problem is not None:
            return wrap(self.problem, 46)[:2], 'error'
        sol = self.solution
        warn = sol.warnings()
        if warn:
            return wrap(warn[0], 46)[:2], 'warn'
        worst = (0.0, 0, 0.0)
        for k in range(sol.N):
            hi, r = sol.peaks(k)['vm'][:2]
            if hi > worst[0]:
                worst = (hi, k, r)
        b = self.model['bodies'][worst[1]]
        safety = ('  SF %s' % units.number(b['Sy'] / 1e6 / worst[0], 3)) if worst[0] > 0 and b['Sy'] > 0 else ''
        first = 'max vM %s MPa  B%d at r %s mm%s' % (units.number(worst[0], 3), worst[1] + 1,
                                                     units.number(worst[2], 3), safety)
        if sol.N > 1:
            pcs = ', '.join(units.number(p / 1e6, 3) for p in sol.values['pc'])
            second = 'contact %s MPa' % pcs
        else:
            second = 'speed %s' % _fmt(sol.values['speed'], self.speed_unit())
        return [first, second], 'ok'

    def result_rows(self):
        """(label, value, detail, color, plot radius mm or None)"""
        sol = self.solution
        if sol is None:
            return [('Model problem', None, self.problem, None, None)]
        m = self.model
        rows = [('Values', None, '', None, None)]
        for key, label, v in dm.scalars(m):
            if key == 'Pi' and m['radii'][0] == 0:
                continue
            unit = {'speed': self.speed_unit(), 'Pi': 'MPa', 'Po': 'MPa'}.get(key) or \
                ('um' if key[0] == 'delta' else 'MPa')
            rows.append((label, _fmt(sol.value(key), unit), 'found' if v['find'] else 'given', None, None))
        for w in sol.warnings():
            rows.append(('Warning', '!', w, theme.AMBER, None))
        for k, b in enumerate(m['bodies']):
            pk = sol.peaks(k)
            rows.append(('Body %d  %s' % (k + 1, dm.MATERIALS[b['material']][0]), None, '', None, None))
            hi, r = pk['vm'][:2]
            safety = b['Sy'] / 1e6 / hi if hi > 0 and b['Sy'] > 0 else None
            rows.append(('Max von Mises', _fmt(hi * 1e6, 'MPa', 4), 'at r = %s mm  safety %s' % (
                units.number(r, 4), '--' if safety is None else units.number(safety, 3)),
                theme.ERROR if safety is not None and safety < 1 else None, r))
            for name, label in (('st', 'hoop'), ('sr', 'radial')):
                hi, rh, lo, rl = pk[name]
                rows.append(('Max %s stress' % label, _fmt(hi * 1e6, 'MPa', 4), 'at r = %s mm' % units.number(rh, 4),
                             None, rh))
                rows.append(('Min %s stress' % label, _fmt(lo * 1e6, 'MPa', 4), 'at r = %s mm' % units.number(rl, 4),
                             None, rl))
            hi, rh, lo, rl = pk['u']
            big = (hi, rh) if abs(hi) >= abs(lo) else (lo, rl)
            rows.append(('Radial displacement', _fmt(big[0] * 1e-3, 'um', 3), 'at r = %s mm' % units.number(big[1], 4),
                         None, big[1]))
        for j in range(len(m['fits'])):
            rows.append(('Fit %d  at d %s mm' % (j + 1, units.number(2e3 * m['radii'][j + 1], 4)), None, '', None, None))
            T, F = sol.torque(j)
            rows.append(('Holding torque', _fmt(max(T, 0.0), 'Nm', 3), 'axial force %s, friction %s' % (
                _fmt(max(F, 0.0), 'kN', 3), units.number(m['fits'][j]['mu'], 3)), None, None))
            heat = sol.heating(j)
            rows.append(('Assembly heating', '--' if heat is None else _fmt(heat, 'K', 3),
                         'outer part, to open the interference', None, None))
            loose = sol.loosening(j)
            rows.append(('Comes loose at', 'never' if loose is None else _fmt(loose, self.speed_unit(), 4),
                         'speed where contact pressure reaches 0', None, None))
        if sol.values['speed'] > 0 or m['speed']['find']:
            I, energy = sol.inertia()
            rows.append(('Rotor', None, '', None, None))
            rows.append(('Inertia', units.number(I, 4) + ' kgm2', 'about the axis, all bodies', None, None))
            rows.append(('Kinetic energy', _fmt(energy, 'kJ', 4), 'at the speed above', None, None))
        return rows

    # ------------------------------------------------------------ drawing

    def properties_rect(self):
        size = self.vm.draw.size
        return (8, LIST_TOP, int(size.x) - 16, int(size.y) - FOOT - LIST_TOP - 3)

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
        page = self.page
        hint = 'F9 Help'
        if page == 'model':
            sub = self.draw_model(draw, p)
            row = self.row()
            if not self.message and self.focus == 'list' and row and row[4] and row[4][0] == 'var':
                self.message = 'SPACE given/find'
        elif page in ('options', 'open'):
            if page == 'options':
                rows = [(o, dm.TEMPLATES[i][1] if i < len(dm.TEMPLATES) else '') for i, o in enumerate(OPTIONS)]
                sub = 'options'
            else:
                rows = [(name, 'ENTER opens; Z undoes') for name in self.files] or [('No saved models', '')]
                sub = 'open'
            menu(draw, p, rows, self.menu_index, sub.upper(), bottom)
        else:
            panel(draw, p, (8, 43, int(draw.size.x) - 16, bottom - 46), '' if page == 'plot' else 'RESULTS')
            bounded = Viewport(draw, (10, 44, int(draw.size.x) - 10, bottom - 5))
            if page == 'plot':
                sub = self.draw_plot(bounded, p, bottom)
            else:
                rows = self.result_rows()
                self.menu_index = min(self.menu_index, len(rows) - 1)
                if rows[self.menu_index][1] is None and not rows[self.menu_index][2] and len(rows) > 1:
                    self.menu_index += 1
                results(bounded, p, [r[:4] for r in rows], self.menu_index, 67, bottom - 7)
                sub = 'results'
        chrome(draw, p, sub, self.message, self.error, title=TITLE, fallback=PATH, hint=hint)
        if self.message == 'SPACE given/find':
            self.message = ''
        if self.popup is not None:
            title, options, index, apply = self.popup
            popup(draw, p, title, options, index, self.properties_rect() if page == 'model' else None)
        if self.prompt is not None:
            q = self.prompt
            prompt(draw, p, q['title'], q['detail'], q['edit'], q['message'] or 'ENTER saves  ESC cancels',
                   bool(q['message']))
        draw.swap()

    def draw_model(self, draw, p):
        m = self.model
        x, y, w, h = PREVIEW
        sel = self.selected()
        status = '%d bod%s  %s' % (len(m['bodies']), 'y' if len(m['bodies']) == 1 else 'ies',
                                   '3D' if self.view == '3d' else 'section')
        found = len(dm.finds(m))
        need = len(m['bodies']) - 1
        title = 'SECTION' if self.view == 'section' else 'WIREFRAME'
        panel(draw, p, PREVIEW, title + ('  find %d/%d' % (found, need) if need else ''), status, p.PANEL)
        if self.focus == 'preview':
            draw._rectangle(x, y, w, h, p.ACCENT)
            draw._rectangle(x + 1, y + 1, w - 2, h - 2, p.ACCENT)
        pp = theme.colors(p.PANEL, p.TEXT, p.ACCENT)
        pp.ERROR = p.ERROR
        sketch = Viewport(draw, SKETCH)
        try:
            if self.view == 'section':
                dd.section(sketch, pp, m, SKETCH, sel, self.zoom, self.pan)
            else:
                dd.wireframe(sketch, pp, m, SKETCH, self.yaw, self.pitch, self.zoom, sel, self.pan)
        except (ZeroDivisionError, ValueError):
            text(draw, 20, 120, 'Nothing to draw: check the radii', p.ERROR)
        lines, state = self.summary()
        if self.info or state != 'ok':
            top = y + h - 10 * len(lines) - 11
            color = p.ERROR if state == 'error' else theme.AMBER if state == 'warn' else p.GRID
            draw._fill_rectangle(x + 5, top, w - 10, 10 * len(lines) + 7, p.BG)
            draw._rectangle(x + 5, top, w - 10, 10 * len(lines) + 7, color)
            for i, line in enumerate(lines):
                text(draw, x + 10, top + 4 + 10 * i, line[:48], p.TEXT if state == 'ok' else color)
        elif self.focus == 'preview':
            right_text(draw, x + w - 8, y + h - 12, ('Move' if self.view == 'section' else self.navigation)+' / SPACE mode / +/- zoom', p.MUTED)
        else:
            right_text(draw, x + w - 8, y + h - 12, 'TAB preview  I results', p.MUTED)
        rect = self.properties_rect()
        rows = self.rows()
        counts = [len(m['bodies']), 3, len(m['fits'])]
        tabs(draw, p, rect, TABS, self.tab, counts)
        if self.focus == 'preview':
            draw._rectangle(rect[0], rect[1], rect[2], rect[3], p.GRID)
        if rows:
            index = min(self.rows_at[self.tab], len(rows) - 1)
            shown = [r[:4] for r in rows]
            if self.edit is not None:
                r = rows[index]
                shown[index] = (r[0], r[1], units.number(units.from_si(self.number_of(r[4]), r[5]), 7) + ' ' + r[5],
                                r[3])
            form(draw, p, shown, index if self.focus == 'list' else -1, self.edit, LIST_TOP + 25,
                 rect[1] + rect[3] - 5)
        else:
            text(draw, rect[0] + 10, rect[1] + 30, 'One body has no fits', p.MUTED)
            text(draw, rect[0] + 10, rect[1] + 44, 'Bodies tab: F1 adds a ring or shaft', p.MUTED)
        return 'model'

    def draw_plot(self, draw, p, bottom):
        sol = self.solution
        k = 0
        for i in range(sol.N):
            if sol.R[i] <= self.cursor:
                k = i
        values = sol.at(k, self.cursor)
        text(draw, 16, 47, 'Through the radius', p.TEXT, SM)
        right_text(draw, int(draw.size.x) - 16, 47, 'B%d  r %s mm' % (k + 1, units.number(self.cursor, 4)), p.ACCENT, SM)
        readout = 'sr %s  st %s  vM %s MPa  u %s um' % (units.number(values[0], 3), units.number(values[1], 3),
                                                     units.number(values[4], 3), units.number(values[3] * 1e3, 3))
        text(draw, 16, 60, readout[:48], p.TEXT)
        dd.plots(draw, p, sol, ('sr', 'st', self.third), self.cursor, bottom - 6)
        return 'plot'


class DiscsView:
    def __init__(self):
        self.app = None

    def start(self, vm):
        global _active
        self.app = _active = Discs(vm)
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
    return open_view(vm, 'discs_view', DiscsView())
