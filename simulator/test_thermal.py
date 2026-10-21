"""Thermal: 2D heat conduction model, then the screen and its keys.

Run with the desktop MicroPython build, from the project root.
"""
import os, sys
from math import exp
from time import ticks_ms
root = os.getcwd()
for part in ('src/MicroPython', 'simulator/hardware', 'builds/MicroPython/apps_unfrozen'):
    sys.path.insert(0, root + '/' + part)
import sim_runtime
sim_runtime.configure(root, '/private/tmp/gungos-thermal-' + str(ticks_ms()), root + '/builds/MicroPython/apps_unfrozen',
                      1, 'picocalc-pico2w', 0, True, False, False, False, '',
                      _network_mode='offline', _audio_mode='silent', _sd_profile='clean')
from picoware.system.view_manager import ViewManager
from picoware.system.view import View
from picoware.system.input import Input
from picoware.system import buttons as k
from engtools.thermal import model as tm
Input.button = property(lambda self: self._last_button)


def near(a, b, tol=0.01):
    assert abs(a - b) <= tol * max(abs(a), abs(b), 1e-9), (a, b)


def solve(state, budget=10000):
    plate = tm.Plate(state)
    while not plate.advance(budget):
        pass
    return plate


def state_with(**changes):
    state = tm.new_state()
    sides = changes.pop('sides', None)
    state.update(changes)
    for index, values in (sides or {}).items():
        state['sides'][index].update(values)
    return state


# One-dimensional slab: linear profile, flux k*A*dT/L, energy balance.
plate = solve(tm.new_state())
stats = plate.stats()
near(stats['max'], 100 - 100 / 48, 0.02)   # first cell centre, half a cell from the left edge
near(plate.temperature(0, plate.nx // 2) + 0.0, 100 - 100 * (plate.nx // 2 + 0.5) / plate.nx, 0.02)
flows = plate.flows()
expected = 167.0 * 0.06 * 0.010 * 100 / 0.1
near(flows['sides'][0], expected)
near(flows['sides'][1], -expected)
assert abs(flows['net']) < 1e-3 * flows['scale']
assert abs(flows['sides'][2]) + abs(flows['sides'][3]) < 1e-6
print('PASS: 1D slab temperature, heat flow and balance')

# Uniform generation, both ends fixed: T(centre) = T0 + q L^2 / (8 k).
state = state_with(gen=2e6, sides={0: {'kind': tm.TEMPERATURE, 'T': 20.0}, 1: {'kind': tm.TEMPERATURE, 'T': 20.0}})
plate = solve(state)
near(plate.stats()['max'] - 20, 2e6 * 0.1 ** 2 / (8 * 167.0), 0.03)
flows = plate.flows()
near(flows['generated'], 2e6 * 0.1 * 0.06 * 0.010)
assert abs(flows['net']) < 1e-3 * flows['scale']
print('PASS: generation parabola and energy balance')

# Wall with convection both sides: q = dT / (L/k + 1/h1 + 1/h2).
state = state_with(W=200.0, H=40.0, k=0.72, mat=9, res=0, sides={
    0: {'kind': tm.CONVECTION, 'T': 20.0, 'h': 8.0}, 1: {'kind': tm.CONVECTION, 'T': -5.0, 'h': 25.0}})
plate = solve(state)
flux = 25.0 / (0.2 / 0.72 + 1 / 8.0 + 1 / 25.0)
near(plate.flows()['sides'][0], flux * 0.04 * 0.010, 0.01)
print('PASS: wall with convection (U value)')

# Symmetric corner: equal fixed temperatures on two sides are the same on the diagonal.
state = state_with(W=60.0, H=60.0, sides={0: {'kind': tm.TEMPERATURE, 'T': 100.0},
                                          2: {'kind': tm.TEMPERATURE, 'T': 100.0},
                                          1: {'kind': tm.TEMPERATURE, 'T': 0.0},
                                          3: {'kind': tm.TEMPERATURE, 'T': 0.0}})
plate = solve(state)
n = plate.nx
mid = plate.temperature(n // 2, n // 2)
assert 45 < mid < 55, mid
near(plate.temperature(2, 5), plate.temperature(5, 2), 1e-3)
print('PASS: symmetric corner problem')

# Lumped cooling: a conductive body in air follows exp(-t/tau).
state = state_with(mode='transient', W=40.0, H=40.0, mat=0, k=400.0, rho=8960.0, cp=385.0, T0=200.0, tend=300.0,
                   res=0, sides={0: {'kind': tm.CONVECTION, 'T': 20.0, 'h': 100.0},
                                1: {'kind': tm.CONVECTION, 'T': 20.0, 'h': 100.0},
                                2: {'kind': tm.CONVECTION, 'T': 20.0, 'h': 100.0},
                                3: {'kind': tm.CONVECTION, 'T': 20.0, 'h': 100.0}})
tau = 8960.0 * 385.0 * 0.01 / 100.0
plate = solve(state)
near(plate.time, 300.0)
near(plate.stats()['mean'], 20 + 180 * exp(-300.0 / tau), 0.03)
print('PASS: lumped transient cooling')

# A steady state is the long-time limit of the transient.
state = state_with(mode='transient', tend=3000.0, res=0)
late = solve(state).stats()
steady = solve(state_with(res=0)).stats()
near(late['mean'], steady['mean'], 0.01)
print('PASS: transient reaches the steady state')

# Heat patch: the power is kept at any grid.
for res in range(len(tm.RESOLUTIONS)):
    plate = tm.Plate(state_with(pq=4e6, px=10.0, py=10.0, pw=10.0, ph=10.0, res=res, sides={
        0: {'kind': tm.CONVECTION, 'T': 25.0, 'h': 25.0}}))
    near(plate.flows()['generated'], 4e6 * 0.01 * 0.01 * 0.010, 1e-4)
print('PASS: patch power independent of the grid')

# A weakly cooled plate (small Biot number) converges quickly and balances: 2 W out through 4 x h = 25 edges.
state = state_with(W=60.0, H=60.0, depth=5.0, pq=4e6, px=25.0, py=25.0, pw=10.0, ph=10.0, res=2,
                   sides={i: {'kind': tm.CONVECTION, 'T': 25.0, 'h': 25.0} for i in range(4)})
plate = solve(state)
assert plate.converged and plate.iterations < 800, plate.iterations
flows = plate.flows()
near(flows['generated'], 2.0, 1e-4)
assert abs(flows['net']) < 1e-3 * flows['scale'], flows
assert 80 < plate.stats()['mean'] < 100, plate.stats()
print('PASS: weakly cooled plate converges (%d iterations) and balances' % plate.iterations)

# Problems are named, not solved.
for bad, words in ((state_with(sides={0: {'kind': tm.INSULATED}, 1: {'kind': tm.INSULATED}}), 'Steady'),
                   (state_with(pq=1e6, px=90.0, pw=20.0), 'patch'),
                   (state_with(W=-5.0), 'positive'),
                   (state_with(sides={0: {'kind': tm.CONVECTION, 'h': 0.0}}), 'h')):
    try:
        tm.Plate(bad)
    except ValueError as exc:
        assert words in str(exc), exc
    else:
        raise AssertionError('accepted ' + words)
print('PASS: unsolvable problems are refused with a reason')


# ---------------------------------------------------------------- UI
vm = ViewManager(); vm._wifi = None
vm.add(View('parent', lambda vm: None, lambda vm: True, lambda vm: None)); vm.switch_to('parent')
from engtools import session
session.kept.pop('thermal', None)
from engtools.thermal import app


def key(button):
    vm.input_manager._last_button = button
    vm.run()


def text(value):
    for c in value:
        key(vm.input_manager._key_to_button(ord(c)))


def settle(limit=3000):
    for _ in range(limit):
        key(k.BUTTON_NONE)
        if not a.running:
            return
    raise AssertionError('still running: ' + a.status())


def row_label():
    return a.current()[1]


app.show(vm)
a = app._active
assert vm.current_view.name == 'thermal_view' and vm.current_view.help
settle()
assert a.plate.done and a.plate.converged and 'Converged' in a.message
# Typing replaces a value, arithmetic works, and a steady state re-solves by itself.
while row_label() != 'Width':
    key(k.BUTTON_DOWN)
text('50*2'); key(k.BUTTON_CENTER)
assert a.state['W'] == 100.0 and a.edit is None and a.plate.iterations
settle()
# Editing the conductivity makes the material Custom.
while row_label() != 'Conductivity k':
    key(k.BUTTON_DOWN)
text('200'); key(k.BUTTON_CENTER)
assert tm.MATERIALS[a.state['mat']][0] == 'Custom' and a.state['k'] == 200.0
settle()
# A rejected value keeps the edit open with the error shown.
while row_label() != 'Width':
    key(k.BUTTON_UP)
text('-5'); key(k.BUTTON_CENTER)
assert a.error and a.edit is not None; key(k.BUTTON_ESCAPE); assert a.edit is None and a.state['W'] == 100.0
# Side conditions add and remove their rows.
while row_label() != 'Condition':
    key(k.BUTTON_DOWN)
key(k.BUTTON_CENTER); assert a.popup is not None
assert a.state['sides'][0]['kind'] == tm.TEMPERATURE and 'Coefficient h' not in [r[1] for r in a.rows()]
key(k.BUTTON_DOWN); key(k.BUTTON_CENTER)    # Temperature -> Convection
assert a.state['sides'][0]['kind'] == tm.CONVECTION
assert 'Coefficient h' in [r[1] for r in a.rows()]
settle()
# Worked-out rows refuse editing with a message.
while row_label() != 'Highest':
    key(k.BUTTON_DOWN)
key(k.BUTTON_CENTER); assert a.error and a.edit is None
# M switches to transient: it waits for SPACE, runs, finishes and can be paused.
text('m'); assert a.state['mode'] == 'transient' and not a.running and a.plate is not None
a.state['tend'], a.state['res'] = 20000.0, 3
a.restart(); text(' '); assert a.running
key(k.BUTTON_ESCAPE); assert not a.running and vm.current_view.name == 'thermal_view'
a.state['tend'], a.state['res'] = 60.0, 0
a.restart(); text(' '); settle()
assert a.plate.done and 'Finished' in a.message
assert 'Stored rate' in [r[1] for r in a.rows()]
# Examples all solve (a transient after SPACE); F6 moves the probe.
for index in range(len(app.EXAMPLES)):
    key(k.BUTTON_F3); assert a.popup is not None
    a.popup[2] = index; key(k.BUTTON_CENTER)
    assert a.plate is not None, (index, a.message)
    if a.state['mode'] == 'transient':
        text(' ')
    settle()
    assert a.plate.done, index
key(k.BUTTON_F6); assert a.focus == 'field'
before = list(a.probe); key(k.BUTTON_RIGHT); key(k.BUTTON_UP); assert a.probe[0] > before[0] and a.probe[1] > before[1]
key(k.BUTTON_ESCAPE); assert a.focus == 'list'
text('c'); assert a.bands
# An unsolvable plate says why instead of drawing a field.
a.state['sides'] = [{'kind': tm.INSULATED, 'T': 20.0, 'h': 25.0, 'q': 0.0} for _ in range(4)]
a.state['mode'] = 'steady'; a.restart(); a.draw()
assert a.plate is None and a.error and 'Steady' in a.message
key(k.BUTTON_ESCAPE); assert vm.current_view.name == 'parent'
print('PASS: typed values, side conditions, steady/transient, examples, probe, errors')
