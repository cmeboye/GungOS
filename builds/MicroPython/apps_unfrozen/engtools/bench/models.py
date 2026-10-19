"""Deterministic disposable benchmark models; never open or save user cases."""


def beam(count, frame=False, cases=1):
    from engtools.beamlab import model as bm
    if frame:
        joints = [(i * 4.0, y) for i in range(count + 1) for y in (0.0, 3.0)]
        members = [(2*i, 2*i+1) for i in range(count+1)]
        members += [(2*i+1, 2*i+3) for i in range(count)]
        m = bm.empty_model(joints, members)
        m['supports'] = [bm.support(i, 0.0, 'Fixed') for i in range(count+1)]
        loaded = list(range(count+1, len(members)))
    else:
        m = bm.empty_model([(float(i)*2, 0.0) for i in range(count+1)], [(i, i+1) for i in range(count)])
        m['supports'] = [bm.support(0, 0.0, 'Pin'), bm.support(count-1, 2.0, 'Roller')]
        loaded = range(count)
    m['cases'] = ['Case '+str(i+1) for i in range(cases)]
    m['combos'] = [{'name': 'Sum', 'factors': [1.0]*cases}]
    if cases > 1:
        m['combos'] = [{'name': 'Combo '+str(i+1), 'factors': [1.0 if j==i else .25 for j in range(cases)]} for i in range(cases)]
    for j, member in enumerate(loaded):
        length = bm.member_length(m, member)
        m['loads'].append(bm.dist_load(member, 0.0, length, 1000.0, case=j%cases))
        m['loads'].append(bm.point_load(member, length/2, 500.0, case=(j+1)%cases))
    return m


def cad(kind, count, quality):
    from engtools.picocad import model as dm
    m = dm.blank(); m['resolution'] = quality
    if kind == 'notch':
        m = dm.example(); m['resolution'] = quality; m['features'][1]['y'] = 15.0
    elif kind == 'bores':
        m['features'] = [dm.primitive()]
        for i in range(count):
            f = dm.primitive('Cylinder', 'Cut', i+2)
            f['a'] = 1.2; f['x'] = -15.0 + i * 5.0
            m['features'].append(f)
    elif kind == 'limit':
        m['features'] = [dm.primitive('Box', index=i+1) for i in range(9)]
    elif kind == 'invalid':
        m = dm.example(); m['features'][1]['a'] = 0.0
    elif kind == 'unsupported':
        m = dm.example(); m['features'][1]['x'] = 20.0; m['features'][1]['y'] = 15.0
    else:
        for i in range(count):
            f = dm.primitive(kind, index=i+1)
            if kind == 'Box': f['a'], f['b'], f['c'] = 8.0, 8.0, 8.0
            f['x'], f['y'] = (i%4)*16.0, (i//4)*16.0
            m['features'].append(f)
    return m


def cases(full):
    # kind, count, curve quality, build/release cycles. Parameters stay small;
    # only the currently running model is ever materialized.
    if not full:
        return (('beam',1,1,1), ('beam',4,1,1), ('frame',1,1,1),
                ('Cylinder',4,8,1), ('notch',1,8,1), ('bores',2,12,1),
                ('limit',9,8,1), ('invalid',1,8,1), ('unsupported',1,8,1))
    rows = [('beam',n,1,1) for n in (1,4,8,16)]
    rows += [('beam',16,6,1)]
    rows += [('frame',n,1,1) for n in (1,3,7)]
    # Explicit synthetic cases above the editor's 16-member / 48-item caps.
    # They test the real model/solver/render API, without changing those caps.
    rows += [('beam',n,1,1) for n in (32,64,128)]
    rows += [('frame',n,1,1) for n in (15,31)]
    rows += [('beam',8,1,5)]
    rows += [(shape,1,8,1) for shape in ('Box','Sphere','Cone')]
    rows += [('Cylinder',n,q,1) for q in (6,12,24) for n in (1,2,4,8)]
    rows += [('bores',n,24,1) for n in (2,4,7)]
    rows += [('notch',1,24,1), ('Cylinder',8,24,5)]
    rows += [('limit',9,8,1), ('invalid',1,8,1), ('unsupported',1,8,1)]
    return tuple(rows)
