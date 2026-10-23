"""PicoSpice editing: the items of each tab, their fields and every change.

A reference is ('node', i), ('element', i), ('probe', i) or ('sim', 0). A
field is (id, label, kind, unit, editable) with kind 'num', 'int', 'choice'
or 'text'. Choices are (label, value) options; values move between display
text and SI here. No drawing.
"""
from . import model as sm

TABS = ('Node', 'Element', 'Probe', 'Sim')
NODE, ELEMENT, PROBE, SIM = range(4)
# A value field must satisfy its rule: 'pos' > 0, 'nonneg' >= 0, 'nonzero'.
RULES = {'R': 'nonzero', 'C': 'nonneg', 'L': 'nonneg', 'Is': 'pos', 'N': 'pos', 'BF': 'pos', 'BR': 'pos',
         'VAF': 'nonneg', 'KP': 'pos', 'LAMBDA': 'nonneg', 'Ron': 'pos', 'Roff': 'pos', 'Vh': 'nonneg',
         'A': 'nonneg', 'td': 'nonneg', 'tr': 'nonneg', 'tf': 'nonneg', 'pw': 'nonneg', 'per': 'nonneg',
         'freq': 'nonneg', 'tstop': 'pos', 'hmax': 'nonneg'}
WHY = {'pos': 'Must be above zero', 'nonneg': 'Must not be negative', 'nonzero': 'Must not be zero'}


def refs(c, tab):
    if tab == NODE:
        return [('node', i) for i in range(len(c['nodes']))]
    if tab == ELEMENT:
        return [('element', i) for i in range(len(c['elements']))]
    if tab == PROBE:
        return [('probe', i) for i in range(len(c['probes']))]
    return [('sim', 0)]


def tab_of(ref):
    return ('node', 'element', 'probe', 'sim').index(ref[0])


def node_option(c, i):
    if i < 0:
        return 'Ground'
    x, y, grounded = c['nodes'][i]
    return '%s (%d,%d)%s' % (sm.node_label(c, i), x, y, ' gnd' if grounded else '')


def title(c, ref):
    kind, i = ref
    if kind == 'node':
        x, y, grounded = c['nodes'][i]
        n = len(sm.links(c, i))
        return '%s  (%d,%d)  %s' % (sm.node_label(c, i), x, y,
                                    'ground' if grounded else '%d pin%s' % (n, '' if n == 1 else 's'))
    if kind == 'element':
        e = c['elements'][i]
        pins = '-'.join(sm.node_label(c, n) for n in e['nodes'])
        summary = sm.element_summary(c, e)
        return '%s  %s%s' % (e['name'], summary + '  ' if summary else '', pins)
    if kind == 'probe':
        return 'P%d  %s' % (i + 1, sm.probe_label(c, c['probes'][i]))
    return 'Analysis'


def fields(c, ref):
    kind, i = ref
    if kind == 'node':
        return [('x', 'X', 'int', '', True), ('y', 'Y (down)', 'int', '', True), ('gnd', 'Ground', 'choice', '', True)]
    if kind == 'element':
        e = c['elements'][i]
        info = sm.INFO[e['kind']]
        out = [('pin%d' % t, ('End ' if e['kind'] == 'W' else 'Pin ') + name, 'choice', '', True)
               for t, name in enumerate(info[3])]
        out += [('v:' + f[0], f[1], 'num', f[2], True) for f in info[4]]
        if e['kind'] in sm.SOURCES:
            out.append(('wave', 'Waveform', 'choice', '', True))
            wave = e.get('wave', 'DC')
            if wave in sm.WAVE_FIELDS:
                out += [('w:' + f[0], f[1], 'num', sm.value_unit(e['kind'], f[2]), True) for f in sm.WAVE_FIELDS[wave]]
            elif wave == 'PWL':
                out.append(('pwl', 'Points: t v, t v', 'text', '', True))
        if e['kind'] in ('F', 'H'):
            out.append(('ctrl', 'Controlled by', 'choice', '', True))
        return out
    if kind == 'probe':
        p = c['probes'][i]
        out = [('ptype', 'Measures', 'choice', '', True)]
        if p['kind'] == 'V':
            out += [('a', 'Node +', 'choice', '', True), ('b', 'Node -', 'choice', '', True)]
        else:
            out += [('node', 'At node', 'choice', '', True), ('element', 'Into element', 'choice', '', True)]
        return out
    s = c['sim']
    out = [('kind', 'Analysis', 'choice', '', True)]
    if s['kind'] == 'dc':
        unit = sweep_unit(c)
        out += [('source', 'Sweep source', 'choice', '', True), ('start', 'Start', 'num', unit, True),
                ('stop', 'Stop', 'num', unit, True), ('points', 'Points', 'int', '', True)]
    elif s['kind'] == 'tran':
        out += [('tstop', 'Stop time', 'num', 's', True), ('tpoints', 'Points', 'int', '', True),
                ('hmax', 'Max step (0 auto)', 'num', 's', True), ('uic', 'Start from', 'choice', '', True)]
    return out


def sweep_unit(c):
    src = c['sim']['source']
    if 0 <= src < len(c['elements']):
        return 'V' if c['elements'][src]['kind'] == 'V' else 'A'
    return ''


# ---------------------------------------------------------------- choices

def options(c, ref, field):
    """(label, value) choices of a field."""
    kind, i = ref
    nodes = [(node_option(c, n), n) for n in range(len(c['nodes']))]
    if field.startswith('pin') or field in ('a', 'node'):
        return nodes
    if field == 'gnd':
        return [('No', False), ('Yes', True)]
    if field == 'wave':
        return [(w, w) for w in sm.WAVES]
    if field == 'ctrl':
        return [(e['name'], j) for j, e in enumerate(c['elements']) if e['kind'] in sm.BRANCH] or [('None yet', -1)]
    if field == 'ptype':
        return [('Voltage', 'V'), ('Current', 'I')]
    if field == 'b':
        return [('Ground', -1)] + nodes
    if field == 'element':
        p = c['probes'][i]
        return [(c['elements'][e]['name'], e) for e, t in sm.links(c, p['node'])
                if c['elements'][e]['kind'] != 'W'] or [('No element here', -1)]
    if field == 'kind':
        return [(name, k) for name, k in zip(sm.ANALYSIS_NAMES, sm.ANALYSES)]
    if field == 'source':
        return [(e['name'], j) for j, e in enumerate(c['elements']) if e['kind'] in sm.SOURCES] or [('No source', -1)]
    if field == 'uic':
        return [('Operating point', False), ('Zero, start values', True)]
    return []


def get(c, ref, field):
    kind, i = ref
    if kind == 'node':
        n = c['nodes'][i]
        return {'x': n[0], 'y': n[1], 'gnd': n[2]}[field]
    if kind == 'element':
        e = c['elements'][i]
        if field.startswith('pin'):
            return e['nodes'][int(field[3:])]
        if field.startswith('v:'):
            return e['values'][field[2:]]
        if field.startswith('w:'):
            return e['wave_values'][field[2:]]
        if field == 'pwl':
            return sm.pwl_text(e)
        return e.get(field, -1 if field == 'ctrl' else 'DC')
    if kind == 'probe':
        p = c['probes'][i]
        return p['kind'] if field == 'ptype' else p[field]
    return c['sim'][field]


def choice_index(c, ref, field):
    value = get(c, ref, field)
    for index, (label, v) in enumerate(options(c, ref, field)):
        if v == value:
            return index
    return 0


def text(c, ref, f):
    field, label, kind, unit, editable = f
    if kind == 'choice':
        opts = options(c, ref, field)
        return opts[choice_index(c, ref, field)][0] if opts else '--'
    value = get(c, ref, field)
    if kind == 'num':
        return sm.eng(value, unit)
    return str(value)


def set_choice(c, ref, field, index):
    kind, i = ref
    opts = options(c, ref, field)
    value = opts[index % len(opts)][1]
    if kind == 'node':
        c['nodes'][i][2] = value
    elif kind == 'element':
        e = c['elements'][i]
        if field.startswith('pin'):
            e['nodes'][int(field[3:])] = value
        elif field == 'wave':
            sm.set_wave(e, value)
        elif field == 'ctrl':
            e['ctrl'] = value
    elif kind == 'probe':
        p = c['probes'][i]
        if field == 'ptype' and value != p['kind']:
            node = p['a'] if p['kind'] == 'V' else p['node']
            p.clear()
            if value == 'V':
                p.update(kind='V', a=node, b=-1)
            else:
                p.update(kind='I', node=node, element=-1)
                p['element'] = options(c, ref, 'element')[0][1]
        elif field == 'node':
            p['node'] = value
            p['element'] = options(c, ref, 'element')[0][1]
        elif field != 'ptype':
            p[field] = value
    else:
        c['sim'][field] = value


def set_text(c, ref, field, text_value):
    """Numbers (with SPICE suffixes) and the PWL points."""
    kind, i = ref
    if field == 'pwl':
        c['elements'][i]['pwl'] = sm.parse_pwl(text_value)
        return
    f = next(f for f in fields(c, ref) if f[0] == field)
    if f[2] == 'int':
        from engtools.ui.forms import parse_number
        value = parse_number(text_value)
        if value != int(value):
            raise ValueError('Whole numbers only')
        set_int(c, ref, field, int(value))
        return
    value = sm.parse_value(text_value)
    if value != value or abs(value) > 1e30:
        raise ValueError('Enter a finite number')
    name = field.split(':')[-1]
    rule = RULES.get(name)
    if rule == 'pos' and not value > 0 or rule == 'nonneg' and value < 0 or rule == 'nonzero' and value == 0:
        raise ValueError(WHY[rule])
    if kind == 'element':
        e = c['elements'][i]
        (e['values'] if field.startswith('v:') else e['wave_values'])[name] = value
    else:
        c['sim'][field] = value


def set_int(c, ref, field, value):
    kind, i = ref
    if kind == 'node':
        if not -99 <= value <= 99:
            raise ValueError('Keep the grid within -99..99')
        x, y = c['nodes'][i][0], c['nodes'][i][1]
        x, y = (value, y) if field == 'x' else (x, value)
        other = sm.node_at(c, x, y)
        if other >= 0 and other != i:
            raise ValueError('%s is already there' % sm.node_label(c, other))
        c['nodes'][i][0], c['nodes'][i][1] = x, y
        return
    low = 2 if field == 'tpoints' else 1
    if not low <= value <= sm.POINT_LIMIT:
        raise ValueError('Points: %d to %d' % (low, sm.POINT_LIMIT))
    c['sim'][field] = value
