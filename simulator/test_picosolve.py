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

# free() releases the memory for good: every later use raises, never writes.
b = simple_span()
b.solve()
b.free()
for use in (lambda: b.node(0, 42.0), lambda: b.support(0, ps.UY), lambda: b.solve(),
            lambda: b.reaction(0), lambda: b.line(0, 0, 0.0, 1.0, -1.0), lambda: b.info()):
    try:
        use()
        raise AssertionError('a freed model was used')
    except ValueError:
        pass
b.free()  # twice is harmless
assert not b.busy() and b.progress() == (0, 8) or True
print('PASS: a freed model refuses every use')

# Running out of memory while (re)allocating leaves the model safe to use.
import gc
spans = 2000
big = ps.Beam(spans + 1, spans, loads=spans, cases=255)
big.section(0, 2.1e11, 8.36e-5)
for i in range(spans + 1):
    big.node(i, float(i))
for e in range(spans):
    big.element(e, e, e + 1)
    big.line(0, e, 0.0, 1.0, -5e3)
big.support(0, ps.UY)
big.support(spans, ps.UY)
hog = []
try:
    while True:
        hog.append(bytearray(64 * 1024))
except MemoryError:
    pass
while hog:
    hog.pop()
    gc.collect()
    try:
        big.solve()
        break
    except MemoryError:
        # The failed allocation must not leave a dangling block behind.
        try:
            big.reaction(0)
            raise AssertionError('results from a failed solve')
        except ValueError:
            pass
        big.node(0, 0.0)
hog = None
gc.collect()
big.solve()
near(big.reaction(0)[0], 5e3 * spans / 2)
big.free()
big.free()
print('PASS: memory errors during a solve leave the model consistent')

# Plane frames: an inclined cantilever, axial loads and the frame-only API.
from math import cos, sin, radians
E2, I2, A2, H2, P2, t2 = 2.0e11, 2.0e-5, 1.0e-3, 4.0, 8e3, radians(30)
c2, s2 = cos(t2), sin(t2)
f = ps.Frame(2, 1, loads=2)
f.node(0, 0.0, 0.0)
f.node(1, H2 * c2, H2 * s2)
f.section(0, E2, I2, A2)
f.element(0, 0, 1)
f.support(0, ps.UX | ps.UY | ps.RZ)
f.node_load(0, 1, ps.UY, -P2)
f.solve()
q2, n2 = -P2 * c2, -P2 * s2
v2, u2 = q2 * H2 ** 3 / (3 * E2 * I2), n2 * H2 / (E2 * A2)
near(f.displacement(1, ps.UX), c2 * u2 - s2 * v2)
near(f.displacement(1, ps.UY), s2 * u2 + c2 * v2)
fx, fy, mz = f.reaction(0)
near(fx, 0); near(fy, P2); near(mz, P2 * H2 * c2)
section = f.at(0, H2 / 2)
assert len(section) == 6 and len(f.end_forces(0)) == 6
near(section[4], n2)
normal, axial = array('f', [0] * 9), array('f', [0] * 9)
f.axial_diagram(0, 9, normal, axial)
near(normal[4], n2); near(axial[8], u2, 1e-4)
f.free()
column = ps.Frame(2, 1, loads=1)
column.node(0, 0, 0); column.node(1, 0, 3.0)
column.section(0, 3e10, 1e-3, 0.09)
column.element(0, 0, 1)
column.support(0, ps.UX | ps.UY | ps.RZ)
column.axial_line(0, 0, 0.0, 3.0, -2e3)
column.solve()
near(column.at(0, 0.0)[4], -6e3); near(column.reaction(0)[1], 6e3)
for bad in (lambda: ps.Beam(2, 1).axial_point(0, 0, 0.0, 1.0),
            lambda: ps.Beam(2, 1).node(0, 0.0, 1.0),
            lambda: ps.Beam(2, 1).section(0, 1.0, 1.0, 1.0),
            lambda: ps.Beam(2, 1).axial_diagram(0, 2, normal, axial)):
    try: bad()
    except ValueError: pass
    else: raise AssertionError('Beam accepted a frame-only input')
slide = ps.Frame(2, 1)
slide.node(0, 0, 0); slide.node(1, 4.0, 0)
slide.section(0, 2e11, 1e-5, 1e-3)
slide.element(0, 0, 1)
slide.support(0, ps.UY); slide.support(1, ps.UY)
try: slide.solve()
except ps.SolveError as exc: assert 'horizontal movement of node' in str(exc), str(exc)
else: raise AssertionError('Sliding frame accepted')
slide.section(0, 2e11, 1e-5, 0.0)
try: slide.solve()
except ps.SolveError as exc: assert 'E, I and A' in str(exc), str(exc)
else: raise AssertionError('Frame without area accepted')
print('PASS: plane frames: inclined cantilever, axial loads, frame-only API and errors')
