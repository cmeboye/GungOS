"""Section Properties first pass. All stored and calculated values are SI.

Origin: bottom-left corner of the outer bounding box. y right, z up.
Iy = integral (z-cz)^2 dA; Iz = integral (y-cy)^2 dA.
All templates have a vertical symmetry axis, so Iyz is zero.
"""
from math import sqrt, pi, isfinite
from engtools import sections, materials

TOOL = 'sectionprops'
SHAPES = ('rectangle', 'box', 'circle', 'tube', 'i-section', 'tee')
NAMES = ('Rectangle', 'Hollow rectangle', 'Solid circle', 'Circular tube', 'I-section', 'T-section')
DIMS = {shape: sections.DIMS[shape] for shape in SHAPES if shape != 'tee'}
DIMS['tee'] = ('b', 'h', 'tw', 'tf')
BEAM_SHAPES = {'rectangle': 'Rectangle', 'box': 'Hollow rect', 'circle': 'Circle',
               'tube': 'Tube', 'i-section': 'I-section', 'tee': 'T-section'}
EXPORTS = (('A', 'm2'), ('cy', 'm'), ('cz', 'm'), ('Iy', 'm4'), ('Iz', 'm4'), ('Iyz', 'm4'),
           ('Ip', 'm4'), ('Wy_top', 'm3'), ('Wy_bottom', 'm3'), ('Wz_right', 'm3'), ('Wz_left', 'm3'),
           ('ry', 'm'), ('rz', 'm'), ('I1', 'm4'), ('I2', 'm4'), ('theta', 'rad'),
           ('mass_per_length', 'kg/m'), ('EIy', 'N*m2'), ('EIz', 'N*m2'), ('G', 'Pa'))


def material(index=0):
    record = materials.preset(index)
    record['rho'] = (7850.0, 2700.0, 1000.0)[index]
    return record


def new_state():
    return {'name': 'Section', 'shape': 'rectangle', 'dims': sections.defaults(), 'material': material()}


def copy(state):
    out = dict(state)
    out['dims'], out['material'] = dict(state['dims']), dict(state['material'])
    return out


def geometry(state):
    shape, d = state['shape'], state['dims']
    if shape not in SHAPES:
        raise ValueError('Unknown section shape')
    for key in DIMS[shape]:
        v = d[key]
        if type(v) not in (int, float) or not isfinite(v) or (v < 0 if key == 'di' else v <= 0):
            raise ValueError('Section dimensions must be finite and positive')
    b, h = (d['d'], d['d']) if shape in ('circle', 'tube') else (d['b'], d['h'])
    cy, cz = b/2, h/2
    if shape == 'tee':
        tw, tf = d['tw'], d['tf']
        if tw > b or tf >= h:
            raise ValueError('Web and flange must fit inside the T-section')
        web = h-tf
        Af, Aw = b*tf, tw*web
        A = Af+Aw
        zf, zw = h-tf/2, web/2
        cz = (Af*zf+Aw*zw)/A
        Iy = b*tf**3/12+Af*(zf-cz)**2+tw*web**3/12+Aw*(zw-cz)**2
        Iz = (tf*b**3+web*tw**3)/12
    else:
        p = sections.properties(shape, d)
        A, Iy, Iz = p['A'], p['Iy'], p['Iz']
    out = {'A': A, 'cy': cy, 'cz': cz, 'Iy': Iy, 'Iz': Iz, 'Iyz': 0.0,
           'Ip': Iy+Iz, 'Wy_top': Iy/(h-cz), 'Wy_bottom': Iy/cz,
           'Wz_right': Iz/(b-cy), 'Wz_left': Iz/cy, 'ry': sqrt(Iy/A), 'rz': sqrt(Iz/A),
           'I1': max(Iy, Iz), 'I2': min(Iy, Iz), 'theta': 0.0 if Iy >= Iz else pi/2,
           'width': b, 'height': h}
    if any(not isfinite(v) or (v <= 0 and key not in ('Iyz', 'theta')) for key, v in out.items()):
        raise ValueError('Section properties exceed the numeric range')
    out['equal_axes'] = abs(Iy-Iz) <= 1e-6*max(Iy, Iz)
    out['J'] = out['Ip'] if shape in ('circle', 'tube') else None
    return out


def solve(state):
    if not isinstance(state['name'], str) or not state['name'].strip() or len(state['name']) > 24 or any(ord(c) < 32 or ord(c) > 126 for c in state['name']):
        raise ValueError('Name needs 1-24 printable characters')
    materials.check(state['material'])
    mat = state['material']
    if type(mat.get('rho')) not in (int, float) or not isfinite(mat['rho']) or mat['rho'] < 0:
        raise ValueError('Density must be zero or positive')
    out = geometry(state)
    out.update(mass_per_length=mat['rho']*out['A'], EIy=mat['E']*out['Iy'], EIz=mat['E']*out['Iz'],
               G=mat['E']/(2*(1+mat['nu'])))
    if any(not isfinite(out[k]) for k in ('mass_per_length', 'EIy', 'EIz', 'G')):
        raise ValueError('Material results exceed the numeric range')
    return out


def preview_record(state, draft=False):
    d = dict(state['dims'])
    if state['shape'] == 'tube':
        d['t'] = (d['d']-d['di'])/2
    return {'name': 'Draft' if draft else state['name'], 'shape': BEAM_SHAPES[state['shape']], 'dims': d}


def to_case(state):
    out = copy(state)
    out.update(tool=TOOL, kind='section-properties-case')
    return out


def from_case(record):
    if not isinstance(record, dict):
        raise ValueError('Invalid Section Properties case')
    state = new_state()
    for key in state:
        if key not in record:
            raise ValueError('Missing section case field: '+key)
        if isinstance(state[key], dict):
            if not isinstance(record[key], dict) or any(k not in record[key] for k in state[key]):
                raise ValueError('Invalid section case field: '+key)
            state[key] = {k: record[key][k] for k in state[key]}
        else:
            state[key] = record[key]
    solve(state)
    return state


def report(state):
    return {'kind': 'section-properties', 'version': 1, 'from': TOOL,
            'inputs': copy(state), 'results': solve(state),
            'units': 'SI', 'origin': 'outer bounding box bottom-left; y right, z up',
            'note': 'Standalone report; cross-app section exchange is not implemented.'}


EXAMPLES = ('Rectangle 40 x 60', 'Hollow rectangular section', 'Solid circular bar',
            'Circular tube', 'I-section', 'T-section: offset centroid')


def example(index):
    state = new_state()
    state['shape'] = SHAPES[index]
    state['name'] = ('Rectangle', 'Box', 'Round bar', 'Tube', 'I section', 'T section')[index]
    if index in (4, 5):
        state['dims'].update(b=.1, h=.15, tw=.008, tf=.012)
    return state
