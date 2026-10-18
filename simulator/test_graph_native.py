"""Graph draws the same with its C loops as with its Python loops.

Every plot is drawn twice: all in Python (eval, the Python contour tracer,
per-point drawing) and all in C (compiled formulas, C contours, C curve,
segment and shading loops). Images must match pixel for pixel and the plot
extents exactly. Timings show the gain.

Run with the desktop MicroPython build, from the project root.
"""
exec(open('simulator/test_graph.py').read().split("for text,kind in")[0])
from time import ticks_us, ticks_diff
assert hasattr(vm.draw, '_plot_curve') and hasattr(vm.draw, '_stipple'), 'The simulator must include gfx_plot'


def render(texts, native, bounds=None):
    Graph.NATIVE_FORMULA = Graph.NATIVE_GEOMETRY = Graph.NATIVE_DRAW = native
    if bounds:
        a.bounds = list(bounds)
    a.items = [Graph.Expression(t, Graph.COLORS[i % len(Graph.COLORS)]) for i, t in enumerate(texts)]
    a.dirty = True
    a.refine = None
    start = ticks_us()
    finish()
    took = ticks_diff(ticks_us(), start)
    image = b''.join(vm.draw._read_row(y) for y in range(vm.draw.height))
    return image, [e.bbox for e in a.items], [(e.valid > 0, e.invalid > 0) for e in a.items], took


cases = (
    (['sin(x)', 'cos(x)', 'y=x^2/4'], None),
    (['tan(x)'], None),                             # jumps across poles are not joined
    (['1/x'], (-0.5, 0.5, -50, 50)),                # huge values near the pole
    (['x=sin(y)*2', 'x=y^2-3'], None),              # vertical curves
    (['y>=sin(x)', 'y<=sin(x)+2'], None),           # shaded band from explicit curves
    (['y<x/2', 'x>cos(y)'], None),                  # strict: dashed edge, shading across
    (['16*sin(t)^3;13*cos(t)-5*cos(2*t)-2*cos(3*t)-cos(4*t)'], (-20, 20, -20, 20)),
    (['cos(t);sin(t)', 'cos(3*t);sin(2*t)'], (-2, 2, -1.5, 1.5)),
    (['x^2+y^2<=25', 'x^2+y^2=25'], None),          # shaded disk with its edge
    (['x*y>1', 'x^2/16+y^2/4<1'], None),            # dashed contours, overlapping shading
    (['sin(x)*sin(y)=0.2', '1/x+y=0'], None),       # saddles, a pole
    (['y=sqrt(x)', 'y=sqrt(-x)-1'], None),          # undefined halves
    (['x^3-x'], (-0.001, 0.001, -0.001, 0.001)),    # tiny window
    (['1e20*x'], None),                             # beyond the 1e12 limit
)
default = list(a.bounds)
for texts, bounds in cases:
    py = render(texts, False, bounds or default)
    c = render(texts, True, bounds or default)
    assert py[0] == c[0], '%s: images differ' % texts
    assert py[1] == c[1], '%s: extents differ %s %s' % (texts, py[1], c[1])
    assert py[2] == c[2], '%s: defined/undefined counts differ' % texts
    print('  %-44s %4d ms -> %3d ms' % (', '.join(texts)[:44], py[3] // 1000, c[3] // 1000))
Graph.NATIVE_FORMULA = Graph.NATIVE_GEOMETRY = Graph.NATIVE_DRAW = True
a.bounds = default
print('PASS: Graph draws %d plots pixel for pixel with its C loops' % len(cases))
