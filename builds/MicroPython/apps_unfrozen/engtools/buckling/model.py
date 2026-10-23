"""Two-axis Euler buckling and axial yield screening, SI internally."""
from math import pi, sqrt, isfinite
from engtools import sections, materials

TOOL = 'buckling'
# Ideal end conditions; fixed-pinned uses the customary rounded K = 0.7.
ENDS = (('Pinned - pinned', 1.0), ('Fixed - fixed', .5),
        ('Fixed - pinned (~0.7)', .7), ('Fixed - free', 2.0), ('Custom K', None))


def new_state():
    return {'length': 2.0, 'compression': 10000.0, 'shape': 'rectangle',
            'section': sections.defaults(), 'ends_y': 0, 'ends_z': 0,
            'Ky': 1.0, 'Kz': 1.0, 'material': materials.preset()}


def copy(state):
    out = dict(state)
    out['section'], out['material'] = dict(state['section']), dict(state['material'])
    return out


def factor(state, axis):
    index = state['ends_'+axis]
    if type(index) is not int or not 0 <= index < len(ENDS):
        raise ValueError('Unknown end condition')
    value = ENDS[index][1]
    return state['K'+axis] if value is None else value


def solve(state):
    materials.check(state['material'])
    L, P, E, strength = state['length'], state['compression'], state['material']['E'], state['material']['yield']
    for value in (L, P, state['Ky'], state['Kz']):
        if type(value) not in (int, float) or not isfinite(value):
            raise ValueError('Length, load and K must be finite numbers')
    if L <= 0:
        raise ValueError('Column length must be positive')
    if P < 0:
        raise ValueError('Compression is positive; use zero for no applied load')
    prop = sections.properties(state['shape'], state['section'])
    out = {'properties': prop, 'axes': {}, 'applied_stress': P/prop['A']}
    for axis in ('y', 'z'):
        K = factor(state, axis)
        if K <= 0:
            raise ValueError('Effective length factor K must be positive')
        Le = K*L
        r = sqrt(prop['I'+axis]/prop['A'])
        slenderness = Le/r
        # Stress form avoids intermediate E*I or L**2 overflow.
        critical_stress = E*(pi/slenderness)**2
        critical = critical_stress*prop['A']
        record = {'K': K, 'effective_length': Le, 'r': r, 'slenderness': slenderness,
                  'critical_stress': critical_stress, 'critical': critical,
                  'factor': critical/P if P > 0 else None}
        if any(not isfinite(v) or v <= 0 for v in record.values() if v is not None):
            raise ValueError('Buckling results exceed the numeric range')
        out['axes'][axis] = record
    y, z = out['axes']['y']['critical'], out['axes']['z']['critical']
    out['governing'] = 'y' if y <= z else 'z'
    out['equal_axes'] = abs(y-z) <= 1e-6*max(y, z)
    out['critical'] = min(y, z)
    out['factor'] = out['critical']/P if P > 0 else None
    out['yield_load'] = strength*prop['A'] if strength > 0 else None
    out['yield_factor'] = out['yield_load']/P if strength > 0 and P > 0 else None
    out['transition_slenderness'] = pi*sqrt(E/strength) if strength > 0 else None
    out['yield_first'] = strength > 0 and out['critical'] > out['yield_load']
    if not isfinite(out['applied_stress']) or any(v is not None and not isfinite(v) for v in (out['yield_load'], out['yield_factor'], out['transition_slenderness'])):
        raise ValueError('Yield results exceed the numeric range')
    out['notes'] = []
    if out['yield_first']:
        out['notes'].append('Yield precedes Euler; elastic critical load is not a capacity.')
    elif strength == 0:
        out['notes'].append('Yield check off; elastic-range validity is unchecked.')
    if P >= out['critical']:
        out['notes'].append('Applied load reaches or exceeds Euler critical load.')
    if strength and P >= out['yield_load']:
        out['notes'].append('Applied load reaches or exceeds axial yield load.')
    return out


def to_case(state):
    record = copy(state)
    record['tool'] = TOOL
    return record


def from_case(record):
    if not isinstance(record, dict):
        raise ValueError('Invalid Buckling case')
    state = new_state()
    for key in state:
        if key not in record:
            raise ValueError('Missing Buckling case field: '+key)
        if isinstance(state[key], dict):
            if not isinstance(record[key], dict) or any(k not in record[key] for k in state[key]):
                raise ValueError('Invalid Buckling case field: '+key)
            state[key] = {k: record[key][k] for k in state[key]}
        else:
            state[key] = record[key]
    solve(state)
    return state


def plot_spec(state, result):
    E, strength = state['material']['E'], state['material']['yield']
    lam = result['axes'][result['governing']]['slenderness']
    low, high = .5*lam, 2*lam
    points = []
    for i in range(97):
        x = low+(high-low)*i/96
        points.append((x, E*(pi/x)**2/1e6))
    # Leave room below the shared legend so the yield line stays visible.
    max_y = max(points[0][1], strength/1e6)*1.25
    series = [{'type': 'samples', 'name': 'Euler (elastic)', 'points': points, 'style': 'line'},
              {'type': 'samples', 'name': 'Current axis',
               'points': [(lam, result['critical']/result['properties']['A']/1e6)], 'style': 'scatter'}]
    if strength:
        series.append({'type': 'samples', 'name': 'Yield', 'points': [(low, strength/1e6), (high, strength/1e6)], 'style': 'line'})
    return {'title': 'Euler stress / slenderness', 'bounds': [low, high, 0, max_y], 'legend': True,
            'axes': {'x': {'label': 'Effective slenderness KL/r'}, 'y': {'label': 'Stress', 'unit': 'MPa'}},
            'series': series}


EXAMPLES = ('Slender rectangular column', 'Fixed-free cantilever', 'Short column: yield first',
            'Different restraints: y governs', 'Circular tube', 'I-section column', 'No applied load')


def example(index):
    state = new_state()
    if index == 1:
        state['ends_y'] = state['ends_z'] = 3
    elif index == 2:
        state['length'] = .25
    elif index == 3:
        state['ends_y'], state['ends_z'] = 3, 1
    elif index == 4:
        state['shape'] = 'tube'
    elif index == 5:
        state['shape'] = 'i-section'
        state['section'].update(b=.1, h=.2, tw=.006, tf=.01)
        state['length'], state['compression'] = 3.0, 50000.0
    elif index == 6:
        state['compression'] = 0.0
    return state
