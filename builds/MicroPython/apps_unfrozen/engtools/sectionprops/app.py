"""Standalone section editor, live properties and material records."""
from picoware.system import buttons as k
from picoware.system.font import FONT_XTRA_SMALL as XS
from engtools import materials
from engtools.ui import theme
from engtools.ui import section as section_view
from engtools.ui.forms import LineEdit, parse_number, erase_key
from engtools.ui.lab import chrome, panel, text, right_text, form, menu, popup, prompt, results, Viewport
from engtools.ui.lab import tabs as draw_tabs
from engtools.ui.tool import Tabs, EquationHelp
from . import model

TITLE = 'SECTION PROPERTIES'
PATH = ('modules', 'structural', 'Section Properties')
PREVIEW = (8, 43, 304, 184)
TOP = 230
LABELS = {'b': 'Width along y', 'h': 'Height along z', 't': 'Wall thickness',
          'd': 'Outer diameter', 'di': 'Inner diameter', 'tw': 'Web thickness', 'tf': 'Flange thickness'}
OPTIONS = (('Examples', 'Six section templates'), ('Save section', 'Versioned SI inputs'),
           ('Open section', 'Load a saved section'), ('Export CSV', 'One row of SI properties'),
           ('Export JSON report', 'Inputs and results; standalone format'), ('New section', 'Reset to a rectangle; Z undoes'))
HELP = ('Axes and properties:', 'Origin: outer box bottom-left', 'y right, z up; centroid shown by a dot',
        'Iy bends about y; Iz bends about z', 'Section moduli use extreme fibres',
        'T-section flange is at the top', 'All templates have vertical symmetry',
        'Iyz is zero about the centroid', 'I1 >= I2; angle from +y toward +z',
        'Equal moments: any principal direction',
        'Ip is polar AREA moment, not mass inertia',
        'J = Ip only for the circular templates',
        'Noncircular torsion constant is not solved',
        'Material:', 'Presets are illustrative, not certified', 'Density sets mass per unit length',
        'E sets bending rigidity; G is isotropic',
        'Keys:', 'LEFT/RIGHT tabs; UP/DOWN chooses a row',
        'ENTER edits; type numbers to replace', 'Valid drafts preview before ENTER',
        'ENTER applies; ESC cancels or goes back', 'F1 shape; F2 material; F3 files/examples',
        'F4 enlarged section; TAB toggles axes', 'F5 full results; F6 refresh; F9 equations', 'Z undo',
        'First-pass scope:', 'Six templates; no composite/CAD profiles',
        'Saved sections stay within this app', 'Connections to other apps come later')
_active = None


def shown(value):
    return '0' if value == 0 else '%.6g' % value


def property_rows(r):
    """label, value, detail, key; geometry in engineering display units."""
    rows = []
    for key, label, scale, unit, detail in (
        ('A', 'Area', 1e-6, 'mm2', 'Cross-sectional area'),
        ('cy', 'Centroid y', .001, 'mm', 'From the outer box left edge'),
        ('cz', 'Centroid z', .001, 'mm', 'From the outer box bottom edge'),
        ('Iy', 'Inertia Iy', 1e-12, 'mm4', 'Centroidal axis y'),
        ('Iz', 'Inertia Iz', 1e-12, 'mm4', 'Centroidal axis z'),
        ('Iyz', 'Product Iyz', 1e-12, 'mm4', 'Zero by vertical symmetry'),
        ('Ip', 'Polar area Ip', 1e-12, 'mm4', 'Iy + Iz; distinct from torsion constant'),
        ('Wy_top', 'Wy top', 1e-9, 'mm3', 'Positive z extreme fibre'),
        ('Wy_bottom', 'Wy bottom', 1e-9, 'mm3', 'Negative z extreme fibre'),
        ('Wz_right', 'Wz right', 1e-9, 'mm3', 'Positive y extreme fibre'),
        ('Wz_left', 'Wz left', 1e-9, 'mm3', 'Negative y extreme fibre'),
        ('ry', 'Gyration ry', .001, 'mm', 'About the centroidal y axis'),
        ('rz', 'Gyration rz', .001, 'mm', 'About the centroidal z axis'),
        ('I1', 'Principal I1', 1e-12, 'mm4', 'Larger principal area moment'),
        ('I2', 'Principal I2', 1e-12, 'mm4', 'Smaller principal area moment'),
        ('mass_per_length', 'Mass / length', 1, 'kg/m', 'Density times section area'),
        ('EIy', 'Rigidity EIy', 1, 'Nm2', 'Elastic bending rigidity about y'),
        ('EIz', 'Rigidity EIz', 1, 'Nm2', 'Elastic bending rigidity about z'),
        ('G', 'Shear modulus G', 1e9, 'GPa', 'Isotropic E and nu relation')):
        rows.append((label, shown(r[key]/scale)+' '+unit, detail, key))
    rows.insert(15, ('Principal angle', 'Any' if r['equal_axes'] else shown(r['theta']*180/3.141592653589793)+' deg',
                     'I1 axis measured from +y toward +z', 'theta'))
    rows.append(('Torsion J', shown(r['J']/1e-12)+' mm4' if r['J'] is not None else '--',
                 'Circular shaft only' if r['J'] is not None else 'Noncircular torsion is not calculated', 'J'))
    return rows


class SectionProperties:
    def __init__(self, vm):
        from engtools import session
        self.vm = vm
        self.state = model.copy(session.kept.get(model.TOOL) or model.new_state())
        self.solution = model.solve(self.state)
        self.tabs = Tabs(('Geometry', 'Material', 'Properties'))
        self.help_view = EquationHelp()
        self.page, self.row, self.index = 'model', 0, 0
        self.edit, self.choice, self.dialog = None, None, None
        self.undo, self.files = [], []
        self.axes = True
        self.message, self.error = '', False

    def say(self, message, error=False):
        self.message, self.error = message, error

    def changed(self, state):
        result = model.solve(state)
        self.undo.append(model.copy(self.state))
        del self.undo[:-8]
        self.state, self.solution = state, result
        self.say('Section updated')

    def value(self, path):
        value = self.state
        for key in path:
            value = value[key]
        return value

    def numeric(self, label, path, unit, scale):
        return ('field', label, shown(self.value(path)/scale)+(' '+unit if unit else ''), True, path, unit, scale)

    def rows(self):
        s = self.state
        f = self.numeric
        if self.tabs.label == 'Geometry':
            rows = [('field', 'Shape', model.NAMES[model.SHAPES.index(s['shape'])], True, ('shape',), 'choice', 1)]
            rows += [f(LABELS[key], ('dims', key), 'mm', .001) for key in model.DIMS[s['shape']]]
            rows.append(('field', 'Name', s['name'], True, ('name',), 'text', 1))
            return rows
        if self.tabs.label == 'Material':
            return [('field', 'Preset', s['material']['name'], True, ('material',), 'choice', 1),
                    f('Density rho', ('material', 'rho'), 'kg/m3', 1),
                    f('Young modulus E', ('material', 'E'), 'GPa', 1e9),
                    f('Poisson ratio nu', ('material', 'nu'), '', 1),
                    f('Yield (0 = off)', ('material', 'yield'), 'MPa', 1e6),
                    f('Expansion alpha', ('material', 'alpha'), 'um/mK', 1e-6)]
        return [('field', label, value, False, ('result', key), '', 1) for label, value, _, key in property_rows(self.solution)]

    def switch_tab(self, step):
        current = self.rows()[self.row][4]
        target = self.tabs.switch(step, current)
        self.row = next((i for i, r in enumerate(self.rows()) if r[4] == target), 0)

    def select_tab(self, label):
        self.switch_tab(self.tabs.labels.index(label)-self.tabs.index)

    def begin(self, button=None):
        r = self.rows()[self.row]
        if not r[3]:
            self.say('Calculated property; change the geometry or material')
        elif r[5] == 'choice':
            if r[4] == ('shape',):
                self.choice = ['Section shape', model.NAMES, model.SHAPES.index(self.state['shape']), ('shape',)]
            else:
                names = tuple(p[0] for p in materials.PRESETS)
                at = names.index(self.state['material']['name']) if self.state['material']['name'] in names else 2
                self.choice = ['Illustrative material', names, at, ('material',)]
        else:
            value = self.value(r[4]) if r[5] == 'text' else shown(self.value(r[4])/r[6])
            self.edit = LineEdit(str(value) if button is None else '', 24 if r[5] == 'text' else 40)
            if button is not None:
                self.edit.key(self.vm, button)

    def edit_state(self):
        state = model.copy(self.state)
        r = self.rows()[self.row]
        value = self.edit.text.strip() if r[5] == 'text' else parse_number(self.edit.text)*r[6]
        parent = state
        for key in r[4][:-1]:
            parent = parent[key]
        parent[r[4][-1]] = value
        if r[4][0] == 'material':
            state['material']['name'] = 'Custom'
        return state

    def draft(self):
        state = model.copy(self.state)
        active = self.edit is not None or self.choice is not None
        error = ''
        if self.choice is not None:
            if self.choice[3] == ('shape',):
                state['shape'] = model.SHAPES[self.choice[2]]
            else:
                state['material'] = model.material(self.choice[2])
        if self.edit is not None:
            try:
                state = self.edit_state()
            except (ValueError, TypeError, ZeroDivisionError, OverflowError):
                error = 'Incomplete draft'
        try:
            result = model.solve(state)
        except (ValueError, TypeError, ZeroDivisionError, OverflowError) as exc:
            result, error = None, str(exc)
        return state, result, active, error

    def option(self, index):
        from engtools import cases
        if index == 0:
            self.page, self.index = 'examples', 0
        elif index == 1:
            self.dialog = LineEdit(self.state['name'], 24)
        elif index == 2:
            self.files = []
            for name in cases.list_cases(self.vm.storage):
                try:
                    cases.load_case(self.vm.storage, name, model.TOOL)
                    self.files.append(name)
                except (ValueError, RuntimeError, OSError):
                    pass
            self.page, self.index = 'files', 0
        elif index in (3, 4):
            extension = 'csv' if index == 3 else 'json'
            path = cases.free_path(self.vm.storage, cases.EXPORT_DIRECTORY, 'section', extension)
            if index == 3:
                columns = list(model.EXPORTS)
                if self.solution['J'] is not None:
                    columns.append(('J', 'm4'))
                cases.export_csv(self.vm.storage, path, [key+' ['+unit+']' for key, unit in columns],
                                 ([self.solution[key] for key, _ in columns],))
            else:
                from json import dumps
                data = dumps(model.report(self.state))
                if not self.vm.storage.write(path, data) or self.vm.storage.read(path) != data:
                    raise RuntimeError('JSON report write failed')
            self.page = 'model'
            self.say('Exported '+path.rsplit('/', 1)[-1])
        else:
            self.changed(model.new_state())
            self.tabs.index, self.row, self.page = 0, 0, 'model'

    def run(self, button):
        if button == k.BUTTON_NONE:
            return False
        if self.help_view.opened:
            self.help_view.key(button)
            return True
        if button == k.BUTTON_F9:
            self.help_view.open('sectionprops', HELP)
            return True
        try:
            self.handle(button)
        except (ValueError, TypeError, KeyError, ZeroDivisionError, OverflowError, RuntimeError, OSError) as exc:
            self.say(str(exc) or 'Section calculation failed', True)
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
                state, result, active, error = self.draft()
                if error:
                    raise ValueError(error)
                self.changed(state)
                self.choice = None
                self.row = min(self.row, len(self.rows())-1)
            return
        if self.edit is not None:
            action = self.edit.key(self.vm, button)
            if action == 'cancel':
                self.edit = None
                self.say('Edit cancelled')
            elif action:
                self.changed(self.edit_state())
                self.edit = None
                if action in ('up', 'down'):
                    self.row = min(max(0, self.row+(1 if action == 'down' else -1)), len(self.rows())-1)
            return
        self.message, self.error = '', False
        if esc:
            if self.page == 'model':
                self.vm.back()
            else:
                self.page = 'model'
            return
        char = self.vm.input_manager.button_to_char(button) or ''
        if char.lower() == 'z' and self.undo:
            self.state = self.undo.pop()
            self.solution = model.solve(self.state)
            self.row = min(self.row, len(self.rows())-1)
            self.say('Undone')
        elif button == k.BUTTON_F1:
            self.page = 'model'; self.select_tab('Geometry'); self.row = 0; self.begin()
        elif button == k.BUTTON_F2:
            self.page = 'model'; self.select_tab('Material'); self.row = 0; self.begin()
        elif button == k.BUTTON_F3:
            self.page, self.index = 'options', 0
        elif button == k.BUTTON_F4:
            self.page = 'model' if self.page == 'view' else 'view'
        elif button == k.BUTTON_F5:
            self.page, self.index = 'results', 0
        elif button == k.BUTTON_F6:
            self.solution = model.solve(self.state); self.say('Properties refreshed')
        elif button == k.BUTTON_TAB and self.page in ('model', 'view'):
            self.axes = not self.axes
        elif self.page in ('options', 'files', 'examples', 'results'):
            count = len(OPTIONS) if self.page == 'options' else len(self.files) if self.page == 'files' else len(model.EXAMPLES) if self.page == 'examples' else len(property_rows(self.solution))
            if button in (k.BUTTON_UP, k.BUTTON_DOWN):
                self.index = (self.index+(1 if button == k.BUTTON_DOWN else -1))%max(1, count)
            elif button == k.BUTTON_CENTER and count:
                if self.page == 'options':
                    self.option(self.index)
                elif self.page in ('examples', 'files'):
                    state = model.example(self.index) if self.page == 'examples' else model.from_case(cases.load_case(self.vm.storage, self.files[self.index], model.TOOL))
                    self.changed(state)
                    self.tabs.index, self.row, self.page = 0, 0, 'model'
        elif self.page == 'model':
            if button in (k.BUTTON_LEFT, k.BUTTON_RIGHT):
                self.switch_tab(-1 if button == k.BUTTON_LEFT else 1)
            elif button in (k.BUTTON_UP, k.BUTTON_DOWN):
                self.row = min(max(0, self.row+(1 if button == k.BUTTON_DOWN else -1)), len(self.rows())-1)
            elif button == k.BUTTON_CENTER:
                self.begin()
            elif self.rows()[self.row][3] and self.rows()[self.row][5] not in ('choice', 'text') and ((char and (char.isdigit() or char in '-+.(')) or erase_key(self.vm, button)):
                self.begin(button)

    def draw(self):
        draw, p = self.vm.draw, theme.system_palette(self.vm)
        bottom = int(draw.size.y)-12
        draw.fill_screen(p.BG)
        if self.help_view.opened:
            chrome(draw, p, 'Help', title=TITLE, fallback=PATH)
            self.help_view.draw(draw, p); draw.swap(); return
        if self.page in ('model', 'view'):
            state, result, active, problem = self.draft()
            record = model.preview_record(state, active)
            path = self.rows()[self.row][4]
            field = 'dim:'+('t' if path[1] == 'di' else path[1]) if path[0] == 'dims' else None
            validate = lambda shape, dims: model.geometry(state)
            centroid = lambda shape, dims: result['height']-result['cz'] if result else None
            if self.page == 'view':
                panel(draw, p, (8, 43, 304, bottom-46), 'CROSS SECTION', state['name'])
                section_view.cross_section(Viewport(draw, (14, 65, 306, bottom-22)), p, record, field,
                                           (18, 67, 300, bottom-25), False, validate=validate,
                                           centroid_from_top=centroid, axes=self.axes)
                text(draw, 18, bottom-17, 'TAB Axes   F4 / ESC Back', p.MUTED)
            else:
                def details(target, pp, x, y):
                    if result is None:
                        text(target, x, y, 'Check dimensions', pp.ERROR)
                        return
                    for i, (label, value) in enumerate((('A', shown(result['A']/1e-6)+' mm2'),
                        ('Iy', shown(result['Iy']/1e-12)+' mm4'), ('Iz', shown(result['Iz']/1e-12)+' mm4'),
                        ('cy', shown(result['cy']/.001)+' mm'), ('cz', shown(result['cz']/.001)+' mm'),
                        ('Mass', shown(result['mass_per_length'])+' kg/m'))):
                        text(target, x, y+i*15, label, pp.MUTED)
                        right_text(target, 304, y+i*15, value, pp.TEXT)
                footer = problem or ('Draft: Enter applies; Esc cancels' if active else state['material']['name'])
                section_view.preview(draw, p, record, field, PREVIEW, details, footer,
                                     validate=validate, centroid_from_top=centroid, axes=self.axes)
                rows = self.rows()
                draw_tabs(draw, p, (8, TOP, 304, bottom-TOP-3), self.tabs.labels, self.tabs.index,
                          [None]*len(self.tabs.labels), font=XS, height=14)
                form(draw, p, [r[:4] for r in rows], self.row, self.edit, TOP+18, bottom-7, font=XS, row_height=12)
        elif self.page == 'results':
            panel(draw, p, (8, 43, 304, bottom-46), 'PROPERTIES')
            results(draw, p, [(label, value, detail, None) for label, value, detail, _ in property_rows(self.solution)], self.index, 72, bottom-7)
        else:
            rows = OPTIONS if self.page == 'options' else tuple((name, 'Enter loads this section') for name in model.EXAMPLES) if self.page == 'examples' else tuple((name, 'Saved Section Properties case') for name in self.files)
            menu(draw, p, rows or (('No saved sections', 'ESC returns'),), self.index, self.page.upper(), bottom)
        chrome(draw, p, '' if self.page != 'model' else 'Inputs', self.message, self.error, title=TITLE, fallback=PATH)
        if self.choice is not None:
            popup(draw, p, self.choice[0], self.choice[1], self.choice[2])
        if self.dialog is not None:
            prompt(draw, p, 'SAVE SECTION', 'Choose a new filename', self.dialog, self.message, self.error)
        draw.swap()


class SectionPropertiesView:
    HELP = None

    def start(self, vm):
        global _active
        self.app = _active = SectionProperties(vm)
        vm.input_manager.reset(); self.app.draw(); return True

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
    return open_view(vm, 'sectionprops_view', SectionPropertiesView())
