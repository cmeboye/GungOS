"""PicoSpice circuits: the element catalogue, the circuit as saved, checks,
the simulation through picosolve.Circuit and its results.

A circuit is a dict. nodes: [x, y, grounded] on the whole-number grid, y
down. elements: {'kind', 'name', 'nodes', 'values'} plus a waveform for
sources and a control element for F and H. Wires join nodes into one net
and grounded nodes all belong to the ground net, the solver's node 0.
Values are SI floats keyed by field. No drawing and no storage here.
"""
from array import array
from engtools.units import number

MAX_NODES = 50
MAX_ELEMENTS = 80
MAX_PROBES = 8

# kind, title, name prefix, pin labels, value fields (id, label, unit, default)
KINDS = (
    ('W', 'Wire', 'W', ('A', 'B'), ()),
    ('R', 'Resistor', 'R', ('A', 'B'), (('R', 'Resistance', 'ohm', 1e3),)),
    ('C', 'Capacitor', 'C', ('+', '-'), (('C', 'Capacitance', 'F', 1e-6), ('v0', 'Start voltage', 'V', 0.0))),
    ('L', 'Inductor', 'L', ('A', 'B'), (('L', 'Inductance', 'H', 1e-3), ('i0', 'Start current', 'A', 0.0))),
    ('V', 'Voltage source', 'V', ('+', '-'), (('dc', 'DC value', 'V', 5.0),)),
    ('I', 'Current source', 'I', ('+', '-'), (('dc', 'DC value', 'A', 1e-3),)),
    ('D', 'Diode', 'D', ('Anode', 'Cathode'), (('Is', 'Saturation Is', 'A', 1e-14), ('N', 'Ideality N', '', 1.0))),
    ('NPN', 'NPN transistor', 'Q', ('C', 'B', 'E'),
     (('Is', 'Saturation Is', 'A', 1e-15), ('BF', 'Beta forward', '', 100.0), ('BR', 'Beta reverse', '', 1.0),
      ('VAF', 'Early voltage', 'V', 0.0))),
    ('PNP', 'PNP transistor', 'Q', ('C', 'B', 'E'),
     (('Is', 'Saturation Is', 'A', 1e-15), ('BF', 'Beta forward', '', 100.0), ('BR', 'Beta reverse', '', 1.0),
      ('VAF', 'Early voltage', 'V', 0.0))),
    ('NMOS', 'N-channel MOSFET', 'M', ('D', 'G', 'S'),
     (('VTO', 'Threshold', 'V', 1.0), ('KP', 'KP x W/L', 'A/V2', 1e-3), ('LAMBDA', 'Lambda', '1/V', 0.0))),
    ('PMOS', 'P-channel MOSFET', 'M', ('D', 'G', 'S'),
     (('VTO', 'Threshold', 'V', -1.0), ('KP', 'KP x W/L', 'A/V2', 1e-3), ('LAMBDA', 'Lambda', '1/V', 0.0))),
    ('E', 'Voltage-controlled V', 'E', ('+', '-', 'c+', 'c-'), (('gain', 'Gain', 'V/V', 10.0),)),
    ('G', 'Voltage-controlled I', 'G', ('+', '-', 'c+', 'c-'), (('gm', 'Gm', 'A/V', 1e-3),)),
    ('F', 'Current-controlled I', 'F', ('+', '-'), (('gain', 'Gain', 'A/A', 1.0),)),
    ('H', 'Current-controlled V', 'H', ('+', '-'), (('r', 'Gain', 'V/A', 1e3),)),
    ('OPAMP', 'Op-amp', 'U', ('in+', 'in-', 'out'), (('A', 'Open-loop gain (0 ideal)', '', 0.0),)),
    ('SW', 'Voltage switch', 'S', ('A', 'B', 'c+', 'c-'),
     (('Ron', 'R on', 'ohm', 1.0), ('Roff', 'R off', 'ohm', 1e6), ('Vt', 'Threshold', 'V', 2.5),
      ('Vh', 'Half transition', 'V', 0.1))),
)
INFO = dict((k[0], k) for k in KINDS)
BRANCH = ('L', 'V', 'E', 'H', 'OPAMP')   # elements whose current can control F and H
SOURCES = ('V', 'I')

WAVES = ('DC', 'PULSE', 'SIN', 'PWL')
WAVE_FIELDS = {
    'PULSE': (('v1', 'Initial', '*', 0.0), ('v2', 'Pulsed', '*', 5.0), ('td', 'Delay', 's', 0.0),
              ('tr', 'Rise', 's', 1e-6), ('tf', 'Fall', 's', 1e-6), ('pw', 'Width', 's', 1e-3),
              ('per', 'Period', 's', 2e-3)),
    'SIN': (('vo', 'Offset', '*', 0.0), ('va', 'Amplitude', '*', 1.0), ('freq', 'Frequency', 'Hz', 1e3),
            ('td', 'Delay', 's', 0.0), ('theta', 'Damping', '1/s', 0.0), ('phase', 'Phase', 'deg', 0.0)),
}

ANALYSES = ('op', 'dc', 'tran')
ANALYSIS_NAMES = ('Operating point', 'DC sweep', 'Transient')
SIM_DEFAULTS = {'kind': 'tran', 'source': -1, 'start': 0.0, 'stop': 5.0, 'points': 51,
                'tstop': 5e-3, 'tpoints': 501, 'hmax': 0.0, 'uic': False}
POINT_LIMIT = 2001

SUFFIXES = (('meg', 1e6), ('t', 1e12), ('g', 1e9), ('k', 1e3), ('m', 1e-3), ('u', 1e-6), ('n', 1e-9),
            ('p', 1e-12), ('f', 1e-15))
ENGINEERING = ((1e12, 'T'), (1e9, 'G'), (1e6, 'Meg'), (1e3, 'k'), (1.0, ''), (1e-3, 'm'), (1e-6, 'u'),
               (1e-9, 'n'), (1e-12, 'p'), (1e-15, 'f'))


class CircuitError(ValueError):
    """A problem that names the node or element to fix (index or None)."""

    def __init__(self, message, node=None, element=None):
        super().__init__(message)
        self.node, self.element = node, element


# ---------------------------------------------------------------- values

def parse_value(text):
    """A number with an optional SPICE suffix (4.7k, 10u, 2meg; m is milli),
    or arithmetic such as 2*pi*50."""
    from engtools.ui.forms import parse_number
    t = text.strip().lower().replace('\xb5', 'u')
    for suffix, scale in SUFFIXES:
        head = t[:-len(suffix)]
        if t.endswith(suffix) and head and (head[-1].isdigit() or head[-1] in '.)'):
            return parse_number(head) * scale
    return parse_number(t)


def eng(value, unit='', digits=4):
    """With a unit, a prefixed unit after a space: 5 ms, 4.7 kohm, 2 MV.
    Without, a SPICE value that can be typed back: 4.7k, 100n, 2Meg."""
    if value != value:
        return '--' + (' ' + unit if unit else '')
    size = abs(value)
    if unit == 'deg' or size < 1e-18 or size >= 1e15 or size < 1e-15:
        return number(value, digits) + (' ' + unit if unit else '')
    for scale, suffix in ENGINEERING:
        if size >= scale * 0.99995:
            break
    shown = number(value / scale, digits)
    if not unit:
        return shown + suffix
    return shown + ' ' + ('M' if suffix == 'Meg' else suffix) + unit


def value_unit(kind, unit):
    """A waveform field's unit follows its source: V or A."""
    return ('V' if kind == 'V' else 'A') if unit == '*' else unit


# ---------------------------------------------------------------- the circuit

def new_circuit():
    return {'nodes': [], 'elements': [], 'probes': [], 'sim': dict(SIM_DEFAULTS), 'name': None}


def copy(c):
    out = {'nodes': [list(n) for n in c['nodes']], 'elements': [], 'probes': [dict(p) for p in c['probes']],
           'sim': dict(c['sim']), 'name': c.get('name')}
    for e in c['elements']:
        d = dict(e)
        d['nodes'] = list(e['nodes'])
        d['values'] = dict(e['values'])
        if 'wave_values' in e:
            d['wave_values'] = dict(e['wave_values'])
        if 'pwl' in e:
            d['pwl'] = [list(p) for p in e['pwl']]
        out['elements'].append(d)
    return out


def node_label(c, i):
    if i < 0:
        return 'Ground'
    return 'N%d' % (i + 1)


def node_at(c, x, y):
    for i, n in enumerate(c['nodes']):
        if n[0] == x and n[1] == y:
            return i
    return -1


def add_node(c, x, y, grounded=False):
    if len(c['nodes']) >= MAX_NODES:
        raise ValueError('Up to %d nodes' % MAX_NODES)
    if node_at(c, x, y) >= 0:
        raise ValueError('A node is already there')
    c['nodes'].append([x, y, bool(grounded)])
    return len(c['nodes']) - 1


def links(c, i):
    """(element, terminal) pairs attached to node i."""
    return [(e, t) for e, el in enumerate(c['elements']) for t, n in enumerate(el['nodes']) if n == i]


def name_for(c, prefix):
    used = set(e['name'] for e in c['elements'])
    n = 1
    while '%s%d' % (prefix, n) in used:
        n += 1
    return '%s%d' % (prefix, n)


def new_element(c, kind, nodes):
    info = INFO[kind]
    if len(c['elements']) >= MAX_ELEMENTS:
        raise ValueError('Up to %d elements' % MAX_ELEMENTS)
    if len(nodes) != len(info[3]):
        raise ValueError('%s needs %d nodes' % (info[1], len(info[3])))
    e = {'kind': kind, 'name': name_for(c, info[2]), 'nodes': list(nodes),
         'values': dict((f[0], f[3]) for f in info[4])}
    if kind in SOURCES:
        e['wave'] = 'DC'
    if kind in ('F', 'H'):
        e['ctrl'] = next((i for i, x in enumerate(c['elements']) if x['kind'] in BRANCH), -1)
    c['elements'].append(e)
    return len(c['elements']) - 1


def set_wave(e, wave):
    """Choose a source's waveform, starting it from the DC value."""
    e['wave'] = wave
    if wave in WAVE_FIELDS and e.get('wave_kind') != wave:
        e['wave_values'] = dict((f[0], f[3]) for f in WAVE_FIELDS[wave])
        e['wave_kind'] = wave
        e['wave_values']['v2' if wave == 'PULSE' else 'va'] = e['values']['dc']
    if wave == 'PWL' and 'pwl' not in e:
        e['pwl'] = [[0.0, 0.0], [1e-3, e['values']['dc']]]


def pwl_text(e):
    return ', '.join('%s %s' % (eng(t), eng(v)) for t, v in e.get('pwl', ()))


def parse_pwl(text):
    """'0 0, 1m 5, 2m 5': time and value pairs, times not decreasing."""
    points = []
    for part in text.replace(';', ',').split(','):
        words = part.split()
        if not words:
            continue
        if len(words) != 2:
            raise ValueError('Write pairs: time value, time value')
        t, v = parse_value(words[0]), parse_value(words[1])
        if points and t < points[-1][0]:
            raise ValueError('Times must not decrease')
        points.append([t, v])
    if not points:
        raise ValueError('Give at least one time and value')
    if len(points) > 64:
        raise ValueError('Up to 64 points')
    return points


def new_probe(c, kind, node, element=-1):
    if len(c['probes']) >= MAX_PROBES:
        raise ValueError('Up to %d probes' % MAX_PROBES)
    if kind == 'V':
        p = {'kind': 'V', 'a': node, 'b': -1}
    else:
        p = {'kind': 'I', 'node': node, 'element': element}
    c['probes'].append(p)
    return len(c['probes']) - 1


def probe_label(c, p):
    if p['kind'] == 'V':
        if p['b'] < 0:
            return 'V(%s)' % node_label(c, p['a'])
        return 'V(%s,%s)' % (node_label(c, p['a']), node_label(c, p['b']))
    e = p['element']
    name = c['elements'][e]['name'] if 0 <= e < len(c['elements']) else '?'
    return 'I(%s>%s)' % (node_label(c, p['node']), name)


def probe_unit(p):
    return 'V' if p['kind'] == 'V' else 'A'


def remove_node(c, i):
    if links(c, i):
        raise ValueError('%s is connected: remove its elements first' % node_label(c, i))
    if any(p['kind'] == 'V' and i in (p['a'], p['b']) or p['kind'] == 'I' and p['node'] == i for p in c['probes']):
        raise ValueError('%s is probed: remove its probe first' % node_label(c, i))
    del c['nodes'][i]
    for e in c['elements']:
        e['nodes'] = [n - (n > i) for n in e['nodes']]
    for p in c['probes']:
        for key in ('a', 'b', 'node'):
            if key in p and p[key] > i:
                p[key] -= 1


def remove_element(c, i):
    """Remove an element with the current probes on it; F and H that it
    controlled are left without a control until one is chosen."""
    del c['elements'][i]
    c['probes'] = [p for p in c['probes'] if not (p['kind'] == 'I' and p['element'] == i)]
    for p in c['probes']:
        if p['kind'] == 'I' and p['element'] > i:
            p['element'] -= 1
    for e in c['elements']:
        if e.get('ctrl', -1) == i:
            e['ctrl'] = -1
        elif e.get('ctrl', -1) > i:
            e['ctrl'] -= 1
    s = c['sim']
    if s['source'] == i:
        s['source'] = -1
    elif s['source'] > i:
        s['source'] -= 1


def element_summary(c, e):
    """'1k', '5 V' or 'PULSE': an element's main value; empty for devices."""
    kind = e['kind']
    if kind in ('W', 'D', 'NPN', 'PNP', 'NMOS', 'PMOS', 'SW'):
        return ''
    if kind == 'OPAMP':
        return 'ideal' if e['values']['A'] == 0 else 'A ' + eng(e['values']['A'])
    if e.get('wave', 'DC') != 'DC':
        return e['wave']
    f = INFO[kind][4][0]
    return eng(e['values'][f[0]], f[2] if kind in SOURCES else '')


def bounds(c):
    if not c['nodes']:
        return 0, 0, 0, 0
    xs = [n[0] for n in c['nodes']]
    ys = [n[1] for n in c['nodes']]
    return min(xs), min(ys), max(xs), max(ys)


# ---------------------------------------------------------------- nets

def nets(c):
    """Each node's net: 0 for ground, then 1, 2, ... for nets that a solver
    element touches; -1 for nets nothing but wires touch."""
    parent = list(range(len(c['nodes'])))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for e in c['elements']:
        if e['kind'] == 'W':
            a, b = root(e['nodes'][0]), root(e['nodes'][1])
            if a != b:
                parent[a] = b
    grounded = set(root(i) for i, n in enumerate(c['nodes']) if n[2])
    used = set()
    for e in c['elements']:
        if e['kind'] != 'W':
            for n in e['nodes']:
                used.add(root(n))
    ids, out = {}, []
    for i in range(len(c['nodes'])):
        r = root(i)
        if r in grounded:
            out.append(0)
        elif r in used:
            if r not in ids:
                ids[r] = len(ids) + 1
            out.append(ids[r])
        else:
            out.append(-1)
    return out, len(ids) + 1


def check(c):
    """Raise CircuitError, naming what to fix, before anything is solved."""
    if not any(n[2] for n in c['nodes']):
        raise CircuitError('Ground a node: Node tab, Ground')
    if not any(e['kind'] != 'W' for e in c['elements']):
        raise CircuitError('Add an element first')
    for i, e in enumerate(c['elements']):
        if e['kind'] in ('F', 'H'):
            ctrl = e.get('ctrl', -1)
            if not 0 <= ctrl < len(c['elements']) or c['elements'][ctrl]['kind'] not in BRANCH:
                raise CircuitError('%s needs a control: a V, L, E, H or op-amp' % e['name'], element=i)
        if e['kind'] != 'W' and len(set(e['nodes'])) == 1:
            raise CircuitError('%s has every pin on one node' % e['name'], element=i)
    s = c['sim']
    if s['kind'] == 'dc':
        src = s['source']
        if not 0 <= src < len(c['elements']) or c['elements'][src]['kind'] not in SOURCES:
            raise CircuitError('Choose a V or I source to sweep: Sim tab')
        if not 1 <= s['points'] <= POINT_LIMIT:
            raise CircuitError('Sweep points: 1 to %d' % POINT_LIMIT)
    if s['kind'] == 'tran' and (not s['tstop'] > 0 or not 2 <= s['tpoints'] <= POINT_LIMIT):
        raise CircuitError('Transient: a positive stop time and 2 to %d points' % POINT_LIMIT)
    net, count = nets(c)
    for k, p in enumerate(c['probes']):
        for key in ('a', 'b', 'node'):
            n = p.get(key, -1)
            if n >= 0 and net[n] < 0:
                raise CircuitError('%s is not connected to an element' % node_label(c, n), node=n)
        if p['kind'] == 'I':
            e = p['element']
            if not 0 <= e < len(c['elements']) or p['node'] not in c['elements'][e]['nodes']:
                raise CircuitError('Probe %d: choose an element at %s' % (k + 1, node_label(c, p['node'])))
            if c['elements'][e]['kind'] == 'W':
                raise CircuitError('Probe %d: current probes go on elements, not wires' % (k + 1))
    if count < 2:
        raise CircuitError('Everything is grounded: nothing to solve')
    return net, count


# ---------------------------------------------------------------- simulation

class Simulation:
    """One analysis of a circuit: an operating point solves at once; a DC
    sweep or transient steps in slices through advance()."""

    def __init__(self, c):
        import picosolve as ps
        C = ps.Circuit
        net, count = check(c)
        self.c, self.net = c, net
        s = c['sim']
        self.kind = s['kind']
        self.solver = [i for i, e in enumerate(c['elements']) if e['kind'] != 'W']
        index = dict((e, k) for k, e in enumerate(self.solver))
        pool = 32
        for i in self.solver:
            e = c['elements'][i]
            pool += len(INFO[e['kind']][4]) + 7 + 2 * len(e.get('pwl', ()))
        probes = c['probes']
        circuit = self.circuit = C(count, len(self.solver), values=pool, probes=max(1, len(probes)))
        try:
            for k, i in enumerate(self.solver):
                e = c['elements'][i]
                values = tuple(e['values'][f[0]] for f in INFO[e['kind']][4])
                nodes = tuple(net[n] for n in e['nodes'])
                if e['kind'] in ('F', 'H'):
                    circuit.element(k, getattr(C, e['kind']), nodes, values, index[e['ctrl']])
                else:
                    circuit.element(k, getattr(C, e['kind']), nodes, values)
                wave = e.get('wave', 'DC')
                if wave in WAVE_FIELDS:
                    circuit.wave(k, getattr(C, wave), tuple(e['wave_values'][f[0]] for f in WAVE_FIELDS[wave]))
                elif wave == 'PWL':
                    flat = []
                    for t, v in e['pwl']:
                        flat += (t, v)
                    circuit.wave(k, C.PWL, tuple(flat))
            for k, p in enumerate(probes):
                if p['kind'] == 'V':
                    circuit.probe(k, C.VOLTAGE, net[p['a']], net[p['b']] if p['b'] >= 0 else 0)
                else:
                    e = c['elements'][p['element']]
                    circuit.probe(k, C.CURRENT, index[p['element']], e['nodes'].index(p['node']))
            self.points = 0
            if self.kind == 'op':
                circuit.op()
            elif self.kind == 'dc':
                self.points = s['points']
                circuit.dc(index[s['source']], s['start'], s['stop'], s['points'])
            else:
                self.points = s['tpoints']
                circuit.tran(s['tstop'], s['tpoints'], s['hmax'], s['uic'])
        except ps.SolveError as exc:
            self.fail(exc)
        self.traces = [array('f', bytes(4 * self.points)) for _ in probes]
        self.count = 0
        self.done = False
        self.op = None
        if self.kind == 'op':
            self.finish()
        elif self.points:
            self.count = 1
            for k in range(len(probes)):
                circuit.trace(k, self.traces[k])

    def fail(self, exc):
        """Raise the solver's problem with this circuit's own names."""
        node, element = self.circuit.error()
        text = str(exc)
        c, named_node, named_element = self.c, None, None
        if node >= 0:
            named_node = next((i for i, n in enumerate(self.net) if n == node), None)
            name = 'Ground' if node == 0 else node_label(c, named_node) if named_node is not None else 'a node'
            text = text.replace('node %d' % node, name)
        if 0 <= element < len(self.solver):
            named_element = self.solver[element]
            text = text.replace('element %d' % element, c['elements'][named_element]['name'])
        self.circuit.free()
        self.done = True
        raise CircuitError(text[0].upper() + text[1:], named_node, named_element)

    def advance(self, ms):
        """Work for about ms; True once finished."""
        if self.done:
            return True
        import picosolve as ps
        try:
            finished = self.circuit.run(ms)
        except ps.SolveError as exc:
            self.fail(exc)
        self.count = self.circuit.progress()[0]
        for k in range(len(self.traces)):
            self.circuit.trace(k, self.traces[k])
        if finished:
            self.finish()
        return finished

    def finish(self):
        """Keep what the results need and release the solver."""
        circuit, c = self.circuit, self.c
        self.info = circuit.info()
        if self.kind == 'op':
            self.op = {'nodes': [circuit.voltage(n) if n >= 0 else None for n in self.net],
                       'currents': {}, 'probes': []}
            for k, i in enumerate(self.solver):
                pins = len(c['elements'][i]['nodes'])
                self.op['currents'][i] = [circuit.current(k, t) for t in range(pins)]
            for p in c['probes']:
                self.op['probes'].append(self.probe_value(p))
        circuit.free()
        self.done = True

    def probe_value(self, p):
        """A probe's operating-point value from the stored results."""
        op = self.op
        if p['kind'] == 'V':
            return op['nodes'][p['a']] - (op['nodes'][p['b']] if p['b'] >= 0 else 0.0)
        e = self.c['elements'][p['element']]
        return op['currents'][p['element']][e['nodes'].index(p['node'])]

    @property
    def progress(self):
        return self.count, self.points

    def x(self, i):
        """The sweep value or time of sample i."""
        s = self.c['sim']
        if self.kind == 'dc':
            if self.points < 2:
                return s['start']
            return s['start'] + (s['stop'] - s['start']) * i / (self.points - 1)
        return s['tstop'] * i / (self.points - 1)

    def x_unit(self):
        if self.kind == 'dc':
            return 'V' if self.c['elements'][self.c['sim']['source']]['kind'] == 'V' else 'A'
        return 's'

    def stats(self, k):
        """Final, minimum and maximum (with their samples), mean, RMS and
        peak to peak of probe k over the samples so far."""
        trace, n = self.traces[k], self.count
        if n < 1:
            return None
        lo = hi = trace[0]
        at_lo = at_hi = 0
        total = squares = 0.0
        for i in range(n):
            v = trace[i]
            if v < lo:
                lo, at_lo = v, i
            if v > hi:
                hi, at_hi = v, i
            w = 0.5 if (i == 0 or i == n - 1) and n > 1 else 1.0
            total += w * v
            squares += w * v * v
        span = n - 1 if n > 1 else 1
        mean = total / span
        return {'final': trace[n - 1], 'min': lo, 'at_min': at_lo, 'max': hi, 'at_max': at_hi,
                'mean': mean, 'rms': max(squares / span, 0.0) ** 0.5, 'pp': hi - lo}


# ---------------------------------------------------------------- saved cases

def to_case(c):
    case = copy(c)
    case['tool'] = 'spice'
    return case


def from_case(case):
    """A circuit from a saved case, keeping what is valid."""
    c = new_circuit()
    for n in (case.get('nodes') or ())[:MAX_NODES]:
        if isinstance(n, list) and len(n) == 3 and all(isinstance(v, int) for v in n[:2]):
            c['nodes'].append([n[0], n[1], bool(n[2])])
    count = len(c['nodes'])
    for e in (case.get('elements') or ())[:MAX_ELEMENTS]:
        if not isinstance(e, dict) or e.get('kind') not in INFO:
            continue
        info = INFO[e['kind']]
        nodes = e.get('nodes')
        if not isinstance(nodes, list) or len(nodes) != len(info[3]) or \
                not all(isinstance(n, int) and 0 <= n < count for n in nodes):
            continue
        d = {'kind': e['kind'], 'name': str(e.get('name') or name_for(c, info[2]))[:8], 'nodes': list(nodes),
             'values': {}}
        values = e.get('values') if isinstance(e.get('values'), dict) else {}
        for f in info[4]:
            v = values.get(f[0])
            d['values'][f[0]] = float(v) if isinstance(v, (int, float)) else f[3]
        if e['kind'] in SOURCES:
            wave = e.get('wave') if e.get('wave') in WAVES else 'DC'
            set_wave(d, 'DC')
            if wave in WAVE_FIELDS:
                set_wave(d, wave)
                given = e.get('wave_values') if isinstance(e.get('wave_values'), dict) else {}
                for f in WAVE_FIELDS[wave]:
                    if isinstance(given.get(f[0]), (int, float)):
                        d['wave_values'][f[0]] = float(given[f[0]])
            elif wave == 'PWL':
                points = [p for p in (e.get('pwl') or ()) if isinstance(p, list) and len(p) == 2]
                try:
                    d['pwl'] = parse_pwl(', '.join('%r %r' % (float(t), float(v)) for t, v in points))
                    d['wave'] = 'PWL'
                except (ValueError, TypeError):
                    pass
        if e['kind'] in ('F', 'H'):
            d['ctrl'] = e.get('ctrl') if isinstance(e.get('ctrl'), int) else -1
        c['elements'].append(d)
    for p in (case.get('probes') or ())[:MAX_PROBES]:
        if not isinstance(p, dict):
            continue
        if p.get('kind') == 'V' and isinstance(p.get('a'), int) and 0 <= p['a'] < count and \
                isinstance(p.get('b'), int) and -1 <= p['b'] < count:
            c['probes'].append({'kind': 'V', 'a': p['a'], 'b': p['b']})
        elif p.get('kind') == 'I' and isinstance(p.get('node'), int) and 0 <= p['node'] < count and \
                isinstance(p.get('element'), int) and 0 <= p['element'] < len(c['elements']):
            c['probes'].append({'kind': 'I', 'node': p['node'], 'element': p['element']})
    sim = case.get('sim') if isinstance(case.get('sim'), dict) else {}
    for key, default in SIM_DEFAULTS.items():
        v = sim.get(key)
        if key == 'kind':
            c['sim'][key] = v if v in ANALYSES else default
        elif isinstance(default, bool):
            c['sim'][key] = bool(v) if v is not None else default
        elif isinstance(default, int) and isinstance(v, int):
            c['sim'][key] = v
        elif isinstance(default, float) and isinstance(v, (int, float)):
            c['sim'][key] = float(v)
    if isinstance(case.get('name'), str):
        c['name'] = case['name']
    return c


# ---------------------------------------------------------------- examples

class _Build:
    def __init__(self):
        self.c = new_circuit()

    def node(self, point):
        x, y = point[0], point[1]
        i = node_at(self.c, x, y)
        if i < 0:
            i = add_node(self.c, x, y, len(point) > 2)
        return i

    def add(self, kind, points, values=None, wave=None, ctrl=None):
        e = new_element(self.c, kind, [self.node(p) for p in points])
        el = self.c['elements'][e]
        el['values'].update(values or {})
        if wave:
            name, given = wave[0], wave[1]
            set_wave(el, name)
            if name == 'PWL':
                el['pwl'] = [list(p) for p in given]
            else:
                el['wave_values'].update(given)
        if ctrl is not None:
            el['ctrl'] = ctrl
        return e

    def probe(self, kind, point, element=-1, other=None):
        k = new_probe(self.c, kind, self.node(point), element)
        if other is not None:
            self.c['probes'][k]['b'] = self.node(other)


G = 'g'
EXAMPLES = ('Voltage divider', 'RC step response', 'RLC ringing', 'Half-wave rectifier', 'Inverting amplifier',
            'Transistor switch', 'CMOS inverter', 'Diode curve (DC sweep)')


def example(index):
    b = _Build()
    s = b.c['sim']
    if index == 0:
        b.add('V', ((0, 0), (0, 3, G)), {'dc': 10.0})
        b.add('R', ((0, 0), (4, 0)), {'R': 1e3})
        b.add('R', ((4, 0), (4, 3, G)), {'R': 3e3})
        b.probe('V', (4, 0))
        s['kind'] = 'op'
    elif index == 1:
        b.add('V', ((0, 0), (0, 3, G)), {'dc': 5.0}, ('PULSE', {'v1': 0.0, 'v2': 5.0, 'td': 0.5e-3, 'tr': 1e-6,
                                                               'tf': 1e-6, 'pw': 2e-3, 'per': 4e-3}))
        r = b.add('R', ((0, 0), (4, 0)), {'R': 1e3})
        cap = b.add('C', ((4, 0), (4, 3, G)), {'C': 1e-6})
        b.probe('V', (0, 0))
        b.probe('V', (4, 0))
        b.probe('I', (4, 0), cap)
        s.update(kind='tran', tstop=5e-3, tpoints=501)
    elif index == 2:
        b.add('V', ((0, 0), (0, 3, G)), {'dc': 1.0}, ('PULSE', {'v1': 0.0, 'v2': 1.0, 'td': 0.0, 'tr': 1e-7,
                                                               'tf': 1e-7, 'pw': 1.0, 'per': 0.0}))
        b.add('R', ((0, 0), (3, 0)), {'R': 10.0})
        ind = b.add('L', ((3, 0), (6, 0)), {'L': 1e-3})
        b.add('C', ((6, 0), (6, 3, G)), {'C': 1e-6})
        b.probe('V', (6, 0))
        b.probe('I', (3, 0), ind)
        s.update(kind='tran', tstop=2e-3, tpoints=801)
    elif index == 3:
        b.add('V', ((0, 0), (0, 3, G)), {'dc': 10.0}, ('SIN', {'vo': 0.0, 'va': 10.0, 'freq': 50.0}))
        d = b.add('D', ((0, 0), (3, 0)))
        b.add('C', ((3, 0), (3, 3, G)), {'C': 100e-6})
        b.add('W', ((3, 0), (6, 0)))
        b.add('R', ((6, 0), (6, 3, G)), {'R': 1e3})
        b.probe('V', (0, 0))
        b.probe('V', (3, 0))
        b.probe('I', (0, 0), d)
        s.update(kind='tran', tstop=60e-3, tpoints=601)
    elif index == 4:
        b.add('V', ((0, 2), (0, 5, G)), {'dc': 0.5}, ('SIN', {'vo': 0.0, 'va': 0.5, 'freq': 1e3}))
        b.add('R', ((0, 2), (3, 2)), {'R': 1e3})
        b.add('W', ((3, 2), (3, 0)))
        b.add('R', ((3, 0), (7, 0)), {'R': 4.7e3})
        b.add('W', ((7, 0), (7, 3)))
        b.add('OPAMP', ((3, 4, G), (3, 2), (7, 3)))
        b.add('R', ((7, 3), (7, 6, G)), {'R': 10e3})
        b.probe('V', (0, 2))
        b.probe('V', (7, 3))
        s.update(kind='tran', tstop=3e-3, tpoints=601)
    elif index == 5:
        b.add('V', ((7, 0), (7, 5, G)), {'dc': 5.0})
        b.add('R', ((7, 0), (4, 0)), {'R': 1e3})
        b.add('V', ((0, 2), (0, 5, G)), {'dc': 5.0}, ('PULSE', {'v1': 0.0, 'v2': 5.0, 'td': 0.2e-3, 'tr': 1e-6,
                                                               'tf': 1e-6, 'pw': 0.5e-3, 'per': 1e-3}))
        b.add('R', ((0, 2), (3, 2)), {'R': 10e3})
        b.add('NPN', ((4, 0), (3, 2), (4, 4, G)))
        b.probe('V', (0, 2))
        b.probe('V', (4, 0))
        s.update(kind='tran', tstop=2e-3, tpoints=401)
    elif index == 6:
        b.add('V', ((6, 0), (6, 6, G)), {'dc': 5.0})
        b.add('W', ((6, 0), (3, 0)))
        b.add('V', ((0, 3), (0, 6, G)), {'dc': 5.0}, ('PULSE', {'v1': 0.0, 'v2': 5.0, 'td': 1e-6, 'tr': 1e-7,
                                                               'tf': 1e-7, 'pw': 2e-6, 'per': 4e-6}))
        b.add('W', ((0, 3), (2, 3)))
        b.add('PMOS', ((3, 2), (2, 3), (3, 0)), {'KP': 1e-3, 'LAMBDA': 0.01})
        b.add('NMOS', ((3, 4), (2, 3), (3, 6, G)), {'KP': 1e-3, 'LAMBDA': 0.01})
        b.add('W', ((3, 2), (3, 4)))
        b.add('W', ((3, 4), (5, 4)))
        b.add('C', ((5, 4), (5, 6, G)), {'C': 10e-12})
        b.probe('V', (0, 3))
        b.probe('V', (5, 4))
        s.update(kind='tran', tstop=8e-6, tpoints=401)
    else:
        src = b.add('V', ((0, 0), (0, 3, G)), {'dc': 1.0})
        b.add('R', ((0, 0), (3, 0)), {'R': 100.0})
        d = b.add('D', ((3, 0), (3, 3, G)))
        b.probe('V', (3, 0))
        b.probe('I', (3, 0), d)
        s.update(kind='dc', source=src, start=0.0, stop=5.0, points=51)
    b.c['name'] = None
    return b.c
