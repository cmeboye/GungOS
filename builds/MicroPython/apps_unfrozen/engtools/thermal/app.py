"""Heat transfer 2D in PicoLAB: conduction in a rectangular plate, steady or
transient, with fixed-temperature, convection, heat-flux and insulated sides
and heat sources, drawn as a temperature field beside the properties.

The inputs stay in RAM while PicoLAB runs. Steady state solves by itself
after every change; a transient waits for SPACE.
"""
from picoware.system import buttons as keys
from engtools.ui import theme
from engtools.ui.forms import LineEdit, parse_number, erase_key
from engtools.ui.lab import text, centre_text, panel, chrome, form, popup, Viewport, HEAD, FOOT
from engtools.units import number
from . import model as tm

TITLE = 'HEAT TRANSFER'
PATH = ('modules', 'thermal', 'Heat transfer 2D')
PREVIEW = (8, HEAD + 5, 304, 142)
FIELD = (14, 62, 244, 104)
BAR = (264, 62, 6, 104)
PROPERTIES_TOP = 191
BUDGET_MS = 30
LEVELS = 60
BAND = 6
STOPS = ((0.0, (24, 32, 150)), (0.25, (30, 140, 230)), (0.5, (60, 200, 110)),
         (0.75, (245, 220, 60)), (1.0, (225, 45, 30)))
EXAMPLES = (
    ('Slab: hot left, cold right', {}, {}),
    ('Chip on a cooled plate', {'W': 60.0, 'H': 60.0, 'depth': 5.0, 'gen': 0.0, 'pq': 4e6, 'px': 25.0,
                                'py': 25.0, 'pw': 10.0, 'ph': 10.0, 'res': 2},
     {i: {'kind': tm.CONVECTION, 'T': 25.0, 'h': 25.0} for i in range(4)}),
    ('Square, two hot sides', {'W': 60.0, 'H': 60.0, 'res': 2},
     {0: {'kind': tm.TEMPERATURE, 'T': 100.0}, 1: {'kind': tm.TEMPERATURE, 'T': 0.0},
      2: {'kind': tm.TEMPERATURE, 'T': 100.0}, 3: {'kind': tm.TEMPERATURE, 'T': 0.0}}),
    ('Wall: indoors and outdoors', {'W': 200.0, 'H': 80.0, 'material': 'Brick', 'res': 0},
     {0: {'kind': tm.CONVECTION, 'T': 20.0, 'h': 8.0}, 1: {'kind': tm.CONVECTION, 'T': -5.0, 'h': 25.0}}),
    ('Slab heated from inside', {'gen': 2e6},
     {0: {'kind': tm.TEMPERATURE, 'T': 20.0}, 1: {'kind': tm.TEMPERATURE, 'T': 20.0}}),
    ('Heated strip on top', {'W': 80.0, 'H': 40.0, 'material': 'Copper'},
     {0: {'kind': tm.INSULATED}, 1: {'kind': tm.INSULATED}, 2: {'kind': tm.CONVECTION, 'T': 20.0, 'h': 500.0},
      3: {'kind': tm.FLUX, 'q': 50000.0}}),
    ('Block cooling in air', {'mode': 'transient', 'W': 50.0, 'H': 50.0, 'material': 'Carbon steel', 'T0': 200.0,
                              'tend': 1200.0, 'res': 0},
     {i: {'kind': tm.CONVECTION, 'T': 20.0, 'h': 50.0} for i in range(4)}),
)
HELP = (
    'Moving and editing:',
    'UP/DOWN\tchoose a value',
    'ENTER\tedit or choose; type to replace',
    'ENTER/TAB\tapply',
    'ESC\tcancel the edit',
    'Arithmetic works: 120*0.8, 50/2',
    'Running:',
    'SPACE\trun or pause',
    'R\tstart again',
    'M\tsteady or transient',
    'C\tsmooth or banded colours',
    'F3\texamples',
    'F6\tprobe: arrows move it, ESC back',
    'ESC\tpause, then leave',
    'Steady state solves by itself after every change; a transient waits for SPACE.',
    'Edge lines:',
    'amber\tfixed temperature',
    'accent\tconvection',
    'white\theat flux',
    'grey\tinsulated',
    'Model:',
    'One material, 2D conduction; the faces are insulated. Heat flows are in W over the plate depth, '
    'positive into the plate. Values are at cell centres; temperature and convection sides act through '
    'half a cell. Heat flux is W/m2 into the plate.',
    'Units: mm, W/mK, kg/m3, J/kgK, W/m2K, W/m3, C, s',
)

_active = None
_lut = None


def palette_lut():
    """LEVELS colours from cold to hot as RGB565."""
    global _lut
    if _lut is None:
        table = []
        for n in range(LEVELS):
            t = n / (LEVELS - 1)
            for k in range(1, len(STOPS)):
                if t <= STOPS[k][0] or k == len(STOPS) - 1:
                    (t0, a), (t1, b) = STOPS[k - 1], STOPS[k]
                    f = (t - t0) / (t1 - t0)
                    r, g, bl = (int(a[c] + (b[c] - a[c]) * f) for c in range(3))
                    table.append(((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (bl >> 3))
                    break
        _lut = table
    return _lut


def material_index(name):
    for index, row in enumerate(tm.MATERIALS):
        if row[0] == name:
            return index
    return tm.CUSTOM


class Heat:
    def __init__(self, vm):
        self.vm = vm
        from engtools import session
        self.state = session.kept.get('thermal') or tm.new_state()
        self.row = 0
        self.edit = None
        self.popup = None
        self.focus = 'list'
        self.probe = [0.5, 0.5]
        self.bands = False
        self.message, self.error = '', False
        self.plate = None
        self.running = False
        self.restart()

    def keep(self):
        from engtools import session
        session.kept['thermal'] = self.state

    def palette(self):
        return theme.system_palette(self.vm)

    def say(self, message, error=False):
        self.message, self.error = message, error

    # ------------------------------------------------------------ solving

    def restart(self):
        """Build the plate again from the inputs; steady state starts solving."""
        self.plate, self.running = None, False
        self.plate_error = ''
        from gc import collect
        collect()
        try:
            self.plate = tm.Plate(self.state)
        except (ValueError, MemoryError) as exc:
            self.plate_error = str(exc) or 'Out of memory: use a coarser grid'
            self.say(self.plate_error, True)
            return
        if self.state['mode'] == 'steady':
            self.running = True
            self.say('')
        else:
            self.say('SPACE runs the transient')

    def finished(self):
        plate = self.plate
        self.running = False
        if self.state['mode'] == 'steady':
            if plate.converged:
                self.say('Converged after %d iterations' % plate.iterations)
            else:
                self.say('Stopped at %d iterations: not fully converged' % plate.iterations, True)
        else:
            self.say('Finished at t = %s s' % number(self.state['tend'], 4))

    def toggle_run(self):
        if self.plate is None:
            raise ValueError(self.plate_error or 'Nothing to run')
        if self.plate.done:
            self.restart()
            if self.state['mode'] == 'steady':
                return
        self.running = not self.running
        self.say('Running' if self.running else 'Paused')

    # ------------------------------------------------------------ rows

    def rows(self):
        """(kind, label, value text, editable, key, unit)"""
        s = self.state
        transient = s['mode'] == 'transient'
        out = []

        def head(title):
            out.append(('head', title, '', False, None, ''))

        def field(label, value, key=None, unit=''):
            out.append(('field', label, value, key is not None, key, unit))

        def quantity(label, key, unit, digits=5):
            field(label, number(self.get(key), digits) + ' ' + unit, key, unit)
        head('Analysis')
        field('Mode', 'Transient' if transient else 'Steady', 'mode', 'choice')
        if transient:
            quantity('End time', 'tend', 's')
            quantity('Initial temperature', 'T0', 'C')
        head('Plate')
        quantity('Width', 'W', 'mm')
        quantity('Height', 'H', 'mm')
        quantity('Depth', 'depth', 'mm')
        field('Material', tm.MATERIALS[s['mat']][0], 'mat', 'choice')
        quantity('Conductivity k', 'k', 'W/mK')
        if transient:
            quantity('Density', 'rho', 'kg/m3')
            quantity('Specific heat', 'cp', 'J/kgK')
        field('Grid', tm.RESOLUTION_NAMES[s['res']], 'res', 'choice')
        head('Heat sources')
        quantity('Whole plate', 'gen', 'W/m3')
        quantity('Heat patch', 'pq', 'W/m3')
        if s['pq'] != 0:
            for label, key in (('Patch x', 'px'), ('Patch y', 'py'), ('Patch width', 'pw'), ('Patch height', 'ph')):
                quantity(label, key, 'mm')
        for index, side in enumerate(s['sides']):
            name = tm.SIDES[index]
            head(name + ' side')
            field('Condition', tm.KINDS[side['kind']], 'side:%d:kind' % index, 'choice')
            if side['kind'] == tm.TEMPERATURE:
                quantity('Temperature', 'side:%d:T' % index, 'C')
            elif side['kind'] == tm.CONVECTION:
                quantity('Ambient', 'side:%d:T' % index, 'C')
                quantity('Coefficient h', 'side:%d:h' % index, 'W/m2K')
            elif side['kind'] == tm.FLUX:
                quantity('Heat flux in', 'side:%d:q' % index, 'W/m2')
        head('Results')
        plate = self.plate
        if plate is None:
            field('Status', 'not solvable', None)
            return out
        stats, flows = plate.stats(), plate.flows()
        field('Lowest', number(stats['min'], 5) + ' C')
        field('Highest', number(stats['max'], 5) + ' C')
        field('Mean', number(stats['mean'], 5) + ' C')
        j, i = stats['hot']
        field('Hottest at', '%s, %s mm' % (number((i + 0.5) * plate.dx * 1000, 3), number((j + 0.5) * plate.dy * 1000, 3)))
        for index, name in enumerate(tm.SIDES):
            field(name + ' heat in', number(flows['sides'][index], 4) + ' W')
        if flows['generated']:
            field('Generated', number(flows['generated'], 4) + ' W')
        if transient:
            field('Stored rate', number(flows['net'], 4) + ' W')
            alpha = tm.diffusivity(s)
            longest = max(s['W'], s['H']) / 1000
            field('Diffusion time', number(longest * longest / alpha, 3) + ' s')
        else:
            share = 100 * abs(flows['net']) / flows['scale'] if flows['scale'] else 0.0
            field('Imbalance', number(share, 2) + ' %')
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

    # ------------------------------------------------------------ changes

    def target(self, key):
        """The dictionary and entry a row key refers to."""
        if key.startswith('side:'):
            _, index, name = key.split(':')
            return self.state['sides'][int(index)], name
        return self.state, key

    def get(self, key):
        owner, name = self.target(key)
        return owner[name]

    def set(self, key, value):
        owner, name = self.target(key)
        if name in ('W', 'H', 'depth'):
            if not 0.1 <= value <= 10000:
                raise ValueError('Keep sizes between 0.1 and 10000 mm')
        elif name in ('k', 'rho', 'cp', 'h', 'tend'):
            if not 0 < value <= 1e9:
                raise ValueError('Must be positive')
        elif name in ('T', 'T0'):
            if not -273.15 <= value <= 10000:
                raise ValueError('Keep temperatures between -273 and 10000 C')
        elif name in ('px', 'py') and value < 0:
            raise ValueError('The patch must lie inside the plate')
        elif name in ('pw', 'ph') and value <= 0:
            raise ValueError('Must be positive')
        elif abs(value) > 1e12:
            raise ValueError('Too large')
        owner[name] = value
        if name in ('k', 'rho', 'cp'):
            self.state['mat'] = tm.CUSTOM
        self.changed()

    def changed(self):
        self.restart()

    def set_mode(self, mode):
        self.state['mode'] = mode
        self.restart()
        self.say('Transient: SPACE runs it' if mode == 'transient' else 'Steady state')

    def set_material(self, index):
        s = self.state
        s['mat'] = index
        if index != tm.CUSTOM:
            _, s['k'], s['rho'], s['cp'] = tm.MATERIALS[index]
        self.changed()

    def example(self, index):
        name, values, sides = EXAMPLES[index]
        state = tm.new_state()
        values = dict(values)
        material = values.pop('material', 'Aluminium 6061')
        state.update(values)
        for side, changes in sides.items():
            state['sides'][side].update(changes)
        self.state = state
        self.set_material(material_index(material))
        self.row = 1
        self.say(name)

    def begin_edit(self, button=None):
        kind, label, value, editable, key, unit = self.current()
        if kind == 'head':
            return
        if not editable:
            raise ValueError('Worked out from the inputs')
        if key == 'mode':
            self.popup = ['Mode', ('Steady state', 'Transient'), 0 if self.state['mode'] == 'steady' else 1,
                          lambda i: self.set_mode(('steady', 'transient')[i])]
            return
        if key == 'mat':
            self.popup = ['Material', tuple(m[0] for m in tm.MATERIALS), self.state['mat'], self.set_material]
            return
        if key == 'res':
            def choose(i):
                self.state['res'] = i
                self.changed()
            self.popup = ['Grid', tm.RESOLUTION_NAMES, self.state['res'], choose]
            return
        if key.endswith(':kind'):
            owner, name = self.target(key)

            def choose(i):
                owner['kind'] = i
                self.changed()
                self.clamp_row()
            self.popup = [tm.SIDES[int(key.split(':')[1])] + ' side', tm.KINDS, owner['kind'], choose]
            return
        if button is None or erase_key(self.vm, button):
            self.edit = LineEdit(number(self.get(key), 7), 16)
            if button is not None:
                self.edit.key(self.vm, button)
        else:
            self.edit = LineEdit('', 16)
            self.edit.key(self.vm, button)

    def clamp_row(self):
        self.row = min(self.row, len(self.rows()) - 1)

    def commit(self):
        key = self.current()[4]
        value = parse_number(self.edit.text)
        self.set(key, value)
        self.edit = None

    # ------------------------------------------------------------ keys

    def run(self, button):
        """Handle a key and advance a running solve; True when the screen changes."""
        dirty = False
        if button != keys.BUTTON_NONE:
            dirty = True
            try:
                self.handle(button)
            except (ValueError, TypeError, ZeroDivisionError, OverflowError) as exc:
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

    def handle(self, button):
        esc = button == self.vm.input_manager._key_esc
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
        if button == keys.BUTTON_F6:
            self.focus = 'list' if self.focus == 'field' else 'field'
            self.say('Probe: arrows move it' if self.focus == 'field' else '')
            return
        if self.focus == 'field':
            self.key_probe(button, esc)
            return
        self.message, self.error = '', False
        if esc:
            if self.running:
                self.running = False
                self.say('Paused')
            else:
                self.vm.back()
            return
        c = self.vm.input_manager.button_to_char(button)
        c = c.lower() if c else ''
        row = self.current()
        typing = row[5] not in ('choice', '')
        if button in (keys.BUTTON_UP, keys.BUTTON_DOWN):
            self.move(-1 if button == keys.BUTTON_UP else 1)
        elif button == keys.BUTTON_CENTER:
            self.begin_edit()
        elif button == keys.BUTTON_F3:
            self.popup = ['Examples', tuple(name for name, _, _ in EXAMPLES), 0, self.example]
        elif button == keys.BUTTON_SPACE or c == ' ':
            self.toggle_run()
        elif c == 'r':
            self.restart()
            self.say('Started again' if self.running else self.message)
        elif c == 'm':
            self.set_mode('steady' if self.state['mode'] == 'transient' else 'transient')
        elif c == 'c':
            self.bands = not self.bands
            self.say('Banded colours' if self.bands else 'Smooth colours')
        elif typing and ((c and (c.isdigit() or c in '-.(')) or erase_key(self.vm, button)):
            self.begin_edit(button)

    def key_probe(self, button, esc):
        plate = self.plate
        if esc:
            self.focus = 'list'
            self.say('')
        elif button == keys.BUTTON_SPACE:
            self.toggle_run()
        elif plate is not None:
            dx = (button == keys.BUTTON_RIGHT) - (button == keys.BUTTON_LEFT)
            dy = (button == keys.BUTTON_UP) - (button == keys.BUTTON_DOWN)
            self.probe[0] = min(max(self.probe[0] + dx / plate.nx, 0.0), 0.9999)
            self.probe[1] = min(max(self.probe[1] + dy / plate.ny, 0.0), 0.9999)

    def probe_cell(self):
        plate = self.plate
        return int(self.probe[1] * plate.ny), int(self.probe[0] * plate.nx)

    # ------------------------------------------------------------ drawing

    def properties_rect(self):
        size = self.vm.draw.size
        return (8, PROPERTIES_TOP, int(size.x) - 16, int(size.y) - FOOT - PROPERTIES_TOP - 3)

    def status(self):
        plate = self.plate
        if plate is None:
            return 'not solvable'
        if self.state['mode'] == 'steady':
            return ('%d iterations' % plate.iterations) if self.running else ('converged' if plate.done and plate.converged else
                                                                      'paused' if plate.iterations else 'ready')
        return 't = %s s  %d%%' % (number(plate.time, 4), int(100 * plate.progress))

    def draw(self):
        draw = self.vm.draw
        p = self.palette()
        draw.fill_screen(p.BG)
        s = self.state
        panel(draw, p, PREVIEW, 'TEMPERATURE', self.status(), p.PANEL)
        if self.focus == 'field':
            x, y, w, h = PREVIEW
            draw._rectangle(x, y, w, h, p.ACCENT)
            draw._rectangle(x + 1, y + 1, w - 2, h - 2, p.ACCENT)
        if self.plate is None:
            centre_text(draw, 160, 100, 'Not solvable', p.ERROR)
            if self.plate_error:
                text(Viewport(draw, (16, 118, 304, 160)), 16, 118, self.plate_error[:48], p.MUTED)
        else:
            self.draw_field(draw, p)
        rect = self.properties_rect()
        rows = self.rows()
        self.row = min(self.row, len(rows) - 1)
        panel(draw, p, rect, 'PROPERTIES', '%d/%d' % (self.row + 1, len(rows)))
        form(draw, p, [row[:4] for row in rows], self.row, self.edit, PROPERTIES_TOP + 26, rect[1] + rect[3] - 5)
        chrome(draw, p, s['mode'], self.message, self.error, title=TITLE, fallback=PATH)
        if self.popup is not None:
            title, options, index, apply = self.popup
            popup(draw, p, title, options, index, rect)
        draw.swap()

    def draw_field(self, draw, p):
        plate = self.plate
        fx, fy, fw, fh = FIELD
        nx, ny = plate.nx, plate.ny
        scale = min(fw / nx, fh / ny)
        w, h = int(scale * nx), int(scale * ny)
        ox, oy = fx + (fw - w) // 2, fy + (fh - h) // 2
        stats = plate.stats()
        low, high = stats['min'], stats['max']
        if high - low < 1e-6:
            low, high = low - 0.5, high + 0.5
        span = high - low
        k = (LEVELS - 0.001) / span
        colours = palette_lut()
        ref = plate.ref - low
        rows = plate.T.tolist()
        bands = self.bands
        for j in range(ny):
            top = oy + h - int((j + 1) * scale + 0.5)
            height = oy + h - int(j * scale + 0.5) - top
            row = rows[j]
            for i in range(nx):
                left = ox + int(i * scale + 0.5)
                index = int((row[i] + ref) * k)
                if bands:
                    index = index // BAND * BAND + BAND // 2
                draw._fill_rectangle(left, top, ox + int((i + 1) * scale + 0.5) - left, height,
                                     colours[min(LEVELS - 1, max(0, index))])
        # The side conditions along the four edges.
        shade = {tm.INSULATED: p.GRID, tm.TEMPERATURE: theme.AMBER, tm.CONVECTION: p.ACCENT, tm.FLUX: p.TEXT}
        sides = self.state['sides']
        draw._fill_rectangle(ox - 3, oy, 2, h, shade[sides[0]['kind']])
        draw._fill_rectangle(ox + w + 1, oy, 2, h, shade[sides[1]['kind']])
        draw._fill_rectangle(ox, oy + h + 1, w, 2, shade[sides[2]['kind']])
        draw._fill_rectangle(ox, oy - 3, w, 2, shade[sides[3]['kind']])
        # Probe cell.
        pj, pi = self.probe_cell()
        left = ox + int(pi * scale + 0.5)
        top = oy + h - int((pj + 1) * scale + 0.5)
        size = max(3, int(scale))
        draw._rectangle(left - 1, top - 1, size + 2, size + 2, p.BG)
        draw._rectangle(left, top, size, size, p.TEXT)
        # Colour bar with its range.
        bx, by, bw, bh = BAR
        for n in range(bh):
            draw._fill_rectangle(bx, by + n, bw, 1, colours[min(LEVELS - 1, int((bh - 1 - n) * LEVELS / bh))])
        text(draw, bx + bw + 3, by, number(high, 3), p.TEXT)
        text(draw, bx + bw + 3, by + bh - 8, number(low, 3), p.TEXT)
        summary = 'probe %s mm  %s C' % ('%s, %s' % (number((pi + 0.5) * plate.dx * 1000, 3),
                                                     number((pj + 0.5) * plate.dy * 1000, 3)),
                                         number(plate.temperature(pj, pi), 4))
        text(draw, 16, 173, summary, p.MUTED)


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
