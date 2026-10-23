"""Euler references, section/axis selection and keyboard-driven Buckling UI."""
import os, sys
from math import pi, sqrt
from time import ticks_ms
root = os.getcwd()
for part in ('src/MicroPython', 'simulator/hardware', 'builds/MicroPython/apps_unfrozen'):
    sys.path.insert(0, root+'/'+part)
from engtools.buckling import model as m
from engtools import sections


def near(got, want, tol=5e-6):
    assert abs(got-want) <= tol*max(abs(want), 1e-12), (got, want)


def fails(fn):
    try:
        fn()
    except (ValueError, KeyError, TypeError, ZeroDivisionError, OverflowError):
        return
    raise AssertionError('Invalid case accepted')


s = m.new_state()
r = m.solve(s)
A, Iy, Iz = .04*.06, .04*.06**3/12, .06*.04**3/12
expected = pi*pi*200e9*Iz/4
near(r['critical'], expected)
near(r['axes']['y']['critical'], pi*pi*200e9*Iy/4)
near(r['axes']['z']['slenderness'], 2/sqrt(Iz/A))
near(r['axes']['z']['critical_stress'], expected/A)
near(r['yield_load'], 250e6*A)
near(r['factor'], expected/10000)
assert r['governing'] == 'z' and not r['yield_first']
for index, ratio in ((0, 1), (1, 4), (2, 1/.7**2), (3, .25)):
    s['ends_y'] = s['ends_z'] = index
    near(m.solve(s)['critical'], expected*ratio)
s = m.new_state(); s['length'] = 4
near(m.solve(s)['critical'], expected/4)
s = m.example(3); r = m.solve(s)
assert r['governing'] == 'y'  # Stronger inertia loses because K is larger.
near(r['critical'], pi*pi*200e9*Iy/(2*2)**2)
s['ends_y'] = s['ends_z'] = 4
s['Ky'], s['Kz'] = 1.25, .8
r = m.solve(s)
near(r['axes']['y']['critical'], pi*pi*200e9*Iy/(1.25*2)**2)
print('PASS: Euler loads/stress, slenderness, length scaling, all ideal/custom K and governing axis')

# Independent shape properties, symmetry and geometric scaling.
d = sections.defaults()
for shape in sections.SHAPES:
    p = sections.properties(shape, d)
    assert min(p.values()) > 0
    if shape != 'custom':
        scaled = dict(d)
        for key in sections.DIMS[shape]:
            scaled[key] *= 2
        q = sections.properties(shape, scaled)
        near(q['A'], 4*p['A']); near(q['Iy'], 16*p['Iy']); near(q['Iz'], 16*p['Iz'])
for shape in ('circle', 'tube'):
    p = sections.properties(shape, d)
    di = d['di'] if shape == 'tube' else 0
    near(p['Iy'], pi*(d['d']**4-di**4)/64)
    s = m.new_state(); s['shape'] = shape
    assert m.solve(s)['equal_axes']
p = sections.properties('box', d)
near(p['A'], .04*.06-.034*.054)
p = sections.properties('i-section', d)
near(p['Iy'], (.04*.06**3-(.04-.004)*(.06-2*.006)**3)/12)
near(p['Iz'], (2*.006*.04**3+(.06-2*.006)*.004**3)/12)
bad = dict(d, t=.03)
fails(lambda: sections.properties('box', bad))
bad = dict(d, di=.05)
fails(lambda: sections.properties('tube', bad))
print('PASS: six section types, independent properties and dimensional scaling')

r = m.solve(m.example(2)); assert r['yield_first'] and r['notes']
near(r['transition_slenderness'], pi*sqrt(200e9/250e6))
assert r['critical'] > r['yield_load']  # Never silently cap the Euler answer.
s = m.new_state(); s['compression'] = 0
r = m.solve(s); assert r['factor'] is None and r['yield_factor'] is None
s['material']['yield'] = 0
r = m.solve(s); assert r['yield_load'] is None and r['transition_slenderness'] is None and r['notes']
for i in range(len(m.EXAMPLES)):
    s = m.example(i)
    r = m.solve(s)
    assert m.from_case(m.to_case(s)) == s
    assert m.plot_spec(s, r)['series']
for field, value in (('length', 0), ('length', -1), ('compression', -1), ('length', float('inf'))):
    s = m.new_state(); s[field] = value
    fails(lambda: m.solve(s))
s = m.new_state(); s['ends_y'], s['Ky'] = 4, 0
fails(lambda: m.solve(s))
s = m.new_state(); s['ends_z'] = 99
fails(lambda: m.solve(s))
fails(lambda: m.from_case({'length': 1}))
print('PASS: yield-first warning, zero load, disabled yield, cases, examples and invalid inputs')

import sim_runtime
sim_runtime.configure(root, '/private/tmp/gungos-buckling-'+str(ticks_ms()),
                      root+'/builds/MicroPython/apps_unfrozen', 1, 'picocalc-pico2w', 0,
                      True, False, False, False, '', _network_mode='offline', _audio_mode='silent', _sd_profile='clean')
from picoware.system.view_manager import ViewManager
from picoware.system.view import View
from picoware.system.input import Input
from picoware.system import buttons as k
Input.button = property(lambda self: self._last_button)
vm = ViewManager(); vm._wifi = None
vm.add(View('parent', lambda vm: None, lambda vm: True, lambda vm: None)); vm.switch_to('parent')
from engtools.buckling import app
app.show(vm); a = app._active


def key(button):
    vm.input_manager._last_button = button
    vm.run()


def text(value):
    for char in value:
        key(vm.input_manager._key_to_button(ord(char)))


def field(path):
    in_section = path[0] in ('shape', 'section', 'material')
    if in_section and a.page != 'section':
        if a.page != 'model':
            key(k.BUTTON_ESCAPE)
        while a.tabs.label != 'Section':
            key(k.BUTTON_LEFT)
        key(k.BUTTON_CENTER)
    elif not in_section and a.page == 'section':
        key(k.BUTTON_ESCAPE)
    for _ in range(len(a.tabs.labels)):
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
    for _ in range((index-a.choice[2])%len(a.choice[1])):
        key(k.BUTTON_DOWN)
    key(k.BUTTON_CENTER)


def option(index):
    key(k.BUTTON_F3)
    for _ in range(index):
        key(k.BUTTON_DOWN)
    key(k.BUTTON_CENTER)


assert vm.current_view.name == 'buckling_view' and a.solution is None
# F9 must lead with the equation, not controls.
assert vm.current_view.help is None
key(k.BUTTON_F9)
sim_runtime.lcd_screenshot('/private/tmp/gungos-buckling-help.bmp')
key(k.BUTTON_ESCAPE)
key(k.BUTTON_F6); assert a.solution is not None and not a.error
sim_runtime.lcd_screenshot('/private/tmp/gungos-buckling-inputs.bmp')
assert a.tabs.labels == ('Section', 'Member', 'Ends') and app.PREVIEW[3] == 184
key(k.BUTTON_CENTER); assert a.page == 'section'
field(('section', 'b'))
original, old_solution = m.copy(a.state), a.solution
before = [bytes(vm.draw._read_row(y)) for y in range(65, 199)]
text('80')  # live draft, not yet committed
draft, editing, problem = a.section_draft()
near(draft['section']['b'], .08)
assert editing and not problem and a.state == original and a.solution is old_solution
after = [bytes(vm.draw._read_row(y)) for y in range(65, 199)]
assert before != after, 'Typing a size did not redraw the cross-section'
sim_runtime.lcd_screenshot('/private/tmp/gungos-buckling-section-draft.bmp')
key(k.BUTTON_ESCAPE); assert a.state == original and a.solution is old_solution
text('80'); key(k.BUTTON_CENTER)
near(a.state['section']['b'], .08); assert a.solution is None
text('z'); assert a.state == original
# Invalid sizes stay in the editor until corrected/cancelled.
text('0'); key(k.BUTTON_CENTER); assert a.edit is not None and a.error
key(k.BUTTON_ESCAPE)
key(k.BUTTON_F2); assert a.page == 'section' and a.choice[3] == ('material',)
key(k.BUTTON_ESCAPE)  # cancel preset chooser; E follows material in this view
key(k.BUTTON_DOWN); assert a.rows()[a.row][4] == ('material', 'E')
text('210')
draft, editing, problem = a.section_draft()
near(draft['material']['E'], 210e9); near(a.state['material']['E'], 200e9)
key(k.BUTTON_ESCAPE)
assert 'engtools.beamlab.model' not in sys.modules, 'Section preview loaded Beam view solver/model code'
sim_runtime.lcd_screenshot('/private/tmp/gungos-buckling-section-material.bmp')
key(k.BUTTON_ESCAPE); assert a.page == 'model'
field(('length',)); text('2*2'); key(k.BUTTON_CENTER)
assert a.solution is None; near(a.state['length'], 4)
text('z'); near(a.state['length'], 2)
key(k.BUTTON_F1)
for _ in range(3):
    key(k.BUTTON_DOWN)
key(k.BUTTON_CENTER)
assert a.state['ends_y'] == a.state['ends_z'] == 3
key(k.BUTTON_F6); near(a.solution['critical'], expected/4)
choose(('ends_y',), 4)
field(('Ky',)); text('0'); key(k.BUTTON_CENTER)
assert a.edit is not None and a.error
key(k.BUTTON_ESCAPE)
text('1.25'); key(k.BUTTON_CENTER)
key(k.BUTTON_F6); assert a.solution is not None
choose(('shape',), 3)
key(k.BUTTON_F2); key(k.BUTTON_DOWN); key(k.BUTTON_CENTER)
assert a.state['shape'] == 'tube' and a.state['material']['E'] == 70e9
key(k.BUTTON_F6)
key(k.BUTTON_F5); assert a.page == 'results'
for _ in range(20):
    key(k.BUTTON_DOWN)
sim_runtime.lcd_screenshot('/private/tmp/gungos-buckling-results.bmp')
key(k.BUTTON_ESCAPE)
# Shared plot is a child view; returning preserves inputs, results and focus.
saved, solution, row = m.copy(a.state), a.solution, a.row
from engtools.plots import plot2d
graph_class = plot2d.GraphApp
captured = []
def capture_graph(*args, **kwargs):
    graph = graph_class(*args, **kwargs)
    captured.append(graph)
    return graph
plot2d.GraphApp = capture_graph
key(k.BUTTON_F4); assert vm.current_view.name == 'eng_plot2d' and app._active is None
plot2d.GraphApp = graph_class
for _ in range(400):
    key(k.BUTTON_NONE)
    if captured[0].completed:
        break
assert captured[0].completed
from sim_pixels import Pixels, colour
chart = captured[0]
# A horizontal yield line coincides with the 200 MPa gridline. The final
# axes/labels pass must not paint over it.
px, py = chart.pixel(sum(chart.bounds[:2])/2, a.state['material']['yield']/1e6)
assert Pixels(vm.draw).pixel(int(px), int(py)) == colour(chart.items[2].color)
sim_runtime.lcd_screenshot('/private/tmp/gungos-buckling-plot.bmp')
key(k.BUTTON_ESCAPE)
a = app._active
assert vm.current_view.name == 'buckling_view' and a.state == saved and a.solution is solution and a.row == row
option(1)
for _ in range(20):
    key(k.BUTTON_BACKSPACE)
text('column-check'); key(k.BUTTON_CENTER)
assert a.dialog is None and not a.error, a.message
option(3); assert not a.error, a.message
files = vm.storage.listdir('picoware/engineering/exports')
data = vm.storage.read('picoware/engineering/exports/'+files[0])
assert 'Pcr [N]' in data and 'I [m4]' in data and len(data.strip().split('\n')) == 3
option(2); assert a.files == ['column-check']
key(k.BUTTON_CENTER); assert a.state == saved and a.solution is None
for index in range(len(m.EXAMPLES)):
    option(0)
    for _ in range(index):
        key(k.BUTTON_DOWN)
    key(k.BUTTON_CENTER); key(k.BUTTON_F6)
    assert a.solution is not None and not a.error
    key(k.BUTTON_F5); a.draw(); key(k.BUTTON_ESCAPE)
    for row in range(len(a.rows())):
        a.row = row; a.draw()
for shape in range(len(sections.SHAPES)):
    choose(('shape',), shape)
    key(k.BUTTON_F6); assert a.solution is not None and not a.error
    sim_runtime.lcd_screenshot('/private/tmp/gungos-buckling-section-'+sections.SHAPES[shape]+'.bmp')
vm.background_color = 0xffff; vm.foreground_color = 0
for page in ('model', 'results', 'options'):
    a.page = page; a.index = 0; a.draw()
a.page = 'model'
saved = m.copy(a.state)
key(k.BUTTON_ESCAPE); assert vm.current_view.name == 'parent'
app.show(vm); a = app._active
assert a.state == saved and a.solution is None
print('PASS: equation-first F9, edits, undo, per-axis/custom K, material, plots and return, files, CSV, examples, themes and lifecycle')
