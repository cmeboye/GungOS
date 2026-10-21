"""Heat transfer 2D inputs: the property rows of each tab, what a row key
refers to, and the rules for changing a value.

A row is (kind, label, value text, editable, key, unit). Keys name an entry
of the state: 'W', 'side:1:h', 'patch:0:P'. A heading's key names the side
or patch it introduces, so the preview can highlight it.
"""
from engtools.units import number
from . import model as tm

TABS = ('Plate', 'Sides', 'Sources', 'Solve')
PLATE, SIDES, SOURCES, SOLVE = range(4)
CHOICES = ('mode', 'mat', 'res', 'kind')


def target(state, key):
    """The dictionary and entry a row key refers to."""
    if key.startswith('side:') or key.startswith('patch:'):
        group, index, name = key.split(':')
        return state['sides' if group == 'side' else 'patches'][int(index)], name
    return state, key


def get(state, key):
    owner, name = target(state, key)
    return owner[name]


def is_choice(key):
    return key is not None and key.split(':')[-1] in CHOICES


def rows(state, tab):
    s = state
    transient = s['mode'] == 'transient'
    out = []

    def head(title, key=None):
        out.append(('head', title, '', False, key, ''))

    def field(label, value, key=None, unit=''):
        out.append(('field', label, value, key is not None, key, unit))

    def quantity(label, key, unit, digits=5):
        field(label, number(get(s, key), digits) + ' ' + unit, key, unit)

    if tab == PLATE:
        quantity('Width', 'W', 'mm')
        quantity('Height', 'H', 'mm')
        quantity('Depth', 'depth', 'mm')
        field('Material', tm.MATERIALS[s['mat']][0], 'mat', 'choice')
        quantity('Conductivity k', 'k', 'W/mK')
        quantity('Density', 'rho', 'kg/m3')
        quantity('Specific heat', 'cp', 'J/kgK')
    elif tab == SIDES:
        for index, side in enumerate(s['sides']):
            prefix = 'side:%d:' % index
            head(tm.SIDES[index] + ' side', prefix[:-1])
            field('Condition', tm.KINDS[side['kind']], prefix + 'kind', 'choice')
            if side['kind'] == tm.TEMPERATURE:
                quantity('Temperature', prefix + 'T', 'C')
            elif side['kind'] == tm.CONVECTION:
                quantity('Ambient', prefix + 'T', 'C')
                quantity('Coefficient h', prefix + 'h', 'W/m2K')
            elif side['kind'] == tm.FLUX:
                quantity('Heat flux in', prefix + 'q', 'W/m2')
    elif tab == SOURCES:
        quantity('Whole plate', 'gen', 'W/m3')
        if not s['patches']:
            head('No heat patches')
        for index in range(len(s['patches'])):
            prefix = 'patch:%d:' % index
            head('Patch %d' % (index + 1), prefix[:-1])
            quantity('Power', prefix + 'P', 'W')
            quantity('Left x', prefix + 'x', 'mm')
            quantity('Bottom y', prefix + 'y', 'mm')
            quantity('Width', prefix + 'w', 'mm')
            quantity('Height', prefix + 'h', 'mm')
    else:
        field('Mode', 'Transient' if transient else 'Steady', 'mode', 'choice')
        if transient:
            quantity('End time', 'tend', 's')
            quantity('Initial temperature', 'T0', 'C')
        field('Grid', tm.RESOLUTION_NAMES[s['res']], 'res', 'choice')
        nx, ny = tm.grid_size(s)
        field('Cells', '%d x %d' % (nx, ny))
        field('Cell size', '%s x %s mm' % (number(s['W'] / nx, 3), number(s['H'] / ny, 3)))
        if transient:
            alpha = tm.diffusivity(s)
            longest = max(s['W'], s['H']) / 1000
            field('Diffusivity', number(alpha, 3) + ' m2/s')
            field('Diffusion time', number(longest * longest / alpha, 3) + ' s')
    return out


def choices(state, key):
    """(title, options, index, apply) for a choice row."""
    owner, name = target(state, key)
    if name == 'mode':
        return 'Mode', ('Steady', 'Transient'), 0 if state['mode'] == 'steady' else 1, \
            lambda i: state.update(mode=('steady', 'transient')[i])
    if name == 'mat':
        return 'Material', tuple(m[0] for m in tm.MATERIALS), state['mat'], lambda i: set_material(state, i)
    if name == 'res':
        return 'Grid', tm.RESOLUTION_NAMES, state['res'], lambda i: state.update(res=i)
    return (tm.SIDES[int(key.split(':')[1])] + ' side', tm.KINDS, owner['kind'],
            lambda i: owner.update(kind=i))


def set_material(state, index):
    state['mat'] = index
    if index != tm.CUSTOM:
        _, state['k'], state['rho'], state['cp'] = tm.MATERIALS[index]


def set_value(state, key, value):
    """Check a typed value against its entry and store it; ValueError says why not."""
    owner, name = target(state, key)
    patch = key.startswith('patch:')
    if name in ('W', 'H', 'depth'):
        if not 0.1 <= value <= 10000:
            raise ValueError('Keep sizes between 0.1 and 10000 mm')
    elif patch and name in ('x', 'y'):
        if value < 0:
            raise ValueError('The patch must lie inside the plate')
    elif patch and name in ('w', 'h'):
        if value <= 0:
            raise ValueError('Must be positive')
    elif name in ('k', 'rho', 'cp', 'h', 'tend'):
        if not 0 < value <= 1e9:
            raise ValueError('Must be positive')
    elif name in ('T', 'T0'):
        if not -273.15 <= value <= 10000:
            raise ValueError('Keep temperatures between -273 and 10000 C')
    elif abs(value) > 1e12:
        raise ValueError('Too large')
    owner[name] = value
    if name in ('k', 'rho', 'cp') and not patch:
        state['mat'] = tm.CUSTOM


def selected(key):
    """('side' or 'patch', index) for a row key, else None."""
    if key and (key.startswith('side:') or key.startswith('patch:')):
        parts = key.split(':')
        return parts[0], int(parts[1])
    return None
