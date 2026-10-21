"""Heat transfer 2D in PicoLAB: conduction in a rectangular plate, steady or
transient, with fixed-temperature, convection, heat-flux and insulated sides
and heat sources.

The model page shows the plate to scale above tabbed properties. F6
evaluates; editing clears the field. F4 plots the field, profiles and a
transient's history, F5 lists the results and F3 holds examples and files.
The inputs stay in RAM while PicoLAB runs; saving to the SD card is explicit.
"""
from picoware.system import buttons as keys
from engtools.ui import theme
from engtools.ui.forms import LineEdit, parse_number, erase_key
from engtools.ui.lab import (text, right_text, panel, chrome, form, popup, prompt, menu, results, tabs, wrap,
                             Viewport, XS, SM)
from engtools.units import number
from engtools import cases
from . import model as tm
from . import items
from . import render

TITLE = 'HEAT TRANSFER'
PATH = ('modules', 'thermal', 'Heat transfer 2D')
BUDGET_MS = 30
UNDO_LIMIT = 12
PIN_LIMIT = 8
PLOT_VIEWS = ('field', 'profiles', 'history')
OPTIONS = (
    ('Examples', 'Load a ready-made plate'),
    ('New plate', 'Slab, hot left and cold right; Z undoes'),
    ('Save', 'Write the inputs to SD'),
    ('Open', 'Load saved inputs without evaluating'),
    ('Export field CSV', 'Every cell: x, y, T, qx, qy'),
    ('Export profiles CSV (Eggcel)', 'Row and column through the cursor'),
    ('Export history CSV (Eggcel)', 'Transient min, mean and max over time'),
)
EXAMPLES = (
    ('Slab: hot left, cold right', {}, {}, ()),
    ('Chip on a cooled plate', {'W': 60.0, 'H': 60.0, 'depth': 5.0, 'res': 2},
     {i: {'kind': tm.CONVECTION, 'T': 25.0, 'h': 25.0} for i in range(4)},
     ({'P': 2.0, 'x': 25.0, 'y': 25.0, 'w': 10.0, 'h': 10.0},)),
    ('Two chips on a spreader', {'W': 80.0, 'H': 30.0, 'depth': 2.0, 'res': 3},
     {0: {'kind': tm.INSULATED}, 1: {'kind': tm.INSULATED}, 2: {'kind': tm.CONVECTION, 'T': 25.0, 'h': 2000.0}},
     ({'P': 3.0, 'x': 12.0, 'y': 25.0, 'w': 12.0, 'h': 5.0}, {'P': 1.5, 'x': 54.0, 'y': 25.0, 'w': 12.0, 'h': 5.0})),
    ('Square, two hot sides', {'W': 60.0, 'H': 60.0, 'res': 2},
     {0: {'kind': tm.TEMPERATURE, 'T': 100.0}, 1: {'kind': tm.TEMPERATURE, 'T': 0.0},
      2: {'kind': tm.TEMPERATURE, 'T': 100.0}, 3: {'kind': tm.TEMPERATURE, 'T': 0.0}}, ()),
    ('Wall: indoors and outdoors', {'W': 200.0, 'H': 80.0, 'material': 'Brick', 'res': 0},
     {0: {'kind': tm.CONVECTION, 'T': 20.0, 'h': 8.0}, 1: {'kind': tm.CONVECTION, 'T': -5.0, 'h': 25.0}}, ()),
    ('Slab heated from inside', {'gen': 2e6},
     {0: {'kind': tm.TEMPERATURE, 'T': 20.0}, 1: {'kind': tm.TEMPERATURE, 'T': 20.0}}, ()),
    ('Heated strip on top', {'W': 80.0, 'H': 40.0, 'material': 'Copper'},
     {0: {'kind': tm.INSULATED}, 1: {'kind': tm.INSULATED}, 2: {'kind': tm.CONVECTION, 'T': 20.0, 'h': 500.0},
      3: {'kind': tm.FLUX, 'q': 50000.0}}, ()),
    ('Block cooling in air', {'mode': 'transient', 'W': 50.0, 'H': 50.0, 'material': 'Carbon steel', 'T0': 200.0,
                              'tend': 1200.0, 'res': 0},
     {i: {'kind': tm.CONVECTION, 'T': 20.0, 'h': 50.0} for i in range(4)}, ()),
)
HELP = (
    'Model:',
    'LEFT/RIGHT\tPlate, Sides, Sources, Solve tabs',
    'UP/DOWN\tchoose a value',
    'ENTER\tedit or choose; type to replace',
    '[ / ]\tcycle the highlighted choice',
    'ENTER/TAB\tapply',
    'ESC\tcancel the edit, pause, then leave',
    'Arithmetic works: 120*0.8, 50/2',
    'F1\tadd a heat patch (Sources)',
    'F2\tremove the selected patch',
    'Z\tundo (12 steps)',
    'M\tsteady or transient',
    'C\tsmooth or banded colours',
    'Evaluating:',
    'F6\tevaluate: the only solve command',
    'SPACE\tpause or resume; evaluates when there is no field',
    'Edits clear the field; F4 and F5 need F6 first.',
    'Pages:',
    'F3\toptions: examples, save, open, CSV',
    'F4\tplots',
    'F5\tresults',
    'ESC\tback to the model',
    'Plots:',
    'arrows\tmove the cursor one cell',
    'TAB\thottest, coldest, then pinned points',
    'ENTER\tpin the cursor (up to 8, listed in F5)',
    'D\tfield, profiles, history (transient)',
    'Results:',
    'ENTER\tshow the point in the plots',
    'F2\tunpin a pinned point',
    'Edge lines:',
    'amber\tfixed temperature',
    'accent\tconvection',
    'white\theat flux',
    'grey\tinsulated',
    'Model:',
    'One material, 2D conduction; the faces are insulated. Heat flows are in W over the plate depth, '
    'positive into the plate. Values are at cell centres; temperature and convection sides act through '
    'half a cell. Heat flux is W/m2 into the plate; a patch gives its power in W.',
    'Units: mm, W/mK, kg/m3, J/kgK, W/m2K, W/m3, W, C, s',
)

_active = None


def material_index(name):
    for index, row in enumerate(tm.MATERIALS):
        if row[0] == name:
            return index
    return tm.CUSTOM


class Heat:
    def __init__(self, vm):
        self.vm = vm
        from engtools import session
        kept = session.kept.get('thermal') or {}
        self.state = kept.get('state') or tm.new_state()
        if 'sides' in kept:   # kept by the first version: the state itself
            self.state = tm.from_case(kept)
        self.tab = kept.get('tab', items.PLATE)
        self.tab_rows = [0] * len(items.TABS)
        self.page = 'model'
        self.view = 0
        self.edit = self.popup = self.prompt = None
        self.menu_index = 0
        self.files = []
        self.confirm = None
        self.undo = []
        self.bands = False
        self.message, self.error = '', False
        self.plate, self.problem, self.running = None, '', False
        self.probe = [self.state['W'] / 2, self.state['H'] / 2]
        self.pins = []
        self.peak, self.note = -1, ''
        self.result_cache = None

    def keep(self):
        """What survives closing the tool while PicoLAB stays open: the
        inputs and tab, not the field or the undo history."""
        from engtools import session
        session.kept['thermal'] = {'state': self.state, 'tab': self.tab}

    def palette(self):
        return theme.system_palette(self.vm)

    def say(self, message, error=False):
        self.message, self.error = message, error

    # ------------------------------------------------------------ solving

    def drop(self):
        """Clear the field after an edit; never solve."""
        self.plate, self.problem, self.running = None, '', False
        self.result_cache = None
        from gc import collect
        collect()

    def evaluate(self):
        self.drop()
        try:
            self.plate = tm.Plate(self.state)
        except (ValueError, MemoryError) as exc:
            self.problem = str(exc) or 'Out of memory: use a coarser grid'
            self.say(self.problem, True)
            return False
        self.clamp_points()
        self.running = True
        self.say('Solving' if self.state['mode'] == 'steady' else 'Running')
        return True

    def finished(self):
        plate = self.plate
        self.running = False
        if self.state['mode'] == 'steady':
            if plate.converged:
                self.say('Converged: %d iterations' % plate.iterations)
            else:
                self.say('Not converged after %d iterations' % plate.iterations, True)
        else:
            self.say('Finished at t = %s s' % number(self.state['tend'], 4))

    def toggle_run(self):
        if self.plate is None or self.plate.done:
            self.evaluate()
            return
        self.running = not self.running
        self.say('Running' if self.running else 'Paused')

    def status(self):
        plate = self.plate
        mode = self.state['mode']
        if plate is None:
            return mode + (' / not solvable' if self.problem else ' / geometry')
        if mode == 'steady':
            if self.running:
                return 'steady / %d iterations' % plate.iterations
            return 'steady / ' + ('converged' if plate.done and plate.converged else 'stopped' if plate.done else 'paused')
        return 't = %s s  %d%%' % (number(plate.time, 4), int(100 * plate.progress))

    # ------------------------------------------------------------ rows

    def rows(self):
        return items.rows(self.state, self.tab)

    @property
    def row(self):
        return self.tab_rows[self.tab]

    def current(self):
        rows = self.rows()
        index = min(max(self.row, 0), len(rows) - 1)
        while rows[index][0] == 'head' and index + 1 < len(rows):
            index += 1
        self.tab_rows[self.tab] = index
        return rows[index]

    def move(self, step):
        rows = self.rows()
        index = self.row + step
        while 0 <= index < len(rows) and rows[index][0] == 'head':
            index += step
        if 0 <= index < len(rows):
            self.tab_rows[self.tab] = index

    def switch_tab(self, step):
        self.tab = (self.tab + step) % len(items.TABS)
        self.current()

    def focus_key(self, key):
        """Select the row with this key on the current tab."""
        for index, row in enumerate(self.rows()):
            if row[4] == key:
                self.tab_rows[self.tab] = index
                return

    def chosen(self):
        """The side and patch the current row belongs to, for the preview."""
        if self.page != 'model':
            return None, None
        picked = items.selected(self.current()[4])
        if picked is None:
            return None, None
        return (picked[1], None) if picked[0] == 'side' else (None, picked[1])

    # ------------------------------------------------------------ changes

    def snapshot(self):
        self.undo.append(tm.copy_state(self.state))
        if len(self.undo) > UNDO_LIMIT:
            del self.undo[0]

    def changed(self):
        had = self.plate is not None
        self.drop()
        if had:
            self.say('Edited: field cleared')

    def undo_last(self):
        if not self.undo:
            raise ValueError('Nothing to undo')
        self.state = self.undo.pop()
        self.drop()
        self.current()
        self.say('Undone')

    def set_mode(self, mode):
        self.snapshot()
        self.state['mode'] = mode
        self.changed()
        self.say('Transient' if mode == 'transient' else 'Steady state')

    def replace_state(self, state, message):
        self.snapshot()
        self.state = state
        self.drop()
        self.tab_rows = [0] * len(items.TABS)
        self.current()
        self.clamp_points(True)
        self.page = 'model'
        self.say(message)

    def example(self, index):
        name, values, sides, patches = EXAMPLES[index]
        state = tm.new_state()
        values = dict(values)
        material = values.pop('material', 'Aluminium 6061')
        state.update(values)
        for side, changes in sides.items():
            state['sides'][side].update(changes)
        state['patches'] = [dict(patch) for patch in patches]
        items.set_material(state, material_index(material))
        self.replace_state(state, name)

    def add_patch(self):
        patches = self.state['patches']
        if len(patches) >= tm.MAX_PATCHES:
            raise ValueError('Up to %d patches' % tm.MAX_PATCHES)
        self.snapshot()
        patches.append(tm.new_patch(self.state))
        self.changed()
        self.tab = items.SOURCES
        self.focus_key('patch:%d:P' % (len(patches) - 1))
        self.say('Patch %d added' % len(patches))

    def remove_patch(self):
        picked = items.selected(self.current()[4]) if self.tab == items.SOURCES else None
        if picked is None or picked[0] != 'patch':
            raise ValueError('Select a patch first')
        self.snapshot()
        del self.state['patches'][picked[1]]
        self.changed()
        self.current()
        self.say('Patch %d removed / Z undoes' % (picked[1] + 1))

    def begin_edit(self, button=None):
        kind, label, value, editable, key, unit = self.current()
        if kind == 'head':
            return
        if not editable:
            raise ValueError('Worked out from the inputs')
        if items.is_choice(key):
            title, options, index, apply = items.choices(self.state, key)

            def choose(i):
                self.snapshot()
                apply(i)
                self.changed()
                self.focus_key(key)
            self.popup = [title, options, index, choose]
            return
        if button is None or erase_key(self.vm, button):
            self.edit = LineEdit(number(items.get(self.state, key), 7), 16)
            if button is not None:
                self.edit.key(self.vm, button)
        else:
            self.edit = LineEdit('', 16)
            self.edit.key(self.vm, button)

    def cycle_choice(self, step):
        key = self.current()[4]
        if not items.is_choice(key):
            return
        title, options, index, apply = items.choices(self.state, key)
        self.snapshot()
        apply((index + step) % len(options))
        self.changed()
        self.focus_key(key)

    def commit(self):
        key = self.current()[4]
        value = parse_number(self.edit.text)
        before = tm.copy_state(self.state)
        items.set_value(self.state, key, value)
        self.undo.append(before)
        if len(self.undo) > UNDO_LIMIT:
            del self.undo[0]
        self.edit = None
        self.changed()
        self.clamp_points()

    def clamp_points(self, centre=False):
        s = self.state
        if centre:
            self.probe = [s['W'] / 2, s['H'] / 2]
            self.pins = []
        self.probe = [min(max(self.probe[0], 0.0), s['W']), min(max(self.probe[1], 0.0), s['H'])]
        self.pins = [(min(x, s['W']), min(y, s['H'])) for x, y in self.pins]

    # ------------------------------------------------------------ keys

    def run(self, button):
        """Handle a key and advance a running solve; True when the screen changes."""
        dirty = False
        if button != keys.BUTTON_NONE:
            dirty = True
            try:
                self.handle(button)
            except (ValueError, TypeError, KeyError, IndexError, ZeroDivisionError, OverflowError,
                    RuntimeError, OSError) as exc:
                self.say(str(exc) or 'Not possible here', True)
        if self.running and self.plate is not None:
            dirty = True
            try:
                if self.plate.advance(BUDGET_MS):
                    self.finished()
            except MemoryError:
                self.running = False
                self.say('Out of memory: use a coarser grid', True)
        return dirty

    def char(self, button):
        c = self.vm.input_manager.button_to_char(button)
        return c.lower() if c else ''

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
                except (ValueError, RuntimeError, OSError) as exc:
                    self.prompt['message'] = str(exc)
            return
        if self.popup is not None:
            title, options, index, apply = self.popup
            c = self.char(button)
            if esc:
                self.popup = None
            elif button in (keys.BUTTON_UP, keys.BUTTON_DOWN) or c in ('[', ']'):
                self.popup[2] = (index + (1 if button == keys.BUTTON_DOWN or c == ']' else -1)) % len(options)
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
        c = self.char(button)
        if button == keys.BUTTON_F6:
            self.evaluate()
            return
        if button == keys.BUTTON_SPACE or c == ' ':
            self.toggle_run()
            return
        page = {keys.BUTTON_F3: 'options', keys.BUTTON_F4: 'plots', keys.BUTTON_F5: 'results'}.get(button)
        if page:
            self.menu_index = 0
            self.page = page
            return
        if self.page != 'model' and esc:
            self.page = 'options' if self.page in ('examples', 'open') else 'model'
            self.menu_index = 0
            return
        getattr(self, 'key_' + self.page)(button, esc, c)

    def key_model(self, button, esc, c):
        if esc:
            if self.running:
                self.running = False
                self.say('Paused')
            else:
                self.vm.back()
            return
        row = self.current()
        typing = row[5] not in ('choice', '')
        if button in (keys.BUTTON_UP, keys.BUTTON_DOWN):
            self.move(-1 if button == keys.BUTTON_UP else 1)
        elif button in (keys.BUTTON_LEFT, keys.BUTTON_RIGHT):
            self.switch_tab(-1 if button == keys.BUTTON_LEFT else 1)
        elif button == keys.BUTTON_CENTER:
            self.begin_edit()
        elif button == keys.BUTTON_F1:
            self.add_patch()
        elif button == keys.BUTTON_F2:
            self.remove_patch()
        elif c in ('[', ']'):
            self.cycle_choice(-1 if c == '[' else 1)
        elif c == 'z':
            self.undo_last()
        elif c == 'm':
            self.set_mode('steady' if self.state['mode'] == 'transient' else 'transient')
        elif c == 'c':
            self.bands = not self.bands
            self.say('Banded colours' if self.bands else 'Smooth colours')
        elif typing and ((c and (c.isdigit() or c in '-.(')) or erase_key(self.vm, button)):
            self.begin_edit(button)

    # ------------------------------------------------------------ plots

    def views(self):
        plate = self.plate
        if plate is not None and self.state['mode'] == 'transient' and len(plate.history) > 1:
            return PLOT_VIEWS
        return PLOT_VIEWS[:2]

    def probe_cell(self):
        return self.plate.cell(*self.probe)

    def peaks(self):
        """(label, x, y) points TAB steps through: hottest, coldest, pins."""
        plate = self.plate
        stats = plate.stats()
        out = [('Hottest',) + plate.centre(*stats['hot']), ('Coldest',) + plate.centre(*stats['cold'])]
        for n, (x, y) in enumerate(self.pins):
            out.append(('Pin %d' % (n + 1), x, y))
        return out

    def key_plots(self, button, esc, c):
        if self.plate is None:
            raise ValueError(self.problem or 'Not evaluated yet')
        plate = self.plate
        if button in (keys.BUTTON_LEFT, keys.BUTTON_RIGHT, keys.BUTTON_UP, keys.BUTTON_DOWN):
            j, i = self.probe_cell()
            i += (button == keys.BUTTON_RIGHT) - (button == keys.BUTTON_LEFT)
            j += (button == keys.BUTTON_UP) - (button == keys.BUTTON_DOWN)
            j, i = min(max(j, 0), plate.ny - 1), min(max(i, 0), plate.nx - 1)
            self.probe = list(plate.centre(j, i))
            self.peak, self.note = -1, ''
        elif button == keys.BUTTON_TAB:
            peaks = self.peaks()
            self.peak = (self.peak + 1) % len(peaks)
            label, x, y = peaks[self.peak]
            self.probe, self.note = [x, y], label
        elif button == keys.BUTTON_CENTER:
            here = tuple(plate.centre(*self.probe_cell()))
            if here in self.pins:
                self.note = 'Already pinned'
            elif len(self.pins) >= PIN_LIMIT:
                raise ValueError('Up to %d pinned points' % PIN_LIMIT)
            else:
                self.pins.append(here)
                self.note = 'Pinned %d' % len(self.pins)
        elif c == 'd':
            views = self.views()
            self.view = (self.view + 1) % len(views)
        elif c == 'c':
            self.bands = not self.bands

    # ------------------------------------------------------------ results

    def result_rows(self):
        """(label, value, detail, colour, action) rows for F5, built once per
        state of the solve and set of pins."""
        plate = self.plate
        if plate is None:
            return [('Not evaluated', None, self.problem or 'Evaluate the plate first', None, None)]
        key = (plate.iterations, getattr(plate, 'step_count', 0), plate.done, tuple(self.pins))
        if self.result_cache is None or self.result_cache[0] != key:
            self.result_cache = (key, self.build_result_rows(plate))
        return self.result_cache[1]

    def build_result_rows(self, plate):
        s = self.state
        transient = s['mode'] == 'transient'
        p = self.palette()
        stats, flows = plate.stats(), plate.flows()

        def at(cell):
            x, y = plate.centre(*cell)
            return x, y, 'at %s, %s mm' % (number(x, 3), number(y, 3))
        if transient:
            state = 'running' if self.running else 'finished' if plate.done else 'paused'
            out = [('Status', state, 't = %s of %s s' % (number(plate.time, 4), number(s['tend'], 4)), None, None)]
        else:
            state = 'running' if self.running else ('converged' if plate.converged else 'stopped') if plate.done else 'paused'
            out = [('Status', state, '%d iterations' % plate.iterations,
                    p.ERROR if plate.done and not plate.converged else None, None)]
        out.append(('Temperature', None, '', None, None))
        x, y, detail = at(stats['hot'])
        out.append(('Highest', number(stats['max'], 5) + ' C', detail, None, ('goto', x, y)))
        x, y, detail = at(stats['cold'])
        out.append(('Lowest', number(stats['min'], 5) + ' C', detail, None, ('goto', x, y)))
        out.append(('Mean', number(stats['mean'], 5) + ' C', 'over the whole plate', None, None))
        out.append(('Heat into the plate', None, '', None, None))
        for index, name in enumerate(tm.SIDES):
            side = s['sides'][index]
            length = (s['H'] if index < 2 else s['W']) / 1000 * s['depth'] / 1000
            detail = tm.KINDS[side['kind']]
            if side['kind'] != tm.INSULATED:
                detail += ', mean %s W/m2' % number(flows['sides'][index] / length, 4)
            out.append((name + ' side', number(flows['sides'][index], 4) + ' W', detail, None, None))
        if flows['generated']:
            out.append(('Generated', number(flows['generated'], 4) + ' W',
                        '%d patch%s and the whole plate' % (len(s['patches']), '' if len(s['patches']) == 1 else 'es'),
                        None, None))
        if transient:
            out.append(('Stored rate', number(flows['net'], 4) + ' W', 'heat going into storage now', None, None))
        else:
            share = 100 * abs(flows['net']) / flows['scale'] if flows['scale'] else 0.0
            ok = share < 0.1 or not plate.done
            out.append(('Balance', 'OK' if ok else 'CHECK', 'net %s W, %s %% of the flow' % (
                number(flows['net'], 3), number(share, 2)), None if ok else p.ERROR, None))
        out.append(('Numbers', None, '', None, None))
        alpha = tm.diffusivity(s)
        longest = max(s['W'], s['H']) / 1000
        if transient:
            out.append(('Fourier number', number(alpha * plate.time / longest ** 2, 3),
                        'a t / L2 with L the longer side', None, None))
            out.append(('Diffusion time', number(longest * longest / alpha, 3) + ' s', 'L2 / a', None, None))
        biot = [side['h'] * (s['W'] if index < 2 else s['H']) / 1000 / s['k']
                for index, side in enumerate(s['sides']) if side['kind'] == tm.CONVECTION]
        if biot:
            big = max(biot)
            out.append(('Biot number', number(big, 3), 'h L / k, largest side: %s' % (
                'nearly uniform' if big < 0.1 else 'gradients matter'), None, None))
        if self.pins:
            out.append(('Pinned points', None, '', None, None))
            for n, (x, y) in enumerate(self.pins):
                j, i = plate.cell(x, y)
                qx, qy = plate.flux(j, i)
                out.append(('%s, %s mm' % (number(x, 3), number(y, 3)), number(plate.temperature(j, i), 5) + ' C',
                            'qx %s qy %s W/m2' % (number(qx, 3), number(qy, 3)), None, ('pin', n)))
        out.append(('Solver', None, '', None, None))
        out.append(('Grid', '%d x %d' % (plate.nx, plate.ny), 'cells of %s x %s mm' % (
            number(plate.dx * 1000, 3), number(plate.dy * 1000, 3)), None, None))
        if transient:
            out.append(('Time steps', str(plate.steps), 'explicit, dt = %s s' % number(plate.dt, 3), None, None))
        else:
            out.append(('Iterations', str(plate.iterations), 'preconditioned conjugate gradients', None, None))
        return out

    def result_index(self, rows):
        """Selectable rows (headings are not); keeps menu_index on one."""
        selectable = [i for i, r in enumerate(rows) if r[1] is not None or r[2]]
        if selectable and self.menu_index not in selectable:
            self.menu_index = selectable[0]
        return selectable

    def key_results(self, button, esc, c):
        rows = self.result_rows()
        selectable = self.result_index(rows)
        if not selectable:
            return
        if button in (keys.BUTTON_UP, keys.BUTTON_DOWN):
            at = selectable.index(self.menu_index) + (1 if button == keys.BUTTON_DOWN else -1)
            self.menu_index = selectable[at % len(selectable)]
            return
        action = rows[self.menu_index][4]
        if button == keys.BUTTON_CENTER and action:
            if action[0] == 'goto':
                self.probe = [action[1], action[2]]
            else:
                self.probe = list(self.pins[action[1]])
            self.page, self.view, self.note, self.peak = 'plots', 0, rows[self.menu_index][0], -1
        elif (button == keys.BUTTON_F2 or erase_key(self.vm, button)) and action and action[0] == 'pin':
            del self.pins[action[1]]
            self.result_cache = None

    # ------------------------------------------------------------ menus and files

    def menu_move(self, button, count):
        if button in (keys.BUTTON_UP, keys.BUTTON_DOWN) and count:
            self.menu_index = (self.menu_index + (1 if button == keys.BUTTON_DOWN else -1)) % count
            return True
        return False

    def key_options(self, button, esc, c):
        if self.menu_move(button, len(OPTIONS)) or button != keys.BUTTON_CENTER:
            return
        option = OPTIONS[self.menu_index][0]
        if option == 'Examples':
            self.page, self.menu_index = 'examples', 0
        elif option == 'New plate':
            self.replace_state(tm.new_state(), 'New plate')
        elif option == 'Save':
            self.ask_save()
        elif option == 'Open':
            self.files = cases.list_cases(self.vm.storage)
            self.page, self.menu_index = 'open', 0
        elif option.startswith('Export field'):
            self.export('field')
        elif option.startswith('Export profiles'):
            self.export('profiles')
        else:
            self.export('history')

    def key_examples(self, button, esc, c):
        if self.menu_move(button, len(EXAMPLES)) or button != keys.BUTTON_CENTER:
            return
        self.example(self.menu_index)

    def key_open(self, button, esc, c):
        if self.menu_move(button, len(self.files)) or button != keys.BUTTON_CENTER or not self.files:
            return
        name = self.files[self.menu_index]
        state = tm.from_case(cases.load_case(self.vm.storage, name, tm.TOOL))
        state['name'] = name
        self.replace_state(state, 'Opened ' + name)

    def ask_save(self):
        def apply(value):
            name = cases.clean_name(value)
            if name != self.state.get('name') and cases.exists(self.vm.storage, name) and self.confirm != name:
                self.confirm = name
                raise ValueError(name + ' exists: ENTER again replaces it')
            self.state['name'] = name
            cases.save_case(self.vm.storage, name, tm.to_case(self.state))
            self.confirm = None
            self.page = 'model'
            self.say('Saved ' + name)
        self.confirm = None
        self.prompt = {'title': 'Save plate as', 'detail': 'Saved to ' + cases.CASE_DIRECTORY + '. Letters, digits, - and _.',
                       'edit': LineEdit(self.state.get('name') or 'heat-1', cases.NAME_LIMIT), 'apply': apply, 'message': ''}

    def export(self, what):
        plate = self.plate
        if plate is None or not plate.done:
            raise ValueError('Evaluate and let it finish before exporting')
        if what == 'field':
            columns = ('x_mm', 'y_mm', 'T_C', 'qx_W_m2', 'qy_W_m2')

            def rows():
                for j in range(plate.ny):
                    for i in range(plate.nx):
                        x, y = plate.centre(j, i)
                        yield (x, y, plate.temperature(j, i)) + plate.flux(j, i)
        elif what == 'profiles':
            columns = ('along', 'x_mm', 'y_mm', 'T_C')
            pj, pi = self.probe_cell()

            def rows():
                for i, value in enumerate(plate.row(pj)):
                    yield (0,) + plate.centre(pj, i) + (value,)
                for j, value in enumerate(plate.column(pi)):
                    yield (1,) + plate.centre(j, pi) + (value,)
        else:
            if self.state['mode'] != 'transient':
                raise ValueError('History needs a transient')
            columns = ('t_s', 'min_C', 'mean_C', 'max_C')

            def rows():
                return iter(plate.history)
        stem = (self.state.get('name') or 'heat') + '-' + what
        path = cases.free_path(self.vm.storage, cases.EXPORT_DIRECTORY, stem, 'csv')
        cases.export_csv(self.vm.storage, path, columns, rows())
        self.say('Exported ' + path.rsplit('/', 1)[1])

    # ------------------------------------------------------------ drawing

    def properties_rect(self):
        size = self.vm.draw.size
        top = render.PROPERTIES_TOP
        return (8, top, int(size.x) - 16, int(size.y) - 12 - top - 3)

    def draw(self):
        draw = self.vm.draw
        p = self.palette()
        bottom = int(draw.size.y) - 12
        draw.fill_screen(p.BG)
        if self.page == 'model':
            self.draw_model(draw, p)
        elif self.page == 'options':
            menu(draw, p, OPTIONS, self.menu_index, 'HEAT / OPTIONS', bottom)
        elif self.page == 'examples':
            menu(draw, p, [(name, 'Replaces the inputs; Z undoes') for name, _, _, _ in EXAMPLES],
                 self.menu_index, 'HEAT / EXAMPLES', bottom)
        elif self.page == 'open':
            menu(draw, p, [(n, 'Opens without evaluating') for n in self.files] or
                 [('No saved cases', 'Options / Save creates one')], self.menu_index, 'HEAT / OPEN', bottom)
        else:
            panel(draw, p, (8, 43, int(draw.size.x) - 16, bottom - 46), '' if self.page == 'plots' else 'RESULTS')
            bounded = Viewport(draw, (10, 44, int(draw.size.x) - 10, bottom - 5))
            if self.page == 'plots':
                self.draw_plots(bounded, p, bottom)
            else:
                rows = self.result_rows()
                self.result_index(rows)
                results(bounded, p, [r[:4] for r in rows], self.menu_index, 67, bottom - 7)
        chrome(draw, p, self.page, self.message, self.error, title=TITLE, fallback=PATH)
        box = self.properties_rect() if self.page == 'model' else None
        if self.popup is not None:
            title, options, index, apply = self.popup
            popup(draw, p, title, options, index, box)
        if self.prompt is not None:
            q = self.prompt
            prompt(draw, p, q['title'], q['detail'], q['edit'], q['message'] or 'ENTER saves  ESC cancels',
                   bool(q['message']), box)
        draw.swap()

    def draw_model(self, draw, p):
        x, y, w, h = render.PREVIEW
        plate = self.plate
        panel(draw, p, render.PREVIEW, 'PLATE' if plate is None else 'TEMPERATURE', self.status(), p.PANEL)
        preview = Viewport(draw, (x + 5, y + 17, x + w - 5, y + h - 3))
        fit = render.Fit(self.state, render.PLATE_BOX)
        side, patch = self.chosen()
        if plate is None:
            render.blank(preview, p, fit)
        else:
            stats = plate.stats()
            low, high = render.span(stats['min'], stats['max'])
            render.field(preview, plate, fit, low, high, self.bands)
        render.patches(preview, p, self.state, fit, patch, plate is None or patch is not None)
        render.edges(preview, p, self.state, fit, side)
        render.side_labels(preview, p, self.state, fit, side)
        if self.problem:
            lines = wrap(self.problem, 46)[:2]
            top = y + h - 10 * len(lines) - 11
            draw._fill_rectangle(x + 5, top, w - 10, 10 * len(lines) + 7, p.BG)
            draw._rectangle(x + 5, top, w - 10, 10 * len(lines) + 7, p.ERROR)
            for n, line in enumerate(lines):
                text(draw, x + 10, top + 4 + 10 * n, line, p.ERROR)
        elif plate is None:
            right_text(draw, x + w - 8, y + h - 12, 'not evaluated', p.MUTED)
        else:
            render.colour_bar(preview, p, render.PLATE_BOX[0], render.PLATE_BOX[2], y + h - 23, low, high, self.bands)
            j, i = stats['hot']
            hx, hy = plate.centre(j, i)
            text(preview, x + 8, y + h - 12, 'max %s C at %s, %s mm  mean %s C' % (
                number(stats['max'], 4), number(hx, 3), number(hy, 3), number(stats['mean'], 4)), p.MUTED)
        rect = self.properties_rect()
        rows = self.rows()
        self.current()
        tabs(draw, p, rect, items.TABS, self.tab, [None] * len(items.TABS), font=XS, height=render.TAB_HEIGHT)
        form(draw, p, [row[:4] for row in rows], self.row, self.edit, rect[1] + render.TAB_HEIGHT + 4,
             rect[1] + rect[3] - 5, font=XS, row_height=render.ROW_HEIGHT)

    def draw_plots(self, draw, p, bottom):
        plate = self.plate
        if plate is None:
            for n, line in enumerate(wrap(self.problem or 'Not evaluated yet', 48)):
                text(draw, 16, 70 + 11 * n, line, p.ERROR if self.problem else p.MUTED)
            return
        views = self.views()
        self.view = min(self.view, len(views) - 1)
        view = views[self.view]
        j, i = self.probe_cell()
        x, y = plate.centre(j, i)
        qx, qy = plate.flux(j, i)
        q = (qx * qx + qy * qy) ** 0.5
        from math import atan2, degrees
        heading = 'x %s  y %s mm' % (number(x, 3), number(y, 3))
        text(draw, 16, 47, heading, p.TEXT, SM)
        when = 'Steady' if self.state['mode'] == 'steady' else 't = %s s' % number(plate.time, 4)
        right_text(draw, 304, 47, when, p.ACCENT, SM)
        readout = 'T %s C   |q| %s W/m2' % (number(plate.temperature(j, i), 5), number(q, 3))
        if q > 0:
            readout += ' to %d deg' % int(degrees(atan2(qy, qx)) % 360 + 0.5)
        text(draw, 16, 60, readout, p.TEXT)
        if view == 'history':
            text(draw, 16, 70, 'max', render.HOT)
            text(draw, 40, 70, 'mean', p.TEXT)
            text(draw, 70, 70, 'min', render.COLD)
        elif self.note:
            text(draw, 16, 70, self.note[:50], theme.AMBER)
        stats = plate.stats()
        low, high = render.span(stats['min'], stats['max'])
        if view == 'field':
            fit = render.Fit(self.state, render.PLOT_FIELD)
            render.field(draw, plate, fit, low, high, self.bands)
            render.patches(draw, p, self.state, fit, None, False)
            render.edges(draw, p, self.state, fit)
            for px, py in self.pins:
                pj, pi = plate.cell(px, py)
                render.marker(draw, plate, fit, pj, pi, theme.AMBER, p.BG)
            render.crosshair(draw, p, plate, fit, j, i)
            render.colour_bar(draw, p, render.PLOT_FIELD[0], render.PLOT_FIELD[2], render.PLOT_BAR_Y, low, high,
                              self.bands)
        elif view == 'profiles':
            xs = [plate.centre(j, n)[0] for n in range(plate.nx)]
            render.plot(draw, p, (render.LEFT, 82, render.RIGHT, 188), 'T along x at y = %s mm' % number(y, 3),
                        xs, ((plate.row(j), p.ACCENT),), x, 'C', 'mm', (0.0, self.state['W']))
            ys = [plate.centre(n, i)[1] for n in range(plate.ny)]
            render.plot(draw, p, (render.LEFT, 194, render.RIGHT, 300), 'T along y at x = %s mm' % number(x, 3),
                        ys, ((plate.column(i), theme.AMBER),), y, 'C', 'mm', (0.0, self.state['H']))
        else:
            history = plate.history
            ts = [row[0] for row in history]
            render.plot(draw, p, (render.LEFT, 82, render.RIGHT, 300), 'Temperature over time', ts,
                        (([row[3] for row in history], render.HOT), ([row[2] for row in history], p.TEXT),
                         ([row[1] for row in history], render.COLD)), plate.time, 'C', 's', (0.0, self.state['tend']))


class HeatView:
    HELP = HELP

    def __init__(self):
        self.app = None

    def start(self, vm):
        global _active
        self.app = _active = Heat(vm)
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
    return open_view(vm, 'thermal_view', HeatView())
