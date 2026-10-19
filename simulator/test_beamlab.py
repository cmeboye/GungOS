"""Beam Lab: model checks, closed-form results, frames, load combinations, units and saved cases.

Run with the desktop MicroPython build, from the project root.
"""
import os, sys
from math import cos, sin, radians, pi
root = os.getcwd()
sys.path.insert(0, root + '/src/MicroPython')
sys.path.insert(0, root + '/simulator/hardware')
sys.path.insert(0, root + '/builds/MicroPython/apps_unfrozen')
from engtools.beamlab import model as bm
from engtools import units


def near(got, want, tol=1e-4):
    assert abs(got - want) <= tol * max(1.0, abs(want)), (got, want)


def simple(L=6.0, w=5e3):
    m = bm.template(0)
    m['joints'][1] = [L, 0.0]
    m['supports'] = [bm.support(0, 0.0, 'Pin'), bm.support(0, L, 'Roller')]
    m['loads'] = [bm.dist_load(0, 0.0, L, w)] if w else []
    return m


def stiffness(m, member=0):
    v = bm.section_values(m['sections'][m['members'][member]['section']])
    return v['E'] * v['I']


def balance(sol, view, tol=1e-5):
    fx = sum(r[1] for r in sol.reactions(view))
    fy = sum(r[2] for r in sol.reactions(view))
    ax, ay = sol.applied(view)
    near(fx, -ax, tol); near(fy, -ay, tol)


# Units: display <-> SI and short numbers.
near(units.to_si(12.5, 'kN'), 12500)
near(units.from_si(8.36e-5, 'cm4'), 8360)
near(units.to_si(3, 'mm'), 0.003)
assert units.number(12.345) == '12.35' and units.number(-0.5) == '-0.5' and units.number(0) == '0'
assert units.number(1234.5) == '1235' and units.number(2.0) == '2' and units.show(45e3, 'kNm') == '45 kNm'
assert units.number(1e-6).startswith('1.000e-06') and units.number(float('nan')) == '--'
try: units.to_si(1, 'furlong')
except ValueError: pass
else: raise AssertionError('Unknown unit accepted')
print('PASS: units')

# Sections: every shape, against independent formulas.
I, A, W, h = bm.properties('Rectangle', {'b': 0.1, 'h': 0.2})
near(I, 0.1 * 0.2 ** 3 / 12); near(A, 0.02); near(W, 0.1 * 0.2 ** 2 / 6)
I, A, W, h = bm.properties('Circle', {'d': 0.1})
near(I, pi * 1e-4 / 64); near(A, pi * 0.01 / 4); near(W, pi * 1e-3 / 32)
near(bm.properties('Tube', {'d': 0.1, 't': 0.01})[0], pi * (0.1 ** 4 - 0.08 ** 4) / 64)
# A web as wide as the flanges, or a full-width T, is a rectangle.
near(bm.properties('I-section', {'h': 0.3, 'b': 0.1, 'tw': 0.1, 'tf': 0.02})[0], 0.1 * 0.3 ** 3 / 12)
near(bm.properties('T-section', {'h': 0.3, 'b': 0.1, 'tw': 0.1, 'tf': 0.05})[0], 0.1 * 0.3 ** 3 / 12)
I, A, W, h = bm.properties('Hollow rect', {'h': 0.2, 'b': 0.1, 't': 0.01})
near(I, (0.1 * 0.2 ** 3 - 0.08 * 0.18 ** 3) / 12); near(A, 0.02 - 0.08 * 0.18)
# T-section: centroid 0.0628 m from the top for this one (parallel axes by hand).
I, A, W, h = bm.properties('T-section', {'h': 0.3, 'b': 0.2, 'tw': 0.02, 'tf': 0.03})
top = (0.2 * 0.03 * 0.015 + 0.02 * 0.27 * 0.165) / (0.006 + 0.0054)
near(bm.centroid_from_top('T-section', {'h': 0.3, 'b': 0.2, 'tw': 0.02, 'tf': 0.03}), top)
near(I, 0.2 * 0.03 ** 3 / 12 + 0.006 * (top - 0.015) ** 2 + 0.02 * 0.27 ** 3 / 12 + 0.0054 * (0.165 - top) ** 2)
near(W, I / (0.3 - top))
s = bm.new_section()
v = bm.section_values(s)
assert v['E'] == 210e9 and 7e-5 < v['I'] < 9e-5 and 4e-3 < v['A'] < 6e-3 and v['rho'] == 7850, v
for shape, dims in (('Tube', {'d': 0.1, 't': 0.06}), ('I-section', {'h': 0.1, 'b': 0.1, 'tw': 0.01, 'tf': 0.06}),
                    ('Rectangle', {'b': 0, 'h': 0.1}), ('Hollow rect', {'h': 0.1, 'b': 0.1, 't': 0.05}),
                    ('T-section', {'h': 0.1, 'b': 0.1, 'tw': 0.2, 'tf': 0.02})):
    try: bm.properties(shape, dims)
    except bm.ModelError: pass
    else: raise AssertionError('Impossible section accepted: ' + shape)
bm.set_shape(s, 'Direct')
near(s['I'], v['I']); near(s['A'], v['A']); near(s['W'], v['W'])
bm.set_shape(s, 'Rectangle')
assert set(s['dims']) == {'b', 'h'}
print('PASS: sections')

# Every template solves and stays in equilibrium.
for index, (name, _) in enumerate(bm.TEMPLATES):
    sol = bm.Solution(bm.template(index))
    for view in range(len(sol.view_names())):
        balance(sol, view)
    sol.free()
print('PASS: all templates solve and balance')

# Simply supported span, uniform load: textbook values.
L, w = 6.0, 5e3
m = simple(L, w)
EI = stiffness(m)
sol = bm.Solution(m)
r = sol.reactions(0)
near(r[0][2], w * L / 2); near(r[1][2], w * L / 2); near(r[0][1], 0)
V, M, T, Wd, N, U = sol.at(0, L / 2, 0)
near(M, w * L * L / 8); near(Wd, -5 * w * L ** 4 / (384 * EI)); near(V, 0, 1e-3); near(N, 0, 1e-3)
ext = sol.extremes(0, 0)
near(ext['M'][0], w * L * L / 8); near(ext['M'][1], L / 2, 1e-3)
near(ext['W'][2], -5 * w * L ** 4 / (384 * EI)); near(ext['V'][0], w * L / 2)
ratio, span = sol.deflection_ratio(0)
near(span, L); near(ratio, L / (5 * w * L ** 4 / (384 * EI)))
sigma, at, member = sol.stress(0, 0)
near(sigma, w * L * L / 8 / bm.section_values(m['sections'][0])['W'], 1e-3)
assert bm.is_straight_beam(m)
print('PASS: simply supported span')

# Point load off centre: exact peak under the load, shear jump either side.
m = simple(L, 0)
m['loads'] = [bm.point_load(0, 2.0, 12e3)]
sol = bm.Solution(m)
near(sol.extremes(0, 0)['M'][0], 12e3 * 2 * 4 / 6)
near(sol.at(0, 2.0, 0, -1)[0], 12e3 * 4 / 6); near(sol.at(0, 2.0, 0, 1)[0], -12e3 * 2 / 6)
print('PASS: point load and shear jump')

# Cantilever with a tip load and an applied moment.
m = bm.template(1)
m['loads'] = [bm.point_load(0, 3.0, 10e3), bm.moment_load(0, 3.0, 4e3)]
sol = bm.Solution(m)
(s0, fx, fy, mz), = sol.reactions(0)
near(fy, 10e3); near(mz, 10e3 * 3 - 4e3)
EI = stiffness(m)
near(sol.at(0, 3.0, 0)[3], -10e3 * 27 / (3 * EI) + 4e3 * 9 / (2 * EI))
print('PASS: cantilever')

# A global angled point force must give the same reactions, bending and
# axial/transverse displacements as its analytical components. Check all
# quadrants, cardinal axes, reversed magnitudes and a rotated member.
for beam_angle in (0,37,90):
    c,sine=cos(radians(beam_angle)),sin(radians(beam_angle))
    for angle in (0,45,90,135,180,225,270,315,-45,765):
        for magnitude in (10000,-10000):
            m=bm.template(1)
            bm.set_member(m,0,3,beam_angle)
            _,_,c,sine,_=bm.member_axis(m,0)
            m['loads']=[bm.point_load(0,3,magnitude,angle=angle)]
            sol=bm.Solution(m)
            axes={0:(1,0),90:(0,1),180:(-1,0),270:(0,-1)}
            dx,dy=axes.get(angle%360,(cos(radians(angle%360)),sin(radians(angle%360))))
            fx,fy=magnitude*dx,magnitude*dy
            support,rx,ry,mz=sol.reactions(0)[0]
            near(rx,-fx);near(ry,-fy);near(mz,-(3*c*fy-3*sine*fx))
            applied=sol.applied(0);near(applied[0],fx);near(applied[1],fy)
            values=bm.section_values(m['sections'][0])
            u=(fx*c+fy*sine)*3/(values['E']*values['A'])
            v=(-fx*sine+fy*c)*27/(3*values['E']*values['I'])
            ux,uy=sol.displacement(*m['joints'][1],0)
            near(ux*1000,(u*c-v*sine)*1000)
            near(uy*1000,(u*sine+v*c)*1000)
            balance(sol,0)
            sol.free()
# Axial displacement u along the member: P*x/(EA) for a tip force along a
# 37 deg cantilever, positive toward the member end; its peak is at the tip.
m=bm.template(1);bm.set_member(m,0,3,37)
m['loads']=[bm.point_load(0,3,10000,angle=37)]
sol=bm.Solution(m);EA=bm.section_values(m['sections'][0])['E']*bm.section_values(m['sections'][0])['A']
S,V,M,T,W,N,U,starts=sol.samples(0,0)
for i in range(0,len(S),17):near(U[i]*1e3,10000*S[i]/EA*1e3);near(N[i],10000)
near(sol.at(0,1.5,0)[5]*1e3,10000*1.5/EA*1e3)
hi,shi,lo,slo=sol.extremes(0,0)['U'];near(hi*1e3,10000*3/EA*1e3);near(shi,3.0)
sol.free()
print('PASS: axial displacement along a member and its peak')
m=bm.template(1);m['cases']=['A','B']
m['loads']=[bm.point_load(0,3,8000,case=0,angle=315),bm.point_load(0,1,3000,case=1,angle=135)]
m['combos']=[{'name':'ULS','factors':[1.35,1.5]}]
sol=bm.Solution(m)
for view in range(3):balance(sol,view)
near(sol.applied(2)[0],(1.35*8000-1.5*3000)*cos(pi/4))
near(sol.applied(2)[1],(-1.35*8000+1.5*3000)*sin(pi/4))
sol.free()
for invalid in (None,True,'45',float('nan'),float('inf'),-float('inf')):
    m=bm.template(1);m['loads'][0]['dir']='angle';m['loads'][0]['angle']=invalid
    try:bm.check(m)
    except bm.ModelError as exc:assert 'finite' in str(exc)
    else:raise AssertionError('Invalid point angle accepted')
m=bm.template(0);m['loads'][0]['dir']='angle';m['loads'][0]['angle']=45
try:bm.check(m)
except bm.ModelError as exc:assert 'direction' in str(exc)
else:raise AssertionError('Custom distributed direction accepted')
print('PASS: angled point forces: all quadrants, cardinal axes, rotated members, reactions, displacements, signs, combinations and validation')


# Two spans, uniform load: middle reaction 5wL/4 per span L, hogging wL^2/8.
m = bm.template(4)
sol = bm.Solution(m)
r = sol.reactions(0)
near(r[1][2], 5 * 5e3 * 5 / 4); near(sol.at(0, 5.0, 0)[1], -5e3 * 25 / 8)
print('PASS: two spans')

# Load cases and combinations: a combination is the factored sum.
m = simple(L, 5e3)
m['cases'] = ['Dead', 'Live']
m['loads'].append(bm.dist_load(0, 0.0, L, 3e3, case=1))
m['combos'] = [{'name': 'ULS', 'factors': [1.35, 1.5]}, {'name': 'Live only', 'factors': [0.0, 1.0]}]
sol = bm.Solution(m)
assert sol.view_names() == ['Dead', 'Live', 'Combo ULS', 'Combo Live only']
near(sol.at(0, 3.0, 2)[1], 1.35 * 5e3 * 36 / 8 + 1.5 * 3e3 * 36 / 8)
near(sol.at(0, 3.0, 3)[1], sol.at(0, 3.0, 1)[1])
balance(sol, 2)
S, V, M, T, Wd, N, U, starts = sol.samples(0, 2)
assert len(S) >= 240 and S[0] == 0 and abs(S[len(S) - 1] - L) < 1e-5
print('PASS: load cases and combinations')

# Hinge, spring support, settlement, trapezoid.
m = simple(10.0, 0)
m['supports'] = [bm.support(0, 0.0, 'Fixed'), bm.support(0, 10.0, 'Roller')]
m['hinges'] = [{'m': 0, 'x': 4.0}]
m['loads'] = [bm.dist_load(0, 2.0, 8.0, 2e3, 6e3)]
sol = bm.Solution(m)
near(sol.at(0, 4.0, 0)[1], 0, 1e-3)
balance(sol, 0)
m['supports'][1] = bm.support(0, 10.0, 'Spring')
m['supports'][1]['ky'] = 2e6
sol = bm.Solution(m)
near(sol.reactions(0)[1][2], -2e6 * sol.at(0, 10.0, 0)[3])
m = simple(6.0, 0)
m['supports'][1]['settle_y'] = -0.01  # 10 mm down
sol = bm.Solution(m)
near(sol.at(0, 6.0, 0)[3], -0.01)
print('PASS: hinge, spring, settlement and trapezoid')

# A section change splits the beam into two members on one line.
m = simple(6.0, 5e3)
m['joints'] = [[0, 0], [3.0, 0], [6.0, 0]]
m['members'] = [{'a': 0, 'b': 1, 'section': 0}, {'a': 1, 'b': 2, 'section': 1}]
m['sections'].append(bm.new_section('S2', m['sections'][0]))
m['sections'][1]['dims']['h'] = 0.5
m['supports'] = [bm.support(0, 0.0, 'Pin'), bm.support(1, 3.0, 'Roller')]
m['loads'] = [bm.dist_load(0, 0.0, 3.0, 5e3), bm.dist_load(1, 0.0, 3.0, 5e3)]
sol = bm.Solution(m)
assert sol.lines == [[0, 1]] and bm.is_straight_beam(m)
near(sol.at_line(0, 3.0, 0)[1], 5e3 * 36 / 8)
near(sol.extremes(0, 0)['M'][0], 5e3 * 36 / 8)
# The smaller section governs the stress at the joint where it starts.
m['sections'][1]['dims']['h'] = 0.2
m['loads'] = [bm.point_load(0, 3.0, 10e3)]
sol = bm.Solution(m)
sigma, at, member = sol.stress(0, 0)
near(sigma, 10e3 * 6 / 4 / bm.section_values(m['sections'][1])['W'])
near(at, 3.0); assert member == 1, member
sol.free()
print('PASS: section change as a second member on the same line')

# Frames: portal symmetry, sway, load directions and an inclined member.
m = bm.template(7)
m['loads'] = [bm.dist_load(1, 0.0, 6.0, 10e3)]
sol = bm.Solution(m)
r = sol.reactions(0)
near(r[0][2], 30e3); near(r[1][2], 30e3); near(r[0][1], -r[1][1]); near(r[0][3], -r[1][3])
near(sol.at(0, 2.0, 0)[4], -30e3)                  # column in compression
near(sol.at(1, 3.0, 0)[4], r[1][1])               # beam carries the feet's thrust
m = bm.template(7)
sol = bm.Solution(m)
balance(sol, 0)
near(sum(x[1] for x in sol.reactions(0)), -5e3)
ux, uy = sol.displacement(0.0, 4.0, 0)
assert ux > 0, 'Wind should sway the frame to the right'
assert len(sol.lines) == 3
# An inclined simply supported rafter: gravity, normal and horizontal loads.
m = bm.empty_model(((0, 0), (4.0, 3.0)), ((0, 1),))
m['supports'] = [bm.support(0, 0.0, 'Pin'), bm.support(0, 5.0, 'Roller')]
for direction in bm.DIRECTIONS:
    m['loads'] = [bm.dist_load(0, 0.0, 5.0, 2e3, direction=direction)]
    sol = bm.Solution(m)
    balance(sol, 0)
    ax, ay = sol.applied(0)
    near((ax * ax + ay * ay) ** 0.5, 10e3)
m['loads'] = [bm.dist_load(0, 0.0, 5.0, 2e3, direction='normal')]
sol = bm.Solution(m)
near(sol.extremes(0, 0)['M'][0], 2e3 * 25 / 8)  # like a 5 m beam under 2 kN/m
assert not bm.is_straight_beam(m)
print('PASS: frames: portal, sway, load directions and an inclined rafter')

# Self-weight adds rho*g*A along every member.
m = simple(6.0, 0)
m['selfweight'] = 0
sol = bm.Solution(m)
v = bm.section_values(m['sections'][0])
near(sol.applied(0)[1], -v['rho'] * bm.GRAVITY * v['A'] * 6.0)
balance(sol, 0)
print('PASS: self-weight')

# Saved beams from the first Beam Lab (schema 1) open as members.
old = {'tool': 'beams', 'name': 'old', 'length': 8.0, 'version': 1,
       'sections': [{'x': 0.0, 'material': 0, 'E': 210e9, 'shape': 'I-section',
                     'dims': {'h': 0.3, 'b': 0.15, 'tw': 0.0071, 'tf': 0.0107}, 'I': 8e-5},
                    {'x': 5.0, 'material': 2, 'E': 11e9, 'shape': 'Direct I', 'dims': {}, 'I': 2e-4}],
       'supports': [{'x': 0.0, 'kind': 'Pin', 'ky': 1e7, 'kr': 0.0, 'settle': 0.0, 'case': 0},
                    {'x': 8.0, 'kind': 'Roller', 'ky': 1e7, 'kr': 0.0, 'settle': 0.0, 'case': 0}],
       'hinges': [], 'loads': [{'kind': 'dist', 'x': 0.0, 'x2': 8.0, 'w1': 5e3, 'w2': 5e3, 'case': 0},
                               {'kind': 'point', 'x': 5.0, 'P': 10e3, 'case': 0}],
       'cases': ['Dead'], 'combos': [{'name': 'All x1.0', 'factors': [1.0]}]}
new = bm.upgrade(old)
assert new['schema'] == 3 and len(new['members']) == 2 and new['sections'][1]['shape'] == 'Direct'
assert len([l for l in new['loads'] if l['kind'] == 'dist']) == 2
sol = bm.Solution(new)
balance(sol, 0)
near(sol.applied(0)[1], -(5e3 * 8 + 10e3))
print('PASS: schema 1 beams upgrade to members')

# Problems are named and placed.
for change, words, where in (
        (lambda m: m['supports'].pop(), 'freely', None),
        (lambda m: m.update(supports=[]), 'Add a support', None),
        (lambda m: m['loads'].append(bm.point_load(0, 7.0)), 'off member 1', (6.0, 0.0)),
        (lambda m: m['loads'].append(bm.dist_load(0, 4.0, 3.0)), 'start < end', (4.0, 0.0)),
        (lambda m: m['supports'].append(bm.support(0, 0.0)), 'same point', (0.0, 0.0)),
        (lambda m: m['loads'].append(bm.point_load(0, 1.0, case=3)), 'missing load case', (1.0, 0.0))):
    m = simple()
    change(m)
    try: bm.Solution(m)
    except bm.ModelError as exc:
        assert words in str(exc), str(exc)
        assert where is None or exc.where == where, (exc.where, where)
    else: raise AssertionError('Bad model accepted: ' + words)
m = simple()
m['supports'][0]['kind'] = 'Roller'
try: bm.Solution(m)
except bm.ModelError as exc: assert 'slide sideways' in str(exc), str(exc)
else: raise AssertionError('Sliding beam accepted')
print('PASS: problems are named and placed')

# Saved cases round-trip through the SD card.
import sim_runtime
from time import ticks_ms
sd = '/private/tmp/picoware-beamlab-test-' + str(ticks_ms())
sim_runtime.configure(root, sd, root + '/builds/MicroPython/apps_unfrozen', 1, 'picocalc-pico2w',
                      0, True, False, False, False, '', _network_mode='offline', _audio_mode='silent')
from picoware.system.storage import Storage
from engtools import cases
storage = Storage()
m = bm.template(8)
path = cases.save_case(storage, 'gable frame', m)
assert path.endswith('gable-frame.json') and cases.list_cases(storage) == ['gable-frame']
back = cases.load_case(storage, 'gable-frame', 'beams')
assert back['version'] == cases.CASE_VERSION and len(back['members']) == 4
sol = bm.Solution(back)
balance(sol, 0)
try: cases.load_case(storage, 'gable-frame', 'circuits')
except ValueError: pass
else: raise AssertionError('Wrong tool accepted')
for bad in ('', '  ', '***'):
    try: cases.clean_name(bad)
    except ValueError: pass
    else: raise AssertionError('Empty name accepted')
X, V, M, T, Wd, N, U, starts = sol.samples(0, 0)
csv = cases.export_csv(storage, cases.free_path(storage, cases.EXPORT_DIRECTORY, 'beam', 'csv'),
                       ('x_m', 'V_N'), ((X[i], V[i]) for i in range(len(X))))
text = storage.read(csv)
assert text.startswith('x_m,V_N\n0,') and text.count('\n') == len(X) + 1
print('PASS: saved cases and CSV export')

print('PASS: Beam numerical and persistence regressions complete')
