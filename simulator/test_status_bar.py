"""Native status rendering, charging transitions, themes and passive BLE status."""
import os,sys
from time import ticks_ms
root=os.getcwd()
for path in ('src/MicroPython','simulator/hardware','builds/MicroPython/apps_unfrozen'):
    sys.path.insert(0,root+'/'+path)
import sim_runtime
sim_runtime.configure(root,'/private/tmp/gungos-status-test-'+str(ticks_ms()),root+'/builds/MicroPython/apps_unfrozen',1,
                      'picocalc-pico2w',0,True,False,False,False,'',_network_mode='offline',_audio_mode='silent',_sd_profile='clean')
from picoware.system.view_manager import ViewManager
from picoware.applications import desktop
from picoware.gui.status_bar import foreground,bitmap
from picoware.assets.status_icons import ICONS
from picoware.system import bluetooth
import picoware_southbridge as power
class Clock:
    def datetime(self):return (2026,10,16,4,14,23,0,0)
    def deinit(self):pass
class WiFi:
    connected=False
    def is_connected(self):return self.connected
    def connect_async(self,*args,**kwargs):return False
    def poll(self):pass
    def reset(self):pass
vm=ViewManager();vm._wifi=WiFi();vm.time._rtc=Clock();vm.time._is_set=True
assert desktop.start(vm)
home=desktop._dashboard;token=bluetooth._owner_token
power.set_battery_percentage(50);power.set_battery_charging(False)
home.status_bar.sample(force=True);home.update()
assert bluetooth._owner_token==token,'Drawing indicators initialized the BLE radio'
assert not home.status[2] and not home.status[7]
assert home.status[1]==50 and home.status[6] is False
from sim_pixels import Pixels
fb=Pixels(vm.draw)
assert all(fb.pixel(0,y)==0 for y in range(16))
# One-line footer: F9 Help in the accent colour below a background gap.
assert any(fb.pixel(x,y)==vm.selected_color for x in range(6,50) for y in range(308,320))
assert fb.pixel(0,303)==fb.pixel(0,307)==vm.background_color
assert fb.pixel(0,16)==vm.background_color
before=tuple(fb.pixel(x,y) for y in range(16) for x in range(250,294))
power.set_battery_charging(True)
assert power.read_battery()==(50|0x80) and vm.battery.is_charging
home.status_bar.sample(force=True);home.update()
after=tuple(fb.pixel(x,y) for y in range(16) for x in range(250,294))
assert home.status[6] is True and before==after,'Charging changed the percentage-only display'
vm._wifi.connected=True;home.update();assert home.status[2]
bt=bluetooth.Bluetooth(vm.storage)
assert bt.connect(0,b'\x02\x50\x43\x57\x10\x01')
for _ in range(20):bt.poll()
assert bluetooth.connection_active()
home.update();assert home.status[7]
bt.close();home.update();assert not home.status[7]
vm._wifi.connected=False;home.update();assert not home.status[2]
print('PASS: matching 16-pixel bars, real charging flag, passive BLE status and redraws on link/charging changes')

assert len(ICONS)==4 and not any(name.startswith('battery_') for name in ICONS)
for value in (0,15,25,50,75,100):
    power.set_battery_percentage(value);home.status_bar.sample(force=True);home.update()
    assert home.status[1]==value
assert len(home.status_bar._icons)==2
assert foreground(0x001F)==0xFFFF and foreground(0xFFE0)==0
for name in ICONS:
    for theme in (0x001F,0xFFE0):
        width,height,raw=bitmap(name,theme)
        assert height<=16 and len(raw)==width*height*2
vm.selected_color=0xFFE0;home.update()
assert fb.pixel(0,0)==0 and any(fb.pixel(x,y)==0xFFE0 for x in range(6,50) for y in range(308,320))
assert any(fb.pixel(x,y)==0xFFFF for x in range(8,40) for y in range(2,14)),'Clock must stay white on the black status bar'
assert len(home.status_bar._icons)==2
print('PASS: exact battery percentages, alpha blits, bounded two-icon cache and live theme contrast')
desktop.stop(vm)
