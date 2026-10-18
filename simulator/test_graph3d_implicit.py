"""Implicit geometry, custom resolution and warning/cancellation regressions."""
import os,sys
from time import ticks_ms
root=os.getcwd()
sys.path.insert(0,root+'/src/MicroPython');sys.path.insert(0,root+'/simulator/hardware')
sys.path.insert(0,root+'/builds/MicroPython/apps_unfrozen')
import sim_runtime
sd='/private/tmp/picoware-implicit-test-'+str(ticks_ms())
sim_runtime.configure(root,sd,root+'/builds/MicroPython/apps_unfrozen',1,'picocalc-pico2w',0,True,False,False,False,'',_network_mode='offline',_audio_mode='silent')
sim_runtime.mkdir_p(sd)
from picoware.system.view_manager import ViewManager
from picoware.system.input import Input
from picoware.system.buttons import *
Input.button=property(lambda self:self._last_button)
from engtools.plots import plot3d as g
vm=ViewManager()
def key(button):
 vm.input_manager._last_button=button; vm._button=button; g.run(vm)
def sample(expression,n=16,r=2):
 g._expr=expression;g._expr2='';g._grid_n=n;g._range=r;g._need_eval=True
 g._goto_plot(vm)
 assert g._state==g.ST_SAMPLING
 for i in range(10000):
  key(BUTTON_NONE)
  if g._state!=g.ST_SAMPLING: break
 assert g._state==g.ST_PLOT,(expression,g._error_msg)
 key(BUTTON_NONE)
 assert g._mesh_colors and len(g._mesh)==len(g._mesh_colors)*9
 return i
assert g.start(vm)
for equation,implicit in [('z = x^2+y^2',False),('x+y=z',False),('sin(x)*cos(y)',False),('x^2+y^2+z^2=1',True),('x^2+y^2+z^2-1',True),('z^2=x^2+y^2',True),('x=0',True)]:
 assert g._surface_expression(equation)[0]==implicit,equation
for bad in ('x==y','z=','open(x)','__import__(x)','x.__class__','x<y'):
 try:g._surface_expression(bad)
 except Exception:pass
 else:raise AssertionError(bad)
# Any integer N in the supported range, not just a preset.
for n in (4,9,15,24,64): assert g._resolution_warning(n)[2]>0
for n in (0,3,65,12.5):
 try:g._resolution_warning(n)
 except ValueError:pass
 else:raise AssertionError(n)
# Sphere is closed in all octants, includes both z hemispheres and keeps equal XYZ scale.
iterations=sample('x^2+y^2+z^2=1',16)
assert iterations>1 and g._has_implicit and g._zscale==1
vertices=[g._mesh[i:i+3] for i in range(0,len(g._mesh),3)]
for axis in (0,1,2):
 assert min(v[axis] for v in vertices)<-.9
 assert max(v[axis] for v in vertices)>.9
assert max(abs(sum(x*x for x in v)-1) for v in vertices)<.1
vm.draw.screenshot('/private/tmp/graph3d-sphere.bmp')
# All projected vertices of the auto-fitted sphere are inside the frame.
for v in vertices:
 p=g._world_point(v)
 assert p and g._px0<=p[0]<=g._px1 and g._py0<=p[1]<=g._py1,p
# General axis-aligned equations and toroidal topology are sampled, not converted to a heightfield.
sample('x=0',12); assert all(abs(g._mesh[i])<1e-6 for i in range(0,len(g._mesh),3))
sample('(sqrt(x^2+y^2)-1.2)^2+z^2=0.25',16)
assert g._has_implicit
vm.draw.screenshot('/private/tmp/graph3d-torus.bmp')
# Mixed heightfield + implicit surfaces share one coordinate scale and both color groups.
g._expr='x^2+y^2+z^2=1';g._expr2='z=0';g._grid_n=12;g._range=2
assert g._eval_grid(),g._error_msg
assert any(c==0 for c in g._mesh_colors) and any(c==1 for c in g._mesh_colors) and g._zs2
# Exercise actual numeric-editor validation and warning transitions.
class KeyboardStub:
 def __init__(self): self.response='';self.title='';self.is_finished=False
 def reset(self): self.response='';self.is_finished=False
 def run(self,force=False): return True
# Graph3D owns a scoped keyboard to retain its PicoLAB breadcrumb.
old_keyboard=g._keyboard
g._keyboard=KeyboardStub()
g._grid_n=12;g._state=g.ST_SETTINGS;g._set_row=1
key(BUTTON_CENTER);assert g._state==g.ST_RESOLUTION
g._keyboard.response='12.5';g._keyboard.is_finished=True
key(BUTTON_NONE);assert g._state==g.ST_RESOLUTION and g._grid_n==12
g._keyboard.response='25';g._keyboard.is_finished=True
key(BUTTON_NONE);assert g._state==g.ST_RES_WARNING and g._grid_n==12
key(BUTTON_ESCAPE);assert g._state==g.ST_SETTINGS and g._grid_n==12
key(BUTTON_CENTER);g._keyboard.response='15';g._keyboard.is_finished=True
key(BUTTON_NONE);assert g._state==g.ST_SETTINGS and g._grid_n==15
g._keyboard=old_keyboard
# Warning leaves the old resolution untouched until confirmed.
g._grid_n=12;g._resolution_return=g.ST_SETTINGS;g._pending_resolution=25;g._state=g.ST_RES_WARNING
g._draw_resolution_warning(vm.draw)
vm.draw.screenshot('/private/tmp/graph3d-resolution-warning.bmp')
key(BUTTON_ESCAPE);assert g._grid_n==12 and g._state==g.ST_SETTINGS
g._state=g.ST_RES_WARNING;key(BUTTON_CENTER);assert g._grid_n==25 and g._need_eval
# Cancel a large cubic job before it can finish; release memory and retain editable expressions.
g._expr2='';g._goto_plot(vm);key(BUTTON_NONE)
assert g._state==g.ST_SAMPLING
key(BUTTON_ESCAPE);assert g._state==g.ST_MENU and g._sampling is None and g._mesh is None
# Invalid or unresolved equations produce a clear error instead of a partial surface.
g._expr='x^2+y^2+z^2=-1';g._grid_n=8;g._need_eval=True;g._goto_plot(vm)
for _ in range(1000):
 key(BUTTON_NONE)
 if g._state!=g.ST_SAMPLING:break
assert g._state==g.ST_ERROR and g._mesh is None
# Dense mesh safeguards reject the complete result; they never truncate the surface silently.
g._expr='z=x*y';g._grid_n=12;generator=g._sample_job();next(generator);g._mesh_limit=1
try:
 for _ in generator:pass
except ValueError as exc:assert 'detailed' in str(exc)
else:raise AssertionError('Mesh cap ignored')
g._release_mesh()
print('PASS: sphere octants/equal scale, torus, planes, mixed surfaces, custom N, warnings, confirmation, cancellation, domain errors and mesh memory cap')
