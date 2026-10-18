"""picosolve from Python: beam results, precision, errors and background solves.

Run with the desktop MicroPython build, from the project root.
"""
import picosolve as ps
from array import array
import _thread
from time import sleep_ms

L, EI, W, P = 6.0, 2.1e11 * 8.36e-5, -5e3, -12e3


def near(got, want, tol=1e-5):
    assert abs(got - want) <= tol * max(1.0, abs(want)), (got, want)


def simple_span(elements=4, loads=8):
    b = ps.Beam(elements + 1, elements, loads=loads)
    b.section(0, 2.1e11, 8.36e-5)
    for i in range(elements + 1):
        b.node(i, L * i / elements)
    for e in range(elements):
        b.element(e, e, e + 1)
        b.line(0, e, 0.0, L / elements, W)
    b.support(0, ps.UY)
    b.support(elements, ps.UY)
    return b


# Simply supported span under a uniform load, every precision.
for precision in (ps.AUTO, ps.DOUBLE, ps.SINGLE):
    b = simple_span()
    b.solve(precision)
    near(b.reaction(0)[0], -W * L / 2)
    near(b.at(1, L / 4)[1], -W * L * L / 8)                  # midspan moment
    near(b.at(1, L / 4)[3], 5 * W * L ** 4 / (384 * EI))     # midspan deflection
    near(b.displacement(2, ps.UY), 5 * W * L ** 4 / (384 * EI))
    info = b.info()
    assert info['equations'] == 8 and info['bytes'] > 0 and not info['ill_conditioned']
    if precision == ps.SINGLE:
        assert info['precision'] == 'single' and info['refinements'] >= 1
    if precision == ps.AUTO:
        assert info['precision'] == 'double', 'A narrow beam band should solve in double'
print('PASS: simply supported span in AUTO, DOUBLE and SINGLE precision')

# Cantilever: end forces, point loads, moments, hinges and diagrams.
b = ps.Beam(3, 2, loads=4)
b.section(0, 2.1e11, 8.36e-5)
for i in range(3):
    b.node(i, L * i / 2)
b.element(0, 0, 1)
b.element(1, 1, 2)
b.support(0, ps.UY | ps.RZ)
b.node_load(0, 2, ps.UY, P)
b.solve()
near(b.displacement(2, ps.UY), P * L ** 3 / (3 * EI))
near(b.reaction(0)[1], -P * L)
fy1, m1, fy2, m2 = b.end_forces(0)
near(fy1, -P) and near(m1, -P * L)
n = 9
shear, moment, slope, deflection = (array('f', [0.0] * n) for _ in range(4))
b.diagram(1, n, shear, moment, slope, deflection)
near(moment[0], P * L / 2)
near(moment[n - 1], 0.0)
near(deflection[n - 1], P * L ** 3 / (3 * EI))
b.diagram(0, n, None, moment, None, None)
near(moment[0], P * L)
print('PASS: cantilever end forces, reactions and diagram buffers')

# Problems name what is wrong.
def fails(build, words):
    b = build()
    try:
        b.solve()
    except ps.SolveError as e:
        text = str(e)
        assert all(w in text for w in words), text
        return
    raise AssertionError('expected SolveError ' + str(words))

def mechanism():
    b = simple_span()
    b.support(4, 0)
    return b
fails(mechanism, ('structure can move', 'node'))

def unconnected():
    b = ps.Beam(3, 1)
    b.section(0, 1e9, 1e-4)
    b.node(1, 1.0)
    b.element(0, 0, 1)
    b.support(0, ps.UY | ps.RZ)
    return b
fails(unconnected, ('node 2', 'not attached'))

def outside():
    b = simple_span()
    b.point(0, 0, 9.0, P)
    return b
fails(outside, ('load', 'outside'))

def no_section():
    b = simple_span()
    b.section(0, 0.0, 1.0)
    return b
fails(no_section, ('section 0',))

try:
    ps.Beam(3, 2).displacement(0, ps.UY)
except ps.SolveError as e:
    assert 'solve the model first' in str(e)
else:
    raise AssertionError('results before solving must fail')
b = ps.Beam(3, 2, loads=1)
b.section(0, 1e9, 1e-4)
b.point(0, 0, 0.0, 1.0)
try:
    b.point(0, 0, 0.0, 1.0)
except ValueError as e:
    assert 'loads=' in str(e)
else:
    raise AssertionError('load capacity must be enforced')
print('PASS: mechanisms, loose nodes, misplaced loads and bad sections are named')

# Background: begin() allocates here, compute() runs on another thread.
spans = 4000
b = ps.Beam(spans + 1, spans, loads=spans)
b.section(0, 2.1e11, 8.36e-5)
for i in range(spans + 1):
    b.node(i, float(i))
for e in range(spans):
    b.element(e, e, e + 1)
    b.line(0, e, 0.0, 1.0, W)
for i in range(0, spans + 1, 4):
    b.support(i, ps.UY)
b.begin()
_thread.start_new_thread(b.compute, ())
polls = 0
while True:
    sleep_ms(1)
    polls += 1
    done, total = b.progress()
    assert 0 <= done <= total
    if not b.busy() and b.finish():
        break
assert b.info()['equations'] > spans
near(b.reaction(spans // 2)[0], -W * 4, 1e-3)  # far from the ends, a support carries one span
print('PASS: background compute with progress polling (%d polls)' % polls)

# Cancelling stops the solve and is reported.
b.begin()
b.cancel()
b.compute()
try:
    b.finish()
except ps.SolveError as e:
    assert 'cancelled' in str(e)
else:
    raise AssertionError('cancel must be reported')
b.free()
print('PASS: cancel and free')
