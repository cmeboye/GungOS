"""Run from the repo root with builds/MicroPython/desktop/micropython -X heapsize=16M simulator/test_preferences.py."""

import os
import sys
from time import sleep, ticks_ms

root = os.getcwd()
sys.path.insert(0, root + '/src/MicroPython')
sys.path.insert(0, root + '/simulator/hardware')
import sim_runtime
sd_root = '/private/tmp/picoware-preferences-regression-' + str(ticks_ms())
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


from picoware.applications import settings as app
from picoware.system.buttons import BUTTON_CENTER, BUTTON_F1
vm=ViewManager()
alerts=[]
ViewManager.alert=lambda self, message, *args: alerts.append(message)
# Start with the same minimal WiFi-only file that the user created manually.
assert vm.storage.serialize({'wifi_ssid':'Initial', 'wifi_password':'initial-pass', 'custom_field':'keep'}, 'picoware/settings/picoware.json')
assert app.start(vm)
# Credentials saved elsewhere after opening Settings must not be overwritten.
assert utils.save_wifi_ssid(vm.storage, 'Updated')
assert utils.save_wifi_password(vm.storage, 'updated-pass')
app.__open_appearance()
app._appearance.values['theme_color']=0xF800
vm._button=BUTTON_F1
app.run(vm)
from picoware.gui.theme_picker import PRESETS
red=PRESETS[0][1]
assert vm.selected_color == red
app.__open_choice_brightness()
app._choice.state=3
vm._button=BUTTON_CENTER
app.run(vm)
assert sim_runtime.lcd_brightness == 40
assert not app._menu.item_exists('Dark Mode')
assert not app._menu.item_exists('Exit Button')
assert Settings(vm.storage).update({'dark_mode':False})
assert vm.background_color == 0 and 'dark_mode' not in Settings(vm.storage).settings
assert not any(app._menu.item_exists(name) for name in
               ('Debug', 'Onscreen Keyboard', 'Fast Drawing'))
# Removing the menu toggle must preserve old SD preferences and keyboard APIs.
assert Settings(vm.storage).update({'onscreen_keyboard': True})
vm.keyboard.show_keyboard = True
assert vm.keyboard.show_keyboard
saved=Settings(vm.storage)
assert saved.theme_color==red and saved.screen_brightness==40
assert saved.wifi_settings == {'ssid':'Updated','password':'updated-pass'}
assert saved.settings['custom_field']=='keep'
assert Settings.get(vm.storage, 'onscreen_keyboard', False)
print('PASS: confirmed theme, brightness, fixed dark mode, and keyboard preferences persist')
print('PASS: stale Settings view preserves newer WiFi credentials and unknown fields')
class FailedWrites:
    def __init__(self, backing, claim_success=False): self.backing=backing; self.claim_success=claim_success
    def exists(self,path): return self.backing.exists(path)
    def read(self,path): return self.backing.read(path)
    def serialize(self,value,path): return self.claim_success
storage=vm.storage
for claim_success in (False, True):
    app._settings._storage=FailedWrites(storage,claim_success)
    app.__open_choice_brightness()
    app._choice.state=7
    vm._button=BUTTON_CENTER
    app.run(vm)
    assert app._choice is not None
    assert sim_runtime.lcd_brightness==40 and Settings(storage).screen_brightness==40
    assert alerts and 'Could not save brightness' in alerts[-1]
    app.__open_appearance()
    app._appearance.values['theme_color']=0x07E0
    vm._button=BUTTON_F1
    app.run(vm)
    assert vm.selected_color==red and Settings(storage).theme_color==red
    assert 'Save failed' in app._appearance.error
    failed=Settings(FailedWrites(storage,claim_success))
    try:
        failed.screen_brightness=90
        raise AssertionError('Property setter silently ignored failed write')
    except OSError:
        pass
    assert failed.screen_brightness==40
print('PASS: failed and falsely successful writes do not apply unsaved preferences')
app._settings._storage=storage
# A new ViewManager exercises the same load/apply path as a fresh boot.
app.stop(vm)
del vm
vm=ViewManager()
assert vm.selected_color==red
assert sim_runtime.lcd_brightness==40
assert vm.background_color==0
assert vm.keyboard.show_keyboard
assert Settings(vm.storage).wifi_settings['ssid']=='Updated'
print('PASS: fresh startup restores all preferences and WiFi')
# Unreadable JSON must not be replaced with defaults by a later setting update.
config=Settings(vm.storage)
assert vm.storage.write('picoware/settings/picoware.json', '{invalid', 'w')
assert not config.update({'theme_color':123})
assert vm.storage.read('picoware/settings/picoware.json')=='{invalid'
print('PASS: malformed settings are not overwritten by an update')
del vm
