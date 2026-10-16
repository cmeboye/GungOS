"""Productivity models, structured Word entry, Paint tools and SD failures."""
import os,sys,json
from time import ticks_ms
root=os.getcwd()
for relative in ('src/MicroPython','simulator/hardware','builds/MicroPython/apps_unfrozen'):
    sys.path.insert(0,root+'/'+relative)
from desktopapps.paint_model import Canvas,WIDTH,HEIGHT,packed,on
from desktopapps.word_model import Document,paragraph,pack_tree,unpack_tree
from engtools.calculator.editor import Editor,source,Node

c=Canvas();original=bytes(c.pixels)
c.checkpoint();c.rectangle(10,10,30,30,0);c.dirty=True
for _ in c.fill(20,20,packed(0xF800),0):pass
assert c.pixels[20*WIDTH+20]==packed(0xF800) and c.pixels[9*WIDTH+20]==255
assert c.restore() and bytes(c.pixels)==original and not c.dirty
c.checkpoint()
for _ in c.fill(0,0,0,1):pass
assert sum(value==0 for value in c.pixels)==WIDTH*HEIGHT//4
assert c.restore() and bytes(c.pixels)==original
c.checkpoint();job=c.fill(0,0,0,2)
next(job);job.close();assert c.restore() and bytes(c.pixels)==original
c.brush(0,0,0,15);assert c.pixels[0]==0 and len(c.pixels)==WIDTH*HEIGHT
bmp=b''.join(bytes(part) for part in c.bmp_chunks())
assert bmp[:2]==b'BM' and len(bmp)==1078+WIDTH*HEIGHT
d=Document();d.set_block(0,paragraph('hello',3,0xF800,1));assert d.restore() and d.blocks[0]['text']==''
e=Editor()
for char in '2^':e.insert(char)
assert e.expand();e.insert('3')
row=unpack_tree(pack_tree(e.root));assert source(row)=='2^(3)'
d.apply([paragraph('Example',2),{'type':'equation','row':row,'font':2,'color':None,'align':1}])
restored=Document.parse(d.document())
assert restored.plain()==d.plain() and not restored.dirty
for bad in ({'picoword':2,'blocks':[]},{'picoword':1,'blocks':[{'type':'text','text':'a','font':9,'color':None,'align':0}]}):
    try:Document.parse(json.dumps(bad))
    except ValueError:pass
    else:raise AssertionError('Bad Word document accepted')
try:unpack_tree([['bad',[]]])
except ValueError:pass
else:raise AssertionError('Bad equation accepted')
print('PASS: bounded canvas/fills/patterns/undo and Word rich/equation documents')

import sim_runtime
sim_runtime.configure(root,'/private/tmp/desktop-apps-'+str(ticks_ms()),root+'/builds/MicroPython/apps_unfrozen',
                      1,'picocalc-pico2w',0,True,False,False,False,'',_network_mode='offline',_audio_mode='silent')
from picoware.system.view_manager import ViewManager
from picoware.system.view import View
from picoware.system.input import Input
from picoware.system.storage import Storage
from picoware.system import buttons as k
from desktopapps import launcher
from desktopapps.word import Word
from desktopapps.paint import Paint
from engtools.plots.view import open_view
import PicoLAB
import PicoDESK
# MicroPython bound methods do not expose __self__; capture test controllers.
controllers={}
word_init,paint_init=Word.__init__,Paint.__init__
def word_create(self):word_init(self);controllers['word']=self
def paint_create(self):paint_init(self);controllers['paint']=self
Word.__init__,Paint.__init__=word_create,paint_create
Input.button=property(lambda self:self._last_button)
vm=ViewManager()
vm.add(View('parent',lambda vm:None,lambda vm:True,lambda vm:None));vm.switch_to('parent')
vm.add(View('desk',PicoDESK.run,PicoDESK.start,PicoDESK.stop));vm.switch_to('desk')
def key(button):vm.input_manager._last_button=button;vm.run()
def text(value):
    for char in value:key(vm.input_manager._key_to_button(ord(char)))
assert vm.current_view.name=='desk'
vm.draw.screenshot('/private/tmp/desktop-apps-menu.bmp')
key(k.BUTTON_DOWN);key(k.BUTTON_CENTER)
assert vm.current_view.name=='picoword'
# Obtain the controller bound to this managed view.
word=controllers['word']
text('Hello eq() ');assert word.page=='equation' and word.eq is not None
text('2^ ');text('3');key(k.BUTTON_CENTER)
assert word.page=='edit' and [b['type'] for b in word.model.blocks]==['text','equation','text']
assert source(word.model.blocks[1]['row'])=='2^(3)'
text('after');assert word.model.blocks[word.block]['text']=='after'
key(k.BUTTON_F3);key(k.BUTTON_DOWN);key(k.BUTTON_CENTER)
assert word.model.blocks[word.block]['font']==2
key(k.BUTTON_F4);key(k.BUTTON_RIGHT);key(k.BUTTON_RIGHT);key(k.BUTTON_RIGHT);key(k.BUTTON_CENTER)
assert word.model.blocks[word.block]['color']==0xF800
# Empty equation insertion is cancellable without touching the document.
before=word.model.document();key(k.BUTTON_F5);key(vm.input_manager._key_esc)
assert word.model.document()==before and word.page=='edit'
path=word.directory+'/Test.pword';word.write(path)
assert not word.model.dirty and word.load(path).plain()==word.model.plain()
original=vm.storage.read(path,'rb')
text('x');old_write=Storage.write;Storage.write=lambda *args,**kwargs:False
try:
    try:word.write(path)
    except OSError:pass
    else:raise AssertionError('Failed Word save reported success')
finally:Storage.write=old_write
assert word.model.dirty and vm.storage.read(path,'rb')==original
# A failed replacement restores the old document and keeps the edit dirty.
old_rename=Storage.rename
def failed_replace(self,origin,target):
    if origin==path+'.tmp':return False
    return old_rename(self,origin,target)
Storage.rename=failed_replace
try:
    try:word.write(path)
    except OSError:pass
    else:raise AssertionError('Failed replacement reported success')
finally:Storage.rename=old_rename
assert word.model.dirty and vm.storage.read(path,'rb')==original and not vm.storage.exists(path+'.bak')
word.write(path);assert not word.model.dirty
word.model.restore();assert word.model.dirty
text_path=word.directory+'/Test.txt';word.write(text_path,True)
assert vm.storage.read(text_path)==word.model.plain() and word.model.dirty
word.model=word.example();word.reset_cursor();word.draw()
vm.draw.screenshot('/private/tmp/picoword-dark.bmp')
word.start_equation();text('int() ');text('0');key(k.BUTTON_TAB);text('1');key(k.BUTTON_TAB);text('x^ ');text('2')
vm.draw.screenshot('/private/tmp/picoword-equation.bmp')
key(vm.input_manager._key_esc)
vm.background_color,vm.foreground_color,vm.selected_color=0xFFFF,0,0xB300
word.draw();vm.draw.screenshot('/private/tmp/picoword-light.bmp')
key(vm.input_manager._key_esc);assert word.page=='confirm'
key(k.BUTTON_DOWN);key(k.BUTTON_CENTER);assert vm.current_view.name=='desk' and word.model is None
key(k.BUTTON_DOWN);key(k.BUTTON_CENTER);assert vm.current_view.name=='picopaint'
paint=controllers['paint']
key(k.BUTTON_CENTER);assert paint.pen
key(k.BUTTON_RIGHT);key(k.BUTTON_DOWN);key(k.BUTTON_CENTER);assert not paint.pen and paint.model.dirty
key(k.BUTTON_F7);assert not paint.model.dirty
key(k.BUTTON_F3)
for _ in range(4):key(k.BUTTON_DOWN)
key(k.BUTTON_CENTER);assert paint.tool==4
paint.ink=packed(0xF800);key(k.BUTTON_CENTER)
key(k.BUTTON_NONE);assert paint.job is not None
key(vm.input_manager._key_esc);assert paint.job is None and not paint.model.dirty
key(k.BUTTON_CENTER)
for _ in range(100):
    key(k.BUTTON_NONE)
    if paint.job is None:break
assert paint.job is None and all(value==paint.ink for value in paint.model.pixels)
paint_path=paint.directory+'/Canvas.ppaint';paint.write(paint_path)
assert not paint.model.dirty and paint.load(paint_path).pixels==paint.model.pixels
paint.model.restore();assert paint.model.dirty
bmp_path=paint.directory+'/Canvas.bmp';paint.write(bmp_path,True)
assert vm.storage.size(bmp_path)==1078+WIDTH*HEIGHT
paint.model=paint.example();paint.reset_cursor();paint.draw()
vm.draw.screenshot('/private/tmp/picopaint-light.bmp')
vm.background_color,vm.foreground_color,vm.selected_color=0,0xFFFF,0x001F
paint.draw();vm.draw.screenshot('/private/tmp/picopaint-dark.bmp')
key(k.BUTTON_F4);vm.draw.screenshot('/private/tmp/picopaint-palette.bmp')
key(vm.input_manager._key_esc);key(vm.input_manager._key_esc)
assert paint.page=='confirm'
key(k.BUTTON_DOWN);key(k.BUTTON_CENTER);assert vm.current_view.name=='desk' and paint.model is None
key(vm.input_manager._key_esc);assert vm.current_view.name=='parent'
vm.add(View('lab',PicoLAB.run,PicoLAB.start,PicoLAB.stop));vm.switch_to('lab')
PicoLAB._selected=0;key(k.BUTTON_UP);assert PicoLAB._selected==len(PicoLAB.TOOLS)+4
print('PASS: independent PicoDESK, equation entry, fonts/colours, SD verification, Paint fill/cancel/export and return')
