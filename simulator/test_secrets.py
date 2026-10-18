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

# SSH: migrate all fields in one verified flash update, then remove SD copies.
from picoware.applications.utilities import ssh
storage.mkdir('picoware/ssh')
fields = (
    ('ssh_host', 'host.txt', ssh.VIEW_KEYBOARD_HOST, 'example.local'),
    ('ssh_port', 'port.txt', ssh.VIEW_KEYBOARD_PORT, '2222'),
    ('ssh_username', 'username.txt', ssh.VIEW_KEYBOARD_USERNAME, 'pi'),
    ('ssh_password', 'password.txt', ssh.VIEW_KEYBOARD_PASSWORD, 'ssh-legacy'),
)
load_ssh = getattr(ssh, '__load_ssh_credentials')
for key, filename, mode, value in fields:
    assert storage.write('picoware/ssh/' + filename, value)
assert load_ssh(vm)
for key, filename, mode, value in fields:
    assert secrets.get(key) == value
    assert not storage.exists('picoware/ssh/' + filename)
assert ssh.ssh_host == 'example.local' and ssh.ssh_port == '2222'
assert ssh.ssh_username == 'pi' and ssh.ssh_password == 'ssh-legacy'
assert secrets.get('wifi_password') == 'kept-on-card'

# Each editor writes flash only, and a fresh load restores the entire profile.
new_values = ('new.example.local', '2200', 'engineer', 'ssh-new')
for (key, filename, mode, _), value in zip(fields, new_values):
    ssh.current_view = mode
    vm.keyboard.response = value
    assert ssh._keyboard_save(vm)
    assert secrets.get(key) == value
    assert not storage.exists('picoware/ssh/' + filename)
ssh.ssh_host = ssh.ssh_port = ssh.ssh_username = ssh.ssh_password = ''
assert load_ssh(vm)
assert (ssh.ssh_host, ssh.ssh_port, ssh.ssh_username, ssh.ssh_password) == new_values

# A failed edit must not change the active or saved connection profile.
ssh.current_view = ssh.VIEW_KEYBOARD_USERNAME
vm.keyboard.response = 'unsaved-user'
secrets.update = lambda values: False
try:
    assert not ssh._keyboard_save(vm)
    assert ssh.ssh_username == 'engineer' and secrets.get('ssh_username') == 'engineer'
finally:
    secrets.update = working_update

# Device credentials win over stale cards, even an intentionally empty field.
assert secrets.update({'ssh_username': ''})
assert storage.write('picoware/ssh/username.txt', 'stale-user')
assert not load_ssh(vm)
assert ssh.ssh_username == '' and not storage.exists('picoware/ssh/username.txt')

# If migration fails, retain every SD original for recovery and a later retry.
assert secrets.update({key: None for key, _, _, _ in fields})
for key, filename, mode, value in fields:
    assert storage.write('picoware/ssh/' + filename, value)
secrets.update = lambda values: False
try:
    assert load_ssh(vm)  # old values remain usable in RAM for this visit
    for key, filename, mode, value in fields:
        assert storage.read('picoware/ssh/' + filename) == value
        assert key not in secrets.load()
finally:
    secrets.update = working_update
assert load_ssh(vm)
for key, filename, mode, value in fields:
    assert secrets.get(key) == value and not storage.exists('picoware/ssh/' + filename)

# Cleanup failure must not replace the verified on-chip value with a stale SD one.
class ReadOnlyCleanup:
    def exists(self, path): return storage.exists(path)
    def read(self, path): return storage.read(path)
    def remove(self, path): return False
class SSHView:
    storage = ReadOnlyCleanup()
    def log(self, *args): pass
assert storage.write('picoware/ssh/password.txt', 'stale-password')
assert load_ssh(SSHView())
assert ssh.ssh_password == 'ssh-legacy'
assert storage.exists('picoware/ssh/password.txt')
assert load_ssh(vm) and not storage.exists('picoware/ssh/password.txt')
print('PASS: full SSH profile stays on-chip; verified migration, failed edits and stale/read-only SD recovery')

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
