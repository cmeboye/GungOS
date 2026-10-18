"""Native-size widgets blit directly; arbitrary sizes retain fitted pixels."""
import os,sys
from time import ticks_ms
root=os.getcwd()
for part in ('src/MicroPython','simulator/hardware'):sys.path.insert(0,root+'/'+part)
import sim_runtime
sim_runtime.configure(root,'/private/tmp/gungos-widget-composition-'+str(ticks_ms()),
    root+'/builds/MicroPython/apps_unfrozen',1,'picocalc-pico2w',0,True,
    False,False,False,'',_network_mode='offline',_audio_mode='silent')
from picoware.system.view_manager import ViewManager
from picoware.gui.widget import WidgetDraw,WidgetHost
vm=ViewManager();vm._wifi=None
draw=vm.draw
native=draw._bytearray
calls=[]
def blit(*args):
    calls.append(draw.scale_set)
    return native(*args)
draw._bytearray=blit
for w,h in ((238,238),(320,200)):
    host=WidgetHost(vm,(80,63,238,238))
    host.draw=WidgetDraw(vm,w,h)
    for y in range(h):
        for x in range(w):host.draw.buffer[y*w+x]=(x+3*y)&255
    draw.fill_screen(0xFFFF)
    draw.set_scaling(2,2,True)  # composition must establish its own transform
    host.paint()
    assert calls[-1] == (w!=238 or h!=238)
    assert not draw.scale_set and not draw.scale_position
    scale=min(238/w,238/h);dw,dh=int(w*scale),int(h*scale)
    left,top=80+(238-dw)//2,63+(238-dh)//2
    for y in range(dh):
        row=draw._read_row(top+y)
        for x in range(dw):
            expected=((x*w//dw)+3*(y*h//dh))&255
            assert row[left+x]==expected,(w,h,x,y,row[left+x],expected)
        assert row[left-1]==255 and row[left+dw]==255
    assert not host.draw.changed
print('PASS: direct 238x238 blit, scaled rectangular widget, pixel parity, clipping and transform restoration')
