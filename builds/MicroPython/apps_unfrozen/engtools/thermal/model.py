"""Two-dimensional heat conduction in a rectangular plate.

The plate is split into W x H cells with a finite-volume balance on each:
conductances between cells, a half-cell conductance to each boundary and a
heat source per cell. Steady state uses preconditioned conjugate gradients
and a transient uses explicit steps, both on whole ulab arrays. The plate has a uniform
conductivity; the faces (front and back) are insulated, so the problem is
per unit depth and "depth" only scales the heat flows into watts.

Temperatures are stored relative to a reference so float32 keeps its
precision. Inputs are in mm, W/mK, kg/m3, J/kgK, W/m2K, W/m3, C and s.
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


def new_state():
    sides = [{'kind': INSULATED, 'T': 20.0, 'h': 25.0, 'q': 0.0} for _ in SIDES]
    sides[0].update(kind=TEMPERATURE, T=100.0)
    sides[1].update(kind=TEMPERATURE, T=0.0)
    return {'mode': 'steady', 'W': 100.0, 'H': 60.0, 'depth': 10.0, 'mat': 1,
            'k': MATERIALS[1][1], 'rho': MATERIALS[1][2], 'cp': MATERIALS[1][3],
            'gen': 0.0, 'pq': 0.0, 'px': 40.0, 'py': 25.0, 'pw': 20.0, 'ph': 10.0,
            'res': 1, 'T0': 20.0, 'tend': 60.0, 'sides': sides}


def copy_state(state):
    out = dict(state)
    out['sides'] = [dict(side) for side in state['sides']]
    return out


def diffusivity(state):
    return state['k'] / (state['rho'] * state['cp'])


def check(state):
    """Raise ValueError, in plain words, when the problem cannot be solved."""
    if state['W'] <= 0 or state['H'] <= 0 or state['depth'] <= 0:
        raise ValueError('Width, height and depth must be positive')
    if state['k'] <= 0 or state['rho'] <= 0 or state['cp'] <= 0:
        raise ValueError('k, density and specific heat must be positive')
    if state['pq'] != 0 and (state['pw'] <= 0 or state['ph'] <= 0 or state['px'] < 0 or state['py'] < 0
                             or state['px'] + state['pw'] > state['W'] + 1e-9
                             or state['py'] + state['ph'] > state['H'] + 1e-9):
        raise ValueError('The heat patch must lie inside the plate')
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
        self.patch = 0
        if state['pq'] != 0:
            self.patch = self._patch(source, state['pq'] * dx * dy)
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

    def _patch(self, source, power):
        """Add the patch's source to the cells whose centres fall in it."""
        state = self.state
        dx, dy = self.dx * 1000, self.dy * 1000
        cells = []
        for j in range(self.ny):
            for i in range(self.nx):
                x, y = (i + 0.5) * dx, (j + 0.5) * dy
                if state['px'] <= x <= state['px'] + state['pw'] and state['py'] <= y <= state['py'] + state['ph']:
                    cells.append((j, i))
        if not cells:   # a patch smaller than a cell still heats the cell it sits in
            x, y = state['px'] + state['pw'] / 2, state['py'] + state['ph'] / 2
            cells.append((min(self.ny - 1, int(y / dy)), min(self.nx - 1, int(x / dx))))
        # Keep the total power of the patch whatever the cell count.
        per_cell = state['pq'] * state['pw'] / 1000 * state['ph'] / 1000 / len(cells)
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

    def temperature(self, j, i):
        return float(self.T[j, i]) + self.ref

    def stats(self):
        np, T = self.np, self.T
        low, high = float(np.min(T)), float(np.max(T))
        where = int(np.argmax(T))
        return {'min': low + self.ref, 'max': high + self.ref, 'mean': float(np.mean(T)) + self.ref,
                'hot': (where // self.nx, where % self.nx)}

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
