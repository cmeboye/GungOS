"""Conversions, validation and versioned SI cases; independent of the UI."""
from math import isfinite
from .catalog import category, units

TOOL = 'unitconvert'


def shown(value):
    # Do not collapse very small values to zero (capacitance, electronvolts).
    return '0' if value == 0 else '%.7g' % value


def unit(key, symbol):
    for record in units(key):
        if record[0] == symbol:
            return record
    raise ValueError('Unknown unit in ' + category(key)[1])


def new_state(key='length'):
    choices = units(key)
    return {'category': key, 'from': choices[0][0], 'to': choices[1][0], 'value': 1.0}


def to_si(key, symbol, value):
    if not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError('Enter a finite number')
    u = unit(key, symbol)
    if key == 'fuel' and value <= 0:
        raise ValueError('Fuel consumption / economy must be positive')
    result = value * u[2] + u[3] if u[2] > 0 else -u[2] / value
    if not isfinite(result) or (value != 0 and result == 0 and not u[3]):
        raise ValueError('Value exceeds the numeric range')
    if key == 'temperature':
        if result < -0.0001:
            raise ValueError('Temperature is below absolute zero')
        result = max(0.0, result)
    return result


def from_si(key, symbol, value):
    u = unit(key, symbol)
    if u[2] < 0 and value <= 0:
        raise ValueError('Fuel consumption / economy must be positive')
    result = (value - u[3]) / u[2] if u[2] > 0 else -u[2] / value
    if not isfinite(result) or (value != 0 and result == 0 and not u[3]):
        raise ValueError('Value exceeds the numeric range')
    return result


def result(state):
    return from_si(state['category'], state['to'], to_si(state['category'], state['from'], state['value']))


def swap(state):
    value = result(state)
    state['from'], state['to'], state['value'] = state['to'], state['from'], value


def to_case(state):
    return {'tool': TOOL, 'kind': 'unit-conversion', 'category': state['category'],
            'from': state['from'], 'to': state['to'],
            'si': to_si(state['category'], state['from'], state['value'])}


def from_case(record):
    if not isinstance(record, dict):
        raise ValueError('Invalid conversion record')
    key = record.get('category')
    state = new_state(key)
    unit(key, record.get('from'))
    unit(key, record.get('to'))
    value = record.get('si')
    if not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError('Invalid saved SI value')
    if (key == 'temperature' and value < 0) or (key == 'fuel' and value <= 0):
        raise ValueError('Invalid saved SI value')
    state.update({'from': record['from'], 'to': record['to'],
                  'value': from_si(key, record['from'], value)})
    result(state)
    return state


def matches(text, query):
    return all(word in text.lower() for word in query.lower().split())
