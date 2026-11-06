"""Beam-style navigation and calculator-rendered help across the three tools."""
import os, sys
from time import ticks_ms
root = os.getcwd()
for part in ('src/MicroPython', 'simulator/hardware', 'builds/MicroPython/apps_unfrozen'):
    sys.path.insert(0, root+'/'+part)
import sim_runtime
sim_runtime.configure(root, '/private/tmp/gungos-tool-tabs-'+str(ticks_ms()),
                      root+'/builds/MicroPython/apps_unfrozen', 1, 'picocalc-pico2w', 0,
                      True, False, False, False, '', _network_mode='offline', _audio_mode='silent', _sd_profile='clean')
from picoware.system.view_manager import ViewManager
from picoware.system.view import View
from picoware.system.input import Input
from picoware.system import buttons as k
from engtools import session
Input.button = property(lambda self: self._last_button)
vm = ViewManager(); vm._wifi = None
vm.add(View('parent', lambda vm: None, lambda vm: True, lambda vm: None)); vm.switch_to('parent')


def key(button):
    vm.input_manager._last_button = button
    vm.run()


def shot(name):
    sim_runtime.lcd_screenshot('/private/tmp/gungos-tabs-'+name+'.bmp')


def rich_help(a, name):
    old_page = a.page
    old_row, old_tab = a.row, a.tabs.index
    key(k.BUTTON_F9)
    assert a.help_view.opened and a.help_view.blocks[0][0] == 'formula'
    # A real calculator fraction tree, rather than flattened slash text.
    assert any(not isinstance(part, str) and part.kind == 'frac'
               for kind, _, expression in a.help_view.blocks if kind == 'formula' for part in expression)
    shot(name+'-equations')
    for _ in range(len(a.help_view.blocks)+5):
        key(k.BUTTON_DOWN)
    assert a.help_view.first == len(a.help_view.blocks)-1
    key(k.BUTTON_F9)
    assert not a.help_view.opened and (a.page, a.row, a.tabs.index) == (old_page, old_row, old_tab)


from engtools.buckling import app as buckling
session.kept.pop('buckling', None)
buckling.show(vm); a = buckling._active
assert a.tabs.labels == ('Section', 'Member', 'Ends')
assert a.tabs.label == 'Section'
key(k.BUTTON_CENTER); assert a.page == 'section'
key(k.BUTTON_DOWN); key(k.BUTTON_DOWN)
assert a.rows()[a.row][4] == ('section', 'h')
key(k.BUTTON_CENTER); cursor = a.edit.cursor
key(k.BUTTON_LEFT); assert a.edit.cursor == cursor-1
key(k.BUTTON_ESCAPE); assert a.edit is None
key(k.BUTTON_ESCAPE); assert a.page == 'model'
key(k.BUTTON_RIGHT); assert a.tabs.label == 'Member' and a.row == 0
key(k.BUTTON_DOWN); assert a.rows()[a.row][4] == ('compression',)
key(k.BUTTON_RIGHT); assert a.tabs.label == 'Ends'
key(k.BUTTON_DOWN); assert a.rows()[a.row][4] == ('ends_z',)
key(k.BUTTON_LEFT); assert a.rows()[a.row][4] == ('compression',)
key(k.BUTTON_LEFT); assert a.tabs.label == 'Section'
key(k.BUTTON_CENTER); assert a.page == 'section' and a.rows()[a.row][4] == ('section', 'h')
key(k.BUTTON_ESCAPE)
key(k.BUTTON_F6); solution = a.solution
rich_help(a, 'buckling')
assert a.solution is solution
shot('buckling-section')
key(k.BUTTON_RIGHT); shot('buckling-member')
key(k.BUTTON_ESCAPE); assert vm.current_view.name == 'parent'

from engtools.stressstrain import app as stress
session.kept.pop('stressstrain', None)
stress.show(vm); a = stress._active
assert a.tabs.label == 'Section'
for _ in range(2):
    key(k.BUTTON_DOWN)
assert a.rows()[a.row][4] == ('point', 'z')
key(k.BUTTON_RIGHT); assert a.tabs.label == 'Loads'
for _ in range(3):
    key(k.BUTTON_DOWN)
assert a.rows()[a.row][4] == ('loads', 'T')
key(k.BUTTON_LEFT); assert a.rows()[a.row][4] == ('point', 'z')
key(k.BUTTON_UP); key(k.BUTTON_UP); key(k.BUTTON_CENTER)
assert a.page == 'section' and a.section_tabs.label == 'Geometry'
key(k.BUTTON_DOWN); assert a.rows()[a.row][4] == ('section', 'd')
key(k.BUTTON_RIGHT); assert a.section_tabs.label == 'Material'
key(k.BUTTON_DOWN); assert a.rows()[a.row][4] == ('material', 'E')
key(k.BUTTON_LEFT); assert a.rows()[a.row][4] == ('section', 'd')
key(k.BUTTON_RIGHT); assert a.rows()[a.row][4] == ('material', 'E')
key(k.BUTTON_ESCAPE); assert a.page == 'model' and a.tabs.label == 'Section'
rich_help(a, 'stress-section')
# Analysis is a field on the Analysis tab, not the retired F1 shortcut.
key(k.BUTTON_LEFT); key(k.BUTTON_CENTER); key(k.BUTTON_DOWN); key(k.BUTTON_CENTER)
assert a.state['mode'] == 'constitutive' and a.tabs.label == 'Analysis'
key(k.BUTTON_RIGHT); assert a.tabs.label == 'Inputs'
key(k.BUTTON_DOWN); assert a.rows()[a.row][4] == ('stress', 1)
key(k.BUTTON_RIGHT); key(k.BUTTON_LEFT)
assert a.rows()[a.row][4] == ('stress', 1)
rich_help(a, 'stress-constitutive')
shot('stress-inputs')
key(k.BUTTON_ESCAPE); assert vm.current_view.name == 'parent'

from engtools.unitconvert import app as units
session.kept.pop('unitconvert', None)
units.show(vm); a = units._active
assert a.page == 'convert' and a.row == 1
key(k.BUTTON_DOWN); assert a.row == 2
before = dict(a.state)
key(k.BUTTON_RIGHT); assert a.page == 'results'
for _ in range(3):
    key(k.BUTTON_DOWN)
assert a.index == 3
key(k.BUTTON_RIGHT); assert a.page == 'favorites'
key(k.BUTTON_RIGHT); assert a.page == 'recent'
key(k.BUTTON_LEFT); key(k.BUTTON_LEFT)
assert a.page == 'results' and a.index == 3
key(k.BUTTON_LEFT); assert a.page == 'convert' and a.row == 2 and a.state == before
rich_help(a, 'units')
shot('unitconvert')
# Modal search retains arrow navigation; it cannot switch the tool tab.
key(k.BUTTON_CENTER); assert a.page == 'units'
key(k.BUTTON_RIGHT); assert a.page == 'units'
key(k.BUTTON_ESCAPE); assert a.page == 'convert'
# Read-only equations also render under the light palette.
vm.background_color = 0xffff; vm.foreground_color = 0
key(k.BUTTON_F9); a.draw(); shot('units-equations-light')
key(k.BUTTON_ESCAPE)
key(k.BUTTON_ESCAPE); key(k.BUTTON_ESCAPE)
assert vm.current_view.name == 'parent'
print('PASS: all three tools share Beam-style tabs; per-tab focus, editor/search arrows, rich equation help, scrolling, light theme and state preservation')
