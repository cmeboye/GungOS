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
vm=ViewManager()
vm.add(View('desktop', lambda vm: None, lambda vm: True, lambda vm: None))
vm.switch_to('desktop')
assert library.CATEGORIES==('Apps','System','Comms','Utils')
assert library.SECTIONS[0]==('PicoDESK','PicoLAB','Games','Misc')
assert library.SECTIONS[2]==('Bluetooth','USB','WiFi')
# Each desktop entry opens its view, answers F9 and returns to the desktop.
for item,view in (('WiFi','wifi'),('File Manager','file_manager'),('PicoDESK','app_PicoDESK'),
                  ('Settings','settings'),('Info','system_info')):
    library.launch(vm,item)
    assert vm.current_view.name==view,(item,vm.current_view.name)
    assert vm.help,item+' has no F9 help'
    vm.back()
    assert vm.current_view.name=='desktop',item
# Root app launches reuse registered views rather than filling MAX_VIEWS.
count=vm._view_count
library.launch(vm,'WiFi')
vm.back()
assert vm._view_count==count
# Routing aliases still produce paths through the reorganized menu.
for name in ('Menu','Apps','Comms','WiFi','Settings','Applications/Misc/Screensavers','Utilities/File Manager','Apps/PicoLAB/Graph','Apps/PicoLAB/Graph3D','PicoLAB'):
    sim_runtime._keys=[]
    sim_runtime.request_open(name)
    assert sim_runtime._keys
print('PASS: release Apps, direct Graph launch, Settings, and essential feature launches')
print('PASS: desktop entries open with F9 help and return, existing views reused, simulator routes resolve')
del vm
