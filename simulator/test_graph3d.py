"""Run with the desktop MicroPython build, from the project root."""
import os,sys
from time import ticks_ms,sleep_ms
root=os.getcwd()
sys.path.insert(0,root+'/src/MicroPython')
sys.path.insert(0,root+'/simulator/hardware')
sys.path.insert(0,root+'/builds/MicroPython/apps_unfrozen')
import sim_runtime
sd='/private/tmp/picoware-graph3d-test-'+str(ticks_ms())
sim_runtime.configure(root,sd,root+'/builds/MicroPython/apps_unfrozen',1,
                     'picocalc-pico2w',0,True,False,False,False,'',
                     _network_mode='offline',_audio_mode='silent')
sim_runtime.mkdir_p(sd)
from picoware.system.view_manager import ViewManager
from picoware.system.input import Input
from picoware.system.buttons import *
Input.button=property(lambda self:self._last_button)
from engtools.plots import plot3d as g
from engtools.plots import plot2d as Graph
vm=ViewManager()
def key(button):
 vm.input_manager._last_button=button
 vm._button=button
 g.run(vm)
def sampled():
 for _ in range(10000):
  if g._state!=g.ST_SAMPLING: break
  key(BUTTON_NONE)
 assert g._state==g.ST_PLOT,(g._state,g._error_msg)
 key(BUTTON_NONE)
def settle():
 sleep_ms(270); key(BUTTON_NONE)
assert g.start(vm)
sampled()
assert g._state==g.ST_PLOT and g._zs and g._navigation=='pan'
key(BUTTON_NONE)
vm.draw.screenshot('/private/tmp/graph3d-default.bmp')
palette=Graph.theme.system_palette(vm)
assert g.C_BG==palette.BG and g.C_PANEL==palette.PANEL and g.C_ACCENT==vm.selected_color and g.C_SEL==palette.SELECT
mesh=g._zs
pitch,yaw=g._pitch,g._yaw
key(BUTTON_RIGHT); assert g._pan_x>0 and (g._pitch,g._yaw)==(pitch,yaw)
key(BUTTON_UP); assert g._pan_y<0
assert g._zs is mesh and not g._need_eval
key(BUTTON_PLUS); assert g._zoom>1
key(BUTTON_MINUS); assert abs(g._zoom-1)<1e-6
settle(); assert g._preview_at is None
vm.draw.screenshot('/private/tmp/graph3d-pan.bmp')
key(BUTTON_SPACE); assert g._navigation=='orbit'
key(BUTTON_RIGHT); assert g._yaw!=yaw
key(BUTTON_UP); assert g._pitch!=pitch
settle()
vm.draw.screenshot('/private/tmp/graph3d-orbit.bmp')
key(BUTTON_F)
assert g._zs is mesh
assert (g._pitch,g._yaw)!=(pitch,yaw)
vm.draw.screenshot('/private/tmp/graph3d-fit.bmp')
# Every fitted sampled vertex must project inside the plot's padding.
for j,row in enumerate(g._zs):
 for i,z in enumerate(row):
  if z is None: continue
  p=g._xform(-g._range+i*2*g._range/(g._grid_n-1),(z-(g._zmin+g._zmax)/2)*g._zscale,-g._range+j*2*g._range/(g._grid_n-1))
  assert p and g._px0<=p[0]<=g._px1 and g._py0<=p[1]<=g._py1,p
# Clipping never passes floats or offscreen coordinates into native drawing.
class GuardDraw:
 def _line(self,*args):
  for i,v in enumerate(args[:-1]): assert isinstance(v,int)
  assert all(g._px0<=args[i]<=g._px1 for i in (0,2))
  assert all(g._py0<=args[i]<=g._py1 for i in (1,3))
 def _fill_triangle(self,*args):
  assert all(isinstance(v,int) for v in args)
  assert all(g._px0<=args[i]<=g._px1 for i in (0,2,4))
  assert all(g._py0<=args[i]<=g._py1 for i in (1,3,5))
guard=GuardDraw()
g._clip_line(guard,(-100,100),(500,150),g.C_ACCENT)
g._fill_clipped_triangle(guard,(-100,-100),(500,100),(100,500),g.C_ACCENT)
# High zoom/pan remain safe; a final solid render refines the wire preview.
for _ in range(12): key(BUTTON_PLUS)
settle(); assert g._zoom==8.0
vm.draw.screenshot('/private/tmp/graph3d-zoom.bmp')
for _ in range(30): key(BUTTON_MINUS)
assert g._zoom==0.2
key(BUTTON_R); assert (g._pitch,g._yaw,g._zoom,g._pan_x,g._pan_y)==(.55,.70,1.,0.,0.)
key(BUTTON_W); assert g._state==g.ST_SETTINGS
key(BUTTON_NONE)
vm.draw.screenshot('/private/tmp/graph3d-settings.bmp')
def row(name): return [r[0] for r in g._settings_rows()].index(name)
def typed(text):
 for c in text: key(vm.input_manager._key_to_button(ord(c)))
g._set_row=row('nav'); before=g._navigation; key(BUTTON_CENTER); assert g._navigation!=before
key(BUTTON_CENTER); assert g._navigation==before
# Ranges are typed in place, like Beam view's values: no on-screen keyboard.
g._set_row=row('x1'); typed('6'); assert g._edit is not None and g._edit.text=='6'
key(BUTTON_DOWN); assert g._edit is None and g._bounds==[-4,6,-4,4] and g._need_eval and g._set_row==row('y0')
typed('-2'); key(BUTTON_CENTER); assert g._bounds==[-4,6,-2,4]
g._set_row=row('x0'); typed('9'); key(BUTTON_CENTER)
assert g._edit is not None and g._edit_error and 'below' in g._edit_note and g._bounds==[-4,6,-2,4]
key(BUTTON_ESCAPE); assert g._edit is None and g._state==g.ST_SETTINGS
vm.draw.screenshot('/private/tmp/graph3d-settings-ranges.bmp')
key(BUTTON_ESCAPE); sampled(); assert g._state==g.ST_PLOT and not g._need_eval
xs=[g._mesh[i] for i in range(0,len(g._mesh),3)]; ys=[g._mesh[i+1] for i in range(0,len(g._mesh),3)]
assert abs(max(xs)-min(xs)-10)<1e-3 and abs(max(ys)-min(ys)-6)<1e-3, 'Equal aspect keeps true x and y spans'
vm.draw.screenshot('/private/tmp/graph3d-ranges.bmp')
# Box aspect stretches both axes to the same displayed size; a fixed Z clips the surface.
key(BUTTON_W); g._set_row=row('aspect'); key(BUTTON_CENTER); assert g._aspect=='box'
g._set_row=row('z1'); typed('0.3'); key(BUTTON_CENTER); assert g._zrange and g._zrange[1]==0.3
key(BUTTON_ESCAPE); sampled()
xs=[g._mesh[i] for i in range(0,len(g._mesh),3)]; ys=[g._mesh[i+1] for i in range(0,len(g._mesh),3)]
assert abs((max(xs)-min(xs))-(max(ys)-min(ys)))<1e-3 and g._zmax==0.3
assert max(g._mesh[i+2] for i in range(0,len(g._mesh),3))<=0.3+1e-6
key(BUTTON_W); g._set_row=row('zmode'); key(BUTTON_CENTER); assert g._zrange is None
g._set_row=row('aspect'); key(BUTTON_CENTER); assert g._aspect=='equal'
key(BUTTON_ESCAPE); sampled()
# Heat map: style cycles wire -> heat map; the probe reads f at its cell.
key(BUTTON_S); sampled(); assert g._style==0
key(BUTTON_S); sampled(); assert g._style==2 and g._heat_info and g._heat_lines is not None
cols,rows,left,top,cw,ch,lo,hi=g._heat_info
assert cols>40 and rows>30 and lo<0<hi
vm.draw.screenshot('/private/tmp/graph3d-heatmap.bmp')
p0=list(g._probe); key(BUTTON_RIGHT); key(BUTTON_UP); assert g._probe==[p0[0]+1,p0[1]-1]
x,y=g._probe_point(); assert abs(g._field(g._surface_expression(g._expr)[1],dict(g._SAFE),x,y)-0.6*g.sin(x)*g.cos(y))<1e-5
key(BUTTON_L); assert not g._contours
vm.draw.screenshot('/private/tmp/graph3d-heatmap-plain.bmp')
key(BUTTON_L); old=g._xy_bounds(); key(BUTTON_PLUS); sampled()
assert g._xy_bounds()[1]-g._xy_bounds()[0]<old[1]-old[0] and g._style==2
# An implicit surface refuses the heat map with a reason and stays 3D.
g._expr='x^2+y^2+z^2=1'; g._bounds=None; g._range=2; g._need_eval=g._need_heat=True; g._goto_plot(vm); sampled()
assert g._style==1 and g._toast_error and 'implicit' in g._toast
vm.draw.screenshot('/private/tmp/graph3d-heatmap-implicit.bmp')
key(BUTTON_S); key(BUTTON_S); sampled(); assert g._style==1 and g._toast_error
g._expr='0.6*sin(x)*cos(y)'; g._range=4; g._need_eval=g._need_heat=True; g._goto_plot(vm); sampled()
key(BUTTON_ESCAPE); assert g._state==g.ST_MENU
vm.draw.screenshot('/private/tmp/graph3d-menu.bmp')
# Existing presets, second surface, saved equations and slices remain usable.
g._menu.set_selected(3); key(BUTTON_CENTER); assert g._state==g.ST_PRESETS
g._preset_menu.set_selected(2); key(BUTTON_CENTER); sampled(); assert g._state==g.ST_PLOT
g._expr2='0.1*x*y'; g._need_eval=True; g._goto_plot(vm); sampled()
assert g._zs2
key(BUTTON_C); assert g._state==g.ST_SLICE
key(BUTTON_RIGHT); key(BUTTON_C); key(BUTTON_ESCAPE)
key(BUTTON_F9); assert g._state==g.ST_HELP
key(BUTTON_DOWN); key(BUTTON_ESCAPE)
g._saved=[g._pack_entry()]; assert g._write_saved(vm.storage)
g._saved=[]; g._load_saved(vm.storage); assert '0.1*x*y' in g._saved[0]
# Idle plot stays still; auto-spin is paced rather than tied to loop speed.
g._goto_plot(vm); sampled()
yaw=g._yaw; key(BUTTON_NONE); assert g._yaw==yaw
key(BUTTON_A); assert g._auto
sleep_ms(60); key(BUTTON_NONE); assert g._yaw!=yaw
key(BUTTON_A); settle(); assert not g._auto and g._preview_at is None
g.stop(vm); assert g._zs is None and g._zs2 is None
print('PASS: pan/orbit, zoom limits, fit, typed ranges, aspect, fixed z, heat map, probe, contours, implicit refusal, menus, slices, presets, saved equations and paced spin')
