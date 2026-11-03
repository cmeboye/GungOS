"""Real baseline JPEG images through the GUI and native JPEGDEC simulator helper."""
import os,sys,gc
from time import ticks_ms
root=os.getcwd()
for part in ('src/MicroPython','simulator/hardware','builds/MicroPython/apps_unfrozen'):
    sys.path.insert(0,root+'/'+part)
import sim_runtime
sim_runtime.configure(root,'/private/tmp/gungos-jpeg-images-'+str(ticks_ms()),root+'/builds/MicroPython/apps_unfrozen',
                      1,'picocalc-pico2w',0,True,False,False,False,'',_network_mode='offline',_audio_mode='silent')
from picoware.system.view_manager import ViewManager
from picoware.system.vector import Vector
from picoware.gui.jpeg import JPEG
from sim_pixels import Pixels,colour
vm=ViewManager();draw=vm.draw;pixels=Pixels(draw)
fixture=sys.argv[1]
for name in ('1x1','17x19','31x17','319x241','321x319','601x799','1281x961'):
    path=fixture+'/'+name+'.jpg'
    with open(path,'rb') as f:data=f.read()
    draw.fill_screen(0xFD20)
    assert draw.image_jpeg_buffer(Vector(0,0),data),name
    assert pixels.pixel(319,319)==colour(0xFD20),name
    gc.collect()
    draw.fill_screen(0xFD20)
    assert draw.image_jpeg(Vector(0,0),path,vm.storage),name
    assert pixels.pixel(319,319)==colour(0xFD20),name
    gc.collect()
# File and borrowed-buffer output must be byte-identical.
path=fixture+'/321x319.jpg'
with open(path,'rb') as f:data=f.read()
draw.fill_screen(0);assert draw.image_jpeg_buffer(Vector(13,17),data)
a=[bytes(draw._read_row(y)) for y in range(320)]
draw.fill_screen(0);assert draw.image_jpeg(Vector(13,17),path,vm.storage)
assert all(a[y]==bytes(draw._read_row(y)) for y in range(320))
with open(fixture+'/progressive.jpg','rb') as f:data=f.read()
assert not draw.image_jpeg_buffer(Vector(0,0),data)
assert not draw.image_jpeg_buffer(Vector(0,0),b'bad')
# Reused caller-owned decoders stay open; explicitly closed ones reject new draws.
jpeg=JPEG()
with open(path,'rb') as f:data=f.read()
for _ in range(3):assert draw.image_jpeg_buffer(Vector(0,0),data,jpeg)
assert not jpeg._closed
jpeg.close();assert not jpeg.draw_buffer(0,0,data)
print('PASS: actual JPEGDEC images, direct/file equality, odd sizes/scaling, malformed/progressive input and decoder lifecycle')
