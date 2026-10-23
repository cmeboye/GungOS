"""Centroidal properties of doubly symmetric sections, in SI units."""
from math import pi, isfinite

SHAPES = ('rectangle', 'box', 'circle', 'tube', 'i-section', 'custom')
NAMES = ('Rectangle', 'Hollow rectangle', 'Solid circle', 'Circular tube', 'I-section', 'Custom A / Iy / Iz')
DIMS = {'rectangle': ('b', 'h'), 'box': ('b', 'h', 't'), 'circle': ('d',),
        'tube': ('d', 'di'), 'i-section': ('b', 'h', 'tw', 'tf'), 'custom': ('A', 'Iy', 'Iz')}


def defaults():
    return {'b': .04, 'h': .06, 't': .003, 'd': .04, 'di': .02, 'tw': .004, 'tf': .006,
            'A': .0024, 'Iy': 7.2e-7, 'Iz': 3.2e-7}


def properties(shape, dims):
    if shape not in SHAPES:
        raise ValueError('Unknown section shape')
    for key in DIMS[shape]:
        value = dims[key]
        if type(value) not in (int, float) or not isfinite(value) or (value < 0 if key == 'di' else value <= 0):
            raise ValueError('Section sizes must be finite and positive')
    if shape == 'custom':
        A, Iy, Iz = dims['A'], dims['Iy'], dims['Iz']
    elif shape in ('circle', 'tube'):
        d, di = dims['d'], dims['di'] if shape == 'tube' else 0.0
        if di >= d:
            raise ValueError('Inner diameter must be below outer diameter')
        A = pi*(d-di)*(d+di)/4
        Iy = Iz = pi*(d-di)*(d+di)*(d*d+di*di)/64
    else:
        b, h = dims['b'], dims['h']
        if shape == 'rectangle':
            A, Iy, Iz = b*h, b*h**3/12, h*b**3/12
        elif shape == 'box':
            t = dims['t']
            if 2*t >= min(b, h):
                raise ValueError('Wall must be below half the width and height')
            bi, hi = b-2*t, h-2*t
            A, Iy, Iz = b*h-bi*hi, (b*h**3-bi*hi**3)/12, (h*b**3-hi*bi**3)/12
        else:
            tw, tf = dims['tw'], dims['tf']
            if tw > b or 2*tf >= h:
                raise ValueError('Web and flanges must fit inside the I-section')
            web = h-2*tf
            A = 2*b*tf+tw*web
            Iy = 2*(b*tf**3/12+b*tf*((h-tf)/2)**2)+tw*web**3/12
            Iz = (2*tf*b**3+web*tw**3)/12
    if any(not isfinite(v) or v <= 0 for v in (A, Iy, Iz)):
        raise ValueError('Section properties exceed the numeric range')
    return {'A': A, 'Iy': Iy, 'Iz': Iz}
