"""Beam Lab: model editor, section editor, diagrams, results and options in PicoLAB.

F3 Model, F4 Diagrams, F5 Results and F6 Options switch views. The model
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

OPTIONS = ('New beam', 'Load cases', 'Combinations', 'Self-weight', 'Save', 'Open', 'Export CSV',
           'Conventions and keys')
UNDO_LIMIT = 12
MENU_PAGES = ('start', 'options', 'cases', 'combos', 'open')
ZOOMS = (1.0, 2.0, 4.0)
HELP = (
    'Model (F3):',
    'LEFT/RIGHT move along the beam or member',
    'TAB next straight run of members (frames)',
    'UP/DOWN choose an item or a value',
    'Type a number, or ENTER to edit; 6/4 works',
    'S support  P point load  M moment',
    'W distributed load  H hinge',
    'B new member from here (length, angle)',
    'C section change: splits the member here',
    'DEL on an item heading removes it  Z undoes',
    '+ - zoom around the cursor',
    'Section (ENTER on Edit section):',
    'the cross-section to scale; the size you',
    'edit is highlighted, the axis is dashed',
    'Diagrams (F4):',
    'LEFT/RIGHT move  , . move faster',
    'UP/DOWN jump to the previous/next point',
    'TAB next peak  ENTER pin  V next view',
    'D slope / normal force  M next run',
    'F whole frame: moment, shear, N, shape',
    'Results (F5): ENTER opens a peak or pin',
    'Signs:',
    'Loads: forces and w along their direction +',
    '  (down, normal to member or right)',
    'Moments ccw +; settlement down +',
    'Reactions up and right +',
    'Sagging moment +; V = dM/dx; tension +',
    'Units: m, kN, kNm, kN/m, GPa, cm4, mm, mrad',
    'Euler-Bernoulli members; small deflections',
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
        self.page = 'model' if self.model else 'start'
        self.back_page = 'model'
        self.line, self.s = 0, 0.0
        self.sel = None  # (ref, field id or None)
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
        self.solution, self.problem = None, None
        self.peaks = {}
        self.dline, self.ds, self.third, self.cache = 0, 0.0, 'W', None
        self.tab, self.note, self.whole, self.quantity = -1, '', False, 0
        self.confirm = None
        if self.model:
            self.resolve()
            self.select_point(0, 0.0)

    # ------------------------------------------------------------ state

    def keep(self):
        global _kept
        _kept = {'model': self.model, 'undo': self.undo[-UNDO_LIMIT:], 'view': self.view, 'pins': self.pins}

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
        self.ds = min(self.ds, self.line_length(self.dline))

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
        self.view, self.pins, self.ds, self.dline, self.zoom = len(model['cases']), [], 0.0, 0, 0
        self.line, self.s, self.sel = 0, 0.0, None
        self.resolve()
        self.select_point(0, 0.0)
        self.page = 'model'

    # ------------------------------------------------------------ model rows

    def rows(self):
        """(kind, label, value, editable, ref, field) at the cursor."""
        out = []
        expanded = self.sel[0] if self.sel else None
        for ref in items.items_at(self.model, self.line, self.s):
            out.append(('head', items.title(self.model, ref), '', True, ref, None))
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
        here = items.items_at(self.model, self.line, self.s, runs)
        if self.sel and any(items.same(ref, self.sel[0]) for ref in here):
            return
        chosen = None
        for ref in here:
            if ref[0] not in ('member', 'joint'):
                chosen = ref
                break
        if chosen is None and here:
            chosen = here[0]
        self.sel = (chosen, None) if chosen else None

    def focus(self, ref, field=None):
        """Put the cursor where an item is and select it (or one of its fields)."""
        kind, obj = ref
        runs = bm.lines(self.model)
        if kind == 'joint':
            for m, member in enumerate(self.model['members']):
                if obj in (member['a'], member['b']):
                    line, offset = items.line_of(self.model, m, runs)
                    s = offset + (0.0 if member['a'] == obj else bm.member_length(self.model, m))
                    break
        elif kind == 'member':
            line, offset = items.line_of(self.model, obj, runs)
            s = offset + (bm.member_length(self.model, obj) if field in ('length', 'angle') and
                          len(self.model['members']) > 1 else 0.0)
        else:
            line, offset = items.line_of(self.model, obj['m'], runs)
            s = offset + (obj['x2'] if field == 'x2' else obj['x'])
        self.sel = (ref, field)
        self.line = line
        points = items.stops(self.model, line, runs)
        self.s = min(points, key=lambda p: abs(p - s))

    def move_row(self, step):
        rows = self.rows()
        if not rows:
            return
        index = min(max(self.row_index(rows) + step, 0), len(rows) - 1)
        row = rows[index]
        self.sel = (row[4], row[5][0] if row[5] else None)

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

    def handle(self, button):
        esc = button == self.vm.input_manager._key_esc
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
        page = {keys.BUTTON_F3: 'model', keys.BUTTON_F4: 'diagrams', keys.BUTTON_F5: 'results',
                keys.BUTTON_F6: 'options'}.get(button)
        if page and self.model is not None:
            if page in ('options', 'results'):
                self.menu_index = 0
            if page == 'diagrams' and self.page == 'model':
                self.dline, self.ds, self.cache = self.line, self.s, None
            self.page = page
            return
        if button == keys.BUTTON_F9 or (self.page != 'help' and self.vm.input_manager.button_to_char(button) == '?'):
            self.back_page, self.page, self.help_first = self.page, 'help', 0
            return
        getattr(self, 'key_' + self.page)(button, esc)

    def char(self, button):
        c = self.vm.input_manager.button_to_char(button)
        return c.lower() if c else ''

    def key_model(self, button, esc):
        if esc:
            self.vm.back()
            return
        c = self.char(button)
        if button in (keys.BUTTON_LEFT, keys.BUTTON_RIGHT):
            points = items.stops(self.model, self.line)
            i = min(range(len(points)), key=lambda j: abs(points[j] - self.s))
            i = min(max(i + (1 if button == keys.BUTTON_RIGHT else -1), 0), len(points) - 1)
            self.sel = None
            self.select_point(self.line, points[i])
        elif button == keys.BUTTON_TAB:
            runs = bm.lines(self.model)
            if len(runs) < 2:
                raise ValueError('One straight run here: B adds a member')
            here = items.cursor_point(self.model, self.line, self.s, runs)
            nxt = (self.line + 1) % len(runs)
            s = 0.0
            for p in items.stops(self.model, nxt, runs):
                if items.same_point(items.cursor_point(self.model, nxt, p, runs), here):
                    s = p
            self.sel = None
            self.select_point(nxt, s)
        elif button in (keys.BUTTON_UP, keys.BUTTON_DOWN):
            self.move_row(-1 if button == keys.BUTTON_UP else 1)
        elif button == keys.BUTTON_CENTER:
            row = self.current()
            if row is not None and row[0] == 'head':
                fields = items.fields(self.model, row[4])
                editable = [f for f in fields if f[4]]
                self.sel = (row[4], (editable or fields)[0][0])
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
            self.snapshot()
            try:
                items.delete(self.model, row[4])
            except ValueError:
                self.undo.pop()
                raise
            self.resolve()
            self.sel = None
            self.select_point(self.line, self.s)
            self.say('Removed: Z undoes')
        elif c == 'z':
            self.undo_last()
        elif c in ('+', '='):
            self.zoom = min(self.zoom + 1, len(ZOOMS) - 1)
        elif c == '-':
            self.zoom = max(self.zoom - 1, 0)
        elif c in items.INSERT_KEYS:
            self.snapshot()
            try:
                ref, field = items.insert(self.model, items.INSERT_KEYS[c], self.line, self.s)
            except ValueError:
                self.undo.pop()
                raise
            self.resolve()
            self.focus(ref, field)
            self.say({'split': 'Split here with its own section: ENTER changes it',
                      'member': 'New member: length, then angle'}.get(items.INSERT_KEYS[c],
                                                                                  'Added: type its position, or move on'))
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

    def key_diagrams(self, button, esc):
        if esc:
            self.page = 'model'
            return
        if self.solution is None:
            raise ValueError('Fix the model first (F3)')
        total = self.line_length(self.dline)
        c = self.char(button)
        step = total / (render.RIGHT - render.LEFT)
        if button in (keys.BUTTON_LEFT, keys.BUTTON_RIGHT) or c in (',', '.', '<', '>'):
            sign = -1 if button == keys.BUTTON_LEFT or c in (',', '<') else 1
            self.ds = min(max(self.ds + sign * step * (10 if c else 1), 0.0), total)
            self.note, self.tab = '', -1
        elif button in (keys.BUTTON_UP, keys.BUTTON_DOWN):
            points = items.stops(self.model, self.dline)
            if button == keys.BUTTON_DOWN:
                later = [p for p in points if p > self.ds + 1e-9]
                self.ds = later[0] if later else total
            else:
                earlier = [p for p in points if p < self.ds - 1e-9]
                self.ds = earlier[-1] if earlier else 0.0
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
        elif c == 'm':
            self.dline = (self.dline + 1) % len(self.solution.lines)
            self.ds, self.cache, self.tab, self.note = 0.0, None, -1, ''
        elif c == 'f':
            self.whole = not self.whole

    def next_view(self):
        self.view = (self.view + 1) % (len(self.model['cases']) + len(self.model['combos']))
        self.cache = None
        self.tab = -1

    def peak_list(self):
        ext = self.extremes(self.dline)
        out = []
        names = (('M', 'moment', 'kNm'), ('V', 'shear', 'kN'), ('N', 'normal', 'kN'), ('W', 'deflection', 'mm'),
                 ('T', 'slope', 'mrad'))
        for q, name, unit in names:
            hi, sh, lo, sl = ext[q]
            if abs(hi) > 1e-6:
                out.append(('max %s %s at %s m' % (name, units.show(hi, unit), units.number(sh)), sh, q))
            if abs(lo) > 1e-6:
                out.append(('min %s %s at %s m' % (name, units.show(lo, unit), units.number(sl)), sl, q))
        return out or [('No load effects in this view', 0.0, 'M')]

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
                self.dline, self.ds = action[1], action[2]
                self.page, self.note, self.cache, self.whole = 'diagrams', '', None, False
        elif erase_key(self.vm, button) and action and action[0] == 'pin':
            self.pins.remove((action[1], action[2]))

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
                V, M, T, W, N, U = sol.at_line(line, min(s, self.line_length(line)), self.view)
                label = ('x = ' if straight else 'L%d s = ' % (line + 1)) + units.show(s, 'm')
                rows.append((label, units.show(M, 'kNm'), 'V ' + units.show(V, 'kN') + '  w ' + units.show(W, 'mm') +
                             ('' if straight else '  N ' + units.show(N, 'kN')) + '  DEL unpins', None, ('pin', line, s)))
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
        elif option == 'Export CSV':
            self.export()
        else:
            self.back_page, self.page, self.help_first = 'options', 'help', 0

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
        elif erase_key(self.vm, button) and index < len(names):
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
        elif erase_key(self.vm, button) and index < len(combos):
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

    def key_help(self, button, esc):
        if esc or button == keys.BUTTON_F9 or button == keys.BUTTON_CENTER:
            self.page = self.back_page
        elif button in (keys.BUTTON_UP, keys.BUTTON_DOWN):
            self.help_first = min(max(self.help_first + (1 if button == keys.BUTTON_DOWN else -1), 0), len(HELP) - 5)

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

    def export(self):
        if self.solution is None:
            raise ValueError('Fix the model before exporting')
        sol = self.solution

        def rows():
            for line in range(len(sol.lines)):
                S, V, M, T, W, N, U, starts = sol.samples(line, self.view)
                for i in range(len(S)):
                    yield (line + 1, S[i], V[i] / 1e3, M[i] / 1e3, N[i] / 1e3, T[i] * 1e3, W[i] * 1e3)
        stem = self.model.get('name') or 'beam'
        path = cases.free_path(self.vm.storage, cases.EXPORT_DIRECTORY, stem, 'csv')
        cases.export_csv(self.vm.storage, path, ('line', 's_m', 'V_kN', 'M_kNm', 'N_kN', 'slope_mrad', 'w_mm'), rows())
        self.say('Exported ' + path.rsplit('/', 1)[1] + ' (' + sol.view_names()[self.view] + ')')

    # ------------------------------------------------------------ drawing

    def draw(self):
        vm = self.vm
        draw = vm.draw
        p = self.palette()
        note = self.message
        if self.page in MENU_PAGES:
            rows, subtitle, hint1 = self.menu_rows()
            theme.menu(draw, rows, self.menu_index, subtitle, hint1=hint1, hint2=note or 'ESC returns', palette=p)
            if self.prompt is not None:
                self.draw_prompt(draw, p)
                draw.swap()
            return
        draw.fill_screen(p.BG)
        if self.page == 'model':
            subtitle, hint1, hint2 = self.draw_model(draw, p)
        elif self.page == 'section':
            subtitle, hint1, hint2 = self.draw_section(draw, p)
        elif self.page == 'diagrams':
            subtitle, hint1, hint2 = self.draw_diagrams(draw, p)
        elif self.page == 'results':
            subtitle = 'Beam / results'
            hint1, hint2 = 'ENTER open  V view  DEL unpin', 'F3 Model  F4 Diagrams  F6 Options'
            rows = self.result_rows()
            self.result_index(rows)
            render.results(draw, p, [r[:4] for r in rows], self.menu_index, theme.HEAD_HEIGHT + 6,
                           int(draw.size.y) - theme.FOOT_HEIGHT - 2)
        elif self.page == 'combo':
            subtitle = 'Beam / combination'
            hint1, hint2 = 'ENTER edit  type a factor', 'ESC combinations'
            render.form(draw, p, [r[:4] for r in self.combo_rows()], max(1, self.menu_index), None,
                        theme.HEAD_HEIGHT + 8, int(draw.size.y) - theme.FOOT_HEIGHT)
        else:
            subtitle, hint1, hint2 = 'Beam / help', 'UP/DOWN scroll', 'ESC returns'
            render.help_page(draw, p, HELP, self.help_first)
        if note:
            hint2 = note
        theme.chrome(draw, subtitle, hint1, hint2, palette=p)
        if self.error and note:
            bottom = int(draw.size.y) - theme.FOOT_HEIGHT
            draw._fill_rectangle(0, bottom + 18, int(draw.size.x), 16, p.PANEL)
            theme.text(draw, 6, bottom + 20, note[:38], p.ERROR)
        if self.popup is not None:
            title, options, index, apply = self.popup
            render.popup(draw, p, title, options, index)
        if self.prompt is not None:
            self.draw_prompt(draw, p)
        draw.swap()

    def draw_prompt(self, draw, p):
        q = self.prompt
        render.prompt(draw, p, q['title'], q['detail'], q['edit'], q['message'] or 'ENTER saves  ESC cancels',
                      bool(q['message']))

    def menu_rows(self):
        if self.page == 'start':
            rows = [(name, detail) for name, detail in bm.TEMPLATES] + [('Open saved beam', 'From ' + cases.CASE_DIRECTORY)]
            return rows, 'Beam / new', 'ENTER starts this model'
        if self.page == 'options':
            weight = self.model.get('selfweight')
            details = ('Start again from a template', ', '.join(self.model['cases']),
                       '%d combination(s)' % len(self.model['combos']),
                       'Off  (ENTER: add it to a load case)' if weight is None else
                       'In ' + self.model['cases'][weight] + '  (ENTER: next case or off)',
                       'Write this model to the SD card', 'Replace this model with a saved one',
                       'Diagram values of the current view', 'Signs, units and keys')
            return list(zip(OPTIONS, details)), 'Beam / options', 'ENTER chooses'
        if self.page == 'cases':
            rows = []
            for i, name in enumerate(self.model['cases']):
                used = sum(1 for load in self.model['loads'] if load['case'] == i)
                rows.append((name, '%d load(s)  ENTER renames  DEL removes' % used))
            rows.append(('+ Add load case', 'Up to %d cases' % bm.MAX_CASES))
            return rows, 'Beam / load cases', 'ENTER rename or add'
        if self.page == 'combos':
            rows = [(c['name'], items.combo_text(self.model, c)) for c in self.model['combos']]
            rows.append(('+ Add combination', 'Factored sum of load cases'))
            return rows, 'Beam / combinations', 'ENTER edit  DEL removes'
        rows = [(name, 'ENTER opens; this model stays in undo') for name in self.files]
        return rows or [('No saved models', 'Save one from Options first')], 'Beam / open', 'ENTER opens'

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
        return ['%s: |M| %s |N| %s |w| %s' % (name[:12], units.show(peak['M'], 'kNm', 3), units.show(peak['N'], 'kN', 3),
                                              units.show(peak['W'], 'mm', 3))], False

    def draw_model(self, draw, p):
        frame = render.layout(self.model)
        runs = bm.lines(self.model)
        here = items.cursor_point(self.model, self.line, self.s, runs)
        view = render.View(self.model, frame['box'], ZOOMS[self.zoom], here)
        sel = self.sel[0] if self.sel else None
        shape = None
        if self.solution is not None:
            shape = render.deflected(self.model, self.solution, view, self.view)
        render.sketch(draw, p, self.model, view, sel, (here, self.s), self.problem, shape, runs[self.line],
                      frame['bottom'])
        width, height = int(draw.size.x), int(draw.size.y)
        draw._fill_rectangle(0, frame['bottom'], width, height - frame['bottom'], p.BG)
        lines, bad = self.summary()
        colors = [p.ERROR if bad else p.MUTED] * 3
        if not bm.is_straight_beam(self.model):
            m, x = items.locate(self.model, self.line, self.s, runs)
            lines = ['Run %d/%d (member %d)  s = %s  at %s' % (self.line + 1, len(runs), m + 1, units.show(self.s, 'm'),
                                                               self.where(*here))] + lines
            colors = [p.TEXT] + colors
        if self.zoom:
            lines[0] = lines[0][:44] + '  x%d' % int(ZOOMS[self.zoom])
        render.status(draw, p, lines, colors, frame['status'])
        top = frame['list']
        draw._line(4, top - 5, width - 5, top - 5, p.GRID)
        rows = self.rows()
        if rows:
            render.form(draw, p, [r[:4] for r in rows], self.row_index(rows), self.edit, top, height - theme.FOOT_HEIGHT)
        else:
            render.text(draw, 12, top + 4, 'Nothing here yet. Add with', p.MUTED)
            render.text(draw, 12, top + 16, 'S support  P point  M moment  W distributed', p.MUTED)
            render.text(draw, 12, top + 28, 'H hinge  B member  C section change', p.MUTED)
        if self.edit is not None:
            return 'Beam / model', 'ENTER apply  ESC cancel', 'Arithmetic works: 6/4, 2*pi'
        hint1 = 'SPMWH BC add DEL del Z undo' if bm.is_straight_beam(self.model) else 'SPMWH BC add TAB run +- zoom'
        return 'Beam / model', hint1, 'F4 Diagrams F5 Results F6 Opt ?'

    def draw_section(self, draw, p):
        section = self.section
        rows = self.section_rows()
        self.section_row = min(self.section_row, len(rows) - 1)
        field = rows[self.section_row][0]
        render.cross_section(draw, p, section, field, (6, 28, 172, 150))
        render.section_panel(draw, p, self.model, section, 180, 30)
        width, height = int(draw.size.x), int(draw.size.y)
        form_rows = [('field', r[1], items.section_text(section, r), r[4]) for r in rows]
        render.form(draw, p, form_rows, self.section_row, self.edit, 158, height - theme.FOOT_HEIGHT)
        if self.edit is not None:
            return 'Section ' + section['name'], 'ENTER apply  ESC cancel', 'Arithmetic works: 300-2*10'
        return 'Section ' + section['name'], 'UP/DOWN choose  ENTER edit', 'ESC back to the model'

    def draw_diagrams(self, draw, p):
        subtitle = 'Beam / diagrams'
        if self.solution is None:
            for i, line in enumerate(render.wrap(str(self.problem), 48)):
                render.text(draw, 10, 40 + 11 * i, line, p.ERROR)
            render.text(draw, 10, 80, 'F3 opens the model to fix it.', p.MUTED)
            return subtitle, 'F3 Model', 'ESC returns'
        sol = self.solution
        straight = bm.is_straight_beam(self.model)
        left = sol.at_line(self.dline, self.ds, self.view, -1)
        right = sol.at_line(self.dline, self.ds, self.view, 1)

        def pair(q, unit):
            a, b = units.number(units.from_si(left[q], unit), 3), units.number(units.from_si(right[q], unit), 3)
            return a if a == b else a + '|' + b
        if straight:
            readout = 'V %s kN  M %s kNm  w %s mm  rot %s mrad' % (pair(0, 'kN'), pair(1, 'kNm'), pair(3, 'mm'),
                                                                 units.number(right[2] * 1e3, 3))
            title = 'x = ' + units.show(self.ds, 'm')
        else:
            readout = 'V %s kN  M %s kNm  N %s kN  w %s mm' % (pair(0, 'kN'), pair(1, 'kNm'), pair(4, 'kN'), pair(3, 'mm'))
            title = 'Run %d  s = %s' % (self.dline + 1, units.show(self.ds, 'm'))
        if self.whole:
            m, x = sol.locate(self.dline, self.ds)
            render.text(draw, 6, 27, title, p.TEXT, render.SM)
            render.right_text(draw, int(draw.size.x) - 6, 27, sol.view_names()[self.view][:20], p.ACCENT, render.SM)
            render.text(draw, 6, 41, readout[:52], p.TEXT)
            render.overview(draw, p, self.model, sol, self.view, render.OVERVIEW[self.quantity],
                            bm.point(self.model, m, x), self.dline, (40, 96, 280, 262))
            return subtitle, 'D quantity  V view  M run', 'F member diagrams  ESC model'
        panels = ('V', 'M', self.third)
        if self.cache is None:
            self.cache = render.diagram_cache(sol, self.dline, self.view, panels)
        marks = []
        if self.tab >= 0:
            label, s, q = self.peak_list()[self.tab]
            marks.append((s, q))
        render.diagrams(draw, p, sol, self.dline, self.view, panels, self.cache, self.ds, readout, self.note, marks,
                        title)
        if straight:
            return subtitle, '<> , . move  ^v points  TAB peaks', 'ENTER pin  V view  D slope  ESC'
        return subtitle, '<> move ^v points TAB peaks M run', 'ENTER pin V view D 3rd F whole'


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
