"""Offline dictionary conversion, bounded lookup and native UI lifecycle."""
import os,sys,struct
root=os.getcwd()
for relative in ('src/MicroPython','simulator/hardware','builds/MicroPython/apps_unfrozen'):
    sys.path.insert(0,root+'/'+relative)
from desktopapps.dictionary.local import Dictionary,MAGIC,FIELD,RECORD,HEADER,normalize

class Fixture:
    def __init__(self):
        self.data=MAGIC+struct.pack('<I',3)
        for key,value in (('apple','mela'),('eat','mangiare'),('water','acqua')):
            self.data+=key.encode()+b'\x00'*(FIELD-len(key.encode()))+value.encode()+b'\x00'*(FIELD-len(value.encode()))
        self.reads=0
    def read(self,path,mode,index=0,count=0):
        assert count<=RECORD
        self.reads+=1
        return self.data[index:index+count]
    def size(self,path):return len(self.data)
assert normalize(' PERCHÉ ')== 'perché'
assert normalize('l’acqua')=="l'acqua"
fixture=Fixture();dictionary=Dictionary(fixture)
for word,expected in ((' APPLE ','mela'),('eat','mangiare'),('water','acqua'),('absent',None),('zebra',None)):
    assert dictionary.lookup(word)==expected
for word in ('','two words','123','a'*64):
    try:dictionary.lookup(word)
    except ValueError:pass
    else:raise AssertionError('Invalid input accepted')
fixture.data=fixture.data[:-1]
try:dictionary.lookup('apple')
except OSError:pass
else:raise AssertionError('Truncated data accepted')

# Actual packaged data (optional for a clean checkout); bound I/O per lookup.
class Disk:
    def __init__(self):self.reads=0
    def read(self,path,mode,index=0,count=0):
        self.reads+=1
        with open(root+'/sd-card/'+path,mode) as handle:
            handle.seek(index);return handle.read(count)
    def size(self,path):return os.stat(root+'/sd-card/'+path)[6]
try:os.stat(root+'/sd-card/picoware/dictionary/en-it.pdict')
except OSError:print('SKIP: supplied dictionary data not built')
else:
    disk=Disk();actual=Dictionary(disk)
    for direction in ('en-it','it-en'):
        path='picoware/dictionary/'+direction+'.pdict'
        count=(disk.size(path)-HEADER)//RECORD
        # Exercise first/last records and samples across the entire index.
        for index in list(range(0,count,max(1,count//100)))+[count-1]:
            row=disk.read(path,'rb',HEADER+index*RECORD,RECORD)
            key=row[:FIELD].split(b'\x00',1)[0].decode()
            value=row[FIELD:].split(b'\x00',1)[0].decode()
            disk.reads=0
            assert actual.lookup(key,direction)==value
            assert disk.reads<=18
    print('PASS: supplied dictionaries sampled in both directions; <=18 bounded reads')

import sim_runtime
from time import ticks_ms
sim_runtime.configure(root,'/private/tmp/dictionary-'+str(ticks_ms()),root+'/builds/MicroPython/apps_unfrozen',
    1,'picocalc-pico2w',0,True,False,False,False,'',_network_mode='offline',_audio_mode='silent')
from picoware.system.view_manager import ViewManager
from picoware.system.view import View
from picoware.system.input import Input
from picoware.system import buttons as k
from desktopapps.dictionary.app import PicoDict
from desktopapps import launcher
import PicoDESK
Input.button=property(lambda self:self._last_button)
vm=ViewManager()
vm.add(View('parent',lambda vm:None,lambda vm:True,lambda vm:None));vm.switch_to('parent')
vm.add(View('desk',PicoDESK.run,PicoDESK.start,PicoDESK.stop));vm.switch_to('desk')
def key(button):vm.input_manager._last_button=button;vm.run()
for _ in range(3):key(k.BUTTON_DOWN)
key(k.BUTTON_CENTER)
assert vm.current_view.name=='picodict'
key(vm.input_manager._key_esc)
assert vm.current_view.name=='desk'
app=PicoDict()
vm.add(View('dict-test',app.run,app.start,app.stop));vm.switch_to('dict-test')
fixture=Fixture();app.dictionary=Dictionary(fixture)
for char in 'apple':key(vm.input_manager._key_to_button(ord(char)))
key(k.BUTTON_CENTER);assert app.result=='mela'
key(k.BUTTON_F2);assert app.direction=='it-en' and not app.result
key(k.BUTTON_F5);assert not app.query and app.cursor==0
key(k.BUTTON_CENTER);assert app.message=='Enter one word'
key(k.BUTTON_F9);assert app.help
key(vm.input_manager._key_esc);assert not app.help and app.vm is vm
app.query='apple';app.cursor=5;app.search();app.draw()
vm.draw.screenshot('/private/tmp/picodict.bmp')
key(k.BUTTON_DELETE);assert app.query=='appl' and not app.result
app.dictionary=Dictionary(vm.storage);app.search()
assert app.message=='Install dictionary data on SD'
key(vm.input_manager._key_esc);assert app.vm is None and app.dictionary is None
print('PASS: PicoDESK launch, translation, direction, editing, help, missing SD and cleanup')
