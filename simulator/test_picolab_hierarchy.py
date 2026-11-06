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
assert [r[1] for r in lab.MENUS['checks']]==['Numerics check','Plot previews','Calculator check']
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
pick('Calculator check');assert vm.current_view.name=='calculator_check'
path('checks','Calculator check')
exit_child();assert lab._page=='checks' and lab._selected==2
key(k.BUTTON_ESCAPE);assert lab._page=='root' and lab._selected==0
pick('Tools');path('tools');shot('tools')
assert [r[1] for r in lab.MENUS['tools']]==['Grapher','Scientific calculator','UnitConverter']
pick('UnitConverter');assert vm.current_view.name=='unitconvert_view'
path('tools','UnitConverter')
sys.modules['engtools.unitconvert.app']._active.row=0
key(k.BUTTON_CENTER);key(k.BUTTON_CENTER)  # Category field / Length
key(k.BUTTON_ESCAPE);key(k.BUTTON_ESCAPE)
assert lab._page=='tools' and lab._selected==2;path('tools')
pick('Scientific calculator');assert vm.current_view.name=='eng_calculator'
path('tools','Scientific calculator');shot('calculator')
from engtools.calculator import app as calc
key(k.BUTTON_F3);calc._active.selected=2;key(k.BUTTON_CENTER);assert calc._active.page=='modes';path('tools','Scientific calculator')
key(k.BUTTON_ESCAPE);exit_child()
assert lab._page=='tools' and lab._selected==1;path('tools')
# The unified workspace keeps the route through mode changes and editors.
pick('Grapher');assert vm.current_view.name=='eng_grapher';path('tools','Grapher')
from engtools.plots import runtime
for _ in range(2000):
    key(k.BUTTON_NONE)
    if runtime._active.controller.app.completed:break
key(k.BUTTON_CENTER);key(k.BUTTON_CENTER)
assert runtime._active.controller.app.state=='input'
assert runtime._active.controller.app.edit is not None
path('tools','Grapher');shot('grapher-editor')
key(k.BUTTON_2);path('tools','Grapher')
key(k.BUTTON_ESCAPE);key(k.BUTTON_ESCAPE);key(k.BUTTON_F3);key(k.BUTTON_DOWN);key(k.BUTTON_DOWN);key(k.BUTTON_CENTER)
for _ in range(2000):
    key(k.BUTTON_NONE)
    engine=runtime._active.engine
    if engine._state==engine.ST_PLOT and not engine._dirty:break
key(k.BUTTON_CENTER)
assert engine._state==engine.ST_INPUT and engine._edit is not None
path('tools','Grapher');shot('grapher-3d-editor')
exit_child();assert lab._page=='tools' and lab._selected==0
assert engine._edit is None and breadcrumbs.current(vm,'eng_grapher') is None
key(k.BUTTON_ESCAPE);assert lab._page=='root' and lab._selected==1
pick('Modules');path('modules');shot('modules')
assert [r[1] for r in lab.MENUS['modules']]==['Structural','Machine design','Dynamics','Fluids','Thermal','Electrical']
for label in ('Dynamics','Fluids'):
    pick(label);path('modules',label.lower())
    assert lab.MENUS[lab._page]==()
    names={'Dynamics':('ModalHarmonics','TransientSolve','Multibody','TransferFunc'),
           'Fluids':('FlowRegimes','PipeLoss','BoundaryDrag','1DNetSolve')}
    assert tuple(row[0] for row in lab.PLANNED[lab._page])==names[label]
    assert all(row[1].startswith('Planned:') for row in lab.PLANNED[lab._page])
    before=set(sys.modules)
    page=lab._page
    key(k.BUTTON_UP);key(k.BUTTON_DOWN);key(k.BUTTON_CENTER)
    assert lab._page==page and vm.current_view.name=='lab' and set(sys.modules)==before
    shot(label.lower())
    key(k.BUTTON_ESCAPE);assert lab._page=='modules'
# The moved tool retains its model, folder selection and new breadcrumb.
pick('Machine design');path('modules','machine design');shot('machine-design')
assert [r[1] for r in lab.MENUS['machine']]==['PicoCAD']
pick('PicoCAD');assert vm.current_view.name=='picocad_view'
path('modules','machine design','PicoCAD')
from engtools.picocad import app as cad
for _ in range(2000):
    key(k.BUTTON_NONE)
    if cad._active.job is None:break
assert cad._active.geometry is not None
model=cad.dm.clone(cad._active.model)
key(k.BUTTON_F9);assert cad._active.help_open
path('modules','machine design','PicoCAD');shot('machine-design-help')
key(k.BUTTON_ESCAPE);exit_child()
assert lab._page=='machine' and lab._selected==0
pick('PicoCAD');cad=sys.modules['engtools.picocad.app'];assert cad._active.model==model
exit_child();key(k.BUTTON_ESCAPE)
assert lab._page=='modules' and lab._selected==1
# Electrical holds PicoSpice, opened with its breadcrumb; ESC returns.
pick('Electrical');path('modules','electrical')
assert [r[1] for r in lab.MENUS['electrical']]==['PicoSpice']
pick('PicoSpice');assert vm.current_view.name=='spice_view';path('modules','electrical','PicoSpice')
shot('picospice')
exit_child();assert lab._page=='electrical' and lab._selected==0
key(k.BUTTON_ESCAPE);assert lab._page=='modules'
pick('Structural');path('modules','structural');shot('structural')
pick('Section Properties');assert vm.current_view.name=='sectionprops_view'
path('modules','structural','Section Properties')
from engtools.sectionprops import app as sectionprops
assert sectionprops._active.solution['A'] > 0
key(k.BUTTON_F9);assert sectionprops._active.help_view.opened
key(k.BUTTON_ESCAPE);key(k.BUTTON_ESCAPE)
assert lab._page=='structural' and lab._selected==5
pick('Buckling');assert vm.current_view.name=='buckling_view';path('modules','structural','Buckling')
key(k.BUTTON_F6)
from engtools.buckling import app as buckling
assert buckling._active.solution is not None
key(k.BUTTON_F9);assert buckling._active.help_view.opened
key(k.BUTTON_ESCAPE)
key(k.BUTTON_ESCAPE);assert lab._page=='structural' and lab._selected==4
pick('StressStrain');assert vm.current_view.name=='stressstrain_view';path('modules','structural','StressStrain')
key(k.BUTTON_F6)
from engtools.stressstrain import app as stressstrain
assert stressstrain._active.solution is not None
key(k.BUTTON_ESCAPE);assert lab._page=='structural' and lab._selected==3
pick('BeamView');assert vm.current_view.name=='beam_lab';path('modules','structural','BeamView')
from engtools.beamlab import app as beam
key(k.BUTTON_CENTER);assert beam._active.solution is None
key(k.BUTTON_F6);assert beam._active.solution is not None
shot('beam-view')
key(k.BUTTON_F9);assert beam._active.help_open;path('modules','structural','BeamView')
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
for route in ('PicoLAB/checks/Numerics check','PicoLAB/checks/Plot previews','PicoLAB/checks/Calculator check',
              'PicoLAB/tools/Grapher','PicoLAB/tools/Graph','PicoLAB/tools/Graph3D','PicoLAB/tools/Scientific calculator','PicoLAB/tools/UnitConverter',
              'PicoLAB/modules/structural/BeamView','PicoLAB/modules/thermal',
              'PicoLAB/modules/Machine design','PicoLAB/modules/Machine design/PicoCAD',
              'PicoLAB/modules/machine/PicoCAD','Apps/PicoLAB/tools/PicoCAD','PicoLAB/PicoCAD',
              'PicoLAB/modules/structural/StressStrain',
              'PicoLAB/modules/structural/Buckling',
              'PicoLAB/modules/structural/Section Properties',
              'PicoLAB/modules/electrical/PicoSpice',
              'Apps/PicoLAB/Graph','PicoLAB/Beam Lab'):
    sim_runtime._keys=[];sim_runtime.request_open(route);assert sim_runtime._keys
for folder,name in (('dynamics','ModalHarmonics'),('fluids','PipeLoss')):
    try:sim_runtime.request_open('PicoLAB/modules/'+folder+'/'+name)
    except sim_runtime.LaunchTargetError:pass
    else:raise AssertionError('Planned app accepted as a launch target')
try:sim_runtime.request_open('PicoLAB/modules/structural/Missing')
except sim_runtime.LaunchTargetError:pass
else:raise AssertionError('Invalid nested path accepted')
print('PASS: Checks/Tools/Modules hierarchy, planned disciplines, selection restoration, BeamView rename, native keyboard bounds and logo breadcrumbs throughout')
print('PASS: managed path inheritance, child cleanup, Home cleanup and full/legacy simulator routes')
