"""picosolve.Formula evaluates exactly what Python's eval evaluates.

Thousands of random formulas over the plot tools' names are evaluated both
ways at awkward points (zero, signs, poles, overflow, domain edges) and
compared bit for bit, including where Python raises. Then map/points against
single calls, the derived r of Graph3D, and the speed against eval.

Run with the desktop MicroPython build, from the project root.
"""
import math
import struct
from array import array
from time import ticks_us, ticks_diff
import picosolve as ps

SAFE = {'abs': abs, 'min': min, 'max': max, 'pow': pow, 'round': round, 'int': int, 'float': float,
        'pi': math.pi, 'e': math.e, '__builtins__': {}}
for name in ('sin', 'cos', 'tan', 'asin', 'acos', 'atan', 'atan2', 'sqrt', 'log', 'log10', 'exp',
             'floor', 'ceil', 'sinh', 'cosh', 'tanh', 'degrees', 'radians'):
    SAFE[name] = getattr(math, name)
CONSTANTS = {'pi': math.pi, 'e': math.e}

seed = 12345


def rand(n):
    global seed
    seed = (seed * 1103515245 + 12345) & 0x7fffffff
    return (seed >> 8) % n


def pick(items):
    return items[rand(len(items))]


LEAVES = ('x', 'y', 'x', 'y', '0', '1', '2', '3', '10', '0.5', '1.5', '2.5', '0.1', '1e3', '3.0', 'pi', 'e', '0.0')
EXPONENTS = ('2', '3', '0', '1', '0.5', '1.5', '-1', '-2', 'x', 'y', '0.0', '-0.5')
F1 = ('sin', 'cos', 'tan', 'asin', 'acos', 'atan', 'sqrt', 'exp', 'log', 'log10', 'sinh', 'cosh', 'tanh',
      'floor', 'ceil', 'round', 'int', 'float', 'abs', 'degrees', 'radians')
F2 = ('atan2', 'min', 'max', 'log', 'pow')
OPS = ('+', '-', '*', '/', '//', '%')


def formula(depth):
    r = rand(10)
    if depth <= 0 or r < 2:
        return pick(LEAVES)
    if r < 5:
        a, b = formula(depth - 1), formula(depth - 1)
        text = a + pick(OPS) + b
        return '(' + text + ')' if rand(2) else text
    if r < 6:
        # Exponents stay small so Python's exact integers stay small too.
        return '(' + formula(depth - 1) + ')**' + pick(EXPONENTS)
    if r < 7:
        return '-' + formula(depth - 1)
    if r < 9:
        return pick(F1) + '(' + formula(depth - 1) + ')'
    name = pick(F2)
    second = pick(EXPONENTS) if name == 'pow' else formula(depth - 1)
    extra = ',' + formula(depth - 1) if name in ('min', 'max') and rand(2) else ''
    return name + '(' + formula(depth - 1) + ',' + second + extra + ')'


POINTS = [(0.0, 0.0), (-0.0, 1.0), (1.0, -1.0), (2.5, 0.5), (-2.5, 3.0), (0.5, -0.5), (3.0, 3.0),
          (-7.0, 2.0), (1e-3, -1e5), (1e5, 100.0), (math.pi, -math.e), (-1.0, 0.0), (90.0, -0.0),
          (1e30, 1e-30), (-1e30, 7.0)]


def python(code, x, y):
    env = dict(SAFE)
    env['x'], env['y'] = x, y
    try:
        v = eval(code, env)
        if isinstance(v, (int, float)) and not math.isnan(v) and not math.isinf(v):
            return v
    except Exception:
        pass
    return None


def bits(v):
    return struct.pack('<f', v)


compared = refused = exact = big_int = signed_zero = 0
failures = []
for case in range(4000):
    text = formula(1 + rand(4))
    try:
        code = compile(text, '<f>', 'eval')
    except SyntaxError:
        continue
    try:
        f = ps.Formula(text, ('x', 'y'), constants=CONSTANTS)
    except ValueError:
        refused += 1
        continue
    for x, y in POINTS:
        want, got = python(code, x, y), f(x, y)
        compared += 1
        if want is None or got is None:
            if want is None and got is None:
                exact += 1
            elif isinstance(want, int) and abs(want) > 1 << 24:
                big_int += 1
            else:
                failures.append((text, x, y, want, got))
            continue
        try:
            wf = float(want)
        except OverflowError:
            wf = math.inf
        if bits(wf) == bits(got):
            exact += 1
        elif wf == got == 0:
            signed_zero += 1
        elif isinstance(want, int) and abs(want) > 1 << 24:
            big_int += 1
        else:
            failures.append((text, x, y, want, got))

for failure in failures[:20]:
    print('  MISMATCH %s at (%r, %r): python %r, formula %r' % failure)
assert not failures, '%d mismatches' % len(failures)
assert refused < 200, 'too many formulas refused: %d' % refused
assert signed_zero <= compared // 2000, 'signed zeros: %d' % signed_zero
print('PASS: %d evaluations identical to eval (%d whole numbers beyond 2^24, %d signed zeros, %d formulas left to Python)'
      % (exact, big_int, signed_zero, refused))

# Refused on purpose: Python would give a real abs() of a complex power.
for text in ('abs(x**0.5)', 'atan2(-max(x, 0), -1)', 'x(2)', 'x, y', 'math', 'sin'):
    try:
        ps.Formula(text, ('x', 'y'))
        raise AssertionError('compiled: ' + text)
    except ValueError:
        pass
print('PASS: formulas Python evaluates differently are refused')

# map and points give what single calls give, across block boundaries.
f = ps.Formula('sin(x)*y + 1/(x-3) - floor(y)', ('x', 'y'), limit=50)
n = 77
xs = array('f', [i * 0.1 for i in range(n)])
ys = array('f', [(i % 9) - 4.5 for i in range(n)])
flat = array('f')
for i in range(n):
    flat.extend((xs[i], ys[i]))
out, out2, out3 = array('f', [0.0] * n), array('f', [0.0] * n), array('f', [0.0] * n)
kept = f.map(out, xs, ys)
assert f.points(out2, flat, n) == kept
f.map(out3, xs, 2.0)
singles = [f(xs[i], ys[i]) for i in range(n)]
assert kept == sum(1 for v in singles if v is not None)
for i in range(n):
    s = singles[i]
    assert (s is None and out[i] != out[i]) or bits(out[i]) == bits(s), i
    assert bits(out[i]) == bits(out2[i]) or (out[i] != out[i] and out2[i] != out2[i])
    t = f(xs[i], 2.0)
    assert (t is None and out3[i] != out3[i]) or bits(out3[i]) == bits(t)
assert any(v is None for v in singles), 'the limit should drop the pole'
print('PASS: map and points match single calls (%d of %d kept)' % (kept, n))

# Graph3D's r is compiled in place from its definition.
g = ps.Formula('r*r - x*x - y*y - z*z', ('x', 'y', 'z'), derived={'r': 'sqrt(x*x+y*y+z*z)'})
h = ps.Formula('sqrt(x*x+y*y+z*z)', ('x', 'y', 'z'))
r = ps.Formula('r', ('x', 'y', 'z'), derived={'r': 'sqrt(x*x+y*y+z*z)'})
for p in ((1.0, 2.0, 2.0), (0.3, -0.7, 1.1), (0.0, 0.0, 0.0)):
    assert bits(r(*p)) == bits(h(*p))
    x, y, z = p
    rr = math.sqrt(x * x + y * y + z * z)
    assert bits(g(*p)) == bits(rr * rr - x * x - y * y - z * z)
print('PASS: derived names')

# Speed: one row of 4096 points, eval against map.
for text in ('0.6*sin(x)*cos(y)', 'x^2+y^2-9'.replace('^', '**'), 'sin(x)+cos(y)', 'tan(x*y)-1'):
    code = compile(text, '<f>', 'eval')
    f = ps.Formula(text, ('x', 'y'), constants=CONSTANTS)
    xs = array('f', [-4 + 8 * i / 4095 for i in range(4096)])
    out = array('f', [0.0] * 4096)
    env = dict(SAFE)
    start = ticks_us()
    for x in xs:
        env['x'], env['y'] = x, 0.75
        try:
            eval(code, env)
        except Exception:
            pass
    slow = ticks_diff(ticks_us(), start)
    start = ticks_us()
    f.map(out, xs, 0.75)
    fast = max(1, ticks_diff(ticks_us(), start))
    print('  %-20s eval %6d us, map %5d us: %4dx' % (text, slow, fast, slow // fast))
print('PASS: timings above')
