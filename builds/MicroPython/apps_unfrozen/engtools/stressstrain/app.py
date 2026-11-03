"""Keyboard-driven StressStrain first pass: sections and thermoelasticity."""
from math import sqrt, pi, sin, cos
from picoware.system import buttons as k
from picoware.system.font import FONT_SMALL as SM
from engtools import materials
from engtools.ui import theme
from engtools.ui.forms import LineEdit, parse_number, erase_key
from engtools.ui.lab import chrome, panel, text, right_text, form, menu, popup, prompt, results, Viewport
from engtools.ui.lab import tabs as draw_tabs
from engtools.ui.tool import Tabs, EquationHelp
from picoware.system.font import FONT_XTRA_SMALL as XS
from . import model
from .field import SectionField, KINDS, CRITICAL

TITLE = 'STRESS / STRAIN'
PATH = ('modules', 'structural', 'StressStrain')
MODES = ('section', 'constitutive')
MODE_NAMES = ('Section loads', 'Stress <-> strain')
OPTIONS = (('Examples', 'Sections, shear and thermal restraint'),
           ('Save case', 'Versioned inputs in SI'), ('Open case', 'Load a StressStrain calculation'),
           ('Export CSV', 'Stress and total strain, in SI'),
           ('Export stress state', 'SI JSON for future app exchange'),
           ('Assumptions / signs', 'Axes, shear and thermal conventions'))
HELP = ('Inputs:', 'UP/DOWN choose; ENTER edit or choose',
        'Type a number to replace; arithmetic works',
        'ENTER apply  ESC cancel  Z undo',
        'LEFT/RIGHT tabs; UP/DOWN selects a row',
        'Section tab: ENTER opens section view',
        'Section view: Geometry / Material / Properties',
        'Valid dimension drafts preview before ENTER',
        'ESC cancels an edit, then returns to inputs',
        'Mode / material: ENTER on their fields',
        'F3 files, examples and assumptions',
        'F4 stress map / tensor view', 'F5 results  F6 calculate  F9 help',
        'Section view:', 'Arrows move the point by 5% of size',
        'P cycles edge points and centre', 'Probe movement updates calculated results',
        'F7 cycles sx / shear / von Mises maps',
        'F8 jumps through four critical points',
        'Max/min sx: exact within the section model',
        'Shear / von Mises maxima: sampled estimates',
        'Shear map is resultant sqrt(txy^2+txz^2)',
        'Map colours show stress, not yield status',
        'Custom sections have no map or extrema',
        'Axes and signs:', 'x along member; y right; z up',
        'Tension is positive; moments right-hand',
        'Rectangular shear is breadth-averaged',
        'Custom sections: principal y/z axes',
        'Strains:', 'ex/ey/ez are total normal strains',
        'gxy/gyz/gzx are engineering shear',
        'Plane stress: sz=tyz=tzx=0',
        'Plane strain: ez=gyz=gzx=0',
        'Section thermal expansion is free',
        'Material examples are editable inputs',
        'Model: small-strain isotropic elasticity',
        'Rosettes, plastic curves and meshes later')
_active = None


def shown(value):
    return '0' if value == 0 else '%.6g' % value


def coordinate(value, extent):
    # Trigonometric samples can leave negligible float32 residues at axes.
    return shown(0 if abs(value) < extent*1e-6 else value*1000)


class StressStrain:
    def __init__(self, vm):
        self.vm = vm
        from engtools import session
        self.state = model.copy(session.kept.get(model.TOOL) or model.new_state())
        self.page, self.row, self.index = 'model', 0, 0
        self.preview_focus = False
        self.edit, self.choice, self.dialog = None, None, None
        self.solution = None
        self.section_map, self.map_cache = None, None
        self.map_kind, self.critical_index = 0, -1
        self.message, self.error = 'F6 calculates this case', False
        self.undo, self.files = [], []
        self.tabs = Tabs(('Analysis', 'Section', 'Loads'))
        self.tabs.index = 1 if self.state['mode'] == 'section' else 0
        self.section_tabs = Tabs(('Geometry', 'Material', 'Properties'))
        self.section_row, self.section_return_row = 0, 0
        self.help_view = EquationHelp()

    def say(self, message, error=False):
        self.message, self.error = message, error

    def changed(self, state, probe=False):
        calculated = self.solution is not None
        self.undo.append(model.copy(self.state))
        del self.undo[:-8]
        self.state, self.solution = state, None
        self.critical_index = -1
        if not probe:
            self.section_map, self.map_cache = None, None
        if probe and calculated:
            self.solution = model.solve(state)
            self.say('Probe updated')
            return
        self.say('Changed; F6 calculates')

    def value(self, path):
        value = self.state
        for key in path:
            value = value[key]
        return value

    def numeric(self, label, path, unit='', scale=1):
        return ('field', label, shown(self.value(path)/scale) + (' '+unit if unit else ''), True, path, unit, scale)

    def all_rows(self):
        s = self.state
        rows = [('field', 'Analysis', MODE_NAMES[MODES.index(s['mode'])], True, ('mode',), 'choice', 1)]
        f = self.numeric
        if s['mode'] == 'section':
            rows += [('head', 'Section / evaluation point', '', False, None, '', 1),
                     ('field', 'Shape', model.SHAPE_NAMES[model.SHAPES.index(s['shape'])], True, ('shape',), 'choice', 1)]
            shape = s['shape']
            if shape in ('circle', 'tube'):
                rows.append(f('Outer diameter', ('section', 'd'), 'mm', .001))
                if shape == 'tube':
                    rows.append(f('Inner diameter', ('section', 'di'), 'mm', .001))
            elif shape == 'rectangle':
                rows += [f('Width along y', ('section', 'b'), 'mm', .001), f('Height along z', ('section', 'h'), 'mm', .001)]
            else:
                rows += [f('Area', ('section', 'A'), 'mm2', 1e-6),
                         f('Inertia about y', ('section', 'Iy'), 'mm4', 1e-12),
                         f('Inertia about z', ('section', 'Iz'), 'mm4', 1e-12)]
            rows += [f('Point y', ('point', 'y'), 'mm', .001), f('Point z', ('point', 'z'), 'mm', .001),
                     ('head', 'Loads on the +x cut face', '', False, None, '', 1)]
            for key, label, unit, scale in (('N', 'Axial N', 'kN', 1000), ('My', 'Bending My', 'Nm', 1),
                                           ('Mz', 'Bending Mz', 'Nm', 1), ('T', 'Torque T', 'Nm', 1),
                                           ('Vy', 'Shear Vy', 'kN', 1000), ('Vz', 'Shear Vz', 'kN', 1000)):
                rows.append(f(label, ('loads', key), unit, scale))
        else:
            rows += [('field', 'Condition', model.CONDITION_NAMES[model.CONDITIONS.index(s['condition'])], True, ('condition',), 'choice', 1),
                     ('field', 'Given', 'Stress -> strain' if s['direction'] == 'stress' else 'Strain -> stress', True, ('direction',), 'choice', 1),
                     ('head', 'Stress inputs' if s['direction'] == 'stress' else 'Total strain inputs', '', False, None, '', 1)]
            stress = s['direction'] == 'stress'
            names = model.STRESSES if stress else model.STRAINS
            for i in (range(6) if s['condition'] == '3d' else (0, 1, 3)):
                rows.append(f(names[i], ('stress' if stress else 'strain', i), 'MPa' if stress else 'ue', 1e6 if stress else 1e-6))
        rows += [('head', 'Isotropic material / temperature', '', False, None, '', 1),
                 ('field', 'Material', s['material']['name'], True, ('material',), 'choice', 1),
                 f('Young modulus E', ('material', 'E'), 'GPa', 1e9),
                 f('Poisson ratio nu', ('material', 'nu')),
                 f('Expansion alpha', ('material', 'alpha'), 'um/mK', 1e-6),
                 f('Yield (0 = off)', ('material', 'yield'), 'MPa', 1e6),
                 f('Temperature change', ('dt',), 'K', 1)]
        return rows

    def rows(self):
        if self.page == 'section':
            return self.section_rows()
        self.tabs.configure(('Analysis', 'Section', 'Loads') if self.state['mode'] == 'section' else ('Analysis', 'Inputs', 'Material'))
        if self.state['mode'] == 'section' and self.tabs.label == 'Section':
            return [('field', 'Section + material', model.SHAPE_NAMES[model.SHAPES.index(self.state['shape'])],
                     True, ('section_editor',), 'action', 1),
                    self.numeric('Point y', ('point', 'y'), 'mm', .001),
                    self.numeric('Point z', ('point', 'z'), 'mm', .001)]
        def group(path):
            if path[0] in ('mode', 'condition', 'direction'):
                return 'Analysis'
            if path[0] in ('shape', 'section', 'point'):
                return 'Section'
            if path[0] == 'loads':
                return 'Loads'
            return 'Material' if path[0] in ('material', 'dt') else 'Inputs'
        return [r for r in self.all_rows() if r[4] is not None and group(r[4]) == self.tabs.label]

    def section_rows(self):
        if self.section_tabs.label == 'Properties':
            try:
                props = model.section(self.state)
                values = [(key, shown(props[key]/(1e-6 if key == 'A' else 1e-12))+(' mm2' if key == 'A' else ' mm4') if props[key] is not None else '--') for key in ('A', 'Iy', 'Iz', 'J')]
                values.append(('G', shown(self.state['material']['E']/(2*(1+self.state['material']['nu']))/1e9)+' GPa'))
            except (ValueError, ZeroDivisionError, OverflowError):
                values = [('Invalid section', 'Check geometry')]
            return [('field', key, value, False, ('property', key), '', 1) for key, value in values]
        keys = ('shape', 'section') if self.section_tabs.label == 'Geometry' else ('material', 'dt')
        return [r for r in self.all_rows() if r[4] is not None and r[4][0] in keys]

    def open_section(self, material=False):
        if self.page != 'section':
            self.section_return_row = self.row
            self.page, self.row = 'section', self.section_row
            self.row = min(self.row, len(self.rows())-1)
        if material:
            self.switch_tab(self.section_tabs.labels.index('Material')-self.section_tabs.index)
            self.row = 0

    def close_section(self):
        if self.page == 'section':
            self.section_row = self.row
            self.page, self.row = 'model', self.section_return_row

    def switch_tab(self, step):
        rows = self.rows()
        path = rows[min(self.row, len(rows)-1)][4]
        tabs = self.section_tabs if self.page == 'section' else self.tabs
        target = tabs.switch(step, path)
        self.row = next((i for i, r in enumerate(self.rows()) if r[4] == target), 0)

    def select_tab(self, label):
        self.close_section()
        self.rows()
        self.switch_tab(self.tabs.labels.index(label)-self.tabs.index)

    def move(self, step):
        rows = self.rows()
        index = self.row+step
        while 0 <= index < len(rows) and rows[index][0] == 'head':
            index += step
        if 0 <= index < len(rows):
            self.row = index

    def choose(self, path, index):
        s = model.copy(self.state)
        if path == ('mode',):
            s['mode'] = MODES[index]
        elif path == ('shape',):
            s['shape'] = model.SHAPES[index]
            # Preserve loads so an unsupported combination is reported by F6.
            # A new shape starts at a valid, visible outer point.
            s['point'].update(y=0.0, z=s['section']['h']/2 if s['shape'] == 'rectangle' else s['section']['d']/2)
        elif path == ('condition',):
            s['condition'] = model.CONDITIONS[index]
        elif path == ('direction',):
            direction = ('stress', 'strain')[index]
            if direction != s['direction']:
                result = model.solve(s)
                s[direction] = list(result[direction])
                s['direction'] = direction
        else:
            s['material'] = materials.preset(index)
        self.changed(s)
        self.row = min(self.row, len(self.rows())-1)
        if path == ('shape',):
            self.say('Shape changed; check loads, then F6')

    def begin(self, button=None):
        row = self.rows()[self.row]
        path = row[4]
        if not row[3]:
            self.say('Calculated property; edit geometry or material')
        elif path == ('section_editor',):
            self.open_section()
        elif row[5] == 'choice':
            if path == ('mode',):
                title, options, index = 'Analysis', MODE_NAMES, MODES.index(self.state['mode'])
            elif path == ('shape',):
                title, options, index = 'Section shape', model.SHAPE_NAMES, model.SHAPES.index(self.state['shape'])
            elif path == ('condition',):
                title, options, index = 'Condition', model.CONDITION_NAMES, model.CONDITIONS.index(self.state['condition'])
            elif path == ('direction',):
                title, options, index = 'Given components', ('Stress -> strain', 'Strain -> stress'), ('stress', 'strain').index(self.state['direction'])
            else:
                title, options, index = 'Illustrative material', tuple(r[0] for r in materials.PRESETS), 0
            self.choice = [title, options, index, path]
        else:
            self.edit = LineEdit(shown(self.value(path)/row[6]) if button is None else '', 40)
            if button is not None:
                self.edit.key(self.vm, button)

    def calculate(self):
        self.solution = None
        self.section_map, self.map_cache = None, None
        solution = model.solve(self.state)
        if self.state['mode'] == 'section' and self.state['shape'] != 'custom':
            self.section_map = SectionField(self.state)
        self.solution = solution
        self.critical_index = -1
        self.say('Calculated' if not self.solution['notes'] else self.solution['notes'][0])

    def jump_critical(self):
        if self.section_map is None:
            self.calculate()
        if self.section_map is None:
            raise ValueError('Critical points need a known section boundary')
        index = (self.critical_index+1)%4
        value, y, z = self.section_map.extrema[index]
        state = model.copy(self.state)
        state['point'].update(y=y, z=z)
        self.changed(state, probe=True)
        self.critical_index = index
        self.map_kind = (0, 0, 1, 2)[index]
        self.say(CRITICAL[index]+(' exact' if index < 2 else ' sampled'))

    def result_rows(self):
        r = self.solution
        if r is None:
            return [('F6 Calculate first', '', 'Input changes clear earlier results', None)]
        rows = [('Stress at the selected point', None, '', None)]
        if self.section_map is not None:
            rows = [('Section critical points', None, '', None)]
            for i, (value, y, z) in enumerate(self.section_map.extrema):
                detail = ('Exact' if i < 2 else 'Sampled')+'; y '+coordinate(y, self.section_map.ry)+', z '+coordinate(z, self.section_map.rz)+' mm'
                rows.append((CRITICAL[i], shown(value/1e6)+' MPa', detail, None))
            rows.append(('Search resolution', '', self.section_map.method, None))
            rows.append(('Stress at the selected point', None, '', None))
        rows += [(name, shown(value/1e6)+' MPa', 'Cartesian stress component', None) for name, value in zip(model.STRESSES, r['stress'])]
        rows.append(('Total strain', None, '', None))
        rows += [(name, shown(value/1e-6)+' ue', 'Engineering shear gamma' if i >= 3 else 'Includes thermal strain', None)
                 for i, (name, value) in enumerate(zip(model.STRAINS, r['strain']))]
        rows.append(('Principal / yield', None, '', None))
        for key, name in (('s1', 'Principal s1'), ('s2', 'Principal s2'), ('s3', 'Principal s3'),
                          ('mises', 'von Mises'), ('tmax', 'Maximum shear'), ('tresca', 'Tresca equivalent')):
            rows.append((name, shown(r['invariants'][key]/1e6)+' MPa', 'At this point; not a section-wide maximum', None))
        rows.append(('Yield factor', shown(r['safety']) if r['safety'] is not None else '--',
                     'Yield / von Mises' if self.state['material']['yield'] else 'Yield check disabled', None))
        rows += [('Shear modulus G', shown(r['G']/1e9)+' GPa', 'Isotropic relation; F9 shows the equation', None),
                 ('Free thermal strain', shown(r['thermal']/1e-6)+' ue', 'Uniform free expansion in each normal direction', None)]
        if r['properties']:
            rows.append(('Section properties', None, '', None))
            for key in ('A', 'Iy', 'Iz', 'J'):
                v = r['properties'][key]
                if v is not None:
                    rows.append((key, shown(v/(1e-6 if key == 'A' else 1e-12))+(' mm2' if key == 'A' else ' mm4'), 'Centroidal section property', None))
            rows.append(('Stress contributions', None, '', None))
            labels = ('Axial', 'Bending about y', 'Bending about z', 'Torsion: xy', 'Torsion: zx', 'Shear Vy', 'Shear Vz')
            rows += [(name, shown(item[1]/1e6)+' MPa', 'Superposed at the evaluation point', None) for name, item in zip(labels, r['contributions'])]
        rows += [('Model note', '', note, None) for note in r['notes']]
        return rows

    def option(self, index):
        from engtools import cases
        if index == 0:
            self.page, self.index = 'examples', 0
        elif index == 1:
            self.dialog = LineEdit('stress-case', 24)
        elif index == 2:
            self.files = []
            for name in cases.list_cases(self.vm.storage):
                try:
                    cases.load_case(self.vm.storage, name, model.TOOL)
                    self.files.append(name)
                except (ValueError, OSError, RuntimeError):
                    pass
            self.page, self.index = 'files', 0
        elif index in (3, 4):
            if self.solution is None:
                raise ValueError('F6 Calculate before exporting')
            if index == 3:
                path = cases.free_path(self.vm.storage, cases.EXPORT_DIRECTORY, 'stressstrain', 'csv')
                columns = tuple(name+' [Pa]' for name in model.STRESSES)+tuple(name+' [1]' for name in model.STRAINS)
                cases.export_csv(self.vm.storage, path, columns, (self.solution['stress']+self.solution['strain'],))
            else:
                from json import dumps
                path = cases.free_path(self.vm.storage, 'picoware/exchange', 'stress-state', 'json')
                data = dumps(model.stress_record(self.state, self.solution))
                if not self.vm.storage.write(path, data) or self.vm.storage.read(path) != data:
                    raise RuntimeError('Stress state write failed')
            self.page = 'model'
            self.say('Exported '+path.rsplit('/', 1)[-1])
        else:
            self.vm.show('ASSUMPTIONS / SIGNS', HELP[HELP.index('Axes and signs:'):])

    def move_point(self, button):
        s = model.copy(self.state)
        p = model.section(s)
        if button == k.BUTTON_P:
            points = [(0.0, p['rz']), (p['ry'], 0.0), (0.0, -p['rz']), (-p['ry'], 0.0)]
            if s['shape'] != 'tube':
                points.append((0.0, 0.0))
            current = (s['point']['y'], s['point']['z'])
            at = next((i for i, pt in enumerate(points) if abs(pt[0]-current[0])+abs(pt[1]-current[1]) < max(p['ry'], p['rz'])*1e-5), -1)
            s['point']['y'], s['point']['z'] = points[(at+1)%len(points)]
        else:
            dy = .1*p['ry']*(1 if button == k.BUTTON_RIGHT else -1 if button == k.BUTTON_LEFT else 0)
            dz = .1*p['rz']*(1 if button == k.BUTTON_UP else -1 if button == k.BUTTON_DOWN else 0)
            s['point']['y'] += dy
            s['point']['z'] += dz
            if not model.contains(s, s['point']['y'], s['point']['z']):
                raise ValueError('Point would leave the section material')
        self.changed(s, probe=True)

    def run(self, button):
        if button == k.BUTTON_NONE:
            return False
        if self.help_view.opened:
            self.help_view.key(button)
            return True
        if button == k.BUTTON_F9:
            self.help_view.open('sectionprops' if self.page == 'section' else self.state['mode'], HELP)
            return True
        try:
            self.handle(button)
        except (ValueError, TypeError, KeyError, ZeroDivisionError, OverflowError, OSError, RuntimeError) as exc:
            self.say(str(exc) or 'Calculation failed', True)
        return True

    def handle(self, button):
        from engtools import cases
        esc = button == self.vm.input_manager._key_esc
        if self.dialog is not None:
            action = self.dialog.key(self.vm, button)
            if action == 'cancel':
                self.dialog = None
            elif action:
                name = cases.clean_name(self.dialog.text)
                if cases.exists(self.vm.storage, name):
                    raise ValueError('Name exists; choose another name')
                # Cases must reopen as valid calculations.
                model.solve(self.state)
                cases.save_case(self.vm.storage, name, model.to_case(self.state))
                self.dialog, self.page = None, 'model'
                self.say('Saved '+name)
            return
        if self.choice is not None:
            if esc:
                self.choice = None
            elif button in (k.BUTTON_UP, k.BUTTON_DOWN):
                self.choice[2] = (self.choice[2]+(1 if button == k.BUTTON_DOWN else -1))%len(self.choice[1])
            elif button == k.BUTTON_CENTER:
                title, options, index, path = self.choice
                self.choose(path, index)
                self.choice = None
            return
        if self.edit is not None:
            action = self.edit.key(self.vm, button)
            if action == 'cancel':
                self.edit = None
            elif action:
                row = self.rows()[self.row]
                value = parse_number(self.edit.text)*row[6]
                model.finite([value])
                s = model.copy(self.state)
                parent = s
                for key in row[4][:-1]:
                    parent = parent[key]
                parent[row[4][-1]] = value
                if row[4][0] == 'material':
                    s['material']['name'] = 'Custom'
                    materials.check(s['material'])
                if row[4][0] == 'section':
                    model.section(s)
                self.changed(s)
                self.edit = None
                if action in ('up', 'down'):
                    self.move(-1 if action == 'up' else 1)
            return
        self.message, self.error = '', False
        if self.page == 'model' and self.state['mode'] == 'section' and self.solution is not None:
            if button == k.BUTTON_TAB:
                self.preview_focus = not self.preview_focus
                return
            if self.preview_focus:
                if esc:
                    self.preview_focus = False
                elif button in (k.BUTTON_LEFT, k.BUTTON_RIGHT, k.BUTTON_UP, k.BUTTON_DOWN, k.BUTTON_P):
                    self.move_point(button)
                elif button not in (k.BUTTON_F3, k.BUTTON_F4, k.BUTTON_F5, k.BUTTON_F6):
                    return
                else:
                    self.preview_focus = False
                if button not in (k.BUTTON_F3, k.BUTTON_F4, k.BUTTON_F5, k.BUTTON_F6):
                    return
        if esc:
            if self.page == 'section':
                self.close_section()
            elif self.page == 'model':
                self.vm.back()
            else:
                self.page = 'model'
            return
        char = self.vm.input_manager.button_to_char(button) or ''
        if char.lower() == 'z' and self.undo:
            self.state, self.solution = self.undo.pop(), None
            self.section_map, self.map_cache = None, None
            self.critical_index = -1
            self.row = min(self.row, len(self.rows())-1)
            self.say('Undone; F6 calculates')
            return
        if button == k.BUTTON_F6:
            self.calculate()
        elif button == k.BUTTON_F3:
            self.close_section()
            self.page, self.index = 'options', 0
        elif button == k.BUTTON_F4:
            if self.page != 'plots' and self.solution is None:
                raise ValueError('F6 Calculate before plotting')
            self.close_section()
            self.page = 'model' if self.page == 'plots' else 'plots'
        elif button in (k.BUTTON_F7, k.BUTTON_F8) and self.page == 'plots' and self.state['mode'] == 'section':
            if button == k.BUTTON_F7:
                if self.solution is None:
                    raise ValueError('F6 Calculate before plotting')
                if self.section_map is None:
                    raise ValueError('A custom section has no boundary to map')
                self.map_kind = (self.map_kind+1)%3
                self.say(KINDS[self.map_kind])
            else:
                self.jump_critical()
        elif button == k.BUTTON_F5:
            self.close_section()
            self.page, self.index = 'results', 0
        elif button in (k.BUTTON_F1, k.BUTTON_F2):
            return
        elif self.page in ('options', 'examples', 'files', 'results'):
            count = len(OPTIONS) if self.page == 'options' else len(model.EXAMPLES) if self.page == 'examples' else len(self.files) if self.page == 'files' else len(self.result_rows())
            if button in (k.BUTTON_UP, k.BUTTON_DOWN):
                self.index = (self.index+(1 if button == k.BUTTON_DOWN else -1))%max(1, count)
            elif button == k.BUTTON_CENTER and count:
                if self.page == 'options':
                    self.option(self.index)
                elif self.page == 'examples':
                    self.changed(model.example(self.index))
                    self.page, self.row = 'model', 0
                    self.say('Example loaded; F6 calculates')
                elif self.page == 'files':
                    state = model.from_case(cases.load_case(self.vm.storage, self.files[self.index], model.TOOL))
                    self.changed(state)
                    self.page, self.row = 'model', 0
        elif self.page == 'plots':
            if self.state['mode'] == 'section' and button in (k.BUTTON_LEFT, k.BUTTON_RIGHT, k.BUTTON_UP, k.BUTTON_DOWN, k.BUTTON_P):
                self.move_point(button)
        else:
            if button in (k.BUTTON_LEFT, k.BUTTON_RIGHT):
                self.switch_tab(-1 if button == k.BUTTON_LEFT else 1)
            elif button in (k.BUTTON_UP, k.BUTTON_DOWN):
                self.move(1 if button == k.BUTTON_DOWN else -1)
            elif button == k.BUTTON_CENTER:
                self.begin()
            elif self.rows()[self.row][3] and self.rows()[self.row][5] not in ('choice', 'action') and ((char and (char.isdigit() or char in '-+.(')) or erase_key(self.vm, button)):
                self.begin(button)

    def draw(self):
        draw = self.vm.draw
        p = theme.system_palette(self.vm)
        bottom = int(draw.size.y)-12
        draw.fill_screen(p.BG)
        if self.help_view.opened:
            chrome(draw, p, 'Help', title=TITLE, fallback=PATH)
            self.help_view.draw(draw, p)
            draw.swap()
            return
        if self.page == 'model':
            self.draw_preview(draw, p, (8, 43, 304, 112))
            rows = self.rows()
            self.row = min(self.row, len(rows)-1)
            draw_tabs(draw, p, (8, 161, 304, bottom-164), self.tabs.labels, self.tabs.index,
                      [None]*len(self.tabs.labels), font=XS)
            form(draw, p, [r[:4] for r in rows], -1 if self.preview_focus else self.row, self.edit, 188, bottom-24, font=XS)
            text(draw, 15, bottom-17, 'F3 Options  F5 Results  F6 Calculate', p.MUTED)
        elif self.page == 'section':
            self.draw_section(draw, p, bottom)
        elif self.page == 'plots':
            self.draw_preview(draw, p, (8, 43, 304, 171))
            if self.state['mode'] == 'section':
                text(draw, 16, 222, 'Arrows: probe   P: edge / centre', p.MUTED)
                text(draw, 16, 237, 'F7: map field   F8: critical point', p.MUTED)
                if self.section_map is not None:
                    for i, (value, y, z) in enumerate(self.section_map.extrema):
                        text(draw, 16, 254+i*12, CRITICAL[i]+': '+shown(value/1e6)+' MPa'+(' exact' if i < 2 else ' sampled'), p.TEXT)
                else:
                    text(draw, 16, 258, 'Custom: no outline or section search', p.MUTED)
            else:
                for i, name in enumerate(model.STRAINS):
                    value = shown(self.solution['strain'][i]/1e-6)+' ue' if self.solution else '--'
                    text(draw, 16+(i%2)*148, 230+(i//2)*20, name+' '+value, p.TEXT)
        elif self.page == 'results':
            panel(draw, p, (8, 43, 304, bottom-46), 'RESULTS', 'SI / engineering display')
            results(draw, p, self.result_rows(), self.index, 72, bottom-7)
        else:
            rows = OPTIONS if self.page == 'options' else tuple((name, 'Enter loads this example') for name in model.EXAMPLES) if self.page == 'examples' else tuple((name, 'Saved SI case') for name in self.files)
            menu(draw, p, rows or (('No saved cases', 'ESC returns'),), self.index, self.page.upper(), bottom)
        chrome(draw, p, {'model': 'Inputs', 'section': 'Section', 'plots': 'View'}.get(self.page, ''), self.message, self.error, title=TITLE, fallback=PATH)
        if self.choice is not None:
            popup(draw, p, self.choice[0], self.choice[1], self.choice[2])
        if self.dialog is not None:
            prompt(draw, p, 'SAVE CASE', 'Choose a new filename', self.dialog, self.message, self.error)
        draw.swap()

    def section_draft(self):
        state = model.copy(self.state)
        active = self.edit is not None or self.choice is not None
        problem = ''
        if self.choice is not None:
            path, index = self.choice[3], self.choice[2]
            if path == ('shape',):
                state['shape'] = model.SHAPES[index]
            elif path == ('material',):
                state['material'] = materials.preset(index)
        if self.edit is not None:
            r = self.rows()[self.row]
            try:
                value = parse_number(self.edit.text)*r[6]
                model.finite([value])
                parent = state
                for key in r[4][:-1]:
                    parent = parent[key]
                parent[r[4][-1]] = value
                if r[4][0] == 'material':
                    state['material']['name'] = 'Custom'
            except (ValueError, TypeError, ZeroDivisionError, OverflowError):
                state, problem = model.copy(self.state), 'Incomplete draft'
        try:
            props = model.section(state)
            materials.check(state['material'])
        except (ValueError, TypeError, ZeroDivisionError, OverflowError) as exc:
            props, problem = None, str(exc)
        return state, props, active, problem

    def draw_section(self, draw, p, bottom):
        from engtools.ui.section import preview as section_preview
        state, props, active, problem = self.section_draft()
        shape = {'rectangle': 'Rectangle', 'circle': 'Circle', 'tube': 'Tube', 'custom': 'Direct'}[state['shape']]
        dims = dict(state['section'])
        if shape == 'Tube':
            dims['t'] = (dims['d']-dims['di'])/2
        record = {'shape': shape, 'dims': dims, 'name': 'Draft' if active else 'StressStrain'}
        rows = self.rows()
        self.row = min(self.row, len(rows)-1)
        path = rows[self.row][4]
        field = 'dim:'+('t' if path[1] == 'di' else path[1]) if path[0] == 'section' else None

        def details(target, pp, x, y):
            if props is None:
                text(target, x, y, 'Check section inputs', pp.ERROR)
                return
            values = [(key, shown(props[key]/(1e-6 if key == 'A' else 1e-12))+(' mm2' if key == 'A' else ' mm4') if props[key] is not None else '--') for key in ('A', 'Iy', 'Iz', 'J')]
            values += [('E', shown(state['material']['E']/1e9)+' GPa'),
                       ('Yield', shown(state['material']['yield']/1e6)+' MPa')]
            for i, (label, value) in enumerate(values):
                text(target, x, y+i*15, label, pp.MUTED)
                right_text(target, 304, y+i*15, value, pp.TEXT)

        footer = problem or ('Draft: Enter applies; Esc cancels' if active else state['material']['name'])
        section_preview(draw, p, record, field, (8, 43, 304, 184), details, footer,
                        validate=lambda shape, dims: model.section(state), axes=True)
        draw_tabs(draw, p, (8, 230, 304, bottom-233), self.section_tabs.labels, self.section_tabs.index,
                  [None]*len(self.section_tabs.labels), font=XS, height=14)
        form(draw, p, [r[:4] for r in rows], -1 if self.preview_focus else self.row, self.edit, 248, bottom-7, font=XS, row_height=12)

    def draw_preview(self, draw, p, rect):
        if self.section_map is not None and self.solution is not None:
            map_preview(draw, p, self, rect)
        else:
            preview(draw, p, self.state, self.solution, rect)
        if self.preview_focus and self.page == 'model':
            draw._rectangle(*rect, p.ACCENT)


def map_preview(draw, p, app, rect):
    from engtools.ui.lab import mix
    x, y, w, h = rect
    field, kind = app.section_map, app.map_kind
    panel(draw, p, rect, KINDS[kind].upper(), 'MPa / Probe' if app.preview_focus and app.page == 'model' else 'MPa / F4 View' if h < 150 else 'MPa')
    scale = min(118/(2*field.ry), (h-54)/(2*field.rz))
    width, height = max(1, int(2*field.ry*scale)+1), max(1, int(2*field.rz*scale)+1)
    left, top = x+73-width//2, y+25
    low, high = field.limits(kind)
    # Fixed physical colours: blue compression, white zero, red tension;
    # nonnegative fields use blue -> yellow -> red. The legend always
    # reports the range, independently of the user's selection colour.
    middle = 0xFFFF if kind == 0 else 0xFFE0
    colours = [mix(0x025F, middle, i, 16) if i <= 16 else mix(middle, 0xF800, i-16, 16) for i in range(33)]
    key = (id(field), kind, width, height, p.BG)
    if app.map_cache is None or app.map_cache[0] != key:
        raw = bytearray(width*height*2)
        span = high-low
        for j in range(height):
            z = ((height-1)/2-j)/scale
            for i in range(width):
                yy = (i-(width-1)/2)/scale
                color = p.BG
                if model.contains(field.state, yy, z):
                    value = field.values(yy, z)[kind]
                    level = max(0, min(32, int((value-low)/span*32+.5))) if span else (16 if kind == 0 else 0)
                    color = colours[level]
                at = 2*(j*width+i)
                raw[at], raw[at+1] = color & 255, color >> 8
        app.map_cache = (key, raw)
    draw._bytearray(left, top, width, height, app.map_cache[1])
    cx, cy = left+(width-1)/2, top+(height-1)/2
    bounded = Viewport(draw, (x+6, y+23, x+w-6, y+h-3))
    if field.state['shape'] == 'rectangle':
        bounded._rectangle(left, top, width, height, p.TEXT)
    else:
        bounded._circle(cx, cy, field.ry*scale, p.TEXT)
        if field.state['shape'] == 'tube':
            bounded._circle(cx, cy, field.state['section']['di']/2*scale, p.TEXT)
    py, pz = app.state['point']['y'], app.state['point']['z']
    px, pz_px = cx+py*scale, cy-pz*scale
    bounded._circle(px, pz_px, 4, p.BG)
    bounded._circle(px, pz_px, 3, p.TEXT)
    bounded._line(px-5, pz_px, px+5, pz_px, p.TEXT)
    bounded._line(px, pz_px-5, px, pz_px+5, p.TEXT)
    text(bounded, left+width+4, cy-3, 'y', p.MUTED)
    text(bounded, cx+4, top, 'z', p.TEXT)
    rx = x+151
    text(bounded, rx, y+27, 'y '+coordinate(py, field.ry)+' mm', p.TEXT)
    text(bounded, rx, y+40, 'z '+coordinate(pz, field.rz)+' mm', p.TEXT)
    probe = field.values(py, pz)[kind]
    text(bounded, rx, y+57, 'Probe '+shown(probe/1e6), p.TEXT)
    if h > 150:
        text(bounded, rx, y+76, 'Scale (MPa)', p.MUTED)
        text(bounded, rx, y+90, 'Low '+shown(low/1e6), p.TEXT)
        text(bounded, rx, y+104, 'High '+shown(high/1e6), p.TEXT)
        text(bounded, rx, y+123, 'sx extrema: exact', p.MUTED)
        text(bounded, rx, y+136, 'VM / shear: sampled', p.MUTED)
    else:
        text(bounded, rx, y+75, shown(low/1e6)+' .. '+shown(high/1e6), p.MUTED)
    for i in range(33):
        bounded._fill_rectangle(x+13+i*4, y+h-16, 4, 6, colours[i])
    text(bounded, rx, y+h-16, '- / 0 / +' if kind == 0 else '0 / high', p.MUTED)


def arrow(draw, x1, y1, x2, y2, color):
    draw._line(x1, y1, x2, y2, color)
    dx, dy = x2-x1, y2-y1
    length = sqrt(dx*dx+dy*dy)
    if length:
        ux, uy = dx/length, dy/length
        draw._line(x2, y2, x2-5*ux+3*uy, y2-5*uy-3*ux, color)
        draw._line(x2, y2, x2-5*ux-3*uy, y2-5*uy+3*ux, color)


def preview(draw, p, state, solution, rect):
    x, y, w, h = rect
    panel(draw, p, rect, 'SECTION +x FACE' if state['mode'] == 'section' else 'STRESS TENSOR',
          'F4 View / F6 Solve' if h < 150 else '')
    bounded = Viewport(draw, (x+6, y+23, x+w-6, y+h-5))
    if state['mode'] == 'section':
        try:
            props = model.section(state)
            ry, rz = props['ry'], props['rz']
            scale = min(54/ry, (h-45)/2/rz)
            cx, cy = x+76, y+(h+22)/2
            shape = state['shape']
            if shape in ('circle', 'tube'):
                bounded._circle(cx, cy, ry*scale, p.TEXT)
                if shape == 'tube':
                    bounded._circle(cx, cy, state['section']['di']/2*scale, p.TEXT)
            elif shape == 'rectangle':
                bounded._rectangle(cx-ry*scale, cy-rz*scale, 2*ry*scale, 2*rz*scale, p.TEXT)
            else:
                text(bounded, x+26, y+h-15, 'axes only', p.MUTED)
            arrow(bounded, cx, cy, cx+ry*scale+12, cy, p.MUTED)
            arrow(bounded, cx, cy, cx, cy-rz*scale-6, p.MUTED)
            text(bounded, cx+ry*scale+5, cy+4, 'y', p.MUTED)
            text(bounded, cx+4, cy-rz*scale-2, 'z', p.MUTED)
            py, pz = state['point']['y'], state['point']['z']
            if model.contains(state, py, pz):
                bounded._fill_circle(cx+py*scale, cy-pz*scale, 3, p.ACCENT)
            else:
                text(bounded, x+8, y+26, 'Point outside material', p.ERROR)
            if h > 150:
                loads = state['loads']
                if loads['Vy']:
                    sign = 1 if loads['Vy'] > 0 else -1
                    yy = cy+rz*scale+9
                    arrow(bounded, cx-18*sign, yy, cx+18*sign, yy, p.ACCENT)
                if loads['Vz']:
                    sign = 1 if loads['Vz'] > 0 else -1
                    xx = cx-ry*scale-9
                    arrow(bounded, xx, cy+18*sign, xx, cy-18*sign, p.ACCENT)
                if loads['T']:
                    radius = max(ry, rz)*scale+7
                    sign = 1 if loads['T'] > 0 else -1
                    for i in range(15):
                        a, b = sign*i*pi/12, sign*(i+1)*pi/12
                        start = (cx+radius*cos(a), cy-radius*sin(a))
                        end = (cx+radius*cos(b), cy-radius*sin(b))
                        if i == 14:
                            arrow(bounded, start[0], start[1], end[0], end[1], p.ACCENT)
                        else:
                            bounded._line(start[0], start[1], end[0], end[1], p.ACCENT)
            text(bounded, x+151, y+27, 'y '+shown(py*1000)+' mm', p.TEXT)
            text(bounded, x+151, y+41, 'z '+shown(pz*1000)+' mm', p.TEXT)
            if solution:
                text(bounded, x+151, y+61, 'sx '+shown(solution['stress'][0]/1e6)+' MPa', p.ACCENT)
                text(bounded, x+151, y+77, 'VM '+shown(solution['invariants']['mises']/1e6)+' MPa', p.TEXT)
                if h > 150:
                    for i, key in enumerate(('txy', 'tzx')):
                        text(bounded, x+151, y+97+i*17, key+' '+shown(solution['stress'][3 if i == 0 else 5]/1e6)+' MPa', p.TEXT)
            else:
                text(bounded, x+151, y+64, 'F6 Calculate', p.MUTED)
        except (ValueError, ZeroDivisionError, OverflowError):
            text(bounded, x+12, y+35, 'Check section dimensions; F6 for details', p.ERROR)
    else:
        text(bounded, x+12, y+27, model.CONDITION_NAMES[model.CONDITIONS.index(state['condition'])], p.MUTED)
        if solution:
            for i, name in enumerate(model.STRESSES):
                text(bounded, x+12+(i%2)*146, y+46+(i//2)*17, name+' '+shown(solution['stress'][i]/1e6)+' MPa', p.TEXT)
            if h > 150:
                text(bounded, x+12, y+111, 'von Mises '+shown(solution['invariants']['mises']/1e6)+' MPa', p.ACCENT)
        else:
            text(bounded, x+12, y+53, 'Enter stress or total strain; F6 calculates', p.TEXT)


class StressStrainView:
    HELP = None

    def start(self, vm):
        global _active
        self.app = _active = StressStrain(vm)
        vm.input_manager.reset()
        self.app.draw()
        return True

    def run(self, vm):
        app = self.app
        if app is not None and app.run(vm.button) and self.app is not None:
            app.draw()

    def stop(self, vm):
        global _active
        from engtools import session
        session.kept[model.TOOL] = model.copy(self.app.state)
        self.app = _active = None


def show(vm):
    from engtools.plots.view import open_view
    return open_view(vm, 'stressstrain_view', StressStrainView())
