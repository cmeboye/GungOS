"""Section Properties: independent geometry references and keyboard flows."""
import os, sys
from math import pi, sqrt
from time import ticks_ms
root = os.getcwd()
for part in ('src/MicroPython', 'simulator/hardware', 'builds/MicroPython/apps_unfrozen'):
    sys.path.insert(0, root+'/'+part)
from engtools.sectionprops import model as m


def near(got, want, tol=8e-6):
    assert abs(got-want) <= tol*max(abs(want), 1e-20), (got, want)


def fails(fn):
    try:
        fn()
    except (ValueError, TypeError, KeyError, ZeroDivisionError, OverflowError):
        return
    raise AssertionError('Invalid section accepted')


s = m.new_state(); r = m.solve(s)
near(r['A'], .0024); near(r['cy'], .02); near(r['cz'], .03)
near(r['Iy'], 7.2e-7); near(r['Iz'], 3.2e-7)
near(r['Wy_top'], .04*.06**2/6); near(r['Wz_left'], .06*.04**2/6)
near(r['ry'], .06/sqrt(12)); near(r['rz'], .04/sqrt(12))
near(r['mass_per_length'], 18.84); near(r['EIy'], 144000)
assert r['J'] is None and r['theta'] == 0 and r['Iyz'] == 0
s['dims'].update(b=.08, h=.04); r = m.solve(s)
near(r['theta'], pi/2); assert r['I1'] == r['Iz']
s['dims'].update(b=.04, h=.04); assert m.solve(s)['equal_axes']
for shape in ('circle', 'tube'):
    s = m.new_state(); s['shape'] = shape
    di = .02 if shape == 'tube' else 0
    r = m.solve(s)
    near(r['A'], pi*(.04**2-di**2)/4)
    near(r['Iy'], pi*(.04**4-di**4)/64)
    near(r['J'], pi*(.04**4-di**4)/32)
    assert r['equal_axes']
s = m.new_state(); s['shape'] = 'box'; r = m.solve(s)
near(r['A'], .04*.06-.034*.054)
near(r['Iy'], (.04*.06**3-.034*.054**3)/12)
s = m.example(4); r = m.solve(s)
near(r['Iy'], (.1*.15**3-(.1-.008)*(.15-.024)**3)/12)
near(r['Iz'], (2*.012*.1**3+(.15-.024)*.008**3)/12)
print('PASS: area, centroid, moments, moduli, gyration, material quantities and circular-only torsion')

# T-section: independent midpoint integration over height, not the model's
# two-rectangle parallel-axis calculation.
s = m.example(5); r = m.solve(s)
near(r['A'], .002304); near(r['cz'], .1080625)
n, dz = 1500, .15/1500
area, first, raw_second = 0.0, 0.0, 0.0
for i in range(n):
    z = (i+.5)*dz
    width = .008 if z < .138 else .1
    a = width*dz
    area += a; first += a*z; raw_second += a*z*z
near(area, r['A'], .0001)
near(first/area, r['cz'], .0001)
near(raw_second-area*(first/area)**2, r['Iy'], .0006)
near(r['Wy_top'], r['Iy']/(.15-r['cz']))
near(r['Wy_bottom'], r['Iy']/r['cz'])
assert r['Wy_top'] > r['Wy_bottom'] and r['Iyz'] == 0
for i in range(len(m.SHAPES)):
    s = m.example(i); r = m.solve(s)
    assert m.from_case(m.to_case(s)) == s
    scaled = m.copy(s)
    for key in m.DIMS[s['shape']]:
        scaled['dims'][key] *= 2
    q = m.solve(scaled)
    for key, factor in (('A', 4), ('cy', 2), ('cz', 2), ('Iy', 16), ('Iz', 16),
                         ('Wy_top', 8), ('Wy_bottom', 8), ('ry', 2), ('mass_per_length', 4)):
        near(q[key], factor*r[key])
    report = m.report(s)
    assert report['kind'] == 'section-properties' and report['units'] == 'SI'
for shape, key, value in (('rectangle', 'b', 0), ('tube', 'di', .05), ('box', 't', .03),
                          ('i-section', 'tf', .04), ('tee', 'tf', .06), ('circle', 'd', float('nan'))):
    s = m.new_state(); s['shape'] = shape; s['dims'][key] = value
    fails(lambda: m.solve(s))
s = m.new_state(); s['material']['rho'] = -1; fails(lambda: m.solve(s))
s['material']['rho'] = 0; near(m.solve(s)['mass_per_length'], 0)
fails(lambda: m.from_case({'shape': 'circle'}))
print('PASS: T centroid and inertia integration, all six cases, dimensional scaling, reports and invalid inputs')

import sim_runtime
sim_runtime.configure(root, '/private/tmp/gungos-sectionprops-'+str(ticks_ms()),
                      root+'/builds/MicroPython/apps_unfrozen', 1, 'picocalc-pico2w', 0,
                      True, False, False, False, '', _network_mode='offline', _audio_mode='silent', _sd_profile='clean')
from picoware.system.view_manager import ViewManager
from picoware.system.view import View
from picoware.system.input import Input
from picoware.system import buttons as k
Input.button = property(lambda self: self._last_button)
vm = ViewManager(); vm._wifi = None
vm.add(View('parent', lambda vm: None, lambda vm: True, lambda vm: None)); vm.switch_to('parent')
from engtools.sectionprops import app
app.show(vm); a = app._active


def key(button):
    vm.input_manager._last_button = button
    vm.run()


def text(value):
    for char in value:
        key(vm.input_manager._key_to_button(ord(char)))


def field(path):
    for _ in range(len(a.tabs.labels)):
        target = next((i for i, r in enumerate(a.rows()) if r[4] == path), None)
        if target is not None:
            for _ in range(abs(target-a.row)):
                key(k.BUTTON_DOWN if target > a.row else k.BUTTON_UP)
            return
        key(k.BUTTON_RIGHT)
    raise AssertionError('Missing field '+str(path))


def option(index):
    key(k.BUTTON_F3)
    for _ in range(index):
        key(k.BUTTON_DOWN)
    key(k.BUTTON_CENTER)


assert vm.current_view.name == 'sectionprops_view'
assert a.tabs.labels == ('Geometry', 'Material', 'Properties')
sim_runtime.lcd_screenshot('/private/tmp/gungos-sectionprops-home.bmp')
field(('dims', 'b'))
saved, solution = m.copy(a.state), a.solution
before = [bytes(vm.draw._read_row(y)) for y in range(65, 199)]
text('80')
draft, prop, active, error = a.draft()
assert active and not error and a.state == saved and a.solution is solution
near(prop['A'], .0048)
assert before != [bytes(vm.draw._read_row(y)) for y in range(65, 199)]
sim_runtime.lcd_screenshot('/private/tmp/gungos-sectionprops-draft.bmp')
key(k.BUTTON_ESCAPE); assert a.state == saved
text('2*40'); key(k.BUTTON_CENTER); near(a.state['dims']['b'], .08)
text('z'); assert a.state == saved
text('0'); key(k.BUTTON_CENTER); assert a.error and a.edit is not None
key(k.BUTTON_ESCAPE)
# Material and numeric drafts are reversible; tab focus survives switching.
key(k.BUTTON_RIGHT); assert a.tabs.label == 'Material'
key(k.BUTTON_DOWN); assert a.rows()[a.row][4] == ('material', 'rho')
text('1000'); key(k.BUTTON_CENTER); near(a.solution['mass_per_length'], 2.4)
key(k.BUTTON_RIGHT); assert a.tabs.label == 'Properties'
key(k.BUTTON_CENTER); assert a.edit is None and not a.error
key(k.BUTTON_LEFT); assert a.rows()[a.row][4] == ('material', 'rho')
a.select_tab('Material'); a.row=0; key(k.BUTTON_CENTER)
while a.choice[2] != 1:
    key(k.BUTTON_DOWN)
key(k.BUTTON_CENTER)
near(a.state['material']['rho'], 2700)
a.select_tab('Geometry'); a.row=0; key(k.BUTTON_CENTER)
for _ in range(5):
    key(k.BUTTON_DOWN)
assert a.state['shape'] == 'rectangle' and a.draft()[0]['shape'] == 'tee'
key(k.BUTTON_CENTER); assert a.state['shape'] == 'tee'
near(a.solution['cz'], m.solve(a.state)['cz'])
sim_runtime.lcd_screenshot('/private/tmp/gungos-sectionprops-tee.bmp')
key(k.BUTTON_F4); assert a.page == 'view'
sim_runtime.lcd_screenshot('/private/tmp/gungos-sectionprops-view.bmp')
old_axes = a.axes
before = [bytes(vm.draw._read_row(y)) for y in range(67, 280)]
key(k.BUTTON_A); assert a.axes != old_axes
assert before != [bytes(vm.draw._read_row(y)) for y in range(67, 280)]
key(k.BUTTON_ESCAPE); assert a.page == 'model'
key(k.BUTTON_F5); assert a.page == 'results'
for _ in range(7):
    key(k.BUTTON_DOWN)
sim_runtime.lcd_screenshot('/private/tmp/gungos-sectionprops-results.bmp')
key(k.BUTTON_ESCAPE)
key(k.BUTTON_F9); assert a.help_view.opened and a.help_view.blocks[0][0] == 'formula'
sim_runtime.lcd_screenshot('/private/tmp/gungos-sectionprops-help.bmp')
for _ in range(6):
    key(k.BUTTON_DOWN)
key(k.BUTTON_F9); assert not a.help_view.opened
# Saved inputs and standalone exports; files from other apps are filtered.
from engtools import cases
cases.save_case(vm.storage, 'other-tool', {'tool': 'buckling'})
option(1)
for _ in range(30):
    key(k.BUTTON_BACKSPACE)
text('review-section'); key(k.BUTTON_CENTER)
assert a.dialog is None and not a.error, a.message
saved = m.copy(a.state)
option(3); assert not a.error
option(4); assert not a.error
from json import loads
files = vm.storage.listdir(cases.EXPORT_DIRECTORY)
csv = vm.storage.read(cases.EXPORT_DIRECTORY+'/'+next(f for f in files if f.endswith('.csv')))
assert 'Iy [m4]' in csv and 'Wy_top [m3]' in csv and 'J [m4]' not in csv
report = loads(vm.storage.read(cases.EXPORT_DIRECTORY+'/'+next(f for f in files if f.endswith('.json'))))
assert report['kind'] == 'section-properties' and report['results']['J'] is None
option(2); assert a.files == ['review-section']
key(k.BUTTON_CENTER); assert a.state == saved
for index in range(len(m.EXAMPLES)):
    option(0)
    for _ in range(index):
        key(k.BUTTON_DOWN)
    key(k.BUTTON_CENTER)
    assert a.state == m.example(index)
    for row in range(len(a.rows())):
        a.row = row; a.draw()
    for button in (k.BUTTON_F4, k.BUTTON_F5):
        key(button); a.draw()
    key(k.BUTTON_ESCAPE)
assert 'engtools.beamlab.model' not in sys.modules
assert 'engtools.buckling.app' not in sys.modules and 'engtools.stressstrain.app' not in sys.modules
vm.background_color = 0xffff; vm.foreground_color = 0
for tab in range(3):
    a.tabs.index, a.row = tab, 0; a.draw()
sim_runtime.lcd_screenshot('/private/tmp/gungos-sectionprops-light.bmp')
saved = m.copy(a.state)
key(k.BUTTON_ESCAPE); assert vm.current_view.name == 'parent'
app.show(vm); a = app._active; assert a.state == saved
print('PASS: live drafts, cancellation, invalid edits, tab focus, material, shape preview, axes, help, files, exports, six examples, themes and app isolation')
