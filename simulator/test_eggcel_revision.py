"""Eggcel revision: deep evaluation, fills, value snapshots, charts and recovery."""
import os,sys,json,gc
from time import ticks_ms
root=os.getcwd()
for relative in ('src/MicroPython','simulator/hardware','builds/MicroPython/apps_unfrozen'):sys.path.insert(0,root+'/'+relative)
from desktopapps.eggcel.model import Sheet,read_sheet,DIRECTORY
from desktopapps.eggcel.formulas import CellError,Parser,Evaluation,address
from desktopapps.eggcel.charts import build_spec

def value(expression,expected):
 s=Sheet();s.apply({(0,0):'='+expression});actual=s.value((0,0))
 assert actual==expected,(expression,actual,expected)
for expression,expected in (('-2^2',4),('2^3^2',64),('-(2+3)*4',-20),('2^-2',.25),
 ('SUM(1,2,3)',6),('SUM()',0),('ROUND(-1.25,1)',-1.3),('IF(TRUE,7,1/0)',7),
 ('IF(FALSE,1/0,8)',8),('IF(FALSE,1)',False),('MIN(4,2,3)',2),('50%*4',2),
 ('COUNT(1,"x",TRUE)',2),('"a"&"b"','ab'),('SUM(1,SUM(2,3),4)',10)):
 value(expression,expected)
for expression in ('SUM(,1)','SUM(1,)','(1,2)','1 2','1+','()','SUM((1)','SUM(1))'):
 s=Sheet();s.apply({(0,0):'='+expression});assert isinstance(s.value((0,0)),CellError),expression
s=Sheet();changes={(0,0):'1'}
for i in range(1,512):changes[(i%200,i//200)]='='+address((i-1)%200,(i-1)//200)+'+1'
s.apply(changes);assert s.value((111,2))==512
s.cache={};engine=Evaluation(s);job=engine.job((111,2));assert next(job)>0;job.close()
assert s.value((111,2))==512
s=Sheet();s.apply({(0,0):'=IF(TRUE,1,A1)',(0,1):'=IF(FALSE,B1,2)',(0,2):'=D1',(0,3):'=C1'})
assert s.value((0,0))==1 and s.value((0,1))==2 and s.value((0,2)).code=='#CYCLE!'
s=Sheet();s.apply({(0,0):'1',(1,0):'=A1+1',(0,1):'=A1+1'})
s.fill((1,0,199,0));s.cache={};assert s.value((199,0))==200
s.fill((0,1,0,25));assert s.value((0,25))==26
s.apply({(1,1):'=$A1+A$1+$A$1'})
s.fill((1,1,2,2),'down');assert s.cells[(2,1)]=='=$A2+A$1+$A$1'
before=s.document()
try:s.fill((0,0,199,25))
except ValueError:pass
else:raise AssertionError('Oversized fill accepted')
assert s.document()==before
s=Sheet();s.apply({(0,0):'1',(1,0):'=A1+1'});s.fill((1,0,199,0));original=dict(s.cells)
job=s.convert_job((1,0,199,0));next(job);job.close();assert s.cells==original
for _ in s.convert_job((1,0,199,0)):pass
assert all(not raw.startswith('=') for raw in s.cells.values()) and s.value((199,0))==200
assert s.restore() and s.cells==original
s.apply({(0,1):'=1/0'});before=dict(s.cells)
try:
 for _ in s.convert_job((0,0,199,1)):pass
except ValueError:pass
else:raise AssertionError('Partially invalid conversion accepted')
assert s.cells==before
s=Sheet();s.apply({(0,0):'=1/7',(0,1):'=TRUE',(0,2):'="001"',(0,3):'=IF(FALSE,1)'})
expected=s.value((0,0))
for _ in s.convert_job((0,0,0,3)):pass
assert s.value((0,0))==expected and s.value((0,1)) is True and s.value((0,2))=='001' and s.value((0,3)) is False
s.mark_saved();assert s.restore() and s.dirty
assert Sheet.from_document(s.document()).undo is None
print('PASS: iterative parsing/lazy IF, 512-cell cold chains/cycles, fills, atomic conversion/precision and undo')

import sim_runtime
sim_runtime.configure(root,'/private/tmp/eggcel-next-test-'+str(ticks_ms()),root+'/builds/MicroPython/apps_unfrozen',1,'picocalc-pico2w',0,True,False,False,False,'',_network_mode='offline',_audio_mode='silent')
from picoware.system.view_manager import ViewManager
from picoware.system.view import View
from picoware.system.input import Input
from picoware.system import buttons as k
from desktopapps.eggcel import app
Input.button=property(lambda self:self._last_button)
vm=ViewManager();vm.selected_color=0x07E0
vm.add(View('parent',lambda vm:None,lambda vm:True,lambda vm:None));vm.switch_to('parent')
shots=[];native_capture=vm.draw.screenshot
def capture(path):shots.append(path);return native_capture(path)
vm.draw.screenshot=capture
app.show(vm);ui=app._active

def key(button):vm.input_manager._last_button=button;vm.run()
def text(value):
 for char in value:key(vm.input_manager._key_to_button(ord(char)))
def finish():
 for _ in range(3000):
  if ui.job is None:return
  key(k.BUTTON_NONE)
 raise AssertionError('Job did not finish')
def go(target):key(k.BUTTON_F7);text(target);key(k.BUTTON_CENTER)
key(k.BUTTON_F1);assert ui.page=='file' and 'screenshot.bmp' not in shots
key(k.BUTTON_ESCAPE)
key(k.BUTTON_ALT_S);assert shots==['screenshot.bmp'] and ui.page=='grid' and vm.button==-1
shots.clear()
text('1');key(k.BUTTON_CENTER);key(k.BUTTON_DOWN);text('=A1+1');key(k.BUTTON_CENTER)
key(k.BUTTON_F3);go('A200');assert ui.bounds==(1,0,199,0) and ui.anchor==(1,0)
key(k.BUTTON_F2);assert ui.page=='actions';key(k.BUTTON_CENTER);finish()
assert ui.sheet.value((199,0))==200 and ui.anchor==(1,0)
key(k.BUTTON_F4);assert ui.clipboard is not None
# Go uses the original anchor, handles backwards selections and cancellation.
go('B2');key(k.BUTTON_F3);go('D10');assert ui.bounds==(1,1,9,3)
bounds=ui.bounds;key(k.BUTTON_F7);text('bad');key(k.BUTTON_CENTER);assert ui.error and ui.bounds==bounds
key(k.BUTTON_ESCAPE);assert ui.bounds==bounds
key(k.BUTTON_F7);text('A1');key(k.BUTTON_ESCAPE);assert ui.bounds==bounds
key(k.BUTTON_F3);go('A2');key(k.BUTTON_F3);go('A200')
key(k.BUTTON_F2);ui.selected=3;key(k.BUTTON_CENTER);assert ui.page=='convert_confirm' and ui.selected==1
key(k.BUTTON_UP);key(k.BUTTON_CENTER);assert ui.job_kind=='Converting';finish()
assert ui.sheet.cells[(199,0)]=='200'
ui.sheet.restore();ui.calc_paused=False;ui.sheet.cache={};ui.safe_draw();finish()
assert ui.sheet.value((199,0))==200
vm.draw.screenshot('/private/tmp/eggcel-next-sequence.bmp')
# F5 pastes text and never silently clears a populated entry.
ui.anchor=None;go('B1');text('abc');key(k.BUTTON_F4);key(k.BUTTON_F5)
assert ui.buffer=='abcabc';key(k.BUTTON_ESCAPE)
# Build categorical charts and retain the exact workbook through managed views.
ui.sheet=Sheet();ui.sheet.apply({(0,0):'Part',(0,1):'Value',(0,2):'Other',
 (1,0):'Steel',(2,0):'Copper',(3,0):'Aluminium',(4,0):'Glass',
 (1,1):'12',(2,1):'8',(3,1):'16',(4,1):'4',
 (1,2):'-4',(2,2):'6',(3,2):'10',(4,2):'2'})
ui.row,ui.col,ui.top,ui.left=0,0,0,0;ui.anchor=(4,2);ui.error='';ui.calc_paused=False
ui.open_plot_setup();ui.plot_options['style']='column';ui.safe_draw()
vm.draw.screenshot('/private/tmp/eggcel-next-chart-setup.bmp')
spec=build_spec(ui.sheet,ui.plot_options,vm);assert spec['bounds']==(-4.,16.)
state=(ui.sheet,ui.sheet.document(),ui.position,ui.anchor,ui.filename,ui.sheet.dirty)
ui.open_plot();finish();assert vm.current_view.name=='eggcel_chart' and ui.suspended and vm.draw.screenshot is capture
vm.draw.screenshot('/private/tmp/eggcel-next-columns.bmp')
key(k.BUTTON_RIGHT);key(k.BUTTON_DOWN);key(k.BUTTON_PLUS);key(k.BUTTON_ESCAPE)
assert vm.current_view.name=='eggcel' and (ui.sheet,ui.sheet.document(),ui.position,ui.anchor,ui.filename,ui.sheet.dirty)==state
ui.plot_options['style']='pie';ui.open_plot();finish();assert vm.current_view.name=='eggcel_chart'
vm.draw.screenshot('/private/tmp/eggcel-next-pie.bmp')
key(k.BUTTON_RIGHT);key(k.BUTTON_F9);key(k.BUTTON_ESCAPE)
# Pie constraints and column gaps.
ui.sheet.apply({(1,1):'-1'})
try:build_spec(ui.sheet,ui.plot_options,vm)
except ValueError:pass
else:raise AssertionError('Negative pie slice accepted')
ui.plot_options['style']='column';ui.sheet.apply({(1,1):'text'})
assert build_spec(ui.sheet,ui.plot_options,vm)['series'][0]['values'][0] is None
# Explicit direction for rectangular fills; categorical labels are not headers.
ui.sheet=Sheet();ui.sheet.apply({(0,0):'Steel',(0,1):'3',(1,0):'Copper',(1,1):'4'})
ui.row,ui.col=1,1;ui.anchor=(0,0);ui.page='actions';ui.selected=0
key(k.BUTTON_CENTER);assert ui.page=='fill_direction'
key(k.BUTTON_ESCAPE)
ui.open_plot_setup();ui.plot_options['style']='scatter';ui.cycle_plot_type(1)
assert ui.plot_options['style']=='column' and not ui.plot_options['header']
assert len(build_spec(ui.sheet,ui.plot_options,vm)['labels'])==2
ui.cycle_plot_type(-1);assert ui.plot_options['style']=='scatter'
# Recovery Edit jumps to the first offending formula rather than the current cell.
ui.sheet.apply({(2,1):'=1/0'});ui.start_job(ui.sheet.recalculate_job(),'Calculating');finish()
assert ui.sheet.problem==(2,1) and ui.error
key(k.BUTTON_F2);ui.selected=1;key(k.BUTTON_CENTER)
assert ui.editing and ui.position==(2,1)
key(k.BUTTON_ESCAPE)
# Resource failure: keep the view, data and recovery choices alive.
original_recalc=Sheet.recalculate_job
before=ui.sheet.document();dirty=ui.sheet.dirty

def bad_calculation(self,clear=True):
 yield 1
 raise RuntimeError('maximum recursion depth exceeded')
Sheet.recalculate_job=bad_calculation
ui.start_job(ui.sheet.recalculate_job(),'Calculating');key(k.BUTTON_NONE)
Sheet.recalculate_job=original_recalc
assert vm.current_view.name=='eggcel' and ui.error and ui.sheet.document()==before and ui.job is None
vm.draw.screenshot('/private/tmp/eggcel-next-error.bmp')
key(k.BUTTON_F2);assert ui.page=='recovery'
ui.selected=5;key(k.BUTTON_CENTER)
recovery=read_sheet(vm.storage,DIRECTORY+'/Recovery-001.egg')
assert recovery.document()==before and ui.sheet.dirty==dirty
# Drawing failure uses a non-evaluating native fallback and still allows Save.
original_draw=app.Spreadsheet.draw
app.Spreadsheet.draw=lambda self:(_ for _ in ()).throw(MemoryError())
ui.safe_draw();assert ui._safe_mode and vm.current_view.name=='eggcel'
key(k.BUTTON_F2);ui.selected=5;key(k.BUTTON_CENTER)
assert vm.storage.exists(DIRECTORY+'/Recovery-002.egg')
app.Spreadsheet.draw=original_draw
ui.resume();ui.safe_draw()
key(k.BUTTON_ESCAPE);assert ui.page=='confirm'
key(k.BUTTON_DOWN);key(k.BUTTON_CENTER)
assert vm.current_view.name=='parent' and app._active is None and vm.draw.screenshot is capture
shots.clear();key(k.BUTTON_F1);assert not shots
key(k.BUTTON_ALT_S);assert shots==['screenshot.bmp']
print('PASS: remapped keys/F1 and Alt+S lifecycle, Range-Go/fill, async conversion, categorical charts and resource/drawing recovery')
