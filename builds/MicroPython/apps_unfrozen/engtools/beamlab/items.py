"""Beam Lab editing: the cursor along lines, the items at a point, their fields
and every change to the model.

The cursor is (line, s): a straight run of members and the distance along
it. An item reference is (kind, obj): ('joint', j), ('member', m),
('support', s), ('hinge', h) or ('load', l), where obj is a dict inside the
model (or an index for joints and members). Values move between display
units and SI here; no drawing.
"""
from math import cos, sin, radians
from engtools import units
from . import model as bm

LOAD_TITLES = {'point': 'Point load', 'moment': 'Moment', 'dist': 'Distributed'}
NEW_SECTION = '+ New section'


# ---------------------------------------------------------------- the cursor

def line_of(model, m, runs=None):
    """(line index, offset of member m along it)."""
    runs = runs or bm.lines(model)
    for i, run in enumerate(runs):
        if m in run:
            offsets, total = bm.line_offsets(model, run)
            return i, offsets[run.index(m)]
    return 0, 0.0


def along(model, item, field='x'):
    """An item's position along its line."""
    return line_of(model, item['m'])[1] + item[field]


def locate(model, line, s, runs=None):
    """(member, x) at s along a line; at a joint, the member that starts there."""
    run = (runs or bm.lines(model))[line]
    offsets, total = bm.line_offsets(model, run)
    s = min(max(s, 0.0), total)
    for m, o in zip(run, offsets):
        if s < o + bm.member_length(model, m) - 1e-9:
            return m, max(s - o, 0.0)
    return run[-1], bm.member_length(model, run[-1])


def stops(model, line, runs=None):
    """Positions along a line where the cursor stops."""
    run = (runs or bm.lines(model))[line]
    offsets, total = bm.line_offsets(model, run)
    at = dict((m, o) for m, o in zip(run, offsets))
    points = {0: 0.0, bm.key(total): total}
    for o, m in zip(offsets, run):
        points[bm.key(o)] = o
    for group in ('supports', 'hinges', 'loads'):
        for item in model[group]:
            if item['m'] in at:
                for field in ('x', 'x2'):
                    if field in item:
                        s = at[item['m']] + item[field]
                        points[bm.key(s)] = s
    # Points where another member meets this line.
    for j, (X, Y) in enumerate(model['joints']):
        for m, o in zip(run, offsets):
            X0, Y0, c, s_, L = bm.member_axis(model, m)
            t = (X - X0) * c + (Y - Y0) * s_
            if -1e-9 <= t <= L + 1e-9 and abs(-(X - X0) * s_ + (Y - Y0) * c) < 1e-6:
                points[bm.key(o + t)] = o + t
    return [points[k] for k in sorted(points)]


def cursor_point(model, line, s, runs=None):
    m, x = locate(model, line, s, runs)
    return bm.point(model, m, x)


def same_point(a, b):
    return bm.pkey(*a) == bm.pkey(*b)


def items_at(model, line, s, runs=None):
    """References at the cursor's point, in display order."""
    runs = runs or bm.lines(model)
    here = cursor_point(model, line, s, runs)
    current, x = locate(model, line, s, runs)
    straight = bm.is_straight_beam(model)
    out = []
    if not straight:
        for j, joint in enumerate(model['joints']):
            if same_point(joint, here):
                out.append(('joint', j))
    single = straight and len(model['members']) == 1
    for m, member in enumerate(model['members']):
        start, end = model['joints'][member['a']], model['joints'][member['b']]
        if single:
            show = same_point(start, here)  # the beam's own row sits at its start
        else:
            show = m == current or same_point(start, here) or same_point(end, here)
        if show:
            out.append(('member', m))
    for group, kind in (('supports', 'support'), ('hinges', 'hinge'), ('loads', 'load')):
        for item in model[group]:
            points = [bm.point(model, item['m'], item['x'])]
            if item.get('kind') == 'dist':
                points.append(bm.point(model, item['m'], item['x2']))
            if any(same_point(p, here) for p in points):
                out.append((kind, item))
    return out


def same(a, b):
    if a is None or b is None or a[0] != b[0]:
        return False
    return a[1] == b[1] if a[0] in ('joint', 'member') else a[1] is b[1]


def case_name(model, index):
    cases = model['cases']
    return cases[index] if 0 <= index < len(cases) else '?'


def title(model, ref):
    kind, obj = ref
    if kind == 'joint':
        X, Y = model['joints'][obj]
        return 'Joint  (%s, %s) m' % (units.number(X), units.number(Y))
    if kind == 'member':
        L = bm.member_length(model, obj)
        section = model['sections'][model['members'][obj]['section']]['name']
        if bm.is_straight_beam(model) and len(model['members']) == 1:
            return 'Beam  L = %s  %s' % (units.show(L, 'm'), section)
        return 'Member %d  %s  %s' % (obj + 1, units.show(L, 'm'), section)
    if kind == 'support':
        return 'Support  ' + obj['kind']
    if kind == 'hinge':
        return 'Hinge'
    text = LOAD_TITLES[obj['kind']]
    if obj['kind'] == 'point':
        text += '  ' + units.show(obj['P'], 'kN')
    elif obj['kind'] == 'moment':
        text += '  ' + units.show(obj['M'], 'kNm')
    else:
        text += '  ' + units.show(obj['w1'], 'kN/m')
        if obj['w2'] != obj['w1']:
            text += ' to ' + units.number(units.from_si(obj['w2'], 'kN/m'))
    if obj['kind'] != 'moment' and obj.get('dir', 'down') != 'down':
        text += ' ' + obj['dir']
    if len(model['cases']) > 1:
        text += '  ' + case_name(model, obj['case'])
    return text


# A field is (id, label, kind, unit, editable); kind 'num', 'choice' or 'action'.
def fields(model, ref):
    kind, obj = ref
    straight = bm.is_straight_beam(model)
    if kind == 'joint':
        return [('X', 'X', 'num', 'm', True), ('Y', 'Y', 'num', 'm', True)]
    if kind == 'member':
        rows = [('length', 'Length', 'num', 'm', True)]
        if not straight:
            rows.append(('angle', 'Angle (ccw from right)', 'num', 'deg', True))
        rows += [('section', 'Section', 'choice', '', True), ('edit', 'Edit section', 'action', '', True)]
        return rows
    if kind == 'support':
        rows = [('x', 'Position', 'num', 'm', True), ('kind', 'Type', 'choice', '', True)]
        if obj['kind'] == 'Spring':
            if not straight:
                rows.append(('kx', 'Horizontal k', 'num', 'kN/m', True))
            rows += [('ky', 'Vertical k', 'num', 'kN/m', True), ('kr', 'Rotation k', 'num', 'kNm/rad', True)]
        elif 'y' in bm.SUPPORT_FLAGS[obj['kind']]:
            rows.append(('settle', 'Settlement', 'num', 'mm', True))
            if obj['settle']:
                rows.append(('case', 'Settle case', 'choice', '', True))
        return rows
    if kind == 'hinge':
        return [('x', 'Position', 'num', 'm', True)]
    if obj['kind'] == 'point':
        rows = [('x', 'Position', 'num', 'm', True), ('P', 'Force', 'num', 'kN', True)]
    elif obj['kind'] == 'moment':
        rows = [('x', 'Position', 'num', 'm', True), ('M', 'Moment (ccw +)', 'num', 'kNm', True)]
    else:
        rows = [('x', 'Start', 'num', 'm', True), ('x2', 'End', 'num', 'm', True),
                ('w1', 'w start', 'num', 'kN/m', True), ('w2', 'w end', 'num', 'kN/m', True)]
    if obj['kind'] != 'moment':
        rows.append(('dir', 'Acts', 'choice', '', True))
    rows.append(('case', 'Load case', 'choice', '', True))
    return rows


def get(model, ref, field):
    """The SI value of a numeric field (degrees for angles)."""
    kind, obj = ref
    if kind == 'joint':
        return model['joints'][obj][0 if field == 'X' else 1]
    if kind == 'member':
        return bm.member_length(model, obj) if field == 'length' else bm.member_angle(model, obj)
    if field in ('x', 'x2'):
        return along(model, obj, field)
    return obj[field]


def choices(model, ref, field):
    kind, obj = ref
    if field == 'section':
        return [s['name'] for s in model['sections']] + [NEW_SECTION]
    if field == 'kind':
        return list(bm.SUPPORTS)
    if field == 'dir':
        return list(bm.DIRECTION_TITLES)
    return list(model['cases'])


def choice_index(model, ref, field):
    kind, obj = ref
    if field == 'section':
        return model['members'][obj]['section']
    if field == 'kind':
        return bm.SUPPORTS.index(obj['kind'])
    if field == 'dir':
        return bm.DIRECTIONS.index(obj.get('dir', 'down'))
    return obj[field]


def text(model, ref, field_row):
    field, label, kind, unit, editable = field_row
    if kind == 'action':
        return 'ENTER'
    if kind == 'choice':
        return choices(model, ref, field)[choice_index(model, ref, field)]
    try:
        value = get(model, ref, field)
        if unit == 'deg':
            return units.number(value) + ' deg'
        return units.show(value, unit)
    except ValueError:
        return '--'


def set_choice(model, ref, field, index):
    kind, obj = ref
    if field == 'section':
        if index == len(model['sections']):
            current = model['sections'][model['members'][obj]['section']]
            model['sections'].append(bm.new_section(bm.section_name(model), current))
        model['members'][obj]['section'] = index
        prune_sections(model)
    elif field == 'kind':
        obj['kind'] = bm.SUPPORTS[index]
    elif field == 'dir':
        obj['dir'] = bm.DIRECTIONS[index]
    else:
        obj['case'] = index


def prune_sections(model):
    """Drop sections no member uses, keeping indices consistent."""
    used = sorted(set(member['section'] for member in model['members']))
    if len(used) == len(model['sections']):
        return
    remap = dict((old, new) for new, old in enumerate(used))
    model['sections'] = [model['sections'][i] for i in used]
    for member in model['members']:
        member['section'] = remap[member['section']]


def _geometry_change(model, change):
    """Apply a change to the joints; items keep their place at member ends
    and must still fit their members, or nothing changes."""
    before = [list(j) for j in model['joints']]
    lengths = [bm.member_length(model, m) for m in range(len(model['members']))]
    change()
    for m in range(len(model['members'])):
        if bm.member_length(model, m) < 1e-6:
            model['joints'] = before
            raise ValueError('Member %d would have no length' % (m + 1))
    moved = []
    for group in ('supports', 'hinges', 'loads'):
        for item in model[group]:
            old, new = lengths[item['m']], bm.member_length(model, item['m'])
            for field in ('x', 'x2'):
                if field not in item:
                    continue
                if abs(item[field] - old) < 1e-9:
                    moved.append((item, field, item[field]))
                    item[field] = new
                elif item[field] > new + 1e-9:
                    model['joints'] = before
                    for i, f, v in moved:
                        i[f] = v
                    raise ValueError('Items lie beyond the new end of member %d: move them first' % (item['m'] + 1))


def set_number(model, ref, field, unit, shown):
    """Apply a typed value (display units); raise ValueError without changing anything."""
    kind, obj = ref
    value = shown if unit == 'deg' else units.to_si(shown, unit)
    if kind == 'joint':
        if not abs(value) <= 1000:
            raise ValueError('Joints stay within 1000 m of the origin')
        index = 0 if field == 'X' else 1

        def move():
            model['joints'][obj][index] = value
        _geometry_change(model, move)
        return
    if kind == 'member':
        length, angle = bm.member_length(model, obj), bm.member_angle(model, obj)
        if field == 'length':
            if not 0 < value <= 1000:
                raise ValueError('Length must be above 0 and at most 1000 m')
            length = value
        else:
            angle = value
        _geometry_change(model, lambda: bm.set_member(model, obj, length, angle))
        return
    if field in ('x', 'x2'):
        runs = bm.lines(model)
        line, offset = line_of(model, obj['m'], runs)
        total = bm.line_offsets(model, runs[line])[1]
        if not -1e-9 <= value <= total + 1e-9:
            raise ValueError('Position must be from 0 to %s m' % units.number(total))
        value = min(max(value, 0.0), total)
        if kind == 'load' and obj['kind'] == 'dist':
            m, x = obj['m'], value - offset
            L = bm.member_length(model, m)
            if not -1e-9 <= x <= L + 1e-9:
                raise ValueError('A distributed load stays on one member: add another for the next one')
            x = min(max(x, 0.0), L)
            start, end = (x, obj['x2']) if field == 'x' else (obj['x'], x)
            if not start < end - 1e-9:
                raise ValueError('Start must be before the end')
            obj[field] = x
            return
        m, x = locate(model, line, value, runs)
        where = bm.point(model, m, x)
        if kind == 'support' and any(s is not obj and same_point(bm.point(model, s['m'], s['x']), where)
                                     for s in model['supports']):
            raise ValueError('A support is already there')
        if kind == 'hinge' and any(h is not obj and h['m'] == m and bm.key(h['x']) == bm.key(x) for h in model['hinges']):
            raise ValueError('A hinge is already there')
        obj['m'], obj['x'] = m, x
        return
    if field in ('kx', 'ky', 'kr'):
        if value < 0:
            raise ValueError('Stiffness cannot be negative')
        obj[field] = value
        return
    if field == 'w1' and obj['w1'] == obj['w2']:
        obj['w2'] = value  # a uniform load stays uniform
    obj[field] = value


# ---------------------------------------------------------------- inserting

INSERT_KEYS = {'s': 'support', 'p': 'point', 'm': 'moment', 'w': 'dist', 'h': 'hinge',
               'c': 'split', 'b': 'member'}


def split(model, m, x):
    """Split member m at x; returns the new member's index (the far part)."""
    L = bm.member_length(model, m)
    if not 1e-6 < x < L - 1e-6:
        raise ValueError('Move the cursor inside a member to split it')
    if len(model['members']) >= bm.MAX_MEMBERS:
        raise ValueError('Up to %d members' % bm.MAX_MEMBERS)
    X, Y = bm.point(model, m, x)
    model['joints'].append([bm.snap(X), bm.snap(Y)])
    joint = len(model['joints']) - 1
    member = model['members'][m]
    new = {'a': joint, 'b': member['b'], 'section': member['section']}
    member['b'] = joint
    model['members'].append(new)
    n = len(model['members']) - 1
    for group in ('supports', 'hinges', 'loads'):
        extra = []
        for item in model[group]:
            if item['m'] != m:
                continue
            if item.get('kind') == 'dist':
                if item['x'] < x - 1e-9 and item['x2'] > x + 1e-9:  # crosses the cut: two loads
                    w = item['w1'] + (item['w2'] - item['w1']) * (x - item['x']) / (item['x2'] - item['x'])
                    far = bm.dist_load(n, 0.0, item['x2'] - x, w, item['w2'], item['case'], item['dir'])
                    item['x2'], item['w2'] = x, w
                    extra.append(far)
                elif item['x'] >= x - 1e-9:
                    item['m'] = n
                    item['x'] = max(item['x'] - x, 0.0)
                    item['x2'] -= x
            elif item['x'] > x + 1e-9:
                item['m'] = n
                item['x'] -= x
                if 'x2' in item:
                    item['x2'] -= x
        model[group].extend(extra)
    return n


def _free_angle(model, joint):
    """A direction for a new member from a joint that no member uses yet."""
    used = []
    for m, member in enumerate(model['members']):
        a = bm.member_angle(model, m)
        if member['a'] == joint:
            used.append(a)
        elif member['b'] == joint:
            used.append(a + 180)
    for angle in (90, 0, -90, 180, 45, 135, -45, -135):
        if all(abs(((angle - u) + 180) % 360 - 180) > 1 for u in used):
            return angle
    return 30


def add_member(model, m, x):
    """A new 3 m member from the point at x on member m; returns its index."""
    if len(model['members']) >= bm.MAX_MEMBERS:
        raise ValueError('Up to %d members' % bm.MAX_MEMBERS)
    L = bm.member_length(model, m)
    if x < 1e-9:
        joint = model['members'][m]['a']
    elif x > L - 1e-9:
        joint = model['members'][m]['b']
    else:
        split(model, m, x)
        joint = model['members'][m]['b']
    X, Y = model['joints'][joint]
    angle = _free_angle(model, joint)
    model['joints'].append([bm.snap(X + 3.0 * cos(radians(angle))), bm.snap(Y + 3.0 * sin(radians(angle)))])
    model['members'].append({'a': joint, 'b': len(model['joints']) - 1, 'section': model['members'][m]['section']})
    return len(model['members']) - 1


def insert(model, what, line, s):
    """Add an item at or near the cursor and return (reference, field to edit)."""
    if bm.item_count(model) >= bm.MAX_ITEMS:
        raise ValueError('Item limit reached (%d)' % bm.MAX_ITEMS)
    runs = bm.lines(model)
    m, x = locate(model, line, s, runs)
    L = bm.member_length(model, m)
    if what == 'split':
        n = split(model, m, x)
        current = model['sections'][model['members'][n]['section']]
        model['sections'].append(bm.new_section(bm.section_name(model), current))
        model['members'][n]['section'] = len(model['sections']) - 1
        return ('member', n), 'section'
    if what == 'member':
        return ('member', add_member(model, m, x)), 'length'
    if what == 'support':
        here = bm.point(model, m, x)
        if any(same_point(bm.point(model, t['m'], t['x']), here) for t in model['supports']):
            raise ValueError('A support is already here: move the cursor first')
        obj = bm.support(m, x, 'Roller' if model['supports'] else 'Pin')
        model['supports'].append(obj)
        return ('support', obj), 'x'
    if what == 'hinge':
        if any(h['m'] == m and bm.key(h['x']) == bm.key(x) for h in model['hinges']):
            raise ValueError('A hinge is already here')
        if (x < 1e-9 or x > L - 1e-9) and len(runs[line]) == 1 and not any(
                same_point(bm.point(model, m, x), model['joints'][o['a']]) or
                same_point(bm.point(model, m, x), model['joints'][o['b']])
                for i, o in enumerate(model['members']) if i != m):
            raise ValueError('A hinge at a free end does nothing: move the cursor inside')
        obj = {'m': m, 'x': x}
        model['hinges'].append(obj)
        return ('hinge', obj), 'x'
    if what == 'dist':
        if x < L - 1e-9:
            later = [p - (s - x) for p in stops(model, line, runs) if p > s + 1e-9]
            end = min([p for p in later if p <= L + 1e-9] or [L])
            obj = bm.dist_load(m, x, end)
        else:
            earlier = [p - (s - x) for p in stops(model, line, runs) if p < s - 1e-9]
            obj = bm.dist_load(m, max([p for p in earlier if p >= -1e-9] or [0.0]), x)
        model['loads'].append(obj)
        return ('load', obj), 'x'
    obj = bm.point_load(m, x) if what == 'point' else bm.moment_load(m, x)
    model['loads'].append(obj)
    return ('load', obj), 'x'


def delete(model, ref):
    kind, obj = ref
    if kind == 'joint':
        raise ValueError('Joints go with their members: remove a member instead')
    if kind == 'member':
        if len(model['members']) == 1:
            raise ValueError('The last member stays; try F6 New beam')
        for group in ('supports', 'hinges', 'loads'):
            model[group] = [i for i in model[group] if i['m'] != obj]
            for item in model[group]:
                if item['m'] > obj:
                    item['m'] -= 1
        del model['members'][obj]
        used = sorted(set(j for member in model['members'] for j in (member['a'], member['b'])))
        remap = dict((old, new) for new, old in enumerate(used))
        model['joints'] = [model['joints'][j] for j in used]
        for member in model['members']:
            member['a'], member['b'] = remap[member['a']], remap[member['b']]
        prune_sections(model)
        return
    group = {'support': 'supports', 'hinge': 'hinges', 'load': 'loads'}[kind]
    items = model[group]
    for i, item in enumerate(items):
        if item is obj:
            del items[i]
            return
    raise ValueError('Item already removed')


# ---------------------------------------------------------------- sections

SECTION_FIELDS = {'h': 'mm', 'b': 'mm', 'tw': 'mm', 'tf': 'mm', 'd': 'mm', 't': 'mm'}


def section_fields(section):
    """Rows for the section editor: (id, label, kind, unit, editable)."""
    custom = bm.MATERIALS[section['material']][1] is None
    rows = [('name', 'Name', 'text', '', True), ('material', 'Material', 'choice', '', True),
            ('E', 'E', 'num', 'GPa', custom), ('rho', 'Density', 'num', 'kg/m3', custom),
            ('shape', 'Shape', 'choice', '', True)]
    for name in bm.SHAPE_DIMS[section['shape']]:
        rows.append(('dim:' + name, bm.DIM_LABELS[name], 'num', 'mm', True))
    if section['shape'] == 'Direct':
        rows += [('I', 'I', 'num', 'cm4', True), ('A', 'Area A', 'num', 'cm2', True), ('W', 'Modulus W', 'num', 'cm3', True)]
    return rows


def section_get(section, field):
    if field.startswith('dim:'):
        return section['dims'][field[4:]]
    if field in ('E', 'rho'):
        material = bm.MATERIALS[section['material']]
        return material[1 if field == 'E' else 2] if material[1] is not None else section[field]
    return section[field]


def section_text(section, row):
    field, label, kind, unit, editable = row
    if kind == 'text':
        return section['name']
    if field == 'material':
        return bm.MATERIALS[section['material']][0]
    if field == 'shape':
        return section['shape']
    return units.show(section_get(section, field), unit)


def section_choices(field):
    return [m[0] for m in bm.MATERIALS] if field == 'material' else list(bm.SHAPES)


def section_choice(section, field, index):
    if field == 'material':
        if bm.MATERIALS[index][1] is None:
            current = bm.MATERIALS[section['material']]
            if current[1] is not None:
                section['E'], section['rho'] = current[1], current[2]
        section['material'] = index
    else:
        bm.set_shape(section, bm.SHAPES[index])


def section_number(section, field, unit, shown):
    value = units.to_si(shown, unit)
    if not value > 0 and field != 'rho':
        raise ValueError('Must be above zero')
    if field == 'rho' and value < 0:
        raise ValueError('Density cannot be negative')
    if field.startswith('dim:'):
        dims = dict(section['dims'])
        dims[field[4:]] = value
        bm.properties(section['shape'], dims)
        section['dims'] = dims
        return
    section[field] = value


def rename_section(model, section, name):
    name = name.strip()[:8]
    if not name:
        raise ValueError('Type a name')
    if any(s is not section and s['name'] == name for s in model['sections']):
        raise ValueError('Another section has that name')
    section['name'] = name


# ---------------------------------------------------------------- cases

def add_case(model, name):
    if len(model['cases']) >= bm.MAX_CASES:
        raise ValueError('Up to %d load cases' % bm.MAX_CASES)
    model['cases'].append(name)
    for combo in model['combos']:
        combo['factors'].append(1.0 if combo['name'] == 'All x1.0' else 0.0)


def remove_case(model, index):
    if len(model['cases']) == 1:
        raise ValueError('Keep at least one load case')
    used = sum(1 for load in model['loads'] if load['case'] == index)
    used += sum(1 for s in model['supports'] if s['settle'] and s['case'] == index)
    used += 1 if model.get('selfweight') == index else 0
    if used:
        raise ValueError('%d item(s) use this case: move or delete them first' % used)
    del model['cases'][index]
    for combo in model['combos']:
        del combo['factors'][index]
    for item in model['loads'] + model['supports']:
        if item['case'] > index:
            item['case'] -= 1
    if model.get('selfweight') is not None and model['selfweight'] > index:
        model['selfweight'] -= 1


def add_combo(model):
    if len(model['combos']) >= bm.MAX_COMBOS:
        raise ValueError('Up to %d combinations' % bm.MAX_COMBOS)
    combo = {'name': 'C%d' % (len(model['combos']) + 1), 'factors': [1.0] * len(model['cases'])}
    model['combos'].append(combo)
    return combo


def combo_text(model, combo):
    parts = ['%s %s' % (units.number(f, 3), name) for f, name in zip(combo['factors'], model['cases']) if f]
    return ' + '.join(parts) or 'No loads'


# ---------------------------------------------------------------- undo

def copy(value):
    if isinstance(value, dict):
        return dict((k, copy(v)) for k, v in value.items())
    if isinstance(value, list):
        return [copy(v) for v in value]
    return value
