"""Two-dimensional heat conduction in a rectangular plate.

The plate is split into W x H cells with a finite-volume balance on each:
conductances between cells, a half-cell conductance to each boundary and a
heat source per cell. Steady state uses preconditioned conjugate gradients
and a transient uses explicit steps, both on whole ulab arrays. The plate has a uniform
conductivity; the faces (front and back) are insulated, so the problem is
per unit depth and "depth" only scales the heat flows into watts.

Temperatures are stored relative to a reference so float32 keeps its
precision. Inputs are in mm, W/mK, kg/m3, J/kgK, W/m2K, W/m3, W, C and s.
Heat patches (chips, heaters) give their total power in W over the depth.
"""
from math import sqrt
from time import ticks_ms, ticks_diff

# name, conductivity W/mK, density kg/m3, specific heat J/kgK
MATERIALS = (
    ('Copper', 400.0, 8960.0, 385.0),
    ('Aluminium 6061', 167.0, 2700.0, 896.0),
    ('Silicon', 148.0, 2330.0, 705.0),
    ('Brass', 109.0, 8500.0, 380.0),
    ('Carbon steel', 50.0, 7850.0, 490.0),
    ('Stainless 304', 16.0, 8000.0, 500.0),
    ('Titanium Ti-6Al-4V', 6.7, 4430.0, 526.0),
    ('Concrete', 1.4, 2300.0, 880.0),
    ('Glass', 1.0, 2500.0, 840.0),
    ('Brick', 0.72, 1920.0, 835.0),
    ('FR4 board', 0.3, 1850.0, 1100.0),
    ('Pine wood', 0.12, 500.0, 1700.0),
    ('Polystyrene foam', 0.033, 30.0, 1210.0),
    ('Custom', 1.0, 1000.0, 1000.0),
)
CUSTOM = len(MATERIALS) - 1
SIDES = ('Left', 'Right', 'Bottom', 'Top')
KINDS = ('Insulated', 'Temperature', 'Convection', 'Heat flux')
INSULATED, TEMPERATURE, CONVECTION, FLUX = range(4)
RESOLUTIONS = (16, 24, 32, 40)
RESOLUTION_NAMES = ('Coarse 16', 'Medium 24', 'Fine 32', 'Finest 40')
ITERATION_LIMIT = 6000
STEP_LIMIT = 2000000
TOLERANCE = 1e-6      # residual relative to the heat sources
RESOLUTION = 1e-6     # an update this small, against the field, is below float32
REFRESH = 25          # iterations between true residuals
MAX_PATCHES = 4
HISTORY = 120         # transient samples after the start: with t, min, mean, max a CSV fits Eggcel
TOOL = 'thermal'


def new_state():
    sides = [{'kind': INSULATED, 'T': 20.0, 'h': 25.0, 'q': 0.0} for _ in SIDES]
    sides[0].update(kind=TEMPERATURE, T=100.0)
    sides[1].update(kind=TEMPERATURE, T=0.0)
    return {'mode': 'steady', 'W': 100.0, 'H': 60.0, 'depth': 10.0, 'mat': 1,
            'k': MATERIALS[1][1], 'rho': MATERIALS[1][2], 'cp': MATERIALS[1][3],
            'gen': 0.0, 'patches': [], 'res': 1, 'T0': 20.0, 'tend': 60.0, 'sides': sides}


def new_patch(state):
    """A patch a fifth of the plate, centred, giving 1 W."""
    w, h = state['W'] / 5, state['H'] / 5
    return {'P': 1.0, 'x': (state['W'] - w) / 2, 'y': (state['H'] - h) / 2, 'w': w, 'h': h}


def copy_state(state):
    out = dict(state)
    out['sides'] = [dict(side) for side in state['sides']]
    out['patches'] = [dict(patch) for patch in state['patches']]
    return out


def to_case(state):
    case = copy_state(state)
    case['tool'] = TOOL
    return case


def from_case(case):
    """A state from a saved case, keeping only known entries of the right
    type, so a damaged or older file cannot break the screen."""
    state = new_state()
    for key, value in state.items():
        if key in ('sides', 'patches'):
            continue
        given = case.get(key)
        if isinstance(value, float) and isinstance(given, (int, float)):
            state[key] = float(given)
        elif isinstance(value, int) and isinstance(given, int):
            state[key] = given
        elif isinstance(value, str) and given in ('steady', 'transient'):
            state[key] = given
    state['mat'] = min(max(state['mat'], 0), CUSTOM)
    state['res'] = min(max(state['res'], 0), len(RESOLUTIONS) - 1)
    for side, given in zip(state['sides'], case.get('sides') or ()):
        if isinstance(given, dict):
            for key in side:
                if isinstance(given.get(key), (int, float)):
                    side[key] = type(side[key])(given[key])
            side['kind'] = min(max(side['kind'], 0), len(KINDS) - 1)
    if case.get('pq'):   # the first version's single patch, in W/m3
        case = dict(case, patches=[{'P': case['pq'] * case['pw'] * case['ph'] * case['depth'] / 1e9,
                                    'x': case['px'], 'y': case['py'], 'w': case['pw'], 'h': case['ph']}])
    for given in (case.get('patches') or ())[:MAX_PATCHES]:
        if isinstance(given, dict) and all(isinstance(given.get(key), (int, float)) for key in 'Pxywh'):
            state['patches'].append({key: float(given[key]) for key in 'Pxywh'})
    if isinstance(case.get('name'), str):
        state['name'] = case['name']
    return state


def diffusivity(state):
    return state['k'] / (state['rho'] * state['cp'])


def check(state):
    """Raise ValueError, in plain words, when the problem cannot be solved."""
    if state['W'] <= 0 or state['H'] <= 0 or state['depth'] <= 0:
        raise ValueError('Width, height and depth must be positive')
    if state['k'] <= 0 or state['rho'] <= 0 or state['cp'] <= 0:
        raise ValueError('k, density and specific heat must be positive')
    for n, patch in enumerate(state['patches']):
        if (patch['w'] <= 0 or patch['h'] <= 0 or patch['x'] < 0 or patch['y'] < 0
                or patch['x'] + patch['w'] > state['W'] + 1e-9 or patch['y'] + patch['h'] > state['H'] + 1e-9):
            raise ValueError('Patch %d must lie inside the plate' % (n + 1))
    cooled = False
    for side in state['sides']:
        if side['kind'] == CONVECTION:
            if side['h'] <= 0:
                raise ValueError('Convection needs h > 0')
            cooled = True
        elif side['kind'] == TEMPERATURE:
            cooled = True
    if state['mode'] == 'steady' and not cooled:
        raise ValueError('Steady state needs a Temperature or Convection side')
    if state['mode'] == 'transient' and state['tend'] <= 0:
        raise ValueError('End time must be positive')


def grid_size(state):
    n = RESOLUTIONS[state['res']]
    if state['W'] >= state['H']:
        return n, max(2, int(n * state['H'] / state['W'] + 0.5))
    return max(2, int(n * state['W'] / state['H'] + 0.5)), n


class Plate:
    """Cells, sources and boundary conductances for one problem, with the
    temperature field and the stepping routines that advance it."""

    def __init__(self, state):
        from engtools.numerics.backend import require
        check(state)
        np = self.np = require()[0]
        self.state = state
        nx, ny = self.nx, self.ny = grid_size(state)
        dx, dy = self.dx, self.dy = state['W'] / 1000 / nx, state['H'] / 1000 / ny
        k = state['k']
        gx, gy = self.gx, self.gy = k * dy / dx, k * dx / dy
        self.depth = state['depth'] / 1000
        self.capacity = state['rho'] * state['cp'] * dx * dy
        sides = state['sides']
        # Reference: the mean of the fixed and ambient temperatures.
        fixed = [s['T'] for s in sides if s['kind'] in (TEMPERATURE, CONVECTION)]
        steady = state['mode'] == 'steady'
        self.ref = sum(fixed) / len(fixed) if fixed and steady else state['T0']
        ref = self.ref
        source = np.ones((ny, nx)) * (state['gen'] * dx * dy)
        self.patch_cells = [self._patch(source, patch) for patch in state['patches']]
        conductance = np.zeros((ny, nx))
        pull = np.zeros((ny, nx))   # conductance times boundary temperature
        flux = np.zeros((ny, nx))   # imposed heat flux through the edges
        self.edges = [[], [], [], []]
        for index, side in enumerate(sides):
            horizontal = index < 2
            face = dy if horizontal else dx
            half = (dx if horizontal else dy) / 2
            kind = side['kind']
            if kind == INSULATED:
                g = 0.0
            elif kind == TEMPERATURE:
                g, boundary = k * face / half, side['T'] - ref
            elif kind == CONVECTION:
                g, boundary = face / (half / k + 1.0 / side['h']), side['T'] - ref
            if kind == FLUX:
                g, boundary = 0.0, 0.0
            cells = ([(j, 0 if index == 0 else nx - 1) for j in range(ny)] if horizontal else
                     [(0 if index == 2 else ny - 1, i) for i in range(nx)])
            for j, i in cells:
                if kind == FLUX:
                    flux[j, i] = flux[j, i] + side['q'] * face
                elif g:
                    conductance[j, i] = conductance[j, i] + g
                    pull[j, i] = pull[j, i] + g * boundary
                self.edges[index].append((j, i, g, boundary if g else 0.0))
        self.source = source
        self.conductance = conductance
        self.pull = pull
        self.base = source + pull + flux
        denominator = conductance + 0.0
        denominator[:, 1:] = denominator[:, 1:] + gx
        denominator[:, :-1] = denominator[:, :-1] + gx
        denominator[1:, :] = denominator[1:, :] + gy
        denominator[:-1, :] = denominator[:-1, :] + gy
        self.denominator = denominator
        self.time = 0.0
        self.iterations = 0
        self.done = False
        self.converged = True
        self.T = np.zeros((ny, nx))   # relative to ref, which is the start temperature
        if steady:
            self.residual = self.base + 0.0
            self.direction = self.residual / denominator
            self.rz = float(np.sum(self.residual * self.direction))
            self.norm = sqrt(float(np.sum(self.base * self.base)))
            self.done = self.norm == 0.0   # nothing drives a change from the reference
        else:
            self.dt = 0.9 * self.capacity / float(np.max(denominator))
            steps = state['tend'] / self.dt
            if steps > STEP_LIMIT:
                raise ValueError('Too many time steps (%d): shorten the end time or use a coarser grid' % steps)
            self.steps = max(1, int(steps) + 1)
            self.dt = state['tend'] / self.steps
            self.step_count = 0
            self.every = max(1, -(-self.steps // HISTORY))
            self.history = []
            self._record()

    def _patch(self, source, patch):
        """Add the patch's source to the cells whose centres fall in it."""
        dx, dy = self.dx * 1000, self.dy * 1000
        x0, y0, x1, y1 = patch['x'], patch['y'], patch['x'] + patch['w'], patch['y'] + patch['h']
        i0, i1 = max(0, int(x0 / dx - 0.5)), min(self.nx - 1, int(x1 / dx))
        j0, j1 = max(0, int(y0 / dy - 0.5)), min(self.ny - 1, int(y1 / dy))
        cells = [(j, i) for j in range(j0, j1 + 1) for i in range(i0, i1 + 1)
                 if x0 <= (i + 0.5) * dx <= x1 and y0 <= (j + 0.5) * dy <= y1]
        if not cells:   # a patch smaller than a cell still heats the cell it sits in
            cells.append((min(self.ny - 1, int((y0 + y1) / 2 / dy)), min(self.nx - 1, int((x0 + x1) / 2 / dx))))
        # Keep the total power of the patch whatever the cell count: W per metre of depth.
        per_cell = patch['P'] / self.depth / len(cells)
        for j, i in cells:
            source[j, i] = source[j, i] + per_cell
        return len(cells)

    # ------------------------------------------------------------ stepping

    def _apply(self, x):
        """The conduction matrix times a temperature field. Built from
        temperature differences so a nearly uniform plate keeps float32 precision."""
        gx, gy = self.gx, self.gy
        y = self.conductance * x
        flow = x[:, 1:] - x[:, :-1]
        y[:, :-1] = y[:, :-1] - gx * flow
        y[:, 1:] = y[:, 1:] + gx * flow
        flow = x[1:, :] - x[:-1, :]
        y[:-1, :] = y[:-1, :] - gy * flow
        y[1:, :] = y[1:, :] + gy * flow
        return y

    def _iterate(self):
        """One preconditioned conjugate gradient iteration; True once converged."""
        np = self.np
        p = self.direction
        ap = self._apply(p)
        curvature = float(np.sum(p * ap))
        if curvature <= 0.0:
            return True
        alpha = self.rz / curvature
        self.T = self.T + alpha * p
        self.iterations += 1
        # The field is stored to about 1e-7 of its size; once the updates are
        # smaller than that the residual only measures that rounding.
        step = abs(alpha) * max(float(np.max(p)), -float(np.min(p)))
        size = max(float(np.max(self.T)), -float(np.min(self.T)))
        if step <= RESOLUTION * size:
            return True
        if self.iterations % REFRESH == 0:
            self.residual = self.base - self._apply(self.T)   # undo float32 drift
        else:
            self.residual = self.residual - alpha * ap
        r = self.residual
        z = r / self.denominator
        rz = float(np.sum(r * z))
        self.direction = z + (rz / self.rz) * p
        self.rz = rz
        return sqrt(float(np.sum(r * r))) <= TOLERANCE * self.norm

    def _step(self):
        T, gx, gy = self.T, self.gx, self.gy
        net = self.base - self.conductance * T
        flow = T[:, 1:] - T[:, :-1]
        net[:, :-1] = net[:, :-1] + gx * flow
        net[:, 1:] = net[:, 1:] - gx * flow
        flow = T[1:, :] - T[:-1, :]
        net[:-1, :] = net[:-1, :] + gy * flow
        net[1:, :] = net[1:, :] - gy * flow
        self.T = T + (self.dt / self.capacity) * net

    def advance(self, budget_ms):
        """Work for about budget_ms, then return True once finished."""
        if self.done:
            return True
        start = ticks_ms()
        steady = self.state['mode'] == 'steady'
        while True:
            if steady:
                for _ in range(4):
                    if self._iterate():
                        self.done = True
                        break
                    if self.iterations >= ITERATION_LIMIT:
                        self.done, self.converged = True, False
                        break
            else:
                for _ in range(8):
                    if self.step_count >= self.steps:
                        break
                    self._step()
                    self.step_count += 1
                    if self.step_count % self.every == 0 or self.step_count == self.steps:
                        self._record()
                self.time = self.step_count * self.dt
                if self.step_count >= self.steps:
                    self.done = True
                    self.time = self.state['tend']
            if self.done or ticks_diff(ticks_ms(), start) >= budget_ms:
                return self.done

    @property
    def progress(self):
        """0..1 of the work known in advance (transient), else None."""
        if self.state['mode'] == 'steady':
            return None
        return self.step_count / self.steps

    # ------------------------------------------------------------ results

    def _record(self):
        np, T = self.np, self.T
        self.history.append((self.step_count * self.dt, float(np.min(T)) + self.ref,
                             float(np.mean(T)) + self.ref, float(np.max(T)) + self.ref))

    def temperature(self, j, i):
        return float(self.T[j, i]) + self.ref

    def cell(self, x, y):
        """The (j, i) cell containing the point x, y in mm."""
        return (min(self.ny - 1, max(0, int(y / (self.dy * 1000)))),
                min(self.nx - 1, max(0, int(x / (self.dx * 1000)))))

    def centre(self, j, i):
        """The centre of cell (j, i) in mm."""
        return (i + 0.5) * self.dx * 1000, (j + 0.5) * self.dy * 1000

    def flux(self, j, i):
        """Heat flux (qx, qy) in W/m2 at a cell centre, from the temperature
        differences to its neighbours (one-sided at the edges)."""
        T, k = self.T, self.state['k']
        a, b = max(0, i - 1), min(self.nx - 1, i + 1)
        qx = -k * (float(T[j, b]) - float(T[j, a])) / ((b - a) * self.dx) if b > a else 0.0
        a, b = max(0, j - 1), min(self.ny - 1, j + 1)
        qy = -k * (float(T[b, i]) - float(T[a, i])) / ((b - a) * self.dy) if b > a else 0.0
        return qx, qy

    def row(self, j):
        """Temperatures along x through row j."""
        return [v + self.ref for v in self.T[j, :].tolist()]

    def column(self, i):
        """Temperatures along y through column i."""
        return [v + self.ref for v in self.T[:, i].tolist()]

    def stats(self):
        np, T = self.np, self.T
        low, high = float(np.min(T)), float(np.max(T))
        hot, cold = int(np.argmax(T)), int(np.argmin(T))
        return {'min': low + self.ref, 'max': high + self.ref, 'mean': float(np.mean(T)) + self.ref,
                'hot': (hot // self.nx, hot % self.nx), 'cold': (cold // self.nx, cold % self.nx)}

    def flows(self):
        """Heat into the plate through each side, the heat generated inside
        and their sum (zero in a converged steady state), in W."""
        T, depth = self.T, self.depth
        sides = []
        for index, edge in enumerate(self.edges):
            total = 0.0
            if self.state['sides'][index]['kind'] == FLUX:
                total = self.state['sides'][index]['q'] * len(edge) * (self.dy if index < 2 else self.dx)
            else:
                for j, i, g, boundary in edge:
                    total += g * (boundary - float(T[j, i]))
            sides.append(total * depth)
        generated = float(self.np.sum(self.source)) * depth
        return {'sides': sides, 'generated': generated, 'net': sum(sides) + generated,
                'scale': sum(abs(v) for v in sides) + abs(generated)}
