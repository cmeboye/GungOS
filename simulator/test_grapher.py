"""Isolated Grapher contract, lifecycle and keys; no solver app is migrated."""
import os, sys, gc, json
from time import ticks_ms
root = os.getcwd()
for part in ('src/MicroPython', 'simulator/hardware', 'builds/MicroPython/apps_unfrozen'):
    sys.path.insert(0, root + '/' + part)
from engtools import plots
assert 'engtools.plots.plot2d' not in sys.modules
assert 'engtools.plots.plot3d' not in sys.modules
from engtools.plots.document import example, normalize
assert 'picoware.system.view' not in sys.modules
assert 'engtools.plots.runtime' not in sys.modules

doc = example()
points = [(0, 1), (None, None), (2, 3)]
doc['sources']['data'] = {'kind': 'samples', 'points': points}
doc['layers'].append({'source': 'data', 'style': 'line', 'marker': 'diamond'})
copy = normalize(doc)
assert copy is not doc and copy['sources'] is not doc['sources']
assert copy['sources']['data']['points'] is points
copy['layers'][0]['name'] = 'Copy'
assert 'name' not in doc['layers'][0]

def rejects(document, action=normalize):
    try:
        action(document)
    except (ValueError, TypeError):
        return
    raise AssertionError('Invalid plot accepted: ' + str(document))

bad = example(); bad['version'] = 2; rejects(bad)
bad = example(); bad['unknown'] = True; rejects(bad)
bad = example(); bad['layers'][0]['source'] = 'missing'; rejects(bad)
bad = example(); bad['axes']['x'] = {'scale': 'log'}; rejects(bad)
bad = example(); bad['axes']['x'] = {'bounds': [0, float('inf')]}; rejects(bad)
bad = example(); bad['axes']['x'] = {'bounds': [1, 1]}; rejects(bad)
bad = example(); bad['sources']['f'] = {'kind': 'grid'}; rejects(bad)
bad = example('3d'); bad['view']['resolution'] = True; rejects(bad)
bad = example('3d'); bad['axes']['z'] = {'unit': 'K'}; rejects(bad)
for point in ((1, None), (float('nan'), 0), (True, 1)):
    bad = example(); bad['sources']['f'] = {'kind': 'samples', 'points': [point]}; rejects(bad)
bad = example(); bad['sources']['f'] = {'kind': 'samples', 'points': [(0, 0)] * 4097}; rejects(bad)
print('PASS: renderer-free document validation, strict capabilities and borrowed buffers')

import sim_runtime
sd = '/private/tmp/gungos-grapher-test-' + str(ticks_ms())
sim_runtime.configure(root, sd, root + '/builds/MicroPython/apps_unfrozen', 1, 'picocalc-pico2w', 0,
                      True, False, False, False, '', _network_mode='offline', _audio_mode='silent', _sd_profile='clean')
sim_runtime.mkdir_p(sd)
from picoware.system.view_manager import ViewManager
from picoware.system.view import View
from picoware.system.input import Input
from picoware.system import buttons as k
from engtools.plots import runtime
from engtools.plots.grapher import Grapher, SESSION, fixture
Input.button = property(lambda self: self._last_button)
vm = ViewManager()
vm.add(View('parent', lambda vm: None, lambda vm: True, lambda vm: None)); vm.switch_to('parent')

def key(button):
    vm.input_manager._last_button = button
    vm.run()

def finish(viewer):
    for _ in range(6000):
        key(k.BUTTON_NONE)
        if viewer.mode == '2d':
            app = viewer.controller.app
            if app.completed and app.job is None and not app.dirty:
                return
        else:
            engine = viewer.engine
            assert engine._state != engine.ST_ERROR, engine._error_msg
            if engine._state == engine.ST_PLOT and not engine._dirty:
                return
    raise AssertionError('Plot did not finish')

def absent():
    assert runtime._active is None
    assert 'engtools.plots.plot2d' not in sys.modules
    assert 'engtools.plots.plot3d' not in sys.modules
    assert not hasattr(plots, 'plot2d') and not hasattr(plots, 'plot3d')

for directory in ('picoware/settings', 'picoware/settings/graph', 'picoware/settings/graph3d'):
    vm.storage.mkdir(directory)
legacy = ('picoware/settings/graph/session.json', 'picoware/settings/graph3d/session.json',
          'picoware/settings/graph3d/saved.txt')
for path in legacy:
    vm.storage.write(path, 'legacy sentinel')

validated = plots.validate(doc)
assert validated['sources']['data']['points'] is points
absent()
for mode in ('2d', '3d'):
    bad = example(mode); bad['sources']['f']['expression'] = '__import__(x)'
    rejects(bad, lambda d: plots.show(vm, d))
    assert vm.current_view.name == 'parent' and vm._view_count == 1
    absent()
bad = example('3d'); bad['sources']['f']['expression'] = 'x*x+y*y+z*z=1'; bad['view']['style'] = 'heatmap'
rejects(bad, lambda d: plots.show(vm, d)); absent()

for index in range(6):
    document = fixture(index)
    assert plots.show(vm, document) == 'eng_plot'
    viewer = runtime._active
    assert ('engtools.plots.plot3d' in sys.modules) == (viewer.mode == '3d')
    assert ('engtools.plots.plot2d' in sys.modules) == (viewer.mode == '2d')
    finish(viewer)
    if index == 0:
        assert viewer.controller.app.items[1].points is document['sources']['data']['points']
    rejects(example(), lambda d: plots.show(vm, d))
    assert runtime._active is viewer and vm.current_view.name == 'eng_plot'
    sim_runtime.lcd_screenshot('/private/tmp/grapher-fixture-%d.bmp' % index)
    key(k.BUTTON_ESCAPE)
    assert vm.current_view.name == 'parent' and vm._view_count == 1
    assert viewer.controller is None and viewer.document is None
    absent()
print('PASS: six synthetic fixtures, lazy loading, reentry rejection and cleanup')

# Startup failures return to the caller and release both view and engine.
from engtools.plots import plot2d
start_plot = plot2d._PlotView.start
def fail_start(self, vm):
    raise MemoryError('injected startup failure')
plot2d._PlotView.start = fail_start
alert = vm.alert
vm.alert = lambda *args: None
rejects(example(), lambda d: plots.show(vm, d))
assert vm.current_view.name == 'parent' and vm._view_count == 1 and runtime._active is None
plot2d._PlotView.start = start_plot
runtime._unload('engtools.plots.plot2d', plot2d)
del start_plot, plot2d
vm.alert = alert
absent()

# Cancellation before and during meshing releases all renderer-owned state.
for n in (12, 25):
    document = fixture(4); document['view']['resolution'] = n
    plots.show(vm, document)
    assert runtime._active.engine._state in (runtime._active.engine.ST_SAMPLING, runtime._active.engine.ST_RES_WARNING)
    key(k.BUTTON_ESCAPE)
    absent()
    assert vm.current_view.name == 'parent' and vm._view_count == 1

# The adapter restores settings of an already imported legacy engine.
from engtools.plots import plot3d
plot3d._aspect, plot3d._contours, plot3d._saved, plot3d._probe = 'box', False, ['saved'], [2, 3]
before = (plot3d._expr, plot3d._aspect, plot3d._contours, plot3d._saved, plot3d._probe)
plots.show(vm, fixture(3)); finish(runtime._active); key(k.BUTTON_ESCAPE)
assert before == (plot3d._expr, plot3d._aspect, plot3d._contours, plot3d._saved, plot3d._probe)
assert not plot3d._viewer_active and plot3d._mesh is None
runtime._unload('engtools.plots.plot3d', plot3d)
del plot3d
absent()

# Match FAT32: rename cannot overwrite an existing destination.
rename = vm.storage.rename
def fat_rename(source, target):
    return False if vm.storage.exists(target) else rename(source, target)
vm.storage.rename = fat_rename

app = Grapher()
vm.add(View('grapher', app.run, app.start, app.stop)); vm.switch_to('grapher')
assert app.page == 'plot' and app.mode == '2d'
finish(app.viewer)
key(k.BUTTON_F9); assert app.page == 'help'
key(k.BUTTON_ESCAPE); assert app.page == 'plot'
key(k.BUTTON_F3)
for _ in range(3): key(k.BUTTON_DOWN)
key(k.BUTTON_CENTER); assert app.page == 'options'
key(k.BUTTON_CENTER); assert app.viewer.controller.app.state == 'expressions'
key(k.BUTTON_ESCAPE); assert app.page == 'plot'
key(k.BUTTON_RIGHT)
original_bounds = app.viewer.controller.app.bounds[:]
key(k.BUTTON_CENTER); key(k.BUTTON_CENTER)
assert app.viewer.controller.app.state == 'input'
key(k.BUTTON_ESCAPE); key(k.BUTTON_ESCAPE)
key(k.BUTTON_F2)
assert app.mode == '3d' and 'engtools.plots.plot2d' not in sys.modules
finish(app.viewer)
key(k.BUTTON_SPACE); key(k.BUTTON_RIGHT)
yaw = app.viewer.engine._yaw
key(k.BUTTON_F2); finish(app.viewer)
assert app.viewer.controller.app.bounds == original_bounds
key(k.BUTTON_F2); finish(app.viewer)
assert app.viewer.engine._yaw == yaw
key(k.BUTTON_F3); assert app.page == 'menu'
key(k.BUTTON_F9); assert app.page == 'help'
key(k.BUTTON_ESCAPE); key(k.BUTTON_ESCAPE)
assert vm.current_view.name == 'parent'
absent()
assert vm.storage.exists(SESSION)
assert not vm.storage.exists(SESSION + '.bak')
for path in legacy:
    assert vm.storage.read(path) == 'legacy sentinel'
print('PASS: keyboard mode switching preserves bounds/camera; legacy sessions stay untouched')

# Reopening restores both documents and releases memory on repeated switches.
app = Grapher()
vm.add(View('grapher', app.run, app.start, app.stop)); vm.switch_to('grapher')
assert app.mode == '3d'
finish(app.viewer)
assert app.viewer.engine._yaw == yaw
measurements = []
for i in range(6):
    key(k.BUTTON_F2); finish(app.viewer)
    key(k.BUTTON_F2); finish(app.viewer)
    vm._log.logs[:] = []
    gc.collect()
    measurements.append(gc.mem_alloc())
assert max(measurements[2:]) - min(measurements[2:]) < 2048, measurements
print('PASS: repeated 2D/3D switches have bounded retained heap:', measurements)
key(k.BUTTON_F3)
write = vm.storage.write
vm.storage.write = lambda *args: False
old = vm.storage.read(SESSION)
key(k.BUTTON_ESCAPE)
assert vm.current_view.name == 'grapher' and app.page == 'menu' and app.error
assert vm.storage.read(SESSION) == old
vm.storage.write = write
def fail_replace(source, target):
    if source == SESSION + '.tmp':
        return False
    return fat_rename(source, target)
vm.storage.rename = fail_replace
key(k.BUTTON_ESCAPE)
assert vm.current_view.name == 'grapher' and app.error
assert vm.storage.read(SESSION) == old
vm.storage.rename = fat_rename
key(k.BUTTON_ESCAPE); absent()
assert vm.current_view.name == 'parent'
print('PASS: FAT32 saves, failed writes/replacements and rollback keep the previous session')

# Recover the backup left by an interrupted replacement and close via Home.
assert vm.storage.rename(SESSION, SESSION + '.bak')
app = Grapher()
vm.add(View('grapher', app.run, app.start, app.stop)); vm.switch_to('grapher')
assert app.mode == '3d' and app.page == 'plot'
assert vm.storage.exists(SESSION) and not vm.storage.exists(SESSION + '.bak')
key(k.BUTTON_HOME)
assert vm.current_view.name == 'parent'
absent()
print('PASS: backup recovery and Home cleanup')
