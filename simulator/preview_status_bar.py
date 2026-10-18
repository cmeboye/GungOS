"""Capture full native framebuffer previews with explicit simulated status states."""
import os,sys
from time import ticks_ms
root=os.getcwd()
for path in ('src/MicroPython','simulator/hardware','builds/MicroPython/apps_unfrozen'):
    sys.path.insert(0,root+'/'+path)
import sim_runtime
argv=getattr(sys,'argv',[])
output=argv[1] if len(argv)>1 else root+'/verification/status-bar'
if not output.startswith('/'):output=root+'/'+output
sim_runtime.mkdir_p(output)
sim_runtime.configure(root,output+'/sd',root+'/builds/MicroPython/apps_unfrozen',1,
                      'picocalc-pico2w',0,True,False,False,False,'',
                      _network_mode='offline',_audio_mode='silent',_sd_profile='clean')
from picoware.system.view_manager import ViewManager
from picoware.applications import desktop
from picoware.system import bluetooth
from picoware.system.buttons import BUTTON_NONE
import picoware_southbridge as power
class Clock:
    def datetime(self):return (2026,10,16,4,14,23,0,0)
    def deinit(self):pass
class WiFiFixture:
    connected=False
    def is_connected(self):return self.connected
    def connect_async(self,*args,**kwargs):return False
    def poll(self):pass
    def reset(self):pass
vm=ViewManager()
vm._wifi=WiFiFixture();vm.time._rtc=Clock();vm.time._is_set=True
assert desktop.start(vm)
home=desktop._dashboard
original=bluetooth.connection_active
state=[False];bluetooth.connection_active=lambda:state[0]
try:
    for level in (15,25,50,75,100):
        for wifi in (False,True):
            for bt in (False,True):
                vm._wifi.connected=wifi;state[0]=bt
                power.set_battery_percentage(level);power.set_battery_charging(False)
                home.status_bar.sample(force=True)
                vm._button=BUTTON_NONE;home.update()
                name='battery_%d_wifi_%s_bt_%s'%(level,'on' if wifi else 'off','on' if bt else 'off')
                vm.draw.screenshot(output+'/'+name+'.bmp')
    for name,colour in (('red',0xF800),('yellow',0xFFE0),('green',0x07E0),('purple',0x780F)):
        vm.selected_color=colour;vm._wifi.connected=True;state[0]=True
        power.set_battery_percentage(50);power.set_battery_charging(True)
        home.status_bar.sample(force=True);home.update()
        vm.draw.screenshot(output+'/theme_'+name+'.bmp')
finally:
    bluetooth.connection_active=original
    desktop.stop(vm)
print('Captured 20 battery/connection combinations and four theme screenshots: '+output)
