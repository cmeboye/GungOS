"""PicoSpice in PicoLAB: draw a circuit on a grid of nodes, connect elements
between them, place probes and simulate.

The model page shows the schematic above Node, Element, Probe and Sim tabs.
TAB moves to the schematic's grid cursor (arrows move it, + and - zoom).
Only F6 simulates; editing clears the results. F4 shows the probes'
waveforms, F5 the results and F3 holds examples and files. The circuit stays
in RAM while PicoLAB runs; saving to the SD card is explicit.
"""
from picoware.system import buttons as keys
from engtools.ui import theme
from engtools.ui.forms import LineEdit, erase_key
from engtools.ui.lab import (text, right_text, panel, chrome, form, popup, prompt, menu, results, tabs, wrap,
                             Viewport, XS, SM)
from engtools import cases
from . import model as sm
from . import items
from . import render

TITLE = 'PICOSPICE'
PATH = ('modules', 'electrical', 'PicoSpice')
BUDGET_MS = 40
UNDO_LIMIT = 12
OPTIONS = (
    ('New circuit', 'Blank: place nodes with TAB and F1; Z undoes'),
    ('Examples', 'Ready-made circuits to simulate'),
    ('Save', 'Write the circuit to SD'),
    ('Open', 'Load a saved circuit without simulating'),
    ('Export CSV', 'Probe samples; small runs fit Eggcel'),
)
HELP = (
    'Model:',
    'LEFT/RIGHT\tNode, Element, Probe, Sim tabs',
    'UP/DOWN\tchoose an item or a value',
    'ENTER\topen an item, edit a value or choose',
    '[ / ]\tcycle the highlighted choice, or the items',
    'ESC\tcancel, close the item, then leave',
    'F1\tadd: a node at the cursor, an element, a probe',
    'F2\tremove the selected item',
    'Z\tundo (12 steps)',
    'Values take SPICE suffixes: 4.7k, 10u, 2meg (m is milli).',
    'Schematic:',
    'TAB\tgrid cursor: arrows move it, TAB or ESC back',
    'ENTER\tselect the node or element at the cursor',
    'F1\ta node at the cursor (in any tab)',
    '+ / -\tzoom; names show from the third zoom',
    'A new element joins the selected node and the nodes nearest it; '
    'change its pins with [ ] and watch the schematic.',
    'Wires join nodes into one net. Ground any node in the Node tab: '
    'every grounded node is the same ground.',
    'Simulating:',
    'F6\tsimulate the Sim tab analysis: the only solve command',
    'ESC\tstop a running simulation',
    'Edits clear the results.',
    'Operating point: node voltages show on the schematic.',
    'Probes:',
    'Voltage: a node against ground, or against a minus node',
    'Current: at a node, flowing into one of its elements',
    'Pages:',
    'F3\toptions: new, examples, save, open, CSV',
    'F4\twaveforms: LEFT/RIGHT cursor, , and . step 10',
    'UP/DOWN\tchoose the probe; P its maximum and minimum',
    'F5\tresults: final, extremes, mean, RMS, peak to peak',
    'ENTER\ton an extreme: show it in the waveforms',
    'Models:',
    'Diode: Shockley. BJT: Ebers-Moll with Early voltage. MOSFET: level 1. '
    'Op-amp: ideal or a finite gain, no output limits. Switch: smooth Ron to Roff.',
    'Currents are positive into the pin: a source that supplies reads negative.',
)

_active = None


class Spice:
    def __init__(self, vm):
        self.vm = vm
        from engtools import session
        kept = session.kept.get('spice') or {}
        self.circuit = kept.get('circuit')
        self.tab = kept.get('tab', items.NODE)
        self.tab_selections = [None] * len(items.TABS)
        self.sel = None
        self.page = 'model' if self.circuit else 'start'
        self.view = False
        self.zoom = kept.get('zoom', 1)
        self.center = kept.get('center', [0, 0])
        self.cursor = kept.get('cursor', [0, 0])
        self.edit = self.popup = self.prompt = self.choice = None
        self.last_node = -1     # where new elements and probes attach
        self.menu_index = 0
        self.files = []
        self.confirm = None
        self.undo = []
        self.sim, self.running, self.problem = None, False, None
        self.active, self.at, self.peak, self.panes = 0, 0, -1, None
        self.result_cache = None
        self.message, self.error = '', False
        if self.circuit:
            self.restore_selection()

    def keep(self):
        """What survives closing PicoSpice while PicoLAB stays open: the
        circuit and the view, not the results or the undo history."""
        from engtools import session
        if self.circuit is not None:
            session.kept['spice'] = {'circuit': self.circuit, 'tab': self.tab, 'zoom': self.zoom,
                                     'center': self.center, 'cursor': self.cursor}

    def palette(self):
        return theme.system_palette(self.vm)

    def say(self, message, error=False):
        self.message, self.error = message, error

    # ------------------------------------------------------------ circuit changes

    def snapshot(self):
        self.undo.append(sm.copy(self.circuit))
        if len(self.undo) > UNDO_LIMIT:
            del self.undo[0]

    def drop(self):
        """Clear results after an edit; never simulate."""
        self.sim, self.running, self.problem = None, False, None
        self.panes = self.result_cache = None
        from gc import collect
        collect()

    def replace(self, circuit, message):
        if self.circuit is not None:
            self.snapshot()
        self.circuit = circuit
        self.drop()
        self.zoom, self.center = render.fit_zoom(circuit)
        nodes = circuit['nodes']
        self.cursor = [nodes[0][0], nodes[0][1]] if nodes else [0, 0]
        self.tab_selections = [None] * len(items.TABS)
        self.tab = items.ELEMENT if circuit['elements'] else items.NODE
        self.view = False
        self.last_node = -1
        self.restore_selection()
        self.page = 'model'
        self.say(message)

    def undo_last(self):
        if not self.undo:
            raise ValueError('Nothing to undo')
        self.circuit = self.undo.pop()
        self.drop()
        self.last_node = -1
        self.tab_selections = [None] * len(items.TABS)
        self.restore_selection()
        self.say('Undone')

    # ------------------------------------------------------------ selection

    def rows(self):
        """(kind, label, value, editable, ref, field) in the current tab."""
        c = self.circuit
        if self.tab == items.SIM:
            ref = ('sim', 0)
            return [('field', f[1], items.text(c, ref, f), f[4], ref, f) for f in items.fields(c, ref)]
        out = []
        expanded = self.sel[0] if self.sel and self.sel[1] is not None else None
        for ref in items.refs(c, self.tab):
            if expanded is not None and ref != expanded:
                continue
            out.append(('head', items.title(c, ref), '', True, ref, None))
            if ref == expanded:
                for f in items.fields(c, ref):
                    out.append(('field', f[1], items.text(c, ref, f), f[4], ref, f))
        return out

    def row_index(self, rows):
        if not rows:
            return -1
        if self.sel:
            ref, field = self.sel
            for i, row in enumerate(rows):
                if row[4] == ref and (row[5][0] if row[5] else None) == field:
                    return i
            for i, row in enumerate(rows):
                if row[4] == ref:
                    return i
        return 0

    def current(self):
        rows = self.rows()
        i = self.row_index(rows)
        return rows[i] if i >= 0 else None

    def restore_selection(self):
        refs = items.refs(self.circuit, self.tab)
        sel = self.tab_selections[self.tab]
        if sel is None or sel[0] not in refs:
            sel = (refs[0], None) if refs else None
        self.sel = sel

    def select(self, ref, field=None, move=True):
        tab = items.tab_of(ref)
        if tab != self.tab:
            self.tab_selections[self.tab] = self.sel
            self.tab = tab
        self.sel = (ref, field)
        self.tab_selections[tab] = self.sel
        if ref[0] == 'node':
            self.last_node = ref[1]
        if move:
            point = self.point_of(ref)
            if point is not None:
                self.cursor = list(point)
                self.follow()

    def point_of(self, ref):
        c = self.circuit
        kind, i = ref
        if kind == 'node':
            return c['nodes'][i][:2]
        if kind == 'element':
            nodes = [c['nodes'][n] for n in c['elements'][i]['nodes']]
            return (int(sum(n[0] for n in nodes) / len(nodes) + 0.5), int(sum(n[1] for n in nodes) / len(nodes) + 0.5))
        if kind == 'probe':
            p = c['probes'][i]
            return c['nodes'][p['a'] if p['kind'] == 'V' else p['node']][:2]
        return None

    def chosen_ref(self):
        return self.sel[0] if self.sel else None

    def move_row(self, step):
        rows = self.rows()
        if not rows:
            return
        index = min(max(self.row_index(rows) + step, 0), len(rows) - 1)
        row = rows[index]
        self.select(row[4], row[5][0] if row[5] else None)

    def switch_tab(self, step):
        self.tab_selections[self.tab] = self.sel
        self.tab = (self.tab + step) % len(items.TABS)
        self.restore_selection()
        if self.sel:
            self.select(*self.sel)

    def cycle_item(self, step):
        refs = items.refs(self.circuit, self.tab)
        if not refs or self.tab == items.SIM:
            return
        ref = self.chosen_ref()
        i = refs.index(ref) if ref in refs else -1
        self.select(refs[(i + step) % len(refs)])

    # ------------------------------------------------------------ the grid cursor

    def follow(self):
        """Scroll so the cursor stays at least a pitch inside the schematic."""
        grid = render.Grid(self.center, self.zoom)
        left, top, right, bottom = render.AREA
        pitch = grid.pitch
        px, py = grid.p(*self.cursor)
        if px < left + pitch:
            self.center[0] -= (left + pitch - px + pitch - 1) // pitch
        elif px > right - pitch:
            self.center[0] += (px - right + pitch + pitch - 1) // pitch
        if py < top + pitch:
            self.center[1] -= (top + pitch - py + pitch - 1) // pitch
        elif py > bottom - pitch:
            self.center[1] += (py - bottom + pitch + pitch - 1) // pitch

    def set_zoom(self, step):
        self.zoom = min(max(self.zoom + step, 0), len(render.ZOOMS) - 1)
        self.center = [self.cursor[0], self.cursor[1]]
        self.say('Zoom %d of %d' % (self.zoom + 1, len(render.ZOOMS)))

    def at_cursor(self):
        """The node, else the element, at the grid cursor."""
        c = self.circuit
        node = sm.node_at(c, *self.cursor)
        if node >= 0:
            return ('node', node)
        for i in range(len(c['elements'])):
            if list(self.point_of(('element', i))) == self.cursor:
                return ('element', i)
        return None

    # ------------------------------------------------------------ adding and removing

    def anchor(self):
        """The node new items attach to: the node last selected (in the
        list or with the cursor), else the node at or nearest the cursor."""
        c = self.circuit
        if not c['nodes']:
            raise ValueError('Place a node first: TAB, arrows, F1')
        if 0 <= self.last_node < len(c['nodes']):
            return self.last_node
        here = sm.node_at(c, *self.cursor)
        if here >= 0:
            return here
        return min(range(len(c['nodes'])), key=lambda i: self.distance(i, self.cursor))

    def distance(self, i, point):
        x, y = self.circuit['nodes'][i][:2]
        return (x - point[0]) ** 2 + (y - point[1]) ** 2

    def add_node(self):
        self.snapshot()
        try:
            i = sm.add_node(self.circuit, self.cursor[0], self.cursor[1])
        except ValueError:
            self.undo.pop()
            raise
        self.drop()
        self.select(('node', i), move=False)
        self.say('%s placed at (%d,%d)' % (sm.node_label(self.circuit, i), self.cursor[0], self.cursor[1]))

    def add_element(self, kind):
        c = self.circuit
        pins = len(sm.INFO[kind][3])
        if len(c['nodes']) < pins:
            raise ValueError('%s needs %d nodes: place them first (TAB, F1)' % (sm.INFO[kind][1], pins))
        first = self.anchor()
        point = c['nodes'][first][:2]
        others = sorted((i for i in range(len(c['nodes'])) if i != first), key=lambda i: self.distance(i, point))
        self.snapshot()
        e = sm.new_element(c, kind, [first] + others[:pins - 1])
        self.drop()
        self.select(('element', e), 'pin0')
        self.say('%s added: [ ] changes its pins' % c['elements'][e]['name'])

    def add_probe(self, kind):
        c = self.circuit
        node = self.anchor()
        element = -1
        if kind == 'I':
            element = next((e for e, t in sm.links(c, node) if c['elements'][e]['kind'] != 'W'), -1)
            if element < 0:
                raise ValueError('%s has no element to measure into' % sm.node_label(c, node))
        self.snapshot()
        k = sm.new_probe(c, kind, node, element)
        self.drop()
        self.select(('probe', k), 'a' if kind == 'V' else 'element')
        self.say('Probe P%d: %s' % (k + 1, sm.probe_label(c, c['probes'][k])))

    def add(self):
        if self.view or self.tab == items.NODE:
            self.add_node()
        elif self.tab == items.ELEMENT:
            kinds = sm.KINDS
            self.popup = ['Add element', [k[1] for k in kinds], 1, lambda i: self.add_element(kinds[i][0])]
        elif self.tab == items.PROBE:
            self.popup = ['Add probe', ['Voltage at a node', 'Current into an element'], 0,
                          lambda i: self.add_probe('VI'[i])]
        else:
            raise ValueError('Nothing to add here')

    def remove(self):
        ref = self.at_cursor() if self.view else self.chosen_ref()
        if ref is None or ref[0] == 'sim':
            raise ValueError('Select a node, element or probe')
        c = self.circuit
        kind, i = ref
        self.snapshot()
        try:
            if kind == 'node':
                name = sm.node_label(c, i)
                sm.remove_node(c, i)
            elif kind == 'element':
                name = c['elements'][i]['name']
                sm.remove_element(c, i)
            else:
                name = 'P%d' % (i + 1)
                del c['probes'][i]
        except ValueError:
            self.undo.pop()
            raise
        self.drop()
        self.last_node = -1
        self.tab_selections = [None] * len(items.TABS)
        self.restore_selection()
        self.say('%s removed: Z undoes' % name)

    # ------------------------------------------------------------ editing

    def begin_edit(self, first=None):
        row = self.current()
        if row is None:
            return
        if row[0] == 'head':
            fields = items.fields(self.circuit, row[4])
            if fields:
                self.select(row[4], fields[0][0])
            return
        if not row[3]:
            raise ValueError('Worked out from the circuit')
        ref, f = row[4], row[5]
        if f[2] == 'choice':
            self.choice = {'ref': ref, 'field': f[0], 'before': sm.copy(self.circuit),
                           'index': items.choice_index(self.circuit, ref, f[0]),
                           'options': [o[0] for o in items.options(self.circuit, ref, f[0])], 'title': f[1]}
            return
        if first is None:
            value = items.get(self.circuit, ref, f[0])
            shown = value if f[2] in ('text', 'int') else sm.eng(value)
            self.edit = LineEdit(str(shown), 120 if f[2] == 'text' else 24)
        else:
            self.edit = LineEdit('', 120 if f[2] == 'text' else 24)
            self.edit.key(self.vm, first)

    def commit_edit(self):
        row = self.current()
        ref, f = row[4], row[5]
        before = sm.copy(self.circuit)
        items.set_text(self.circuit, ref, f[0], self.edit.text)
        self.undo.append(before)
        if len(self.undo) > UNDO_LIMIT:
            del self.undo[0]
        self.edit = None
        self.drop()

    def cycle_choice(self, step):
        row = self.current()
        if row is None or row[0] != 'field' or row[5][2] != 'choice':
            self.cycle_item(step)
            return
        ref, field = row[4], row[5][0]
        n = len(items.options(self.circuit, ref, field))
        self.snapshot()
        items.set_choice(self.circuit, ref, field, (items.choice_index(self.circuit, ref, field) + step) % n)
        self.drop()
        self.select(ref, field)

    def key_choice(self, button, esc):
        q = self.choice
        c = self.char(button)
        if esc:
            self.circuit = q['before']
            self.choice = None
            self.drop()
            self.select(q['ref'], q['field'])
        elif button in (keys.BUTTON_UP, keys.BUTTON_DOWN) or c in ('[', ']'):
            q['index'] = (q['index'] + (-1 if button == keys.BUTTON_UP or c == '[' else 1)) % len(q['options'])
            items.set_choice(self.circuit, q['ref'], q['field'], q['index'])
            self.drop()
            self.select(q['ref'], q['field'])
            q['options'] = [o[0] for o in items.options(self.circuit, q['ref'], q['field'])]
        elif button == keys.BUTTON_CENTER:
            self.undo.append(q['before'])
            if len(self.undo) > UNDO_LIMIT:
                del self.undo[0]
            self.choice = None
            self.select(q['ref'], q['field'])

    # ------------------------------------------------------------ simulating

    def simulate(self):
        self.drop()
        try:
            self.sim = sm.Simulation(self.circuit)
        except sm.CircuitError as exc:
            self.problem = (exc.node, exc.element)
            if exc.element is not None:
                self.select(('element', exc.element))
            elif exc.node is not None:
                self.select(('node', exc.node))
            self.say(str(exc), True)
            return
        except MemoryError:
            self.say('Out of memory: fewer points or probes', True)
            return
        self.active = 0
        self.at = 0
        if self.sim.done:
            self.finished()
        else:
            self.running = True
            self.say('Simulating')

    def finished(self):
        self.running = False
        self.panes = self.result_cache = None
        sim = self.sim
        if sim.kind == 'op':
            self.say('Operating point solved: F5 lists it all')
        else:
            self.at = sim.count - 1
            self.say('%s done: F4 waveforms, F5 results' % ('Transient' if sim.kind == 'tran' else 'Sweep'))

    def status(self):
        sim = self.sim
        name = sm.ANALYSIS_NAMES[sm.ANALYSES.index(self.circuit['sim']['kind'])]
        if self.running:
            done, total = sim.progress
            return '%s %d%%' % (name.split()[0], 100 * done // max(1, total))
        if self.view:
            return 'cursor (%d,%d)' % tuple(self.cursor)
        return name + (' / solved' if sim is not None else '')

    # ------------------------------------------------------------ keys

    def run(self, button):
        dirty = False
        if button != keys.BUTTON_NONE:
            dirty = True
            try:
                self.handle(button)
            except (ValueError, TypeError, KeyError, IndexError, ZeroDivisionError, OverflowError, RuntimeError,
                    OSError) as exc:
                self.say(str(exc) or 'Not possible here', True)
        if self.running and self.sim is not None:
            dirty = True
            self.panes = None
            try:
                if self.sim.advance(BUDGET_MS):
                    self.finished()
            except sm.CircuitError as exc:
                self.running = False
                self.problem = (exc.node, exc.element)
                self.say(str(exc), True)
            except MemoryError:
                self.running = False
                self.say('Out of memory: fewer points or probes', True)
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
        if self.choice is not None:
            self.key_choice(button, esc)
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
                self.commit_edit()
                if result in ('up', 'down'):
                    self.move_row(-1 if result == 'up' else 1)
            return
        self.message, self.error = '', False
        c = self.char(button)
        if self.page in ('start', 'examples', 'open', 'options'):
            getattr(self, 'key_' + self.page)(button, esc)
            return
        if button == keys.BUTTON_F6:
            self.simulate()
            return
        page = {keys.BUTTON_F3: 'options', keys.BUTTON_F4: 'plots', keys.BUTTON_F5: 'results'}.get(button)
        if page:
            self.page, self.menu_index, self.view = page, 0, False
            return
        if esc and self.running:
            self.running = False
            self.say('Stopped: results so far in F4 and F5')
            return
        if self.page != 'model' and esc:
            self.page = 'model'
            return
        getattr(self, 'key_' + self.page)(button, esc, c)

    def leave_preview(self):
        self.view = False
        kept = getattr(self, 'preview_input', None)
        if kept is not None:
            self.tab, self.sel, self.tab_selections, self.last_node = kept
            self.preview_input = None

    def key_model(self, button, esc, c):
        if self.view and c in ('+', '='):
            self.set_zoom(1)
        elif self.view and c == '-':
            self.set_zoom(-1)
        elif c == 'z':
            self.undo_last()
        elif button == keys.BUTTON_F1:
            self.preview_input = None
            self.add()
        elif button == keys.BUTTON_F2:
            self.preview_input = None
            self.remove()
        elif button == keys.BUTTON_TAB:
            if self.view:self.leave_preview()
            else:
                self.preview_input = (self.tab, self.sel, self.tab_selections[:], self.last_node)
                self.view = True
            self.say('Schematic: arrows move, ENTER selects' if self.view else '')
        elif self.view:
            self.key_view(button, esc)
        elif esc:
            if self.sel and self.sel[1] is not None and self.tab != items.SIM:
                self.select(self.sel[0], move=False)
            else:
                self.vm.back()
        elif button in (keys.BUTTON_LEFT, keys.BUTTON_RIGHT):
            self.switch_tab(-1 if button == keys.BUTTON_LEFT else 1)
        elif button in (keys.BUTTON_UP, keys.BUTTON_DOWN):
            self.move_row(-1 if button == keys.BUTTON_UP else 1)
        elif c in ('[', ']'):
            self.cycle_choice(-1 if c == '[' else 1)
        elif button == keys.BUTTON_CENTER:
            self.begin_edit()
        else:
            row = self.current()
            numeric = row is not None and row[0] == 'field' and row[5][2] != 'choice'
            if numeric and (erase_key(self.vm, button) or c and (c.isdigit() or c in '-.(')):
                self.begin_edit(button)

    def key_view(self, button, esc):
        if esc:
            self.leave_preview()
            return
        step = {keys.BUTTON_LEFT: (-1, 0), keys.BUTTON_RIGHT: (1, 0), keys.BUTTON_UP: (0, -1),
                keys.BUTTON_DOWN: (0, 1)}.get(button)
        if step:
            self.cursor = [min(max(self.cursor[0] + step[0], -99), 99), min(max(self.cursor[1] + step[1], -99), 99)]
            self.follow()
            ref = self.at_cursor()
            if ref is not None:
                self.select(ref, move=False)
        elif button == keys.BUTTON_CENTER:
            ref = self.at_cursor()
            if ref is None:
                raise ValueError('Nothing here: F1 places a node')
            self.select(ref, move=False)
            self.view = False

    # ------------------------------------------------------------ waveforms

    def key_plots(self, button, esc, c):
        sim = self.sim
        if sim is None or not sim.points:
            raise ValueError('Simulate a DC sweep or transient first (F6)')
        if not self.circuit['probes']:
            raise ValueError('Add a probe in the Probe tab')
        n = max(1, sim.count)
        step = max(1, sim.points // (render.PLOT_RIGHT - render.PLOT_LEFT))
        if button in (keys.BUTTON_LEFT, keys.BUTTON_RIGHT) or c in (',', '.'):
            size = step * (10 if c in (',', '.') else 1)
            sign = -1 if button == keys.BUTTON_LEFT or c == ',' else 1
            self.at = min(max(self.at + sign * size, 0), n - 1)
            self.peak = -1
        elif button in (keys.BUTTON_UP, keys.BUTTON_DOWN):
            self.active = (self.active + (1 if button == keys.BUTTON_DOWN else -1)) % len(self.circuit['probes'])
            self.peak = -1
        elif c == 'p':
            st = sim.stats(self.active)
            self.peak = (self.peak + 1) % 2
            self.at = st['at_max'] if self.peak == 0 else st['at_min']
            self.say('Maximum' if self.peak == 0 else 'Minimum')

    # ------------------------------------------------------------ results

    def result_rows(self):
        sim = self.sim
        if sim is None:
            return [('Not simulated', None, self.message if self.error else 'F6 simulates the Sim tab analysis',
                     None, None)]
        key = (sim.count, self.running)
        if self.result_cache is None or self.result_cache[0] != key:
            self.result_cache = (key, self.build_rows(sim))
        return self.result_cache[1]

    def build_rows(self, sim):
        c = self.circuit
        out = []
        if sim.kind == 'op':
            op = sim.op
            out.append(('Operating point', 'solved', '%d iterations' % sim.info['iterations'], None, None))
            out.append(('Nodes', None, '', None, None))
            for i, v in enumerate(op['nodes']):
                x, y, grounded = c['nodes'][i]
                out.append((sm.node_label(c, i), sm.eng(v, 'V') if v is not None else '--',
                            '(%d,%d)%s' % (x, y, ' ground' if grounded else '' if v is not None else ' not connected'),
                            None, None))
            out.append(('Elements', None, '', None, None))
            for i, e in enumerate(c['elements']):
                if e['kind'] == 'W':
                    continue
                currents = op['currents'][i]
                pins = sm.INFO[e['kind']][3]
                if len(pins) == 2:
                    va, vb = op['nodes'][e['nodes'][0]], op['nodes'][e['nodes'][1]]
                    v = va - vb
                    detail = 'into %s  V %s  P %s' % (pins[0], sm.eng(v, 'V', 3), sm.eng(v * currents[0], 'W', 3))
                else:
                    detail = 'into %s; ' % pins[0] + '  '.join(
                        '%s %s' % (pins[t], sm.eng(currents[t], 'A', 3)) for t in range(1, len(pins)))
                out.append((e['name'], sm.eng(currents[0], 'A'), detail, None, None))
            if c['probes']:
                out.append(('Probes', None, '', None, None))
                for k, p in enumerate(c['probes']):
                    out.append(('P%d %s' % (k + 1, sm.probe_label(c, p)), sm.eng(op['probes'][k], sm.probe_unit(p)),
                                '', None, None))
        else:
            done, total = sim.progress
            name = 'Transient' if sim.kind == 'tran' else 'DC sweep'
            state = 'running' if self.running else 'done' if sim.done else 'stopped'
            out.append((name, state, '%d of %d points' % (done, total), None, None))
            unit_x = sim.x_unit()
            where = 'at t = ' if sim.kind == 'tran' else 'at '
            for k, p in enumerate(c['probes']):
                st = sim.stats(k)
                if st is None:
                    continue
                unit = sm.probe_unit(p)
                out.append(('P%d %s' % (k + 1, sm.probe_label(c, p)), None, '', None, None))
                out.append(('Final', sm.eng(st['final'], unit), '', None, None))
                out.append(('Maximum', sm.eng(st['max'], unit), where + sm.eng(sim.x(st['at_max']), unit_x),
                            None, ('at', k, st['at_max'])))
                out.append(('Minimum', sm.eng(st['min'], unit), where + sm.eng(sim.x(st['at_min']), unit_x),
                            None, ('at', k, st['at_min'])))
                out.append(('Average', sm.eng(st['mean'], unit), 'over the %s' % ('run' if sim.kind == 'tran' else 'sweep'),
                            None, None))
                out.append(('RMS', sm.eng(st['rms'], unit), '', None, None))
                out.append(('Peak to peak', sm.eng(st['pp'], unit), '', None, None))
        info = getattr(sim, 'info', None)
        if info:
            out.append(('Solver', None, '', None, None))
            out.append(('Equations', str(info['equations']), '%d entries, %d in the factors' % (
                info['entries'], info['factors']), None, None))
            detail = '%d iterations' % info['iterations']
            if sim.kind == 'tran':
                detail += ', %d steps, %d repeated' % (info['steps'], info['rejected'])
            out.append(('Memory', '%d KB' % (info['bytes'] // 1024 + 1), detail, None, None))
        return out

    def result_index(self, rows):
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
        elif button == keys.BUTTON_CENTER:
            action = rows[self.menu_index][4]
            if action and action[0] == 'at':
                self.active, self.at, self.page = action[1], action[2], 'plots'

    # ------------------------------------------------------------ menus and files

    def menu_move(self, button, count):
        if button in (keys.BUTTON_UP, keys.BUTTON_DOWN) and count:
            self.menu_index = (self.menu_index + (1 if button == keys.BUTTON_DOWN else -1)) % count
            return True
        return False

    def start_rows(self):
        return ([('Blank circuit', 'Place nodes with TAB and F1')] +
                [(name, 'Example') for name in sm.EXAMPLES] + [('Open saved', 'Circuits on SD')])

    def key_start(self, button, esc):
        rows = self.start_rows()
        if esc:
            if self.circuit is None:
                self.vm.back()
            else:
                self.page = 'model'
            return
        if self.menu_move(button, len(rows)) or button != keys.BUTTON_CENTER:
            return
        if self.menu_index == 0:
            self.replace(sm.new_circuit(), 'Blank: TAB for the cursor, F1 places nodes')
        elif self.menu_index == len(rows) - 1:
            self.files = cases.list_cases(self.vm.storage)
            self.page, self.menu_index = 'open', 0
        else:
            self.replace(sm.example(self.menu_index - 1), sm.EXAMPLES[self.menu_index - 1] + ': F6 simulates')

    def key_examples(self, button, esc):
        if esc:
            self.page = 'options'
            return
        if self.menu_move(button, len(sm.EXAMPLES)) or button != keys.BUTTON_CENTER:
            return
        self.replace(sm.example(self.menu_index), sm.EXAMPLES[self.menu_index] + ': F6 simulates')

    def key_options(self, button, esc):
        if esc:
            self.page = 'model'
            return
        if self.menu_move(button, len(OPTIONS)) or button != keys.BUTTON_CENTER:
            return
        option = OPTIONS[self.menu_index][0]
        if option == 'New circuit':
            self.replace(sm.new_circuit(), 'Blank: TAB for the cursor, F1 places nodes')
        elif option == 'Examples':
            self.page, self.menu_index = 'examples', 0
        elif option == 'Save':
            self.ask_save()
        elif option == 'Open':
            self.files = cases.list_cases(self.vm.storage)
            self.page, self.menu_index = 'open', 0
        else:
            self.export()

    def key_open(self, button, esc):
        if esc:
            self.page = 'options' if self.circuit else 'start'
            self.menu_index = 0
            return
        if self.menu_move(button, len(self.files)) or button != keys.BUTTON_CENTER or not self.files:
            return
        name = self.files[self.menu_index]
        circuit = sm.from_case(cases.load_case(self.vm.storage, name, 'spice'))
        circuit['name'] = name
        self.replace(circuit, 'Opened ' + name)

    def ask_save(self):
        def apply(value):
            name = cases.clean_name(value)
            if name != self.circuit.get('name') and cases.exists(self.vm.storage, name) and self.confirm != name:
                self.confirm = name
                raise ValueError(name + ' exists: ENTER again replaces it')
            self.circuit['name'] = name
            cases.save_case(self.vm.storage, name, sm.to_case(self.circuit))
            self.confirm = None
            self.page = 'model'
            self.say('Saved ' + name)
        self.confirm = None
        self.prompt = {'title': 'Save circuit as', 'detail': 'Saved to ' + cases.CASE_DIRECTORY + '. Letters, digits, - and _.',
                       'edit': LineEdit(self.circuit.get('name') or 'circuit-1', cases.NAME_LIMIT), 'apply': apply,
                       'message': ''}

    def export(self):
        sim = self.sim
        if sim is None or not sim.points or not sim.count:
            raise ValueError('Simulate a DC sweep or transient first (F6)')
        c = self.circuit
        columns = ['t_s' if sim.kind == 'tran' else 'sweep_' + sim.x_unit()]
        for k, p in enumerate(c['probes']):
            label = ''.join(ch if ch.isalpha() or ch.isdigit() else '_' for ch in sm.probe_label(c, p))
            columns.append('P%d_%s_%s' % (k + 1, label.strip('_'), sm.probe_unit(p)))

        def rows():
            for i in range(sim.count):
                yield (sim.x(i),) + tuple(trace[i] for trace in sim.traces)
        compact = (sim.count + 1) * len(columns) <= 511
        stem = (c.get('name') or 'circuit') + ('-eggcel' if compact else '-full')
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
        if self.page == 'start':
            menu(draw, p, self.start_rows(), self.menu_index, 'PICOSPICE / NEW', bottom)
        elif self.page == 'options':
            menu(draw, p, OPTIONS, self.menu_index, 'PICOSPICE / OPTIONS', bottom)
        elif self.page == 'examples':
            menu(draw, p, [(n, 'Replaces the circuit; Z undoes') for n in sm.EXAMPLES], self.menu_index,
                 'PICOSPICE / EXAMPLES', bottom)
        elif self.page == 'open':
            menu(draw, p, [(n, 'Opens without simulating') for n in self.files] or
                 [('No saved circuits', 'Options / Save creates one')], self.menu_index, 'PICOSPICE / OPEN', bottom)
        elif self.page == 'model':
            self.draw_model(draw, p)
        else:
            panel(draw, p, (8, 43, int(draw.size.x) - 16, bottom - 46), '' if self.page == 'plots' else 'RESULTS')
            bounded = Viewport(draw, (10, 44, int(draw.size.x) - 10, bottom - 5))
            if self.page == 'plots':
                self.draw_plots(bounded, p, bottom)
            else:
                rows = self.result_rows()
                self.result_index(rows)
                results(bounded, p, [r[:4] for r in rows], self.menu_index, 67, bottom - 7)
        chrome(draw, p, self.page if self.page in ('model', 'plots', 'results') else 'menu', self.message, self.error,
               title=TITLE, fallback=PATH)
        box = self.properties_rect() if self.page == 'model' else None
        if self.popup is not None:
            title, options, index, apply = self.popup
            popup(draw, p, title, options, index, box)
        if self.choice is not None:
            q = self.choice
            popup(draw, p, q['title'] + ' / [ ] preview', q['options'], q['index'], box)
        if self.prompt is not None:
            q = self.prompt
            prompt(draw, p, q['title'], q['detail'], q['edit'], q['message'] or 'ENTER saves  ESC cancels',
                   bool(q['message']), box)
        draw.swap()

    def draw_model(self, draw, p):
        c = self.circuit
        x, y, w, h = render.PREVIEW
        panel(draw, p, render.PREVIEW, 'SCHEMATIC', self.status(), p.PANEL)
        area = Viewport(draw, render.AREA)
        grid = render.Grid(self.center, self.zoom)
        problem = self.problem if self.problem and self.error else None
        render.schematic(area, p, c, grid, self.chosen_ref(), self.cursor, self.view, self.sim, problem)
        if not c['nodes']:
            text(draw, x + 10, y + 70, 'Empty: TAB, arrows, then F1 places a node', p.MUTED)
        rect = self.properties_rect()
        tabs(draw, p, rect, items.TABS, self.tab,
             [len(c['nodes']), len(c['elements']), len(c['probes']), None], font=XS, height=render.TAB_HEIGHT)
        rows = self.rows()
        index = self.row_index(rows)
        if rows:
            form(draw, p, [r[:4] for r in rows], index, self.edit, rect[1] + render.TAB_HEIGHT + 4,
                 rect[1] + rect[3] - 5, font=XS, row_height=render.ROW_HEIGHT)
        else:
            hint = ('F1 places a node at the cursor (TAB moves it)', 'F1 adds an element at the selected node',
                    'F1 adds a voltage or current probe')[self.tab]
            text(draw, rect[0] + 10, rect[1] + render.TAB_HEIGHT + 8, 'Nothing yet', p.MUTED)
            text(draw, rect[0] + 10, rect[1] + render.TAB_HEIGHT + 20, hint, p.MUTED)

    def draw_plots(self, draw, p, bottom):
        sim, c = self.sim, self.circuit
        if sim is None or not sim.points or not c['probes']:
            lines = wrap('Operating point: node voltages are on the schematic and in F5.' if sim is not None
                         else 'Not simulated yet: F6 runs the Sim tab analysis.' if c['probes']
                         else 'No probes: add one in the Probe tab.', 48)
            for n, line in enumerate(lines):
                text(draw, 16, 70 + 11 * n, line, p.MUTED)
            return
        self.active = min(self.active, len(c['probes']) - 1)
        self.at = min(self.at, max(0, sim.count - 1))
        k = self.active
        probe = c['probes'][k]
        unit_x = sim.x_unit()
        text(draw, 16, 47, ('t ' if sim.kind == 'tran' else 'at ') + sm.eng(sim.x(self.at), unit_x), p.TEXT, SM)
        value = sim.traces[k][self.at] if sim.count else 0.0
        right_text(draw, 304, 47, sm.eng(value, sm.probe_unit(probe)), render.PROBE_COLORS[k % len(render.PROBE_COLORS)],
                   SM)
        top = render.legend(draw, p, c, k, 61)
        key = (sim.count, top, k)
        if self.panes is None or self.panes[0] != key:
            self.panes = None
            self.panes = (key, render.build_panes(c, sim, top + 2, bottom - 8))
        render.waveforms(draw, p, c, sim, self.panes[1], self.at, k)


class SpiceView:
    HELP = HELP

    def __init__(self):
        self.app = None

    def start(self, vm):
        global _active
        self.app = _active = Spice(vm)
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
    return open_view(vm, 'spice_view', SpiceView())
