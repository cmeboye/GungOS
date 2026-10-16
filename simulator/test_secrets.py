"""Credentials live in internal flash, and old SD copies migrate there.

Run from the repo root with builds/MicroPython/desktop/micropython -X heapsize=16M simulator/test_secrets.py.
"""

import os
import sys
from time import ticks_ms

root = os.getcwd()
sys.path.insert(0, root + '/src/MicroPython')
sys.path.insert(0, root + '/simulator/hardware')
import sim_runtime
sd_root = '/private/tmp/gungos-secrets-regression-' + str(ticks_ms())
sim_runtime.configure(root, sd_root, root + '/builds/MicroPython/apps_unfrozen',
                      1, 'picocalc-pico2w', 0, True, False, False, False, '',
                      _network_mode='offline', _audio_mode='silent')
sim_runtime.mkdir_p(sd_root)
from picoware.system.view_manager import ViewManager
from picoware.system.settings import Settings, SETTINGS_PATH
from picoware.system import secrets

vm = ViewManager()
vm._wifi = None
storage = vm.storage
assert secrets.path().startswith(sd_root + '.flash/'), 'Simulator flash must sit beside the SD card'

# New Wi-Fi credentials: the SSID stays in the SD settings, the password goes to flash.
assert Settings(storage).save_wifi_settings({'ssid': 'Lab', 'password': 'new-pass'})
card = storage.deserialize(SETTINGS_PATH)
assert card['wifi_ssid'] == 'Lab' and 'wifi_password' not in card
assert secrets.get('wifi_password') == 'new-pass'
assert Settings(storage).wifi_settings == {'ssid': 'Lab', 'password': 'new-pass'}

# An SD card from an older release: the plain-text password moves to flash on load.
card['wifi_password'] = 'legacy-pass'
assert storage.serialize(card, SETTINGS_PATH)
assert Settings(storage).wifi_settings['password'] == 'legacy-pass'
assert 'wifi_password' not in storage.deserialize(SETTINGS_PATH), 'Plain-text copy must leave the SD'
assert secrets.get('wifi_password') == 'legacy-pass'

# If flash cannot be written the SD copy is kept, still usable, and nothing is lost.
card['wifi_password'] = 'kept-on-card'
assert storage.serialize(card, SETTINGS_PATH)
working_update = secrets.update
secrets.update = lambda values: False
try:
    stuck = Settings(storage)
    assert stuck.wifi_settings['password'] == 'kept-on-card'
    assert storage.deserialize(SETTINGS_PATH)['wifi_password'] == 'kept-on-card'
    assert not stuck.save_wifi_settings({'ssid': 'Lab', 'password': 'unsaved'})
    assert storage.deserialize(SETTINGS_PATH)['wifi_password'] == 'kept-on-card'
finally:
    secrets.update = working_update
assert Settings(storage).wifi_settings['password'] == 'kept-on-card'
assert 'wifi_password' not in storage.deserialize(SETTINGS_PATH)

# SSH: an old SD password file migrates; new passwords are written to flash only.
from picoware.applications.utilities import ssh
storage.mkdir('picoware/ssh')
for name, value in (('host.txt', 'example.local'), ('username.txt', 'pi'), ('password.txt', 'ssh-legacy')):
    assert storage.write('picoware/ssh/' + name, value)
assert getattr(ssh, '__load_ssh_credentials')(vm)
assert ssh.ssh_password == 'ssh-legacy' and secrets.get('ssh_password') == 'ssh-legacy'
assert not storage.exists('picoware/ssh/password.txt')
ssh.current_view = ssh.VIEW_KEYBOARD_PASSWORD
vm.keyboard.response = 'ssh-new'
assert ssh._keyboard_save(vm)
assert secrets.get('ssh_password') == 'ssh-new' and not storage.exists('picoware/ssh/password.txt')

# Web server access point: an SD password migrates; saving writes flash only.
from picoware.applications.wifi import server
get_setting = getattr(server, '__get_setting')
save_setting = getattr(server, '__save_setting')
storage.mkdir('picoware/wifi')
storage.mkdir('picoware/wifi/server')
assert storage.serialize({'settings': {'mode': 'AP', 'password': 'ap-legacy'}}, server.SERVER_INFO)
assert get_setting(vm, 'password') == 'ap-legacy'
assert 'password' not in storage.deserialize(server.SERVER_INFO)['settings']
assert secrets.get('ap_password') == 'ap-legacy'
assert save_setting(vm, 'password', 'ap-new') and get_setting(vm, 'password') == 'ap-new'
assert get_setting(vm, 'mode') == 'AP'
assert 'password' not in storage.deserialize(server.SERVER_INFO)['settings']
print('PASS: Wi-Fi, SSH and access point passwords live in flash; SD copies migrate safely')
