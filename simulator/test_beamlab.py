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
m['supports'][1]['settle'] = 0.01
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
assert new['schema'] == 2 and len(new['members']) == 2 and new['sections'][1]['shape'] == 'Direct'
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

# ------------------------------------------------------------------ the app
from picoware.system.view_manager import ViewManager
from picoware.system.view import View
from picoware.system.input import Input
from picoware.system import buttons as k
Input.button = property(lambda self: self._last_button)
import PicoLAB as lab
from engtools.beamlab import app as beam_app
from engtools.beamlab import items as bi
shots = '/private/tmp/picoware-beamlab-'
vm = ViewManager()
vm.add(View('parent', lambda vm: None, lambda vm: True, lambda vm: None)); vm.switch_to('parent')
vm.add(View('lab', lab.run, lab.start, lab.stop)); vm.switch_to('lab')


def key(button):
    vm.input_manager._last_button = button
    vm.run()


def text(value):
    for char in value:
        key(vm.input_manager._key_to_button(ord(char)))


def shot(name):
    sim_runtime.lcd_screenshot(shots + name + '.bmp')


def esc():
    key(vm.input_manager._key_esc)


def ui():
    # PicoLAB unloads Beam view when it closes: always ask the live module.
    return sys.modules['engtools.beamlab.app']._active


def pick(index):
    """Choose a row in an open popup list."""
    assert a.popup is not None
    a.popup[2] = index
    key(k.BUTTON_CENTER)


lab._enter('structural');lab._selected = 0
key(k.BUTTON_CENTER)
a = ui()
assert a.page == 'start' and a.model is None
shot('start')
key(k.BUTTON_CENTER)                                   # simply supported template
assert a.page == 'model' and a.solution is not None and a.problem is None
shot('model')
assert a.s == 0 and a.model_tab == 0 and a.sel[0][0] == 'member'
key(k.BUTTON_RIGHT)
assert a.model_tab == 1 and a.sel[0][0] == 'support'
key(k.BUTTON_DOWN)
assert a.s == 6.0 and a.sel[0][1] is a.model['supports'][1]
key(k.BUTTON_UP)
assert a.s == 0 and a.sel[0][1] is a.model['supports'][0]
# Add a point load: P inserts it, typing sets its position.
text('p')
assert a.sel[1] == 'x' and len(a.model['loads']) == 2
text('2'); key(k.BUTTON_CENTER)
load = a.model['loads'][1]
assert load['kind'] == 'point' and load['x'] == 2.0 and a.s == 2.0
key(k.BUTTON_DOWN)
assert a.sel[1] == 'P'
text('12*2'); key(k.BUTTON_CENTER)
assert load['P'] == 24e3 and a.problem is None
shot('model-point')
balance(a.solution, a.view)
# A bad value keeps the editor open with a message; ESC cancels it.
text('2/0'); key(k.BUTTON_CENTER)
assert a.edit is not None and a.error, a.message
esc()
assert a.edit is None and load['P'] == 24e3
# Backspace on a value edits it; only a heading row removes the item.
key(k.BUTTON_BACKSPACE)
assert a.edit is not None and a.edit.text == '2' and len(a.model['loads']) == 2
text('5'); key(k.BUTTON_CENTER)
assert load['P'] == 25e3
key(k.BUTTON_BACKSPACE); key(k.BUTTON_BACKSPACE); text('24'); key(k.BUTTON_CENTER)
assert load['P'] == 24e3
# Direction and load case are lists.
key(k.BUTTON_DOWN)
assert a.sel[1] == 'dir'
key(k.BUTTON_CENTER); pick(2)
assert load['dir'] == 'right' and a.problem is None
balance(a.solution, a.view)
key(k.BUTTON_CENTER); pick(0)
key(k.BUTTON_DOWN)
assert a.sel[1] == 'angle'
key(k.BUTTON_DOWN)
assert a.sel[1] == 'case'
key(k.BUTTON_CENTER)
assert a.popup is not None
esc()
# Removing the left support makes a mechanism, shown on the beam; Z undoes.
cursor = (a.line,a.s)
key(k.BUTTON_LEFT)
assert (a.line,a.s) == cursor and a.sel[0][0] == 'support'
key(k.BUTTON_BACKSPACE)
assert a.problem is not None and a.solution is None
shot('model-problem')
text('z')
assert a.problem is None and len(a.model['supports']) == 2
# The section editor: from the beam's own row, change material, shape and depth.
a.focus(('member', 0), 'edit')
key(k.BUTTON_CENTER)
assert a.page == 'section' and a.section is a.model['sections'][0]
shot('section-i')
rows = a.section_rows()
a.section_row = [r[0] for r in rows].index('material')
key(k.BUTTON_CENTER); pick(2)
assert a.section['material'] == 2 and a.problem is None
a.section_row = [r[0] for r in a.section_rows()].index('shape')
key(k.BUTTON_CENTER); pick(bm.SHAPES.index('Rectangle'))
assert a.section['shape'] == 'Rectangle'
a.section_row = [r[0] for r in a.section_rows()].index('dim:h')
text('400'); key(k.BUTTON_CENTER)
near(a.section['dims']['h'], 0.4)
shot('section-rect')
a.section_row = [r[0] for r in a.section_rows()].index('shape')
key(k.BUTTON_CENTER); pick(bm.SHAPES.index('T-section'))
a.section_row = [r[0] for r in a.section_rows()].index('dim:tf')
shot('section-t')
a.section_row = [r[0] for r in a.section_rows()].index('shape')
key(k.BUTTON_CENTER); pick(bm.SHAPES.index('Tube'))
a.section_row = [r[0] for r in a.section_rows()].index('dim:t')
shot('section-tube')
text('500'); key(k.BUTTON_CENTER)                    # a wall thicker than the radius
assert a.edit is not None and a.error and 'half the diameter' in a.message, a.message
esc()
a.section_row = [r[0] for r in a.section_rows()].index('name')
key(k.BUTTON_CENTER)
for _ in range(3): key(k.BUTTON_BACKSPACE)
text('CHS'); key(k.BUTTON_CENTER)
assert a.section['name'] == 'CHS' and a.prompt is None
esc()
assert a.page == 'model' and a.problem is None
# Every insert key works: split (section change) and a new member too.
a.select_point(0, 2.0)
for c in 'smwh':
    text(c)
    assert a.sel is not None, c
for c in 'cb':
    a.select_point(0, 2.0 if c == 'c' else 1.0)
    text(c)
    assert a.sel is not None and a.problem is None, (c, a.problem)
assert len(a.model['members']) == 3 and len(a.model['sections']) == 2 and len(a.model['hinges']) == 1
assert not bm.is_straight_beam(a.model)
shot('model-inserted')
for _ in range(6):
    text('z')
assert len(a.model['hinges']) == 0 and len(a.model['members']) == 1 and bm.is_straight_beam(a.model)
# Diagrams: move, jump to peaks, pin a point, toggle slope.
key(k.BUTTON_F4)
assert a.page == 'diagrams'
shot('diagrams')
key(k.BUTTON_TAB)
assert a.tab == 0 and 'max moment' in a.note
s_peak = a.ds
key(k.BUTTON_CENTER)
assert a.pins == [(0, s_peak)]
key(k.BUTTON_RIGHT); assert a.ds > s_peak
key(k.BUTTON_DOWN); assert any(abs(a.ds - p) < 1e-9 for p in bi.stops(a.model, 0))
text('d'); assert a.third == 'T'
shot('diagrams-slope')
text('d'); assert a.third == 'U' and len(a.cache) == 3
shot('diagrams-axial')
text('d'); assert a.third == 'W'
# Load cases and a combination.
key(k.BUTTON_F3)
assert a.page == 'options'
a.menu_index = beam_app.OPTIONS.index('Load cases'); key(k.BUTTON_CENTER)
assert a.page == 'cases'
a.menu_index = 1; key(k.BUTTON_CENTER)               # + Add load case, then name it
assert a.prompt is not None
for _ in range(6): key(k.BUTTON_BACKSPACE)
text('Live'); key(k.BUTTON_CENTER)
assert a.model['cases'] == ['Dead', 'Live'] and a.model['combos'][0]['factors'] == [1.0, 1.0]
assert a.solution.view_names()[a.view] == 'Combo All x1.0', 'Adding a case changed the view'
esc()
a.menu_index = beam_app.OPTIONS.index('Combinations'); key(k.BUTTON_CENTER)
a.menu_index = 1; key(k.BUTTON_CENTER)               # + Add combination
assert a.page == 'combo'
shot('combo')
key(k.BUTTON_DOWN)
text('1.35'); key(k.BUTTON_CENTER)
key(k.BUTTON_DOWN)
text('1.5'); key(k.BUTTON_CENTER)
assert a.model['combos'][1]['factors'] == [1.35, 1.5]
esc(); esc()
assert a.page == 'options'
a.menu_index = beam_app.OPTIONS.index('Self-weight'); key(k.BUTTON_CENTER)
assert a.model['selfweight'] == 0 and a.problem is None
key(k.BUTTON_CENTER); key(k.BUTTON_CENTER)
assert a.model['selfweight'] is None
esc()
assert a.page == 'model'
# Put the point load in Live and check the combination (undo restored copies).
load = [l for l in a.model['loads'] if l['kind'] == 'point'][0]
a.focus(('load', load), 'case')
key(k.BUTTON_CENTER); pick(1)
assert load['case'] == 1
assert a.solution.view_names() == ['Dead', 'Live', 'Combo All x1.0', 'Combo C2']
near(sum(r[2] for r in a.solution.reactions(3)), 1.35 * 30e3 + 1.5 * 24e3)
shot('model-cases')
# Results.
key(k.BUTTON_F5)
assert a.page == 'results'
rows = a.result_rows()
assert any(r[0] == 'Equilibrium' and r[1] == 'OK' for r in rows) and any(r[0] == 'Max stress' for r in rows)
shot('results')
text('v')
key(k.BUTTON_DOWN); key(k.BUTTON_CENTER)
assert a.page == 'diagrams'
# Save, open and export.
key(k.BUTTON_F3)
a.menu_index = beam_app.OPTIONS.index('Save'); key(k.BUTTON_CENTER)
assert a.prompt is not None
for _ in range(10): key(k.BUTTON_BACKSPACE)
text('test beam'); key(k.BUTTON_CENTER)
assert a.prompt is None and a.message == 'Saved test-beam', a.message
a.menu_index = beam_app.OPTIONS.index('Export CSV (Eggcel)'); key(k.BUTTON_CENTER)
assert a.message.startswith('Exported test-beam-eggcel-001.csv'), a.message
a.menu_index = beam_app.OPTIONS.index('New beam'); key(k.BUTTON_CENTER)
a.menu_index = 1; key(k.BUTTON_CENTER)               # cantilever
assert a.model['supports'][0]['kind'] == 'Fixed'
shot('cantilever')
key(k.BUTTON_F3)
a.menu_index = beam_app.OPTIONS.index('Open'); key(k.BUTTON_CENTER)
assert a.files == ['gable-frame', 'test-beam'], a.files
a.menu_index = 1; key(k.BUTTON_CENTER)
assert a.model['name'] == 'test-beam' and a.model['cases'] == ['Dead', 'Live'] and a.problem is None
# A beam saved by the first Beam Lab opens through the app.
from json import dumps
vm.storage.write(cases.CASE_DIRECTORY + '/old-beam.json', dumps(dict(old, version=1)))
key(k.BUTTON_F3)
a.menu_index = beam_app.OPTIONS.index('Open'); key(k.BUTTON_CENTER)
a.menu_index = a.files.index('old-beam'); key(k.BUTTON_CENTER)
assert a.model['schema'] == 2 and len(a.model['members']) == 2 and a.problem is None, a.message
shot('model-upgraded')
# Frames: the portal template, runs, member angle, the whole-frame view.
key(k.BUTTON_F3)
a.menu_index = beam_app.OPTIONS.index('New beam'); key(k.BUTTON_CENTER)
a.menu_index = 7; key(k.BUTTON_CENTER)
assert a.problem is None and not bm.is_straight_beam(a.model) and len(bm.lines(a.model)) == 3
shot('portal')
key(k.BUTTON_TAB)
assert a.line == 1
key(k.BUTTON_TAB)
assert a.line == 2
a.focus(('member', 2), 'angle')
text('80'); key(k.BUTTON_CENTER)
assert abs(bm.member_angle(a.model, 2) - 80) < 1e-3 and a.problem is None
text('z')
assert abs(bm.member_angle(a.model, 2) - 90) < 1e-3
a.focus(('joint', 1), 'Y')
text('5'); key(k.BUTTON_CENTER)
assert a.model['joints'][1][1] == 5.0 and a.problem is None
text('+')
assert a.zoom == 1
shot('portal-zoom')
text('-')
key(k.BUTTON_F4)
assert a.page == 'diagrams'
text('m')
assert a.dline == 1
shot('portal-diagrams')
text('d'); text('d')
assert a.third == 'N'
text('f')
assert a.whole
shot('portal-moment')
text('d')
shot('portal-shear')
text('d'); text('d')
shot('portal-shape')
text('f')
key(k.BUTTON_F5)
rows = a.result_rows()
assert any(r[0] == 'Equilibrium' and r[1] == 'OK' for r in rows), [r for r in rows if r[0] == 'Equilibrium']
shot('portal-results')
key(k.BUTTON_F3)
a.menu_index = beam_app.OPTIONS.index('New beam'); key(k.BUTTON_CENTER)
a.menu_index = 8; key(k.BUTTON_CENTER)
assert a.problem is None
shot('gable')
key(k.BUTTON_F4); text('f')
shot('gable-moment')
# Help, then leave; PicoLAB keeps the model for the next visit.
text('?')
assert a.help_open and a.page == 'diagrams'
shot('help')
esc(); esc(); esc()
assert vm.get_view('beam_lab') is None
key(k.BUTTON_CENTER)
a = ui()
assert a.page == 'model' and len(a.model['members']) == 4
esc()
print('PASS: Beam Lab app: editing, sections, frames, undo, diagrams, cases, combinations, results, files')
