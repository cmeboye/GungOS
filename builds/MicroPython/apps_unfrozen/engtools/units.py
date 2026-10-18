"""Display units and conversion to consistent internal SI values.

The engineering suites show one fixed set of engineering SI units. Models
store SI (m, N, N*m, N/m, Pa, m^4, rad); conversion happens only at the
display and input boundary. Labels are plain ASCII so every font draws them.
"""
from math import floor, log10

SCALE = {
    'm': 1.0, 'cm': 1e-2, 'mm': 1e-3,
    'N': 1.0, 'kN': 1e3,
    'Nm': 1.0, 'kNm': 1e3,
    'N/m': 1.0, 'kN/m': 1e3,
    'kNm/rad': 1e3,
    'Pa': 1.0, 'MPa': 1e6, 'GPa': 1e9,
    'm2': 1.0, 'cm2': 1e-4, 'mm2': 1e-6,
    'm3': 1.0, 'cm3': 1e-6,
    'm4': 1.0, 'cm4': 1e-8, 'mm4': 1e-12,
    'kg/m3': 1.0,
    'rad': 1.0, 'mrad': 1e-3,
    'kNm2': 1e3,
    '': 1.0, 'x': 1.0,
}


def to_si(value, unit):
    """Convert a displayed value to its internal SI value."""
    try:
        return value * SCALE[unit]
    except KeyError:
        raise ValueError('Unknown unit: ' + unit)


def from_si(value, unit):
    """Convert an internal SI value to a display unit."""
    try:
        return value / SCALE[unit]
    except KeyError:
        raise ValueError('Unknown unit: ' + unit)


def number(value, digits=4):
    """A short display string with about `digits` significant figures."""
    if value != value:
        return '--'
    size = abs(value)
    if size < 1e-12:
        return '0'
    if size >= 1e6 or size < 1e-3:
        return ('%.' + str(max(0, digits - 1)) + 'e') % value
    decimals = max(0, digits - 1 - int(floor(log10(size))))
    text = ('%.' + str(decimals) + 'f') % value
    if '.' in text:
        text = text.rstrip('0').rstrip('.')
    return '0' if text in ('-0', '') else text


def show(value, unit, digits=4):
    """Format an SI value in a display unit, with the unit label."""
    text = number(from_si(value, unit), digits)
    return text + ' ' + unit if unit else text
