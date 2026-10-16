"""Shared viewer integration: gallery, sampled data, navigation and isolation."""
import os,sys,json
from time import ticks_ms
root=os.getcwd()
sys.path.insert(0,root+'/src/MicroPython');sys.path.insert(0,root+'/simulator/hardware')
sys.path.insert(0,root+'/builds/MicroPython/apps_unfrozen')
import sim_runtime
sd='/private/tmp/shared-plot-test-'+str(ticks_ms())
sim_runtime.configure(root,sd,root+'/builds/MicroPython/apps_unfrozen',1,'picocalc-pico2w',0,True,False,False,False,'',_network_mode='offline',_audio_mode='silent')
sim_runtime.mkdir_p(sd)
from picoware.system.view_manager import ViewManager
from picoware.system.view import View
from picoware.system.input import Input
from picoware.system.buttons import *
Input.button=property(lambda self:self._last_button)
import PicoLAB as lab
import Graph,Graph3D
assert Graph._engine is None and Graph3D._engine is None
assert 'engtools.plots.plot2d' not in sys.modules and 'engtools.plots.plot3d' not in sys.modules
from engtools.plots import view as plot_view
captured=[]
real_open=plot_view.open_view
def capture_open(vm,name,controller):
 captured[:]=[controller]
 return real_open(vm,name,controller)
plot_view.open_view=capture_open
vm=ViewManager()
vm.add(View('parent',lambda vm:None,lambda vm:True,lambda vm:None));vm.switch_to('parent')
vm.add(View('lab',lab.run,lab.start,lab.stop));vm.switch_to('lab')
vm.storage.mkdir('picoware/settings');vm.storage.mkdir('picoware/settings/graph');vm.storage.mkdir('picoware/settings/graph3d')
baseline=json.dumps({'version':1,'expressions':[['cos(x)',True]],'bounds':[-2,2,-2,2],'t':[0,6.28],'padding':10,'grid':True})
assert vm.storage.write('picoware/settings/graph/session.json',baseline)
assert vm.storage.write('picoware/settings/graph3d/saved.txt','sin(x)\n')
def key(button):
 vm.input_manager._last_button=button;vm.run()
def finish():
 for _ in range(2000):
  key(BUTTON_NONE)
  name=vm.current_view.name
  if name=='eng_plot2d':
   owner=captured[0]
   if owner.app.completed and owner.app.job is None and owner.app.refine is None:return owner
  elif name=='eng_plot3d':
   from engtools.plots import plot3d
   if plot3d._state==plot3d.ST_ERROR:raise AssertionError(plot3d._error_msg)
   if plot3d._state==plot3d.ST_PLOT and not plot3d._dirty:return captured[0]
 raise AssertionError('Plot did not finish')
vm.draw.screenshot('/private/tmp/shared-lab-menu.bmp')
lab._selected=2
key(BUTTON_CENTER);assert lab._page=='gallery'
vm.draw.screenshot('/private/tmp/shared-gallery-menu.bmp')
count=vm._view_count
for index in range(5):
 assert lab._gallery_selected==index
 key(BUTTON_CENTER)
 owner=finish()
 vm.draw.screenshot('/private/tmp/shared-preview-'+str(index)+'.bmp')
 if index==0:assert 'engtools.plots.plot3d' not in sys.modules
 if index==3:
  from engtools.plots import plot3d
  key(BUTTON_H);assert plot3d._state==plot3d.ST_HELP
  key(BUTTON_ESCAPE);finish()
 if index==2:
  assert owner.app.items[0].points and owner.app.items[1].style=='scatter'
  assert owner.app.axes_spec['x']['unit']=='s'
  old=owner.app.bounds[:]
  key(BUTTON_RIGHT);assert owner.app.bounds[0]>old[0]
  key(BUTTON_PLUS);assert owner.app.bounds[1]-owner.app.bounds[0]<old[1]-old[0]
  owner.app.refine=None;owner.app.dirty=True;finish()
  key(BUTTON_CENTER);assert owner.app.state=='expressions'
  key(BUTTON_SPACE);assert not owner.app.items[0].visible
  key(BUTTON_SPACE);key(BUTTON_ESCAPE);finish()
 key(BUTTON_ESCAPE)
 assert vm.current_view.name=='lab' and lab._page=='gallery' and lab._gallery_selected==index
 assert vm._view_count==count
 if index<4:key(BUTTON_DOWN)
assert vm.storage.read('picoware/settings/graph/session.json')==baseline
assert vm.storage.read('picoware/settings/graph3d/saved.txt')=='sin(x)\n'
from engtools.plots import plot2d,plot3d,gallery
assert plot3d._mesh is None and plot3d._sampling is None
assert plot3d._expr=='0.6*sin(x)*cos(y)' and plot3d._range==4
# Invalid specifications cannot replace the caller's current view.
for bad in ({'series':[]},{'series':[{'expression':'open(x)'}]},
            {'series':[{'type':'samples','points':[(0,float('inf'))]}]},
            {'series':[{'expression':'x'}],'axes':{'x':{'scale':'log'}}}):
 try:plot2d.show(vm,bad)
 except ValueError:pass
 else:raise AssertionError('Bad 2D spec accepted')
 assert vm.current_view.name=='lab'
for bad in ({'surfaces':[]},{'surfaces':[{'expression':'z=x'}],'resolution':65},
            {'surfaces':[{'expression':'x^2+y^2+z^2=1'}],'range':0}):
 try:plot3d.show(vm,bad)
 except ValueError:pass
 else:raise AssertionError('Bad 3D spec accepted')
 assert vm.current_view.name=='lab'
# A high-resolution embedded plot can be cancelled before allocation.
plot3d.show(vm,{'title':'Warning test','surfaces':[{'expression':'x^2+y^2+z^2=1'}],'resolution':25})
assert plot3d._state==plot3d.ST_RES_WARNING
key(BUTTON_ESCAPE);assert vm.current_view.name=='lab' and vm._view_count==count
# Confirmation starts an embedded high-N job; sampling/error exits return to the caller.
plot3d.show(vm,{'surfaces':[{'expression':'z=0.1*x*y'}],'resolution':25})
assert plot3d._state==plot3d.ST_RES_WARNING
key(BUTTON_CENTER);finish();assert plot3d._grid_n==25
key(BUTTON_ESCAPE);assert vm.current_view.name=='lab' and vm._view_count==count
plot3d.show(vm,{'surfaces':[{'expression':'x^2+y^2+z^2=1'}]})
assert plot3d._state==plot3d.ST_SAMPLING
key(BUTTON_ESCAPE);assert vm.current_view.name=='lab' and plot3d._sampling is None
plot3d.show(vm,{'surfaces':[{'expression':'x^2+y^2+z^2=-1'}],'resolution':8})
for _ in range(1000):
 key(BUTTON_NONE)
 if plot3d._state==plot3d.ST_ERROR:break
assert plot3d._state==plot3d.ST_ERROR
key(BUTTON_ESCAPE);assert vm.current_view.name=='lab' and vm._view_count==count
# Both original SD apps delegate to the same engines and still work standalone.
key(BUTTON_ESCAPE);key(BUTTON_ESCAPE);assert vm.current_view.name=='parent'
vm.add(View('graph',Graph.run,Graph.start,Graph.stop));vm.switch_to('graph')
assert Graph._engine is plot2d and plot2d._app.persistent
for _ in range(100):
 key(BUTTON_NONE)
 if plot2d._app.completed:break
assert plot2d._app.items[0].text=='cos(x)'
vm.back();assert Graph._engine is None and plot2d._app is None
vm.add(View('graph3d',Graph3D.run,Graph3D.start,Graph3D.stop));vm.switch_to('graph3d')
assert Graph3D._engine is plot3d
for _ in range(2000):
 key(BUTTON_NONE)
 if plot3d._state==plot3d.ST_PLOT and not plot3d._dirty:break
assert plot3d._mesh_colors
vm.back();assert Graph3D._engine is None and plot3d._mesh is None
print('PASS: gallery visuals, sampled curves/scatter, labels, controls, lazy engines, return selection, view cleanup, session isolation, validation, high-N cancellation and standalone wrappers')
