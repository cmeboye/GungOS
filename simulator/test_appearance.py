"""Appearance persistence, safe preview, per-surface ink and shipped apps."""
import os, sys
from time import ticks_ms
root = os.getcwd()
for part in ('src/MicroPython', 'simulator/hardware', 'builds/MicroPython/apps_unfrozen'):
    sys.path.insert(0, root + '/' + part)
import sim_runtime
sd = '/private/tmp/gungos-appearance-check-' + str(ticks_ms())
output = '/private/tmp/gungos-appearance-previews'
sim_runtime.mkdir_p(output)
sim_runtime.configure(root, sd, root + '/builds/MicroPython/apps_unfrozen', 1,
                      'picocalc-pico2w', 0, True, False, False, False, '',
                      _network_mode='offline', _audio_mode='silent', _sd_profile='clean')
from picoware.system.view_manager import ViewManager
from picoware.system.settings import Settings
from picoware.system import buttons as k
from picoware.gui import appearance, style
from picoware.gui.status_bar import foreground
from picoware.gui.theme_picker import from_hex
from picoware.applications import settings as app
from sim_pixels import Pixels, colour
vm = ViewManager(); vm._wifi = None
assert vm.background_color == 0 and vm.foreground_color == 0xFFFF
assert appearance.contrast(0, 0xFFFF) > 20.9
assert appearance.contrast(0, 0) == 1
assert app.start(vm)
def key(button):
    vm._button = button
    app.run(vm)
def snapshot(name):
    sim_runtime.lcd_screenshot(output + '/' + name + '.bmp')
def open_editor():
    app._menu.set_selected(app._menu.items.index('Appearance'))
    key(k.BUTTON_CENTER)
    return app._appearance

original = appearance.values(Settings(vm.storage).settings)
editor = open_editor()
snapshot('settings-default')
key(k.BUTTON_DOWN); key(k.BUTTON_CENTER)
assert editor.picker.field == 'background_color'
editor.picker._select(1); editor.picker.draw()
key(k.BUTTON_CENTER)
assert editor.values['background_color'] == 0x07E0
assert vm.background_color == 0 and Settings(vm.storage).settings['background_color'] == 0
key(k.BUTTON_ESCAPE)
assert appearance.values(Settings(vm.storage).settings) == original

editor = open_editor()
custom = {'theme_color': from_hex('F5BE48'), 'background_color': from_hex('142838'),
          'text_on_dark': from_hex('C9E8DA'), 'text_on_light': from_hex('182030')}
editor.values.update(custom); editor.draw(); snapshot('settings-custom-dark')
# Low contrast must be visible without altering any active roles.
editor.values['text_on_dark'] = custom['background_color']
editor.draw(); snapshot('settings-low-contrast')
assert vm.foreground_color == 0xFFFF
key(k.BUTTON_F2)
assert editor.values == appearance.DEFAULTS
assert Settings(vm.storage).theme_color == original['theme_color']
editor.values.update(custom)
key(k.BUTTON_F1)
assert app._appearance is None
assert vm.background_color == custom['background_color']
assert vm.foreground_color == custom['text_on_dark']
assert vm.draw.background == vm.background_color and vm.draw.foreground == vm.foreground_color
assert app._menu.background_color == vm.background_color and app._menu.text_color == vm.foreground_color
assert foreground(custom['theme_color']) == custom['text_on_light']
assert foreground(0) == custom['text_on_dark']
assert foreground(0xFFFF) == custom['text_on_light']
assert vm.keyboard.text_color == vm.foreground_color and vm.keyboard.background_color == vm.background_color
app.stop(vm)
vm = ViewManager(); vm._wifi = None
assert vm.background_color == custom['background_color'] and vm.foreground_color == custom['text_on_dark']
assert vm.text_on_light == custom['text_on_light']
print('PASS: per-surface text roles, draft/cancel/reset/save, keyboard sync and fresh startup')

from picoware.gui.dashboard import Dashboard
from picoware.gui.file_browser import FileBrowser, FILE_BROWSER_SELECTOR
from picoware.gui.menu import Menu
from desktopapps.launcher import Launcher
from desktopapps.eggcel.app import Spreadsheet
from desktopapps.word import Word
from desktopapps.paint import Paint
from engtools.calculator.app import Calculator
from engtools.beamlab.app import BeamLab
from engtools.discs.app import Discs
from engtools.picocad.app import CAD

for name, background in (('dark', custom['background_color']), ('light', from_hex('E2E8D8'))):
    colors = dict(custom); colors['background_color'] = background
    assert Settings(vm.storage).update(colors)
    vm.apply_appearance(colors)
    fg = custom['text_on_light'] if name == 'light' else custom['text_on_dark']
    assert vm.foreground_color == fg
    # Home, native menu, browser, PicoDESK and every calculator mode.
    home = Dashboard(vm); vm._button = k.BUTTON_NONE; home.update(); snapshot(name + '-home')
    fb = Pixels(vm.draw)
    assert fb.pixel(319, 18) == colour(background)
    menu = Menu(vm.draw, 'Appearance review', 0, 320, fg, background, vm.selected_color)
    menu.add_item('Selected'); menu.add_item('Another item'); menu.draw()
    snapshot(name + '-menu')
    browser = FileBrowser(vm, FILE_BROWSER_SELECTOR); browser.run(); snapshot(name + '-files')
    desk = Launcher(); desk.start(vm); snapshot(name + '-desk')
    for title, cls in (('eggcel', Spreadsheet), ('word', Word), ('paint', Paint)):
        tool = cls(); tool.start(vm); tool.draw(); snapshot(name + '-' + title)
        assert Pixels(vm.draw).pixel(0, 45) == colour(background)
        tool.stop(vm)
    calc = Calculator(); calc.start(vm)
    assert calc.palette.BG == background and calc.palette.TEXT == fg
    for mode in range(6):
        calc.choose_mode(mode); calc.draw(); snapshot(name + '-calc-' + str(mode))
    calc.stop(vm)
    # Offscreen calculator receives the same surface and text roles.
    from picoware.gui.widget import WidgetHost
    host = WidgetHost(vm, (99, 70, 220, 220)); host.load('Calculator Widget')
    assert host.module is not None, host.error
    host.focused = True; host.step(k.BUTTON_2); host.step(k.BUTTON_PLUS); host.step(k.BUTTON_3); host.step(k.BUTTON_CENTER)
    from engtools.calculator import app as calculator
    assert calculator._active.answer == 5
    assert calculator._active.palette.TEXT == fg and calculator._active.palette.BG == background
    host.paint(); snapshot(name + '-calculator-widget'); host.stop()
    for title, cls in (('beam', BeamLab), ('shrink-fit', Discs), ('cad', CAD)):
        tool = cls(vm); tool.draw(); snapshot(name + '-' + title)
    # Shipped plotting engines, games and screensavers use the same roles.
    from engtools.plots import plot2d, plot3d
    vm._button = k.BUTTON_NONE
    assert plot2d.start(vm)
    plot2d.run(vm); snapshot(name + '-graph')
    assert plot2d._app.palette.BG == background
    plot2d.stop(vm)
    assert plot3d.start(vm)
    for _ in range(2000):
        plot3d.run(vm)
        if plot3d._state != plot3d.ST_SAMPLING: break
    assert plot3d.C_BG == background and plot3d.C_TITLE == fg
    snapshot(name + '-graph3d'); plot3d.stop(vm)
    for directory in ('misc/screensavers', 'games'):
        sys.path.insert(0, root + '/builds/MicroPython/apps_unfrozen/' + directory)
    for module in ('Lorenz', 'Lenia', 'Tetris'):
        tool = __import__(module)
        assert tool.start(vm)
        tool.run(vm); snapshot(name + '-' + module.lower()); tool.stop(vm)
    home.stop()
    # The menu logos expose their canvas and use per-surface white lettering.
    from picoware.assets.logos import decode, LOGOS
    raw = decode('picolab', background, vm.selected_color)
    palette = {raw[i] | raw[i + 1] << 8 for i in range(0, len(raw), 2)}
    assert background in palette and fg in palette and vm.selected_color in palette
print('PASS: dark/light canvases across dashboard, menus, files, PicoDESK, six calculator modes, widget and structural/CAD tools')

# A reset is transactional too; it restores all four fields on disk and at boot.
assert app.start(vm)
editor = open_editor(); key(k.BUTTON_F2); key(k.BUTTON_F1)
assert appearance.values(Settings(vm.storage).settings) == appearance.DEFAULTS
app.stop(vm)
vm = ViewManager(); vm._wifi = None
assert vm.background_color == 0 and vm.foreground_color == 0xFFFF and vm.selected_color == 0x001F
# Malformed colours in a manually edited file fall back safely without rewriting it.
assert Settings(vm.storage).update({'background_color': -1, 'text_on_dark': 'bad', 'text_on_light': None, 'theme_color': 999999})
vm = ViewManager(); vm._wifi = None
assert vm.background_color == 0 and vm.foreground_color == 0xFFFF and vm.selected_color == 0x001F
print('PASS: persisted reset and invalid-colour fallback; screenshots: ' + output)
