"""Graph3D's C renderer draws what the Python renderer draws.

Both paths render the same surfaces from several views and styles; the images
must agree except for the colour table's 256 steps and the order of
equally deep triangles. Run with the desktop MicroPython build, from the
project root.
"""
import os, sys
from time import ticks_ms, ticks_us, ticks_diff
root = os.getcwd()
sys.path.insert(0, root + '/src/MicroPython')
sys.path.insert(0, root + '/simulator/hardware')
sys.path.insert(0, root + '/builds/MicroPython/apps_unfrozen')
import sim_runtime
sd = '/private/tmp/gungos-graph3d-native-' + str(ticks_ms())
sim_runtime.configure(root, sd, root + '/builds/MicroPython/apps_unfrozen', 1,
                      'picocalc-pico2w', 0, True, False, False, False, '',
                      _network_mode='offline', _audio_mode='silent')
sim_runtime.mkdir_p(sd)
from picoware.system.view_manager import ViewManager
from picoware.system.input import Input
from picoware.system.buttons import BUTTON_NONE
Input.button = property(lambda self: self._last_button)
from engtools.plots import plot3d as g

vm = ViewManager()
draw = vm.draw
assert hasattr(draw, '_mesh3d'), 'The simulator must include the C renderer'


def key(button):
    vm.input_manager._last_button = button
    vm._button = button
    g.run(vm)


def sample():
    for _ in range(20000):
        if g._state != g.ST_SAMPLING:
            break
        key(BUTTON_NONE)
    assert g._state == g.ST_PLOT, (g._state, g._error_msg)


def image():
    return b''.join(draw._read_row(y) for y in range(draw.height))


def table_shade(t, shade, cool=False):
    """Python's colour with the 256-step table the C renderer uses."""
    ramp = g._mesh_ramp()
    t = 0.0 if not t > 0 else (1.0 if t > 1 else t)
    o = (768 if cool else 0) + 3 * int(t * 255 + 0.5)
    return g._rgb565(int(ramp[o] * shade), int(ramp[o + 1] * shade), int(ramp[o + 2] * shade))


def compare(label, preview=False):
    """Identical with the same colour table; within one colour step otherwise."""
    g._draw_mesh(draw, preview, native=True)
    native = image()
    exact = g._shade_color
    g._shade_color = table_shade
    try:
        g._draw_mesh(draw, preview, native=False)
    finally:
        g._shade_color = exact
    assert image() == native, label + ': C and Python renderers differ'
    g._draw_mesh(draw, preview, native=False)
    reference = image()
    share = sum(1 for a, b in zip(reference, native) if a != b) / len(reference)
    assert share < 0.03, '%s: %.2f%% of pixels differ in colour' % (label, 100 * share)
    return share


assert g.start(vm)
sample()
worst = 0.0
views = ((0.55, 0.8, 1.0, 0, 0), (-0.3, 2.4, 1.6, 20, -15), (1.2, -1.0, 0.7, -40, 30),
         (0.1, 0.0, 3.5, 0, 0))  # the last zooms far past the plot window
for style in (1, 0):
    g._style = style
    for pitch, yaw, zoom, pan_x, pan_y in views:
        g._pitch, g._yaw, g._zoom, g._pan_x, g._pan_y = pitch, yaw, zoom, pan_x, pan_y
        worst = max(worst, compare('style %d view %s' % (style, (pitch, yaw, zoom))))
worst = max(worst, compare('preview', preview=True))

# A second surface uses the cool colour table.
g.start(vm)
g._expr, g._expr2 = 'sin(x)*cos(y)', '0.5'
g._need_eval = True
key(BUTTON_NONE)
sample()
assert any(g._mesh_colors), 'Second surface must be present'
worst = max(worst, compare('two surfaces'))

# Rough host timing; device speed comes from the benchmark.
start = ticks_us(); g._draw_mesh(draw, False, native=False); python = ticks_diff(ticks_us(), start)
start = ticks_us(); g._draw_mesh(draw, False, native=True); native = ticks_diff(ticks_us(), start)
print('PASS: C renderer draws exactly what Python draws (colour-table steps alter %.2f%% of pixels at most); host frame %d ms -> %d ms, %d triangles'
      % (100 * worst, python // 1000, native // 1000, len(g._mesh_colors)))
