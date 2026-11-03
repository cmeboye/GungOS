"""The calculator's compiled integrands and equations match its evaluator.

native_function turns a calculator parse tree into a picosolve.Formula.
At single points it must give exactly what Evaluator.run gives (or fail
where it raises), in degrees and radians; integrals and equation roots must
come out identical with and without it. Timings show the gain.

Run with the desktop MicroPython build, from the project root.
"""
import os, sys, struct
from time import ticks_us, ticks_diff
root = os.getcwd()
sys.path.insert(0, root + '/src/MicroPython')
sys.path.insert(0,root+'/'+(sys.argv[1] if len(sys.argv)>1 else 'builds/MicroPython/apps_unfrozen'))
import engtools.calculator.evaluate as ev
from engtools.calculator.evaluate import Parser, Evaluator, calculate, native_function
from engtools.numerics.equations import root_job

VARIABLES = {'a': 2.5, 'k': -3.0, 'n': 4, 'Ans': 0.75}
EXPRESSIONS = (
    'x^2', '2x+1', 'sin(x)', 'cos(x)^2+sin(x)^2', 'asin(x/100)', 'atan(x)',
    'sqrt(x)', 'ln(x)', 'log(x)', 'logb(2,x)', 'logb(x,8)', 'exp(-x^2)', 'e^x', 'pi x',
    '1/x', 'x%3', '(-x)^0.5', 'x^-1', 'abs(x)-a', 'floor(x)*k', 'ceil(x/n)', 'round(x)',
    'sinh(x)/cosh(x)-tanh(x)', 'min(x,a,1)', 'max(x)', 'Ans*x', '-x^2', '2^3^x',
    'floor(x+16777216)+floor(x+1)-floor(x+16777216)', 'round(x*1e4)*round(x*1e4)-round(x*1e4)^2',
    're(x)+conj(x)', 'x^40', '(x*1e20)*1e20', '1/((x*1e20)*1e20)', 'k x(x-a)',
)
POINTS = (0.0, 1.0, -1.0, 0.5, 2.0, -2.5, 3.0, 45.0, 90.0, -90.0, 100.0, 1e-3, 7.25, -0.0)


def python(tree, x, angle):
    try:
        value = Evaluator(VARIABLES, angle).run(tree, {'x': x})
        return None if isinstance(value, complex) else value
    except Exception:
        return None


def bits(v):
    return struct.pack('<f', v)


compared = compiled = 0
for text in EXPRESSIONS:
    tree = Parser(text).parse()[1]
    for angle in ('DEG', 'RAD'):
        f = native_function(tree, VARIABLES, angle)
        if f is None:
            continue
        compiled += 1
        for x in POINTS:
            want, got = python(tree, x, angle), f(x)
            compared += 1
            if want is None or got is None:
                assert want is None and got is None, (text, angle, x, want, got)
            else:
                assert bits(float(want)) == bits(got), (text, angle, x, want, got)
assert compiled >= 2 * (len(EXPRESSIONS) - 2), compiled
for text in ('i*x', 'x!', 'mean(X)', 'im(x)', 'q*x', 'tan(x)', 'sin(tan(x))', 'ncr(5,2)', 'cbrt(x)'):
    assert native_function(Parser(text).parse()[1], VARIABLES) is None, text
print('PASS: %d evaluations identical to the calculator evaluator (%d of %d compiled)'
      % (compared, compiled, 2 * len(EXPRESSIONS)))


def both(run):
    ev.NATIVE_FORMULA = False
    start = ticks_us()
    try: slow = run()
    except Exception as exc: slow = 'error'
    slow_time = ticks_diff(ticks_us(), start)
    ev.NATIVE_FORMULA = True
    start = ticks_us()
    try: fast = run()
    except Exception as exc: fast = 'error'
    return slow, fast, slow_time, ticks_diff(ticks_us(), start)


# Whole numbers past 2^24 must be exact, as in the evaluator (it gives 1).
text = 'int(0,1,floor(x+16777216)+floor(x+1)-floor(x+16777216))'
assert calculate(text, {}, 'RAD')[0] == 1, calculate(text, {}, 'RAD')
for text in ('int(0,1,x^2)', 'int(0,pi,sin(x))', 'int(-3,3,exp(-x^2))', 'int(1,10,ln(x)/x)',
             'int(0,90,cos(x))', 'int(-1,1,1/x)'):
    angle = 'DEG' if '90' in text else 'RAD'
    slow, fast, ts, tf = both(lambda: calculate(text, dict(VARIABLES), angle)[0])
    assert slow == fast, (text, slow, fast)
    print('  %-24s %-12s %5d us -> %4d us' % (text, slow, ts, tf))


def solve(text, lower, upper, guess, angle):
    result = None
    for step in root_job(text, lower, upper, guess, dict(VARIABLES), angle):
        result = step
    return result['root'], result['iterations']


for text, lower, upper, guess, angle in (('x^3-2x-5', -10, 10, 0, 'RAD'), ('cos(x)=x', 0, 1, 0.5, 'RAD'),
                                         ('sin(x)=0.5', 0, 90, 10, 'DEG'), ('exp(x)=a x+3', -5, 5, 1, 'RAD'),
                                         ('1/x', -1, 1, 0.3, 'RAD')):
    slow, fast, ts, tf = both(lambda: solve(text, lower, upper, guess, angle))
    assert slow == fast, (text, slow, fast)
    print('  %-24s %-24s %5d us -> %4d us' % (text, slow, ts, tf))
print('PASS: integrals and equation roots identical with compiled formulas')
