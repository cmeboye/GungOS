"""Regression checks for the selected firmware and its existing SD settings."""

import os
import sys
from time import ticks_ms

root = os.getcwd()
sys.path.insert(0, root + "/src/MicroPython")
sys.path.insert(0, root + "/simulator/hardware")
import sim_runtime

sim_runtime.configure(root, "/private/tmp/picoware-trim-regression-" + str(ticks_ms()),
                      root + "/builds/MicroPython/apps_unfrozen", 1,
                      "picocalc-pico2w", 0, True, False, False, False, "",
                      _network_mode="offline", _audio_mode="silent", _sd_profile="clean")

from picoware.system.view_manager import ViewManager
from picoware.system.settings import Settings
from picoware.system.time import Time
from picoware.system.http import HTTP
from picoware.system.buttons import BUTTON_CENTER, BUTTON_NONE
from picoware.applications import desktop, settings, library
from picoware.gui.file_browser import FileBrowser, FILE_BROWSER_MANAGER
from picoware.system.usb import USBKeyboard, USBMedia
import picoware_desktop

assert picoware_desktop.native_modules() == (
    "auto_complete", "font", "picoware_pcm", "response", "sim_raster", "ulab", "vector", "vt")

for name in ("c", "mjs", "mmbasic", "engine", "gameboy", "ghouls",
             "audio", "video", "usb_video_mp", "picoware_lvgl",
             "picoware.applications.system.update", "picoware.applications.applications.app_store",
             "picoware.system.agent", "picoware.applications.ai_setup",
             "picoware.applications.applications.agent"):
    try:
        __import__(name)
        raise AssertionError("Excluded backend was importable: " + name)
    except ImportError:
        pass
for route in ("App Store", "Update", "Apps/Scripts/C", "JavaScript", "MMBasic", "Agent", "Email", "ESP Flasher"):
    try:
        sim_runtime.request_open(route)
        raise AssertionError("Excluded route was launchable: " + route)
    except sim_runtime.LaunchTargetError:
        pass
sim_runtime._keys = []

vm = ViewManager()
assert Settings(vm.storage).update({"lvgl_mode": True, "usb_stream": True,
    "theme_color": 0xF800, "screen_brightness": 40, "dark_mode": False,
    "wifi_ssid": "Saved", "wifi_password": "test-only", "openai_api_key": "test-only",
    "custom_field": "preserve"})
del vm
vm = ViewManager()
assert not vm.draw.use_lvgl and vm.usb_video_stream is None
assert not vm.start_usb_video_stream() and not vm.has_audio
assert vm.selected_color == 0xF800 and vm.draw._brightness == 40
assert vm.background_color == 0 and vm.has_wifi and vm.has_bluetooth
assert Settings(vm.storage).settings["custom_field"] == "preserve"
assert Settings(vm.storage).openai_api_key == "test-only"
assert Settings(vm.storage).wifi_settings["ssid"] == "Saved"
assert settings.start(vm)
assert not settings._menu.item_exists("AI Setup")
assert not settings._menu.item_exists("Server Settings")
assert not settings._menu.item_exists("Use LVGL")
assert not settings._menu.item_exists("USB Stream")
settings.stop(vm)

class ConnectedWifi:
    state = 2
    def is_connected(self):
        return True

class Clock:
    def datetime(self):
        return (2026, 10, 14, 2, 10, 30, 0, 0)
    def deinit(self):
        pass

requests = []
old_http_init = HTTP.__init__
old_fetch = Time.fetch
def forbidden_request(self, *args, **kwargs):
    raise AssertionError("Home created an HTTP client")
def fetch_time(self, offset=0):
    requests.append(offset)
    self._requested = True
HTTP.__init__ = forbidden_request
Time.fetch = fetch_time
vm._wifi = ConnectedWifi()
vm.time._rtc = Clock()
vm.time._is_set = True
vm._button = BUTTON_NONE
try:
    for _ in range(2):
        assert desktop.start(vm)
        for _ in range(3):
            desktop.run(vm)
        desktop.stop(vm)
    assert not requests, "Home refetched an already set clock"
    vm.time._is_set = False
    vm.gmt_offset = 3
    desktop.start(vm)
    desktop.run(vm)
    desktop.run(vm)
    assert requests == [3], "Home must retain NTP without firmware requests"
    desktop.stop(vm)
finally:
    HTTP.__init__ = old_http_init
    Time.fetch = old_fetch

vm.storage.mkdir("lean_checks")
for filename in ("sample.c", "sample.js", "sample.bas", "sound.mp3", "movie.mp4", "notes.txt"):
    assert vm.storage.write("lean_checks/" + filename, "test")
browser = FileBrowser(vm, FILE_BROWSER_MANAGER, "/lean_checks")
for filename in ("sample.c", "sample.js", "sample.bas", "sound.mp3", "movie.mp4", "notes.txt"):
    browser._app_state["left_index"] = browser._app_state["left_files"].index(filename)
    vm._button = BUTTON_CENTER
    browser.run()
    menu = browser._context_menu
    assert menu is not None
    for action in ("Run", "Play Audio", "Watch Video"):
        assert not menu.item_exists(action), (filename, action)
    if filename.endswith((".c", ".js", ".bas", ".txt")):
        assert menu.item_exists("View") and menu.item_exists("Edit")
    assert menu.item_exists("Copy") and menu.item_exists("Delete")
    browser._context_menu = None
del browser
from picoware.applications.applications.games import games
vm.storage.mkdir("picoware/apps/games")
assert vm.storage.write("picoware/apps/games/lean_check.py", "# Python game fixture\n")
assert games.start(vm)
assert not games._games.item_exists("lean_check")
assert games._games.item_exists("Tetris")
assert not games._games.item_exists("GameBoy Emulator")
assert not games._games.item_exists("Ghouls")
games.stop(vm)
sim_runtime.request_game("Tetris")
assert games._games_index == 0
sim_runtime._keys = []
sim_runtime._delayed_keys = []
print("PASS: lean native inventory and excluded import/menu routes")
print("PASS: old LVGL/video settings boot safely; preferences, AI keys, Wi-Fi and Bluetooth retained")
print("PASS: connected home has no HTTP/update requests and retains NTP")
print("PASS: File Manager omits unsupported actions; Agent/AI excluded")
print("PASS: release game allowlist and simulator launch indices")
