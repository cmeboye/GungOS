"""Shrink fit tool: Lame solutions, given/find combinations, keys and drawing.

Run with the desktop MicroPython build, from the project root.
"""
import os, sys
from math import pi
from time import ticks_ms
root = os.getcwd()
for part in ('src/MicroPython', 'simulator/hardware', 'builds/MicroPython/apps_unfrozen'):
    sys.path.insert(0, root + '/' + part)
import sim_runtime
sim_runtime.configure(root, '/private/tmp/gungos-discs-' + str(ticks_ms()), root + '/builds/MicroPython/apps_unfrozen',
                      1, 'picocalc-pico2w', 0, True, False, False, False, '',
                      _network_mode='offline', _audio_mode='silent', _sd_profile='clean')
from picoware.system.view_manager import ViewManager
from picoware.system.view import View
from picoware.system.input import Input
from picoware.system import buttons as k
from engtools.discs import model as dm
Input.button = property(lambda self: self._last_button)


def near(a, b, tol=1e-4):
    assert abs(a - b) <= tol * max(1.0, abs(a), abs(b)), (a, b)


def raises(model, words):
    try:
        dm.Solution(model)
    except dm.ModelError as exc:
        assert words in str(exc), str(exc)
        return
    raise AssertionError('accepted: ' + words)


# ---------------------------------------------------------------- closed forms
# Shaft (solid, b = 25 mm) in a hub (c = 60 mm), same steel, 50 um diametral:
# p = E (delta/2) / b * (c^2 - b^2) / (2 c^2).
s = dm.Solution(dm.template(0))
E, b, c = 210e3, 25.0, 60.0
p = E * 0.025 / b * (c * c - b * b) / (2 * c * c)
near(s.values['pc'][0] / 1e6, p)
near(s.at(0, 10.0)[0], -p); near(s.at(0, 10.0)[1], -p)              # shaft: uniform -p
near(s.at(1, b)[1], p * (c * c + b * b) / (c * c - b * b))          # hub bore hoop
near(s.at(1, c)[0], 0.0, 1e-3)                                     # free outside
near(s.at(1, b)[3] - s.at(0, b)[3], 0.025)                         # radial interference
# Thick cylinder, plane strain: bore hoop p (a^2 + b^2)/(b^2 - a^2), sz = nu (sr + st).
s = dm.Solution(dm.template(3))
near(s.at(0, 50.0)[1], 100 * (2500 + 10000) / 7500); near(s.at(0, 50.0)[0], -100.0)
near(s.at(0, 70.0)[2], 0.3 * (s.at(0, 70.0)[0] + s.at(0, 70.0)[1]))
# Solid rotating disc: sr = st = (3 + nu)/8 rho w^2 R^2 at the centre; sr = 0 at the rim.
s = dm.Solution(dm.template(1)); w = 3000 * pi / 30
near(s.at(0, 0.0)[0], 3.3 / 8 * 7850 * w * w * 0.04 / 1e6); near(s.at(0, 200.0)[0], 0.0, 1e-3)
# Rotating ring: bore hoop rho w^2/4 ((3 + nu) b^2 + (1 - nu) a^2), sr = 0 at both edges.
s = dm.Solution(dm.template(2)); w = 6000 * pi / 30
near(s.at(0, 100.0)[1], 7850 * w * w / 4 * (3.3 * 0.0625 + 0.7 * 0.01) / 1e6)
near(s.at(0, 100.0)[0], 0.0, 1e-3); near(s.at(0, 250.0)[0], 0.0, 1e-3)
print('PASS: shrink fit, thick cylinder (plane strain), solid disc and ring against closed forms')

# ---------------------------------------------------------------- given / find
# Forward then inverse: the interference that gives 40 MPa reproduces it.
m = dm.template(5); s = dm.Solution(m)
near(s.values['pc'][0], 40e6); delta = s.values['delta'][0]
m2 = dm.template(5); m2['fits'][0]['delta'] = dm.var(delta); m2['fits'][0]['pc'] = dm.var(0.0, True)
near(dm.Solution(m2).values['pc'][0], 40e6, 1e-3)
# Contact 0 given, speed found = the loosening speed; that speed gives zero contact.
m = dm.template(0); s = dm.Solution(m); w = s.loosening(0)
m3 = dm.template(0); m3['fits'][0]['pc'] = dm.var(0.0); m3['speed'] = dm.var(0.0, True)
near(dm.Solution(m3).values['speed'], w, 1e-3)
m['speed']['v'] = w; assert abs(dm.Solution(m).values['pc'][0]) < 1e-3 * 86e6
# Find the bore pressure that makes a given contact pressure in a compound cylinder.
m = dm.template(4); s = dm.Solution(m); pc = s.values['pc'][0]
m4 = dm.template(4); m4['Pi'] = dm.var(0.0, True); m4['fits'][0]['pc'] = dm.var(pc)
near(dm.Solution(m4).values['Pi'], 150e6, 1e-3)
# Holding torque mu p 2 pi r^2 L; heating delta / (alpha d).
s = dm.Solution(dm.template(0)); T, F = s.torque(0)
near(T, 0.15 * p * 2 * pi * 25 ** 2 * 40 / 1e3); near(F, 0.15 * p * 2 * pi * 25 * 40)
near(s.heating(0), 50e-6 / (12e-6 * 0.05))
print('PASS: inverse interference, loosening speed, bore pressure from contact, torque and heating')

# ---------------------------------------------------------------- errors
m = dm.template(0); m['speed']['find'] = True; raises(m, 'Mark exactly 1')
m = dm.template(1); m['Po']['find'] = True; raises(m, 'One body has nothing to find')
m = dm.template(0); m['fits'][0]['pc']['find'] = False; m['Pi']['find'] = True; raises(m, 'needs a bore')
m = dm.template(0); m['radii'][1] = 0.07; raises(m, 'Body 2: outer radius')
m = dm.template(0)
for bd in m['bodies']: bd['rho'] = 0.0
m['fits'][0]['pc'] = dm.var(10e6); m['speed'] = dm.var(0.0, True); raises(m, 'cannot be found together')
m = dm.template(0); m['fits'][0]['pc'] = dm.var(200e6); m['speed'] = dm.var(0.0, True); raises(m, 'No speed')
m = dm.template(0); m['speed']['v'] = 40000 * pi / 30
assert 'opens' in dm.Solution(m).warnings()[0]
print('PASS: wrong Find counts, solid bore pressure, bad radii, singular and impossible finds, opened fits')

# ---------------------------------------------------------------- UI
vm = ViewManager(); vm._wifi = None
vm.add(View('parent', lambda vm: None, lambda vm: True, lambda vm: None)); vm.switch_to('parent')
from engtools import session
session.kept.pop('discs', None)
from engtools.discs import app


def key(button):
    vm.input_manager._last_button = button
    vm.run()


def text(value):
    for ch in value:
        key(vm.input_manager._key_to_button(ord(ch)))


def goto(label):
    labels = [r[1] for r in a.rows()]
    assert label in labels, ('no row ' + label, labels)
    target = labels.index(label)
    while a.rows_at[a.tab] != target:
        key(k.BUTTON_DOWN if a.rows_at[a.tab] < target else k.BUTTON_UP)


app.show(vm); a = app._active
assert vm.current_view.name == 'discs_view' and a.solution is not None
# Typed radius in mm with arithmetic; the result updates at once.
goto('Outer radius'); text('50/2'); key(k.BUTTON_CENTER)
assert abs(a.model['radii'][1] - 0.025) < 1e-9
# Editing E switches to Custom.
goto("Young's modulus"); text('200'); key(k.BUTTON_CENTER)
assert a.model['bodies'][0]['E'] == 200e9 and dm.MATERIALS[a.model['bodies'][0]['material']][0] == 'Custom'
key(vm.input_manager._key_to_button(ord('z'))); assert a.model['bodies'][0]['material'] == 0
# Fits tab: SPACE on contact pressure gives a wrong count; on interference fixes it.
key(k.BUTTON_RIGHT); key(k.BUTTON_RIGHT); assert a.tab == 2
goto('Contact pressure'); text(' '); assert a.problem and 'Mark exactly 1' in a.problem
key(k.BUTTON_UP); text(' '); assert a.problem is None
near(a.solution.values['pc'][0], 86.77083e6, 1e-3)  # contact kept as the given value
# Typing on a found value makes it given.
goto('Interference (dia.)'); text(' '); assert a.problem
goto('Contact pressure'); text('40'); key(k.BUTTON_CENTER)
assert not a.model['fits'][0]['pc']['find'] and a.problem and 'Mark exactly 1' in a.problem
goto('Interference (dia.)'); text(' '); assert a.problem is None
near(a.solution.values['pc'][0], 40e6, 1e-3)
# F1 adds a ring outside and a fit; F2 removes the selected body.
key(k.BUTTON_LEFT); key(k.BUTTON_LEFT); assert a.tab == 0
key(k.BUTTON_F1); key(k.BUTTON_CENTER)
assert len(a.model['bodies']) == 3 and len(a.model['fits']) == 2 and a.problem is None
key(k.BUTTON_F2); assert len(a.model['bodies']) == 2 and a.problem is None
# Loads tab: speed in rpm; the solid centre has no inner pressure.
key(k.BUTTON_RIGHT); goto('Speed'); text('3000'); key(k.BUTTON_CENTER)
near(a.model['speed']['v'], 3000 * pi / 30)
goto('Inner pressure Pi'); text(' '); assert a.error
# F6 focuses the preview: arrows orbit in 3D, V switches, ESC returns.
key(k.BUTTON_TAB); assert a.focus == 'preview'
text('v'); assert a.view == '3d'
yaw = a.yaw; key(k.BUTTON_RIGHT); assert a.yaw == (yaw + 15) % 360
key(k.BUTTON_UP); key(k.BUTTON_CENTER); assert a.view == 'section'
selected=a.selected(); pan=a.pan[0]
key(k.BUTTON_RIGHT); assert a.selected() == selected and a.pan[0] == pan+8
key(k.BUTTON_ESCAPE); assert a.focus == 'list' and vm.current_view.name == 'discs_view'
# Plot, results and options.
key(k.BUTTON_F4); assert a.page == 'plot'
text('.'); near(a.cursor, 25.0); text('d'); assert a.third == 'u'
key(k.BUTTON_F5); assert a.page == 'results'
for _ in range(30): key(k.BUTTON_DOWN)
key(k.BUTTON_ESCAPE); key(k.BUTTON_F3)
a.menu_index = app.OPTIONS.index('New: Compound cylinder'); key(k.BUTTON_CENTER)
assert a.page == 'model' and len(a.model['bodies']) == 2 and a.model['plane'] == 'strain'
key(k.BUTTON_F3); a.menu_index = app.OPTIONS.index('Save'); key(k.BUTTON_CENTER)
key(k.BUTTON_CENTER); assert a.prompt is None and a.message.startswith('Saved')
key(k.BUTTON_F3); a.menu_index = app.OPTIONS.index('New: Rotating disc'); key(k.BUTTON_CENTER)
key(k.BUTTON_F3); a.menu_index = app.OPTIONS.index('Open'); key(k.BUTTON_CENTER)
assert a.page == 'open' and 'fit-1' in a.files
a.menu_index = a.files.index('fit-1'); key(k.BUTTON_CENTER)
assert a.model['plane'] == 'strain' and len(a.model['bodies']) == 2
key(k.BUTTON_F9); assert a.help_open
for _ in range(80): key(k.BUTTON_DOWN)
key(k.BUTTON_F9)
print('PASS: typed values, Custom material, given/find toggles, add/remove, speed, preview focus, plot, results, save/open')

# Every template in both views and pages draws without errors.
for t in range(len(dm.TEMPLATES)):
    a.replace_model(dm.template(t))
    for view in ('section', '3d'):
        a.view = view
        for pitch in (-90, 0, 35, 90):
            a.pitch = pitch; a.info = pitch == 35; a.draw()
    for page in ('plot', 'results'):
        a.page = page; a.draw()
    a.page = 'model'
a.model['radii'][1] = a.model['radii'][0]; a.resolve(); a.draw()
assert a.problem
print('PASS: all templates draw in section and 3D, plots and results; a broken model shows its problem')

# Leaving keeps the model for the next visit.
a.replace_model(dm.template(2))
key(k.BUTTON_ESCAPE); assert vm.current_view.name == 'parent' and app._active is None
app.show(vm); assert app._active.model['radii'] == dm.template(2)['radii']
key(k.BUTTON_ESCAPE)
print('PASS: ESC leaves; the model comes back on the next visit')
