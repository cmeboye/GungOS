"""Section stress fields; exact normal extrema and bounded sampled searches.

The shear field is the same elementary beam/shaft model as model.solve().
Sampling is a visual aid, not a certified upper bound on equivalent stress.
"""
from math import sqrt, sin, cos, pi
from . import model

KINDS = ('Normal sx', 'Shear |tau|', 'von Mises')
CRITICAL = ('Max sx', 'Min sx', 'Max |tau|', 'Max von Mises')


class SectionField:
    def __init__(self, state):
        # Validate loads, material, dimensions and the current probe first.
        result = model.solve(state)
        if state['mode'] != 'section' or state['shape'] == 'custom':
            raise ValueError('A known section boundary is needed for a stress map')
        self.state = model.copy(state)
        self.props = result['properties']
        p, loads = self.props, state['loads']
        self.axial = loads['N']/p['A']
        self.by, self.bz = loads['My']/p['Iy'], -loads['Mz']/p['Iz']
        self.t = loads['T']/p['J'] if p['J'] else 0.0
        self.vy, self.vz = 1.5*loads['Vy']/p['A'], 1.5*loads['Vz']/p['A']
        self.ry, self.rz = p['ry'], p['rz']
        self.extrema = [None]*4
        self.samples = 0
        if state['shape'] == 'rectangle':
            for j in range(33):
                for i in range(33):
                    self.visit(self.ry*(i/16-1), self.rz*(j/16-1))
            self.method = '33 x 33 grid incl. edges'
        else:
            inner = state['section']['di']/2 if state['shape'] == 'tube' else 0.0
            for j in range(9):
                radius = inner+(self.ry-inner)*j/8
                for i in range(96):
                    angle = 2*pi*i/96
                    self.visit(radius*cos(angle), radius*sin(angle))
            self.method = '9 radii x 96 angles incl. edges'
        # A linear normal-stress field has exact extrema on corners or on
        # the outer circle in the bending-gradient direction.
        if state['shape'] == 'rectangle':
            y = self.ry if self.bz >= 0 else -self.ry
            z = self.rz if self.by >= 0 else -self.rz
        else:
            # Scale the gradient before taking its length on float32.
            scale = max(abs(self.by), abs(self.bz))
            if scale:
                a, b = self.bz/scale, self.by/scale
                length = sqrt(a*a+b*b)
                y, z = self.ry*a/length, self.rz*b/length
            else:
                y, z = self.ry, 0.0
        self.visit(y, z)
        self.visit(-y, -z)
        self.extrema[0] = (self.values(y, z)[0], y, z)
        self.extrema[1] = (self.values(-y, -z)[0], -y, -z)

    def values(self, y, z):
        normal = self.axial+self.by*z+self.bz*y
        ty, tz = -self.t*z, self.t*y
        if self.state['shape'] == 'rectangle':
            ty += self.vy*(1-(y/self.ry)**2)
            tz += self.vz*(1-(z/self.rz)**2)
        # Normalise before squares to avoid overflowing float32.
        scale = max(abs(normal), abs(ty), abs(tz))
        if not scale:
            return (0.0, 0.0, 0.0)
        shear2 = (ty/scale)**2+(tz/scale)**2
        values = (normal, scale*sqrt(shear2), scale*sqrt((normal/scale)**2+3*shear2))
        model.finite(values)
        return values

    def visit(self, y, z):
        values = self.values(y, z)
        self.samples += 1
        for index, value in enumerate((values[0], values[0], values[1], values[2])):
            old = self.extrema[index]
            if old is None or (value < old[0] if index == 1 else value > old[0]):
                self.extrema[index] = (value, y, z)

    def limits(self, kind):
        if kind == 0:
            span = max(abs(self.extrema[0][0]), abs(self.extrema[1][0]))
            return -span, span
        return 0.0, self.extrema[kind+1][0]
