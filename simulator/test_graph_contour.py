"""Graph's C contour tracer draws exactly what the Python tracer drew.

Run with the desktop MicroPython build, from the project root.
"""
exec(open('simulator/test_graph.py').read().split("for text,kind in")[0])
from time import ticks_us, ticks_diff
assert Graph._geometry() is not None, 'The simulator must include the C contour tracer'


def render(texts, native):
    Graph.NATIVE_GEOMETRY = native
    a.items = [Graph.Expression(t, Graph.COLORS[i % len(Graph.COLORS)]) for i, t in enumerate(texts)]
    a.dirty = True
    a.refine = None
    start = ticks_us()
    finish()
    took = ticks_diff(ticks_us(), start)
    image = b''.join(vm.draw._read_row(y) for y in range(vm.draw.height))
    return image, [e.bbox for e in a.items], took


cases = (
    ['x^2+y^2=25'],                  # closed curve
    ['x*y=1'],                       # two branches
    ['x^2+y^2<=9'],                  # filled inequality with a solid edge
    ['y>sin(x)*x', 'x^2/16+y^2/4<1'],  # dashed edges, overlapping shading
    ['1/x+y=0'],                     # sign change across a pole must not join
    ['sin(x)*sin(y)=0.2'],           # many saddles
    ['tan(x*y)=1'],                  # poles everywhere
)
for texts in cases:
    py_image, py_boxes, py_time = render(texts, False)
    c_image, c_boxes, c_time = render(texts, True)
    assert py_image == c_image, '%s: images differ' % texts
    assert py_boxes == c_boxes, '%s: extents differ %s %s' % (texts, py_boxes, c_boxes)
    print('  %-36s %4d ms -> %3d ms' % (', '.join(texts), py_time // 1000, c_time // 1000))
Graph.NATIVE_GEOMETRY = True
print('PASS: C contour tracer reproduces Python on %d plots, pixel for pixel' % len(cases))
