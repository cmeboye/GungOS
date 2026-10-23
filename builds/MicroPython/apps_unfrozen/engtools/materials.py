"""Small editable isotropic material records, shared by engineering apps.

Presets are illustrative inputs, not certified material grades. SI inside.
The future Materialprop catalogue can produce the same records.
"""
from math import isfinite

PRESETS = (('Steel-like example', 200e9, .3, 12e-6, 250e6),
           ('Aluminium-like example', 70e9, .33, 23e-6, 200e6),
           ('Custom', 100e9, .25, 0.0, 0.0))


def preset(index=0):
    name, E, nu, alpha, strength = PRESETS[index]
    return {'name': name, 'E': E, 'nu': nu, 'alpha': alpha, 'yield': strength}


def check(record):
    if not isinstance(record, dict) or not isinstance(record.get('name'), str):
        raise ValueError('Invalid material record')
    for key in ('E', 'nu', 'alpha', 'yield'):
        if not isinstance(record.get(key), (int, float)) or not isfinite(record[key]):
            raise ValueError('Material properties must be finite')
    if record['E'] <= 0:
        raise ValueError('Young modulus must be positive')
    if not -1 < record['nu'] < .5:
        raise ValueError('Poisson ratio must be between -1 and 0.5')
    if record['yield'] < 0:
        raise ValueError('Yield strength must be zero or positive')
