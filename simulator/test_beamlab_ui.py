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

def preview():
    x,y,w,h=render.PREVIEW_RECT
    return [bytes(draw._read_row(yy)[x:x+w]) for yy in range(y,y+h)]

def borders():
    fb=Pixels(draw);expected=colour(a.palette().GRID)
    for x,y,w,h in (render.PREVIEW_RECT,a.properties_rect()):
        assert all(fb.pixel(xx,y)==expected and fb.pixel(xx,y+h-1)==expected for xx in range(x,x+w))
        assert all(fb.pixel(x,yy)==expected and fb.pixel(x+w-1,yy)==expected for yy in range(y,y+h))

key(k.BUTTON_F9);assert a.page=='start' and a.help_open
key(k.BUTTON_F9);assert not a.help_open
key(k.BUTTON_CENTER);assert a.page=='model' and a.solution is not None
# F3 opens Options; ESC returns to the model.
key(k.BUTTON_F3);assert a.page=='options'
key(k.BUTTON_ESCAPE);assert a.page=='model'
# Add Member attaches to the visible cursor, at either endpoint. Exercise
# the actual F1 menu on the float32 simulator: the far-end comparison used
# to reject the exact tip as though it were an interior split.
for position in (0,3):
    a.replace_model(bm.template(1))
    if position:key(vm.input_manager._key_to_button(ord('.')))
    assert a.s==position
    key(k.BUTTON_F1);key(k.BUTTON_CENTER)
    assert a.popup is None and len(a.model['members'])==2 and a.problem is None
    member=a.model['members'][1]
    assert tuple(a.model['joints'][member['a']])==(position,0)
    assert tuple(a.model['joints'][member['b']])==(position,3)
    assert len(a.model['joints'])==3, 'Attachment must reuse the existing joint'
    if position:
        # Turn the new vertical member into a horizontal extension by typing
        # its angle, without moving the original member or attachment joint.
        a.focus(('member',1),'angle')
        key(k.BUTTON_0);key(k.BUTTON_CENTER)
        assert tuple(a.model['joints'][member['a']])==(3,0)
        assert tuple(a.model['joints'][member['b']])==(6,0)
        assert a.problem is None
        key(vm.input_manager._key_to_button(ord('z')))
    key(vm.input_manager._key_to_button(ord('z')))
    assert len(a.model['members'])==1 and len(a.model['joints'])==2
    assert a.model['supports'][0]['kind']=='Fixed' and a.problem is None
# Endpoint classification also applies to free-end hinges, and a refused
# addition must retain all 12 undo entries rather than dropping the oldest.
a.select_point(0,3)
for _ in range(app.UNDO_LIMIT):a.snapshot()
undo=a.undo[:]
key(k.BUTTON_F1);key(k.BUTTON_DOWN);key(k.BUTTON_DOWN);key(k.BUTTON_CENTER)
assert a.error and not a.model['hinges'] and a.undo==undo
# Check endpoints over a range of lengths independently of solver scaling.
for length in (0.25,3,6,10000):
    model=bm.template(1);model['joints'][1][0]=length
    new=app.items.add_member(model,0,length)
    assert model['members'][new]['a']==1 and len(model['members'])==2
    assert tuple(model['joints'][1])==(length,0)
a.replace_model(bm.template(0))
# Left/Right cycle whole-model tabs; Up/Down follows items across positions.
assert a.model_tab==0 and a.sel[0]==('member',0)
solution=a.solution
key(k.BUTTON_RIGHT)
assert a.model_tab==1 and len(a.tab_refs())==2 and a.s==0
assert len([row for row in a.rows() if row[0]=='head'])==2
key(k.BUTTON_DOWN)
assert a.sel[0][1] is a.model['supports'][1] and a.s==6
remembered=a.sel
key(k.BUTTON_RIGHT)
assert a.model_tab==2 and len(a.tab_refs())==1 and a.sel[0][0]=='load'
key(k.BUTTON_RIGHT)
assert a.model_tab==0 and a.sel[0]==('member',0)
key(k.BUTTON_LEFT);key(k.BUTTON_LEFT)
assert a.model_tab==1 and a.sel==remembered and a.s==6
assert a.solution is solution, 'Browsing should not solve or mutate the model'
key(k.BUTTON_LEFT)
assert a.model_tab==0
key(k.BUTTON_CENTER)
assert a.sel[1]=='length' and a.current()[0]=='field'
key(k.BUTTON_ESCAPE)
assert a.page=='model' and a.sel[1] is None and len(a.rows())==1
# Empty tabs remain navigable; no support/load is invented or selected.
empty=bm.template(9);empty['supports']=[]
a.replace_model(empty);a.draw()
key(k.BUTTON_RIGHT);assert a.model_tab==1 and not a.rows() and a.sel is None
key(k.BUTTON_DOWN);assert a.sel is None
key(k.BUTTON_RIGHT);assert a.model_tab==2 and not a.rows() and a.sel is None
key(k.BUTTON_LEFT);key(k.BUTTON_LEFT)
assert a.model_tab==0 and a.sel[0][0]=='member'
for accent in (0x07ff,0xf81f,0xffe0):
    vm.selected_color=accent
    for index in (0,7,8):
        a.replace_model(bm.template(index));a.draw()
        for zoom in range(3):
            a.zoom=zoom;a.draw();borders()
            assert any(any(v for v in draw._read_row(y)) for y in range(18)), 'PicoLAB breadcrumb missing'
a.replace_model(bm.template(0));a.draw()
# F1 contains only additions for the selected tab and cancel changes nothing.
expected=(('Member','Section change','Hinge'),bm.SUPPORTS,
          ('Point load','Moment','Distributed load'))
solution=a.solution;undo_count=len(a.undo)
for tab,labels in enumerate(expected):
    assert a.model_tab==tab
    before=preview()
    key(k.BUTTON_F1)
    assert a.popup is not None and tuple(a.popup[1])==tuple(labels) and preview()==before
    key(k.BUTTON_ESCAPE)
    assert a.popup is None and len(a.undo)==undo_count and a.solution is solution
    if tab<2:key(k.BUTTON_RIGHT)
before=preview()
key(k.BUTTON_F1);assert a.popup is not None and preview()==before
key(k.BUTTON_DOWN);assert preview()==before
key(k.BUTTON_UP);key(k.BUTTON_CENTER)
assert a.popup is None and len(a.model['loads'])==2 and a.sel[0][1]['kind']=='point'
assert a.model_tab==2, 'Adding a point load should select Loads'
key(k.BUTTON_CENTER)
assert a.edit is not None
pending=a.edit.text;caret=a.edit.cursor
key(k.BUTTON_LEFT)
assert a.model_tab==2 and a.edit.text==pending and a.edit.cursor==max(0,caret-1)
key(k.BUTTON_RIGHT)
assert a.model_tab==2 and a.edit.cursor==caret
key(k.BUTTON_ESCAPE)
# Editing a load's position keeps both it and distant loads in the same tab.
key(k.BUTTON_2);key(k.BUTTON_CENTER)
assert a.s==2 and a.sel[0][1]['x']==2
selected_load=a.sel
key(k.BUTTON_LEFT);assert a.model_tab==1
key(k.BUTTON_RIGHT);assert a.model_tab==2 and a.sel==selected_load and a.s==2
assert len(a.tab_refs())==2
key(vm.input_manager._key_to_button(ord(',')));assert a.s==0 and a.model_tab==2
key(vm.input_manager._key_to_button(ord('.')));assert a.s==2 and a.model_tab==2

fixture=app.items.copy(a.model)
# F2 removes the selected item even while its properties are selected;
# it must never remove the object while a value is actively being typed.
a.focus(selected_load[0],selected_load[1])
assert a.sel[1] is not None
count=len(a.model['loads'])
key(k.BUTTON_CENTER);assert a.edit is not None
key(k.BUTTON_F2);assert a.edit is not None and len(a.model['loads'])==count
key(k.BUTTON_ESCAPE)
key(k.BUTTON_F2)
assert len(a.model['loads'])==count-1 and a.page=='model'
key(vm.input_manager._key_to_button(ord('z')))
assert len(a.model['loads'])==count and a.problem is None
# Protected final member and empty tabs report errors without losing undo.
a.replace_model(bm.template(0));undo_count=len(a.undo)
key(k.BUTTON_F2)
assert len(a.model['members'])==1 and len(a.undo)==undo_count and a.error
empty=bm.template(9);empty['supports']=[]
a.replace_model(empty);key(k.BUTTON_RIGHT)
key(k.BUTTON_F2)
assert not a.model['supports'] and a.error
# Restore the fixture for support addition checks.
a.replace_model(fixture);key(k.BUTTON_RIGHT);key(k.BUTTON_RIGHT)

# Each support type is applied as part of one undoable addition.
key(k.BUTTON_LEFT)
for index,kind in enumerate(bm.SUPPORTS):
    a.select_point(0,2)
    before_count=len(a.model['supports']);before_undo=len(a.undo)
    key(k.BUTTON_F1)
    for _ in range(index):key(k.BUTTON_DOWN)
    key(k.BUTTON_CENTER)
    assert a.popup is None and a.model_tab==1
    assert len(a.model['supports'])==before_count+1 and a.sel[0][1]['kind']==kind
    assert a.sel[0][1]['x']==2 and len(a.undo)==min(before_undo+1,app.UNDO_LIMIT)
    key(vm.input_manager._key_to_button(ord('z')))
    assert len(a.model['supports'])==before_count and a.problem is None
key(k.BUTTON_RIGHT)

# Full Beam 2 -> end -> Supports -> Add workflow, including help over Add.
model=bm.template(1)
app.items.add_member(model,0,3)
a.replace_model(model)
solution=a.solution
key(k.BUTTON_TAB)
assert a.cursor_member()==1 and a.model_tab==0 and a.sel==( ('member',1),None )
assert a.cursor_label()=='B2 Start'
key(k.BUTTON_PERIOD)
assert a.cursor_label()=='B2 End'
point=app.items.cursor_point(a.model,a.line,a.s)
assert tuple(point)==(3,3)
position=(a.line,a.s,a.member)
key(k.BUTTON_RIGHT)
assert a.model_tab==1 and (a.line,a.s,a.member)==position and a.solution is solution
key(k.BUTTON_F1)
assert 'B2 End' in a.popup[0]
popup=a.popup
key(k.BUTTON_F9);assert a.help_open and a.popup is popup
key(k.BUTTON_DOWN);key(k.BUTTON_F2)
assert a.help_open and a.popup[2]==0 and len(a.model['supports'])==1
key(k.BUTTON_ESCAPE)
assert not a.help_open and a.popup is popup
key(k.BUTTON_DOWN);key(k.BUTTON_CENTER)  # Roller
support=a.model['supports'][-1]
assert support['m']==1 and support['x']==3 and support['kind']=='Roller'
assert tuple(bm.point(a.model,support['m'],support['x']))==point and a.problem is None
key(vm.input_manager._key_to_button(ord('z')))
assert len(a.model['supports'])==1 and a.problem is None
# Individual beam cycling also works within ONE collinear run, without
# losing which side of a shared joint receives newly inserted items.
model=bm.template(1)
app.items.add_member(model,0,3)
model['joints'][2]=[6,0]
a.replace_model(model)
assert len(bm.lines(a.model))==1
key(k.BUTTON_TAB);assert a.cursor_member()==1 and a.s==3
key(k.BUTTON_PERIOD);assert a.s==6 and a.cursor_label()=='B2 End'
key(k.BUTTON_PERIOD);assert a.s==6 and a.cursor_member()==1
key(k.BUTTON_COMMA);assert a.s==3 and a.cursor_member()==1
key(k.BUTTON_COMMA);assert a.s==3 and a.cursor_member()==1
key(k.BUTTON_LEFT_BRACKET);assert a.cursor_member()==0 and a.s==0
key(k.BUTTON_RIGHT_BRACKET);assert a.cursor_member()==1 and a.s==3
key(k.BUTTON_RIGHT)
assert a.model_tab==1 and a.cursor_label()=='B2 Start'
key(k.BUTTON_F1);key(k.BUTTON_DOWN);key(k.BUTTON_CENTER)
support=a.model['supports'][-1]
assert support['m']==1 and support['x']==0 and a.problem is None
assert a.model['members'][0]['b']==a.model['members'][1]['a']
assert len(a.model['joints'])==3, 'A shared node must not be duplicated'
# Comma/period stay within Beam 1 too, while Tab cycles regardless of tab.
key(k.BUTTON_TAB);assert a.model_tab==1 and a.cursor_member()==0 and a.s==0
key(k.BUTTON_PERIOD);assert a.s==3 and a.cursor_member()==0
key(k.BUTTON_PERIOD);assert a.s==3 and a.cursor_member()==0
key(k.BUTTON_RIGHT);key(k.BUTTON_RIGHT)
assert a.model_tab==0 and a.s==3 and a.cursor_member()==0
# Restore the section/edit fixture for the remaining checks.
a.replace_model(fixture)

# Angle is directly editable on a point force. Presets remain compatible;
# choosing Custom initially keeps the previous direction, and Back/undo,
# help, case save/load and the drawn arrow all use that same angle.
a.replace_model(bm.template(1))
load=a.model['loads'][0];ref=('load',load)
assert app.items.get(a.model,ref,'angle')==270
assert len(app.items.choices(a.model,ref,'dir'))==4
app.items.set_choice(a.model,ref,'dir',3)
assert load['dir']=='angle' and load['angle']==270
app.items.set_choice(a.model,ref,'dir',0)
a.focus(ref,'angle')
key(k.BUTTON_CENTER)
for _ in range(len(a.edit.text)):key(k.BUTTON_BACKSPACE)
key(vm.input_manager._key_to_button(ord('-')))
key(k.BUTTON_4);key(k.BUTTON_5)
assert a.edit.text=='-45'
key(k.BUTTON_F9);key(k.BUTTON_DOWN);key(k.BUTTON_ESCAPE)
assert not a.help_open and a.edit.text=='-45'
key(k.BUTTON_CENTER)
assert load['angle']==315 and load['dir']=='angle' and a.problem is None
assert app.items.get(a.model,ref,'angle')==315
ux,uy=render.screen_direction(a.model,load)
assert abs(ux-0.70710678)<1e-5 and abs(uy-0.70710678)<1e-5
assert '315' in app.items.title(a.model,ref)
sim_runtime.lcd_screenshot('/private/tmp/gungos-beamlab-point-angle.bmp')
from engtools import cases
path=cases.save_case(vm.storage,'angle-ui-check',a.model)
loaded=cases.load_case(vm.storage,'angle-ui-check','beams')
assert loaded['loads'][0]['angle']==315 and loaded['loads'][0]['dir']=='angle'
bm.check(loaded)
vm.storage.remove(path)
key(vm.input_manager._key_to_button(ord('z')))
assert a.model['loads'][0]['dir']=='down' and app.items.get(a.model,('load',a.model['loads'][0]),'angle')==270
# Directly editing a preset's Angle switches to Custom; changing geometry
# leaves that global direction fixed. Normal mode follows the member.
load=a.model['loads'][0];ref=('load',load)
app.items.set_choice(a.model,ref,'dir',1)
assert app.items.get(a.model,ref,'angle')==270
bm.set_member(a.model,0,3,90)
assert abs(app.items.get(a.model,ref,'angle'))<1e-4
app.items.set_choice(a.model,ref,'dir',3)
bm.set_member(a.model,0,3,30)
assert abs(app.items.get(a.model,ref,'angle'))<1e-4
# Invalid numeric angles must not mutate the original data.
before=app.items.copy(load)
try:app.items.set_number(a.model,ref,'angle','deg',float('nan'))
except ValueError:pass
else:raise AssertionError('Non-finite angle accepted')
assert load==before
distributed=bm.template(0)
assert len(app.items.choices(distributed,('load',distributed['loads'][0]),'dir'))==3
a.replace_model(fixture)

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
a.replace_model(model)
key(k.BUTTON_F4)
assert a.dmember==0 and a.dline==0 and a.plot_bounds()==(0,3)
assert a.plot_title()=='B1/2  x=0 m'
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
assert a.plot_title()=='B2/2  x=0 m' and a.cache is not first
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
a.replace_model(model)
a.focus(('member',1));key(k.BUTTON_F4)
key(k.BUTTON_TAB);assert a.ds==3 and a.dmember==1 and a.tab==0
key(k.BUTTON_ESCAPE)
a.replace_model(bm.template(1));key(k.BUTTON_F4)
key(vm.input_manager._key_to_button(ord('m')))
assert a.dmember==0 and a.plot_title().startswith('B1/1')
key(k.BUTTON_ESCAPE)
a.replace_model(fixture)

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
key(k.BUTTON_F1)
sim_runtime.lcd_screenshot('/private/tmp/gungos-beamlab-ui-add.bmp')
key(k.BUTTON_ESCAPE)
key(vm.input_manager._key_to_button(ord('?')));assert a.help_open
key(k.BUTTON_ESCAPE);assert a.page=='model'
key(k.BUTTON_ESCAPE);assert vm.current_view.name=='parent'
print('PASS: stable panel borders across themes, beams/frames, 1x/2x/4x zoom and all section shapes')
print('PASS: F1 Add below preview, F3 Options, F9 modal help/edit preservation and fixed diagram area')
print('PASS: whole-model tabs, selection memory, preview following, empty tabs, edit caret and insertion cursor')
print('PASS: contextual Add menus, non-mutating cancel and all six support types with one-step undo')
print('PASS: float32 beam start/tip attachment, angle editing, shared joints, undo and free-end hinge rejection')

print('PASS: Beam 2 endpoint support placement, shared collinear joints, per-beam point limits, reverse cycling and help over Add')

print('PASS: editable point-force angle, preset conversion, modulo wrapping, drawn vector, help/undo, save round trip and global-axis persistence')

print('PASS: individual-beam plots, indicator, collinear boundary jumps, per-beam scaling/peaks, wrapping, pins, overview selection and unloaded beams')
