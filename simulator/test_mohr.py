"""Mohr circle: stress transformation, principal stresses, keys and drawing.

Run with the desktop MicroPython build, from the project root.
"""
import os, sys
from math import sqrt
from time import ticks_ms
root = os.getcwd()
for part in ('src/MicroPython', 'simulator/hardware', 'builds/MicroPython/apps_unfrozen'):
    sys.path.insert(0, root + '/' + part)
import sim_runtime
sim_runtime.configure(root, '/private/tmp/gungos-mohr-' + str(ticks_ms()), root + '/builds/MicroPython/apps_unfrozen',
                      1, 'picocalc-pico2w', 0, True, False, False, False, '',
                      _network_mode='offline', _audio_mode='silent', _sd_profile='clean')
from picoware.system.view_manager import ViewManager
from picoware.system.view import View
from picoware.system.input import Input
from picoware.system import buttons as k
from engtools.mohr import stress
Input.button = property(lambda self: self._last_button)


def near(a, b, tol=2e-4):
    assert abs(a - b) <= tol * max(1.0, abs(a), abs(b)), (a, b)


# ---------------------------------------------------------------- math
st = stress.new_state()
st['s'] = [80.0, -40.0, 0.0, 30.0, 0.0, 0.0]
r = stress.results(st)
R = sqrt(60 ** 2 + 30 ** 2)
near(r['p1'], 20 + R); near(r['p2'], 20 - R); near(r['radius'], R)
near(r['s1'], 20 + R); assert r['s2'] == 0.0; near(r['s3'], 20 - R)
near(r['mises'], sqrt(80 ** 2 - 80 * -40 + 40 ** 2 + 3 * 30 ** 2))
near(r['tresca'], 2 * R)
# Rotating by theta: sx' = a + b cos2t + txy sin2t, txy' = -b sin2t + txy cos2t.
st['theta'] = 30.0
r = stress.results(st)
near(r['si'], 20 + 60 * 0.5 + 30 * sqrt(3) / 2)
near(r['tij'], -60 * sqrt(3) / 2 + 30 * 0.5)
near(r['si'] + r['sj'], 40.0)
# Principal axes: no shear; sx' is the larger stress; the second press swaps.
st['theta'] = stress.principal_angle(st)
r = stress.results(st)
near(r['tij'], 0.0, 1e-4); near(r['si'], r['p1'])
st['theta'] = stress.principal_angle(st, True)
r = stress.results(st)
near(r['si'], r['p2']); near(r['tij'], 0.0, 1e-4)
st['theta'] = stress.shear_angle(st)
r = stress.results(st)
near(abs(r['tij']), R); near(r['si'], 20.0)
print('PASS: 2D transformation, principal and maximum shear axes, von Mises and Tresca')

# 3D: eigenvalues match invariants; rotation about each axis keeps them.
st = {'mode': '3D', 's': [60.0, 20.0, -30.0, 25.0, 10.0, -15.0], 'theta': 0.0, 'axis': 'z', 'yield': 250.0}
r = stress.results(st)
s1, s2, s3 = r['s1'], r['s2'], r['s3']
assert s1 >= s2 >= s3
near(s1 + s2 + s3, 50.0)
I2 = 60 * 20 + 20 * -30 + -30 * 60 - 25 ** 2 - 10 ** 2 - 15 ** 2
near(s1 * s2 + s2 * s3 + s3 * s1, I2, 1e-3)
T = stress.tensor(st)
det = (T[0][0] * (T[1][1] * T[2][2] - T[1][2] ** 2) - T[0][1] * (T[0][1] * T[2][2] - T[1][2] * T[0][2]) +
       T[0][2] * (T[0][1] * T[1][2] - T[1][1] * T[0][2]))
near(s1 * s2 * s3, det, 1e-3)
near(r['mises'], sqrt(0.5 * ((60 - 20) ** 2 + (20 + 30) ** 2 + (-30 - 60) ** 2) + 3 * (25 ** 2 + 10 ** 2 + 15 ** 2)))
near(r['n_mises'], 250 / r['mises']); near(r['n_tresca'], 250 / (s1 - s3))
for ax in 'xyz':
    st['axis'], st['theta'] = ax, 37.0
    q = stress.results(st)
    near(q['s1'], s1); near(q['s3'], s3)
    i, j = stress.plane(st)
    M = stress.rotated(st)
    near(M[0][0] + M[1][1] + M[2][2], 50.0)
    # The in-plane point lies on its circle.
    near((q['si'] - q['centre']) ** 2 + q['tij'] ** 2, q['radius'] ** 2, 1e-3)
# Rotation about x turns y toward z: a pure syz state at 45 deg gives sy' = tyz.
st = {'mode': '3D', 's': [0.0, 0.0, 0.0, 0.0, 40.0, 0.0], 'theta': 45.0, 'axis': 'x', 'yield': 0.0}
q = stress.results(st)
near(q['si'], 40.0); near(q['sj'], -40.0); near(q['tij'], 0.0, 1e-4)
assert 'n_mises' not in q
# Repeated principal values and the zero state need no special care.
for s in ([-50.0, -50.0, -50.0, 0.0, 0.0, 0.0], [0.0] * 6, [10.0, 10.0, 0.0, 0.0, 0.0, 0.0]):
    q = stress.results({'mode': '3D', 's': s, 'theta': 0.0, 'axis': 'z', 'yield': 100.0})
    assert q['s1'] >= q['s2'] >= q['s3']
print('PASS: 3D principal stresses match the invariants and survive rotation about x, y and z')

# ---------------------------------------------------------------- UI
vm = ViewManager(); vm._wifi = None
vm.add(View('parent', lambda vm: None, lambda vm: True, lambda vm: None)); vm.switch_to('parent')
from engtools import session
session.kept.pop('mohr', None)
from engtools.mohr import app


def key(button):
    vm.input_manager._last_button = button
    vm.run()


def text(value):
    for c in value:
        key(vm.input_manager._key_to_button(ord(c)))


def row_label():
    return a.current()[1]


app.show(vm)
a = app._active
assert vm.current_view.name == 'mohr_view'
assert row_label() == 'Normal sx'
# Typing replaces a stress; arithmetic works; DOWN applies and moves on.
text('100'); key(k.BUTTON_DOWN)
assert a.state['s'][0] == 100.0 and row_label() == 'Normal sy'
text('-60/2'); key(k.BUTTON_CENTER)
assert a.state['s'][1] == -30.0
key(k.BUTTON_DOWN); text('40'); key(k.BUTTON_CENTER)
assert a.state['s'][3] == 40.0
# Arrows turn the element; P lands on the principal axes, S on max shear.
key(k.BUTTON_TAB); key(k.BUTTON_RIGHT); key(k.BUTTON_RIGHT); assert a.state['theta'] == 2.0
text(']'); assert a.state['theta'] == 17.0
text('p'); near(a.result['tij'], 0.0, 1e-4); near(a.result['si'], a.result['p1'])
text('p'); near(a.result['si'], a.result['p2'])
text('s'); near(abs(a.result['tij']), a.result['radius'])
text('r'); assert a.state['theta'] == 0.0
key(k.BUTTON_TAB)
# Worked-out rows refuse editing with a message instead of an error box.
while row_label() != 'von Mises':
    key(k.BUTTON_DOWN)
key(k.BUTTON_CENTER); assert a.error and a.edit is None
# Yield strength enables safety factors.
key(k.BUTTON_DOWN); key(k.BUTTON_DOWN); assert row_label() == 'Yield strength'
text('250'); key(k.BUTTON_CENTER)
assert [r for r in a.rows() if r[1] == 'Safety, von Mises']
# A rejected value keeps the edit open with the error shown.
text('-5'); key(k.BUTTON_CENTER)
assert a.error and a.edit is not None; key(k.BUTTON_ESCAPE); assert a.edit is None and a.state['yield'] == 250.0
# M switches to 3D: six stresses and an axis appear; A cycles the axis.
text('m'); assert a.state['mode'] == '3D'
labels = [r[1] for r in a.rows()]
for name in ('Normal sz', 'Shear tyz', 'Shear tzx', 'About axis', 'Principal s3'):
    assert name in labels, name
text('a'); assert a.state['axis'] == 'x'
assert "Rotated sy'" in [r[1] for r in a.rows()]
# F3 examples fill a state.
key(k.BUTTON_F3); key(k.BUTTON_CENTER); assert a.popup is not None
for _ in range(4): key(k.BUTTON_DOWN)
key(k.BUTTON_CENTER); assert a.state['s'] == [60.0, 20.0, -30.0, 25.0, 10.0, -15.0]
text('m'); assert a.state['mode'] == '2D' and a.message
text('a'); assert a.error  # 2D turns about z only
# Help opens over everything and closes with F9.
key(k.BUTTON_F9); assert a.help_open
for _ in range(40): key(k.BUTTON_DOWN)
key(k.BUTTON_F9); assert not a.help_open
print('PASS: typed stresses, rotation keys, principal/shear jumps, yield check, 2D/3D, examples and help')

# Every state draws inside the screen without errors, including degenerate ones.
for mode in ('2D', '3D'):
    for s in ([0.0] * 6, [-50.0, -50.0, -50.0, 0.0, 0.0, 0.0], [1e-3, 0.0, 0.0, 0.0, 0.0, 0.0],
              [500.0, -2.0, 300.0, 1.0, 400.0, -7.0], [0.0, 0.0, 0.0, 50.0, 0.0, 0.0]):
        a.state['mode'], a.state['s'] = mode, list(s)
        for theta in (0.0, 33.0, -135.0, 180.0):
            for ax in 'xyz':
                a.state['theta'], a.state['axis'] = theta, ax
                a.solve(); a.draw()
print('PASS: 2D and 3D drawings for zero, hydrostatic, tiny, large and pure-shear states at any angle')

# Leaving keeps the state for the next visit while PicoLAB is open.
a.state['s'] = [11.0, 22.0, 0.0, 3.0, 0.0, 0.0]
key(k.BUTTON_ESCAPE)
assert vm.current_view.name == 'parent' and app._active is None
app.show(vm)
assert app._active.state['s'][:2] == [11.0, 22.0]
key(k.BUTTON_ESCAPE)
print('PASS: ESC leaves; the stress state comes back on the next visit')
