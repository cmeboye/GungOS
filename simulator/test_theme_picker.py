"""Exercise theme editing, cancellation, failed saves and restoration on restart."""
import os, sys
from time import ticks_ms
root = os.getcwd()
for path in ('src/MicroPython', 'simulator/hardware', 'builds/MicroPython/apps_unfrozen'):
    sys.path.insert(0, root + '/' + path)
import sim_runtime
output = '/private/tmp/gungos-theme-picker-previews'
sim_runtime.mkdir_p(output)
sim_runtime.configure(root, '/private/tmp/gungos-theme-test-' + str(ticks_ms()),
                      root + '/builds/MicroPython/apps_unfrozen', 1,
                      'picocalc-pico2w', 0, True, False, False, False, '',
                      _network_mode='offline', _audio_mode='silent', _sd_profile='clean')
from picoware.system.view_manager import ViewManager
from picoware.system.settings import Settings
from picoware.system import buttons as k
from picoware.applications import settings as app
from picoware.gui.theme_picker import PRESETS, from_hex, to_hex
from picoware.gui.status_bar import foreground
assert len(PRESETS) == 32 and len(set(colour for _, colour in PRESETS)) == 32
for colour in (0, 0xFFFF, 0x001F, 0x07E0, 0xF800, 0xD69A, 0x03EF, 0x9A60, from_hex('D48844')):
    assert from_hex(to_hex(colour)) == colour
assert from_hex('#ffffff') == 0xFFFF and from_hex('000000') == 0
for invalid in ('', '12345', '1234567', 'GG0000', '-12345', '0x1234'):
    try:
        from_hex(invalid)
        raise AssertionError('Invalid hex accepted')
    except ValueError:
        pass
vm = ViewManager(); vm._wifi = None
assert app.start(vm)
original = vm.selected_color
labels = [app._menu.get_item(i) for i in range(app._menu.item_count)]
app._menu.set_selected(labels.index('Appearance'))
def key(button):
    vm._button = button
    app.run(vm)
def text(value):
    for char in value.upper():
        key(getattr(k, 'BUTTON_' + char))
def snap(name):
    sim_runtime.lcd_screenshot(output + '/' + name + '.bmp')
key(k.BUTTON_CENTER)
editor = app._appearance
key(k.BUTTON_CENTER)
picker = editor.picker
assert picker and picker.colour == original
snap('swatches')
key(k.BUTTON_DOWN); key(k.BUTTON_RIGHT)
assert picker.index == 8 and vm.selected_color == original
assert Settings(vm.storage).theme_color == original
key(k.BUTTON_ESCAPE)
assert editor.picker is None and vm.selected_color == original
key(k.BUTTON_CENTER); picker = editor.picker
picker._select(0); picker.draw()
key(k.BUTTON_LEFT); assert picker.index == 31
key(k.BUTTON_RIGHT); assert picker.index == 0
key(k.BUTTON_UP); assert picker.index == 27
key(k.BUTTON_DOWN); assert picker.index == 0
picker._select(14); picker.draw(); snap('amber-preview')
from sim_pixels import Pixels, colour
fb = Pixels(vm.draw)
assert fb.pixel(0, 0) == colour(PRESETS[14][1]) and foreground(picker.colour) == 0
assert any(fb.pixel(x,y)==0 for y in range(245,265) for x in range(194,280))
key(k.BUTTON_F2); assert picker.editing
text('D48'); key(k.BUTTON_CENTER)
assert picker.editing and picker.error and len(picker.draft) == 3
snap('incomplete-hex')
text('844'); assert picker.colour == from_hex('D48844')
snap('custom-entry')
key(k.BUTTON_CENTER); assert not picker.editing
assert vm.selected_color == original
snap('custom-preview')
custom = picker.colour
# Back and Delete always erase BEFORE the cursor; Esc restores the draft colour.
key(k.BUTTON_F2); key(k.BUTTON_LEFT); key(k.BUTTON_DELETE)
assert len(picker.draft)==5 and picker.cursor==4
key(k.BUTTON_BACK); assert len(picker.draft)==4 and picker.cursor==3
key(k.BUTTON_ESCAPE); assert not picker.editing and picker.colour == custom
key(k.BUTTON_F2); text('FFFFFF'); key(k.BUTTON_ESCAPE)
assert picker.colour == custom
# Entering an optional # works, and typing is bounded to six hex digits.
key(k.BUTTON_F2); key(k.BUTTON_HASH); text('000000'); text('FF')
assert picker.draft == '000000' and picker.colour == 0
key(k.BUTTON_ESCAPE); assert picker.colour == custom
# Accept the selected colour into the draft, then commit with F1.
key(k.BUTTON_CENTER)
assert editor.picker is None and vm.selected_color == original
class FailedWrites:
    def __init__(self, storage, claim_success): self.storage, self.claim_success = storage, claim_success
    def exists(self, path): return self.storage.exists(path)
    def read(self, path): return self.storage.read(path)
    def serialize(self, value, path): return self.claim_success
storage = vm.storage
for claim_success in (False, True):
    app._settings._storage = FailedWrites(storage, claim_success)
    key(k.BUTTON_F1)
    assert app._appearance is editor and editor.error
    assert vm.selected_color == original and Settings(storage).theme_color == original
snap('save-error')
app._settings._storage = storage
assert Settings(storage).update({'wifi_ssid': 'Theme regression', 'custom_field': 'keep'})
key(k.BUTTON_F1)
assert app._appearance is None and vm.selected_color == custom
assert app._menu.selected_color == custom
saved = Settings(storage)
assert saved.theme_color == custom and saved.settings['custom_field'] == 'keep'
assert saved.wifi_settings['ssid'] == 'Theme regression'
app.stop(vm)
vm = ViewManager(); vm._wifi = None
assert vm.selected_color == custom and vm.background_color == 0
assert app.start(vm)
app.__open_appearance()
key(k.BUTTON_CENTER)
assert app._appearance.picker.index == -1 and app._appearance.picker.colour == custom
key(k.BUTTON_ESCAPE); key(k.BUTTON_ESCAPE)
# Unrelated brightness choice remains usable after the new picker.
app.__open_choice_brightness(); app._choice.state = 3
key(k.BUTTON_CENTER)
assert Settings(vm.storage).screen_brightness == 40
app.stop(vm)
print('PASS: 32 swatches, RGB565 matching, live contrast, hex editing and cancellation')
print('PASS: failed-save recovery, credential preservation, immediate menu colour and fresh-boot restoration')
print('Theme preview screenshots: ' + output)
