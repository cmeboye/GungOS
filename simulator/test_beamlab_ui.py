"""Beam Lab panel clipping, theme changes, inline controls and compact help."""
import os,sys
from time import ticks_ms
root=os.getcwd()
for part in ('src/MicroPython','simulator/hardware','builds/MicroPython/apps_unfrozen'):
    sys.path.insert(0,root+'/'+part)
import sim_runtime
sim_runtime.configure(root,'/private/tmp/gungos-beamlab-ui-'+str(ticks_ms()),
    root+'/builds/MicroPython/apps_unfrozen',1,'picocalc-pico2w',0,True,False,False,False,'',
    _network_mode='offline',_audio_mode='silent',_sd_profile='clean')
from picoware.system.view_manager import ViewManager
from picoware.system.view import View
from picoware.system.input import Input
from picoware.system import buttons as k
from engtools.ui.viewport import Viewport
from engtools.ui.forms import LineEdit
from engtools.beamlab import app,model as bm,render
from sim_pixels import Pixels,colour
Input.button=property(lambda self:self._last_button)
vm=ViewManager();vm._wifi=None;draw=vm.draw
# Circles crossing each viewport edge retain the native midpoint pixels.
box=(20,35,60,75);bounded=Viewport(draw,box)
for method in ('_circle','_fill_circle'):
    for cx,cy in ((20,55),(59,55),(40,35),(40,74)):
        draw.fill_screen(0xffff)
        getattr(draw,method)(cx,cy,11,0x07e0)
        reference=[bytes(draw._read_row(y)[20:60]) for y in range(35,75)]
        draw.fill_screen(0xffff)
        getattr(bounded,method)(cx,cy,11,0x07e0)
        for y in range(320):
            row=draw._read_row(y)
            if 35<=y<75:
                assert bytes(row[20:60])==reference[y-35]
                assert all(v==255 for v in row[:20]) and all(v==255 for v in row[60:])
            else:assert all(v==255 for v in row)
# All remaining preview primitives stay within exclusive panel bounds.
draw.fill_screen(0xffff)
bounded._fill_triangle(-100,-100,400,-100,40,400,0)
bounded._line(-100,0,400,200,0x07e0)
bounded._rectangle(0,0,90,90,0x07e0)
bounded._fill_rectangle(0,0,320,320,0)
bounded._text(-20,40,'Text across the whole viewport',0x07e0,0)
for y in range(320):
    row=draw._read_row(y)
    for x in range(320):
        if not (20<=x<60 and 35<=y<75):assert row[x]==255,(x,y)
print('PASS: panel-only lines, rectangles, text, triangles and native-parity edge circles')
# Back and Del both erase before the cursor, including the middle of a number.
e=LineEdit('1234');e.cursor=2
e.key(vm,k.BUTTON_DELETE);assert e.text=='134' and e.cursor==1
e.key(vm,k.BUTTON_BACKSPACE);assert e.text=='34' and e.cursor==0
print('PASS: engineering input Back/Del both use backspace semantics')
vm.add(View('parent',lambda vm:None,lambda vm:True,lambda vm:None));vm.switch_to('parent')
app._kept=None
app.show(vm);a=app._active

def key(button):
    vm.input_manager._last_button=button;vm.run()

def preview_rect():
    return render.MODEL_PREVIEW if a.page=='model' else render.PREVIEW_RECT

def preview():
    x,y,w,h=preview_rect()
    return [bytes(draw._read_row(yy)[x:x+w]) for yy in range(y,y+h)]

def borders():
    fb=Pixels(draw);expected=colour(a.palette().GRID)
    for x,y,w,h in (preview_rect(),a.properties_rect()):
        assert all(fb.pixel(xx,y)==expected and fb.pixel(xx,y+h-1)==expected for xx in range(x,x+w))
        assert all(fb.pixel(x,yy)==expected and fb.pixel(x+w-1,yy)==expected for yy in range(y,y+h))

key(k.BUTTON_CENTER);assert a.solution is None
assert a.evaluate()
fixture=app.items.copy(a.model)
for accent in (0x07ff,0xf81f,0xffe0):
    vm.selected_color=accent
    for index in (0,7,8):
        a.replace_model(bm.template(index))
        for zoom in range(3):
            a.zoom=zoom;a.draw();borders()
a.replace_model(fixture);a.draw()
# Help is modal and scrollable, retaining selection, values and the fixed footer.
a.draw();before=preview();selected=a.sel;model=a.model
key(k.BUTTON_F9);assert a.help_open and a.sel==selected and a.model is model
assert a.footer_height==12 and a.help_first==0
key(k.BUTTON_DOWN);assert a.help_first==1
key(k.BUTTON_END)
capacity=render.help_capacity(int(draw.size.y)-a.footer_height)
assert a.help_first==len(app.HELP)-capacity
sim_runtime.lcd_screenshot('/private/tmp/gungos-beamlab-help-end.bmp')
key(k.BUTTON_CTRL_UP);assert a.help_first==0
key(k.BUTTON_RIGHT);assert a.help_first==capacity
key(k.BUTTON_LEFT);assert a.help_first==0
key(k.BUTTON_F2);assert a.help_open and a.model is model and a.sel==selected
sim_runtime.lcd_screenshot('/private/tmp/gungos-beamlab-help.bmp')
key(k.BUTTON_F9);assert not a.help_open and preview()==before
# Every section shape stays inside the same preview, with a scrolling editor.
a.open_section(a.model['sections'][0])
for shape in bm.SHAPES:
    bm.set_shape(a.section,shape);a.resolve()
    a.section_row=len(a.section_rows())-1;a.draw();borders()
bm.set_shape(a.section,'Rectangle');a.resolve()
a.section_row=[r[0] for r in a.section_rows()].index('dim:h');a.draw()
key(k.BUTTON_CENTER);assert a.edit is not None
pending=a.edit.text
key(k.BUTTON_F9);assert a.edit is not None and a.edit.text==pending and a.help_open
key(k.BUTTON_DOWN);assert a.edit.text==pending
key(k.BUTTON_ESCAPE);assert not a.help_open and a.edit is not None
key(k.BUTTON_ESCAPE);assert a.edit is None and a.page=='section'
key(k.BUTTON_ESCAPE);assert a.page=='model'
# Plot switching covers INDIVIDUAL beams, even within a single collinear
# run. A joint load deliberately makes their boundary shears different.
model=bm.empty_model(((0,0),(3,0),(6,0)),((0,1),(1,2)))
model['supports']=[bm.support(0,0,'Fixed')]
model['loads']=[bm.point_load(0,3,20000),bm.point_load(1,3,10000)]
a.replace_model(model);assert a.evaluate()
key(k.BUTTON_F4)
assert a.dmember==0 and a.dline==0 and a.plot_bounds()==(0,3)
assert a.plot_title()=='L1/2  x=0 m'
first=a.cache
assert abs(first[0][4]-30000)<1
assert abs(first[1][3]+120000)<1
for record in first:
    assert record[0][0]==render.LEFT and record[0][-1]==render.RIGHT
    assert min(record[0])==render.LEFT and max(record[0])==render.RIGHT
# Boundaries use this beam's side of the joint, not the neighbour's.
samples=a.solution.samples(0,a.view,member=0)
assert samples[0][0]==0 and samples[0][-1]==3
assert abs(samples[1][-1]-30000)<1
key(k.BUTTON_DOWN);assert a.ds==3
key(k.BUTTON_RIGHT);assert a.ds==3
key(k.BUTTON_CENTER)
key(k.BUTTON_F5)
rows=a.result_rows();a.menu_index=next(i for i,r in enumerate(rows) if r[4] and r[4][0]=='pin')
assert 'V 30 kN' in rows[a.menu_index][2] and rows[a.menu_index][0].startswith('B1')
key(k.BUTTON_CENTER);assert a.dmember==0 and a.ds==3
key(vm.input_manager._key_to_button(ord('m')))
assert a.dmember==1 and a.dline==0 and a.ds==3 and a.plot_bounds()==(3,6)
assert a.plot_title()=='L2/2  x=0 m' and a.cache is not first
assert abs(a.cache[0][4]-10000)<1
assert abs(a.cache[1][3]+30000)<1
samples=a.solution.samples(0,a.view,member=1)
assert samples[0][0]==3 and samples[0][-1]==6
assert abs(samples[1][0]-10000)<1
for record in a.cache:assert record[0][0]==render.LEFT and record[0][-1]==render.RIGHT
sim_runtime.lcd_screenshot('/private/tmp/gungos-beamlab-plot-beam2.bmp')
# Peak stepping and cursor movement remain inside the selected beam.
for _ in range(len(a.peak_list())+1):
    key(k.BUTTON_TAB);assert 3<=a.ds<=6
key(k.BUTTON_CENTER);assert (0,a.ds) in a.pins
key(k.BUTTON_F5)
rows=a.result_rows();a.menu_index=next(i for i,r in enumerate(rows) if r[4] and r[4][0]=='pin')
key(k.BUTTON_CENTER)
assert a.page=='diagrams' and a.dmember==1 and 3<=a.ds<=6
key(k.BUTTON_LEFT_BRACKET);assert a.dmember==0 and a.ds==0
key(k.BUTTON_RIGHT_BRACKET);assert a.dmember==1 and a.ds==3
key(k.BUTTON_RIGHT_BRACKET);assert a.dmember==0 and a.ds==0
key(k.BUTTON_LEFT_BRACKET);assert a.dmember==1 and a.ds==3
key(vm.input_manager._key_to_button(ord('f')));assert a.whole
key(k.BUTTON_LEFT_BRACKET);assert a.whole and a.dmember==0
key(k.BUTTON_RIGHT_BRACKET);assert a.whole and a.dmember==1
sim_runtime.lcd_screenshot('/private/tmp/gungos-beamlab-plot-overview.bmp')
key(vm.input_manager._key_to_button(ord('f')));assert not a.whole
key(k.BUTTON_ESCAPE)
a.focus(('member',1))
key(k.BUTTON_F4);assert a.dmember==1 and a.ds==3
# An unloaded secondary beam has no peaks; TAB must stay at its own start.
model['loads']=[]
a.replace_model(model);assert a.evaluate()
a.focus(('member',1));key(k.BUTTON_F4)
key(k.BUTTON_TAB);assert a.ds==3 and a.dmember==1 and a.tab==0
key(k.BUTTON_ESCAPE)
a.replace_model(bm.template(1));assert a.evaluate();key(k.BUTTON_F4)
key(vm.input_manager._key_to_button(ord('m')))
assert a.dmember==0 and a.plot_title().startswith('L1/1')
key(k.BUTTON_ESCAPE)
a.replace_model(fixture);assert a.evaluate()

# Opening help preserves diagram geometry/cache and the fixed footer.
key(k.BUTTON_F4);assert a.page=='diagrams' and a.cache is not None
cache=a.cache
for _ in range(2):
    key(k.BUTTON_F9)
    assert a.cache is cache and a.footer_height==12
    bottom=int(draw.size.y)-a.footer_height-6
    assert render.panel_bounds(2,bottom)[2]<bottom
    for slot,record in enumerate(a.cache):
        top,lo,hi=render.panel_bounds(slot,bottom)
        assert min(record[1])>=lo-1 and max(record[1])<=hi+1
key(k.BUTTON_ESCAPE)
assert a.page=='model'
a.open_section(a.model['sections'][0]);a.draw()
sim_runtime.lcd_screenshot('/private/tmp/gungos-beamlab-ui-section.bmp')
key(k.BUTTON_ESCAPE)
a.replace_model(bm.template(7));a.help_open=False;a.draw()
sim_runtime.lcd_screenshot('/private/tmp/gungos-beamlab-ui-frame.bmp')
a.replace_model(bm.template(0));a.draw()
sim_runtime.lcd_screenshot('/private/tmp/gungos-beamlab-ui-model.bmp')
# Section names follow the member IDs, clear of a straight beam's line.
m=bm.template(0);app.items.split(m,0,3.0)
m['sections'].append(bm.new_section('S2',m['sections'][0]));m['members'][1]['section']=1
a.replace_model(m);a.draw()
view=render.View(a.model,render.MODEL_BOX,1.0,None)
(x0,y),(x1,_)=view.p(*a.model['joints'][0]),view.p(*a.model['joints'][2])
fb=Pixels(draw);row=[fb.pixel(x,y) for x in range(x0+8,x1-7)]
assert row==[row[0]]*len(row) and row[0]!=colour(a.palette().MUTED),row
# The whole-frame outline keeps its quantity's colour for any active member.
a.replace_model(bm.template(7));assert a.evaluate()
key(k.BUTTON_F4);a.inspect_member(0);a.whole=True;a.quantity=0
colours=[];original=render.clip
def spy(draw,x1,y1,x2,y2,color,*rest):
    colours.append(color);original(draw,x1,y1,x2,y2,color,*rest)
render.clip=spy
try:a.draw()
finally:render.clip=original
assert render.COLORS['M'] in colours
a.whole=False;key(k.BUTTON_ESCAPE);assert a.page=='model'
a.replace_model(bm.template(0));a.draw()
a.switch_model_tab(2)
key(k.BUTTON_F1)
sim_runtime.lcd_screenshot('/private/tmp/gungos-beamlab-ui-add.bmp')
key(k.BUTTON_ESCAPE)
key(vm.input_manager._key_to_button(ord('?')));assert a.help_open
key(k.BUTTON_ESCAPE);assert a.page=='model'
key(k.BUTTON_ESCAPE);assert vm.current_view.name=='parent'
print('PASS: panel borders, themes, section shapes, modal help, per-member plots, pins, peaks and overviews')
