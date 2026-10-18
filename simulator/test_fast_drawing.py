"""Fast Drawing: PSRAM screen by default, SRAM by preference or borrowed by an app.

Run from the repo root with builds/MicroPython/desktop/micropython -X heapsize=16M simulator/test_fast_drawing.py.
"""

import os
import sys
from time import ticks_ms

root = os.getcwd()
sys.path.insert(0, root + '/src/MicroPython')
sys.path.insert(0, root + '/simulator/hardware')
import sim_runtime
sd_root = '/private/tmp/gungos-fast-drawing-regression-' + str(ticks_ms())
sim_runtime.configure(root, sd_root, root + '/builds/MicroPython/apps_unfrozen',
                      1, 'picocalc-pico2w', 0, True, False, False, False, '',
                      _network_mode='offline', _audio_mode='silent')
sim_runtime.mkdir_p(sd_root)
from picoware.system.view_manager import ViewManager
from picoware.system.view import View
from picoware.system.settings import Settings
from picoware.system import buttons as k

vm = ViewManager()
vm._wifi = None
draw = vm.draw
SRAM, PSRAM = draw.MODE_SRAM, draw.MODE_PSRAM
assert draw.mode == PSRAM and not vm.fast_drawing, 'PSRAM is the default screen mode'

# The preference moves the screen image both ways.
assert vm.set_fast_drawing(True) and draw.mode == SRAM
assert vm.set_fast_drawing(False) and draw.mode == PSRAM

# An app borrows SRAM while it runs and gives it back when its view stops.
def animated_start(view_manager):
    assert view_manager.request_fast_drawing()
    return True
vm.add(View('home', lambda v: None, lambda v: True, lambda v: None))
vm.switch_to('home')
vm.add(View('animated', lambda v: None, animated_start, lambda v: None))
vm.switch_to('animated')
assert draw.mode == SRAM
vm.back()
assert draw.mode == PSRAM, 'Leaving the app returns the SRAM screen'

# Even when the app crashes.
alerts = []
vm.alert = lambda message, back=False, title='Alert': alerts.append(message) or True
def crash(view_manager):
    raise ValueError('boom')
vm.add(View('crashy', crash, animated_start, lambda v: None))
vm.switch_to('crashy')
assert draw.mode == SRAM
vm._button = -1
vm.run()
assert alerts and draw.mode == PSRAM, 'A crashing app must not keep the SRAM screen'

# While an app holds SRAM, a preference change waits for it to stop.
vm.add(View('animated2', lambda v: None, animated_start, lambda v: None))
vm.switch_to('animated2')
assert vm.set_fast_drawing(True) and draw.mode == SRAM
assert vm.set_fast_drawing(False) and draw.mode == SRAM, 'The running app keeps its SRAM screen'
vm.back()
assert draw.mode == PSRAM

# The menu no longer offers Fast Drawing; existing SD preferences and per-app
# borrowing must still work (including a failed SRAM allocation).
from picoware.applications import settings as app
vm.add(View('settings', app.run, app.start, app.stop))
vm.switch_to('settings')
labels = [app._menu.get_item(i) for i in range(app._menu.item_count)]
assert 'Fast Drawing' not in labels
assert Settings(vm.storage).update({'fast_drawing': True})
assert vm.set_fast_drawing(True) and draw.mode == SRAM
assert Settings(vm.storage).update({'fast_drawing': False})
assert vm.set_fast_drawing(False) and draw.mode == PSRAM

draw.set_mode = lambda mode: None
assert Settings(vm.storage).update({'fast_drawing': True})
assert not vm.set_fast_drawing(True)
assert Settings(vm.storage).fast_drawing and draw.mode == PSRAM
del draw.set_mode
vm.back()

# A new start applies the saved preference.
vm2 = ViewManager()
assert vm2.fast_drawing and vm2.draw.mode == SRAM
print('PASS: PSRAM screen by default; saved Fast Drawing preference and per-app SRAM borrowing, also after crashes')
