"""SI section loads and small-strain isotropic thermoelasticity.

Section x is longitudinal, y right, z up on the +x cut face.
T, My and Mz follow the right-hand rule on that face. Stress/strain order:
xx, yy, zz, xy, yz, zx. Strains use engineering gamma, not tensor shear.
"""
from math import pi, sqrt, isfinite
from engtools import materials

TOOL = 'stressstrain'
SHAPES = ('circle', 'tube', 'rectangle', 'custom')
SHAPE_NAMES = ('Solid circle', 'Circular tube', 'Rectangle', 'Custom principal section')
CONDITIONS = ('3d', 'plane-stress', 'plane-strain')
CONDITION_NAMES = ('3D general', 'Plane stress (sz = 0)', 'Plane strain (ez = 0)')
STRESSES = ('sx', 'sy', 'sz', 'txy', 'tyz', 'tzx')
STRAINS = ('ex', 'ey', 'ez', 'gxy', 'gyz', 'gzx')


def new_state():
    return {'mode': 'section', 'shape': 'circle',
            'section': {'d': .04, 'di': .02, 'b': .04, 'h': .06,
                        'A': .001, 'Iy': 1e-7, 'Iz': 1e-7},
            'point': {'y': .02, 'z': 0.0},
            'loads': {'N': 10000.0, 'My': 100.0, 'Mz': 0.0, 'T': 100.0, 'Vy': 0.0, 'Vz': 0.0},
            'material': materials.preset(), 'dt': 0.0,
            'condition': '3d', 'direction': 'stress',
            'stress': [100e6, 0.0, 0.0, 0.0, 0.0, 0.0],
            'strain': [.0005, -.00015, -.00015, 0.0, 0.0, 0.0]}


def copy(state):
    out = dict(state)
    for key in ('section', 'point', 'loads', 'material'):
        out[key] = dict(state[key])
    out['stress'], out['strain'] = list(state['stress']), list(state['strain'])
    return out


def finite(values):
    if any(not isinstance(v, (int, float)) or not isfinite(v) for v in values):
        raise ValueError('Inputs and results must be finite numbers')


def section(state):
    s, shape = state['section'], state['shape']
    if shape not in SHAPES:
        raise ValueError('Unknown section shape')
    if shape in ('circle', 'tube'):
        d, di = s['d'], s['di'] if shape == 'tube' else 0.0
        if d <= 0 or not 0 <= di < d:
            raise ValueError('Use 0 <= inner diameter < outer diameter')
        A, I = pi*(d-di)*(d+di)/4, pi*(d-di)*(d+di)*(d*d+di*di)/64
        out = {'A': A, 'Iy': I, 'Iz': I, 'J': 2*I, 'ry': d/2, 'rz': d/2}
    elif shape == 'rectangle':
        b, h = s['b'], s['h']
        if min(b, h) <= 0:
            raise ValueError('Width and height must be positive')
        out = {'A': b*h, 'Iy': b*h**3/12, 'Iz': h*b**3/12, 'J': None, 'ry': b/2, 'rz': h/2}
    else:
        if min(s['A'], s['Iy'], s['Iz']) <= 0:
            raise ValueError('Area and principal inertias must be positive')
        out = {'A': s['A'], 'Iy': s['Iy'], 'Iz': s['Iz'], 'J': None,
               'ry': max(abs(state['point']['y'])*1.25, .02),
               'rz': max(abs(state['point']['z'])*1.25, .02)}
    finite(v for v in out.values() if v is not None)
    if min(out['A'], out['Iy'], out['Iz']) <= 0:
        raise ValueError('Section properties exceed the numeric range')
    return out


def contains(state, y, z):
    s, shape = state['section'], state['shape']
    if shape in ('circle', 'tube'):
        r = sqrt(y*y+z*z)
        return (s['di']/2 if shape == 'tube' else 0.0)-s['d']*1e-6 <= r <= s['d']/2+s['d']*1e-6
    if shape == 'rectangle':
        return abs(y) <= s['b']*(.5+1e-6) and abs(z) <= s['h']*(.5+1e-6)
    return True  # A custom record has no boundary to check.


def compliance(stress, material, dt):
    E, nu = material['E'], material['nu']
    thermal, G = material['alpha']*dt, E/(2*(1+nu))
    return [(stress[i]-nu*(stress[(i+1)%3]+stress[(i+2)%3]))/E+thermal for i in range(3)] + [v/G for v in stress[3:]]


def stiffness(strain, material, dt):
    E, nu = material['E'], material['nu']
    G, thermal = E/(2*(1+nu)), material['alpha']*dt
    mechanical = [v-thermal for v in strain[:3]]
    lam_trace = E*nu/((1+nu)*(1-2*nu))*sum(mechanical)
    return [2*G*v+lam_trace for v in mechanical] + [G*v for v in strain[3:]]


def constitutive(state):
    mat, dt = state['material'], state['dt']
    E, nu, thermal = mat['E'], mat['nu'], mat['alpha']*dt
    plane = state['condition']
    if state['direction'] == 'stress':
        s = list(state['stress'])
        if plane != '3d':
            s[2] = 0.0 if plane == 'plane-stress' else nu*(s[0]+s[1])-E*thermal
            s[4] = s[5] = 0.0
        e = compliance(s, mat, dt)
        if plane == 'plane-strain':
            e[2] = 0.0
    else:
        e = list(state['strain'])
        if plane != '3d':
            e[2] = 0.0 if plane == 'plane-strain' else thermal-nu/(1-nu)*(e[0]+e[1]-2*thermal)
            e[4] = e[5] = 0.0
        s = stiffness(e, mat, dt)
        if plane == 'plane-stress':
            s[2] = 0.0
    return s, e


def solve(state):
    materials.check(state['material'])
    if state['mode'] not in ('section', 'constitutive') or state['condition'] not in CONDITIONS or state['direction'] not in ('stress', 'strain'):
        raise ValueError('Unknown analysis mode')
    finite([state['dt']] + list(state['section'].values()) + list(state['point'].values()) +
           list(state['loads'].values()) + state['stress'] + state['strain'])
    contributions, props, notes = [], None, []
    if state['mode'] == 'section':
        props = section(state)
        y, z = state['point']['y'], state['point']['z']
        L, shape = state['loads'], state['shape']
        if not contains(state, y, z):
            raise ValueError('Evaluation point must lie in the section material')
        if L['T'] and shape not in ('circle', 'tube'):
            raise ValueError('Torsion is supported for circular sections only')
        if (L['Vy'] or L['Vz']) and shape != 'rectangle':
            raise ValueError('Transverse shear is supported for rectangles only')
        axial, by, bz = L['N']/props['A'], L['My']*z/props['Iy'], -L['Mz']*y/props['Iz']
        ty, tz = (-L['T']*z/props['J'], L['T']*y/props['J']) if props['J'] else (0.0, 0.0)
        vy, vz = (1.5*L['Vy']/props['A']*(1-(y/props['ry'])**2),
                  1.5*L['Vz']/props['A']*(1-(z/props['rz'])**2)) if shape == 'rectangle' else (0.0, 0.0)
        s = [axial+by+bz, 0.0, 0.0, ty+vy, 0.0, tz+vz]
        e = compliance(s, state['material'], state['dt'])
        contributions = [('N / A', axial), ('My * z / Iy', by), ('-Mz * y / Iz', bz),
                         ('T -> txy', ty), ('T -> txz', tz), ('Vy -> txy', vy), ('Vz -> txz', vz)]
        if shape == 'rectangle':
            notes.append('Transverse shear uses breadth-averaged beam theory.')
        if shape == 'custom':
            notes.append('Custom y/z axes must be centroidal principal axes; boundary is unchecked.')
        if state['dt']:
            notes.append('Section thermal expansion is free; no restraint stress is added.')
    else:
        s, e = constitutive(state)
    finite(s+e+[v for _, v in contributions])
    # The existing Mohr routine expects MPa; this avoids squared Pa values
    # overflowing float32 while keeping one implementation of invariants.
    from engtools.mohr import stress
    ms = stress.new_state()
    ms.update(mode='3D', s=[v/1e6 for v in s])
    summary = stress.results(ms)
    invariants = {name: summary[name]*1e6 for name in ('s1', 's2', 's3', 'mises', 'tmax', 'tresca')}
    finite(invariants.values())
    sy = state['material']['yield']
    safety = sy/invariants['mises'] if sy > 0 and invariants['mises'] > 0 else None
    if sy and invariants['mises'] > sy:
        notes.append('von Mises exceeds yield; elastic strains are extrapolated.')
    return {'stress': s, 'strain': e, 'properties': props, 'contributions': contributions,
            'invariants': invariants, 'safety': safety, 'notes': notes,
            'G': state['material']['E']/(2*(1+state['material']['nu'])),
            'thermal': state['material']['alpha']*state['dt']}


def to_case(state):
    out = copy(state)
    out['tool'] = TOOL
    return out


def from_case(record):
    if not isinstance(record, dict):
        raise ValueError('Invalid StressStrain case')
    out = new_state()
    for key in out:
        if key not in record:
            raise ValueError('Missing case field: ' + key)
        if isinstance(out[key], dict):
            if not isinstance(record[key], dict) or any(k not in record[key] for k in out[key]):
                raise ValueError('Invalid case field: ' + key)
            out[key] = {k: record[key][k] for k in out[key]}
        elif isinstance(out[key], list):
            if not isinstance(record[key], list) or len(record[key]) != 6:
                raise ValueError('Expected six tensor components')
            out[key] = list(record[key])
        else:
            out[key] = record[key]
    solve(out)
    return out


def stress_record(state, result):
    return {'kind': 'stress-state', 'version': 1, 'from': TOOL, 'units': 'Pa',
            'components': dict(zip(STRESSES, result['stress'])),
            'point': dict(state['point']) if state['mode'] == 'section' else None,
            'axes': 'x longitudinal; y right; z up' if state['mode'] == 'section' else 'Cartesian x y z'}


EXAMPLES = ('Shaft: bending + torsion', 'Rectangle: axial + bending + shear',
            'Tube: torsion', 'Uniaxial stress', 'Pure shear', 'Plane strain restraint', 'Free thermal expansion', 'Fully restrained heating')


def example(index):
    s = new_state()
    if index == 0:
        s['point'].update(y=0.0, z=.02)
    elif index == 1:
        s['shape'] = 'rectangle'
        s['point'].update(y=0.0, z=.015)
        s['loads'].update(T=0.0, Vy=1000.0, Vz=2000.0, My=500.0)
    elif index == 2:
        s['shape'] = 'tube'
        s['loads'].update(N=0.0, My=0.0, T=200.0)
    else:
        s['mode'] = 'constitutive'
        if index == 4:
            s['stress'] = [0.0, 0.0, 0.0, 50e6, 0.0, 0.0]
        elif index == 5:
            s['condition'], s['dt'] = 'plane-strain', 50.0
        elif index in (6, 7):
            s['dt'] = 50.0
            if index == 6:
                s['stress'] = [0.0]*6
            else:
                s['direction'], s['strain'] = 'strain', [0.0]*6
    return s
