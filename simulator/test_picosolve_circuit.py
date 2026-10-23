"""picosolve.Circuit from Python: every element kind, the three analyses,
slices, traces, errors and memory.

Run with the desktop MicroPython build, from the project root.
"""
import picosolve as ps
from array import array
from math import exp, sqrt, sin, pi
from time import ticks_ms, ticks_diff

C = ps.Circuit


def near(got, want, tol=1e-6):
    assert abs(got - want) <= tol * max(1.0, abs(want)), (got, want)


def raises(kind, words, call, *args):
    try:
        call(*args)
    except kind as exc:
        assert words in str(exc), exc
        return
    raise AssertionError('no %s for %s' % (kind.__name__, words))


# Divider and the source current sign: into + of a source that supplies is negative.
c = C(3, 3)
c.element(0, C.V, (1, 0), (10,))
c.element(1, C.R, (1, 2), (1e3,))
c.element(2, C.R, (2, 0), (3e3,))
c.op()
near(c.voltage(2), 7.5)
near(c.current(0, 0), -2.5e-3)
near(c.current(1, 0), 2.5e-3)
info = c.info()
assert info['equations'] == 3 and info['iterations'] == 1 and info['bytes'] > 0, info
print('PASS: divider, currents, info')

# Every controlled source and an ideal op-amp in one circuit.
c = C(9, 14)
c.element(0, C.V, (1, 0), (1,))
c.element(1, C.R, (1, 0), (1e3,))
c.element(2, C.E, (2, 0, 1, 0), (5,))
c.element(3, C.G, (3, 0, 1, 0), (2e-3,))
c.element(4, C.F, (4, 0), (3,), 0)
c.element(5, C.H, (5, 0), (2e3,), 0)
for i in range(4):
    c.element(6 + i, C.R, (2 + i, 0), (1e3,))
c.element(10, C.R, (1, 6), (1e3,))
c.element(11, C.R, (6, 7), (1e4,))
c.element(12, C.OPAMP, (0, 6, 7), (0,))
c.element(13, C.R, (8, 0), (1,))   # a node of its own, with nothing driving it
c.op()
for node, want in ((2, 5), (3, -2), (4, 6), (5, -4), (7, -10), (8, 0)):   # I(V1) = -2 mA
    near(c.voltage(node), want)
print('PASS: E, G, F, H and an inverting op-amp')

# Diode, BJT and MOSFET bias points; the PNP and PMOS mirror their twins.
for sign, bjt, mos in ((1, C.NPN, C.NMOS), (-1, C.PNP, C.PMOS)):
    c = C(4, 4)
    c.element(0, C.V, (1, 0), (10 * sign,))
    c.element(1, C.R, (1, 2), (100e3,))
    c.element(2, C.R, (1, 3), (1e3,))
    c.element(3, bjt, (3, 2, 0), (1e-15, 100, 1, 0))
    c.op()
    near(c.current(3, 0) / c.current(3, 1), 100, 1e-3)
    near(c.current(3, 0), c.current(2, 0), 1e-9)
    m = C(4, 4)
    m.element(0, C.V, (1, 0), (10 * sign,))
    m.element(1, C.R, (1, 2), (1e3,))
    m.element(2, C.V, (3, 0), (3 * sign,))
    m.element(3, mos, (2, 3, 0), (1 * sign, 1e-3, 0))
    m.op()
    near(m.voltage(2), 8 * sign)
print('PASS: BJT and MOSFET bias, both polarities')

# DC sweep of a diode: monotonic, about 0.6-0.8 V once conducting.
c = C(3, 3, probes=2)
c.element(0, C.V, (1, 0), (0,))
c.element(1, C.R, (1, 2), (100,))
c.element(2, C.D, (2, 0), (1e-14, 1))
c.probe(0, C.VOLTAGE, 2)
c.probe(1, C.CURRENT, 2, 0)
c.dc(0, 0, 5, 51)
while not c.run(5):
    pass
assert c.progress() == (51, 51)
vd, idd = array('f', [0] * 51), array('f', [0] * 51)
assert c.trace(0, vd) == 51 and c.trace(1, idd) == 51
assert all(vd[i] < vd[i + 1] for i in range(50)) and 0.6 < vd[50] < 0.8
near(idd[50], (5 - vd[50]) / 100, 1e-5)
print('PASS: DC sweep and traces')

# RC step in slices: the trace grows as it runs and matches 1 - exp(-t/RC).
c = C(3, 3, probes=1)
c.element(0, C.V, (1, 0), (0,))
c.wave(0, C.PULSE, (0, 1, 0, 1e-9, 1e-9, 1, 0))
c.element(1, C.R, (1, 2), (1e3,))
c.element(2, C.C, (2, 0), (1e-6, 0))
c.probe(0, C.VOLTAGE, 2)
c.tran(5e-3, 101)
seen = []
while not c.run(0):
    seen.append(c.progress()[0])
assert len(seen) > 5 and seen == sorted(seen)
v = array('f', [0] * 101)
c.trace(0, v)
for i in range(101):
    near(v[i], 1 - exp(-i * 5e-5 / 1e-3), 2e-3)
print('PASS: transient in slices (%d steps)' % c.info()['steps'])

# Sine and PWL sources; uic starts an LC tank from its capacitor voltage.
c = C(2, 2, probes=1)
c.element(0, C.C, (1, 0), (1e-6, 1))
c.element(1, C.L, (1, 0), (1e-3, 0))
c.probe(0, C.VOLTAGE, 1)
c.tran(1e-3, 501, 0, True)
while not c.run(50):
    pass
v = array('f', [0] * 501)
c.trace(0, v)
w = 1 / sqrt(1e-9)
assert max(abs(v[i] - __import__('math').cos(w * 2e-6 * i)) for i in range(1, 501)) < 0.03
c = C(2, 2, probes=1)
c.element(0, C.V, (1, 0), (0,))
c.wave(0, C.PWL, (0, 0, 1e-3, 2, 2e-3, 2, 3e-3, -1))
c.element(1, C.R, (1, 0), (1,))
c.probe(0, C.VOLTAGE, 1)
c.tran(4e-3, 9)
while not c.run(50):
    pass
v = array('f', [0] * 9)
c.trace(0, v)
for got, want in zip(v, (0, 1, 2, 2, 2, 0.5, -1, -1, -1)):
    near(got, want, 1e-6)
print('PASS: uic LC tank and PWL')

# Problems name the node or element; bad values are refused at once.
c = C(3, 2)
c.element(0, C.V, (1, 0), (1,))
c.element(1, C.C, (1, 2), (1e-6, 0))
raises(ps.SolveError, 'node 2 has no DC path', c.op)
assert c.error() == (2, -1)
raises(ps.SolveError, 'run an analysis first', c.voltage, 1)
c = C(2, 2)
c.element(0, C.V, (1, 0), (1,))
c.element(1, C.V, (1, 0), (2,))
raises(ps.SolveError, 'set twice', c.op)
c = C(3, 1)
c.element(0, C.R, (1, 0), (1,))
raises(ps.SolveError, 'node 2 is not connected', c.op)
raises(ps.SolveError, 'element 0', c.element, 0, C.R, (1, 0), (0,))
raises(ps.SolveError, 'element 0', c.element, 0, C.D, (1, 0), (1e-14,))
raises(ValueError, 'at most 4 nodes', c.element, 0, C.R, (1, 0, 0, 0, 0), (1,))
raises(ps.SolveError, 'element 0', c.wave, 0, C.PULSE, (0, 1, 0, 0, 0, 1, 2))
c = C(2, 2)
c.element(0, C.V, (1, 0), (1,))
c.element(1, C.F, (1, 0), (1,), 0)
c.element(0, C.R, (1, 0), (1,))   # F's control loses its branch
raises(ps.SolveError, 'element 1', c.op)
print('PASS: errors name what is at fault')

# Editing clears results; free() releases everything.
c = C(2, 2)
c.element(0, C.V, (1, 0), (1,))
c.element(1, C.R, (1, 0), (1,))
c.op()
near(c.voltage(1), 1)
c.element(0, C.V, (1, 0), (2,))
raises(ps.SolveError, 'run an analysis first', c.voltage, 1)
c.op()
near(c.voltage(1), 2)
c.free()
raises(ValueError, 'released', c.op)
print('PASS: edits clear results; free')

# 50 nodes: a sine supply, 48 resistors, 24 capacitors, 9 diode clamps and a load, run to 2 ms.
import gc
gc.collect()
before = gc.mem_free()
c = C(50, 83, probes=4)
c.element(0, C.V, (1, 0), (0,))
c.wave(0, C.SIN, (0, 5, 1e3, 0, 0, 0))
e = 1
for i in range(1, 49):
    c.element(e, C.R, (i, i + 1), (100,))
    e += 1
    if i % 2 == 0:
        c.element(e, C.C, (i + 1, 0), (10e-9, 0))
        e += 1
    if i % 5 == 0:
        c.element(e, C.D, (i + 1, 0), (1e-14, 1))
        e += 1
c.element(e, C.R, (49, 0), (1e3,))
assert e == 82
for k, node in enumerate((2, 10, 30, 49)):
    c.probe(k, C.VOLTAGE, node)
start = ticks_ms()
c.tran(2e-3, 401)
while not c.run(100):
    pass
used = before - gc.mem_free()
info = c.info()
elapsed = ticks_diff(ticks_ms(), start)
print('PASS: 50 nodes, 83 elements: %d equations, %d entries, %d factor entries, %d steps, %d rejected, '
      '%d iterations, %d bytes of blocks (%d heap incl. objects), %d ms on desktop'
      % (info['equations'], info['entries'], info['factors'], info['steps'], info['rejected'], info['iterations'],
         info['bytes'], used, elapsed))
assert info['bytes'] < 24000, info
