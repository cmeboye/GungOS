"""Closed SD apps give their heap back: modules unload at the menus.

Run with the desktop MicroPython build, from the project root.
"""
import os, sys, gc
from time import ticks_ms
root = os.getcwd()
for part in ('src/MicroPython', 'simulator/hardware', 'builds/MicroPython/apps_unfrozen'):
    sys.path.insert(0, root + '/' + part)
import sim_runtime
sd = '/private/tmp/gungos-memory-test-' + str(ticks_ms())
sim_runtime.configure(root, sd, root + '/builds/MicroPython/apps_unfrozen', 1, 'picocalc-pico2w', 0,
                      True, False, False, False, '', _network_mode='offline', _audio_mode='silent')
from picoware.system.input import Input
from picoware.system.view import View
from picoware.system.view_manager import ViewManager
from picoware.system import buttons as k
Input.button = property(lambda self: self._last_button)
vm = ViewManager()
from picoware.applications import desktop, library
vm.add(View('desktop_view', desktop.run, desktop.start, desktop.stop)); vm.switch_to('desktop_view')


def key(button):
    vm.input_manager._last_button = button
    vm.run()


def text(value):
    for c in value:
        key(vm.input_manager._key_to_button(ord(c)))


def idle(n):
    for _ in range(n):
        key(k.BUTTON_NONE)


def used():
    vm._log.logs[:] = []  # the simulator logger keeps every line; the device logs to a file
    gc.collect(); gc.collect()
    return gc.mem_alloc()


def home():
    for _ in range(12):
        if vm.current_view.name == 'desktop_view':
            return
        key(k.BUTTON_ESCAPE)
    raise AssertionError('Did not return home: ' + vm.current_view.name)


def app_modules():
    return [m for m in sys.modules if m.split('.')[0] in ('engtools', 'PicoLAB', 'Graph', 'Graph3D')]


# Warm the firmware menus (frozen in flash on the device, compiled here).
key(k.BUTTON_NONE)
library.launch(vm, 'PicoLAB'); home()
assert not app_modules(), app_modules()
base = used()

# Inside PicoLAB: Beam view's 100+ KB of code unloads on return to the menu,
# while its model is kept for the next visit. The first load interns new names
# (qstrs) for good, about 35 KB, on the device too; later visits add nothing,
# so warm up with one visit before measuring.
library.launch(vm, 'PicoLAB'); idle(3)
import PicoLAB
PicoLAB._launch(vm, 'beam'); del PicoLAB
key(k.BUTTON_CENTER)
while vm.current_view.name != 'app_PicoLAB': key(k.BUTTON_ESCAPE)
sys.modules['engtools.session'].kept.clear()
menu = used()
import PicoLAB
PicoLAB._launch(vm, 'beam'); del PicoLAB
key(k.BUTTON_CENTER); text('p'); key(k.BUTTON_ESCAPE); key(k.BUTTON_F4); idle(3)
in_use = used()
key(k.BUTTON_ESCAPE); key(k.BUTTON_ESCAPE)
assert vm.current_view.name == 'app_PicoLAB', vm.current_view.name
back = used()
assert not [m for m in sys.modules if 'beamlab' in m], 'Beam view stayed loaded'
assert 'beam' in sys.modules['engtools.session'].kept, 'Beam model was not kept'
assert in_use - back > 100000 and back - menu < 8000, (in_use - base, back - base, menu - base)
import PicoLAB
PicoLAB._launch(vm, 'beam'); del PicoLAB
model = sys.modules['engtools.beamlab.app']._active.model
assert len(model['loads']) == 2, 'The kept model did not come back'
sys.modules['engtools.session'].kept.clear(); del model
home()
print('PASS: Beam view unloads at the PicoLAB menu (in use +%d, menu +%d) and keeps its model' % (
    in_use - base, back - base))

# Leaving PicoLAB unloads every SD module; repeated visits do not accumulate.
base = used()  # after Beam view's names are interned
leftovers = []
for cycle in range(3):
    library.launch(vm, 'PicoLAB')
    from picoware.applications.library import launch
    launch(vm, 'Graph3D'); idle(400)
    g = sys.modules['engtools.plots.plot3d']
    if cycle == 0:
        g._expr, g._bounds = '0.2*x*y', [-3.0, 5.0, -2.0, 2.0]
    key(k.BUTTON_S); idle(400); key(k.BUTTON_S); idle(400)
    del g
    home()
    assert not app_modules(), app_modules()
    leftovers.append(used() - base)
assert leftovers[-1] - leftovers[0] < 1000, leftovers  # first entry includes Graph3D's names
print('PASS: closing PicoLAB unloads its modules; retained %s bytes over three visits' % leftovers)

# Graph3D's surface and ranges survive unloading through its SD session.
library.launch(vm, 'PicoLAB')
from picoware.applications.library import launch
launch(vm, 'Graph3D'); idle(400)
g = sys.modules['engtools.plots.plot3d']
assert g._expr == '0.2*x*y' and g._bounds == [-3.0, 5.0, -2.0, 2.0], (g._expr, g._bounds)
del g
home()
print('PASS: Graph3D restores its surface and ranges after being unloaded')
