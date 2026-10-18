"""Deterministic Lorenz pacing, settings transactions, limits and widget controls."""
import os, sys
from time import ticks_ms
root = os.getcwd()
for path in ('src/MicroPython', 'simulator/hardware', 'builds/MicroPython/apps_unfrozen',
             'builds/MicroPython/apps_unfrozen/misc/screensavers'):
    sys.path.insert(0, root + '/' + path)
import sim_runtime
output = '/private/tmp/gungos-lorenz-previews'
sim_runtime.mkdir_p(output)
sim_runtime.configure(root, '/private/tmp/gungos-lorenz-test-' + str(ticks_ms()),
                      root + '/builds/MicroPython/apps_unfrozen', 1, 'picocalc-pico2w',
                      0, True, False, False, False, '', _network_mode='offline',
                      _audio_mode='silent', _sd_profile='clean')
from picoware.system.view_manager import ViewManager
from picoware.system.settings import Settings
from picoware.system.storage import Storage
from picoware.system import buttons as k
from picoware.gui.widget import WidgetDraw, WidgetContext
import Lorenz
vm = ViewManager(); vm._wifi = None
# Clock-controlled tests do not infer Pico speed from the host interpreter.
clock = [0]
Lorenz.ticks_ms = lambda: clock[0]
Lorenz.ticks_us = lambda: clock[0] * 1000
assert Lorenz.start(vm)
def key(button, advance=125):
    clock[0] += advance
    vm._button = button
    Lorenz.run(vm)
def frames(count=60, interval=125):
    for _ in range(count): key(k.BUTTON_NONE, interval)
def snap(name): sim_runtime.lcd_screenshot(output + '/' + name + '.bmp')
assert Lorenz._options == Lorenz.DEFAULTS
frames()
assert Lorenz._count == 768 and len(Lorenz._trail) == 1536
assert 7.9 < Lorenz._actual_fps < 8.1
snap('smooth')
key(k.BUTTON_F2); assert Lorenz._draft is not None
snap('settings')
# Unapplied edits never change active options or storage.
original = Lorenz._options.copy()
key(k.BUTTON_RIGHT); assert Lorenz._draft['detail'] == 2
key(k.BUTTON_DOWN); key(k.BUTTON_RIGHT); assert Lorenz._draft['points'] == 1536
key(k.BUTTON_ESCAPE)
assert Lorenz._draft is None and Lorenz._options == original
assert 'lorenz' not in Settings(vm.storage).settings
# Escape closes the overlay instead of leaving the screensaver.
key(k.BUTTON_NONE)
# Read-only and falsely-successful SD writes leave the active demo intact.
key(k.BUTTON_F2); key(k.BUTTON_RIGHT)
key(k.BUTTON_DOWN); key(k.BUTTON_RIGHT)
old_trail = Lorenz._trail
serialize = Storage.serialize
for result in (False, True):
    Storage.serialize = lambda *args, **kwargs: result
    key(k.BUTTON_F2)
    assert Lorenz._draft is not None and 'save failed' in Lorenz._error
    assert Lorenz._trail is old_trail and Lorenz._options == original
    assert 'lorenz' not in Settings(vm.storage).settings
Storage.serialize = serialize
snap('save-error')
# Allocation failure is recoverable and must not persist an unusable capacity.
allocate = Lorenz._allocate
Lorenz._allocate = lambda points: (_ for _ in ()).throw(MemoryError())
key(k.BUTTON_F2)
assert Lorenz._options == original and 'heap' in Lorenz._error
assert 'lorenz' not in Settings(vm.storage).settings
Lorenz._allocate = allocate
assert Settings(vm.storage).update({'wifi_ssid': 'Lorenz regression', 'untouched': 'keep'})
key(k.BUTTON_F2)
assert Lorenz._draft is None and Lorenz._options['points'] == 1536
assert Lorenz._count == 0 and len(Lorenz._trail) == 3072
saved = Settings(vm.storage)
assert saved.settings['lorenz']['detail'] == 2
assert saved.wifi_settings['ssid'] == 'Lorenz regression' and saved.settings['untouched'] == 'keep'
Lorenz.stop(vm); assert Lorenz._trail is None
assert Lorenz.start(vm) and Lorenz._options['points'] == 1536
# Different refresh targets integrate the same number of steps per second.
states = []
for fps in Lorenz.RATES:
    Lorenz._options = dict(detail=3, points=768, fps=fps, stats=True)
    Lorenz._trail = Lorenz._allocate(768); Lorenz._reset()
    for _ in range(fps):
        Lorenz._next = 0
        key(k.BUTTON_NONE, max(1, 1000 // fps))
    states.append((Lorenz._x, Lorenz._y, Lorenz._z))
    assert Lorenz._count == 128
assert all(state == states[0] for state in states)
# Full-screen detail comparisons keep the same evolution and time span.
for stride, points, name in ((12,192,'coarse'), (3,768,'smooth'), (1,6144,'stress')):
    Lorenz._options = dict(detail=stride, points=points, fps=8, stats=True)
    Lorenz._trail = Lorenz._allocate(points); Lorenz._reset()
    frames(130 if points==6144 else 60)
    assert Lorenz._count == points and len(Lorenz._trail) == points*2
    snap(name)
    if name == 'stress':
        key(k.BUTTON_F2); snap('stress-settings'); key(k.BUTTON_ESCAPE)
# Pause, reset and stats work while maintaining responsiveness.
key(k.BUTTON_SPACE); state = (Lorenz._x, Lorenz._y, Lorenz._z)
frames(3); assert state == (Lorenz._x, Lorenz._y, Lorenz._z)
key(k.BUTTON_F5); assert Lorenz._count == 0
key(k.BUTTON_F4); assert not Lorenz._options['stats']
Lorenz.stop(vm)
# A native-size widget receives F2 only after the desktop gives it focus.
class Host:
    def __init__(self): self.master, self.focused = vm, True
host = Host()
widget = WidgetContext(host, WidgetDraw(vm,240,240))
assert Lorenz.start(widget) and Lorenz._widget
Lorenz._options['fps'] = 30
assert Lorenz._effective_fps() == 8
for _ in range(60):
    clock[0] += 125; widget.input_manager._last_button = k.BUTTON_NONE; Lorenz.run(widget)
widget.input_manager._last_button = k.BUTTON_F2; Lorenz.run(widget)
assert Lorenz._draft and Lorenz._effective_fps(Lorenz._draft) == 8
# Compose the widget at native size solely for a readable screenshot.
vm.draw.fill_screen(0)
vm.draw._bytearray(0,0,240,240,widget.draw.buffer)
snap('widget-settings')
widget.input_manager._last_button = k.BUTTON_ESCAPE; Lorenz.run(widget)
assert Lorenz._draft is None and host.focused
widget.input_manager._last_button = k.BUTTON_NONE; clock[0] += 125; Lorenz.run(widget)
vm.draw.fill_screen(0); vm.draw._bytearray(0,0,240,240,widget.draw.buffer); snap('widget')
widget.input_manager._last_button = k.BUTTON_ESCAPE; Lorenz.run(widget)
assert not host.focused
Lorenz.stop(widget)
# Invalid saved values are ignored individually; a large-allocation startup failure
# falls back to a small live demo without rewriting the saved configuration.
assert Settings(vm.storage).update({'lorenz': {'points': 999999, 'fps': 0, 'detail': 0, 'stats': 'bad'}})
assert Lorenz.start(vm) and Lorenz._options == Lorenz.DEFAULTS
Lorenz.stop(vm)
assert Settings(vm.storage).update({'lorenz': dict(detail=1, points=6144, fps=30, stats=True)})
Lorenz._allocate = lambda points: allocate(points) if points == 192 else (_ for _ in ()).throw(MemoryError())
assert Lorenz.start(vm) and Lorenz._options['points'] == 192 and Lorenz._notice
assert Settings(vm.storage).settings['lorenz']['points'] == 6144
Lorenz._allocate = allocate
Lorenz.stop(vm)
print('PASS: denser bounded trails, constant integration rate across 4-30 FPS, pause/reset and native widget controls')
print('PASS: cancel, verified saves, SD/heap failures, restart persistence, input validation and low-memory fallback')
print('Screenshots: ' + output)
