"""Eggcel formulas, transactional edits/files, keyboard routes and rendering."""
import os,sys,json,gc
from time import ticks_ms
root=os.getcwd()
for relative in ('src/MicroPython','simulator/hardware','builds/MicroPython/apps_unfrozen'):
    sys.path.insert(0,root+'/'+relative)
from desktopapps.eggcel.model import Sheet,MAX_CELLS,DIRECTORY,write_verified,read_sheet,demo
from desktopapps.eggcel.formulas import CellError,shifted,address,reference


def close(actual,expected): assert abs(actual-expected)<1e-4*(1+abs(expected)),(actual,expected)
def error(sheet,raw,code):
    sheet.apply({(0,4):raw})
    value=sheet.value((0,4))
    assert isinstance(value,CellError) and value.code==code,(raw,value)


s=Sheet()
s.apply({(0,0):'2',(1,0):'3',(2,0):'Text',(0,1):'=A1+A2',
         (1,1):'=SUM(A1:A3)',(2,1):'=AVERAGE(A1:A3)'})
assert s.value((0,1))==5 and s.value((1,1))==5
close(s.value((2,1)),2.5)
for raw,expected in (('=IF(A1=2,"yes",1/0)','yes'),('=IF(FALSE,1/0,7)',7),
                     ('=50%*10',5),('=2^3^2',64),('=-2^2',4),
                     ('=COUNT(A1:A3)',2),('=MIN(A1:A3)',2),('=MAX(A1:A3)',3),
                     ('=ROUND(-2.5,0)',-3),('=SIN(PI()/2)',1),
                     ('=SQRT(9)+ABS(-4)',7),('=SUM(A1:A2,10)',15),
                     ('=IF("a"="A",TRUE,FALSE)',True)):
    s.apply({(0,4):raw})
    actual=s.value((0,4))
    if isinstance(expected,(str,bool)): assert actual==expected,(raw,actual)
    else: close(actual,expected)
for raw,code in (('=A201','#REF!'),('=AA1','#REF!'),('=1/0','#DIV/0!'),
                 ('=SQRT(-1)','#NUM!'),('=A3+2','#VALUE!'),('=NOPE(2)','#NAME?'),
                 ('=__import__("os")','#ERROR!'),('=1+','#ERROR!'),
                 ('=SUM(A1:Z200)','#LIMIT!'),('=E1','#CYCLE!')):
    error(s,raw,code)
s.apply({(0,4):'=F1',(0,5):'=E1'})
assert s.value((0,4)).code=='#CYCLE!'
s.apply({(0,5):'12'})
assert s.value((0,4))==12
for raw in ('=(', '=SUM(', '=SUM(1,)', '=IF()', '=', '=1e99', '=1+"x"', '=1..2'):
    s.apply({(0,4):raw});assert isinstance(s.value((0,4)),CellError),raw
assert shifted('=A1+$B$2+C$3+$D4+SUM(A1:A2)',2,1)=='=B3+$B$2+D$3+$D6+SUM(B3:B4)'
assert shifted('=IF(A1="A1",1,2)',1,1)=='=IF(B2="A1",1,2)'
assert shifted('=A1',-1,0)=='=#REF!'
assert shifted('=SIN(PI())',2,3)=='=SIN(PI())'
s=Sheet();s.apply({(0,0):'5',(0,1):'=A1*2'})
clip=s.copied((0,0,0,1));s.paste(clip,(1,0))
assert s.cells[(1,1)]=='=A2*2' and s.value((1,1))==10
s.apply({(1,0):'7'});assert s.value((1,1))==14
original=s.document()
try:s.paste(clip,(199,25))
except ValueError:pass
else:raise AssertionError('Out-of-bounds paste accepted')
assert s.document()==original
full=Sheet();full.apply({(i//26,i%26):str(i) for i in range(MAX_CELLS)})
try:full.apply({(199,25):'extra'})
except ValueError:pass
else:raise AssertionError('Cell budget ignored')
assert len(full.cells)==MAX_CELLS
assert Sheet.from_document(s.document()).cells==s.cells
for data in ({'eggcel':2,'cells':[]},{'eggcel':1,'cells':[[0,0,'1'],[0,0,'2']]},
             {'eggcel':1,'cells':[[200,0,'1']]},{'eggcel':1,'cells':[[True,0,'1']]}):
    try:Sheet.from_document(json.dumps(data))
    except ValueError:pass
    else:raise AssertionError('Malformed document accepted')
csv='Name,Value,Note\r\n"A, B",2,"He said ""yes"""\r\n=1+1,3,\r\n'
imported=Sheet.from_csv(csv)
assert imported.value((1,0))=='A, B' and imported.value((1,2))=='He said "yes"'
assert imported.value((2,0))=='=1+1'
assert Sheet.from_csv(imported.csv()).cells==imported.cells
print('PASS: references/functions/errors, cycles, copied anchors, sparse limits and document/CSV validation')

import sim_runtime
sim_runtime.configure(root,'/private/tmp/eggcel-test-'+str(ticks_ms()),root+'/builds/MicroPython/apps_unfrozen',
                      1,'picocalc-pico2w',0,True,False,False,False,'',_network_mode='offline',_audio_mode='silent')
from picoware.system.view_manager import ViewManager
from picoware.system.view import View
from picoware.system.input import Input
from picoware.system import buttons as k
from picoware.system.storage import Storage
from desktopapps.eggcel import app
import PicoLAB as lab
import PicoDESK as desk
Input.button=property(lambda self:self._last_button)
vm=ViewManager()
vm.add(View('parent',lambda vm:None,lambda vm:True,lambda vm:None));vm.switch_to('parent')
vm.add(View('desk',desk.run,desk.start,desk.stop));vm.switch_to('desk')
lab._enter('tools');lab._selected=2
def key(button):
    vm.input_manager._last_button=button;vm.run()
    for _ in range(1000):
        if app._active is None or app._active.job is None or app._active.job_kind!='Calculating':break
        vm.input_manager._last_button=k.BUTTON_NONE;vm.run()
def text(value):
    for char in value:key(vm.input_manager._key_to_button(ord(char)))
key(k.BUTTON_CENTER)
assert vm.current_view.name=='eggcel' and app._active is not None
ui=app._active
assert not ui.sheet.cells and vm._overlay is None
vm.draw.screenshot('/private/tmp/eggcel-empty.bmp')
text('12');key(k.BUTTON_CENTER)
assert ui.sheet.value((0,0))==12 and not ui.editing and ui.position==(0,0)
key(k.BUTTON_CENTER);text('3');key(vm.input_manager._key_esc)
assert ui.sheet.cells[(0,0)]=='12' and not ui.editing
key(k.BUTTON_RIGHT);text('=A1*2');key(k.BUTTON_CENTER)
assert ui.sheet.value((0,1))==24
key(k.BUTTON_LEFT);key(k.BUTTON_F3);key(k.BUTTON_RIGHT);key(k.BUTTON_F4)
key(k.BUTTON_DOWN);key(k.BUTTON_LEFT);key(k.BUTTON_F5)
assert ui.sheet.value((1,1))==24 and ui.sheet.cells[(1,1)]=='=A2*2'
key(k.BUTTON_F9);assert vm._overlay is not None and vm._overlay.title=='KEYBINDINGS'
key(k.BUTTON_F9);assert vm._overlay is None
for _ in range(15):key(k.BUTTON_DOWN)
assert ui.top<=ui.row<ui.top+ui.visible_rows
for _ in range(10):key(k.BUTTON_RIGHT)
assert ui.col in [col for col,_,_ in ui.visible_columns()]
key(k.BUTTON_F7);key(k.BUTTON_F7);text('Z200');key(k.BUTTON_CENTER)
assert ui.position==(199,25)
vm.draw.screenshot('/private/tmp/eggcel-scrolled.bmp')
key(k.BUTTON_F8);assert ui.sheet.widths[25]==96
path=DIRECTORY+'/Keyboard-test.egg'
ui.write(path)
assert not ui.sheet.dirty and read_sheet(vm.storage,path).cells==ui.sheet.cells
original=vm.storage.read(path)
ui.sheet.apply({(0,0):'99'})
old_write=Storage.write
Storage.write=lambda *args,**kwargs:False
try:
    try:ui.write(path)
    except OSError:pass
    else:raise AssertionError('Failed SD save reported success')
finally:Storage.write=old_write
assert ui.sheet.dirty and vm.storage.read(path)==original
ui.write(path);assert not ui.sheet.dirty
assert not vm.storage.exists(path+'.bak')
assert read_sheet(vm.storage,path).value((0,0))==99
ui.sheet.apply({(0,0):'100'})
original=vm.storage.read(path)
old_rename=Storage.rename
Storage.rename=lambda self,old,new: False if old.endswith('.tmp') else old_rename(self,old,new)
try:
    try:ui.write(path)
    except OSError:pass
    else:raise AssertionError('Failed rename reported success')
finally:Storage.rename=old_rename
assert vm.storage.read(path)==original and ui.sheet.dirty
for _ in range(1000):
    if ui.job is None:break
    key(k.BUTTON_NONE)
if ui.error:key(vm.input_manager._key_esc)
key(vm.input_manager._key_esc)
assert ui.page=='confirm'
key(vm.input_manager._key_esc);assert ui.page=='grid' and ui.sheet.dirty
# A deterministic example exercises all four visible columns and both themes.
ui.sheet=demo();ui.row,ui.col,ui.top,ui.left=5,3,0,0;ui.filename='';ui.error=ui.message=''
ui.draw();vm.draw.screenshot('/private/tmp/eggcel-dark.bmp')
key(k.BUTTON_CENTER)
vm.draw.screenshot('/private/tmp/eggcel-edit.bmp')
key(vm.input_manager._key_esc)
vm.foreground_color,vm.background_color,vm.selected_color=0,0xFFFF,0xB300
ui.draw();vm.draw.screenshot('/private/tmp/eggcel-light.bmp')
key(k.BUTTON_F9);vm.draw.screenshot('/private/tmp/eggcel-help.bmp');key(k.BUTTON_F9)
key(k.BUTTON_F1);assert ui.page=='file'
vm.draw.screenshot('/private/tmp/eggcel-file.bmp')
key(vm.input_manager._key_esc)
key(vm.input_manager._key_esc);assert ui.page=='confirm'
key(k.BUTTON_DOWN);key(k.BUTTON_CENTER)
assert vm.current_view.name=='desk' and app._active is None
key(k.BUTTON_CENTER)
assert app._active.sheet.cells=={} and vm._overlay is None
key(vm.input_manager._key_esc)
key(vm.input_manager._key_esc)
assert vm.current_view.name=='parent'
vm.add(View('lab',lab.run,lab.start,lab.stop));vm.switch_to('lab')
lab._enter('tools');lab._selected=next(i for i,row in enumerate(lab.MENUS['tools']) if row[0]=='calculator');key(k.BUTTON_CENTER)
assert vm.current_view.name=='eng_calculator'
key(vm.input_manager._key_esc)
assert vm.current_view.name=='lab'
print('PASS: PicoLAB launch, enter/edit/cancel, range copy, scrolling, SD save/failures, themes and exit guard')
