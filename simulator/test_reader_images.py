"""EPUB JPEG/PNG extraction, real native PNG rows, PSRAM preview and navigation."""
import os,sys,gc,io,binascii
root=os.getcwd()
for part in ('src/MicroPython','simulator/hardware',sys.argv[2] if len(sys.argv)>2 else 'builds/MicroPython/apps_unfrozen'):
    sys.path.insert(0,root+'/'+part)
import sim_runtime
from time import ticks_ms
sim_runtime.configure(root,'/private/tmp/gungos-reader-images-'+str(ticks_ms()),root+'/builds/MicroPython/apps_unfrozen',
    1,'picocalc-pico2w',0,True,False,False,False,'',_network_mode='offline',_audio_mode='silent')
from picoware.system.view_manager import ViewManager
from picoware.system.input import Input
from picoware.system import buttons as k
from desktopapps.reader.app import PicoReader,DIRECTORY
from desktopapps.reader.epub import Book
from picoware.gui.png import draw_png
import pngdec
Input.button=property(lambda self:self._last_button)
vm=ViewManager();app=PicoReader();app.start(vm)
def key(button):
    vm.input_manager._last_button=button;vm._button=button;app.run(vm)
source=sys.argv[1]
with open(source,'rb') as f:data=f.read()
assert vm.storage.write(DIRECTORY+'/images.epub',data,'wb')
app.refresh();app.selected=app.files.index('images.epub');app.open_selected()
def settle():
    for _ in range(10000):
        app.background()
        if not app.reflow and not app.session.pending:break
    assert not app.error,app.error
settle();app.turn(1);settle();anchor=app.page_word();page=app.page
app.list_images();assert len(app.images)==4,app.images
assert app.images[0][0]=='OPS/art/alpha.png'
assert app.images[1][0]=='OPS/art/photo.jpg'
# Native deflate extraction produces exact bytes, then deletes partial outputs on errors.
path=vm.storage.vfs_prefix+'/extracted.png'
book=app.book;size=book.archive.extract(app.images[0][0],path)
with open(path,'rb') as f:png=f.read()
assert size==len(png) and png[:8]==b'\x89PNG\r\n\x1a\n'
entry=book.archive.entries[app.images[0][0]]
book.archive.entries[app.images[0][0]]=entry[:-1]+(entry[-1]^1,)
try:book.archive.extract(app.images[0][0],path);assert False
except ValueError:pass
try:os.stat(path);assert False
except OSError:pass
book.archive.entries[app.images[0][0]]=entry
# A stored ZIP member uses the same bounded extraction checks.
path=vm.storage.vfs_prefix+'/stored.png';book.archive.extract(app.images[2][0],path)
# Native read exceptions and invalid PNGs must release their workspace.
class Short(io.IOBase):
    def __init__(self,data):self.data=data;self.pos=0
    def readinto(self,b):
        n=min(len(b),7,len(self.data)-self.pos);b[:n]=self.data[self.pos:self.pos+n];self.pos+=n;return n
for _ in range(5):
    assert pngdec.draw(Short(png),len(png),0,0,320,280,0xffffff)[0:2]==(101,73)
class Broken(io.IOBase):
    def readinto(self,b):raise OSError('injected read failure')
gc.collect();before=gc.mem_alloc()
for _ in range(20):
    try:pngdec.draw(Broken(),len(png),0,0,320,280,0);assert False
    except OSError:pass
    try:pngdec.draw(io.BytesIO(b'bad'*30),90,0,0,320,280,0);assert False
    except ValueError:pass
gc.collect();assert gc.mem_alloc()-before<4096
# Switch to PSRAM while viewing, hold only the external preview, restore text anchor.
original=vm.draw.mode
for index in (0,1,2,0):
    app.image_selected=index;app.open_image()
    assert not app.lines and app.image_anchor==anchor and app.viewer.preview.length()==320*280
    assert vm.draw.mode==vm.draw.MODE_PSRAM
    rows=[bytes(vm.draw._read_row(y)) for y in range(280)]
    vm.draw.fill_screen(0);app.viewer.draw()
    assert all(rows[y]==bytes(vm.draw._read_row(y)) for y in range(280))
    app.draw();gc.collect()
    if index==0:sim_runtime.lcd_screenshot('/private/tmp/gungos-reader-image-preview.bmp')
app.return_to_text()
assert app.page_word()==anchor and app.page==page and app.lines and app.viewer is None
assert vm.draw.mode==original
# Unsupported resource leaves reading position recoverable, including stop while suspended.
app.list_images();app.image_selected=3
try:app.open_image();assert False
except ValueError as e:assert 'unsupported' in str(e)
assert app.image_anchor==anchor
app.return_to_text();assert app.page_word()==anchor
# Real key paths: list, viewer, help redraw, previous/next and recoverable failure.
key(k.BUTTON_F7);assert app.image_list
key(k.BUTTON_CENTER);assert app.viewer and not app.image_list
key(k.BUTTON_RIGHT);assert app.image_selected==1 and not app.error
key(k.BUTTON_F9);assert app.help
key(vm.input_manager._key_esc);assert not app.help and not app.image_list
key(vm.input_manager._key_esc);assert app.image_list
key(k.BUTTON_DOWN);key(k.BUTTON_CENTER);assert app.image_selected==2 and not app.image_list
key(k.BUTTON_RIGHT);assert app.image_list and 'unsupported' in app.error
key(vm.input_manager._key_esc);assert app.lines and app.page_word()==anchor and not app.image_list
app.list_images();app.open_image();app.save_position()
assert app.state.books[app.name]['word']==anchor
app.stop(vm);assert app.book is None and app.viewer is None and not app.lines
print('PASS: native PNG/ZIP short reads and errors; EPUB JPEG/PNG previews; PSRAM cache; text anchors and cleanup; workspace',pngdec.workspace_size())
