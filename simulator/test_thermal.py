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

# Heat patches: each keeps its power in W at any grid, and several add up.
chip = {'P': 0.4, 'x': 10.0, 'y': 10.0, 'w': 10.0, 'h': 10.0}
for res in range(len(tm.RESOLUTIONS)):
    plate = tm.Plate(state_with(patches=[dict(chip)], res=res, sides={0: {'kind': tm.CONVECTION, 'T': 25.0, 'h': 25.0}}))
    near(plate.flows()['generated'], 0.4, 1e-4)
plate = tm.Plate(state_with(patches=[dict(chip), dict(chip, P=1.1, x=60.0, w=0.5, h=0.5)]))
near(plate.flows()['generated'], 1.5, 1e-4)
assert plate.patch_cells[1] == 1   # smaller than a cell: heats the cell it sits in
print('PASS: patch power independent of the grid, several patches')

# A weakly cooled plate (small Biot number) converges quickly and balances: 2 W out through 4 x h = 25 edges.
state = state_with(W=60.0, H=60.0, depth=5.0, res=2, patches=[{'P': 2.0, 'x': 25.0, 'y': 25.0, 'w': 10.0, 'h': 10.0}],
                   sides={i: {'kind': tm.CONVECTION, 'T': 25.0, 'h': 25.0} for i in range(4)})
plate = solve(state)
assert plate.converged and plate.iterations < 800, plate.iterations
flows = plate.flows()
near(flows['generated'], 2.0, 1e-4)
assert abs(flows['net']) < 1e-3 * flows['scale'], flows
assert 80 < plate.stats()['mean'] < 100, plate.stats()
print('PASS: weakly cooled plate converges (%d iterations) and balances' % plate.iterations)

# The slab's flux at a cell is k dT/L towards the cold side; profiles follow the field.
plate = solve(tm.new_state())
qx, qy = plate.flux(plate.ny // 2, plate.nx // 2)
near(qx, 167.0 * 100 / 0.1, 0.01)
assert abs(qy) < 1e-3 * qx
row, column = plate.row(0), plate.column(3)
assert len(row) == plate.nx and len(column) == plate.ny and row[0] > row[-1]
near(column[0], column[-1], 1e-4)
j, i = plate.cell(*plate.centre(3, 7))
assert (j, i) == (3, 7), (j, i)
print('PASS: flux at a cell, row and column profiles, cells and centres')

# A transient keeps a short history from the start to the end time.
plate = solve(state_with(mode='transient', tend=60.0, res=0))
history = plate.history
assert history[0][0] == 0 and abs(history[-1][0] - 60.0) < 1e-6, (history[0], history[-1])
assert 2 <= len(history) <= tm.HISTORY + 2 and all(a[0] < b[0] for a, b in zip(history, history[1:]))
assert all(row[1] <= row[2] <= row[3] for row in history)
print('PASS: transient history (%d samples)' % len(history))

# Saved cases: a round trip keeps everything; damaged entries and the first version's patch are handled.
state = state_with(mode='transient', W=80.0, patches=[dict(chip)], sides={2: {'kind': tm.FLUX, 'q': 300.0}})
again = tm.from_case(tm.to_case(state))
assert again == state, (again, state)
broken = tm.from_case({'tool': 'thermal', 'W': 'wide', 'res': 99, 'mat': -3, 'mode': 'odd',
                       'sides': [{'kind': 17, 'T': 'hot'}], 'patches': [{'P': 1.0}, 'x']})
assert broken['W'] == 100.0 and broken['res'] == len(tm.RESOLUTIONS) - 1 and broken['mat'] == 0
assert broken['mode'] == 'steady' and broken['sides'][0]['kind'] == len(tm.KINDS) - 1 and broken['patches'] == []
old = tm.from_case({'pq': 4e6, 'px': 25.0, 'py': 25.0, 'pw': 10.0, 'ph': 10.0, 'depth': 5.0})
near(old['patches'][0]['P'], 2.0, 1e-9)
print('PASS: saved cases round trip, damaged values and the old patch')

# Problems are named, not solved.
for bad, words in ((state_with(sides={0: {'kind': tm.INSULATED}, 1: {'kind': tm.INSULATED}}), 'Steady'),
                   (state_with(patches=[dict(chip, x=95.0)]), 'Patch 1'),
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
# Nothing solves until F6; then the steady state converges.
for _ in range(5):
    key(k.BUTTON_NONE)
assert a.plate is None and not a.running and a.page == 'model' and a.tab == 0
key(k.BUTTON_F6); assert a.plate is not None
settle()
assert a.plate.done and a.plate.converged and 'Converged' in a.message
# Typing replaces a value, arithmetic works, and an edit clears the field.
assert row_label() == 'Width'
text('50*2'); key(k.BUTTON_CENTER)
assert a.state['W'] == 100.0 and a.edit is None and a.plate is None and a.undo
# Editing the conductivity makes the material Custom; Z undoes it.
while row_label() != 'Conductivity k':
    key(k.BUTTON_DOWN)
text('200'); key(k.BUTTON_CENTER)
assert tm.MATERIALS[a.state['mat']][0] == 'Custom' and a.state['k'] == 200.0
text('z'); assert a.state['k'] == 167.0 and tm.MATERIALS[a.state['mat']][0] == 'Aluminium 6061'
# A rejected value keeps the edit open with the error shown.
while row_label() != 'Width':
    key(k.BUTTON_UP)
text('-5'); key(k.BUTTON_CENTER)
assert a.error and a.edit is not None; key(k.BUTTON_ESCAPE); assert a.edit is None and a.state['W'] == 100.0
# RIGHT opens Sides; the condition choice adds and removes rows, [ ] cycles it.
key(k.BUTTON_RIGHT); assert a.tab == 1 and row_label() == 'Condition'
assert a.chosen() == (0, None)
key(k.BUTTON_CENTER); assert a.popup is not None
key(k.BUTTON_DOWN); key(k.BUTTON_CENTER)    # Temperature -> Convection
assert a.state['sides'][0]['kind'] == tm.CONVECTION and 'Coefficient h' in [r[1] for r in a.rows()]
text(']'); assert a.state['sides'][0]['kind'] == tm.FLUX and row_label() == 'Condition'
text('['); text('['); assert a.state['sides'][0]['kind'] == tm.TEMPERATURE
# Sources: F1 adds patches up to the limit, F2 removes the selected one.
key(k.BUTTON_RIGHT); assert a.tab == 2 and row_label() == 'Whole plate'
key(k.BUTTON_F2); assert a.error
for n in range(tm.MAX_PATCHES):
    key(k.BUTTON_F1)
    assert len(a.state['patches']) == n + 1 and row_label() == 'Power'
key(k.BUTTON_F1); assert a.error and len(a.state['patches']) == tm.MAX_PATCHES
assert a.chosen() == (None, tm.MAX_PATCHES - 1)
text('3'); key(k.BUTTON_CENTER); assert a.state['patches'][-1]['P'] == 3.0
key(k.BUTTON_F2); assert len(a.state['patches']) == tm.MAX_PATCHES - 1
text('z'); assert len(a.state['patches']) == tm.MAX_PATCHES and a.state['patches'][-1]['P'] == 3.0
# Solve tab: M switches to transient; a transient runs, pauses on ESC and finishes.
key(k.BUTTON_RIGHT); assert a.tab == 3 and row_label() == 'Mode'
text('m'); assert a.state['mode'] == 'transient' and a.plate is None
assert 'End time' in [r[1] for r in a.rows()]
a.state['tend'], a.state['res'] = 20000.0, 3
key(k.BUTTON_F6); assert a.running
key(k.BUTTON_ESCAPE); assert not a.running and vm.current_view.name == 'thermal_view'
text(' '); assert a.running
a.state['tend'], a.state['res'] = 60.0, 0
key(k.BUTTON_F6); settle()
assert a.plate.done and 'Finished' in a.message
# F5: results with heat flows and the stored rate; ENTER on Highest opens the plots there.
key(k.BUTTON_F5); assert a.page == 'results'
labels = [r[0] for r in a.result_rows()]
assert 'Stored rate' in labels and 'Left side' in labels and 'Fourier number' in labels
while a.result_rows()[a.menu_index][0] != 'Highest':
    key(k.BUTTON_DOWN)
key(k.BUTTON_CENTER); assert a.page == 'plots'
hot = a.plate.stats()['hot']; assert a.probe_cell() == hot
# F4: arrows move the cursor, TAB visits hottest and coldest, ENTER pins, D changes the view.
key(k.BUTTON_LEFT); assert a.probe_cell() == (hot[0], max(0, hot[1] - 1))
key(k.BUTTON_TAB); assert a.probe_cell() == hot
key(k.BUTTON_TAB); assert a.probe_cell() == a.plate.stats()['cold']
key(k.BUTTON_CENTER); assert len(a.pins) == 1
key(k.BUTTON_CENTER); assert len(a.pins) == 1
assert a.views() == app.PLOT_VIEWS
for view in app.PLOT_VIEWS:
    text('d'); a.draw()
key(k.BUTTON_F5); assert 'Pinned points' in [r[0] for r in a.result_rows()]
while a.result_rows()[a.menu_index][4] is None or a.result_rows()[a.menu_index][4][0] != 'pin':
    key(k.BUTTON_DOWN)
key(k.BUTTON_F2); assert not a.pins
key(k.BUTTON_ESCAPE); assert a.page == 'model'
# F3: examples all load without solving and all solve with F6.
for index in range(len(app.EXAMPLES)):
    key(k.BUTTON_F3); assert a.page == 'options'
    key(k.BUTTON_CENTER); assert a.page == 'examples'
    a.menu_index = index; key(k.BUTTON_CENTER)
    assert a.page == 'model' and a.plate is None, (index, a.message)
    key(k.BUTTON_F6); settle()
    assert a.plate.done, index
    for tab in range(4):
        a.tab = tab; a.draw()
    for page in (k.BUTTON_F4, k.BUTTON_F5):
        key(page); a.draw()
    key(k.BUTTON_ESCAPE)
# Files: save, open it back, export the field, profiles and history.
key(k.BUTTON_F3)
while app.OPTIONS[a.menu_index][0] != 'Save':
    key(k.BUTTON_DOWN)
key(k.BUTTON_CENTER); assert a.prompt is not None
for _ in range(10):
    key(k.BUTTON_BACKSPACE)
text('cooling'); key(k.BUTTON_CENTER); assert a.prompt is None and 'Saved' in a.message, a.message
saved = tm.copy_state(a.state)
a.state['W'] = 10.0
key(k.BUTTON_F3)
while app.OPTIONS[a.menu_index][0] != 'Open':
    key(k.BUTTON_DOWN)
key(k.BUTTON_CENTER); assert a.page == 'open' and 'cooling' in a.files
a.menu_index = a.files.index('cooling'); key(k.BUTTON_CENTER)
assert a.page == 'model' and a.state == saved and a.plate is None
key(k.BUTTON_F6); settle()
for option in ('Export field CSV', 'Export profiles CSV (Eggcel)', 'Export history CSV (Eggcel)'):
    key(k.BUTTON_F3)
    while app.OPTIONS[a.menu_index][0] != option:
        key(k.BUTTON_DOWN)
    key(k.BUTTON_CENTER); assert 'Exported' in a.message and not a.error, (option, a.message)
key(k.BUTTON_ESCAPE)
files = vm.storage.listdir('picoware/engineering/exports')
assert any(name.startswith('cooling-history') for name in files), files
data = vm.storage.read('picoware/engineering/exports/' + [n for n in files if n.startswith('cooling-history')][0])
assert data.startswith('t_s,min_C,mean_C,max_C') and len(data.split('\n')) * 4 <= 512
# The inputs survive closing the tool; an unsolvable plate says why.
key(k.BUTTON_ESCAPE); assert vm.current_view.name == 'parent'
app.show(vm); a = app._active
assert a.state == saved and a.plate is None
a.state['sides'] = [{'kind': tm.INSULATED, 'T': 20.0, 'h': 25.0, 'q': 0.0} for _ in range(4)]
a.state['mode'] = 'steady'; key(k.BUTTON_F6); a.draw()
assert a.plate is None and a.error and 'Steady' in a.message
key(k.BUTTON_F4); a.draw(); key(k.BUTTON_LEFT); assert a.error
key(k.BUTTON_ESCAPE); key(k.BUTTON_ESCAPE); assert vm.current_view.name == 'parent'
print('PASS: F6-only solving, tabs, choices, patches, undo, results, plots, pins, examples, files, errors')
