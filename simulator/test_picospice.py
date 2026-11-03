"""PicoSpice: the circuit model, then a circuit built and simulated by keys.

Run with the desktop MicroPython build, from the project root.
"""
import os, sys
from math import exp
from time import ticks_ms
root = os.getcwd()
for part in ('src/MicroPython', 'simulator/hardware', 'builds/MicroPython/apps_unfrozen'):
    sys.path.insert(0, root + '/' + part)
import sim_runtime
sim_runtime.configure(root, '/private/tmp/gungos-spice-' + str(ticks_ms()), root + '/builds/MicroPython/apps_unfrozen',
                      1, 'picocalc-pico2w', 0, True, False, False, False, '',
                      _network_mode='offline', _audio_mode='silent', _sd_profile='clean')
from picoware.system.view_manager import ViewManager
from picoware.system.view import View
from picoware.system.input import Input
from picoware.system import buttons as k
from engtools.spice import model as sm, items
Input.button = property(lambda self: self._last_button)


def near(got, want, tol=1e-6):
    assert abs(got - want) <= tol * max(1.0, abs(want)), (got, want)


def run(c):
    s = sm.Simulation(c)
    while not s.advance(1000):
        pass
    return s


# ---------------------------------------------------------------- the model

for typed, want in (('4.7k', 4700), ('10u', 1e-5), ('2meg', 2e6), ('1m', 1e-3), ('100n', 1e-7), ('2*5', 10),
                    ('1e3', 1e3), ('-3.3', -3.3), ('1.5\xb5', 1.5e-6)):
    near(sm.parse_value(typed), want, 1e-6)
for value, unit, shown in ((5e-3, 's', '5 ms'), (4700, 'ohm', '4.7 kohm'), (2e6, 'V', '2 MV'), (2e6, '', '2Meg'),
                           (1e-6, '', '1u'), (0, 'V', '0 V'), (-0.25, 'V', '-250 mV')):
    assert sm.eng(value, unit) == shown, (value, unit, sm.eng(value, unit))
    if not unit:
        near(sm.parse_value(shown), value, 1e-6)   # shown values type back
print('PASS: SPICE values typed and shown')

# Wires join nodes into one net; grounded nodes share net 0; a node only
# wires touch stays out of the equations.
c = sm.example(3)        # rectifier: C and R joined by a wire
net, count = sm.nets(c)
assert net[sm.node_at(c, 3, 0)] == net[sm.node_at(c, 6, 0)] > 0
assert all(net[i] == 0 for i, n in enumerate(c['nodes']) if n[2])
sm.add_node(c, 9, 9)
sm.new_element(c, 'W', [len(c['nodes']) - 1, 0])
net, count2 = sm.nets(c)
assert count2 == count and net[-1] == net[0]
print('PASS: nets from wires and grounds')

# Every example simulates; spot values against hand calculations.
results = [run(sm.example(i)) for i in range(len(sm.EXAMPLES))]
near(results[0].op['nodes'][sm.node_at(sm.example(0), 4, 0)], 7.5)
rc = results[1]
for i in range(0, rc.count, 10):
    t = rc.x(i)
    want = 0.0 if t <= 0.5e-3 else 5 * (1 - exp(-(t - 0.5e-3) / 1e-3))
    if t < 2.5e-3:
        near(rc.traces[1][i], want, 0.01)
near(results[3].stats(1)['max'], 9.27, 0.01)          # rectifier peak: 10 V less a diode
near(results[4].stats(1)['max'], 0.5 * 4.7, 0.01)     # inverting amplifier gain 4.7
assert results[5].stats(1)['min'] < 0.2                  # the transistor saturates
st = results[7].stats(0)
assert 0.7 < st['final'] < 0.8 and abs(st['min']) < 1e-6   # diode curve
print('PASS: all %d examples simulate; values match hand results' % len(results))

# Statistics of a sine: mean 0, RMS amplitude / sqrt 2.
c = sm.example(4)
c['probes'] = c['probes'][:1]
c['sim'].update(tstop=10e-3, tpoints=1001)
st = run(c).stats(0)
near(st['mean'], 0.0, 2e-3)
near(st['rms'], 0.5 / 2 ** 0.5, 2e-3)
near(st['pp'], 1.0, 1e-3)
print('PASS: final, extremes, mean, RMS and peak to peak')

# Saved cases round-trip; damaged ones keep what is valid.
for i in range(len(sm.EXAMPLES)):
    c = sm.example(i)
    again = sm.from_case(sm.to_case(c))
    assert again == sm.copy(c) or again['elements'] == c['elements'], i
broken = sm.from_case({'nodes': [[0, 0, True], [1, 'x', 0], [2, 0, False]], 'elements': [
    {'kind': 'R', 'nodes': [0, 1], 'values': {'R': 'big'}}, {'kind': 'Q', 'nodes': [0, 1]},
    {'kind': 'V', 'nodes': [0, 5]}], 'probes': [{'kind': 'V', 'a': 9, 'b': -1}], 'sim': {'kind': 'ac', 'tpoints': 7}})
assert len(broken['nodes']) == 2 and len(broken['elements']) == 1 and broken['elements'][0]['values']['R'] == 1e3
assert broken['probes'] == [] and broken['sim']['kind'] == 'tran' and broken['sim']['tpoints'] == 7
print('PASS: saved cases round trip; damaged ones are cleaned')

# Removing keeps references straight; problems are named before solving.
c = sm.example(2)        # RLC with a current probe on L1
L = next(i for i, e in enumerate(c['elements']) if e['kind'] == 'L')
sm.remove_element(c, 0)
assert c['probes'][-1]['element'] == L - 1
try:
    sm.remove_node(c, c['elements'][0]['nodes'][0])
except ValueError as exc:
    assert 'connected' in str(exc)
else:
    raise AssertionError('removed a connected node')
def unground(c):
    for n in c['nodes']:
        n[2] = False


def no_source(c):
    c['sim'].update(kind='dc', source=-1)


def shorted(c):
    pins = c['elements'][1]['nodes']
    pins[1] = pins[0]


for change, words in ((unground, 'Ground'), (no_source, 'sweep'), (shorted, 'one node')):
    c = sm.example(1)
    change(c)
    try:
        sm.Simulation(c)
    except sm.CircuitError as exc:
        assert words in str(exc), exc
    else:
        raise AssertionError(words)
c = sm.example(1)        # a capacitor to a node of its own: no DC path, named
sm.add_node(c, 8, 0)
sm.new_element(c, 'C', [sm.node_at(c, 4, 0), len(c['nodes']) - 1])
c['sim']['kind'] = 'op'
try:
    sm.Simulation(c)
except sm.CircuitError as exc:
    assert 'N%d has no DC path' % len(c['nodes']) in str(exc) and exc.node == len(c['nodes']) - 1, exc
else:
    raise AssertionError('floating node solved')
print('PASS: references after removal; problems named by node and element')


# ---------------------------------------------------------------- the screen

vm = ViewManager(); vm._wifi = None
vm.add(View('parent', lambda vm: None, lambda vm: True, lambda vm: None)); vm.switch_to('parent')
from engtools import session
session.kept.pop('spice', None)
from engtools.spice import app


def key(button):
    vm.input_manager._last_button = button
    vm.run()


def text(value):
    for ch in value:
        key(vm.input_manager._key_to_button(ord(ch)))


def settle(limit=3000):
    for _ in range(limit):
        key(k.BUTTON_NONE)
        if not a.running:
            return
    raise AssertionError('still running')


def row():
    r = a.current()
    return (r[0], r[5][0] if r[5] else None) if r else None


def to_field(field):
    for _ in range(30):
        if row() == ('field', field):
            return
        key(k.BUTTON_DOWN)
    raise AssertionError('no field ' + field)


def choose(field, label):
    """Open a choice, step through its live preview to label, accept."""
    to_field(field)
    key(k.BUTTON_CENTER)
    assert a.choice is not None
    for _ in range(len(a.choice['options'])):
        if a.choice['options'][a.choice['index']].startswith(label):
            key(k.BUTTON_CENTER)
            assert a.choice is None
            return
        key(k.BUTTON_DOWN)
    raise AssertionError('no option ' + label)


app.show(vm)
a = app._active
assert vm.current_view.name == 'spice_view' and vm.current_view.help and a.page == 'start'
key(k.BUTTON_CENTER)                       # Blank circuit
assert a.page == 'model' and not a.circuit['nodes']
# Four nodes from the grid cursor: TAB, arrows, F1.
key(k.BUTTON_TAB); assert a.view
for steps in ((), (k.BUTTON_RIGHT,) * 4, (k.BUTTON_DOWN,) * 3, (k.BUTTON_LEFT,) * 4):
    for b in steps:
        key(b)
    key(k.BUTTON_F1)
assert [n[:2] for n in a.circuit['nodes']] == [[0, 0], [4, 0], [4, 3], [0, 3]]
key(k.BUTTON_F1); assert a.error           # a node is already there
# The cursor selects what it lands on; ENTER returns to the list.
key(k.BUTTON_UP); key(k.BUTTON_UP); key(k.BUTTON_UP)
assert a.chosen_ref() == ('node', 0) and a.cursor == [0, 0]
key(k.BUTTON_CENTER); assert not a.view and a.tab == items.NODE
# Ground N4 and N3 (Node tab, Ground: Yes).
for node in (3, 2):
    a.select(('node', node))
    key(k.BUTTON_CENTER)                   # open the node
    choose('gnd', 'Yes')
    key(k.BUTTON_ESCAPE)                   # close it
    assert a.circuit['nodes'][node][2]
# A voltage source from N1, its minus pin moved to N4 with the live preview.
a.select(('node', 0))
key(k.BUTTON_RIGHT); assert a.tab == items.ELEMENT
key(k.BUTTON_F1); assert a.popup is not None
a.popup[2] = [kind[0] for kind in sm.KINDS].index('V'); key(k.BUTTON_CENTER)
v1 = a.circuit['elements'][0]
assert v1['name'] == 'V1' and v1['nodes'][0] == 0
choose('pin1', 'N4')
assert v1['nodes'] == [0, 3]
to_field('v:dc'); text('5'); key(k.BUTTON_CENTER); assert v1['values']['dc'] == 5.0
# R1 from N1 to N2 and C1 from N2 to N3, values typed with suffixes.
key(k.BUTTON_ESCAPE)
key(k.BUTTON_F1); a.popup[2] = 1; key(k.BUTTON_CENTER)       # Resistor
r1 = a.circuit['elements'][1]
assert r1['nodes'] == [0, 3], r1['nodes']     # from N1 to the nearest node, N4
choose('pin1', 'N2')
assert r1['nodes'] == [0, 1]
to_field('v:R'); text('2.2k'); key(k.BUTTON_CENTER); assert r1['values']['R'] == 2200.0
text('z'); assert a.circuit['elements'][1]['values']['R'] == 1e3   # undo
a.select(('node', 1)); key(k.BUTTON_RIGHT)
key(k.BUTTON_F1); a.popup[2] = 2; key(k.BUTTON_CENTER)       # Capacitor at N2
c1 = a.circuit['elements'][2]
choose('pin1', 'N3')
assert c1['nodes'] == [1, 2]
to_field('v:C'); text('1u'); key(k.BUTTON_CENTER)
# Probes: V(N2) and the current at N2 into C1.
key(k.BUTTON_RIGHT); assert a.tab == items.PROBE
key(k.BUTTON_F1); a.popup[2] = 0; key(k.BUTTON_CENTER)
assert a.circuit['probes'][0] == {'kind': 'V', 'a': 1, 'b': -1}
key(k.BUTTON_F1); a.popup[2] = 1; key(k.BUTTON_CENTER)
p2 = a.circuit['probes'][1]
choose('element', 'C1')
assert p2 == {'kind': 'I', 'node': 1, 'element': 2}
# Sim tab: a 5 ms transient from zero, 101 points.
key(k.BUTTON_RIGHT); assert a.tab == items.SIM
to_field('tstop'); text('5m'); key(k.BUTTON_CENTER)
to_field('tpoints'); text('101'); key(k.BUTTON_CENTER)
choose('uic', 'Zero')
near(a.circuit['sim']['tstop'], 5e-3)
assert a.circuit['sim'] == dict(sm.SIM_DEFAULTS, tstop=a.circuit['sim']['tstop'], tpoints=101, uic=True)
# F6 simulates in slices; the RC charges as 5 (1 - exp(-t / 1 ms)).
key(k.BUTTON_F6); assert a.sim is not None
settle()
assert a.sim.done and 'done' in a.message
for i in range(a.sim.count):
    t = a.sim.x(i)
    near(a.sim.traces[0][i], 5 * (1 - exp(-t / 1e-3)), 3e-3)
    if i:
        near(a.sim.traces[1][i], 5e-3 * exp(-t / 1e-3), 1e-2)
# F4: cursor, probe choice and peaks.
key(k.BUTTON_F4); assert a.page == 'plots'
key(k.BUTTON_LEFT); assert a.at == 99
text(','); assert a.at == 89
key(k.BUTTON_DOWN); assert a.active == 1
key(k.BUTTON_P); assert a.at == a.sim.stats(1)['at_max']
a.draw()
# F5: the final value, and ENTER on an extreme opens it in the plots.
key(k.BUTTON_F5); assert a.page == 'results'
rows = a.result_rows()
final = next(r for r in rows if r[0] == 'Final')
assert final[1].startswith('4.96'), final
while a.result_rows()[a.menu_index][0] != 'Minimum':
    key(k.BUTTON_DOWN)
key(k.BUTTON_CENTER); assert a.page == 'plots' and a.at == 0
key(k.BUTTON_ESCAPE); assert a.page == 'model'
# An edit clears the results; problems name the item and select it.
a.select(('node', 2)); key(k.BUTTON_CENTER); choose('gnd', 'No')
a.select(('node', 3)); key(k.BUTTON_CENTER); choose('gnd', 'No')
assert a.sim is None
key(k.BUTTON_F6); assert a.error and 'Ground' in a.message
text('z'); text('z')
key(k.BUTTON_F6); settle(); assert a.sim.done and not a.error
# F2 removes; a connected node is refused; Z undoes.
a.select(('node', 0)); key(k.BUTTON_F2); assert a.error and 'connected' in a.message
a.select(('probe', 1)); key(k.BUTTON_F2); assert len(a.circuit['probes']) == 1
text('z'); assert len(a.circuit['probes']) == 2
# Operating point: node voltages on the schematic.
a.tab = items.SIM; a.sel = None; to_field('kind'); choose('kind', 'Operating')
key(k.BUTTON_F6); assert a.sim.op is not None
near(a.sim.op['nodes'][1], 5.0, 1e-4)      # C charged: no current, N2 at 5 V
a.zoom = 3; a.draw()
key(k.BUTTON_F5); assert any(r[0] == 'C1' and r[2].startswith('into +') for r in a.result_rows()); a.draw()
key(k.BUTTON_ESCAPE)
# Zoom levels and every page draw.
for z in range(len(app.render.ZOOMS)):
    a.zoom = z; a.draw()
text('+'); text('-'); text('-')
# Files: save, open it back, export a transient.
key(k.BUTTON_F3); assert a.page == 'options'
while app.OPTIONS[a.menu_index][0] != 'Save':
    key(k.BUTTON_DOWN)
key(k.BUTTON_CENTER); assert a.prompt is not None
for _ in range(12):
    key(k.BUTTON_BACKSPACE)
text('rc-test'); key(k.BUTTON_CENTER); assert a.prompt is None and 'Saved' in a.message, a.message
saved = sm.copy(a.circuit)
key(k.BUTTON_F3)
while app.OPTIONS[a.menu_index][0] != 'Open':
    key(k.BUTTON_DOWN)
key(k.BUTTON_CENTER); assert 'rc-test' in a.files
a.menu_index = a.files.index('rc-test'); key(k.BUTTON_CENTER)
assert a.page == 'model' and a.circuit['elements'] == saved['elements'] and a.sim is None
a.tab = items.SIM; a.sel = None; choose('kind', 'Transient')
key(k.BUTTON_F6); settle()
key(k.BUTTON_F3)
while app.OPTIONS[a.menu_index][0] != 'Export CSV':
    key(k.BUTTON_DOWN)
key(k.BUTTON_CENTER); assert 'Exported' in a.message and not a.error, a.message
files = vm.storage.listdir('picoware/engineering/exports')
name = [f for f in files if f.startswith('rc-test')][0]
data = vm.storage.read('picoware/engineering/exports/' + name)
assert data.startswith('t_s,P1_V_N2_V,P2_I_N2_C1_A') and len(data.split('\n')) == 103, data[:80]
# Every example through F3, simulated with F6, every page drawn.
for index in range(len(sm.EXAMPLES)):
    key(k.BUTTON_F3)
    while app.OPTIONS[a.menu_index][0] != 'Examples':
        key(k.BUTTON_DOWN)
    key(k.BUTTON_CENTER); a.menu_index = index; key(k.BUTTON_CENTER)
    assert a.page == 'model' and a.sim is None
    key(k.BUTTON_F6); settle()
    assert a.sim.done and not a.error, (index, a.message)
    for page in (k.BUTTON_F4, k.BUTTON_F5):
        key(page); a.draw()
    key(k.BUTTON_ESCAPE)
    for tab in range(4):
        a.tab = tab; a.restore_selection(); a.draw()
# Leaving keeps the circuit for the next visit.
key(k.BUTTON_ESCAPE)
while vm.current_view.name == 'spice_view':
    key(k.BUTTON_ESCAPE)
app.show(vm); a = app._active
assert a.page == 'model' and len(a.circuit['elements']) == len(sm.example(len(sm.EXAMPLES) - 1)['elements'])
print('PASS: built by keys, simulated, waveforms, results, edits, errors, undo, files and every example')
