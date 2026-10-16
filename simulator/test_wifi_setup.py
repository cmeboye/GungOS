"""Run from the repo root with builds/MicroPython/desktop/micropython -X heapsize=16M simulator/test_wifi_setup.py."""

import os
import sys
from time import sleep, ticks_ms

root = os.getcwd()
sys.path.insert(0, root + '/src/MicroPython')
sys.path.insert(0, root + '/simulator/hardware')
import sim_runtime
sd_root = '/private/tmp/picoware-wifi-regression-' + str(ticks_ms())
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

vm = ViewManager()
assert scan.start(vm)
assert scan.__save_ssid(vm)
assert utils.load_wifi_ssid(vm) == 'Lab (2.4 GHz)'
scan.stop(vm)
vm.add(View('wifi_password', password.run, password.start, password.stop))
vm.switch_to('wifi_password')
vm.run()
for char in 'test-pass':
    sim_runtime.enqueue_text(char)
    vm.run()
sim_runtime.enqueue_key_names('enter')
for i in range(150):
    sim_runtime.loop_polled()
    vm.run()
    sleep(0.01)
    if vm.wifi.is_connected():
        break
assert vm._current_view.name == 'wifi_connect', 'Enter did not open connection status'
assert vm.wifi.is_connected(), 'Connection was not started or did not complete'
saved = Settings(vm.storage).wifi_settings
assert saved == {'ssid': 'Lab (2.4 GHz)', 'password': 'test-pass'}, 'Credentials did not persist'
assert 'Connected successfully!' in connect._get_status_text(vm)
print('PASS: scanned SSID with parentheses preserved; Enter saves and connects')
print('PASS: fresh Settings instance reloads both credentials')

class FailingStorage:
    def __init__(self, storage):
        self.storage = storage
    def exists(self, path):
        return self.storage.exists(path)
    def read(self, path):
        return self.storage.read(path)
    def serialize(self, value, path):
        return False

failed = FailingStorage(vm.storage)
assert not utils.save_wifi_ssid(failed, 'Other')
assert not utils.save_wifi_password(failed, 'other-pass')
assert Settings(vm.storage).wifi_settings == saved
print('PASS: failed writes return failure and retain saved credentials')

vm.wifi.disconnect()
vm.switch_to('wifi_password', push_view=False)
original_storage = vm._storage
vm._storage = failed
alerts = []
# Avoid waiting for user input in the save-error alert.
original_alert = ViewManager.alert
ViewManager.alert = lambda self, message, *args: alerts.append(message)
password.__callback_save(vm.keyboard.response)
vm.run()
assert vm._current_view.name == 'wifi_password'
assert alerts and 'Failed to save' in alerts[0]
assert not vm.wifi.is_connected()
assert vm.keyboard.response == 'test-pass'
vm._storage = original_storage
vm.add(View('wifi_ssid', ssid.run, ssid.start, ssid.stop))
vm.switch_to('wifi_ssid', push_view=False)
vm._storage = failed
alerts.clear()
ssid.__callback_save(vm.keyboard.response)
vm.run()
assert vm._current_view.name == 'wifi_ssid'
assert alerts and 'Failed to save WiFi SSID' in alerts[0]
assert vm.keyboard.response == 'Lab (2.4 GHz)'
ViewManager.alert = original_alert
vm._storage = original_storage
print('PASS: password write failure stays in editor without connecting')
print('PASS: SSID write failure stays in editor')

assert utils.save_wifi_password(vm.storage, '')
assert utils.load_wifi_password(vm) == ''
print('PASS: empty password is accepted for open networks')
del vm
