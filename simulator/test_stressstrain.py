"""StressStrain: analytical references, tensor inverses, then UI by keys."""
import os, sys
from math import pi, sqrt
from time import ticks_ms
root = os.getcwd()
for part in ('src/MicroPython', 'simulator/hardware', 'builds/MicroPython/apps_unfrozen'):
    sys.path.insert(0, root+'/'+part)
from engtools.stressstrain import model as m


def near(got, want, tolerance=3e-5, floor=1e-8):
    assert abs(got-want) <= tolerance*max(abs(want), floor), (got, want)


def fails(fn, words):
    try:
        fn()
    except (ValueError, TypeError, KeyError, OverflowError):
        return
    raise AssertionError(words)


# A round shaft: independently derive normal and torsional stress at z=R.
s = m.example(0)
r = m.solve(s)
R = .02
A, I, J = pi*R**2, pi*R**4/4, pi*R**4/2
sx, tau = 10000/A+100*R/I, -100*R/J
near(r['stress'][0], sx)
near(r['stress'][3], tau)
near(r['stress'][5], 0)
near(r['invariants']['mises'], sqrt(sx*sx+3*tau*tau), 2e-4)
near(r['strain'][3], tau/(200e9/(2*1.3)))
near(r['safety'], 250e6/sqrt(sx*sx+3*tau*tau), 2e-4)
# Opposite points reverse bending/torsion but preserve the axial part.
opposite = m.copy(s); opposite['point']['z'] = -R
other = m.solve(opposite)
near((r['stress'][0]+other['stress'][0])/2, 10000/A)
near(other['stress'][3], -tau)
print('PASS: axial + bending + torsion, signs, von Mises, shear strain and yield')

# Rectangle: pointwise bending signs and the parabolic shear approximation.
s = m.example(1)
s['loads'].update(N=24000, My=120, Mz=80, Vy=1200, Vz=2400)
s['point'].update(y=.01, z=.015)
r = m.solve(s)
near(r['properties']['A'], .04*.06)
near(r['stress'][0], 24000/(.04*.06)+120*.015/(.04*.06**3/12)-80*.01/(.06*.04**3/12))
near(r['stress'][3], 1.5*1200/(.04*.06)*(1-(.01/.02)**2))
near(r['stress'][5], 1.5*2400/(.04*.06)*(1-(.015/.03)**2))
# Integrate transverse stress over width/height: recover the applied forces.
for force, coordinate, shear_index, extent, breadth in (('Vy', 'y', 3, .02, .06), ('Vz', 'z', 5, .03, .04)):
    accum, count = 0.0, 160
    for i in range(count):
        trial = m.copy(s)
        trial['point'][coordinate] = -extent+(i+.5)*2*extent/count
        accum += m.solve(trial)['stress'][shear_index]*2*extent/count*breadth
    near(accum, s['loads'][force], 6e-5)
print('PASS: rectangular bending, parabolic shear and force resultants')

s = m.example(2)
r = m.solve(s)
near(r['properties']['J'], pi*(.04**4-.02**4)/32)
near(r['stress'][5], 200*.02/(pi*(.04**4-.02**4)/32))
s['point'].update(y=0, z=0)
fails(lambda: m.solve(s), 'tube hole accepted')
s = m.example(1); s['loads']['T'] = 1
fails(lambda: m.solve(s), 'rectangle torsion accepted')
s = m.example(0); s['loads']['Vy'] = 1
fails(lambda: m.solve(s), 'circular transverse shear accepted')
s = m.example(0); s['point']['y'] = .1
fails(lambda: m.solve(s), 'point outside section accepted')
s = m.example(0); s['shape'] = 'custom'; s['loads']['T'] = 0
s['section'].update(A=.002, Iy=2e-7, Iz=3e-7)
near(m.solve(s)['stress'][0], 10000/.002+100*.02/2e-7)
print('PASS: hollow section, custom principal properties and unsupported-load guards')

# Independent thermoelastic references, including engineering gamma.
s = m.example(3)
r = m.solve(s)
near(r['strain'][0], .0005)
near(r['strain'][1], -.00015)
near(r['strain'][2], -.00015)
s = m.example(4); r = m.solve(s)
near(r['strain'][3], 2*1.3*50e6/200e9)
near(r['invariants']['mises'], sqrt(3)*50e6, 2e-4)
s = m.example(6); r = m.solve(s)
for value in r['strain'][:3]:
    near(value, 12e-6*50)
s = m.example(7); r = m.solve(s)
for value in r['stress'][:3]:
    near(value, -200e9*12e-6*50/(1-2*.3))
near(r['invariants']['mises'], 0)
# Plane stress with fixed total in-plane strain: biaxial thermal restraint.
s['condition'] = 'plane-stress'
r = m.solve(s)
near(r['stress'][0], -200e9*12e-6*50/(1-.3))
near(r['stress'][2], 0)
# Plane strain derives sz, including the thermal contribution.
s = m.example(5); r = m.solve(s)
near(r['stress'][2], .3*100e6-200e9*12e-6*50)
near(r['strain'][2], 0)
for condition in m.CONDITIONS:
    for nu in (-.4, 0.0, .3, .49):
        s = m.example(3)
        s['condition'], s['dt'], s['material']['nu'] = condition, 27, nu
        s['stress'] = [110e6, -45e6, 23e6, 13e6, -19e6, 8e6]
        forward = m.solve(s)
        s['direction'], s['strain'] = 'strain', forward['strain']
        inverse = m.solve(s)
        for got, want in zip(inverse['stress'], forward['stress']):
            near(got, want, .0003, 1e5)
print('PASS: 3D / plane stress / plane strain, thermal restraint, shear convention and inverses')

for i in range(len(m.EXAMPLES)):
    s = m.example(i)
    assert m.from_case(m.to_case(s)) == s
    m.solve(s)
s = m.new_state(); s['material']['nu'] = .5
fails(lambda: m.solve(s), 'incompressible material accepted')
s = m.new_state(); s['loads']['N'] = float('nan')
fails(lambda: m.solve(s), 'nan accepted')
fails(lambda: m.from_case({'mode': 'section'}), 'broken case accepted')
s = m.to_case(m.new_state()); s['stress'] = [0]
fails(lambda: m.from_case(s), 'short tensor accepted')
print('PASS: all examples, SI cases and malformed-input handling')

# Independent section-wide references: exact bending extrema are generally
# between the angular sample locations; pure shear peaks at the centre.
from engtools.stressstrain.field import SectionField
s = m.example(0)
s['loads'].update(My=137, Mz=-83)
f = SectionField(s)
expected = s['loads']['N']/f.props['A']
bending = .02*sqrt(137**2+83**2)/f.props['Iy']
near(f.extrema[0][0], expected+bending)
near(f.extrema[1][0], expected-bending)
tau = abs(s['loads']['T'])*.02/f.props['J']
near(f.extrema[3][0], sqrt((expected+bending)**2+3*tau**2))
for i in range(4):
    value, y, z = f.extrema[i]
    assert m.contains(s, y, z)
    trial = m.copy(s); trial['point'].update(y=y, z=z)
    result = m.solve(trial)
    near(f.values(y, z)[0], result['stress'][0])
    near(f.values(y, z)[2], result['invariants']['mises'], 3e-4)
s = m.example(1)
s['loads'].update(N=0, My=0, Mz=0, Vy=1200, Vz=2400)
f = SectionField(s)
tau = 1.5*sqrt(1200**2+2400**2)/(.04*.06)
near(f.extrema[2][0], tau)
near(f.extrema[3][0], sqrt(3)*tau)
assert f.extrema[2][1:] == (0, 0)
# Thin tube scans retain both boundaries, even when a Cartesian raster has
# no pixel at a specific circumferential location.
s = m.example(2); s['section']['di'] = .03999
f = SectionField(s)
near(f.extrema[2][0], 200*.02/f.props['J'])
for value, y, z in f.extrema:
    assert m.contains(s, y, z)
s = m.example(1); s['loads'].update(N=-1234, My=-71, Mz=103, Vy=0, Vz=0)
f = SectionField(s)
span = abs(s['loads']['My'])*.03/f.props['Iy']+abs(s['loads']['Mz'])*.02/f.props['Iz']
near(f.extrema[0][0], -1234/f.props['A']+span)
near(f.extrema[1][0], -1234/f.props['A']-span)
s['loads'] = dict((name, 0.0) for name in s['loads'])
f = SectionField(s)
assert all(item[0] == 0 for item in f.extrema)
assert f.limits(0) == (0, 0) and f.limits(2) == (0, 0)
s['shape'] = 'custom'
fails(lambda: SectionField(s), 'custom outline invented')
s = m.example(0); s['loads']['Vy'] = 1
fails(lambda: SectionField(s), 'map accepted unsupported shear')
print('PASS: exact biaxial extrema, sampled shear/VM references, thin tubes, zero fields and map guards')

import sim_runtime
sim_runtime.configure(root, '/private/tmp/gungos-stressstrain-'+str(ticks_ms()),
                      root+'/builds/MicroPython/apps_unfrozen', 1, 'picocalc-pico2w', 0,
                      True, False, False, False, '', _network_mode='offline', _audio_mode='silent', _sd_profile='clean')
from picoware.system.view_manager import ViewManager
from picoware.system.view import View
from picoware.system.input import Input
from picoware.system import buttons as k
Input.button = property(lambda self: self._last_button)
vm = ViewManager(); vm._wifi = None
vm.add(View('parent', lambda vm: None, lambda vm: True, lambda vm: None)); vm.switch_to('parent')
from engtools.stressstrain import app
app.show(vm)
a = app._active


def key(button):
    vm.input_manager._last_button = button
    vm.run()


def text(value):
    for char in value:
        key(vm.input_manager._key_to_button(ord(char)))


def field(path):
    embedded = a.state['mode'] == 'section' and path[0] in ('shape', 'section', 'material', 'dt', 'property')
    if embedded and a.page != 'section':
        field(('section_editor',)); key(k.BUTTON_CENTER)
        assert a.page == 'section'
    elif not embedded and a.page == 'section':
        key(k.BUTTON_ESCAPE)
    tabs = a.section_tabs if a.page == 'section' else a.tabs
    for _ in range(len(tabs.labels)):
        rows = a.rows()
        target = next((i for i, r in enumerate(rows) if r[4] == path), None)
        if target is not None:
            for _ in range(abs(target-a.row)):
                key(k.BUTTON_DOWN if target > a.row else k.BUTTON_UP)
            return
        key(k.BUTTON_RIGHT)
    raise AssertionError('Missing field '+str(path))


def choose(path, index):
    field(path); key(k.BUTTON_CENTER)
    assert a.choice is not None
    for _ in range((index-a.choice[2])%len(a.choice[1])):
        key(k.BUTTON_DOWN)
    key(k.BUTTON_CENTER)
    assert a.choice is None


def option(index):
    key(k.BUTTON_F3)
    for _ in range(index):
        key(k.BUTTON_DOWN)
    key(k.BUTTON_CENTER)


assert vm.current_view.name == 'stressstrain_view' and a.solution is None
key(k.BUTTON_F6); assert a.solution is not None and not a.error
sim_runtime.lcd_screenshot('/private/tmp/gungos-stressstrain-inputs.bmp')
# The embedded shared section preview edits this case without touching the
# standalone Section Properties session. Drafts and cancel preserve results.
from engtools import session
session.kept['sectionprops'] = {'sentinel': 'standalone'}
field(('section', 'd'))
assert a.page == 'section' and a.section_tabs.label == 'Geometry'
old_solution, old_map = a.solution, a.section_map
text('50')
draft, props, active, problem = a.section_draft()
assert active and not problem
near(draft['section']['d'], .05)
near(props['A'], pi*.05**2/4)
assert a.state['section']['d'] == .04 and a.solution is old_solution
sim_runtime.lcd_screenshot('/private/tmp/gungos-stressstrain-section-draft.bmp')
key(k.BUTTON_ESCAPE)
assert a.state['section']['d'] == .04 and a.section_map is old_map
text('-2'); key(k.BUTTON_CENTER)
assert a.edit is not None and a.error and a.state['section']['d'] == .04
key(k.BUTTON_ESCAPE)
text('50'); key(k.BUTTON_CENTER)
near(a.state['section']['d'], .05)
assert a.solution is None and a.section_map is None and a.map_cache is None
text('z'); near(a.state['section']['d'], .04)
field(('material', 'E')); text('210'); key(k.BUTTON_CENTER)
near(a.state['material']['E'], 210e9)
text('z'); near(a.state['material']['E'], 200e9)
key(k.BUTTON_RIGHT)
assert a.section_tabs.label == 'Properties'
key(k.BUTTON_CENTER); assert a.edit is None and 'Calculated' in a.message
key(k.BUTTON_F9); assert a.help_view.opened
key(k.BUTTON_ESCAPE)
for bg, fg, name in ((0, 0xffff, 'dark'), (0xffff, 0, 'light')):
    vm.background_color, vm.foreground_color = bg, fg
    a.draw()
    sim_runtime.lcd_screenshot('/private/tmp/gungos-stressstrain-section-editor-'+name+'.bmp')
vm.background_color, vm.foreground_color = 0, 0xffff
assert session.kept['sectionprops'] == {'sentinel': 'standalone'}
key(k.BUTTON_ESCAPE); assert a.page == 'model' and a.tabs.label == 'Section'
field(('loads', 'N')); text('2*10'); key(k.BUTTON_CENTER)
assert a.state['loads']['N'] == 20000 and a.solution is None
text('z'); assert a.state['loads']['N'] == 10000
key(k.BUTTON_F6); key(k.BUTTON_F4); assert a.page == 'plots'
scan = a.section_map
assert scan is not None and a.map_cache is not None
for _ in range(4):
    key(k.BUTTON_P)
assert a.state['point']['z'] == .02 and a.solution is not None
assert a.section_map is scan
key(k.BUTTON_F6)
scan = a.section_map
sim_runtime.lcd_screenshot('/private/tmp/gungos-stressstrain-section.bmp')
key(k.BUTTON_UP); assert a.error and a.solution is not None
key(k.BUTTON_DOWN); assert a.solution is not None and a.section_map is scan
for i in range(4):
    key(k.BUTTON_F8)
    assert a.critical_index == i and a.solution is not None
    near(a.state['point']['y'], scan.extrema[i][1])
    near(a.state['point']['z'], scan.extrema[i][2])
    assert ('exact' if i < 2 else 'sampled') in a.message
for background, foreground, name in ((0, 0xffff, 'dark'), (0xffff, 0, 'light')):
    vm.background_color, vm.foreground_color = background, foreground
    for i in range(3):
        a.map_kind = i; a.draw()
        sim_runtime.lcd_screenshot('/private/tmp/gungos-stressstrain-map-'+name+'-'+str(i)+'.bmp')
    old = a.map_kind
    key(k.BUTTON_F7); assert a.map_kind == (old+1)%3
vm.background_color, vm.foreground_color = 0, 0xffff
key(k.BUTTON_F6); key(k.BUTTON_F5); assert a.page == 'results'
assert any(row[0] == 'von Mises' for row in a.result_rows())
assert any(row[0] == 'Section critical points' for row in a.result_rows())
for _ in range(18):
    key(k.BUTTON_DOWN)
sim_runtime.lcd_screenshot('/private/tmp/gungos-stressstrain-results.bmp')
key(k.BUTTON_ESCAPE)
# Changing shape preserves unsupported loads and F6 explains them.
choose(('shape',), 2)
key(k.BUTTON_F6); assert a.error and 'Torsion' in a.message and a.solution is None
field(('loads', 'T')); text('0'); key(k.BUTTON_CENTER)
key(k.BUTTON_F6); assert a.solution is not None
# Switch analysis and direction by keys; conversion preserves current state.
a.select_tab('Analysis'); a.row=0; key(k.BUTTON_CENTER); key(k.BUTTON_DOWN); key(k.BUTTON_CENTER)
assert a.state['mode'] == 'constitutive'
choose(('condition',), 1)
key(k.BUTTON_F6); expected = list(a.solution['stress'])
choose(('direction',), 1)
key(k.BUTTON_F6)
for got, want in zip(a.solution['stress'], expected):
    near(got, want, .001, 1e5)
field(('material', 'nu')); text('0.5'); key(k.BUTTON_CENTER)
assert a.edit is not None and a.error
key(k.BUTTON_ESCAPE)
choose(('material',), 1)
assert a.state['material']['E'] == 70e9 and a.solution is None
key(k.BUTTON_F6); key(k.BUTTON_F4)
sim_runtime.lcd_screenshot('/private/tmp/gungos-stressstrain-tensor.bmp')
key(k.BUTTON_ESCAPE)
# Save/open/CSV/JSON all through their options.
option(1)
for _ in range(20):
    key(k.BUTTON_BACKSPACE)
text('first-case'); key(k.BUTTON_CENTER)
assert a.dialog is None and not a.error, a.message
saved = m.copy(a.state)
key(k.BUTTON_F6); option(3); assert not a.error, a.message
files = vm.storage.listdir('picoware/engineering/exports')
csv = vm.storage.read('picoware/engineering/exports/'+files[0])
assert csv.startswith('sx [Pa],sy [Pa]') and 'gxy [1]' in csv
option(4); assert not a.error, a.message
from json import loads
files = vm.storage.listdir('picoware/exchange')
record = loads(vm.storage.read('picoware/exchange/'+files[0]))
assert record['kind'] == 'stress-state' and record['units'] == 'Pa' and record['from'] == m.TOOL
option(2); assert a.files == ['first-case']
key(k.BUTTON_CENTER); assert a.state == saved and a.solution is None
key(k.BUTTON_F9); assert a.help_view.opened
key(k.BUTTON_ESCAPE)
# A tube's hole remains background in the cached map, in every field.
a.changed(m.example(2)); a.page = 'model'
key(k.BUTTON_F6); key(k.BUTTON_F4)
for i in range(3):
    a.map_kind = i; a.draw()
    cache_key, raw = a.map_cache
    width, height, bg = cache_key[2:]
    at = 2*((height//2)*width+width//2)
    assert raw[at] | raw[at+1]<<8 == bg
sim_runtime.lcd_screenshot('/private/tmp/gungos-stressstrain-map-tube.bmp')
# A direct A/I record has point results, but no invented map or extrema.
custom = m.example(0); custom['shape'] = 'custom'; custom['loads']['T'] = 0
a.changed(custom); a.page = 'model'
key(k.BUTTON_F6); key(k.BUTTON_F4)
assert a.solution is not None and a.section_map is None
key(k.BUTTON_F8); assert a.error and 'boundary' in a.message
key(k.BUTTON_ESCAPE)
# Every example and page draws in both dark and light themes.
for i in range(len(m.EXAMPLES)):
    a.page = 'model'; option(0)
    for _ in range(i):
        key(k.BUTTON_DOWN)
    key(k.BUTTON_CENTER); assert a.solution is None
    key(k.BUTTON_F6); assert a.solution is not None and not a.error, a.message
    for button in (k.BUTTON_F4, k.BUTTON_F5):
        key(button); a.draw()
    key(k.BUTTON_ESCAPE)
    for row in range(len(a.rows())):
        a.row = row; a.draw()
vm.background_color = 0xffff
vm.foreground_color = 0
for page in ('model', 'plots', 'results', 'options'):
    a.page = page; a.index = 0; a.draw()
a.page = 'model'
key(k.BUTTON_ESCAPE); assert vm.current_view.name == 'parent'
app.show(vm); a = app._active
assert a.state == m.example(len(m.EXAMPLES)-1) and a.solution is None
print('PASS: keyboard edits, undo, moving point, invalid loads, mode conversion, materials, files, exports, themes and lifecycle')
