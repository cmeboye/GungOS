"""Quick XY charts: bounded ranges, gaps, UI lifecycle and shared-view isolation."""
import os,sys,json
from time import ticks_ms
root=os.getcwd()
for relative in ('src/MicroPython','simulator/hardware','builds/MicroPython/apps_unfrozen'):
    sys.path.insert(0,root+'/'+relative)
from desktopapps.eggcel.model import Sheet
from desktopapps.eggcel.charts import defaults,parse_range,build_spec


class Colors:
    foreground_color=0xFFFF
    background_color=0
    selected_color=0xFD20


sheet=Sheet()
sheet.apply({(0,0):'Time',(0,1):'Sensor A',(0,2):'Sensor B',(0,3):'Sensor C',
             (1,0):'0',(2,0):'1',(3,0):'2',(4,0):'3',
             (1,1):'10',(2,1):'=B2+2',(3,1):'=1/0',(4,1):'16',
             (1,2):'9',(2,2):'text',(3,2):'13',(4,2):'15',
             (1,3):'8',(2,3):'10',(3,3):'12',(4,3):'14'})
options=defaults(sheet,(0,0,4,3))
assert options=={'style':'line','x':'A1:A5','ys':['B1:B5','C1:C5','D1:D5'],'header':True}
assert parse_range(' $a$2 : A5 ')==(1,0,4)
before=sheet.document()
spec=build_spec(sheet,options,Colors())
assert len(spec['series'])==3 and spec['series'][0]['points']==[(0,10),(1,12),(None,None),(3,16)]
assert spec['series'][1]['points'][1]==(None,None) and spec['note'].startswith('2 gaps')
assert spec['axes']['x']['label']=='Time' and [s['name'] for s in spec['series']]==['Sensor A','Sensor B','Sensor C']
assert len(set(s['color'] for s in spec['series']))==3
assert len(set(s['marker'] for s in spec['series']))==3
assert sheet.document()==before and sheet.dirty
single=defaults(sheet,(0,3,4,3))
single_spec=build_spec(sheet,single,Colors())
assert single['x']=='' and single_spec['series'][0]['points'][0]==(2,8)
assert single_spec['axes']['x']['label']=='Worksheet row'
for bad in ('A5:A1','A1:B2','A0:A2','A1:A201','A1:','A1:A2:A3'):
    try:parse_range(bad)
    except ValueError:pass
    else:raise AssertionError('Invalid plot range accepted: '+bad)
for changes in ({'x':'A1:A4'},{'ys':['','','']},
                {'x':'A1','ys':['B1','',''],'header':True}):
    candidate=dict(options);candidate.update(changes)
    try:build_spec(sheet,candidate,Colors())
    except ValueError:pass
    else:raise AssertionError('Invalid/empty chart accepted: '+str(candidate))
sheet.apply({(2,0):''})
assert build_spec(sheet,options,Colors())['series'][0]['points'][1]==(None,None)
sheet.apply({(2,0):'1'})
# Multiple nonadjacent Y columns and a one-point chart are supported.
nonadjacent={'style':'scatter','x':'A2:A5','ys':['B2:B5','D2:D5',''],'header':False}
assert len(build_spec(sheet,nonadjacent,Colors())['series'])==2
assert len(build_spec(sheet,{'style':'line','x':'','ys':['D2','',''],'header':False},Colors())['series'][0]['points'])==1
print('PASS: ranges, inferred headers, numeric/formula data, gaps, styles and validation')

import sim_runtime
sim_runtime.configure(root,'/private/tmp/eggcel-plots-'+str(ticks_ms()),root+'/builds/MicroPython/apps_unfrozen',
                      1,'picocalc-pico2w',0,True,False,False,False,'',_network_mode='offline',_audio_mode='silent')
from picoware.system.view_manager import ViewManager
from picoware.system.view import View
from picoware.system.input import Input
from picoware.system import buttons as k
from desktopapps.eggcel import app
from engtools.plots import plot2d
from engtools.ui import theme
Input.button=property(lambda self:self._last_button)
vm=ViewManager()
vm.add(View('parent',lambda vm:None,lambda vm:True,lambda vm:None));vm.switch_to('parent')
app.show(vm);ui=app._active
ui.sheet=sheet;ui.row,ui.col,ui.top,ui.left=4,3,0,0;ui.anchor=(0,0)
ui.filename='unsaved-test.egg';ui.clipboard=sheet.copied((1,1,2,1))
captured=[];real_open=__import__('engtools.plots.view',None,None,('open_view',)).open_view
from engtools.plots import view
def capture(vm,name,owner):
    captured[:]=[owner];return real_open(vm,name,owner)
view.open_view=capture
baseline=json.dumps({'version':1,'expressions':[['sin(x)',True]],'bounds':[-2,2,-2,2]})
vm.storage.mkdir('picoware/settings/graph')
assert vm.storage.write(plot2d.SAVE_PATH,baseline)
def key(button):
    vm.input_manager._last_button=button;vm.run()
    if app._active is not None and app._active.job_kind=='Chart':
        for _ in range(200):
            vm.input_manager._last_button=k.BUTTON_NONE;vm.run()
            if app._active is None or app._active.job is None:break
def text(value):
    for char in value:key(vm.input_manager._key_to_button(ord(char)))
def finish():
    for _ in range(2000):
        key(k.BUTTON_NONE)
        chart=captured[0].app
        if chart.completed and chart.job is None and chart.refine is None:return chart
    raise AssertionError('Chart did not finish')

key(k.BUTTON_F6)
assert ui.page=='plot_setup' and ui.selected==6
vm.draw.screenshot('/private/tmp/eggcel-plot-setup.bmp')
# Editing/cancelling a range keeps both the sheet and original settings.
key(k.BUTTON_UP);key(k.BUTTON_UP);key(k.BUTTON_CENTER)
assert ui.purpose=='plot_y2'
key(k.BUTTON_F7);text('D5:D1');key(k.BUTTON_CENTER)
assert ui.page=='dialog' and ui.error
key(vm.input_manager._key_esc)
assert ui.page=='plot_setup' and ui.plot_options['ys'][2]=='D1:D5'
ui.selected=6
state=(ui.sheet,ui.sheet.document(),ui.sheet.dirty,ui.position,ui.top,ui.left,ui.anchor,ui.filename,ui.clipboard)
count=vm._view_count
key(k.BUTTON_CENTER)
for _ in range(100):
    if vm.current_view.name=='eng_plot2d':break
    key(k.BUTTON_NONE)
assert vm.current_view.name=='eng_plot2d' and ui.suspended and ui.sheet is state[0]
chart=finish()
assert chart.data_only and not chart.persistent and chart.palette.BG==vm.background_color
assert chart.palette.ACCENT==vm.selected_color and theme.BG==0x0841
vm.draw.screenshot('/private/tmp/eggcel-plot-lines.bmp')
original_bounds=chart.bounds[:]
for _ in range(12):key(k.BUTTON_RIGHT)
chart.refine=None;chart.dirty=True;finish()
assert chart.bounds[0]>original_bounds[1]
key(k.BUTTON_F);finish()
assert all(abs(a-b)<1e-5 for a,b in zip(chart.bounds,original_bounds)),(chart.bounds,original_bounds)
key(k.BUTTON_PLUS);assert chart.bounds[1]-chart.bounds[0]<original_bounds[1]-original_bounds[0]
chart.refine=None;chart.dirty=True;finish()
key(k.BUTTON_CENTER);assert chart.state=='expressions'
key(k.BUTTON_SPACE);assert not chart.items[0].visible
key(k.BUTTON_SPACE);key(vm.input_manager._key_esc);finish()
key(k.BUTTON_F9);assert chart.state=='help'
key(vm.input_manager._key_esc);finish()
key(vm.input_manager._key_esc)
assert vm.current_view.name=='eggcel' and vm._view_count==count
assert not ui.suspended and app._active is ui
assert (ui.sheet,ui.sheet.document(),ui.sheet.dirty,ui.position,ui.top,ui.left,ui.anchor,ui.filename,ui.clipboard)==state
assert vm.storage.read(plot2d.SAVE_PATH)==baseline
assert captured[0].app is None and captured[0].spec is None
vm.draw.screenshot('/private/tmp/eggcel-plot-return.bmp')
# Reopening the same marked selection keeps manually chosen chart settings.
ui.plot_options['style']='scatter'
key(k.BUTTON_F6);assert ui.plot_options['style']=='scatter'
key(vm.input_manager._key_esc)
# Reopening after an edit recomputes fresh points, then render in the light theme.
ui.anchor=None;ui.sheet.apply({(1,1):'42'})
vm.background_color,vm.foreground_color,vm.selected_color=0xFFFF,0,0xB300
key(k.BUTTON_F6);ui.plot_options['style']='scatter';key(k.BUTTON_CENTER)
chart=finish();assert chart.items[0].points[0]==(0,42)
assert chart.palette.BG==0xFFFF and chart.palette.TEXT==0
vm.draw.screenshot('/private/tmp/eggcel-plot-scatter-light.bmp')
key(vm.input_manager._key_esc)
# Failed setup leaves the sheet active and all unsaved data retained.
key(k.BUTTON_F6);ui.plot_options['x']='A1:A3';key(k.BUTTON_CENTER)
assert vm.current_view.name=='eggcel' and ui.error and not ui.suspended and ui.sheet.dirty
key(vm.input_manager._key_esc)
# Standalone entry must also survive stop/start callbacks around a child plot.
import Eggcel
vm.add(View('eggcel_standalone',Eggcel.run,Eggcel.start,Eggcel.stop))
vm.switch_to('eggcel_standalone')
standalone=Eggcel._owner;standalone.sheet=sheet
standalone.anchor=(0,0);standalone.row,standalone.col=4,3
key(k.BUTTON_F6);key(k.BUTTON_CENTER);finish()
assert Eggcel._owner is standalone and standalone.suspended
key(vm.input_manager._key_esc)
assert Eggcel._owner is standalone and standalone.sheet is sheet and not standalone.suspended
# Home can remove a suspended parent without leaking its sheet/entry owner.
key(k.BUTTON_F6);key(k.BUTTON_CENTER);finish();key(k.BUTTON_HOME)
assert Eggcel._owner is None and standalone.sheet is None
assert ui.sheet is None and app._active is None
print('PASS: plot setup/editing, pan/zoom/fit, themes, untouched files, resume and Home/standalone cleanup')
