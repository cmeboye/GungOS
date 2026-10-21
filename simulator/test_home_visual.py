"""Run from the repo root with builds/MicroPython/desktop/micropython -X heapsize=16M simulator/test_home_visual.py."""

import os
import sys
from time import sleep, ticks_ms

root = os.getcwd()
sys.path.insert(0, root + '/src/MicroPython')
sys.path.insert(0, root + '/simulator/hardware')
import sim_runtime
sd_root = '/private/tmp/picoware-home-regression-' + str(ticks_ms())
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


from picoware.applications import desktop
from picoware.gui.draw import Draw
class Clock:
    def __init__(self): self.value=(2026,10,13,1,10,10,0,0)
    def datetime(self): return self.value
    def deinit(self): pass
vm=ViewManager()
vm._wifi=None
vm.time._rtc=Clock()
vm.time._is_set=True
assert desktop.start(vm)
swaps=[0]
original=Draw.swap
def count(self,*args,**kwargs):
    swaps[0]+=1
    return original(self,*args,**kwargs)
Draw.swap=count
desktop.run(vm)
vm.draw.screenshot('/private/tmp/picoware-logo-clock.bmp')
assert swaps[0]==1
for second in (1,15,30,59):
    vm.time._rtc.value=(2026,10,13,1,10,10,second,0)
    desktop.run(vm)
assert swaps[0]==1, 'Clock redraws on second changes'
vm.time._rtc.value=(2026,10,13,1,10,11,0,0)
desktop.run(vm)
assert swaps[0]==2, 'Minute change did not redraw'
vm.time._rtc.value=(2026,10,14,2,0,0,0,0)
desktop.run(vm)
assert swaps[0]==3, 'Date change did not redraw'
vm.time._is_set=False
desktop.run(vm)
assert swaps[0]==4, 'Unset time should show a placeholder'
vm.draw.screenshot('/private/tmp/picoware-logo-clock-unset.bmp')
vm.time._is_set=True
vm.background_color=0xFFFF
vm.foreground_color=0
vm.selected_color=0xF800
desktop.run(vm)
assert swaps[0]==5, 'Theme change did not redraw'
vm.draw.screenshot('/private/tmp/picoware-logo-clock-light.bmp')
desktop.stop(vm)
assert desktop._dashboard is None, 'Decoded logo should be released in menus'
Draw.swap=original
print('PASS: logo decodes, clock/date update by minute and midnight, unset time handled')
print('PASS: no per-second redraws; dark/light themes work; logo released on leaving home')
del vm
