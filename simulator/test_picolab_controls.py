"""Keyboard regressions for focus isolation, modal drafts and calculation intent."""
import os, sys
from time import ticks_ms
root = os.getcwd()
for part in ('src/MicroPython', 'simulator/hardware', 'builds/MicroPython/apps_unfrozen'):
    sys.path.insert(0, root+'/'+part)
import sim_runtime
sim_runtime.configure(root, '/private/tmp/picolab-controls-'+str(ticks_ms()),
    root+'/builds/MicroPython/apps_unfrozen', 1, 'picocalc-pico2w', 0, True, False, False, False, '',
    _network_mode='offline', _audio_mode='silent', _sd_profile='clean')
from picoware.system.view_manager import ViewManager
from picoware.system.view import View
from picoware.system.input import Input
from picoware.system import buttons as k
Input.button = property(lambda self: self._last_button)
vm = ViewManager()
vm.add(View('parent', lambda vm: None, lambda vm: True, lambda vm: None));vm.switch_to('parent')
def key(button):
    vm.input_manager._last_button = button
    vm.run()
def text(value):
    for c in value:key(vm.input_manager._key_to_button(ord(c)))
def close():
    vm.back()
    assert vm.current_view.name == 'parent'

from engtools.beamlab import app as beam
beam.show(vm);a=beam._active
key(k.BUTTON_CENTER)
selection, tab, original = a.sel, a.model_tab, beam.items.copy(a.model)
zoom=a.zoom
key(k.BUTTON_PLUS);assert a.zoom == zoom
key(k.BUTTON_TAB);assert a.preview_focus
pan=list(a.pan)
key(k.BUTTON_RIGHT);assert a.pan[0] == pan[0]+8 and a.sel == selection and a.model == original
key(k.BUTTON_PLUS);assert a.zoom == min(zoom+1,len(beam.ZOOMS)-1)
key(k.BUTTON_SPACE);assert a.navigation == 'Probe' and a.model == original
key(k.BUTTON_RIGHT)
probe=(a.line,a.s,a.node_cursor)
a.draw();sim_runtime.lcd_screenshot('/private/tmp/picolab-controls-beam-focus.bmp')
key(k.BUTTON_TAB);assert not a.preview_focus and a.model_tab == tab and a.sel == selection
assert (a.line,a.s,a.node_cursor) == probe
key(k.BUTTON_TAB);key(k.BUTTON_ESCAPE);assert not a.preview_focus and vm.current_view.name == 'beam_lab'
a.draw();sim_runtime.lcd_screenshot('/private/tmp/picolab-controls-beam.bmp')
close()

from engtools.discs import app as discs
discs.show(vm);a=discs._active
selected, tab = a.selected(), a.tab
key(k.BUTTON_F6);assert a.focus == 'list'
key(k.BUTTON_TAB);key(k.BUTTON_CENTER)
assert a.view == '3d'
key(k.BUTTON_SPACE);assert a.navigation == 'Move'
yaw=a.yaw;pan=list(a.pan)
key(k.BUTTON_RIGHT);assert a.yaw == yaw and a.pan[0] == pan[0]+8 and a.selected() == selected
key(k.BUTTON_TAB);assert a.focus == 'list' and a.tab == tab
key(k.BUTTON_TAB);assert a.navigation == 'Move' and a.pan[0] == pan[0]+8
a.draw();sim_runtime.lcd_screenshot('/private/tmp/picolab-controls-discs.bmp')
close()

from engtools.mohr import app as mohr
mohr.show(vm);a=mohr._active
row,theta=a.row,a.state['theta']
key(k.BUTTON_RIGHT);assert a.row == row and a.state['theta'] == theta
key(k.BUTTON_TAB);key(k.BUTTON_RIGHT);assert a.row == row and a.state['theta'] == theta+1
key(k.BUTTON_ESCAPE);assert not a.preview_focus
key(k.BUTTON_CENTER);edit=a.edit;edit.text='-';cursor=edit.cursor
key(k.BUTTON_F9);key(k.BUTTON_ESCAPE)
assert a.edit is edit and edit.text == '-' and edit.cursor == cursor
key(k.BUTTON_TAB);assert a.edit is edit and a.error and not a.preview_focus
key(k.BUTTON_ESCAPE);close()

from engtools.thermal import app as heat
heat.show(vm);a=heat._active
key(k.BUTTON_F7);assert a.plate is None and not a.running
key(k.BUTTON_SPACE);assert a.plate is None and not a.running
key(k.BUTTON_F6)
for _ in range(4000):
    if not a.running:break
    key(k.BUTTON_NONE)
assert a.plate is not None and not a.running
plate=a.plate;tab,row=a.tab,a.row
key(k.BUTTON_TAB);assert a.preview_focus
key(k.BUTTON_SPACE);assert a.plate is plate and not a.running
key(k.BUTTON_LEFT);assert a.tab == tab and a.row == row
key(k.BUTTON_TAB);assert not a.preview_focus and a.tab == tab and a.row == row
key(k.BUTTON_TAB);a.draw();sim_runtime.lcd_screenshot('/private/tmp/picolab-controls-thermal.bmp')
key(k.BUTTON_ESCAPE);close()

from engtools.stressstrain import app as stress
stress.show(vm);a=stress._active
key(k.BUTTON_F4);assert a.solution is None and a.page == 'model' and a.error
key(k.BUTTON_F6);assert a.solution is not None
row,tab=a.row,a.tabs.index
key(k.BUTTON_TAB);assert a.preview_focus
a.draw();sim_runtime.lcd_screenshot('/private/tmp/picolab-controls-stress.bmp')
key(k.BUTTON_P);assert a.row == row and a.tabs.index == tab
key(k.BUTTON_SPACE);assert a.row == row and a.tabs.index == tab
key(k.BUTTON_TAB);assert not a.preview_focus
close()

from engtools.calculator import app as calcmod
from engtools.calculator.editor import source
calcmod.show(vm);calc=calcmod._active
text('2^ ');draft=source(calc.editor.root,False);parents=list(calc.editor.parents)
key(k.BUTTON_F9);key(k.BUTTON_DOWN);key(k.BUTTON_ESCAPE)
assert source(calc.editor.root,False) == draft and calc.editor.parents == parents
text('3');key(k.BUTTON_F6);assert calc.answer == 8 and not calc.editor.root
key(k.BUTTON_F5);assert calc.page == 'history'
key(k.BUTTON_ESCAPE);text('123');calc.editor.move(-1);key(k.BUTTON_DELETE)
assert source(calc.editor.root) == '13'
key(k.BUTTON_F10)
key(k.BUTTON_F3);calc.selected=2;key(k.BUTTON_CENTER)
selection=calc.selected
key(k.BUTTON_F9);key(k.BUTTON_RIGHT);key(k.BUTTON_ESCAPE)
assert calc.page == 'modes' and calc.selected == selection
calc.selected=1;key(k.BUTTON_CENTER);ws=calc.statistics_view()
key(k.BUTTON_CENTER);assert ws.dataset is not None
rows=ws.dataset.rows
key(k.BUTTON_F1);assert ws.dataset.rows == rows+1
key(k.BUTTON_F2);assert ws.dataset.rows == rows
text('12');edit=ws.editor;draft=source(edit.root)
key(k.BUTTON_F9);key(k.BUTTON_ESCAPE);assert ws.editing and source(edit.root) == draft
key(k.BUTTON_F6);assert not ws.editing
calc.draw();sim_runtime.lcd_screenshot('/private/tmp/picolab-controls-calculator.bmp')
close()

from engtools.plots import plot2d
from engtools.plots.view import open_view
controller=plot2d._PlotView({'title':'Help test', 'series':[{'expression':'x'}], 'bounds':[-2,2,-2,2]})
open_view(vm,'focus_plot2d',controller)
a=controller.app
key(k.BUTTON_CENTER);key(k.BUTTON_CENTER)
assert a.state == 'input'
a.edit.text='sin(';edit=a.edit;edit.cursor=2
key(k.BUTTON_F9);assert a.state == 'help'
sim_runtime.lcd_screenshot('/private/tmp/picolab-controls-graph-help.bmp')
key(k.BUTTON_ESCAPE);assert a.state == 'input' and a.edit is edit and edit.text == 'sin(' and edit.cursor == 2
key(k.BUTTON_ESCAPE);close()

from engtools.plots import plot3d
plot3d.show(vm, {'title':'3D help test', 'surfaces':[{'expression':'x+y'}], 'bounds':[-2,2,-2,2], 'resolution':8})
for _ in range(400):
    key(k.BUTTON_NONE)
    if plot3d._state == plot3d.ST_PLOT:break
key(k.BUTTON_CENTER);assert plot3d._edit is not None
edit=plot3d._edit;edit.text='sin(';edit.cursor=2
key(k.BUTTON_F9);assert plot3d._state == plot3d.ST_HELP
sim_runtime.lcd_screenshot('/private/tmp/picolab-controls-graph3d-help.bmp')
key(k.BUTTON_ESCAPE);assert plot3d._edit is edit and edit.text == 'sin(' and edit.cursor == 2
close()
print('PASS: preview focus/camera isolation, modal drafts, explicit calculation, statistics collections and plot editor help')
