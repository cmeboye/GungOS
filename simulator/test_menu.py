"""Run from the repo root with builds/MicroPython/desktop/micropython -X heapsize=16M simulator/test_menu.py."""

import os
import sys
from time import sleep, ticks_ms

root = os.getcwd()
sys.path.insert(0, root + '/src/MicroPython')
sys.path.insert(0, root + '/simulator/hardware')
import sim_runtime
sd_root = '/private/tmp/picoware-menu-regression-' + str(ticks_ms())
sim_runtime.configure(root, sd_root, root + '/builds/MicroPython/apps_unfrozen',
                      1, 'picocalc-pico2w', 0, True, False, False, False, '',
                      _network_mode='offline', _audio_mode='silent')
sim_runtime.mkdir_p(sd_root)
import network
network.sim_clear_aps()
network.sim_add_ap('Lab (2.4 GHz)', passphrase='test-pass', rssi=-30)
from picoware.system.view_manager import ViewManager
from picoware.system.view import View
from picoware.system.settings import Settings
from picoware.applications.wifi import scan, password, ssid, connect, utils
from picoware.system.input import Input
def simulator_input(self):
    sim_runtime.input_polled()
    return self._last_button
# Use the same PicoCalc input hook as simulator/run.py.
Input.button = property(simulator_input)


from picoware.applications import library
from picoware.system.buttons import BUTTON_UP, BUTTON_DOWN, BUTTON_LEFT, BUTTON_RIGHT, BUTTON_CENTER, BUTTON_ESCAPE
vm=ViewManager()
vm.add(View('desktop', lambda vm: None, lambda vm: True, lambda vm: None))
vm.switch_to('desktop')
vm.add(View('library',library.run,library.start,library.stop))
vm.switch_to('library')
def key(button):
    vm._button=button
    library.run(vm)
assert library.CATEGORIES==('Apps','System','Comms','Utils')
assert library._library.items==('PicoDESK','PicoLAB','Games','Misc')
vm.draw.screenshot('/private/tmp/picoware-menu-apps.bmp')
key(BUTTON_DOWN)
assert library._library.category==1 and library._library.current_item=='Settings'
key(BUTTON_DOWN)
assert library._library.items==('Bluetooth','USB','WiFi')
vm.draw.screenshot('/private/tmp/picoware-menu-comms.bmp')
key(BUTTON_RIGHT)
for i in range(2): key(BUTTON_DOWN)
key(BUTTON_CENTER)
assert vm.current_view.name=='wifi'
vm.back()
assert vm.current_view.name=='library'
assert library._library.category==2 and library._library.focus_right
assert library._library.current_item=='WiFi'
key(BUTTON_ESCAPE)
assert not library._library.focus_right
key(BUTTON_DOWN)
assert library._library.category==3
key(BUTTON_RIGHT)
assert library._library.current_item=='File Manager'
key(BUTTON_CENTER)
assert vm.current_view.name=='file_manager'
vm.back()
assert library._library.current_item=='File Manager'
key(BUTTON_LEFT)
key(BUTTON_DOWN)
assert library._library.category==0
key(BUTTON_RIGHT)
assert library._library.current_item=='PicoDESK'
key(BUTTON_CENTER)
assert vm.current_view.name=='app_PicoDESK'
vm.back()
assert library._library.current_item=='PicoDESK'
assert library._library.nested_items is None
key(BUTTON_ESCAPE)
assert not library._library.focus_right
key(BUTTON_DOWN)
key(BUTTON_RIGHT)
key(BUTTON_CENTER)
assert vm.current_view.name=='settings'
vm.back()
assert library._library.category==1
# Root app launches reuse registered views rather than filling MAX_VIEWS.
count=vm._view_count
library.launch(vm,'WiFi')
vm.back()
assert vm._view_count==count
assert library._library.category==1
# Routing aliases still produce paths through the reorganized menu.
for name in ('Menu','Apps','Comms','WiFi','Settings','Applications/Misc/Screensavers','Utilities/File Manager','Apps/PicoLAB/Graph','Apps/PicoLAB/Graph3D','PicoLAB'):
    sim_runtime._keys=[]
    sim_runtime.request_open(name)
    assert sim_runtime._keys
print('PASS: release Apps, direct Graph launch, Settings, and essential feature launches')
print('PASS: back navigation restores selection, existing views reused, simulator routes resolve')
# Returning from the left sidebar exits to the desktop.
key(BUTTON_LEFT)
key(BUTTON_ESCAPE)
assert vm.current_view.name=='desktop'
print('PASS: BACK from sidebar returns to desktop')
del vm
