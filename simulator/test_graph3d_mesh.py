"""Graph3D's C mesh builder produces the Python builder's triangles.

Run with the desktop MicroPython build, from the project root.
"""
import os, sys
from time import ticks_ms, ticks_us, ticks_diff
root = os.getcwd()
sys.path.insert(0, root + '/src/MicroPython')
sys.path.insert(0, root + '/simulator/hardware')
sys.path.insert(0, root + '/builds/MicroPython/apps_unfrozen')
import sim_runtime
sd = '/private/tmp/gungos-graph3d-mesh-' + str(ticks_ms())
sim_runtime.configure(root, sd, root + '/builds/MicroPython/apps_unfrozen', 1,
                      'picocalc-pico2w', 0, True, False, False, False, '',
                      _network_mode='offline', _audio_mode='silent')
sim_runtime.mkdir_p(sd)
from picoware.system.view_manager import ViewManager
from engtools.plots import plot3d as g

vm = ViewManager()
assert g._geometry() is not None, 'The simulator must include the C mesh builder'
g.start(vm)


def build(native):
    start = ticks_us()
    for _ in g._sample_job(native):
        pass
    took = ticks_diff(ticks_us(), start)
    return g._mesh, bytes(g._mesh_colors), g._zmin, g._zmax, took


cases = (
    ('sin(x)*cos(y)', '', 32),          # explicit surface
    ('sqrt(4-x^2-y^2)', '', 24),        # explicit with an undefined region (holes)
    ('x^2+y^2+z^2=4', '', 20),          # implicit sphere
    ('(sqrt(x^2+y^2)-2)^2+z^2=0.8', '', 18),  # implicit torus
    ('1/x+y+z=0', '', 14),              # implicit through a pole
    ('x^2-y^2', 'x^2+y^2+z^2=6', 16),   # explicit and implicit together
)
faster = []
for expr, expr2, n in cases:
    g._expr, g._expr2, g._grid_n = expr, expr2, n
    mesh_py, colors_py, zmin_py, zmax_py, t_py = build(False)
    mesh_c, colors_c, zmin_c, zmax_c, t_c = build(True)
    label = expr + (' & ' + expr2 if expr2 else '')
    assert len(mesh_py) == len(mesh_c) and colors_py == colors_c, \
        '%s: %d vs %d triangles' % (label, len(colors_py), len(colors_c))
    worst = max((abs(a - b) for a, b in zip(mesh_py, mesh_c)), default=0.0)
    assert worst <= 1e-5, '%s: vertices differ by %g' % (label, worst)
    assert abs(zmin_py - zmin_c) <= 1e-5 and abs(zmax_py - zmax_c) <= 1e-5, label
    faster.append(t_py / max(1, t_c))
    print('  %-34s n=%2d %5d triangles  %4d ms -> %3d ms' % (label, n, len(colors_c), t_py // 1000, t_c // 1000))
print('PASS: C mesh builder matches Python on %d surfaces (host speed-up %.1fx to %.1fx)'
      % (len(cases), min(faster), max(faster)))
