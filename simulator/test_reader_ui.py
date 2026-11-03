import os,sys
root=os.getcwd()
for relative in ('src/MicroPython','simulator/hardware',sys.argv[2] if len(sys.argv)>2 else 'builds/MicroPython/apps_unfrozen'):
    sys.path.insert(0,relative if relative.startswith('/') else root+'/'+relative)
from desktopapps.reader.epub import Book
from desktopapps.reader.state import State,PATH
import sim_runtime
from time import ticks_ms
sim_runtime.configure(root,'/private/tmp/reader-'+str(ticks_ms()),root+'/builds/MicroPython/apps_unfrozen',
    1,'picocalc-pico2w',0,True,False,False,False,'',_network_mode='offline',_audio_mode='silent')
from picoware.system.view_manager import ViewManager
from picoware.system.view import View
from picoware.system.input import Input
from picoware.system import buttons as k
from desktopapps.reader.app import PicoReader,DIRECTORY
import PicoDESK
Input.button=property(lambda self:self._last_button)
vm=ViewManager()
vm.add(View('parent',lambda vm:None,lambda vm:True,lambda vm:None));vm.switch_to('parent')
vm.add(View('desk',PicoDESK.run,PicoDESK.start,PicoDESK.stop));vm.switch_to('desk')
def key(button):
    vm.input_manager._last_button=button;vm.run()
    active=vm.current_view.name if vm.current_view else ''
    reader={'reader-test':globals().get('app'),'reader-test2':globals().get('app2'),
            'reader-test3':globals().get('app3'),'reader-test4':globals().get('app4')}.get(active)
    if reader:
        for _ in range(10000):
            if not reader.reflow and (not reader.session or not reader.session.pending):break
            vm.input_manager._last_button=k.BUTTON_NONE;vm.run()
        assert not reader.reflow and (not reader.session or not reader.session.pending),'Reader never settled'
for _ in range(4):key(k.BUTTON_DOWN)
key(k.BUTTON_CENTER);assert vm.current_view.name=='picoreader'
key(vm.input_manager._key_esc);assert vm.current_view.name=='desk'

app=PicoReader();vm.add(View('reader-test',app.run,app.start,app.stop));vm.switch_to('reader-test')
# Supply a real book directly; storage mounting is covered by app.start above.
with open(sys.argv[1],'rb') as handle:data=handle.read()
assert vm.storage.write(DIRECTORY+'/test.epub',data,'wb')
app.refresh();assert 'test.epub' in app.files
key(k.BUTTON_CENTER);assert not app.library and app.book
app.draw()
key(k.BUTTON_RIGHT);assert app.page==1
key(k.BUTTON_LEFT);assert app.page==0
key(k.BUTTON_F4);assert app.chapter==1
key(k.BUTTON_LEFT);assert app.chapter==0 and app.page>0
for _ in range(200):key(k.BUTTON_NONE)
assert app.book_progress() is not None
key(k.BUTTON_F9);assert app.help
key(vm.input_manager._key_esc);assert not app.help
app.draw();sim_runtime.lcd_screenshot('/private/tmp/gungos-reader-buffer-text.bmp')

# Font, bookmarks, index and the saved reading position.
previous_font,previous_page=app.font,app.page
previous_lines,previous_pages=app.lines,app.pages
chapter_reader=app.book.stream
def out_of_memory(index):raise MemoryError('injected chapter allocation')
app.book.stream=out_of_memory
key(k.BUTTON_F6)
assert 'injected chapter' in app.error
assert app.font==previous_font and app.state.font==previous_font
assert app.lines is previous_lines and app.pages is previous_pages and app.page==previous_page
chapter=app.chapter
app.session.cache.ram=[];app.session.cache.bytes=0;app.session.cache.slots=[]
key(k.BUTTON_F4)
assert app.chapter==chapter and app.lines is previous_lines and app.page==previous_page
app.book.stream=chapter_reader
key(k.BUTTON_F6);assert app.font==1 and app.message=='Font: S'
key(k.BUTTON_F1);assert len(app.bookmarks)==1 and app.message=='Bookmark added'
mark_chapter,mark_page=app.chapter,app.page
key(k.BUTTON_F5);assert app.bm_list
key(vm.input_manager._key_esc);assert not app.bm_list
key(k.BUTTON_RIGHT)
key(k.BUTTON_F1);assert len(app.bookmarks)==2
key(k.BUTTON_F5);key(k.BUTTON_UP);key(k.BUTTON_CENTER)
assert not app.bm_list and app.chapter==mark_chapter and app.page==mark_page
saved_chapter,saved_page,saved_font=app.chapter,app.page,app.font
book=app.book
key(vm.input_manager._key_esc);assert app.library
assert app.book is None and not app.lines and book.archive.file is None
key(vm.input_manager._key_esc);assert app.vm is None and book.archive.file is None
assert vm.storage.exists(PATH)

# A second instance restores the font, position, index and bookmarks from SD.
app2=PicoReader();vm.add(View('reader-test2',app2.run,app2.start,app2.stop));vm.switch_to('reader-test2')
assert app2.font==saved_font and app2.files.index('test.epub')>=0
app2.selected=app2.files.index('test.epub');key(k.BUTTON_CENTER)
assert app2.chapter==saved_chapter and app2.page==saved_page
assert len(app2.bookmarks)==2
index=app2.state.books['test.epub']['index']
assert index and index['font']==saved_font and len(index['pages'])==2
key(k.BUTTON_F5);key(k.BUTTON_CENTER)
assert not app2.bm_list and app2.chapter==mark_chapter and app2.page==mark_page
word=app2.page_word();assert app2.bookmark_word(app2.bookmarks[0])==word
key(k.BUTTON_F6);assert app2.font==2
key(k.BUTTON_F5);key(k.BUTTON_CENTER)
low,high=app2.page_range();assert low<=word<high and app2.bookmark_here()
position_word=app2.page_word()
key(k.BUTTON_F5);key(k.BUTTON_F2);assert len(app2.bookmarks)==1 and app2.bm_list
key(vm.input_manager._key_esc);assert not app2.bm_list
key(vm.input_manager._key_esc);assert app2.library
key(vm.input_manager._key_esc);assert app2.vm is None

# TXT books use the same library, pagination and cleanup path.
assert vm.storage.write(DIRECTORY+'/notes.txt','Hello from a text file.\r\n\r\nSecond paragraph.\n'.encode('utf-8'),'wb')
app3=PicoReader();vm.add(View('reader-test3',app3.run,app3.start,app3.stop));vm.switch_to('reader-test3')
app3.selected=app3.files.index('notes.txt');key(k.BUTTON_CENTER)
assert not app3.library and app3.book.title=='notes'
assert 'Hello from a text file.' in app3.book.chapter(0)
assert app3.saved_detail('notes.txt')=='Text file'
key(vm.input_manager._key_esc);assert app3.library
key(vm.input_manager._key_esc);assert app3.vm is None

# A saved word position restores the same passage after a font change.
app4=PicoReader();vm.add(View('reader-test4',app4.run,app4.start,app4.stop));vm.switch_to('reader-test4')
assert app4.font==2
app4.selected=app4.files.index('test.epub');key(k.BUTTON_CENTER)
assert app4.page_word()==position_word
key(vm.input_manager._key_esc);key(vm.input_manager._key_esc);assert app4.vm is None

# Corrupt state is ignored; the next save is verified and reloadable.
vm.storage.write(PATH,'not json')
state=State(vm.storage);assert state.font==0 and state.books=={}
state.set_position('x.epub',10,1,2);assert state.save()
state=State(vm.storage);assert state.books['x.epub']['chapter']==1 and state.books['x.epub']['page']==2
assert not vm.storage.exists(PATH+'.tmp')
# A verified .bak is recovered when the main file is missing.
assert vm.storage.rename(PATH,PATH+'.bak')
state=State(vm.storage);assert state.books['x.epub']['page']==2
assert state.save() and vm.storage.exists(PATH) and not vm.storage.exists(PATH+'.bak')
class LowMemoryStorage:
    active=True
    def exists(self,path):return False
    def mkdir(self,path):return True
    def write(self,path,text):raise MemoryError('injected state allocation')
assert not State(LowMemoryStorage()).save()
print('PASS: PicoDESK launch, TXT, pagination, font, bookmarks, position/index restore, corrupt state and low-memory cleanup')
