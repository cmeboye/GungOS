"""Beam Lab editing: the cursor along lines, the items at a point, their fields
and every change to the model.

The cursor is (line, s): a straight run of members and the distance along
it. An item reference is (kind, obj): ('joint', j), ('member', m),
('support', s), ('hinge', h) or ('load', l), where obj is a dict inside the
model (or an index for joints and members). Values move between display
units and SI here; no drawing.
"""
from engtools import units
from . import model as bm
from . import structure as st

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
    axes = [(o, bm.member_axis(model, m)) for m, o in zip(run, offsets)]
    for X, Y in model['joints']:
        for o, (X0, Y0, c, s_, L) in axes:
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
            points = [st.item_point(model, item)]
            if item.get('kind') == 'dist':
                points.append(st.item_point(model, item, 'x2'))
            if any(same_point(p, here) for p in points):
                out.append((kind, item))
    return out


def same(a, b):
    if a is None or b is None or a[0] != b[0]:
        return False
    return a[1] == b[1] if a[0] in ('joint', 'member') else a[1] is b[1]


def joint_label(model, j):
    X, Y = model['joints'][j]
    return 'J%d (%s,%s)' % (j + 1, units.number(X), units.number(Y))


def title(model,ref):
    kind,obj=ref
    if kind=='joint':
        return joint_label(model,obj)+' '+st.TYPE_NAMES[st.TYPES.index(model['joint_types'][obj])]
    if kind=='member':
        m=model['members'][obj]
        return 'L%d  J%d > J%d  %s'%(obj+1,m['a']+1,m['b']+1,model['sections'][m['section']]['name'])
    if kind=='hinge':return 'Member hinge'
    name='Support '+obj['kind'] if kind=='support' else LOAD_TITLES[obj['kind']]
    return name+(' / J%d'%(obj['node']+1) if 'node' in obj else '')


# A field is (id, label, kind, unit, editable); kind 'num' or 'choice'.
def fields(model, ref):
    kind,obj=ref
    if kind=='joint':
        return [('X','X','num','m',True),('Y','Y','num','m',True),('type','Type','choice','',True)]
    if kind=='member':
        return [('a','Start','choice','',True),('b','End','choice','',True),('section','Section','choice','',True)]
    if kind=='hinge':return [('x','Position','num','m',True)]
    rows=[]
    if 'node' in obj:
        rows.append(('node','From node','choice','',True))
        connected=st.attached(model,obj['node'])
        if len(connected)!=1:rows.append(('along','Along member','choice','',bool(connected)))
    locked=obj.get('at_node') and len(st.attached(model,obj['node']))==1 if 'node' in obj else False
    if kind=='support':
        rows += [('x','Position','num','m',not locked),('kind','Type','choice','',True)]
        flags=bm.SUPPORT_FLAGS.get(obj['kind'],'')
        rows += [('settle_x','Settlement X','num','mm','x' in flags),('settle_y','Settlement Y','num','mm','y' in flags)]
        if obj['settle_x'] or obj['settle_y']:
            rows.append(('case','Settle case','choice','',True))
        if obj['kind']=='Spring':rows += [(key,label,'num',unit,True) for key,label,unit in
                (('kx','Horizontal k','kN/m'),('ky','Vertical k','kN/m'),('kr','Rotation k','kNm/rad'))]
        return rows
    if obj['kind']=='dist':
        rows += [('x','Start','num','m',True),('x2','End','num','m',True),
                 ('w1','w start','num','kN/m',True),('w2','w end','num','kN/m',True)]
    else:
        rows.append(('x','Offset','num','m',True))
        rows.append(('P','Force','num','kN',True) if obj['kind']=='point' else ('M','Moment (ccw +)','num','kNm',True))
    if obj['kind']!='moment':
        rows.append(('dir','Acts','choice','',True))
        if obj['kind']=='point':rows.append(('angle','Angle (0 right, 90 up)','num','deg',True))
    rows.append(('case','Load case','choice','',True))
    return rows


def get(model, ref, field):
    kind,obj=ref
    if kind=='joint':return model['joints'][obj][0 if field=='X' else 1]
    if field in ('x','x2'):
        return obj.get('offset' if field=='x' else 'offset2',obj[field]) if 'node' in obj else along(model,obj,field)
    if kind=='load' and obj['kind']=='point' and field=='angle':return bm.load_angle(model,obj)
    if field in ('w1','w2') and 'node' in obj and obj['m']>=0 and model['members'][obj['m']]['b']==obj['node']:
        return obj['w2' if field=='w1' else 'w1']
    return obj[field]


def choices(model, ref, field):
    kind,obj=ref
    if field in ('a','b','node'):
        return [joint_label(model,j) for j in range(len(model['joints']))]
    if field=='type':return st.TYPE_NAMES
    if field=='along':return ['L%d'%(i+1) for i in st.attached(model,obj['node'])] or ['None - connect node']
    if field=='section':return [s['name'] for s in model['sections']]+[NEW_SECTION]
    if field=='kind':return list(bm.SUPPORTS)
    if field=='dir':return list(bm.POINT_DIRECTION_TITLES if obj['kind']=='point' else bm.DIRECTION_TITLES)
    return list(model['cases'])


def choice_index(model,ref,field):
    kind,obj=ref
    if field in ('a','b','section'):return model['members'][obj][field]
    if field=='type':return st.TYPES.index(model['joint_types'][obj])
    if field=='node':return obj['node']
    if field=='along':
        connected=st.attached(model,obj['node'])
        return connected.index(obj['m']) if obj['m'] in connected else 0
    if field=='kind':return bm.SUPPORTS.index(obj['kind'])
    if field=='dir':return (bm.POINT_DIRECTIONS if obj['kind']=='point' else bm.DIRECTIONS).index(obj.get('dir','down'))
    return obj[field]


def text(model, ref, field_row):
    field, label, kind, unit, editable = field_row
    if kind == 'choice':
        index = choice_index(model, ref, field)
        if field in ('a', 'b', 'node'):  # one label, not the whole node list
            return joint_label(model, index)
        return choices(model, ref, field)[index]
    try:
        value = get(model, ref, field)
        if unit == 'deg':
            return units.number(value) + ' deg'
        return units.show(value, unit)
    except ValueError:
        return '--'


def set_choice(model,ref,field,index):
    kind,obj=ref
    if field in ('a','b'):
        model['members'][obj][field]=index
    elif field=='type':model['joint_types'][obj]=st.TYPES[index]
    elif field=='node':
        node=index;choices=st.attached(model,node)
        member=next((m for m in choices if model['members'][m]['a']==node),choices[0] if choices else -1)
        obj['node'],obj['m'],obj['offset'],obj['at_node']=node,member,0.0,kind!='load'
        if 'offset2' in obj:obj['offset2']=st.axis(model,member,node)[2] if member>=0 else 0.0
    elif field=='along':
        obj['m']=st.attached(model,obj['node'])[index];obj['offset']=0.0
        if 'offset2' in obj:obj['offset2']=st.axis(model,obj['m'],obj['node'])[2]
    elif field=='section':
        if index==len(model['sections']):model['sections'].append(bm.new_section(bm.section_name(model),model['sections'][model['members'][obj]['section']]))
        model['members'][obj]['section']=index
    elif field=='kind':
        obj['kind']=bm.SUPPORTS[index]
        flags=bm.SUPPORT_FLAGS[obj['kind']]
        if 'x' not in flags:obj['settle_x']=0.0
        if 'y' not in flags:obj['settle_y']=0.0
    elif field=='dir':
        direction=(bm.POINT_DIRECTIONS if obj['kind']=='point' else bm.DIRECTIONS)[index]
        if direction=='angle':obj['angle']=bm.load_angle(model,obj)
        obj['dir']=direction
    else:obj['case']=index
    st.sync(model)


def set_number(model,ref,field,unit,shown):
    kind,obj=ref;value=shown if unit=='deg' else units.to_si(shown,unit)
    if not bm.isfinite(value):raise ValueError('Enter a finite number')
    if kind=='joint':
        if abs(value)>1000:raise ValueError('Nodes stay within 1000 m of the origin')
        model['joints'][obj][0 if field=='X' else 1]=value
    elif field in ('x','x2') and 'node' in obj:
        obj['offset' if field=='x' else 'offset2']=value
        if kind=='load':obj['at_node']=False
    elif field=='angle':obj['angle'],obj['dir']=value%360,'angle'
    elif field in ('kx','ky','kr'):
        if value<0:raise ValueError('Stiffness cannot be negative')
        obj[field]=value
    elif field in ('w1','w2'):
        target=field
        if 'node' in obj and obj['m']>=0 and model['members'][obj['m']]['b']==obj['node']:target='w2' if field=='w1' else 'w1'
        if field=='w1' and obj['w1']==obj['w2']:obj['w1']=obj['w2']=value
        else:obj[target]=value
    else:obj[field]=value
    st.sync(model)


# ---------------------------------------------------------------- splitting

def _split(model, m, x, node=None):
    """Split member m at x; returns the new member's index (the far part)."""
    L = bm.member_length(model, m)
    if not 1e-6 < x < L - 1e-6:
        raise ValueError('Move the cursor inside a member to split it')
    if len(model['members']) >= bm.MAX_MEMBERS:
        raise ValueError('Up to %d members' % bm.MAX_MEMBERS)
    X, Y = bm.point(model, m, x)
    if node is None:
        model['joints'].append([bm.snap(X), bm.snap(Y)])
        model.setdefault('joint_types',['rigid']*(len(model['joints'])-1)).append('rigid')
        joint=len(model['joints'])-1
    else:joint=node
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


def split(model,m,x,node=None):
    result=_split(model,m,x,node)
    for group in ('supports','hinges','loads'):
        for obj in model[group]:
            # An orphan stays at its own node until the user reconnects it.
            if 'node' not in obj or not 0<=obj['m']<len(model['members']):continue
            edge=model['members'][obj['m']];j=obj['node']
            if j not in (edge['a'],edge['b']):j=edge['a']
            lock=obj.get('at_node',False)
            st.bind(model,obj,j,obj['m'],lock)
    return result


def delete(model,ref):
    kind,obj=ref
    if kind=='joint':
        if st.attached(model,obj):raise ValueError('Remove connected members before deleting this node')
        if any(t.get('node')==obj for group in ('supports','hinges','loads') for t in model[group]):raise ValueError("Remove this node's supports/loads first")
        del model['joints'][obj];del model['joint_types'][obj]
        for m in model['members']:
            for k in ('a','b'):m[k]-=m[k]>obj
        for group in ('supports','hinges','loads'):
            for t in model[group]:
                if 'node' in t:t['node']-=t['node']>obj
        return
    if kind=='member':
        del model['members'][obj]
        for group in ('supports','hinges','loads'):
            kept=[]
            for t in model[group]:
                if t['m']==obj:
                    if 'node' not in t or abs(t.get('offset',0))>st.EPS or t.get('kind')=='dist':continue
                    t['m']=-1
                elif t['m']>obj:t['m']-=1
                kept.append(t)
            model[group]=kept
        st.sync(model);return
    group={'support':'supports','hinge':'hinges','load':'loads'}[kind]
    for i,t in enumerate(model[group]):
        if t is obj:del model[group][i];return
    raise ValueError('Item already removed')


# ---------------------------------------------------------------- sections

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
    used += sum(1 for s in model['supports'] if s['case'] == index and (s['settle_x'] or s['settle_y']))
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
