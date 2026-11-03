"""Euler buckling UI, cases and shared plotting for PicoLAB."""
from math import pi, sin, cos
from picoware.system import buttons as k
from engtools import sections, materials
from engtools.ui import theme
from engtools.ui.forms import LineEdit, parse_number, erase_key
from engtools.ui.lab import chrome, panel, text, right_text, form, menu, popup, prompt, results, Viewport
from engtools.ui.lab import tabs as draw_tabs
from engtools.ui.tool import Tabs, EquationHelp, equation, formulas
from picoware.system.font import FONT_XTRA_SMALL as XS
from . import model

TITLE = 'BUCKLING'
PATH = ('modules', 'structural', 'Buckling')
PREVIEW = (8, 43, 304, 184)
PROPERTIES_TOP = 230
# EquationHelp renders the mathematical trees before these definitions.
HELP = ('Symbols:', 'E Young modulus; I second moment of area',
        'L physical length; K end-condition factor',
        'A area; P applied load, compression +',
        'Ideal effective lengths:', 'Pinned-pinned K=1; fixed-fixed K=0.5',
        'Fixed-pinned K~0.7; fixed-free K=2',
        'K is independent about y and z',
        'Both axes are checked; smaller Pcr governs',
        'About y uses Iy = integral z^2 dA',
        'About z uses Iz = integral y^2 dA',
        'Yield screen:', 'Transition: Euler stress equals yield',
        'If Pcr > Py, yield precedes Euler',
        'This is a screen, not an inelastic model',
        'No safety factor is defined for P=0',
        'Assumptions:', 'Straight, prismatic, centrally loaded',
        'Linear elastic member and ideal restraints',
        'Eccentricity / imperfections are omitted',
        'Euler also requires proportional elasticity',
        'No local, torsional or whole-frame buckling',
        'Sketch amplitude is illustrative only',
        'Custom K has no calculated mode shape',
        'Custom Iy/Iz must be principal inertias',
        'Keys:', 'UP/DOWN choose; ENTER edits or selects',
        'LEFT/RIGHT changes tab and restores its row',
        'Type to replace; arithmetic is supported',
        'ENTER apply; ESC cancel / back; Z undo',
        'Section tab: ENTER edits section/material',
        'Section editor shares Beam view preview',
        'Valid typed dimensions preview before ENTER',
        'Ends / material: ENTER on their fields',
        'F3 examples, cases and CSV',
        'F4 Euler / slenderness plot',
        'F5 results; F6 calculate; F9 help')
OPTIONS = (('Examples', 'Slender, short, cantilever and two-axis cases'),
           ('Save case', 'Versioned inputs in SI'), ('Open case', 'Load a Buckling case'),
           ('Export CSV', 'Per-axis Euler and yield results in SI'))
LABELS = {'b': 'Width along y', 'h': 'Height along z', 'd': 'Outer diameter',
          'di': 'Inner diameter', 't': 'Wall thickness', 'tw': 'Web thickness', 'tf': 'Flange thickness',
          'A': 'Area', 'Iy': 'Inertia about y', 'Iz': 'Inertia about z'}
_active = None


def shown(value):
    return '0' if value == 0 else '%.6g' % value


class Buckling:
    def __init__(self, vm):
        self.vm = vm
        from engtools import session
        self.state = model.copy(session.kept.get(model.TOOL) or model.new_state())
        self.page, self.row, self.index = 'model', 0, 0
        self.edit, self.choice, self.dialog = None, None, None
        self.solution = None
        self.message, self.error = 'F6 calculates this column', False
        self.undo, self.files = [], []
        self.plot_open = False
        self.tabs = Tabs(('Section', 'Member', 'Ends'))
        self.help_view = EquationHelp()
        self.section_row, self.section_return_row = 0, 0

    def say(self, message, error=False):
        self.message, self.error = message, error

    def changed(self, state):
        self.undo.append(model.copy(self.state))
        del self.undo[:-8]
        self.state, self.solution = state, None
        self.say('Changed; F6 calculates')

    def value(self, path):
        value = self.state
        for key in path:
            value = value[key]
        return value

    def numeric(self, label, path, unit='', scale=1):
        return ('field', label, shown(self.value(path)/scale)+(' '+unit if unit else ''), True, path, unit, scale)

    def all_rows(self):
        s = self.state
        f = self.numeric
        rows = [('field', 'Shape', sections.NAMES[sections.SHAPES.index(s['shape'])], True, ('shape',), 'choice', 1)]
        for dim in sections.DIMS[s['shape']]:
            unit, scale = ('mm2', 1e-6) if dim == 'A' else ('mm4', 1e-12) if dim in ('Iy', 'Iz') else ('mm', .001)
            rows.append(f(LABELS[dim], ('section', dim), unit, scale))
        rows += [('head', 'Member / end conditions', '', False, None, '', 1),
                 f('Physical length L', ('length',), 'm'), f('Compression (+)', ('compression',), 'kN', 1000)]
        for axis in ('y', 'z'):
            rows.append(('field', 'Ends about '+axis, model.ENDS[s['ends_'+axis]][0], True, ('ends_'+axis,), 'choice', 1))
            if s['ends_'+axis] == 4:
                rows.append(f('Custom K'+axis, ('K'+axis,)))
        rows += [('head', 'Material', '', False, None, '', 1),
                 ('field', 'Preset', s['material']['name'], True, ('material',), 'choice', 1),
                 f('Young modulus E', ('material', 'E'), 'GPa', 1e9),
                 f('Yield (0 = off)', ('material', 'yield'), 'MPa', 1e6)]
        return rows

    def rows(self):
        if self.page == 'section':
            return self.section_rows()
        def group(path):
            if path[0] in ('shape', 'section'):
                return 'Section'
            if path[0] in ('length', 'compression'):
                return 'Member'
            return 'Material' if path[0] == 'material' else 'Ends'
        if self.tabs.label == 'Section':
            return [('field', 'Section + material', sections.NAMES[sections.SHAPES.index(self.state['shape'])],
                     True, ('section_editor',), 'action', 1)]
        return [r for r in self.all_rows() if r[4] is not None and group(r[4]) == self.tabs.label]

    def section_rows(self):
        return [r for r in self.all_rows() if r[4] is not None and r[4][0] in ('shape', 'section', 'material')]

    def open_section(self, material=False):
        if self.page != 'section':
            self.section_return_row = self.row
            self.page, self.row = 'section', min(self.section_row, len(self.section_rows())-1)
        if material:
            self.row = next(i for i, r in enumerate(self.section_rows()) if r[4] == ('material',))

    def close_section(self):
        if self.page == 'section':
            self.section_row = self.row
            self.page, self.row = 'model', self.section_return_row

    def switch_tab(self, step):
        rows = self.rows()
        path = rows[min(self.row, len(rows)-1)][4]
        target = self.tabs.switch(step, path)
        self.row = next((i for i, r in enumerate(self.rows()) if r[4] == target), 0)

    def select_tab(self, label):
        self.close_section()
        self.switch_tab(self.tabs.labels.index(label)-self.tabs.index)

    def move(self, step):
        rows = self.rows()
        index = self.row+step
        while 0 <= index < len(rows) and rows[index][0] == 'head':
            index += step
        if 0 <= index < len(rows):
            self.row = index

    def open_choice(self, path):
        if path == ('shape',):
            self.choice = ['Section shape', sections.NAMES, sections.SHAPES.index(self.state['shape']), path]
        elif path == ('material',):
            self.choice = ['Illustrative material', tuple(r[0] for r in materials.PRESETS), 0, path]
        else:
            self.choice = ['Both axes: ends' if path == ('both',) else 'Ends about '+path[0][-1],
                           tuple(r[0] for r in model.ENDS), self.state['ends_y' if path == ('both',) else path[0]], path]

    def choose(self):
        _, options, index, path = self.choice
        state = model.copy(self.state)
        if path == ('shape',):
            state['shape'] = sections.SHAPES[index]
        elif path == ('material',):
            state['material'] = materials.preset(index)
        elif path == ('both',):
            state['ends_y'] = state['ends_z'] = index
        else:
            state[path[0]] = index
        self.changed(state)
        self.choice = None
        self.row = min(self.row, len(self.rows())-1)
        while self.rows()[self.row][0] == 'head':
            self.row -= 1

    def begin(self, button=None):
        row = self.rows()[self.row]
        if row[4] == ('section_editor',):
            self.open_section()
        elif row[5] == 'choice':
            self.open_choice(row[4])
        else:
            self.edit = LineEdit(shown(self.value(row[4])/row[6]) if button is None else '', 40)
            if button is not None:
                self.edit.key(self.vm, button)

    def calculate(self):
        self.solution = None
        self.solution = model.solve(self.state)
        self.say(self.solution['notes'][0] if self.solution['notes'] else 'Calculated: both axes checked')

    def result_rows(self):
        r = self.solution
        if r is None:
            return [('F6 Calculate first', '', 'Input changes clear previous results', None)]
        rows = [('Column summary', None, '', None),
                ('Governing axis', 'y = z' if r['equal_axes'] else r['governing'], 'Smallest Euler load including K', None),
                ('Euler critical', shown(r['critical']/1000)+' kN', 'Ideal elastic buckling load', None),
                ('Euler factor', shown(r['factor']) if r['factor'] is not None else '--', 'Pcr / P; undefined at zero applied load', None),
                ('Applied stress', shown(r['applied_stress']/1e6)+' MPa', 'Compression P / A', None)]
        for axis in ('y', 'z'):
            a = r['axes'][axis]
            rows += [('Buckling about '+axis, None, '', None),
                     ('Effective K', shown(a['K']), model.ENDS[self.state['ends_'+axis]][0], None),
                     ('Effective length', shown(a['effective_length'])+' m', 'K * physical length', None),
                     ('Radius r', shown(a['r']*1000)+' mm', 'sqrt(I / A)', None),
                     ('Slenderness', shown(a['slenderness']), 'K * L / r', None),
                     ('Euler load', shown(a['critical']/1000)+' kN', 'Euler equation; F9 shows the formula', None),
                     ('Euler stress', shown(a['critical_stress']/1e6)+' MPa', 'Pcr / A', None),
                     ('Euler factor', shown(a['factor']) if a['factor'] is not None else '--', 'Pcr / P', None)]
        rows += [('Yield screen', None, '', None),
                 ('Yield load', shown(r['yield_load']/1000)+' kN' if r['yield_load'] is not None else '--', 'Axial yield strength * area; not a column curve', None),
                 ('Yield factor', shown(r['yield_factor']) if r['yield_factor'] is not None else '--', 'Py / P; yield = 0 disables this check', None),
                 ('Transition lambda', shown(r['transition_slenderness']) if r['transition_slenderness'] is not None else '--', 'pi * sqrt(E / yield strength)', None),
                 ('Yield before Euler', 'Yes' if r['yield_first'] else 'Unchecked' if r['yield_load'] is None else 'No', 'Yield comparison does not prove proportional elasticity', None),
                 ('Section properties', None, '', None)]
        for name in ('A', 'Iy', 'Iz'):
            rows.append((name, shown(r['properties'][name]/(1e-6 if name == 'A' else 1e-12))+(' mm2' if name == 'A' else ' mm4'), 'Centroidal principal section property', None))
        rows += [('Model note', '', note, None) for note in r['notes']]
        return rows

    def option(self, index):
        from engtools import cases
        if index == 0:
            self.page, self.index = 'examples', 0
        elif index == 1:
            self.dialog = LineEdit('column-case', 24)
        elif index == 2:
            self.files = []
            for name in cases.list_cases(self.vm.storage):
                try:
                    cases.load_case(self.vm.storage, name, model.TOOL)
                    self.files.append(name)
                except (ValueError, OSError, RuntimeError):
                    pass
            self.page, self.index = 'files', 0
        else:
            if self.solution is None:
                raise ValueError('F6 Calculate before exporting')
            r = self.solution
            path = cases.free_path(self.vm.storage, cases.EXPORT_DIRECTORY, 'buckling', 'csv')
            columns = ('axis [1]', 'L [m]', 'K [1]', 'Le [m]', 'A [m2]', 'I [m4]', 'r [m]',
                       'slenderness [1]', 'E [Pa]', 'P [N]', 'Pcr [N]', 'sigma_cr [Pa]', 'yield [Pa]')
            rows = []
            for number, axis in enumerate(('y', 'z')):
                a = r['axes'][axis]
                rows.append((number, self.state['length'], a['K'], a['effective_length'], r['properties']['A'],
                             r['properties']['I'+axis], a['r'], a['slenderness'], self.state['material']['E'],
                             self.state['compression'], a['critical'], a['critical_stress'], self.state['material']['yield']))
            cases.export_csv(self.vm.storage, path, columns, rows)
            self.page = 'model'
            self.say('Exported '+path.rsplit('/', 1)[-1])

    def run(self, button):
        if button == k.BUTTON_NONE:
            return False
        if self.help_view.opened:
            self.help_view.key(button)
            return True
        if button == k.BUTTON_F9:
            self.help_view.open('buckling', HELP)
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
                self.choose()
            return
        if self.edit is not None:
            action = self.edit.key(self.vm, button)
            if action == 'cancel':
                self.edit = None
                self.say('Edit cancelled')
            elif action:
                row = self.rows()[self.row]
                value = parse_number(self.edit.text)*row[6]
                from math import isfinite
                if not isfinite(value):
                    raise ValueError('Enter a finite number')
                state = model.copy(self.state)
                parent = state
                for key in row[4][:-1]:
                    parent = parent[key]
                parent[row[4][-1]] = value
                if row[4][0] == 'material':
                    state['material']['name'] = 'Custom'
                    materials.check(state['material'])
                if row[4][0] == 'section':
                    sections.properties(state['shape'], state['section'])
                if row[4] in (('length',), ('Ky',), ('Kz',)) and value <= 0:
                    raise ValueError('Length and K must be positive')
                if row[4] == ('compression',) and value < 0:
                    raise ValueError('Compression must be zero or positive')
                self.changed(state)
                self.edit = None
                if action in ('up', 'down'):
                    self.move(-1 if action == 'up' else 1)
            return
        self.message, self.error = '', False
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
            self.row = min(self.row, len(self.rows())-1)
            while self.rows()[self.row][0] == 'head':
                self.row -= 1
            self.say('Undone; F6 calculates')
        elif button == k.BUTTON_F6:
            self.calculate()
        elif button in (k.BUTTON_F1, k.BUTTON_F2):
            return
        elif button == k.BUTTON_F3:
            self.close_section()
            self.page, self.index = 'options', 0
        elif button == k.BUTTON_F4:
            if self.solution is None:
                raise ValueError('F6 Calculate before plotting')
            from engtools.plots import plot2d
            self.close_section()
            spec = model.plot_spec(self.state, self.solution)
            self.plot_open = True
            try:
                plot2d.show(self.vm, spec)
            except Exception:
                self.plot_open = False
                raise
        elif button == k.BUTTON_F5:
            self.close_section()
            self.page, self.index = 'results', 0
        elif self.page in ('options', 'examples', 'files', 'results'):
            count = len(OPTIONS) if self.page == 'options' else len(model.EXAMPLES) if self.page == 'examples' else len(self.files) if self.page == 'files' else len(self.result_rows())
            if button in (k.BUTTON_UP, k.BUTTON_DOWN):
                self.index = (self.index+(1 if button == k.BUTTON_DOWN else -1))%max(1, count)
            elif button == k.BUTTON_CENTER and count:
                if self.page == 'options':
                    self.option(self.index)
                else:
                    state = model.example(self.index) if self.page == 'examples' else model.from_case(cases.load_case(self.vm.storage, self.files[self.index], model.TOOL)) if self.page == 'files' else None
                    if state is not None:
                        self.changed(state)
                        self.page, self.row = 'model', 0
        elif button in (k.BUTTON_LEFT, k.BUTTON_RIGHT) and self.page == 'model':
            self.switch_tab(-1 if button == k.BUTTON_LEFT else 1)
        elif button in (k.BUTTON_UP, k.BUTTON_DOWN):
            self.move(1 if button == k.BUTTON_DOWN else -1)
        elif button == k.BUTTON_CENTER:
            self.begin()
        elif self.rows()[self.row][5] not in ('choice', 'action') and ((char and (char.isdigit() or char in '-+.(')) or erase_key(self.vm, button)):
            self.begin(button)

    def section_draft(self):
        """A valid/partial edit affects only the preview until Enter commits."""
        state = model.copy(self.state)
        draft = self.edit is not None or self.choice is not None
        error = ''
        if self.choice is not None:
            path, index = self.choice[3], self.choice[2]
            if path == ('shape',):
                state['shape'] = sections.SHAPES[index]
            elif path == ('material',):
                state['material'] = materials.preset(index)
        if self.edit is not None:
            r = self.section_rows()[self.row]
            try:
                value = parse_number(self.edit.text)*r[6]
                parent = state
                for key in r[4][:-1]:
                    parent = parent[key]
                parent[r[4][-1]] = value
                if r[4][0] == 'material':
                    state['material']['name'] = 'Custom'
            except (ValueError, TypeError, ZeroDivisionError, OverflowError):
                state, error = model.copy(self.state), 'Incomplete draft'
        try:
            sections.properties(state['shape'], state['section'])
            materials.check(state['material'])
        except (ValueError, TypeError, ZeroDivisionError, OverflowError) as exc:
            error = str(exc)
        return state, draft, error

    def draw_section(self, draw, p, bottom):
        from engtools.ui.section import preview as section_preview
        state, draft, error = self.section_draft()
        shape = {'rectangle': 'Rectangle', 'box': 'Hollow rect', 'circle': 'Circle',
                 'tube': 'Tube', 'i-section': 'I-section', 'custom': 'Direct'}[state['shape']]
        dims = dict(state['section'])
        if shape == 'Tube':
            dims['t'] = (dims['d']-dims['di'])/2
        record = {'shape': shape, 'dims': dims, 'name': 'Draft' if draft else 'Column'}
        rows = self.section_rows()
        self.row = min(self.row, len(rows)-1)
        path = rows[self.row][4]
        field = 'dim:'+('t' if path[1] == 'di' else path[1]) if path[0] == 'section' else None

        def details(target, pp, x, y):
            try:
                prop = sections.properties(state['shape'], state['section'])
                values = [('A', shown(prop['A']/1e-6)+' mm2'),
                          ('Iy', shown(prop['Iy']/1e-12)+' mm4'),
                          ('Iz', shown(prop['Iz']/1e-12)+' mm4'),
                          ('E', shown(state['material']['E']/1e9)+' GPa'),
                          ('Yield', shown(state['material']['yield']/1e6)+' MPa')]
                for i, (label, value) in enumerate(values):
                    text(target, x, y+14*i, label, pp.MUTED)
                    right_text(target, 304, y+14*i, value, pp.TEXT)
            except (ValueError, TypeError, ZeroDivisionError, OverflowError):
                text(target, x, y, 'Check section sizes', pp.ERROR)

        footer = error or ('Draft: Enter applies, Esc cancels' if draft else
                          sections.NAMES[sections.SHAPES.index(state['shape'])]+' | '+state['material']['name'])
        section_preview(draw, p, record, field, PREVIEW, details, footer,
                        validate=lambda shape, dims: sections.properties(state['shape'], state['section']))
        panel(draw, p, (8, PROPERTIES_TOP, 304, bottom-PROPERTIES_TOP-3),
              'SECTION / MATERIAL', '%d/%d' % (self.row+1, len(rows)))
        form(draw, p, [r[:4] for r in rows], self.row, self.edit, PROPERTIES_TOP+24, bottom-7,
             font=XS, row_height=12)

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
            preview(draw, p, self.state, self.solution)
            rows = self.rows()
            self.row = min(self.row, len(rows)-1)
            draw_tabs(draw, p, (8, PROPERTIES_TOP, 304, bottom-PROPERTIES_TOP-3), self.tabs.labels, self.tabs.index,
                      [None]*len(self.tabs.labels), font=XS, height=14)
            form(draw, p, [row[:4] for row in rows], self.row, self.edit, PROPERTIES_TOP+18, bottom-7,
                 font=XS, row_height=12)
        elif self.page == 'section':
            self.draw_section(draw, p, bottom)
        elif self.page == 'results':
            panel(draw, p, (8, 43, 304, bottom-46), 'RESULTS')
            results(draw, p, self.result_rows(), self.index, 72, bottom-7)
        else:
            rows = OPTIONS if self.page == 'options' else tuple((name, 'Enter loads this example') for name in model.EXAMPLES) if self.page == 'examples' else tuple((name, 'Saved SI column case') for name in self.files)
            menu(draw, p, rows or (('No saved cases', 'ESC returns'),), self.index, self.page.upper(), bottom)
        chrome(draw, p, 'Section' if self.page == 'section' else 'Inputs' if self.page == 'model' else '', self.message, self.error, title=TITLE, fallback=PATH)
        if self.choice is not None:
            popup(draw, p, self.choice[0], self.choice[1], self.choice[2])
        if self.dialog is not None:
            prompt(draw, p, 'SAVE COLUMN CASE', 'Choose a new filename', self.dialog, self.message, self.error)
        draw.swap()


def support(draw, p, x, y, kind, top=False):
    if kind == 'free':
        return
    if kind == 'fixed':
        draw._line(x-13, y, x+13, y, p.TEXT)
        for i in range(-12, 13, 6):
            draw._line(x+i, y, x+i-4, y+(-5 if top else 5), p.MUTED)
    else:
        d = -1 if top else 1
        draw._line(x, y, x-6, y+8*d, p.TEXT)
        draw._line(x, y, x+6, y+8*d, p.TEXT)
        draw._line(x-6, y+8*d, x+6, y+8*d, p.TEXT)


def preview(draw, p, state, result):
    panel(draw, p, PREVIEW, 'IDEAL COLUMN', 'F4 Plot / F6 Solve')
    bounded = Viewport(draw, (14, 65, 306, 222))
    axis = result['governing'] if result else 'y'
    ends = state['ends_'+axis]
    x, top, base = 75, 85, 194
    bounded._line(x, top, x, base, p.GRID)
    kinds = (('pin', 'pin'), ('fixed', 'fixed'), ('fixed', 'pin'), ('fixed', 'free'), ('free', 'free'))[ends]
    support(bounded, p, x, base, kinds[0])
    support(bounded, p, x, top, kinds[1], True)
    if ends != 4:
        def shape(t):
            if ends == 0:
                return sin(pi*t)
            if ends == 1:
                return (1-cos(2*pi*t))/2
            if ends == 3:
                return 1-cos(pi*t/2)
            a = 4.493409458
            return sin(a*t)-a*cos(a*t)+a*(1-t)
        samples = [shape(i/32) for i in range(33)]
        scale = 23/max(abs(v) for v in samples)
        for i in range(32):
            bounded._line(x+samples[i]*scale, base-i*(base-top)/32,
                          x+samples[i+1]*scale, base-(i+1)*(base-top)/32, p.ACCENT)
    text(bounded, 18, 67, 'P', p.TEXT)
    bounded._line(30, 69, 30, 89, p.TEXT)
    bounded._line(30, 89, 26, 84, p.TEXT); bounded._line(30, 89, 34, 84, p.TEXT)
    text(bounded, 107, 135, 'L', p.MUTED)
    text(bounded, 16, 211, 'Custom K: no mode' if ends == 4 else 'Illustrative shape', p.MUTED)
    if result:
        text(bounded, 157, 82, 'Pcr '+shown(result['critical']/1000)+' kN', p.ACCENT)
        text(bounded, 157, 106, 'Axis '+('y = z' if result['equal_axes'] else axis), p.TEXT)
        text(bounded, 157, 130, 'Euler n '+(shown(result['factor']) if result['factor'] is not None else '--'), p.TEXT)
        text(bounded, 157, 156, 'Yield before Euler' if result['yield_first'] else 'Yield check off' if result['yield_load'] is None else 'Yield screen checked', p.ERROR if result['yield_first'] else p.MUTED)
    else:
        equation(draw, p, formulas('buckling')[0][1], (146, 84, 155, 57))
        text(bounded, 153, 164, 'F6 checks both axes', p.MUTED)


class BucklingView:
    HELP = None  # app-owned help uses the calculator's mathematical layout

    def __init__(self):
        self.app = None

    def start(self, vm):
        global _active
        if self.app is None:
            self.app = Buckling(vm)
        self.app.plot_open = False
        _active = self.app
        vm.input_manager.reset()
        self.app.draw()
        return True

    def run(self, vm):
        app = self.app
        if app is not None and app.run(vm.button) and self.app is not None and vm.current_view.name == 'buckling_view':
            app.draw()

    def stop(self, vm):
        global _active
        from engtools import session
        if self.app is not None:
            session.kept[model.TOOL] = model.copy(self.app.state)
            if not self.app.plot_open:
                self.app = None
        _active = None


def show(vm):
    from engtools.plots.view import open_view
    return open_view(vm, 'buckling_view', BucklingView())
