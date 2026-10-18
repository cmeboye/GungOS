"""Beam Lab model: members in the plane, picosolve calls and combined results.

A model is a plain dict that saves as JSON (schema 2):
  joints   [[X, Y], ...]                    member ends, m
  members  [{'a', 'b', 'section'}]          joint indices, section index
  sections [{'name', 'material', 'E', 'rho', 'shape', 'dims', 'I', 'A', 'W'}]
  supports [{'m', 'x', 'kind', 'kx', 'ky', 'kr', 'settle', 'case'}]
  hinges   [{'m', 'x'}]
  loads    [{'kind', 'm', 'x', ('x2'), 'P' | 'M' | 'w1', ('w2'), 'dir', 'case'}]
  cases, combos, selfweight (None or a load case)
Items sit on a member at x metres from its start joint. A straight beam is
one member (or several in a row, where its section changes).

Loads use the usual hand-calculation signs: forces and distributed loads
act in their direction ('down', 'normal' or 'right') when positive, applied
moments turn counterclockwise when positive and settlements move a support
down. Results: reactions up / right positive; along a member, sagging
moment, shear (V = dM/dx), tension and deflection to the member's left
(up for a member drawn left to right) are positive.

No display or storage code lives here.
"""
from math import pi, sqrt, atan2, cos, sin, radians, degrees
from array import array

TOOL = {'id': 'beams', 'title': 'Beam Lab', 'description': 'Beams and plane frames: supports, loads, sections and load cases.',
        'status': 'ready', 'planned_outputs': ('Support reactions', 'Shear, moment and normal force', 'Deflections')}

SCHEMA = 2
# name, E (Pa), density (kg/m3)
MATERIALS = (('Steel', 210e9, 7850.0), ('Concrete', 33e9, 2500.0), ('Timber', 11e9, 420.0),
             ('Aluminium', 70e9, 2700.0), ('Custom', None, None))
SHAPES = ('I-section', 'Rectangle', 'Hollow rect', 'T-section', 'Circle', 'Tube', 'Direct')
SHAPE_DIMS = {'I-section': ('h', 'b', 'tw', 'tf'), 'Rectangle': ('b', 'h'), 'Hollow rect': ('h', 'b', 't'),
              'T-section': ('h', 'b', 'tw', 'tf'), 'Circle': ('d',), 'Tube': ('d', 't'), 'Direct': ()}
DIM_LABELS = {'h': 'Depth h', 'b': 'Width b', 'tw': 'Web tw', 'tf': 'Flange tf', 'd': 'Diameter d', 't': 'Wall t'}
DEFAULT_DIMS = {'h': 0.3, 'b': 0.15, 'tw': 0.0071, 'tf': 0.0107, 'd': 0.2, 't': 0.01}
SUPPORTS = ('Pin', 'Roller', 'Roller x', 'Fixed', 'Guide', 'Spring')
SUPPORT_FLAGS = {'Pin': 'xy', 'Roller': 'y', 'Roller x': 'x', 'Fixed': 'xyr', 'Guide': 'xr', 'Spring': ''}
DIRECTIONS = ('down', 'normal', 'right')
DIRECTION_TITLES = ('Gravity (down)', 'Normal to member', 'Horizontal (right)')
MAX_CASES = 6
MAX_COMBOS = 6
MAX_ITEMS = 48
MAX_MEMBERS = 16
GRAVITY = 9.81
GRID = 1e6  # positions closer than a micrometre are the same point


class ModelError(ValueError):
    """A problem with the model, placed at a global point (X, Y) when it has one."""
    def __init__(self, message, where=None):
        super().__init__(message)
        self.where = where


def key(x):
    return int(round(x * GRID))


def pkey(X, Y):
    return (int(round(X * GRID)), int(round(Y * GRID)))


def snap(x):
    """A coordinate rounded to the micrometre grid: no cos(90) noise."""
    return round(x * GRID) / GRID


def m_text(x):
    return ('%.3f' % x).rstrip('0').rstrip('.') or '0'


# ---------------------------------------------------------------- sections

def properties(shape, dims):
    """(I m^4, A m^2, W m^3, depth m) of a shape from its dimensions (m).
    W is the smaller elastic section modulus."""
    for value in dims.values():
        if not value > 0:
            raise ModelError('Section sizes must be above zero')
    if shape == 'I-section':
        h, b, tw, tf = dims['h'], dims['b'], dims['tw'], dims['tf']
        if 2 * tf >= h or tw > b:
            raise ModelError('I-section: flanges must fit the depth, the web the width')
        I = (b * h ** 3 - (b - tw) * (h - 2 * tf) ** 3) / 12
        return I, 2 * b * tf + (h - 2 * tf) * tw, 2 * I / h, h
    if shape == 'Rectangle':
        b, h = dims['b'], dims['h']
        return b * h ** 3 / 12, b * h, b * h * h / 6, h
    if shape == 'Hollow rect':
        h, b, t = dims['h'], dims['b'], dims['t']
        if 2 * t >= h or 2 * t >= b:
            raise ModelError('Hollow section: walls must be under half the width and depth')
        I = (b * h ** 3 - (b - 2 * t) * (h - 2 * t) ** 3) / 12
        return I, b * h - (b - 2 * t) * (h - 2 * t), 2 * I / h, h
    if shape == 'T-section':
        h, b, tw, tf = dims['h'], dims['b'], dims['tw'], dims['tf']
        if tf >= h or tw > b:
            raise ModelError('T-section: the flange must fit the depth, the web the width')
        web = h - tf
        A = b * tf + tw * web
        top = (b * tf * tf / 2 + tw * web * (tf + web / 2)) / A  # centroid from the top
        I = b * tf ** 3 / 12 + b * tf * (top - tf / 2) ** 2 + tw * web ** 3 / 12 + tw * web * (tf + web / 2 - top) ** 2
        return I, A, I / max(top, h - top), h
    if shape == 'Circle':
        d = dims['d']
        return pi * d ** 4 / 64, pi * d * d / 4, pi * d ** 3 / 32, d
    if shape == 'Tube':
        d, t = dims['d'], dims['t']
        if 2 * t >= d:
            raise ModelError('Tube wall must be under half the diameter')
        I = pi * (d ** 4 - (d - 2 * t) ** 4) / 64
        return I, pi * (d * d - (d - 2 * t) ** 2) / 4, 2 * I / d, d
    raise ModelError('Unknown shape')


def centroid_from_top(shape, dims):
    if shape != 'T-section':
        return None
    h, b, tw, tf = dims['h'], dims['b'], dims['tw'], dims['tf']
    web = h - tf
    return (b * tf * tf / 2 + tw * web * (tf + web / 2)) / (b * tf + tw * web)


def section_values(section):
    """{'E', 'I', 'A', 'W', 'rho'} in SI units."""
    name, E, rho = MATERIALS[section['material']]
    if E is None:
        E, rho = section['E'], section['rho']
    if section['shape'] == 'Direct':
        I, A, W = section['I'], section['A'], section['W']
    else:
        I, A, W, depth = properties(section['shape'], section['dims'])
    if not (E > 0 and I > 0 and A > 0 and W > 0):
        raise ModelError('Section %s needs E, I, A and W above zero' % section['name'])
    return {'E': E, 'I': I, 'A': A, 'W': W, 'rho': rho or 0.0}


def new_section(name='S1', like=None):
    if like is not None:
        section = dict(like)
        section['dims'] = dict(like['dims'])
        section['name'] = name
        return section
    dims = dict((d, DEFAULT_DIMS[d]) for d in SHAPE_DIMS['I-section'])
    I, A, W, depth = properties('I-section', dims)
    return {'name': name, 'material': 0, 'E': 210e9, 'rho': 7850.0, 'shape': 'I-section',
            'dims': dims, 'I': I, 'A': A, 'W': W}


def set_shape(section, shape):
    """Change the shape; Direct keeps the current I, A and W."""
    if shape == section['shape']:
        return
    try:
        values = section_values(section)
        section['I'], section['A'], section['W'] = values['I'], values['A'], values['W']
    except ValueError:
        pass
    section['shape'] = shape
    section['dims'] = dict((d, section['dims'].get(d, DEFAULT_DIMS[d])) for d in SHAPE_DIMS[shape])


def section_name(model):
    used = set(s['name'] for s in model['sections'])
    for i in range(1, 100):
        if 'S%d' % i not in used:
            return 'S%d' % i
    return 'S'


# ---------------------------------------------------------------- geometry

def member_axis(model, m):
    """(X0, Y0, c, s, L) of member m."""
    member = model['members'][m]
    X0, Y0 = model['joints'][member['a']]
    X1, Y1 = model['joints'][member['b']]
    L = sqrt((X1 - X0) ** 2 + (Y1 - Y0) ** 2)
    if L <= 0:
        return X0, Y0, 1.0, 0.0, 0.0
    return X0, Y0, (X1 - X0) / L, (Y1 - Y0) / L, L


def member_length(model, m):
    return member_axis(model, m)[4]


def member_angle(model, m):
    X0, Y0, c, s, L = member_axis(model, m)
    return degrees(atan2(s, c))


def point(model, m, x):
    X0, Y0, c, s, L = member_axis(model, m)
    return X0 + c * x, Y0 + s * x


def set_member(model, m, length, angle):
    """Move member m's end joint to the given length and angle (degrees)."""
    member = model['members'][m]
    X0, Y0 = model['joints'][member['a']]
    a = radians(angle)
    model['joints'][member['b']] = [snap(X0 + length * cos(a)), snap(Y0 + length * sin(a))]


def lines(model):
    """Straight runs of members: lists of member indices, each member
    continuing the previous one in the same direction."""
    members = model['members']
    count = len(members)
    nxt, has_prev = {}, set()
    for i in range(count):
        ci, si = member_axis(model, i)[2:4]
        for j in range(count):
            if i != j and members[j]['a'] == members[i]['b'] and j not in has_prev and i not in nxt:
                cj, sj = member_axis(model, j)[2:4]
                if abs(ci - cj) < 1e-6 and abs(si - sj) < 1e-6:
                    nxt[i] = j
                    has_prev.add(j)
    out, seen = [], set()
    for i in range(count):
        if i in has_prev or i in seen:
            continue
        run = [i]
        seen.add(i)
        while run[-1] in nxt and nxt[run[-1]] not in seen:
            run.append(nxt[run[-1]])
            seen.add(run[-1])
        out.append(run)
    for i in range(count):  # closed loops of collinear members cannot happen, but be safe
        if i not in seen:
            out.append([i])
    return out


def line_offsets(model, line):
    """Distance along the line to the start of each of its members."""
    offsets, total = [], 0.0
    for m in line:
        offsets.append(total)
        total += member_length(model, m)
    return offsets, total


def is_straight_beam(model):
    """One horizontal line drawn left to right: the classic beam view."""
    runs = lines(model)
    if len(runs) != 1:
        return False
    X0, Y0, c, s, L = member_axis(model, runs[0][0])
    return abs(s) < 1e-9 and c > 0


def bounds(model):
    xs = [j[0] for j in model['joints']]
    ys = [j[1] for j in model['joints']]
    return min(xs), min(ys), max(xs), max(ys)


# ---------------------------------------------------------------- templates

TEMPLATES = (
    ('Simply supported', 'Pin and roller, uniform load'),
    ('Cantilever', 'Fixed end, point load at the tip'),
    ('Propped cantilever', 'Fixed end and roller, uniform load'),
    ('Fixed-fixed', 'Both ends fixed, uniform load'),
    ('Two spans', 'Continuous over three supports'),
    ('Three spans', 'Continuous over four supports'),
    ('Overhang', 'Two supports and a free end'),
    ('Portal frame', 'Fixed feet, gravity and wind'),
    ('Gable frame', 'Pinned feet, pitched rafters'),
    ('Blank', 'Pin and roller, no loads'),
)


def support(m, x, kind='Pin'):
    return {'m': m, 'x': x, 'kind': kind, 'kx': 0.0, 'ky': 1e7, 'kr': 0.0, 'settle': 0.0, 'case': 0}


def point_load(m, x, P=10e3, case=0, direction='down'):
    return {'kind': 'point', 'm': m, 'x': x, 'P': P, 'dir': direction, 'case': case}


def moment_load(m, x, M=10e3, case=0):
    return {'kind': 'moment', 'm': m, 'x': x, 'M': M, 'case': case}


def dist_load(m, x, x2, w1=5e3, w2=None, case=0, direction='down'):
    return {'kind': 'dist', 'm': m, 'x': x, 'x2': x2, 'w1': w1, 'w2': w1 if w2 is None else w2,
            'dir': direction, 'case': case}


def empty_model(joints, members):
    return {'tool': 'beams', 'schema': SCHEMA, 'name': '', 'joints': [list(j) for j in joints],
            'members': [{'a': a, 'b': b, 'section': 0} for a, b in members], 'sections': [new_section()],
            'supports': [], 'hinges': [], 'loads': [], 'cases': ['Dead'],
            'combos': [{'name': 'All x1.0', 'factors': [1.0]}], 'selfweight': None}


def template(index):
    """A ready-to-solve model for TEMPLATES[index]."""
    name = TEMPLATES[index][0]
    if name == 'Portal frame':
        m = empty_model(((0, 0), (0, 4.0), (6.0, 4.0), (6.0, 0)), ((0, 1), (1, 2), (3, 2)))
        m['supports'] = [support(0, 0.0, 'Fixed'), support(2, 0.0, 'Fixed')]
        m['loads'] = [dist_load(1, 0.0, 6.0, 10e3), point_load(0, 4.0, 5e3, direction='right')]
        return m
    if name == 'Gable frame':
        m = empty_model(((0, 0), (0, 4.0), (5.0, 5.5), (10.0, 4.0), (10.0, 0)), ((0, 1), (1, 2), (2, 3), (4, 3)))
        m['supports'] = [support(0, 0.0, 'Pin'), support(3, 0.0, 'Pin')]
        rafter = member_length(m, 1)
        m['loads'] = [dist_load(1, 0.0, rafter, 4e3), dist_load(2, 0.0, rafter, 4e3)]
        return m
    L = {'Cantilever': 3.0, 'Two spans': 10.0, 'Three spans': 15.0, 'Overhang': 8.0}.get(name, 6.0)
    m = empty_model(((0, 0), (L, 0)), ((0, 1),))
    supports = {
        'Simply supported': ((0, 'Pin'), (L, 'Roller')),
        'Cantilever': ((0, 'Fixed'),),
        'Propped cantilever': ((0, 'Fixed'), (L, 'Roller')),
        'Fixed-fixed': ((0, 'Fixed'), (L, 'Fixed')),
        'Two spans': ((0, 'Pin'), (5.0, 'Roller'), (L, 'Roller')),
        'Three spans': ((0, 'Pin'), (5.0, 'Roller'), (10.0, 'Roller'), (L, 'Roller')),
        'Overhang': ((0, 'Pin'), (6.0, 'Roller')),
        'Blank': ((0, 'Pin'), (L, 'Roller')),
    }[name]
    m['supports'] = [support(0, x, kind) for x, kind in supports]
    if name == 'Cantilever':
        m['loads'] = [point_load(0, L)]
    elif name != 'Blank':
        m['loads'] = [dist_load(0, 0.0, L)]
    return m


def upgrade(model):
    """Bring a saved model to the current schema (schema 1: one straight
    beam with section changes at x positions)."""
    if model.get('schema') == SCHEMA:
        return model
    if 'members' in model:
        raise ModelError('Saved by a newer Beam Lab')
    L = model['length']
    old = sorted(model['sections'], key=lambda s: s['x'])
    cuts = [s['x'] for s in old] + [L]
    joints = [[x, 0.0] for x in cuts]
    out = empty_model(joints, [(i, i + 1) for i in range(len(old))])
    for i, s in enumerate(old):
        section = new_section('S%d' % (i + 1))
        section['material'] = s['material']
        section['E'] = s['E']
        section['shape'] = 'Direct' if s['shape'] == 'Direct I' else s['shape']
        section['dims'] = dict(s['dims'])
        if section['shape'] == 'Direct':
            section['I'] = s['I']  # A and W keep the default I-section values
        out['sections'][i:i + 1] = [section]
        out['members'][i]['section'] = i
    del out['sections'][len(old):]

    def place(x, at_end=False):
        for i in range(len(old)):
            if cuts[i] - 1e-9 <= x <= cuts[i + 1] + 1e-9 and (at_end or x < cuts[i + 1] - 1e-9 or i == len(old) - 1):
                return i, min(max(x - cuts[i], 0.0), cuts[i + 1] - cuts[i])
        return len(old) - 1, x - cuts[-2]
    for s in model['supports']:
        m, x = place(s['x'])
        item = support(m, x, s['kind'] if s['kind'] in SUPPORTS else 'Pin')
        for k in ('ky', 'kr', 'settle', 'case'):
            item[k] = s[k]
        out['supports'].append(item)
    for h in model['hinges']:
        m, x = place(h['x'])
        out['hinges'].append({'m': m, 'x': x})
    for load in model['loads']:
        if load['kind'] != 'dist':
            m, x = place(load['x'])
            item = point_load(m, x, load['P'], load['case']) if load['kind'] == 'point' else moment_load(m, x, load['M'], load['case'])
            out['loads'].append(item)
            continue
        x1, x2, w1, w2 = load['x'], load['x2'], load['w1'], load['w2']
        for i in range(len(old)):
            a, b = max(x1, cuts[i]), min(x2, cuts[i + 1])
            if b > a + 1e-9:
                wa = w1 + (w2 - w1) * (a - x1) / (x2 - x1)
                wb = w1 + (w2 - w1) * (b - x1) / (x2 - x1)
                out['loads'].append(dist_load(i, a - cuts[i], b - cuts[i], wa, wb, load['case']))
    out['name'] = model.get('name', '')
    out['cases'] = list(model['cases'])
    out['combos'] = [{'name': c['name'], 'factors': list(c['factors'])} for c in model['combos']]
    return out


# ---------------------------------------------------------------- checks

def item_count(model):
    return len(model['supports']) + len(model['hinges']) + len(model['loads']) + len(model['members'])


def check(model):
    """Raise ModelError for inputs the solver cannot use."""
    members, joints = model['members'], model['joints']
    if not members:
        raise ModelError('Add a member')
    for X, Y in joints:
        if not (abs(X) <= 1000 and abs(Y) <= 1000):
            raise ModelError('Joints must lie within 1000 m of the origin')
    for i, member in enumerate(members):
        if member['a'] == member['b'] or member_length(model, i) < 1e-6:
            raise ModelError('Member %d has no length' % (i + 1), point(model, i, 0.0))
        if not 0 <= member['section'] < len(model['sections']):
            raise ModelError('Member %d uses a missing section' % (i + 1))

    def on_member(item, field='x'):
        m = item['m']
        if not 0 <= m < len(members):
            raise ModelError('An item lies on a missing member')
        x = item[field]
        if not -1e-9 <= x <= member_length(model, m) + 1e-9:
            raise ModelError('Item lies off member %d' % (m + 1), point(model, m, min(max(x, 0.0), member_length(model, m))))
        return point(model, m, x)
    if not model['supports']:
        raise ModelError('Add a support (S)')
    seen = set()
    for s in model['supports']:
        where = on_member(s)
        if pkey(*where) in seen:
            raise ModelError('Two supports at the same point', where)
        seen.add(pkey(*where))
        if s['kind'] not in SUPPORTS:
            raise ModelError('Unknown support type', where)
        if s['kind'] == 'Spring':
            if s['kx'] < 0 or s['ky'] < 0 or s['kr'] < 0:
                raise ModelError('Spring stiffness cannot be negative', where)
            if not (s['kx'] > 0 or s['ky'] > 0 or s['kr'] > 0):
                raise ModelError('Spring needs a stiffness above zero', where)
        if s['settle'] and 'y' in SUPPORT_FLAGS[s['kind']] and s['case'] >= len(model['cases']):
            raise ModelError('Settlement uses a missing load case', where)
    hinges = set()
    for h in model['hinges']:
        where = on_member(h)
        if (h['m'], key(h['x'])) in hinges:
            raise ModelError('Two hinges at the same point', where)
        hinges.add((h['m'], key(h['x'])))
    for load in model['loads']:
        where = on_member(load)
        if load['case'] >= len(model['cases']):
            raise ModelError('Load uses a missing load case', where)
        if load['kind'] == 'dist':
            on_member(load, 'x2')
            if not load['x'] < load['x2'] - 1e-9:
                raise ModelError('Distributed load needs start < end', where)
        if load.get('dir', 'down') not in DIRECTIONS:
            raise ModelError('Unknown load direction', where)
    for s in model['sections']:
        section_values(s)
    if not model['cases']:
        raise ModelError('Add a load case')
    if model.get('selfweight') is not None and not 0 <= model['selfweight'] < len(model['cases']):
        raise ModelError('Self-weight uses a missing load case')
    for combo in model['combos']:
        if len(combo['factors']) != len(model['cases']):
            raise ModelError('Combination ' + combo['name'] + ' does not match the load cases')


def direction_vector(model, m, name):
    """Unit vector (global) of a load direction on member m."""
    if name == 'down':
        return 0.0, -1.0
    if name == 'right':
        return 1.0, 0.0
    X0, Y0, c, s, L = member_axis(model, m)
    return s, -c  # toward the member's right: down for a member drawn left to right


# ---------------------------------------------------------------- solving

def _located(message, nodes, elements, load_where):
    """Turn the solver's node/element/load numbers into a place."""
    def number(word):
        at = message.find(word + ' ')
        if at < 0:
            return None
        digits = ''
        for c in message[at + len(word) + 1:]:
            if not c.isdigit():
                break
            digits += c
        return int(digits) if digits else None
    node = number('node')
    if node is not None and node < len(nodes):
        X, Y = nodes[node]
        where = 'x = %s m' % m_text(X) if abs(Y) < 1e-9 else '(%s, %s) m' % (m_text(X), m_text(Y))
        if 'can move' in message:
            what = 'rotate' if 'rotation' in message else 'slide sideways' if 'horizontal' in message else 'move'
            hint = 'make a support a Pin or Fixed' if what == 'slide sideways' else 'add a support or remove a hinge'
            return ModelError('Structure can %s freely at %s: %s' % (what, where, hint), (X, Y))
        return ModelError(message, (X, Y))
    element = number('element')
    if element is not None and element < len(elements):
        a, b = elements[element][:2]
        return ModelError(message, ((nodes[a][0] + nodes[b][0]) / 2, (nodes[a][1] + nodes[b][1]) / 2))
    load = number('load')
    if load is not None and load < len(load_where):
        return ModelError(message, load_where[load])
    if 'can move' in message:
        return ModelError('Structure can move freely: add a support', None)
    return ModelError(message, None)


class Solution:
    """A solved model and its results for any load case or combination,
    read along lines (straight runs of members)."""

    def __init__(self, model):
        import picosolve as ps
        self.model = model
        check(model)
        members = model['members']
        # Positions along each member where something starts or acts.
        stations = [dict() for _ in members]
        for m in range(len(members)):
            L = member_length(model, m)
            stations[m][0] = 0.0
            stations[m][key(L)] = L
        for group in ('supports', 'hinges', 'loads'):
            for item in model[group]:
                stations[item['m']][key(item['x'])] = item['x']
                if item.get('kind') == 'dist':
                    stations[item['m']][key(item['x2'])] = item['x2']
        nodes, node_at = [], {}

        def node(X, Y):
            k = pkey(X, Y)
            if k not in node_at:
                node_at[k] = len(nodes)
                nodes.append((X, Y))
            return node_at[k]
        hinges = set((h['m'], key(h['x'])) for h in model['hinges'])
        elements = []  # (node a, node b, member, x start, x end, releases)
        self.member_elements = []
        for m in range(len(members)):
            xs = [stations[m][k] for k in sorted(stations[m])]
            first = len(elements)
            for i in range(len(xs) - 1):
                a, b = node(*point(model, m, xs[i])), node(*point(model, m, xs[i + 1]))
                release = 0
                if (m, key(xs[i + 1])) in hinges:
                    release |= ps.RELEASE_END
                if i == 0 and (m, 0) in hinges:
                    release |= ps.RELEASE_START
                elements.append((a, b, m, xs[i], xs[i + 1], release))
            self.member_elements.append((first, len(elements)))
        self.nodes, self.elements = nodes, elements
        cases = len(model['cases'])
        loads, load_where = [], []

        def element_range(m, x1, x2):
            first, end = self.member_elements[m]
            return [e for e in range(first, end) if elements[e][3] >= x1 - 1e-9 and elements[e][4] <= x2 + 1e-9]
        self.selfweight = []
        if model.get('selfweight') is not None:
            for m, member in enumerate(members):
                values = section_values(model['sections'][member['section']])
                w = values['rho'] * values['A'] * GRAVITY
                if w > 0:
                    self.selfweight.append(dist_load(m, 0.0, member_length(model, m), w, case=model['selfweight']))
        dist = [load for load in model['loads'] if load['kind'] == 'dist'] + self.selfweight
        for load in model['loads']:
            c, m = load['case'], load['m']
            where = point(model, m, load['x'])
            if load['kind'] == 'point':
                dx, dy = direction_vector(model, m, load['dir'])
                n = node(*where)
                loads.append(('node_load', (c, n, ps.UX, load['P'] * dx)))
                loads.append(('node_load', (c, n, ps.UY, load['P'] * dy)))
                load_where += [where, where]
            elif load['kind'] == 'moment':
                loads.append(('node_load', (c, node(*where), ps.RZ, load['M'])))
                load_where.append(where)
        for load in dist:
            c, m = load['case'], load['m']
            X0, Y0, cm, sm, L = member_axis(model, m)
            dx, dy = direction_vector(model, m, load['dir'])
            across, along = dx * -sm + dy * cm, dx * cm + dy * sm  # onto local y and local x
            x1, x2, w1, w2 = load['x'], load['x2'], load['w1'], load['w2']
            for e in element_range(m, x1, x2):
                a, b = elements[e][3], elements[e][4]
                wa = w1 + (w2 - w1) * (a - x1) / (x2 - x1)
                wb = w1 + (w2 - w1) * (b - x1) / (x2 - x1)
                if abs(across) > 1e-12:
                    loads.append(('line', (c, e, 0.0, b - a, wa * across, wb * across)))
                    load_where.append(point(model, m, a))
                if abs(along) > 1e-12:
                    loads.append(('axial_line', (c, e, 0.0, b - a, wa * along, wb * along)))
                    load_where.append(point(model, m, a))
        flags = {'x': ps.UX, 'y': ps.UY, 'r': ps.RZ}
        self.support_nodes = []
        for s in model['supports']:
            n = node(*point(model, s['m'], s['x']))
            self.support_nodes.append(n)
            if s['settle'] and 'y' in SUPPORT_FLAGS[s['kind']]:
                loads.append(('settle', (s['case'], n, ps.UY, -s['settle'])))
                load_where.append(nodes[n])
        f = ps.Frame(nodes=len(nodes), elements=len(elements), sections=len(model['sections']),
                     loads=len(loads), cases=cases)
        self.values = []
        for i, section in enumerate(model['sections']):
            values = section_values(section)
            self.values.append(values)
            f.section(i, values['E'], values['I'], values['A'])
        for i, (X, Y) in enumerate(nodes):
            f.node(i, X, Y)
        for e, (a, b, m, x1, x2, release) in enumerate(elements):
            f.element(e, a, b, members[m]['section'], release)
        for s, n in zip(model['supports'], self.support_nodes):
            if s['kind'] == 'Spring':
                for flag, k in ((ps.UX, s['kx']), (ps.UY, s['ky']), (ps.RZ, s['kr'])):
                    if k > 0:
                        f.spring(n, flag, k)
            else:
                mask = 0
                for c in SUPPORT_FLAGS[s['kind']]:
                    mask |= flags[c]
                f.support(n, mask)
        for method, args in loads:
            getattr(f, method)(*args)
        try:
            f.solve()
        except ps.SolveError as exc:
            f.free()
            raise _located(str(exc), nodes, elements, load_where)
        self.frame = f
        self.info = f.info()
        self.lines = lines(model)
        self._samples = {}

    def free(self):
        if self.frame is not None:
            self.frame.free()
            self.frame = None
        self._samples = {}

    # Views: each load case, then each combination.
    def view_names(self):
        model = self.model
        return list(model['cases']) + ['Combo ' + c['name'] for c in model['combos']]

    def factors(self, view):
        cases = len(self.model['cases'])
        if view < cases:
            return ((view, 1.0),)
        combo = self.model['combos'][view - cases]['factors']
        return tuple((c, f) for c, f in enumerate(combo) if f)

    def element(self, m, x, side=1):
        """The element of member m holding x; at a node, the one after it (side=1) or before."""
        first, end = self.member_elements[m]
        for e in range(first, end):
            a, b = self.elements[e][3], self.elements[e][4]
            if (a <= x < b if side > 0 else a < x <= b):
                return e
        return first if x <= self.elements[first][3] else end - 1

    def at(self, m, x, view, side=1):
        """(shear, moment, slope, deflection, normal, axial) at x on member m, local axes."""
        L = member_length(self.model, m)
        x = min(max(x, 0.0), L)
        e = self.element(m, x, side)
        local = min(max(x - self.elements[e][3], 0.0), self.elements[e][4] - self.elements[e][3])
        total = [0.0] * 6
        for c, f in self.factors(view):
            values = self.frame.at(e, local, c)
            for q in range(6):
                total[q] += f * values[q]
        return total

    def locate(self, line, s):
        """(member, x) at distance s along a line."""
        run = self.lines[line]
        offsets, total = line_offsets(self.model, run)
        s = min(max(s, 0.0), total)
        for m, o in zip(run, offsets):
            if s <= o + member_length(self.model, m) + 1e-9:
                return m, s - o
        return run[-1], member_length(self.model, run[-1])

    def at_line(self, line, s, view, side=1):
        run = self.lines[line]
        offsets, total = line_offsets(self.model, run)
        for i, (m, o) in enumerate(zip(run, offsets)):
            L = member_length(self.model, m)
            last = i == len(run) - 1
            if (s < o + L - 1e-9) or last or (side < 0 and s <= o + L + 1e-9):
                return self.at(m, s - o, view, side)

    def displacement(self, X, Y, view):
        """Global (ux, uy) of the node at (X, Y), or None if there is none."""
        import picosolve as ps
        for n, (nx, ny) in enumerate(self.nodes):
            if pkey(nx, ny) == pkey(X, Y):
                ux = uy = 0.0
                for c, f in self.factors(view):
                    ux += f * self.frame.displacement(n, ps.UX, c)
                    uy += f * self.frame.displacement(n, ps.UY, c)
                return ux, uy
        return None

    def reactions(self, view):
        """[(support, Fx N right, Fy N up, Mz N*m ccw)] for each support."""
        rows = []
        for s, n in zip(self.model['supports'], self.support_nodes):
            fx = fy = mz = 0.0
            for c, f in self.factors(view):
                r = self.frame.reaction(n, c)
                fx += f * r[0]
                fy += f * r[1]
                mz += f * r[2]
            rows.append((s, fx, fy, mz))
        return rows

    def applied(self, view):
        """Total applied force (Fx, Fy) in a view, global, for the equilibrium check."""
        fx = fy = 0.0
        weights = dict(self.factors(view))
        for load in self.model['loads'] + self.selfweight:
            f = weights.get(load['case'], 0.0)
            if not f or load['kind'] == 'moment':
                continue
            dx, dy = direction_vector(self.model, load['m'], load['dir'])
            if load['kind'] == 'point':
                size = load['P']
            else:
                size = (load['w1'] + load['w2']) / 2 * (load['x2'] - load['x'])
            fx += f * size * dx
            fy += f * size * dy
        return fx, fy

    def samples(self, line, view, target=240):
        """(s, V, M, slope, w, N, u, starts): array('f') samples along a line
        (u is the axial displacement).
        Each element is sampled end to end, so jumps show at shared nodes;
        `starts` lists the first sample of each element."""
        cache_key = (line, view)
        if cache_key in self._samples:
            return self._samples[cache_key]
        run = self.lines[line]
        offsets, total = line_offsets(self.model, run)
        spans = []
        for m, o in zip(run, offsets):
            first, end = self.member_elements[m]
            for e in range(first, end):
                spans.append((e, o + self.elements[e][3], o + self.elements[e][4]))
        counts = [max(2, int(target * (b - a) / total) + 1) for e, a, b in spans]
        n_total = sum(counts)
        S = array('f', bytes(4 * n_total))
        out = [array('f', bytes(4 * n_total)) for _ in range(6)]
        largest = max(counts)
        tmp = [array('f', bytes(4 * largest)) for _ in range(6)]
        factors = self.factors(view)
        start, starts = 0, []
        for (e, a, b), n in zip(spans, counts):
            starts.append(start)
            for i in range(n):
                S[start + i] = a + (b - a) * i / (n - 1)
            for c, f in factors:
                self.frame.diagram(e, n, tmp[0], tmp[1], tmp[2], tmp[3], c)
                self.frame.axial_diagram(e, n, tmp[4], tmp[5], c)
                for q in range(6):
                    target_q, part = out[q], tmp[q]
                    for i in range(n):
                        target_q[start + i] += f * part[i]
            start += n
        result = (S, out[0], out[1], out[2], out[3], out[4], out[5], starts)
        if len(self._samples) > 6:
            self._samples = {}
        self._samples[cache_key] = result
        return result

    def extremes(self, line, view):
        """{quantity: (max, s_max, min, s_min)} for V, M, T (slope), W and N
        along a line, interior peaks refined by golden-section search."""
        S, V, M, T, W, N, U, starts = self.samples(line, view)
        ends = set(starts) | set(s - 1 for s in starts[1:]) | {len(S) - 1}
        result = {}
        for name, q, data in (('V', 0, V), ('M', 1, M), ('T', 2, T), ('W', 3, W), ('N', 4, N)):
            hi = lo = 0
            for i in range(len(data)):
                if data[i] > data[hi]:
                    hi = i
                if data[i] < data[lo]:
                    lo = i
            peak = []
            for i, sign in ((hi, 1), (lo, -1)):
                s, value = S[i], data[i]
                if i not in ends:
                    s, value = self._refine(line, view, q, S[i - 1], S[i + 1], sign)
                    if sign * value < sign * data[i]:
                        s, value = S[i], data[i]
                peak.append((value, s))
            result[name] = (peak[0][0], peak[0][1], peak[1][0], peak[1][1])
        return result

    def _refine(self, line, view, q, a, b, sign):
        g = 0.6180339887
        c, d = b - g * (b - a), a + g * (b - a)
        fc, fd = sign * self.at_line(line, c, view)[q], sign * self.at_line(line, d, view)[q]
        for _ in range(24):
            if fc > fd:
                b, d, fd = d, c, fc
                c = b - g * (b - a)
                fc = sign * self.at_line(line, c, view)[q]
            else:
                a, c, fc = c, d, fd
                d = a + g * (b - a)
                fd = sign * self.at_line(line, d, view)[q]
        s = (a + b) / 2
        return s, self.at_line(line, s, view)[q]

    def stress(self, line, view):
        """(largest |N/A| + |M/W| in Pa, s, member) along a line."""
        S, V, M, T, W, N, U, starts = self.samples(line, view)
        best = (0.0, 0.0, self.lines[line][0])
        for i in range(len(S)):
            m, x = self.locate(line, S[i])
            values = self.values[self.model['members'][m]['section']]
            sigma = abs(N[i]) / values['A'] + abs(M[i]) / values['W']
            if sigma > best[0]:
                best = (sigma, S[i], m)
        return best

    def deflection_ratio(self, view):
        """(span/|w| worst ratio, span m) between supports of a straight
        beam; cantilevered ends count their own length. None otherwise."""
        if not is_straight_beam(self.model):
            return None
        S, V, M, T, W, N, U, starts = self.samples(0, view)
        offsets, total = line_offsets(self.model, self.lines[0])
        positions = dict(zip(self.lines[0], offsets))
        cuts = sorted(set([0.0, total] + [positions[s['m']] + s['x'] for s in self.model['supports']]))
        worst = None
        for a, b in zip(cuts, cuts[1:]):
            peak = 0.0
            for i in range(len(S)):
                if a <= S[i] <= b:
                    peak = max(peak, abs(W[i]))
            if peak > 1e-12 and b > a:
                ratio = (b - a) / peak
                if worst is None or ratio < worst[0]:
                    worst = (ratio, b - a)
        return worst


def solve(parameters, job=None):
    """Calculate model results independently of the display."""
    return Solution(parameters)


def validate(parameters):
    """Check model inputs and assumptions."""
    return check(parameters)
