"""Core housekeeping stays off the SD card when nothing has changed.

Run with the desktop MicroPython build, from the project root.
"""
import os, sys
from time import ticks_ms
root = os.getcwd()
for part in ('src/MicroPython', 'simulator/hardware', 'builds/MicroPython/apps_unfrozen'):
    sys.path.insert(0, root + '/' + part)
import sim_runtime
sd = '/private/tmp/gungos-housekeeping-test-' + str(ticks_ms())
sim_runtime.configure(root, sd, root + '/builds/MicroPython/apps_unfrozen', 1, 'picocalc-pico2w', 0,
                      True, False, False, False, '', _network_mode='offline', _audio_mode='silent')
from picoware.system.view import View
from picoware.system.view_manager import ViewManager
from picoware.system.storage import Storage
from picoware.system import buttons as k
from picoware.applications import desktop
from picoware.applications.wifi import utils as wifi_utils

# Saved Wi-Fi is looked up (SD settings and flash secrets) once per retry
# interval on the home screen, not on every frame.
lookups = []


def counted_connect(view_manager):
    lookups.append(ticks_ms())
    return False  # as when no network is saved


wifi_utils.connect_to_saved_wifi = counted_connect
vm = ViewManager()
vm.add(View('desktop_view', desktop.run, desktop.start, desktop.stop))
vm.switch_to('desktop_view')
vm.wifi.disconnect()
assert vm.has_wifi and not vm.wifi.is_connected() and vm.wifi.state == 0
for _ in range(40):
    vm.run()
assert len(lookups) == 1, lookups  # desktop.start only
desktop._wifi_retry = ticks_ms()  # the interval has passed
vm.run(); vm.run()
assert len(lookups) == 2, lookups
print('PASS: saved Wi-Fi is retried once per', desktop.RETRY_MS, 'ms')

# The app loader lists the SD app folders only when something new was
# imported since the last release.
listed = []
listdir = Storage.listdir


def counted_listdir(self, path=''):
    listed.append(path)
    return listdir(self, path)


Storage.listdir = counted_listdir
loader = vm.app_loader
loader.release_unused()
listed[:] = []
for _ in range(3):
    assert loader.release_unused() == 0
assert not listed, listed
__import__('picoware.gui.date_picker')  # a module the menus have not used yet
loader.release_unused()
assert listed
listed[:] = []
loader.release_unused()
assert not listed, listed
Storage.listdir = listdir
print('PASS: app folders are listed only after new imports')

# Key and character tables: every printable key types its own character.
inp = vm.input_manager
for code in range(32, 127):
    inp._was_capitalized = False  # as on_key_callback does for each key
    button = inp._key_to_button(code)
    assert button != k.BUTTON_NONE, code
    assert inp.button_to_char(button) == chr(code), (code, inp.button_to_char(button))
assert inp.button_to_char(k.BUTTON_CENTER) == '\n'
assert inp.button_to_char(k.BUTTON_UP) == inp.button_to_char(k.BUTTON_NONE) == ''
assert inp._key_to_button(0x80) == k.BUTTON_NONE
assert inp._key_to_button(k.KEY_ALT_A + 18) == k.BUTTON_ALT_S
assert inp._key_to_button(k.KEY_F10) == k.BUTTON_F10
print('PASS: printable keys round-trip through the byte tables')

# Removing a view keeps its neighbours and the array's capacity.
for name in ('first', 'second', 'third'):
    assert vm.add(View(name, None, None, None))
count = vm.view_count
vm.remove('second')
assert vm.view_count == count - 1
assert vm.get_view('first') and vm.get_view('third') and vm.get_view('second') is None
while vm.add(View('extra%d' % vm.view_count, None, None, None)):
    pass
assert vm.view_count == vm.MAX_VIEWS and len(vm.views) == vm.MAX_VIEWS
print('PASS: ViewManager.remove keeps the other views')
