"""F9 help, alerts, popups and info boxes share one box that restores the screen.

Run from the repo root with builds/MicroPython/desktop/micropython -X heapsize=16M simulator/test_overlay.py.
"""
import os
import sys
from time import ticks_ms

root = os.getcwd()
sys.path.insert(0, root + '/src/MicroPython')
sys.path.insert(0, root + '/simulator/hardware')
import sim_runtime
sd_root = '/private/tmp/gungos-overlay-' + str(ticks_ms())
sim_runtime.configure(root, sd_root, root + '/builds/MicroPython/apps_unfrozen',
                      1, 'picocalc-pico2w', 0, True, False, False, False, '',
                      _network_mode='offline', _audio_mode='silent')
sim_runtime.mkdir_p(sd_root)
from picoware.system.view_manager import ViewManager, SYSTEM_HELP
from picoware.system.view import View
from picoware.system.input import Input
from picoware.system import buttons as k
from picoware.gui import overlay, style

pending = []
def scripted_button(self):
    if self._last_button == -1 and pending:
        self._last_button = pending.pop(0)
    return self._last_button
Input.button = property(scripted_button)

vm = ViewManager()
vm._wifi = None

def key(button):
    vm.input_manager._last_button = button
    vm.run()

def screen():
    return [vm.draw._read_row(y) for y in range(320)]

# Lines: headings stay, short lines keep their spacing, meanings wrap in their column.
lines = overlay.layout(('Keys:', 'F5\t' + 'save and run the file ' * 4, 'A  B   C'), overlay.RECT[2])
assert lines[0] == 'Keys:' and lines[1].startswith('F5\t') and lines[2].startswith('\t')
assert lines[-1] == 'A  B   C'
assert all(len(line.split('\t')[-1]) <= (overlay.RECT[2] - 28) // overlay.CHAR - overlay.KEY_CHARS for line in lines[1:-1])

# A view with help: F9 opens the box after the frame and the view waits behind it.
frames = []
def run(view_manager):
    frames.append(view_manager.button)
    view_manager.draw.fill_screen(0x07E0)
    view_manager.draw._text(10, 100, 'the view', 0, 1)
    view_manager.draw.swap()
vm.add(View('helped', run, lambda v: True, lambda v: None, ('Test:', 'X\tdo something')))
vm.switch_to('helped')
key(-1)
before = screen()
key(k.BUTTON_F9)
assert vm._overlay is not None and vm._overlay.title == 'KEYBINDINGS'
assert vm._overlay.lines[-len(SYSTEM_HELP):] == list(SYSTEM_HELP), 'System keys end every help'
assert frames == [-1], 'F9 must not reach the view'
key(k.BUTTON_DOWN); key(-1)
assert frames == [-1], 'The view waits while the box is open'
key(k.BUTTON_ESCAPE)
assert vm._overlay is None and screen() == before, 'Closing the box restores the screen exactly'
assert len(frames) == 2, 'The view runs again once the box closes'

# A view may change its help, or hand F9 to itself with None.
vm.help = None
key(k.BUTTON_F9)
assert vm._overlay is None and frames[-1] == k.BUTTON_F9

# vm.show() from inside a frame opens over what that frame drew.
def show_run(view_manager):
    view_manager.draw.fill_screen(0xF800)
    view_manager.draw.swap()
    if view_manager.button == k.BUTTON_I:
        view_manager.show('INFO', ('Name\tvalue',))
vm.add(View('shower', show_run, lambda v: True, lambda v: None, style.PAGE_HELP))
vm.switch_to('shower')
key(-1)
behind = screen()
key(k.BUTTON_I)
assert vm._overlay is not None and vm._overlay.shown
assert vm.draw._read_row(overlay.RECT[1]) != behind[overlay.RECT[1]], 'The box is drawn'
key(k.BUTTON_F9)
assert vm._overlay is None and screen() == behind

# HOME with a box open closes it before going home.
vm.show('INFO', ('x',)); key(-1)
key(k.BUTTON_HOME)
assert vm._overlay is None

# Alerts and popups are boxes over the screen too.
key(-1)
behind = screen()
pending[:] = [k.BUTTON_CENTER]
assert vm.alert('Saved.\nAll good.') is True and screen() == behind
pending[:] = [k.BUTTON_ESCAPE]
assert vm.alert('Cancelled') is False and screen() == behind
pending[:] = [k.BUTTON_DOWN, k.BUTTON_CENTER]
assert vm.choose('Shutdown?', ('No', 'Yes')) == 1 and screen() == behind
pending[:] = [k.BUTTON_ESCAPE]
assert vm.choose('Shutdown?', ('No', 'Yes')) == -1 and screen() == behind
print('PASS: help layout, deferred box, exact restore, F9 routing, HOME, alerts and popups')

# Every firmware screen answers F9 with its own help.
from picoware.applications import library
modules = [path for _, path in library._ROUTES.values()]
modules += ['picoware.applications.wifi.' + name for name in ('connect', 'scan', 'server', 'settings', 'ssid', 'password', 'rssi_monitor')]
modules += ['picoware.applications.bluetooth.' + name for name in ('advertise', 'beacon', 'pair', 'rssi_monitor', 'scan', 'uart_chat')]
modules += ['picoware.applications.usb.' + name for name in ('keyboard', 'media_keys', 'numpad', 'payload')]
modules += ['picoware.applications.system.screensaver_setting']
for path in modules:
    module = __import__(path, None, None, ['HELP'])
    lines = getattr(module, 'HELP', None)
    assert lines and lines[0].endswith(':'), path + ' has no F9 help'
    assert all(isinstance(line, str) for line in lines), path
from picoware.gui.dashboard import HELP as desktop_help
assert desktop_help[0].endswith(':')
print('PASS: %d firmware screens provide F9 help' % (len(modules) + 1))
