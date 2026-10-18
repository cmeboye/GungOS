"""Graph and Graph3D draw the same with compiled formulas as with eval.

Each plot is drawn twice, with picosolve.Formula and with Python's eval, and
must match exactly: Graph pixel for pixel with the same extents, Graph3D
triangle for triangle. Timings show what the compiler saves.

Run with the desktop MicroPython build, from the project root.
"""
exec(open('simulator/test_graph.py').read().split("for text,kind in")[0])
from time import ticks_us, ticks_diff
from engtools.plots import plot3d as g


def render(texts, native):
    Graph.NATIVE_FORMULA = native
    a.items = [Graph.Expression(t, Graph.COLORS[i % len(Graph.COLORS)]) for i, t in enumerate(texts)]
    assert all((e.formula is not None) == native for e in a.items), texts
    a.dirty = True
    a.refine = None
    start = ticks_us()
    finish()
    took = ticks_diff(ticks_us(), start)
    image = b''.join(vm.draw._read_row(y) for y in range(vm.draw.height))
    return image, [e.bbox for e in a.items], [bool(e.valid) for e in a.items], took


graph_cases = (
    ['sin(x)', 'y=x^2/4'],              # explicit curves
    ['x=sin(y)*2'],                     # x = f(y)
    ['y>=sin(x)', 'y<=sin(x)+2'],       # shaded band
    ['16*sin(t)^3;13*cos(t)-5*cos(2*t)-2*cos(3*t)-cos(4*t)'],  # parametric
    ['x^2+y^2=25', 'x*y=1'],            # implicit curves
    ['x^2+y^2<=9'],                     # implicit inequality
    ['1/x+y=0', 'tan(x*y)=1'],          # poles
    ['sqrt(x)+floor(y)%3=1'],           # undefined half-plane, whole numbers
)
for texts in graph_cases:
    py = render(texts, False)
    c = render(texts, True)
    assert py[0] == c[0], '%s: images differ' % texts
    assert py[1] == c[1] and py[2] == c[2], '%s: extents differ %s %s' % (texts, py[1], c[1])
    print('  %-44s %4d ms -> %3d ms' % (', '.join(texts)[:44], py[3] // 1000, c[3] // 1000))
Graph.NATIVE_FORMULA = True
print('PASS: Graph draws %d plots pixel for pixel with compiled formulas' % len(graph_cases))

g.start(vm)
assert g._geometry() is not None


def build(native):
    g.NATIVE_FORMULA = native
    start = ticks_us()
    for _ in g._sample_job():
        pass
    took = ticks_diff(ticks_us(), start)
    return bytes(g._mesh), bytes(g._mesh_colors), g._zmin, g._zmax, took


surface_cases = (
    ('0.6*sin(x)*cos(y)', '', 32),
    ('sqrt(4-x^2-y^2)', '', 24),
    ('x^2+y^2+z^2=4', '', 20),
    ('r=2+0.3*sin(3*x)', '', 16),       # Graph3D's r = sqrt(x^2+y^2+z^2)
    ('(sqrt(x^2+y^2)-2)^2+z^2=0.8', '', 18),
    ('1/x+y+z=0', '', 14),
    ('x^2-y^2', 'x^2+y^2+z^2=6', 16),
)
for expr, expr2, n in surface_cases:
    g._expr, g._expr2, g._grid_n = expr, expr2, n
    py = build(False)
    c = build(True)
    label = expr + (' & ' + expr2 if expr2 else '')
    assert py[:4] == c[:4], '%s: meshes differ' % label
    print('  %-44s n=%2d %4d ms -> %3d ms' % (label[:44], n, py[4] // 1000, c[4] // 1000))
g.NATIVE_FORMULA = True
print('PASS: Graph3D builds %d meshes triangle for triangle with compiled formulas' % len(surface_cases))
