"""Concentric discs and cylinders: rotation, pressures and shrink fits.

A model is a stack of N bodies between radii r0 < r1 < ... < rN (r0 = 0
for a solid centre), stored in SI units:

  radii    [r0, ..., rN]                                   m
  bodies   [{'t', 'material', 'E', 'nu', 'rho', 'alpha', 'Sy'}]
  speed, Pi, Po                {'v': value, 'find': bool}   rad/s, Pa, Pa
  fits     [{'delta': {'v', 'find'}, 'pc': {'v', 'find'}, 'mu'}]
           one per interface; delta is the diametral interference, m
  plane    'stress' (thin discs) or 'strain' (long cylinders, ends held)

Each body follows Lame's solution with the rotation's body force:
  sr = A + B/r^2 - (3+v)/8 rho w^2 r^2
  st = A - B/r^2 - (1+3v)/8 rho w^2 r^2
  u  = r/E ((1-v) A - (1+v) B/r^2 - (1-v^2)/8 rho w^2 r^2)
(plane strain uses E/(1-v^2) and v/(1-v), with sz = v (sr + st)).

The pressures, interferences, contact pressures and w^2 all enter
linearly, so any N-1 of them can be found from the rest: the equations are
the inner and outer boundary conditions, and at each interface equal
radial stress (minus the contact pressure) on both sides and the
interference as the difference of the radial displacements. The solver
works in mm, MPa and w in krad/s so single precision stays well scaled.
"""
from math import pi, sqrt

SCHEMA = 1
MAX_BODIES = 6
# name, E Pa, Poisson, density kg/m3, expansion 1/K, yield Pa
MATERIALS = (('Steel', 210e9, 0.30, 7850.0, 12e-6, 250e6),
             ('Alloy steel', 205e9, 0.29, 7850.0, 12e-6, 650e6),
             ('Cast iron', 110e9, 0.26, 7200.0, 10.8e-6, 200e6),
             ('Aluminium', 70e9, 0.33, 2700.0, 23e-6, 240e6),
             ('Titanium', 114e9, 0.34, 4430.0, 8.6e-6, 880e6),
             ('Brass', 100e9, 0.34, 8500.0, 19e-6, 200e6),
             ('Custom', None, None, None, None, None))
PROPS = ('E', 'nu', 'rho', 'alpha', 'Sy')
TEMPLATES = (
    ('Shrink fit', 'Solid shaft in a hub, interference given'),
    ('Rotating disc', 'Solid disc spinning at 3000 rpm'),
    ('Flywheel ring', 'Hollow disc spinning at 6000 rpm'),
    ('Thick cylinder', 'Bore pressure 100 MPa'),
    ('Compound cylinder', 'Two shrunk rings under bore pressure'),
    ('Required fit', 'Find the interference for 40 MPa contact'),
)
E_REF = 1e5  # scales the displacement equations to MPa-sized terms


class ModelError(Exception):
    pass


def body(t=0.02, material=0):
    b = {'t': t, 'material': material}
    set_material(b, material)
    return b


def set_material(b, index):
    b['material'] = index
    values = MATERIALS[index][1:]
    if values[0] is not None:
        for key, value in zip(PROPS, values):
            b[key] = value


def var(value=0.0, find=False):
    return {'v': value, 'find': find}


def fit(delta=0.0, pc_find=True):
    return {'delta': var(delta, not pc_find), 'pc': var(0.0, pc_find), 'mu': 0.15}


def new_model(radii, bodies):
    return {'tool': 'discs', 'schema': SCHEMA, 'name': '', 'radii': list(radii), 'bodies': bodies,
            'speed': var(), 'Pi': var(), 'Po': var(),
            'fits': [fit() for _ in range(len(bodies) - 1)], 'plane': 'stress', 'rpm': True}


def rpm(value):
    return value * pi / 30


def template(index):
    name = TEMPLATES[index][0]
    if name == 'Shrink fit':
        m = new_model([0.0, 0.025, 0.06], [body(0.04), body(0.04)])
        m['fits'][0]['delta']['v'] = 50e-6
    elif name == 'Rotating disc':
        m = new_model([0.0, 0.2], [body(0.02)])
        m['speed']['v'] = rpm(3000)
    elif name == 'Flywheel ring':
        m = new_model([0.1, 0.25], [body(0.05)])
        m['speed']['v'] = rpm(6000)
    elif name == 'Thick cylinder':
        m = new_model([0.05, 0.1], [body(0.3)])
        m['Pi']['v'] = 100e6
        m['plane'] = 'strain'
    elif name == 'Compound cylinder':
        m = new_model([0.05, 0.075, 0.1], [body(0.3, 1), body(0.3, 1)])
        m['fits'][0]['delta']['v'] = 60e-6
        m['Pi']['v'] = 150e6
        m['plane'] = 'strain'
    else:
        m = new_model([0.0, 0.025, 0.06], [body(0.04), body(0.04)])
        f = m['fits'][0]
        f['pc'], f['delta'] = var(40e6), var(0.0, True)
        m['speed']['v'] = rpm(1500)
    m['name'] = ''
    return m


def copy(model):
    from json import loads, dumps
    return loads(dumps(model))


# ---------------------------------------------------------------- variables

def scalars(model):
    """[(key, label, var)] for every value that may be given or found."""
    out = [('speed', 'Speed', model['speed']), ('Pi', 'Inner pressure', model['Pi']),
           ('Po', 'Outer pressure', model['Po'])]
    for j, f in enumerate(model['fits']):
        out.append((('delta', j), 'Interference %d' % (j + 1), f['delta']))
        out.append((('pc', j), 'Contact pressure %d' % (j + 1), f['pc']))
    return out


def get_var(model, key):
    if isinstance(key, tuple):
        return model['fits'][key[1]][key[0]]
    return model[key]


def finds(model):
    return [label for key, label, v in scalars(model) if v['find']]


def check(model):
    radii, bodies = model['radii'], model['bodies']
    if not bodies:
        raise ModelError('Add a body')
    if len(radii) != len(bodies) + 1 or len(model['fits']) != len(bodies) - 1:
        raise ModelError('Damaged model: radii, bodies and fits disagree')
    if radii[0] < 0:
        raise ModelError('Inner radius cannot be negative')
    for k, b in enumerate(bodies):
        if radii[k + 1] <= radii[k] * (1 + 1e-6) or radii[k + 1] - radii[k] < 1e-6:
            raise ModelError('Body %d: outer radius must exceed its inner radius' % (k + 1))
        if b['t'] <= 0:
            raise ModelError('Body %d: thickness must be above zero' % (k + 1))
        if not b['E'] > 0:
            raise ModelError('Body %d: E must be above zero' % (k + 1))
        if not -1 < b['nu'] < 0.5:
            raise ModelError('Body %d: Poisson ratio must lie between -1 and 0.5' % (k + 1))
        if b['rho'] < 0:
            raise ModelError('Body %d: density cannot be negative' % (k + 1))
    if radii[-1] > 10:
        raise ModelError('Keep radii under 10 m')
    if model['speed']['v'] < 0 and not model['speed']['find']:
        raise ModelError('Speed is a magnitude: use a positive value')
    found = finds(model)
    need = len(bodies) - 1
    if len(found) != need:
        if need == 0:
            raise ModelError('One body has nothing to find: mark every value Given (SPACE)')
        raise ModelError('Mark exactly %d value%s Find (SPACE); now %d' % (need, 's' if need > 1 else '', len(found)))
    if radii[0] == 0 and model['Pi']['find']:
        raise ModelError('Inner pressure needs a bore: body 1 is solid')


# ---------------------------------------------------------------- solving

def _constants(model, k):
    """(E MPa, nu, rho-term) for body k, in the solver's units."""
    b = model['bodies'][k]
    E, nu = b['E'] / 1e6, b['nu']
    if model['plane'] == 'strain':
        E, nu = E / (1 - nu * nu), nu / (1 - nu)
    return E, nu, b['rho'] * 1e-6


def _gauss(rows, rhs):
    """Solve a small dense system by partial pivoting; rows are equilibrated."""
    n = len(rows)
    for i in range(n):
        size = max(abs(v) for v in rows[i]) or 1.0
        rows[i] = [v / size for v in rows[i]]
        rhs[i] /= size
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(rows[r][c]))
        if abs(rows[p][c]) < 1e-5:
            raise ModelError('These values cannot be found together: change which are Find')
        rows[c], rows[p] = rows[p], rows[c]
        rhs[c], rhs[p] = rhs[p], rhs[c]
        pivot = rows[c][c]
        for r in range(c + 1, n):
            f = rows[r][c] / pivot
            if f:
                row, top = rows[r], rows[c]
                for j in range(c, n):
                    row[j] -= f * top[j]
                rhs[r] -= f * rhs[c]
    x = [0.0] * n
    for c in range(n - 1, -1, -1):
        s = rhs[c] - sum(rows[c][j] * x[j] for j in range(c + 1, n))
        x[c] = s / rows[c][c]
    return x


class Solution:
    """Stresses and displacements through the stack, and every value
    (given or found) in SI units."""

    def __init__(self, model):
        check(model)
        self.model = model
        N = len(model['bodies'])
        R = [r * 1e3 for r in model['radii']]  # mm
        self.R = R
        nv = 2 * N + 3 + 2 * (N - 1)
        PI, PO, OM = 2 * N, 2 * N + 1, 2 * N + 2

        def D(j):
            return 2 * N + 3 + j

        def PC(j):
            return 2 * N + 3 + (N - 1) + j
        consts = [_constants(model, k) for k in range(N)]
        self.consts = consts

        def sr(k, r):
            E, nu, c = consts[k]
            row = [0.0] * nv
            row[2 * k] = 1.0
            row[2 * k + 1] = (R[k + 1] / r) ** 2
            row[OM] = -(3 + nu) / 8 * c * r * r
            return row

        def u(k, r):
            E, nu, c = consts[k]
            row = [0.0] * nv
            row[2 * k] = r / E * (1 - nu)
            row[2 * k + 1] = -r / E * (1 + nu) * (R[k + 1] / r) ** 2
            row[OM] = -r / E * (1 - nu * nu) / 8 * c * r * r
            return row
        eqs = []
        if R[0] > 0:
            row = sr(0, R[0])
            row[PI] += 1.0
            eqs.append(row)
        else:
            row = [0.0] * nv
            row[1] = 1.0
            eqs.append(row)
        row = sr(N - 1, R[N])
        row[PO] += 1.0
        eqs.append(row)
        for j in range(N - 1):
            r = R[j + 1]
            for k in (j, j + 1):
                row = sr(k, r)
                row[PC(j)] += 1.0
                eqs.append(row)
            a, b = u(j, r), u(j + 1, r)
            row = [E_REF * (b[i] - a[i]) for i in range(nv)]
            row[D(j)] -= E_REF / 2  # diametral interference, radial share
            eqs.append(row)
        # Known values in solver units; unknown ones become columns.
        known = [None] * nv
        w = model['speed']
        known[PI] = None if model['Pi']['find'] else model['Pi']['v'] / 1e6
        known[PO] = None if model['Po']['find'] else model['Po']['v'] / 1e6
        known[OM] = None if w['find'] else (w['v'] / 1e3) ** 2
        for j, f in enumerate(model['fits']):
            known[D(j)] = None if f['delta']['find'] else f['delta']['v'] * 1e3
            known[PC(j)] = None if f['pc']['find'] else f['pc']['v'] / 1e6
        unknown = [i for i in range(nv) if i < 2 * N or known[i] is None]
        rows = [[e[i] for i in unknown] for e in eqs]
        rhs = [-sum(e[i] * known[i] for i in range(nv) if known[i] is not None) for e in eqs]
        x = _gauss(rows, rhs)
        full = list(known)
        for i, value in zip(unknown, x):
            full[i] = value
        if w['find']:
            if full[OM] < -1e-6 * max(1.0, abs(full[OM])):
                raise ModelError('No speed does this: it would need w^2 < 0')
            full[OM] = max(0.0, full[OM])
        self.x = full
        self.N = N
        self.om = full[OM]
        self.values = {'speed': 1e3 * sqrt(full[OM]), 'Pi': full[PI] * 1e6, 'Po': full[PO] * 1e6,
                       'delta': [full[D(j)] / 1e3 for j in range(N - 1)],
                       'pc': [full[PC(j)] * 1e6 for j in range(N - 1)]}
        if R[0] == 0:
            self.values['Pi'] = 0.0

    def value(self, key):
        if isinstance(key, tuple):
            return self.values[key[0]][key[1]]
        return self.values[key]

    def at(self, k, r_mm):
        """(sr, st, sz MPa, u mm, von Mises MPa) in body k at r mm."""
        E, nu, c = self.consts[k]
        A, B = self.x[2 * k], self.x[2 * k + 1]
        q = (self.R[k + 1] / r_mm) ** 2 if r_mm > 0 else 0.0
        rr = r_mm * r_mm
        om = self.om
        sr = A + B * q - (3 + nu) / 8 * c * om * rr
        st = A - B * q - (1 + 3 * nu) / 8 * c * om * rr
        u = r_mm / E * ((1 - nu) * A - (1 + nu) * B * q - (1 - nu * nu) / 8 * c * om * rr)
        sz = self.model['bodies'][k]['nu'] * (sr + st) if self.model['plane'] == 'strain' else 0.0
        vm = sqrt(max(0.0, ((sr - st) ** 2 + (st - sz) ** 2 + (sz - sr) ** 2) / 2))
        return sr, st, sz, u, vm

    def samples(self, k, n=33):
        a, b = self.R[k], self.R[k + 1]
        return [(a + (b - a) * i / (n - 1),) + self.at(k, a + (b - a) * i / (n - 1)) for i in range(n)]

    def peaks(self, k):
        """{'sr'|'st'|'vm': (max, r, min, r)} in MPa and mm over body k."""
        out = {}
        S = self.samples(k)
        for name, q in (('sr', 1), ('st', 2), ('sz', 3), ('u', 4), ('vm', 5)):
            hi = max(S, key=lambda s: s[q])
            lo = min(S, key=lambda s: s[q])
            out[name] = (hi[q], hi[0], lo[q], lo[0])
        return out

    def warnings(self):
        out = []
        for j, pc in enumerate(self.values['pc']):
            if pc < -1e-3 * max(1.0, max(abs(v) for v in self.values['pc'])):
                out.append('Fit %d opens: contact pressure would be negative' % (j + 1))
        for j, d in enumerate(self.values['delta']):
            if self.model['fits'][j]['delta']['find'] and d < 0:
                out.append('Fit %d needs a clearance, not an interference' % (j + 1))
        return out

    # ------------------------------------------------------------ fit results

    def torque(self, j):
        """Holding torque N*m and axial force N of fit j from friction."""
        m = self.model
        r = self.R[j + 1]
        L = min(m['bodies'][j]['t'], m['bodies'][j + 1]['t']) * 1e3
        pc = self.values['pc'][j] / 1e6
        mu = m['fits'][j]['mu']
        return mu * pc * 2 * pi * r * r * L / 1e3, mu * pc * 2 * pi * r * L

    def heating(self, j):
        """Temperature rise of the outer part that opens the fit's interference, K."""
        alpha = self.model['bodies'][j + 1]['alpha']
        d = 2 * self.model['radii'][j + 1]
        delta = self.values['delta'][j]
        return delta / (alpha * d) if alpha > 0 and delta > 0 else None

    def loosening(self, j):
        """Speed rad/s at which fit j's contact pressure reaches zero, or None."""
        if self.values['pc'][j] <= 0:
            return 0.0
        m = copy(self.model)
        m['Pi'], m['Po'] = var(self.values['Pi']), var(self.values['Po'])
        m['speed'] = var(0.0, True)
        for i, f in enumerate(m['fits']):
            f['delta'] = var(self.values['delta'][i])
            f['pc'] = var(0.0) if i == j else var(0.0, True)
        try:
            return Solution(m).values['speed']
        except ModelError:
            return None

    def inertia(self):
        """Polar moment of inertia kg*m^2 and kinetic energy J."""
        I = 0.0
        r = self.model['radii']
        for k, b in enumerate(self.model['bodies']):
            I += pi / 2 * b['rho'] * b['t'] * (r[k + 1] ** 4 - r[k] ** 4)
        w = self.values['speed']
        return I, I * w * w / 2
