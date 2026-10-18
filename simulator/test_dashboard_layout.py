"""Compact header geometry, honest usage bars and resized native widgets."""
import os,sys
from time import ticks_ms
root=os.getcwd()
for path in ('src/MicroPython','simulator/hardware','builds/MicroPython/apps_unfrozen'):
    sys.path.insert(0,root+'/'+path)
import sim_runtime
output='/private/tmp/gungos-layout-previews'
sim_runtime.mkdir_p(output)
sim_runtime.configure(root,'/private/tmp/gungos-layout-test-'+str(ticks_ms()),root+'/builds/MicroPython/apps_unfrozen',1,'picocalc-pico2w',0,True,False,False,False,'',_network_mode='offline',_audio_mode='silent',_sd_profile='clean')
from picoware.system.view_manager import ViewManager
from picoware.system.view import View
from picoware.system.input import Input
from picoware.system import buttons as k
from picoware.system.resource_info import snapshot,lines
from picoware.applications import desktop
from picoware.gui.dashboard import INFO_RECT,CATEGORY_RECT,MENU_RECT,WIDGET_RECT,WIDGET_SURFACE,FOOTER_RECT
from picoware.assets import dashboard_logo
Input.button=property(lambda self:self._last_button)
vm=ViewManager();vm._wifi=None
vm.add(View('desktop_view',desktop.run,desktop.start,desktop.stop));vm.switch_to('desktop_view')
def key(button):
    vm.input_manager._last_button=button;vm.run()
def snap(name):sim_runtime.lcd_screenshot(output+'/'+name+'.bmp')
key(k.BUTTON_NONE);home=desktop._dashboard
assert INFO_RECT[1]>=16 and INFO_RECT[1]+INFO_RECT[3]<=CATEGORY_RECT[1]
assert dashboard_logo.Y>=16 and dashboard_logo.Y+dashboard_logo.HEIGHT<=CATEGORY_RECT[1]
assert abs(dashboard_logo.X-(INFO_RECT[0]-dashboard_logo.X-dashboard_logo.WIDTH))<=1
assert dashboard_logo.Y==20
assert INFO_RECT==(93,17,226,25)
assert WIDGET_SURFACE[2:]==(238,238)
assert MENU_RECT[0]+MENU_RECT[2]+1==WIDGET_RECT[0]
assert WIDGET_RECT[0]+WIDGET_RECT[2]==319
assert WIDGET_RECT[1]+WIDGET_RECT[3]+1==FOOTER_RECT[1]
assert FOOTER_RECT==(1,303,318,16)
from sim_pixels import Pixels
fb=Pixels(vm.draw)
assert fb.pixel(1,43)==vm.selected_color and fb.pixel(1,60)==vm.selected_color
assert fb.pixel(1,61)==vm.background_color and fb.pixel(1,62)==vm.selected_color
assert fb.pixel(77,200)==vm.selected_color and fb.pixel(78,200)==vm.background_color
assert fb.pixel(79,200)==vm.foreground_color and fb.pixel(318,301)==vm.foreground_color
assert fb.pixel(318,302)==vm.background_color and fb.pixel(318,303)==vm.selected_color
assert all(fb.pixel(x,y)==vm.background_color for x in (0,319) for y in range(16,320))
assert all(fb.pixel(x,319)==vm.background_color for x in range(320))
snap('empty')
# All sidebar text uses the smallest font and fits, including wrapped tool names.
from picoware.gui.draw import Draw
from picoware.system.font import FONT_XTRA_SMALL
original_text=Draw._text
recorded=[]
def capture_text(self,x,y,text,color,font):
    if 0<=x<MENU_RECT[2] and 62<=y<304:
        recorded.append((x,y,str(text),font))
    return original_text(self,x,y,text,color,font)
Draw._text=capture_text
try:
    for category in range(4):
        home.category=category;home.draw()
        if category==2:snap('comms-menu')
        if category==3:snap('utils-menu')
finally:
    del Draw._text
assert recorded and all(font==FONT_XTRA_SMALL for x,y,text,font in recorded)
assert all(x+vm.draw.len(text,font)<MENU_RECT[0]+MENU_RECT[2]-1 for x,y,text,font in recorded)
assert any(text=='File' for x,y,text,font in recorded)
assert any(text=='Manager' for x,y,text,font in recorded)
assert any(text=='Serial' for x,y,text,font in recorded)
assert any(text=='Terminal' for x,y,text,font in recorded)
home.category=0;home.draw()
# Card counters come from Storage, independently of internal filesystem statvfs.
class Card:
    active=True
    total_space=8*1024*1024*1024
    free_space=3*1024*1024*1024
class Context:storage=Card()
rows=snapshot(Context())['rows']
assert next(row for row in rows if row[0]=='SD')==('SD',3*1024**3,5*1024**3,8*1024**3)
Card.active=False
assert next(row for row in snapshot(Context())['rows'] if row[0]=='SD')==('SD',None,None,None)
# Known/missing resource values draw filled/empty bars without inventing usage.
home.info={'board':'Raspberry Pi Pico 2 W','frequency':240,'simulator':True,
           'rows':[('Heap',0,100,100),('Flash',None,None,None),('SD',50,50,100),('PSRAM',None,None,None),('SRAM',None,None,520*1024)]}
home.info_lines=lines(home.info);home.draw()
assert fb.pixel(136,34)==vm.selected_color
assert fb.pixel(208,34)==vm.background_color
assert fb.pixel(280,34)==vm.selected_color and fb.pixel(304,34)==vm.background_color
key(k.BUTTON_F1);assert home.focus=='info'
assert fb.pixel(4,65)==vm.selected_color
for _ in range(8):key(k.BUTTON_DOWN)
assert home.scroll==8
snap('resources');key(k.BUTTON_ESCAPE);assert home.focus=='menu'
assert not vm.storage.exists('screenshot.bmp')
# Native Lorenz adopts the new square and keeps settings/input inside it.
home.widget.load('Lorenz');assert home.widget.module,home.widget.error
assert (home.widget.draw.width,home.widget.draw.height)==(238,238)
for _ in range(65):
    home.widget.next_frame=0;home.widget.module._next=0;key(k.BUTTON_NONE)
snap('lorenz')
key(k.BUTTON_F3);assert home.focus=='widget'
key(k.BUTTON_F2);assert home.widget.module._draft is not None
snap('lorenz-settings')
key(k.BUTTON_ESCAPE);assert home.widget.module._draft is None and home.focus=='widget'
key(k.BUTTON_ESCAPE);assert home.focus=='menu'
# Larger calculator prompt remains editable and retains textbook evaluation.
home.widget.load('Calculator Widget');assert home.widget.module,home.widget.error
key(k.BUTTON_F3)
for button in (k.BUTTON_2,k.BUTTON_PLUS,k.BUTTON_3,k.BUTTON_CENTER):key(button)
from engtools.calculator import app as calc
assert calc._active.answer==5 and not calc._active.history
snap('calculator')
key(k.BUTTON_F9);snap('calculator-help')
key(k.BUTTON_ESCAPE);assert home.focus=='menu'
vm.selected_color=0xFFE0;home.draw();snap('bright-accent')
assert fb.pixel(1,43)==0xFFE0
assert any(fb.pixel(x,y)==0 for x in range(12,70) for y in range(46,57))
key(k.BUTTON_H);snap('help');key(k.BUTTON_ESCAPE)
desktop.stop(vm)
print('PASS: compact non-overlapping geometry, SD counters, missing-data bars and resource scrolling')
print('PASS: 238px Lorenz/calculator input, settings, bright-accent contrast and preserved borders')
print('Layout screenshots: '+output)
