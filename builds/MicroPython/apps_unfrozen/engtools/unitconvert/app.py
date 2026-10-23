"""Searchable offline converter using PicoLAB's keyboard and screen parts."""
from picoware.system import buttons as k
from picoware.system.font import FONT_SMALL as SM
from engtools.ui import theme
from engtools.ui.lab import chrome, panel, text, menu, prompt, Viewport, wrap
from engtools.ui.lab import tabs as draw_tabs, form
from engtools.ui.tool import Tabs, EquationHelp
from picoware.system.font import FONT_XTRA_SMALL as XS
from engtools.ui.forms import LineEdit, parse_number, erase_key
from . import model, catalog

TITLE = 'UNIT CONVERTER'
PATH = ('tools', 'UnitConverter')
PREFS = 'picoware/engineering/unitconvert.json'
PRIMARY = ('convert', 'results', 'favorites', 'recent')
OPTIONS = (('Swap units', 'Keep the quantity and reverse the conversion'),
           ('Add / remove favorite', 'Keep this pair for quick access'),
           ('Favorites', 'Saved unit pairs'), ('Recent conversions', 'Last 12 calculations'),
           ('Save conversion', 'Versioned case with its value in SI'),
           ('Open conversion', 'Load a saved conversion'),
           ('Export SI CSV', 'One value in the category base unit'))
HELP = ('Getting started:', 'Type to search categories or unit names',
        'UP/DOWN choose; ENTER opens', 'ESC clears search, then goes back',
        'Converting:', 'UP/DOWN choose a field; ENTER edits',
        'Type a number to replace the value', 'Arithmetic works: 3/8, 2*pi, 1e-6',
        'ENTER applies; ESC cancels an edit',
        'LEFT/RIGHT tabs; UP/DOWN selects a row',
        'S swaps units and preserves quantity',
        'F1 browse categories  F2 find a unit',
        'F3 options, favorites and saved cases', 'F4 conventions for this quantity',
        'F5 all equivalents  F6 calculate',
        'ENTER opens a searchable unit list',
        'Z undo the last conversion change',
        'Units:', 'US and Imperial measures are distinct',
        'Temperature intervals have no offsets',
        'Fuel economy uses reciprocal conversion',
        'kB is decimal; KiB is binary',
        'Results use the firmware float32 precision',
        'Files:', 'Cases and CSV use SI values',
        'Favorites and recent results live on SD',
        'CSV exports: engineering/exports/',
        'Full cross-app Send to is a later pass')
_active = None


class Converter:
    def __init__(self, vm):
        self.vm = vm
        from engtools import session
        self.state = dict(session.kept.get(model.TOOL) or model.new_state())
        self.favorites, self.recent = [], []
        self.page, self.index, self.row = 'convert', 0, 1
        self.search = LineEdit('', 32)
        self.edit, self.dialog = None, None
        self.unit_field = 'from'
        self.message, self.error = '', False
        self.undo = []
        self.files = []
        self.tabs = Tabs(('Convert', 'All units', 'Favorites', 'Recent'))
        self.help_view = EquationHelp()
        self.read_preferences()

    def switch_tab(self, step):
        self.tabs.index = PRIMARY.index(self.page)
        selected = self.tabs.switch(step, self.row if self.page == 'convert' else self.index)
        self.page = PRIMARY[self.tabs.index]
        if self.page == 'convert':
            self.row = selected if isinstance(selected, int) else 1
        else:
            self.index = selected if isinstance(selected, int) else 0

    def read_preferences(self):
        from json import loads
        storage = self.vm.storage
        try:
            if not storage.active or not storage.exists(PREFS):
                return
            if storage.size(PREFS) > 16384:
                return
            data = loads(storage.read(PREFS))
            if not isinstance(data, dict) or data.get('version') != 1:
                return
            for name in ('favorites', 'recent'):
                records = data.get(name, [])
                if not isinstance(records, list):
                    continue
                valid = []
                for record in records[:12]:
                    try:
                        model.from_case(record)
                        valid.append(record)
                    except (ValueError, TypeError, KeyError, ZeroDivisionError, OverflowError):
                        pass
                setattr(self, name, valid)
        except (ValueError, OSError, RuntimeError, TypeError):
            pass

    def persist(self):
        from engtools import cases
        from json import dumps
        storage = self.vm.storage
        cases._folder(storage, 'picoware/engineering')
        data = dumps({'version': 1, 'favorites': self.favorites, 'recent': self.recent})
        if not storage.write(PREFS, data) or storage.read(PREFS) != data:
            raise RuntimeError('Could not save favorites / history')

    def remember(self):
        record = model.to_case(self.state)
        self.recent = [r for r in self.recent if r != record]
        self.recent.insert(0, record)
        del self.recent[12:]

    def snapshot(self):
        self.undo.append(dict(self.state))
        del self.undo[:-8]

    def say(self, message, error=False):
        self.message, self.error = message, error

    def browse(self):
        self.page, self.index, self.search = 'browse', 0, LineEdit('', 32)

    def choose_category(self, key):
        if key != self.state['category']:
            self.snapshot()
            self.state = model.new_state(key)
        self.page, self.row = 'convert', 1

    def search_rows(self):
        if self.page == 'browse':
            return [(r[0], r[1], r[2]) for r in catalog.CATEGORIES
                    if model.matches(r[1] + ' ' + r[2] + ' ' + r[4], self.search.text)]
        return [(r[0], r[0], r[1]) for r in catalog.units(self.state['category'])
                if model.matches(r[0] + ' ' + r[1], self.search.text)]

    def open_units(self, field):
        self.unit_field = field
        self.page, self.search = 'units', LineEdit('', 32)
        self.index = [u[0] for u in catalog.units(self.state['category'])].index(self.state[field])

    def apply_unit(self, symbol):
        # A unit selection reinterprets the entered value. S preserves the
        # physical quantity when reversing direction instead.
        candidate = dict(self.state)
        candidate[self.unit_field] = symbol
        model.result(candidate)
        self.snapshot()
        self.state = candidate
        self.page = 'convert'

    def label(self, record):
        return record['from'] + ' -> ' + record['to']

    def option(self, index):
        from engtools import cases
        self.page, self.index = 'convert', 0
        if index == 0:
            self.do_swap()
        elif index == 1:
            record = model.to_case(self.state)
            pair = (record['category'], record['from'], record['to'])
            existing = next((r for r in self.favorites if (r['category'], r['from'], r['to']) == pair), None)
            if existing is not None:
                self.favorites.remove(existing)
                self.say('Favorite removed')
            else:
                self.favorites.insert(0, record)
                del self.favorites[12:]
                self.say('Favorite added')
            self.persist()
        elif index in (2, 3):
            self.page = 'favorites' if index == 2 else 'recent'
        elif index == 4:
            self.dialog = LineEdit('units-' + self.state['category'], 24)
        elif index == 5:
            self.files = []
            for name in cases.list_cases(self.vm.storage):
                try:
                    cases.load_case(self.vm.storage, name, model.TOOL)
                    self.files.append(name)
                except (ValueError, OSError, RuntimeError):
                    pass
            self.page = 'files'
        elif index == 6:
            key = self.state['category']
            value = model.to_si(key, self.state['from'], self.state['value'])
            path = cases.free_path(self.vm.storage, cases.EXPORT_DIRECTORY, 'units-' + key, 'csv')
            cases.export_csv(self.vm.storage, path, ('value [' + catalog.category(key)[3] + ']',), ((value,),))
            self.say('CSV: ' + path.rsplit('/', 1)[-1])

    def do_swap(self):
        candidate = dict(self.state)
        model.swap(candidate)
        self.snapshot()
        self.state = candidate
        self.remember()
        self.say('Units swapped')

    def begin_edit(self, button=None):
        self.row = 1
        self.edit = LineEdit(model.shown(self.state['value']) if button is None else '', 40)
        if button is not None:
            self.edit.key(self.vm, button)

    def run(self, button):
        if button == k.BUTTON_NONE:
            return False
        if self.help_view.opened:
            self.help_view.key(button)
            return True
        if button == k.BUTTON_F9:
            self.help_view.open('units', HELP)
            return True
        try:
            self.handle(button)
        except (ValueError, TypeError, ZeroDivisionError, OverflowError, OSError, RuntimeError) as exc:
            self.say(str(exc) or 'Conversion failed', True)
        return True

    def handle(self, button):
        from engtools import cases
        esc = button == self.vm.input_manager._key_esc
        if self.dialog is not None:
            action = self.dialog.key(self.vm, button)
            if action == 'cancel':
                self.dialog = None
            elif action is not None:
                name = cases.clean_name(self.dialog.text)
                if cases.exists(self.vm.storage, name):
                    raise ValueError('Name exists; choose another name')
                cases.save_case(self.vm.storage, name, model.to_case(self.state))
                self.dialog = None
                self.say('Saved ' + name)
            return
        if self.edit is not None:
            action = self.edit.key(self.vm, button)
            if action == 'cancel':
                self.edit = None
            elif action is not None:
                value = parse_number(self.edit.text)
                candidate = dict(self.state, value=value)
                model.result(candidate)
                self.snapshot()
                self.state, self.edit = candidate, None
                self.remember()
                self.say('Converted')
                if action in ('up', 'down'):
                    self.row = (self.row + (-1 if action == 'up' else 1)) % 4
            return
        self.message, self.error = '', False
        if esc:
            if self.page in ('browse', 'units') and self.search.text:
                self.search = LineEdit('', 32)
                self.index = 0
            elif self.page == 'browse':
                self.vm.back()
            elif self.page == 'convert':
                self.browse()
            else:
                self.page = 'convert'
            return
        if self.page in ('browse', 'units'):
            rows = self.search_rows()
            if button in (k.BUTTON_UP, k.BUTTON_DOWN):
                self.index = (self.index + (1 if button == k.BUTTON_DOWN else -1)) % max(1, len(rows))
            elif button in (k.BUTTON_LEFT, k.BUTTON_RIGHT):
                self.index = min(max(0, self.index + (8 if button == k.BUTTON_RIGHT else -8)), max(0, len(rows)-1))
            elif button == k.BUTTON_CENTER and rows:
                if self.page == 'browse':
                    self.choose_category(rows[self.index][0])
                else:
                    self.apply_unit(rows[self.index][0])
            elif button == k.BUTTON_F1:
                self.browse()
            else:
                before = self.search.text
                self.search.key(self.vm, button)
                if self.search.text != before:
                    self.index = 0
            return
        if self.page in PRIMARY and button in (k.BUTTON_LEFT, k.BUTTON_RIGHT):
            self.switch_tab(-1 if button == k.BUTTON_LEFT else 1)
            return
        if self.page in PRIMARY:
            if button == k.BUTTON_F1:
                self.browse()
                return
            if button == k.BUTTON_F3:
                self.page, self.index = 'options', 0
                return
            if button == k.BUTTON_F5:
                self.page, self.index = 'results', 0
                return
            if button == k.BUTTON_F6:
                model.result(self.state)
                self.remember()
                self.say('Converted')
                return
        if self.page in ('options', 'favorites', 'recent', 'files', 'results'):
            if self.page == 'options':
                count = len(OPTIONS)
            elif self.page == 'results':
                count = len(catalog.units(self.state['category']))
            elif self.page == 'files':
                count = len(self.files)
            else:
                count = len(getattr(self, self.page))
            if button in (k.BUTTON_UP, k.BUTTON_DOWN):
                self.index = (self.index + (1 if button == k.BUTTON_DOWN else -1)) % max(1, count)
            elif button == k.BUTTON_CENTER and count:
                if self.page == 'options':
                    self.option(self.index)
                elif self.page == 'results':
                    self.unit_field = 'to'
                    self.apply_unit(catalog.units(self.state['category'])[self.index][0])
                else:
                    record = cases.load_case(self.vm.storage, self.files[self.index], model.TOOL) if self.page == 'files' else getattr(self, self.page)[self.index]
                    candidate = model.from_case(record)
                    self.snapshot()
                    self.state, self.page, self.row = candidate, 'convert', 1
            return
        c = self.vm.input_manager.button_to_char(button) or ''
        if button == k.BUTTON_F1:
            self.browse()
        elif button == k.BUTTON_F2:
            self.open_units('to' if self.row != 2 else 'from')
        elif button == k.BUTTON_F3:
            self.page, self.index = 'options', 0
        elif button == k.BUTTON_F4:
            record = catalog.category(self.state['category'])
            self.vm.show('UNIT CONVENTIONS', tuple(wrap(record[5] or 'Units convert through ' + record[3] + '.', 43)))
        elif button == k.BUTTON_F5:
            self.page, self.index = 'results', 0
        elif button == k.BUTTON_F6:
            model.result(self.state)
            self.remember()
            self.say('Converted')
        elif button in (k.BUTTON_UP, k.BUTTON_DOWN):
            self.row = (self.row + (1 if button == k.BUTTON_DOWN else -1)) % 4
        elif button == k.BUTTON_CENTER:
            if self.row == 0:
                self.browse()
            elif self.row == 1:
                self.begin_edit()
            else:
                self.open_units('from' if self.row == 2 else 'to')
        elif c.lower() == 's':
            self.do_swap()
        elif c.lower() == 'z' and self.undo:
            self.state = self.undo.pop()
            self.say('Undone')
        elif c and (c.isdigit() or c in '-+.('):
            self.begin_edit(button)
        elif erase_key(self.vm, button):
            self.begin_edit()
            self.edit.key(self.vm, button)

    def draw(self):
        draw = self.vm.draw
        p = theme.system_palette(self.vm)
        bottom = int(draw.size.y) - 12
        draw.fill_screen(p.BG)
        if self.help_view.opened:
            chrome(draw, p, 'Help', title=TITLE, fallback=PATH)
            self.help_view.draw(draw, p)
            draw.swap()
            return
        if self.page in PRIMARY:
            self.draw_primary(draw, p, bottom)
            status, hint = '', 'F9 Help'
        elif self.page in ('browse', 'units'):
            heading = 'FIND A QUANTITY' if self.page == 'browse' else 'CHOOSE ' + self.unit_field.upper() + ' UNIT'
            panel(draw, p, (8, 43, 304, bottom-46), heading)
            draw._rectangle(14, 65, 292, 23, p.ACCENT)
            if self.search.text:
                self.search.draw(draw, 20, 70, 280, p.TEXT, p.ACCENT, SM)
            else:
                text(draw, 20, 71, 'Type a name or symbol to search...', p.MUTED)
            rows = self.search_rows()
            self.index = min(self.index, max(0, len(rows)-1))
            capacity = max(1, (bottom-106)//26)
            first = min(max(0, self.index-capacity//2), max(0, len(rows)-capacity))
            clip = Viewport(draw, (14, 92, 306, bottom-7))
            for i in range(first, min(len(rows), first+capacity)):
                y = 96 + (i-first)*26
                if i == self.index:
                    clip._fill_rectangle(14, y-2, 292, 25, p.SELECT)
                    clip._rectangle(14, y-2, 292, 25, p.ACCENT)
                text(clip, 20, y, rows[i][1], p.TEXT, SM)
                text(clip, 20, y+13, rows[i][2], p.MUTED)
            if not rows:
                text(draw, 20, 108, 'No matches. ESC clears the search.', p.MUTED)
            status = '%d found' % len(rows)
            hint = 'Type: search | Enter: open'
        else:
            if self.page == 'options':
                rows, title = OPTIONS, 'OPTIONS'
            else:
                rows = [(name, 'Saved conversion') for name in self.files]
                title = 'OPEN CONVERSION'
            menu(draw, p, rows or [('Nothing saved yet', 'ESC returns')], self.index, title, bottom)
            status, hint = '', 'F9 Help'
        chrome(draw, p, status, self.message, self.error, title=TITLE, fallback=PATH, hint=hint)
        if self.dialog is not None:
            prompt(draw, p, 'SAVE CONVERSION', 'Choose a new case name', self.dialog, self.message, self.error)
        draw.swap()

    def draw_primary(self, draw, p, bottom):
        st = self.state
        quantity = catalog.category(st['category'])
        panel(draw, p, (8, 43, 304, 112), 'CONVERSION', quantity[1])
        bounded = Viewport(draw, (17, 65, 303, 151))
        text(bounded, 18, 73, model.shown(st['value'])+' '+st['from'], p.TEXT, SM)
        text(bounded, 18, 96, '= '+model.shown(model.result(st))+' '+st['to'], p.ACCENT, SM)
        text(bounded, 18, 135, 'S Swap   F1 Categories   F6 Calculate', p.MUTED)
        self.tabs.index = PRIMARY.index(self.page)
        draw_tabs(draw, p, (8, 161, 304, bottom-164), self.tabs.labels, self.tabs.index,
                  [None]*len(self.tabs.labels), font=XS)
        if self.page == 'convert':
            rows = [('field', 'Quantity', quantity[1], True),
                    ('field', 'Value', model.shown(st['value']), True),
                    ('field', 'From', st['from']+' '+model.unit(st['category'], st['from'])[1], True),
                    ('field', 'To', st['to']+' '+model.unit(st['category'], st['to'])[1], True)]
            form(draw, p, rows, self.row, self.edit, 188, bottom-24, font=XS)
        else:
            if self.page == 'results':
                key = st['category']
                si = model.to_si(key, st['from'], st['value'])
                rows = []
                for u in catalog.units(key):
                    try:
                        value = model.shown(model.from_si(key, u[0], si))
                    except (ValueError, OverflowError, ZeroDivisionError):
                        value = 'out of range'
                    rows.append((value+' '+u[0], u[1]))
            else:
                rows = [(self.label(r), catalog.category(r['category'])[1]) for r in getattr(self, self.page)]
            if not rows:
                text(draw, 20, 194, 'Nothing saved yet; F3 opens options', p.MUTED)
            else:
                self.index = min(self.index, len(rows)-1)
                capacity = max(1, (bottom-24-188)//26)
                first = min(max(0, self.index-capacity//2), max(0, len(rows)-capacity))
                bounded = Viewport(draw, (14, 185, 306, bottom-23))
                for i in range(first, min(len(rows), first+capacity)):
                    y = 190+(i-first)*26
                    if i == self.index:
                        bounded._fill_rectangle(14, y-2, 292, 25, p.SELECT)
                        bounded._rectangle(14, y-2, 292, 25, p.ACCENT)
                    text(bounded, 20, y, rows[i][0], p.TEXT)
                    text(bounded, 20, y+12, rows[i][1], p.MUTED)
        text(draw, 16, bottom-17, 'LEFT/RIGHT tabs  UP/DOWN select  ENTER edit', p.MUTED)


class ConverterView:
    HELP = None

    def start(self, vm):
        global _active
        self.app = _active = Converter(vm)
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
        session.kept[model.TOOL] = dict(self.app.state)
        if vm.storage.active:
            try:
                self.app.persist()
            except (OSError, RuntimeError):
                pass
        self.app = _active = None


def show(vm):
    from engtools.plots.view import open_view
    return open_view(vm, 'unitconvert_view', ConverterView())
