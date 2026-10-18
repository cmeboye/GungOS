"""Beam Lab: model editor, section editor, diagrams, results and options in PicoLAB.

F1 Add, F2 Remove, F3 Options, F4 Plot and F5 Results are the main keys. The model
is solved again after every committed change. It stays in RAM while
PicoLAB runs; saving to the SD card is explicit.
"""
from picoware.system import buttons as keys
from engtools.ui import theme
from engtools.ui.forms import LineEdit, parse_number, erase_key
from engtools import units, cases
from . import model as bm
from . import items
from . import render

OPTIONS = ('New beam', 'Load cases', 'Combinations', 'Self-weight', 'Save', 'Open', 'Export CSV (Eggcel)', 'Export full CSV',
           'Conventions and keys')
UNDO_LIMIT = 12
MENU_PAGES = ('start', 'options', 'cases', 'combos', 'open')
ZOOMS = (1.0, 2.0, 4.0)
MODEL_TABS = ('Beams', 'Supports', 'Loads')
ADD_OPTIONS = (
    (('Member', 'member'), ('Section change', 'split'), ('Hinge', 'hinge')),
    tuple((name, 'support') for name in bm.SUPPORTS),
    (('Point load', 'point'), ('Moment', 'moment'), ('Distributed load', 'dist')),
)
HELP = (
    'Help:',
    'UP/DOWN scroll  LEFT/RIGHT page',
    'CTRL+UP/DOWN first/last; F9/ESC close',
    'Main keys:',
    'F1 Add at cursor  F2 Remove selected item',
    'F3 Options  F4 Plot  F5 Results',
    'F9 or ? opens help; edits stay intact',
    'ESC returns; from model items leaves Lab',
    'Model navigation:',
    'LEFT/RIGHT Beams / Supports / Loads tabs',
    'Changing tabs keeps the insertion point',
    'UP/DOWN browse items; ENTER properties',
    'TAB or ] next beam  [ previous beam',
    ', / . previous/next point on that beam',
    '< / > also step points (shifted , / .)',
    'Points: ends, joints, supports and loads',
    'B1/B2... Start/End shows the Add target',
    'ENTER opens a property; ESC returns',
    '+ or = zoom in  - zoom out (1x/2x/4x)',
    'Model shortcuts:',
    'B add member  C split / section change',
    'S support  H hinge',
    'P point load  M moment  W distributed load',
    'F2 remove selected item  Z undo (12 steps)',
    'BACK/DEL on heading also removes item',
    'Adding reuses the joint at the cursor',
    'A new member starts in a free direction',
    'Edit its length and angle (0 right, 90 up)',
    'Point forces: edit Angle in degrees',
    '0 right 90 up 180 left 270 down',
    'Force Angle is global; negative P reverses',
    'Text / numeric entry:',
    'ENTER apply  ESC cancel  TAB apply',
    'UP/DOWN apply and move to another value',
    'LEFT/RIGHT caret  END last character',
    'BACK and DEL erase before the caret',
    'Type a number to replace a numeric value',
    'Arithmetic works: 6/4, 2*pi',
    'Choice / Add menus:',
    'UP/DOWN choose  ENTER apply  ESC cancel',
    'Section editor:',
    'ENTER on Edit section opens its preview',
    'UP/DOWN select value; ENTER edit/choose',
    'ESC returns to model; F9 preserves edits',
    'Plots (F4):',
    'LEFT/RIGHT move  , / . move ten steps',
    'UP/DOWN previous/next point',
    'TAB next peak  ENTER pin (up to 8)',
    'V or SPACE next case / combination',
    'D third diagram / whole-frame quantity',
    'M or ] next beam  [ previous beam',
    'B2/3 identifies the inspected beam',
    'x measures distance from that beam start',
    'Plots/peaks cover only the chosen beam',
    'F whole-frame view; active beam highlighted',
    'ESC returns to model',
    'Results (F5):',
    'UP/DOWN browse  ENTER open peak/pin',
    'V next view  F2 or BACK/DEL unpins a pin',
    'ESC returns to model',
    'Options and files (F3):',
    'UP/DOWN choose  ENTER open  ESC return',
    'Cases: ENTER rename or add; F2 removes',
    'Combinations: ENTER edit/add; F2 removes',
    'Factors: type or ENTER edit; ESC return',
    'Export CSV (Eggcel): sampled, <=511 cells',
    'Export full CSV: every diagram sample',
    'Signs and units:',
    'Loads positive along their direction',
    'Moments ccw +; settlement down +',
    'Reactions up and right +; tension +',
    'Sagging M +; V = dM/dx',
    'm, kN, kNm, kN/m, GPa, cm4, mm, mrad',
    'Euler-Bernoulli; small deflections',
)

_kept = None  # model, undo, view and pins while PicoLAB stays open
_active = None


class BeamLab:
    def __init__(self, vm):
        self.vm = vm
        kept = _kept or {}
        self.model = kept.get('model')
        self.undo = kept.get('undo', [])
        self.view = kept.get('view', 0)
        self.pins = kept.get('pins', [])
        self.pin_beams = kept.get('pin_beams', {})
        self.page = 'model' if self.model else 'start'
        self.line, self.s = 0, 0.0
        self.member = 0
        self.sel = None  # (ref, field id or None)
        self.model_tab = 0
        self.tab_selections = [None] * len(MODEL_TABS)
        self.edit = None
        self.popup = None  # [title, options, index, apply]
        self.prompt = None  # dict(title, detail, edit, apply, message)
        self.message, self.error = '', False
        self.menu_index = 0
        self.files = []
        self.combo = None
        self.section, self.section_row = None, 0
        self.help_first = 0
        self.zoom = 0
        self.help_open = False
        self.solution, self.problem = None, None
        self.peaks = {}
        self.dline, self.ds, self.third, self.cache = 0, 0.0, 'W', None
        self.dmember = 0
        self.tab, self.note, self.whole, self.quantity = -1, '', False, 0
        self.confirm = None
        if self.model:
            self.resolve()
            self.select_point(0, 0.0)

    # ------------------------------------------------------------ state

    def keep(self):
        global _kept
        _kept = {'model': self.model, 'undo': self.undo[-UNDO_LIMIT:], 'view': self.view, 'pins': self.pins, 'pin_beams': self.pin_beams}

    def close(self):
        self.keep()
        if self.solution is not None:
            self.solution.free()
            self.solution = None

    def palette(self):
        return theme.system_palette(self.vm)

    def say(self, message, error=False):
        self.message, self.error = message, error

    def snapshot(self):
        self.undo.append(items.copy(self.model))
        if len(self.undo) > UNDO_LIMIT:
            del self.undo[0]

    def undo_last(self):
        if not self.undo:
            raise ValueError('Nothing to undo')
        self.model = self.undo.pop()
        self.tab_selections = [None] * len(MODEL_TABS)
        self.resolve()
        self.sel = None
        self.select_point(self.line, self.s)
        self.say('Undone')

    def resolve(self):
        if self.solution is not None:
            self.solution.free()
        self.solution, self.problem, self.cache, self.peaks = None, None, None, {}
        try:
            self.solution = bm.Solution(self.model)
        except bm.ModelError as exc:
            self.problem = exc
        except MemoryError:
            self.problem = bm.ModelError('Not enough memory for this model')
        views = len(self.model['cases']) + len(self.model['combos'])
        self.view = min(self.view, views - 1)
        runs = bm.lines(self.model)
        self.line = min(self.line, len(runs) - 1)
        self.dline = min(self.dline, len(runs) - 1)
        self.s = min(self.s, self.line_length(self.line))
        self.dmember = min(self.dmember, len(self.model['members'])-1)
        self.inspect_member(self.dmember, self.ds)

    def line_length(self, line):
        return bm.line_offsets(self.model, bm.lines(self.model)[line])[1]

    def extremes(self, line):
        k = (line, self.view)
        if k not in self.peaks:
            self.peaks[k] = self.solution.extremes(line, self.view)
        return self.peaks[k]

    def replace_model(self, model):
        if self.model is not None:
            self.snapshot()
        self.model = model
        self.model_tab, self.tab_selections = 0, [None] * len(MODEL_TABS)
        self.pin_beams = {}
        self.view, self.pins, self.ds, self.dline, self.zoom = len(model['cases']), [], 0.0, 0, 0
        self.line, self.s, self.sel, self.member, self.dmember = 0, 0.0, None, 0, 0
        self.resolve()
        self.select_point(0, 0.0)
        self.page = 'model'

    # ------------------------------------------------------------ model rows

    @staticmethod
    def ref_tab(ref):
        return 1 if ref[0] == 'support' else 2 if ref[0] == 'load' else 0

    def tab_refs(self, tab=None):
        """All model items in one tab, independent of cursor position."""
        tab = self.model_tab if tab is None else tab
        if tab == 1:
            return [('support', obj) for obj in self.model['supports']]
        if tab == 2:
            return [('load', obj) for obj in self.model['loads']]
        refs = [('member', i) for i in range(len(self.model['members']))]
        if not bm.is_straight_beam(self.model):
            used = sorted(set(j for m in self.model['members'] for j in (m['a'], m['b'])))
            refs += [('joint', i) for i in used]
        refs += [('hinge', obj) for obj in self.model['hinges']]
        return refs

    def switch_model_tab(self, step):
        self.tab_selections[self.model_tab] = self.sel
        self.model_tab = (self.model_tab + step) % len(MODEL_TABS)
        refs = self.tab_refs()
        selected = self.tab_selections[self.model_tab]
        if selected is None or not any(items.same(selected[0], ref) for ref in refs):
            selected = (refs[0], None) if refs else None
        # A category change restores its row, but never moves the Add target.
        self.sel = selected

    def cursor_member(self, runs=None):
        """Keep the chosen member at a shared joint, including collinear ones."""
        runs = runs or bm.lines(self.model)
        if 0 <= self.member < len(self.model['members']):
            line, offset = items.line_of(self.model, self.member, runs)
            length = bm.member_length(self.model, self.member)
            if line == self.line and offset - 1e-6 <= self.s <= offset + length + 1e-6:
                return self.member
        return items.locate(self.model, self.line, self.s, runs)[0]

    def cursor_label(self):
        member = self.cursor_member()
        line, offset = items.line_of(self.model, member)
        x = self.s - offset
        length = bm.member_length(self.model, member)
        point = 'Start' if x <= 1e-6 else 'End' if length - x <= 1e-6 else units.show(x, 'm')
        return 'B%d %s' % (member + 1, point)

    def cycle_member(self, step):
        runs = bm.lines(self.model)
        member = (self.cursor_member(runs) + step) % len(self.model['members'])
        line, offset = items.line_of(self.model, member, runs)
        self.member = member
        self.select_point(line, offset)
        if self.model_tab == 0:
            self.sel = (('member', member), None)
            self.tab_selections[0] = self.sel

    def move_point(self, step):
        runs = bm.lines(self.model)
        member = self.cursor_member(runs)
        line, offset = items.line_of(self.model, member, runs)
        end = offset + bm.member_length(self.model, member)
        points = [s for s in items.stops(self.model, line, runs) if offset <= s <= end]
        i = min(range(len(points)), key=lambda j: abs(points[j] - self.s))
        self.member = member
        self.select_point(line, points[min(max(i + step, 0), len(points) - 1)])

    def row_title(self, ref):
        kind, obj = ref
        title = items.title(self.model, ref)
        if kind in ('support', 'load', 'hinge'):
            group = {'support': 'supports', 'load': 'loads', 'hinge': 'hinges'}[kind]
            index = next(i for i, value in enumerate(self.model[group]) if value is obj) + 1
            if kind == 'support':
                title = '%d. %s at %s' % (index, obj['kind'], units.show(items.along(self.model, obj), 'm'))
            else:
                title = '%d. %s' % (index, title)
        return title

    def rows(self):
        """(kind, label, value, editable, ref, field) in the selected tab."""
        out = []
        expanded = self.sel[0] if self.sel and self.sel[1] is not None else None
        refs = self.tab_refs()
        if expanded is not None:
            refs = [ref for ref in refs if items.same(ref, expanded)]
        for ref in refs:
            out.append(('head', self.row_title(ref), '', True, ref, None))
            if items.same(ref, expanded):
                for f in items.fields(self.model, ref):
                    out.append(('field', f[1], items.text(self.model, ref, f), f[4], ref, f))
        return out

    def row_index(self, rows):
        if not self.sel:
            return -1
        ref, field = self.sel
        for i, row in enumerate(rows):
            if items.same(row[4], ref) and (row[5][0] if row[5] else None) == field:
                return i
        for i, row in enumerate(rows):
            if items.same(row[4], ref):
                return i
        return 0 if rows else -1

    def select_point(self, line, s):
        runs = bm.lines(self.model)
        line = min(max(line, 0), len(runs) - 1)
        points = items.stops(self.model, line, runs)
        self.line = line
        self.s = min(points, key=lambda p: abs(p - s))
        self.member = self.cursor_member(runs)
        refs = self.tab_refs()
        here = items.items_at(self.model, line, self.s, runs)
        if self.sel and any(items.same(ref, self.sel[0]) for ref in refs) and \
                any(items.same(ref, self.sel[0]) for ref in here):
            return
        chosen = next((ref for ref in refs if any(items.same(ref, local) for local in here)), None)
        if chosen is None and self.sel and any(items.same(ref, self.sel[0]) for ref in refs):
            self.tab_selections[self.model_tab] = self.sel
            return
        if chosen is None and refs:
            chosen = refs[0]
        self.sel = (chosen, None) if chosen else None
        self.tab_selections[self.model_tab] = self.sel

    def focus(self, ref, field=None):
        """Put the cursor where an item is and select it (or one of its fields)."""
        kind, obj = ref
        target_tab = self.ref_tab(ref)
        if target_tab != self.model_tab:
            self.tab_selections[self.model_tab] = self.sel
            self.model_tab = target_tab
        runs = bm.lines(self.model)
        if kind == 'joint':
            for m, member in enumerate(self.model['members']):
                if obj in (member['a'], member['b']):
                    line, offset = items.line_of(self.model, m, runs)
                    s = offset + (0.0 if member['a'] == obj else bm.member_length(self.model, m))
                    break
        elif kind == 'member':
            m = obj
            line, offset = items.line_of(self.model, obj, runs)
            s = offset + (bm.member_length(self.model, obj) if field in ('length', 'angle') and
                          len(self.model['members']) > 1 else 0.0)
        else:
            m = obj['m']
            line, offset = items.line_of(self.model, m, runs)
            s = offset + (obj['x2'] if field == 'x2' else obj['x'])
        self.sel = (ref, field)
        self.tab_selections[self.model_tab] = self.sel
        self.line, self.member = line, m
        points = items.stops(self.model, line, runs)
        self.s = min(points, key=lambda p: abs(p - s))

    def move_row(self, step):
        rows = self.rows()
        if not rows:
            return
        index = min(max(self.row_index(rows) + step, 0), len(rows) - 1)
        row = rows[index]
        self.focus(row[4], row[5][0] if row[5] else None)

    def current(self):
        rows = self.rows()
        index = self.row_index(rows)
        return rows[index] if index >= 0 else None

    def begin_edit(self, first=None):
        row = self.current()
        if row is None or row[0] != 'field' or not row[3]:
            raise ValueError('This value is worked out for you' if row and row[0] == 'field' else 'Choose a value first')
        ref, f = row[4], row[5]
        if f[2] == 'action':
            self.open_section(self.model['sections'][self.model['members'][ref[1]]['section']])
            return
        if f[2] == 'choice':
            options = items.choices(self.model, ref, f[0])

            def apply(index, ref=ref, field=f[0]):
                self.snapshot()
                items.set_choice(self.model, ref, field, index)
                self.changed(ref, field)
                if field == 'section' and index == len(options) - 1:
                    self.open_section(self.model['sections'][self.model['members'][ref[1]]['section']])
                    self.say('New section: edit it here')
            self.popup = [f[1], options, items.choice_index(self.model, ref, f[0]), apply]
            return
        if first is None:
            value = items.get(self.model, ref, f[0])
            shown = value if f[3] == 'deg' else units.from_si(value, f[3])
            self.edit = LineEdit(units.number(shown, 7), 24)
        else:
            self.edit = LineEdit('', 24)
            self.edit.key(self.vm, first)

    def commit_edit(self):
        row = self.current()
        ref, f = row[4], row[5]
        value = parse_number(self.edit.text)
        before = items.copy(self.model)
        items.set_number(self.model, ref, f[0], f[3], value)
        self.undo.append(before)
        if len(self.undo) > UNDO_LIMIT:
            del self.undo[0]
        self.edit = None
        self.changed(ref, f[0])

    def changed(self, ref, field=None):
        self.resolve()
        self.focus(ref, field)

    def open_section(self, section):
        self.section, self.section_row, self.page = section, 1, 'section'

    # ------------------------------------------------------------ keys

    def run(self, button):
        if button == keys.BUTTON_NONE:
            return False
        try:
            self.handle(button)
        except (ValueError, TypeError, ZeroDivisionError, OverflowError, RuntimeError, OSError, MemoryError) as exc:
            self.say(str(exc) or 'Not possible here', True)
        return True

    @property
    def footer_height(self):
        return 12

    def properties_rect(self):
        return (8,render.PROPERTIES_TOP,int(self.vm.draw.size.x)-16,
                int(self.vm.draw.size.y)-self.footer_height-render.PROPERTIES_TOP-3)

    def insert_item(self,kind,support_type=None):
        undo_before = self.undo[:]
        self.snapshot()
        try:
            ref,field=items.insert(self.model,kind,self.line,self.s,self.cursor_member())
            if support_type is not None:
                items.set_choice(self.model,ref,'kind',support_type)
        except ValueError:
            self.undo = undo_before
            raise
        self.tab_selections = [None] * len(MODEL_TABS)
        self.resolve();self.focus(ref,field)
        self.say({'split':'Split here with its own section: ENTER changes it',
                  'member':'New member: length, then angle'}.get(kind,'Added: type its position, or move on'))

    def handle(self, button):
        if button==keys.BUTTON_F9:
            if self.help_open:self.help_open=False
            else:self.open_help()
            return
        esc = button == self.vm.input_manager._key_esc
        if self.help_open:
            self.key_help(button,esc)
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
                if self.page == 'section':
                    self.commit_section()
                else:
                    self.commit_edit()
                if result in ('up', 'down'):
                    if self.page == 'section':
                        self.move_section(-1 if result == 'up' else 1)
                    else:
                        self.move_row(-1 if result == 'up' else 1)
            return
        self.message, self.error = '', False
        page = {keys.BUTTON_F3: 'options', keys.BUTTON_F4: 'diagrams',
                keys.BUTTON_F5: 'results'}.get(button)
        if page and self.model is not None:
            if page in ('options', 'results'):
                self.menu_index = 0
            if page == 'diagrams' and self.page == 'model':
                self.inspect_member(self.cursor_member(), self.s)
            self.page = page
            return
        if self.vm.input_manager.button_to_char(button) == '?':
            self.open_help()
            return
        if button==keys.BUTTON_F1 and self.page=='model':
            tab=self.model_tab
            choices=ADD_OPTIONS[tab]
            def add(index,tab=tab,choices=choices):
                self.insert_item(choices[index][1],index if tab==1 else None)
            title=('Add beam','Add support','Add load')[tab]
            self.popup=[title+' / '+self.cursor_label(),tuple(label for label,kind in choices),0,add]
            return
        getattr(self, 'key_' + self.page)(button, esc)

    def char(self, button):
        c = self.vm.input_manager.button_to_char(button)
        return c.lower() if c else ''

    def remove_selected(self):
        if self.sel is None:
            raise ValueError('Nothing to remove here')
        undo_before = self.undo[:]
        self.snapshot()
        try:
            items.delete(self.model, self.sel[0])
        except ValueError:
            self.undo = undo_before
            raise
        self.tab_selections = [None] * len(MODEL_TABS)
        self.resolve()
        self.sel = None
        self.select_point(self.line, self.s)
        self.say('Removed: Z undoes')

    def key_model(self, button, esc):
        if esc:
            if self.sel and self.sel[1] is not None:
                self.focus(self.sel[0])
                return
            self.vm.back()
            return
        c = self.char(button)
        if button == keys.BUTTON_F2:
            self.remove_selected()
        elif button in (keys.BUTTON_LEFT, keys.BUTTON_RIGHT):
            self.switch_model_tab(-1 if button == keys.BUTTON_LEFT else 1)
        elif c in (',', '.', '<', '>'):
            self.move_point(1 if c in ('.', '>') else -1)
        elif button == keys.BUTTON_TAB or c in ('[', ']'):
            self.cycle_member(-1 if c == '[' else 1)
        elif button in (keys.BUTTON_UP, keys.BUTTON_DOWN):
            self.move_row(-1 if button == keys.BUTTON_UP else 1)
        elif button == keys.BUTTON_CENTER:
            row = self.current()
            if row is not None and row[0] == 'head':
                fields = items.fields(self.model, row[4])
                editable = [f for f in fields if f[4]]
                self.focus(row[4], (editable or fields)[0][0])
            else:
                self.begin_edit()
        elif erase_key(self.vm, button):
            row = self.current()
            if row is None:
                raise ValueError('Nothing to remove here')
            if row[0] == 'field':
                if row[5][2] != 'num':
                    raise ValueError('Select the item heading to remove it')
                self.begin_edit()
                self.edit.key(self.vm, button)
                return
            self.remove_selected()
        elif c == 'z':
            self.undo_last()
        elif c in ('+', '='):
            self.zoom = min(self.zoom + 1, len(ZOOMS) - 1)
        elif c == '-':
            self.zoom = max(self.zoom - 1, 0)
        elif c in items.INSERT_KEYS:
            self.insert_item(items.INSERT_KEYS[c])
        elif c and (c.isdigit() or c in '-.('):
            self.begin_edit(button)

    # ------------------------------------------------------------ section editor

    def section_rows(self):
        return items.section_fields(self.section)

    def move_section(self, step):
        rows = self.section_rows()
        self.section_row = min(max(self.section_row + step, 0), len(rows) - 1)

    def commit_section(self):
        row = self.section_rows()[self.section_row]
        value = parse_number(self.edit.text)
        before = items.copy(self.model)
        items.section_number(self.section, row[0], row[3], value)
        self.undo.append(before)
        self.edit = None
        self.resolve()

    def key_section(self, button, esc):
        if esc:
            self.page = 'model'
            return
        rows = self.section_rows()
        self.section_row = min(self.section_row, len(rows) - 1)
        row = rows[self.section_row]
        c = self.char(button)
        if button in (keys.BUTTON_UP, keys.BUTTON_DOWN):
            self.move_section(-1 if button == keys.BUTTON_UP else 1)
        elif button == keys.BUTTON_CENTER or (c and (c.isdigit() or c in '.(') and row[2] == 'num') or \
                (erase_key(self.vm, button) and row[2] == 'num'):
            if not row[4]:
                raise ValueError('Set by the material: choose Custom to type it')
            if row[2] == 'text':
                section = self.section

                def apply(value):
                    self.snapshot()
                    items.rename_section(self.model, section, value)
                self.prompt = {'title': 'Section name', 'detail': 'Up to 8 letters, for example IPE300 or Col.',
                               'edit': LineEdit(section['name'], 8), 'apply': apply, 'message': ''}
            elif row[2] == 'choice':
                section = self.section

                def choose(index, field=row[0]):
                    self.snapshot()
                    items.section_choice(section, field, index)
                    self.resolve()
                options = items.section_choices(row[0])
                current = section['material'] if row[0] == 'material' else bm.SHAPES.index(section['shape'])
                self.popup = [row[1], options, current, choose]
            elif button == keys.BUTTON_CENTER:
                value = units.from_si(items.section_get(self.section, row[0]), row[3])
                self.edit = LineEdit(units.number(value, 7), 16)
            else:
                self.edit = LineEdit(units.number(units.from_si(items.section_get(self.section, row[0]), row[3]), 7)
                                     if erase_key(self.vm, button) else '', 16)
                self.edit.key(self.vm, button)

    # ------------------------------------------------------------ diagrams

    def plot_bounds(self):
        line, start = items.line_of(self.model, self.dmember)
        return start, start + bm.member_length(self.model, self.dmember)

    def inspect_member(self, member, s=None):
        self.dmember = member
        self.dline, start = items.line_of(self.model, member)
        end = start + bm.member_length(self.model, member)
        self.ds = start if s is None else min(max(s, start), end)
        self.cache, self.tab, self.note = None, -1, ''

    def cycle_plot_member(self, step):
        self.inspect_member((self.dmember + step) % len(self.model['members']))

    def plot_title(self):
        start, end = self.plot_bounds()
        return 'B%d/%d  x=%s' % (self.dmember+1, len(self.model['members']), units.show(self.ds-start,'m'))

    def key_diagrams(self, button, esc):
        if esc:
            self.page = 'model'
            return
        if self.solution is None:
            raise ValueError('Fix the model first (ESC)')
        start, end = self.plot_bounds()
        c = self.char(button)
        step = (end-start) / (render.RIGHT - render.LEFT)
        if button in (keys.BUTTON_LEFT, keys.BUTTON_RIGHT) or c in (',', '.', '<', '>'):
            sign = -1 if button == keys.BUTTON_LEFT or c in (',', '<') else 1
            self.ds = min(max(self.ds + sign * step * (10 if c else 1), start), end)
            self.note, self.tab = '', -1
        elif button in (keys.BUTTON_UP, keys.BUTTON_DOWN):
            points = [s for s in items.stops(self.model, self.dline) if start <= s <= end]
            if button == keys.BUTTON_DOWN:
                later = [p for p in points if p > self.ds + 1e-9]
                self.ds = later[0] if later else end
            else:
                earlier = [p for p in points if p < self.ds - 1e-9]
                self.ds = earlier[-1] if earlier else start
            self.note, self.tab = '', -1
        elif button == keys.BUTTON_TAB:
            peaks = self.peak_list()
            self.tab = (self.tab + 1) % len(peaks)
            label, s, q = peaks[self.tab]
            self.ds, self.note = s, label
        elif button == keys.BUTTON_CENTER:
            if len(self.pins) >= 8:
                raise ValueError('Up to 8 pinned points; remove some in F5')
            if not any(line == self.dline and abs(s - self.ds) < 1e-9 for line, s in self.pins):
                self.pins.append((self.dline, self.ds))
                self.pins.sort()
            self.pin_beams[(self.dline,self.ds)] = self.dmember
            self.note = 'Pinned: see F5 Results'
        elif c == 'v' or button == keys.BUTTON_SPACE:
            self.next_view()
        elif c == 'd':
            if self.whole:
                self.quantity = (self.quantity + 1) % len(render.OVERVIEW)
            else:
                order = ('W', 'T', 'N') if not bm.is_straight_beam(self.model) else ('W', 'T')
                self.third = order[(order.index(self.third) + 1) % len(order)] if self.third in order else 'W'
                self.cache = None
        elif c in ('m', '[', ']'):
            self.cycle_plot_member(-1 if c == '[' else 1)
        elif c == 'f':
            self.whole = not self.whole

    def next_view(self):
        self.view = (self.view + 1) % (len(self.model['cases']) + len(self.model['combos']))
        self.cache = None
        self.tab = -1

    def peak_list(self):
        key = (self.dline,self.view,self.dmember)
        if key not in self.peaks:
            self.peaks[key] = self.solution.extremes(self.dline,self.view,self.dmember)
        ext = self.peaks[key]
        start, end = self.plot_bounds()
        out = []
        names = (('M', 'moment', 'kNm'), ('V', 'shear', 'kN'), ('N', 'normal', 'kN'), ('W', 'deflection', 'mm'),
                 ('T', 'slope', 'mrad'))
        for q, name, unit in names:
            hi, sh, lo, sl = ext[q]
            if abs(hi) > 1e-6:
                out.append(('max %s %s at %s m' % (name, units.show(hi, unit), units.number(sh-start)), sh, q))
            if abs(lo) > 1e-6:
                out.append(('min %s %s at %s m' % (name, units.show(lo, unit), units.number(sl-start)), sl, q))
        return out or [('No load effects in this view', start, 'M')]

    # ------------------------------------------------------------ results

    def key_results(self, button, esc):
        if esc:
            self.page = 'model'
            return
        rows = self.result_rows()
        selectable = self.result_index(rows)
        if not selectable:
            return
        if button in (keys.BUTTON_UP, keys.BUTTON_DOWN):
            at = selectable.index(self.menu_index) + (1 if button == keys.BUTTON_DOWN else -1)
            self.menu_index = selectable[at % len(selectable)]
            return
        action = rows[self.menu_index][4]
        if self.char(button) == 'v':
            self.next_view()
        elif button == keys.BUTTON_CENTER and action:
            if action[0] == 'view':
                self.next_view()
            elif action[0] in ('goto', 'pin'):
                member = action[3] if len(action)>3 else items.locate(self.model,action[1],action[2])[0]
                self.inspect_member(member,action[2])
                self.page, self.whole = 'diagrams', False
        elif (button == keys.BUTTON_F2 or erase_key(self.vm, button)) and action and action[0] == 'pin':
            self.pins.remove((action[1], action[2]))
            self.pin_beams.pop((action[1],action[2]),None)

    def result_index(self, rows):
        """Selectable rows (headings are not); keeps menu_index on one."""
        selectable = [i for i, r in enumerate(rows) if r[1] is not None or r[2]]
        if selectable and self.menu_index not in selectable:
            self.menu_index = selectable[0]
        return selectable

    def where(self, X, Y):
        if bm.is_straight_beam(self.model):
            return 'x = ' + units.show(X - bm.bounds(self.model)[0], 'm')
        return '(%s, %s) m' % (units.number(X), units.number(Y))

    def result_rows(self):
        """(label, value, detail, color, action) rows for F5."""
        sol = self.solution
        if sol is None:
            return [('Model problem', None, str(self.problem), None, None)]
        straight = bm.is_straight_beam(self.model)
        rows = [('View', sol.view_names()[self.view][:16], 'ENTER or V: next case or combination', None, ('view',)),
                ('Reactions', None, '', None, None)]
        for n, (support, fx, fy, mz) in enumerate(sol.reactions(self.view)):
            X, Y = bm.point(self.model, support['m'], support['x'])
            detail = support['kind'] + ' at ' + self.where(X, Y)
            flags = bm.SUPPORT_FLAGS[support['kind']]
            if 'x' in flags or (support['kind'] == 'Spring' and support['kx'] > 0):
                if not straight or abs(fx) > 1e-6:
                    detail += '  H ' + units.show(fx, 'kN')
            if 'r' in flags or (support['kind'] == 'Spring' and support['kr'] > 0):
                detail += '  M ' + units.show(mz, 'kNm')
            value = units.show(fy, 'kN') if 'y' in flags or support['kind'] == 'Spring' else '--'
            line, offset = items.line_of(self.model, support['m'])
            rows.append(('R%d' % (n + 1), value, detail, None, ('goto', line, offset + support['x'])))
        ax, ay = sol.applied(self.view)
        tx = sum(r[1] for r in sol.reactions(self.view))
        ty = sum(r[2] for r in sol.reactions(self.view))
        size = max(1.0, abs(ax), abs(ay))
        ok = abs(tx + ax) <= 1e-4 * size and abs(ty + ay) <= 1e-4 * size
        detail = 'Sum R %s, loads %s' % (units.show(ty, 'kN'), units.show(-ay, 'kN'))
        if not straight:
            detail = 'R (%s, %s) kN, loads (%s, %s)' % (units.number(tx / 1e3), units.number(ty / 1e3),
                                                         units.number(-ax / 1e3), units.number(-ay / 1e3))
        rows.append(('Equilibrium', 'OK' if ok else 'CHECK', detail, None if ok else theme.ERROR, None))
        names = (('M', 'moment', 'kNm'), ('V', 'shear', 'kN'), ('W', 'deflection', 'mm'), ('T', 'slope', 'mrad'))
        if not straight:
            names = (('M', 'moment', 'kNm'), ('V', 'shear', 'kN'), ('N', 'normal force', 'kN'), ('W', 'deflection', 'mm'))
        for line in range(len(sol.lines)):
            run = sol.lines[line]
            heading = 'Peaks' if straight else 'Members ' + ', '.join(str(m + 1) for m in run)
            rows.append((heading, None, '', None, None))
            ext = self.extremes(line)
            for q, name, unit in names:
                hi, sh, lo, sl = ext[q]
                rows.append(('Max ' + name, units.show(hi, unit), 'at s = ' + units.show(sh, 'm'), None, ('goto', line, sh)))
                rows.append(('Min ' + name, units.show(lo, unit), 'at s = ' + units.show(sl, 'm'), None, ('goto', line, sl)))
            sigma, ss, m = sol.stress(line, self.view)
            rows.append(('Max stress', units.show(sigma, 'MPa', 3), 'N/A + M/W at s = %s, member %d' % (units.show(ss, 'm'), m + 1),
                         None, ('goto', line, ss)))
        ratio = sol.deflection_ratio(self.view)
        if ratio:
            rows.append(('Span / deflection', 'L/%d' % int(ratio[0]), 'worst span ' + units.show(ratio[1], 'm'), None, None))
        if self.pins:
            rows.append(('Pinned points', None, '', None, None))
            for line, s in self.pins:
                if line >= len(sol.lines):
                    continue
                member = self.pin_beams.get((line,s))
                if member is None or member not in sol.lines[line]:
                    member = items.locate(self.model,line,s)[0]
                member_line, offset = items.line_of(self.model,member)
                x = min(max(s-offset,0.0),bm.member_length(self.model,member))
                V, M, T, W, N, U = sol.at(member,x,self.view)
                label = 'B%d x = ' % (member+1) + units.show(x, 'm')
                rows.append((label, units.show(M, 'kNm'), 'V ' + units.show(V, 'kN') + '  w ' + units.show(W, 'mm') +
                             ('' if straight else '  N ' + units.show(N, 'kN')) + '  F2 unpins', None, ('pin', line, s, member)))
        info = sol.info
        rows.append(('Solver', None, '', None, None))
        rows.append(('Equations', str(info['equations']), '%s precision, %d KB' % (info['precision'], info['bytes'] // 1024 + 1),
                     None, None))
        return rows

    # ------------------------------------------------------------ menus

    def key_options(self, button, esc):
        if esc:
            self.page = 'model'
            return
        if self.menu(button, len(OPTIONS)):
            return
        if button != keys.BUTTON_CENTER:
            return
        option = OPTIONS[self.menu_index]
        if option == 'New beam':
            self.page, self.menu_index = 'start', 0
        elif option == 'Load cases':
            self.page, self.menu_index = 'cases', 0
        elif option == 'Combinations':
            self.page, self.menu_index = 'combos', 0
        elif option == 'Self-weight':
            self.snapshot()
            current = self.model.get('selfweight')
            nxt = 0 if current is None else current + 1
            self.model['selfweight'] = nxt if nxt < len(self.model['cases']) else None
            self.resolve()
        elif option == 'Save':
            self.ask_save()
        elif option == 'Open':
            self.files = cases.list_cases(self.vm.storage)
            self.page, self.menu_index = 'open', 0
        elif option in ('Export CSV (Eggcel)', 'Export full CSV'):
            self.export(compact=option == 'Export CSV (Eggcel)')
        else:
            self.open_help()

    def menu(self, button, count):
        if button in (keys.BUTTON_UP, keys.BUTTON_DOWN) and count:
            self.menu_index = (self.menu_index + (1 if button == keys.BUTTON_DOWN else -1)) % count
            return True
        return False

    def key_start(self, button, esc):
        count = len(bm.TEMPLATES) + 1
        if esc:
            if self.model is None:
                self.vm.back()
            else:
                self.page = 'options'
            return
        if self.menu(button, count) or button != keys.BUTTON_CENTER:
            return
        if self.menu_index == len(bm.TEMPLATES):
            self.files = cases.list_cases(self.vm.storage)
            self.page, self.menu_index = 'open', 0
            return
        had = self.model is not None
        self.replace_model(bm.template(self.menu_index))
        if had:
            self.say('New beam: Z brings the last one back')

    def key_open(self, button, esc):
        if esc:
            self.page = 'options' if self.model else 'start'
            self.menu_index = 0
            return
        if self.menu(button, len(self.files)) or button != keys.BUTTON_CENTER or not self.files:
            return
        name = self.files[self.menu_index]
        loaded = bm.upgrade(cases.load_case(self.vm.storage, name, 'beams'))
        loaded['name'] = name
        loaded.setdefault('selfweight', None)
        bm.check(loaded)
        self.replace_model(loaded)
        self.say('Opened ' + name)

    def key_cases(self, button, esc):
        names = self.model['cases']
        if esc:
            self.page, self.menu_index = 'options', OPTIONS.index('Load cases')
            return
        if self.menu(button, len(names) + 1):
            return
        index = self.menu_index = min(self.menu_index, len(names))
        if button == keys.BUTTON_CENTER:
            if index == len(names):
                self.snapshot()
                items.add_case(self.model, 'Case %d' % (len(names) + 1))
                if self.view >= len(names) - 1:
                    self.view += 1  # stay on the same combination
                self.resolve()
                self.rename_case(len(names) - 1)
            else:
                self.rename_case(index)
        elif (button == keys.BUTTON_F2 or erase_key(self.vm, button)) and index < len(names):
            self.snapshot()
            try:
                items.remove_case(self.model, index)
            except ValueError:
                self.undo.pop()
                raise
            if self.view > index:
                self.view -= 1
            elif self.view == index:
                self.view = 0
            self.resolve()
            self.menu_index = min(index, len(self.model['cases']))

    def rename_case(self, index):
        def apply(value):
            value = value.strip()
            if not value:
                raise ValueError('Type a name')
            self.model['cases'][index] = value[:16]
        self.prompt = {'title': 'Load case name', 'detail': 'For example Dead, Live, Snow or Wind.',
                       'edit': LineEdit(self.model['cases'][index], 16), 'apply': apply, 'message': ''}

    def key_combos(self, button, esc):
        combos = self.model['combos']
        if esc:
            self.page, self.menu_index = 'options', OPTIONS.index('Combinations')
            return
        if self.menu(button, len(combos) + 1):
            return
        index = self.menu_index = min(self.menu_index, len(combos))
        if button == keys.BUTTON_CENTER:
            if index == len(combos):
                self.snapshot()
                items.add_combo(self.model)
                self.resolve()
            self.combo, self.page, self.menu_index = self.model['combos'][index], 'combo', 0
        elif (button == keys.BUTTON_F2 or erase_key(self.vm, button)) and index < len(combos):
            self.snapshot()
            del combos[index]
            self.resolve()
            self.menu_index = min(index, len(combos))

    def combo_rows(self):
        combo = self.combo
        rows = [('head', 'Combination', '', True, None, None),
                ('field', 'Name', combo['name'], True, None, ('name',))]
        for i, name in enumerate(self.model['cases']):
            rows.append(('field', name + ' factor', units.number(combo['factors'][i], 4), True, None, ('factor', i)))
        return rows

    def key_combo(self, button, esc):
        rows = self.combo_rows()
        if esc:
            self.page = 'combos'
            self.menu_index = self.model['combos'].index(self.combo)
            return
        index = min(max(self.menu_index, 1), len(rows) - 1)
        if button in (keys.BUTTON_UP, keys.BUTTON_DOWN):
            self.menu_index = min(max(index + (1 if button == keys.BUTTON_DOWN else -1), 1), len(rows) - 1)
            return
        field = rows[index][5]
        c = self.char(button)
        if field[0] == 'name' and button == keys.BUTTON_CENTER:
            def apply(value, combo=self.combo):
                value = value.strip()
                if not value:
                    raise ValueError('Type a name')
                combo['name'] = value[:16]
            self.prompt = {'title': 'Combination name', 'detail': 'For example ULS or SLS.',
                           'edit': LineEdit(self.combo['name'], 16), 'apply': apply, 'message': ''}
        elif field[0] == 'factor' and (button == keys.BUTTON_CENTER or (c and (c.isdigit() or c in '-.'))):
            i = field[1]
            if button == keys.BUTTON_CENTER:
                edit = LineEdit(units.number(self.combo['factors'][i], 7), 16)
            else:
                edit = LineEdit('', 16)
                edit.key(self.vm, button)

            def apply(value, combo=self.combo, i=i):
                factor = parse_number(value)
                self.snapshot()
                combo['factors'][i] = factor
                self.resolve()
            self.prompt = {'title': self.model['cases'][i] + ' factor',
                           'detail': 'Multiplies every load in this case. 0 leaves it out.',
                           'edit': edit, 'apply': apply, 'message': ''}

    def open_help(self):
        self.help_open, self.help_first = True, 0

    def key_help(self, button, esc):
        if esc or button in (keys.BUTTON_F9, keys.BUTTON_CENTER):
            self.help_open = False
            return
        capacity = render.help_capacity(int(self.vm.draw.size.y)-self.footer_height)
        last = max(0, len(HELP) - capacity)
        if button in (keys.BUTTON_UP, keys.BUTTON_DOWN):
            self.help_first += 1 if button == keys.BUTTON_DOWN else -1
        elif button in (keys.BUTTON_LEFT, keys.BUTTON_RIGHT):
            self.help_first += capacity if button == keys.BUTTON_RIGHT else -capacity
        elif button == keys.BUTTON_CTRL_UP:self.help_first = 0
        elif button in (keys.BUTTON_END,keys.BUTTON_CTRL_DOWN):self.help_first = last
        self.help_first = min(max(self.help_first, 0), last)

    # ------------------------------------------------------------ files

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
        self.prompt = {'title': 'Save beam as', 'detail': 'Saved to ' + cases.CASE_DIRECTORY + '. Letters, digits, - and _.',
                       'edit': LineEdit(self.model.get('name') or 'beam-1', cases.NAME_LIMIT), 'apply': apply, 'message': ''}

    def export(self, compact=True):
        if self.solution is None:
            raise ValueError('Fix the model before exporting')
        sol = self.solution

        def rows():
            for line in range(len(sol.lines)):
                S, V, M, T, W, N, U, starts = sol.samples(line, self.view)
                # Seven columns plus a header fit Eggcel's 512-cell budget:
                # 72 data rows + 1 header = 511 cells, shared across all runs.
                count = min(len(S), 72 // len(sol.lines) + (line < 72 % len(sol.lines))) if compact else len(S)
                for j in range(count):
                    i = j * (len(S) - 1) // (count - 1) if count > 1 else 0
                    yield (line + 1, S[i], V[i] / 1e3, M[i] / 1e3, N[i] / 1e3, T[i] * 1e3, W[i] * 1e3)
        stem = (self.model.get('name') or 'beam') + ('-eggcel' if compact else '-full')
        path = cases.free_path(self.vm.storage, cases.EXPORT_DIRECTORY, stem, 'csv')
        cases.export_csv(self.vm.storage, path, ('line', 's_m', 'V_kN', 'M_kNm', 'N_kN', 'slope_mrad', 'w_mm'), rows())
        self.say('Exported ' + path.rsplit('/', 1)[1] + (' (sampled)' if compact else ' (full)'))

    # ------------------------------------------------------------ drawing

    def draw(self):
        draw=self.vm.draw;p=self.palette()
        bottom=int(draw.size.y)-self.footer_height
        draw.fill_screen(p.BG)
        if self.help_open:
            render.chrome(draw,p,'Help')
            render.help_box(draw,p,HELP,self.help_first,bottom)
            draw.swap()
            return
        if self.page in MENU_PAGES:
            rows,subtitle=self.menu_rows()
            render.menu(draw,p,rows,self.menu_index,subtitle,bottom)
        elif self.page=='model':
            subtitle=self.draw_model(draw,p)
        elif self.page=='section':
            subtitle=self.draw_section(draw,p)
        else:
            subtitle='Beam / '+self.page
            render.panel(draw,p,(8,43,int(draw.size.x)-16,bottom-46),'' if self.page=='diagrams' else self.page.upper())
            bounded=render.Viewport(draw,(10,44,int(draw.size.x)-10,bottom-5))
            if self.page=='diagrams':
                subtitle=self.draw_diagrams(bounded,p)
            elif self.page=='results':
                rows=self.result_rows();self.result_index(rows)
                render.results(bounded,p,[r[:4] for r in rows],self.menu_index,67,bottom-7)
            elif self.page=='combo':
                render.form(bounded,p,[r[:4] for r in self.combo_rows()],max(1,self.menu_index),None,70,bottom-7)

        render.chrome(draw,p,subtitle.replace('Beam / ',''),self.message,self.error)
        box=self.properties_rect() if self.page in ('model','section') else None
        if self.popup is not None:
            title,options,index,apply=self.popup
            render.popup(draw,p,title,options,index,box)
        if self.prompt is not None:self.draw_prompt(draw,p)
        draw.swap()

    def draw_prompt(self,draw,p):
        q=self.prompt
        box=self.properties_rect() if self.page in ('model','section') else None
        render.prompt(draw,p,q['title'],q['detail'],q['edit'],q['message'] or 'ENTER saves  ESC cancels',
                      bool(q['message']),box)

    def menu_rows(self):
        if self.page == 'start':
            rows = [(name, detail) for name, detail in bm.TEMPLATES] + [('Open saved beam', 'From ' + cases.CASE_DIRECTORY)]
            return rows, 'Beam / new'
        if self.page == 'options':
            weight = self.model.get('selfweight')
            details = ('Start again from a template', ', '.join(self.model['cases']),
                       '%d combination(s)' % len(self.model['combos']),
                       'Off  (ENTER: add it to a load case)' if weight is None else
                       'In ' + self.model['cases'][weight] + '  (ENTER: next case or off)',
                       'Write this model to the SD card', 'Replace this model with a saved one',
                       'Diagram values of the current view', 'Signs, units and keys')
            return list(zip(OPTIONS, details)), 'Beam / options'
        if self.page == 'cases':
            rows = []
            for i, name in enumerate(self.model['cases']):
                used = sum(1 for load in self.model['loads'] if load['case'] == i)
                rows.append((name, '%d load(s)  ENTER renames  F2 removes' % used))
            rows.append(('+ Add load case', 'Up to %d cases' % bm.MAX_CASES))
            return rows, 'Beam / load cases'
        if self.page == 'combos':
            rows = [(c['name'], items.combo_text(self.model, c)) for c in self.model['combos']]
            rows.append(('+ Add combination', 'Factored sum of load cases'))
            return rows, 'Beam / combinations'
        rows = [(name, 'ENTER opens; this model stays in undo') for name in self.files]
        return rows or [('No saved models', 'Save one from Options first')], 'Beam / open'

    def summary(self):
        """Two short lines about the current view, or the problem."""
        if self.problem is not None:
            return render.wrap(str(self.problem), 52), True
        sol = self.solution
        name = sol.view_names()[self.view][:18]
        if bm.is_straight_beam(self.model):
            ext = self.extremes(0)
            w = max(abs(ext['W'][0]), abs(ext['W'][2]))
            v = max(abs(ext['V'][0]), abs(ext['V'][2]))
            first = '%s:  M %s / %s kNm' % (name, units.number(ext['M'][0] / 1e3), units.number(ext['M'][2] / 1e3))
            return [first, '|V| %s   |w| %s' % (units.show(v, 'kN'), units.show(w, 'mm'))], False
        peak = {'M': 0.0, 'N': 0.0, 'W': 0.0}
        for line in range(len(sol.lines)):
            ext = self.extremes(line)
            for q in peak:
                peak[q] = max(peak[q], abs(ext[q][0]), abs(ext[q][2]))
        return ['%s: |M| %s' % (name[:18],units.show(peak['M'],'kNm',3)),
                '|N| %s   |w| %s' % (units.show(peak['N'],'kN',3),units.show(peak['W'],'mm',3))],False

    def draw_model(self,draw,p):
        frame=render.layout(self.model);runs=bm.lines(self.model)
        here=items.cursor_point(self.model,self.line,self.s,runs)
        x,y,w,h=render.PREVIEW_RECT
        title='BEAM PREVIEW' if bm.is_straight_beam(self.model) else 'FRAME PREVIEW'
        render.panel(draw,p,render.PREVIEW_RECT,title,self.cursor_label()+'  %dx'%ZOOMS[self.zoom],p.PANEL)
        preview=render.Viewport(draw,(x+5,y+17,x+w-5,frame['bottom']))
        pp=theme.colors(p.PANEL,p.TEXT,p.ACCENT)
        view=render.View(self.model,frame['box'],ZOOMS[self.zoom],here)
        shape=render.deflected(self.model,self.solution,view,self.view) if self.solution is not None else None
        render.sketch(preview,pp,self.model,view,self.sel[0] if self.sel else None,(here,self.s),
                      self.problem,shape,runs[self.line],frame['bottom'],self.cursor_member(runs))
        draw._line(x+7,frame['bottom']+1,x+w-8,frame['bottom']+1,p.GRID)
        lines,bad=self.summary()
        summary=render.Viewport(draw,(x+7,frame['status'],x+w-7,y+h-3))
        render.status(summary,p,lines[:2],[p.ERROR if bad else p.MUTED]*2,frame['status'])
        rect=self.properties_rect();rows=self.rows();index=self.row_index(rows)
        render.model_tabs(draw,p,rect,MODEL_TABS,self.model_tab,[len(self.model['members']),len(self.model['supports']),len(self.model['loads'])])
        if rows:
            render.form(draw,p,[r[:4] for r in rows],index,self.edit,frame['list'],rect[1]+rect[3]-5)
        else:
            render.text(draw,rect[0]+10,rect[1]+30,'No '+MODEL_TABS[self.model_tab].lower()+' yet',p.MUTED)
            render.text(draw,rect[0]+10,rect[1]+44,'F1 adds an item; arrows change tabs',p.MUTED)
        return 'Beam / model'

    def draw_section(self,draw,p):
        section=self.section;rows=self.section_rows()
        self.section_row=min(self.section_row,len(rows)-1)
        field=rows[self.section_row][0]
        render.panel(draw,p,render.PREVIEW_RECT,'SECTION PREVIEW',section['name'],p.PANEL)
        preview=render.Viewport(draw,(14,64,306,157))
        pp=theme.colors(p.PANEL,p.TEXT,p.ACCENT)
        render.cross_section(preview,pp,section,field,(16,64,165,157),False)
        draw._line(171,65,171,156,p.GRID)
        render.section_panel(preview,pp,self.model,section,180,65)
        footer=render.Viewport(draw,(16,164,304,182))
        render.text(footer,16,165,section['shape']+'  |  dimensions in mm',p.MUTED)
        rect=self.properties_rect()
        render.panel(draw,p,rect,'SECTION PROPERTIES','%d/%d'%(self.section_row+1,len(rows)))
        form_rows=[('field',r[1],items.section_text(section,r),r[4]) for r in rows]
        render.form(draw,p,form_rows,self.section_row,self.edit,217,rect[1]+rect[3]-5)
        return 'Section '+section['name']

    def draw_diagrams(self, draw, p):
        subtitle = 'Beam / diagrams'
        if self.solution is None:
            for i, line in enumerate(render.wrap(str(self.problem), 48)):
                render.text(draw, 10, 70 + 11 * i, line, p.ERROR)
            render.text(draw, 10, 110, 'ESC opens the model to fix it.', p.MUTED)
            return subtitle
        sol = self.solution
        straight = bm.is_straight_beam(self.model)
        start, end = self.plot_bounds()
        left = sol.at(self.dmember, self.ds-start, self.view, -1)
        right = sol.at(self.dmember, self.ds-start, self.view, 1)

        def pair(q, unit):
            a, b = units.number(units.from_si(left[q], unit), 3), units.number(units.from_si(right[q], unit), 3)
            return a if a == b else a + '|' + b
        if straight:
            readout = 'V %s kN  M %s kNm  w %s mm  rot %s mrad' % (pair(0, 'kN'), pair(1, 'kNm'), pair(3, 'mm'),
                                                                 units.number(right[2] * 1e3, 3))
        else:
            readout = 'V %s kN  M %s kNm  N %s kN  w %s mm' % (pair(0, 'kN'), pair(1, 'kNm'), pair(4, 'kN'), pair(3, 'mm'))
        title = self.plot_title()
        if self.whole:
            render.diagram_header(draw,p,title,sol.view_names()[self.view],readout)
            render.overview(draw, p, self.model, sol, self.view, render.OVERVIEW[self.quantity],
                            bm.point(self.model, self.dmember, self.ds-start), self.dline, (40, 96, 280, 262),self.dmember)
            return subtitle
        panels = ('V', 'M', self.third)
        if self.cache is None:
            self.cache = render.diagram_cache(sol, self.dline, self.view, panels,int(draw.size.y)-self.footer_height-6,self.dmember)
        marks = []
        if self.tab >= 0:
            label, s, q = self.peak_list()[self.tab]
            marks.append((s, q))
        render.diagrams(draw, p, sol, self.dline, self.view, panels, self.cache, self.ds, readout, self.note, marks,
                        title,int(draw.size.y)-self.footer_height-6,self.dmember)
        return subtitle


class BeamLabView:
    def __init__(self):
        self.app = None

    def start(self, vm):
        global _active
        self.app = _active = BeamLab(vm)
        vm.input_manager.reset()
        self.app.draw()
        return True

    def run(self, vm):
        if self.app is not None and self.app.run(vm.button) and self.app is not None:
            self.app.draw()

    def stop(self, vm):
        global _active
        if self.app is not None:
            self.app.close()
        self.app = _active = None
        from gc import collect
        collect()


def show(vm):
    from engtools.plots.view import open_view
    return open_view(vm, 'beam_lab', BeamLabView())
