"""PicoLAB hierarchy, breadcrumbs, child-view cleanup and graph keyboard bounds."""
import os,sys
from time import ticks_ms
root=os.getcwd()
for part in ('src/MicroPython','simulator/hardware','builds/MicroPython/apps_unfrozen'):
    sys.path.insert(0,root+'/'+part)
import sim_runtime
sim_runtime.configure(root,'/private/tmp/gungos-picolab-hierarchy-'+str(ticks_ms()),root+'/builds/MicroPython/apps_unfrozen',
                      1,'picocalc-pico2w',0,True,False,False,False,'',_network_mode='offline',_audio_mode='silent',_sd_profile='clean')
from picoware.system.view_manager import ViewManager
from picoware.system.view import View
from picoware.system.input import Input
from picoware.system import buttons as k
from engtools.ui import breadcrumbs,theme
import PicoLAB as lab
Input.button=property(lambda self:self._last_button)
vm=ViewManager();vm._wifi=None
vm.add(View('parent',lambda vm:None,lambda vm:True,lambda vm:None));vm.switch_to('parent')
vm.add(View('lab',lab.run,lab.start,lab.stop));vm.switch_to('lab')
def key(button):
    vm.input_manager._last_button=button;vm.run()
    vm.input_manager._last_button=k.BUTTON_NONE;vm.run()
def shot(name):sim_runtime.lcd_screenshot('/private/tmp/gungos-picolab-'+name+'.bmp')
def path(*parts):assert breadcrumbs.current(vm)==parts,(breadcrumbs.current(vm),parts)
def pick(label):
    entries=lab.MENUS[lab._page]
    index=next(i for i,row in enumerate(entries) if row[1]==label)
    for _ in range((index-lab._selected)%len(entries)):key(k.BUTTON_DOWN)
    key(k.BUTTON_CENTER)
def exit_child():
    for _ in range(8):
        if vm.current_view.name=='lab':return
        key(k.BUTTON_ESCAPE)
    raise AssertionError('Did not return to PicoLAB')
assert lab._page=='root' and [r[1] for r in lab.MENUS['root']]==['Checks','Tools','Modules']
path();shot('root')
pick('Checks');path('checks')
assert [r[1] for r in lab.MENUS['checks']]==['Numerics check','Plot previews']
pick('Numerics check');path('checks','Numerics check')
for _ in range(200):
    key(k.BUTTON_NONE)
    if lab._bench is None:break
assert lab._bench_rows and all(row['passed'] for row in lab._bench_rows)
shot('checks')
key(k.BUTTON_ESCAPE);assert lab._page=='checks' and lab._selected==0
pick('Plot previews');path('checks','Plot previews');shot('previews')
key(k.BUTTON_CENTER);assert vm.current_view.name=='eng_plot2d'
path('checks','Plot previews')
key(k.BUTTON_ESCAPE);assert lab._page=='gallery'
key(k.BUTTON_ESCAPE);assert lab._page=='checks' and lab._selected==1
key(k.BUTTON_ESCAPE);assert lab._page=='root' and lab._selected==0
pick('Tools');path('tools');shot('tools')
assert [r[1] for r in lab.MENUS['tools']]==['Graph','Graph3D','Scientific calculator']
pick('Scientific calculator');assert vm.current_view.name=='eng_calculator'
path('tools','Scientific calculator');shot('calculator')
from engtools.calculator import app as calc
key(k.BUTTON_F2);assert calc._active.page=='modes';path('tools','Scientific calculator')
key(k.BUTTON_ESCAPE);exit_child()
assert lab._page=='tools' and lab._selected==2;path('tools')
# Graph's own menus, drawing progress and inline editor retain the route.
pick('Graph');assert vm.current_view.name=='app_Graph';path('tools','Graph')
from engtools.plots import plot2d
for _ in range(2000):
    key(k.BUTTON_NONE)
    if plot2d._app.completed:break
key(k.BUTTON_CENTER);key(k.BUTTON_CENTER)
# Editing happens in place under the shared title bar: no on-screen keyboard.
assert plot2d._app.state=='input' and plot2d._app.edit is not None
assert not hasattr(plot2d._app,'_keyboard')
path('tools','Graph');shot('graph-editor')
key(k.BUTTON_2);path('tools','Graph')
exit_child();assert lab._page=='tools' and lab._selected==0;path('tools')
assert breadcrumbs.current(vm,'app_Graph') is None
pick('Graph3D');assert vm.current_view.name=='app_Graph3D';path('tools','Graph3D')
from engtools.plots import plot3d
for _ in range(2000):
    key(k.BUTTON_NONE)
    if plot3d._state==plot3d.ST_PLOT and not plot3d._dirty:break
key(k.BUTTON_CENTER)
assert plot3d._state==plot3d.ST_INPUT and plot3d._edit is not None,(plot3d._state,vm.current_view.name)
path('tools','Graph3D');shot('graph3d-editor')
exit_child();assert lab._page=='tools' and lab._selected==1
assert plot3d._edit is None and breadcrumbs.current(vm,'app_Graph3D') is None
key(k.BUTTON_ESCAPE);assert lab._page=='root' and lab._selected==1
pick('Modules');path('modules');shot('modules')
assert [r[1] for r in lab.MENUS['modules']]==['Structural','Dynamics','Thermal','Electrical','Fluids']
for label in ('Dynamics','Thermal','Electrical','Fluids'):
    pick(label);path('modules',label.lower())
    assert lab.MENUS[lab._page]==()
    page=lab._page
    key(k.BUTTON_UP);key(k.BUTTON_DOWN);key(k.BUTTON_CENTER)
    assert lab._page==page and vm.current_view.name=='lab'
    shot(label.lower())
    key(k.BUTTON_ESCAPE);assert lab._page=='modules'
pick('Structural');path('modules','structural');shot('structural')
pick('Beam view');assert vm.current_view.name=='beam_lab';path('modules','structural','Beam view')
from engtools.beamlab import app as beam
key(k.BUTTON_CENTER);assert beam._active.solution is not None
shot('beam-view')
key(k.BUTTON_F9);assert beam._active.help_open;path('modules','structural','Beam view')
shot('beam-help')
key(k.BUTTON_ESCAPE);key(k.BUTTON_ESCAPE)
assert lab._page=='structural' and lab._selected==0
path('modules','structural')
key(k.BUTTON_ESCAPE);assert lab._page=='modules' and lab._selected==0
key(k.BUTTON_ESCAPE);assert lab._page=='root' and lab._selected==2
key(k.BUTTON_ESCAPE);assert vm.current_view.name=='parent' and breadcrumbs.current(vm) is None
assert not breadcrumbs._paths
# Home unwinds child+launcher too, without leaking a path to later apps.
vm.add(View('lab',lab.run,lab.start,lab.stop));vm.switch_to('lab')
pick('Tools');pick('Scientific calculator')
key(k.BUTTON_HOME)
assert vm.current_view.name=='parent' and not breadcrumbs._paths
assert lab._page=='root' and not lab._resume and not lab._suspended
# Full and legacy simulator routes resolve through the new folders.
for route in ('PicoLAB/checks/Numerics check','PicoLAB/checks/Plot previews',
              'PicoLAB/tools/Graph','PicoLAB/tools/Graph3D','PicoLAB/tools/Scientific calculator',
              'PicoLAB/modules/structural/Beam view','PicoLAB/modules/thermal',
              'Apps/PicoLAB/Graph','PicoLAB/Beam Lab'):
    sim_runtime._keys=[];sim_runtime.request_open(route);assert sim_runtime._keys
try:sim_runtime.request_open('PicoLAB/modules/structural/Missing')
except sim_runtime.LaunchTargetError:pass
else:raise AssertionError('Invalid nested path accepted')
print('PASS: Checks/Tools/Modules hierarchy, planned disciplines, selection restoration, Beam view rename, native keyboard bounds and logo breadcrumbs throughout')
print('PASS: managed path inheritance, child cleanup, Home cleanup and full/legacy simulator routes')
