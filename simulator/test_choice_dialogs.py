"""Modal Choice dialogs (System shutdown, Wi-Fi save) open, navigate and close.

Run from the repo root with builds/MicroPython/desktop/micropython -X heapsize=16M simulator/test_choice_dialogs.py.
"""

import os
import sys
from time import ticks_ms

root = os.getcwd()
sys.path.insert(0, root + '/src/MicroPython')
sys.path.insert(0, root + '/simulator/hardware')
import sim_runtime
sd_root = '/private/tmp/gungos-choice-regression-' + str(ticks_ms())
sim_runtime.configure(root, sd_root, root + '/builds/MicroPython/apps_unfrozen',
                      1, 'picocalc-pico2w', 0, True, False, False, False, '',
                      _network_mode='offline', _audio_mode='silent')
sim_runtime.mkdir_p(sd_root)
from picoware.system.view_manager import ViewManager
from picoware.system.input import Input
from picoware.system import buttons as k
from picoware.gui.choice import Choice
from picoware.system.vector import Vector

# Feed each modal loop a fixed key sequence.
pending = []
def scripted_button(self):
    if self._last_button == -1 and pending:
        self._last_button = pending.pop(0)
    return self._last_button
Input.button = property(scripted_button)

vm = ViewManager()
vm._wifi = None

choice = Choice(vm.draw, Vector(0, 0), vm.draw.size, 'Test?', ['No', 'Yes'])
assert not choice.is_open()
choice.open(); assert choice.is_open()
choice.scroll_down(); assert choice.state == 1
choice.close(); assert not choice.is_open()

# System > Shutdown: Escape and "No" both return without shutting down.
from picoware.applications.system import system
from picoware.system.system import System
shutdowns = []
System.shutdown_device = lambda self, view_manager=None: shutdowns.append(True)
# The question is a box over the screen; closing it puts the screen back.
vm.draw._fill_rectangle(0, 0, 320, 320, 0x07E0)
vm.draw.swap()
screen = [vm.draw._read_row(y) for y in range(320)]
pending[:] = [k.BUTTON_ESCAPE]
system.activate(vm, 4)
pending[:] = [k.BUTTON_CENTER]
system.activate(vm, 4)
assert not shutdowns, 'Shutdown dialog must cancel cleanly'
assert [vm.draw._read_row(y) for y in range(320)] == screen, 'The screen behind the box must return'
pending[:] = [k.BUTTON_DOWN, k.BUTTON_CENTER]
system.activate(vm, 4)
assert shutdowns == [True], 'Choosing Yes must request shutdown'

# Wi-Fi scan > save network: the dialog returns the chosen answer.
from picoware.applications.wifi import scan
class Item:
    current_item = 'Lab (2.4 GHz) (-30 dBm)'
scan._scan = Item()
ask = getattr(scan, '__should_save_choice')
pending[:] = [k.BUTTON_DOWN, k.BUTTON_CENTER]
assert ask(vm) is True
pending[:] = [k.BUTTON_CENTER]
assert ask(vm) is False
print('PASS: Choice open/close API; shutdown and Wi-Fi save popups answer and restore the screen')
