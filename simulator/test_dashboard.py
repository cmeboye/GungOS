"""Engineering desktop routes, theme, focus, saved widget choice and clipping."""
import os,sys
from time import ticks_ms
root=os.getcwd()
sys.path.insert(0,root+'/src/MicroPython')
sys.path.insert(0,root+'/simulator/hardware')
sys.path.insert(0,root+'/builds/MicroPython/apps_unfrozen')
import sim_runtime
sd='/private/tmp/picoware-dashboard-test-'+str(ticks_ms())
sim_runtime.configure(root,sd,root+'/builds/MicroPython/apps_unfrozen',1,'picocalc-pico2w',0,
                      True,False,False,False,'',_network_mode='offline',_audio_mode='silent')
from picoware.system.view_manager import ViewManager
from picoware.system.view import View
from picoware.system.input import Input
from picoware.system.settings import Settings
from picoware.system.storage import Storage
from picoware.system import buttons as k
from picoware.applications import desktop,settings
from picoware.assets import dashboard_logo
Input.button=property(lambda self:self._last_button)
vm=ViewManager()
vm._wifi=None
vm.add(View('desktop_view',desktop.run,desktop.start,desktop.stop))
vm.switch_to('desktop_view')
def key(button):
    vm.input_manager._last_button=button
    vm.run()
key(k.BUTTON_NONE)
home=desktop._dashboard
assert home.widget.module is None and home.widget.rect[2]==home.widget.rect[3]
assert len(dashboard_logo.decode())==dashboard_logo.WIDTH*dashboard_logo.HEIGHT*2<20000
assert dashboard_logo.decode(True,0)!=dashboard_logo.decode(False,0xFFFF)
assert home.info['rows'][-1]==('SRAM',None,None,520*1024)
vm.draw.screenshot('/private/tmp/picoware-dashboard-dark.bmp')
key(k.BUTTON_RIGHT); assert home.category==1
key(k.BUTTON_DOWN); assert home.indices[1]==1 and home.category==1
key(k.BUTTON_LEFT); assert home.category==0
key(k.BUTTON_RIGHT); assert home.indices[1]==1
shots=[];native_capture=vm.draw.screenshot
vm.draw.screenshot=lambda path:shots.append(path)
key(k.BUTTON_F1); assert home.focus=='info'
assert not shots, 'F1 took a screenshot instead of focusing Box 1'
key(k.BUTTON_ALT_S); assert shots==['screenshot.bmp'] and home.focus=='info', 'Alt+S must capture without changing focus'
vm.draw.screenshot=native_capture
old_category=home.category
for _ in range(8): key(k.BUTTON_DOWN)
assert home.scroll==8 and home.category==old_category
vm.draw.screenshot('/private/tmp/picoware-dashboard-info.bmp')
key(k.BUTTON_ESCAPE); assert home.focus=='menu'
key(k.BUTTON_H); assert home.focus=='help'
vm.draw.screenshot('/private/tmp/picoware-dashboard-help.bmp')
key(k.BUTTON_H); assert home.focus=='menu'
from picoware.applications.system import about
key(k.BUTTON_I)
assert vm.current_view.name=='about' and desktop._dashboard is None
assert about.ABOUT_TEXT.startswith('GungOS v2.2')
assert 'Cem Gungor' in about.ABOUT_TEXT and 'jblanked' in about.ABOUT_TEXT
assert 'GNU GPL v3' in about.ABOUT_TEXT and 'MIT' not in about.ABOUT_TEXT
vm.draw.screenshot('/private/tmp/picoware-gungos-info.bmp')
key(k.BUTTON_DOWN)
key(k.BUTTON_ESCAPE)
assert vm.current_view.name=='desktop_view'
key(k.BUTTON_NONE)
home=desktop._dashboard
assert home.category==1 and home.indices[1]==1
home.category,home.indices[1]=1,0
key(k.BUTTON_CENTER)
assert vm.current_view.name=='settings' and desktop._dashboard is None
labels=[settings._menu.get_item(i) for i in range(settings._menu.item_count)]
assert 'Screensaver' in labels
# Open the selector through Settings and verify the persistent key survives
# later credential updates and a desktop re-entry.
from picoware.applications.system import screensaver_setting as selector
assert vm.storage.mkdir('picoware/apps/screensavers') or vm.storage.exists('picoware/apps/screensavers')
fixture='''WIDGET_SIZE=(160,80)
last=-1
def start(vm):
    vm.draw.fill_screen(0xFFFF)
    vm.draw._line(-30,0,200,79,0xF800)
    vm.draw._text(4,4,'Widget',0,1)
    vm.draw.swap()
    return True
def run(vm):
    global last
    last=vm.button
    if last in (5,77): vm.back()
def stop(vm): pass
'''
assert vm.storage.write('picoware/apps/screensavers/WidgetTest.py',fixture)
settings._menu.set_selected(labels.index('Screensaver'))
key(k.BUTTON_CENTER)
assert vm.current_view.name=='screensaver_setting'
assert selector._items[0]=='None' and 'WidgetTest' in selector._items
selector._selected=selector._items.index('WidgetTest')
key(k.BUTTON_CENTER)
assert Settings(vm.storage).screensaver=='WidgetTest'
assert Settings(vm.storage).update({'wifi_ssid':'keep-network'})
assert Settings(vm.storage).screensaver=='WidgetTest'
vm.back()
assert vm.current_view.name=='desktop_view'
key(k.BUTTON_NONE)
home=desktop._dashboard
assert home.widget.module is not None,home.widget.error
assert home.widget.draw.width==160 and home.widget.draw.height==80
vm.draw.screenshot('/private/tmp/picoware-dashboard-widget.bmp')
original_category=home.category
key(k.BUTTON_RIGHT)
assert home.category==(original_category+1)%4 and home.widget.module.last==-1
key(k.BUTTON_F3)
assert home.focus=='widget' and home.widget.module.last==-1, 'Focus key leaked into widget'
key(k.BUTTON_DOWN)
assert home.category==(original_category+1)%4 and home.widget.module.last==k.BUTTON_DOWN
key(k.BUTTON_ESCAPE)
assert home.focus=='menu' and home.widget.module is not None
assert vm._view_count==1, 'Widget views escaped into the desktop view stack'
# Native-size, real screensaver, nested calculator and compatibility failures.
from picoware.gui.widget import WidgetHost,WidgetDraw
surface=WidgetDraw(vm,40,40)
surface.fill_screen(0xFFFF)
surface._text(0,0,'A',0,0)
assert any(value==0 for value in surface.buffer) and any(value==255 for value in surface.buffer), 'Black glyphs vanished in light mode'
surface._fill_rectangle(-10,-10,100,100,0x07E0)
surface._bytearray(0,0,2,2,bytes((0,255,0,255)))
assert surface.buffer[0]==0 and surface.buffer[1]==255
surface._bytearray(0,0,2,2,bytes((0,255,0,255)),True)
assert surface.buffer[0]==255 and surface.buffer[1]==0
surface.fill_screen(0)
surface._fill_round_rectangle(0,0,20,20,5,0xFFFF)
assert surface.fb.pixel(0,0)==0 and surface.fb.pixel(10,0)==255 and surface.fb.pixel(10,10)==255
vm.input_manager._was_pressed=True
vm.input_manager._elapsed_time=10
assert not home.widget.context.input_manager.is_held()
assert not home.widget.context.input_manager._was_pressed
with open(root+'/simulator/fixtures/Clock.py') as reader:
    assert vm.storage.write('picoware/apps/screensavers/Clock.py',reader.read())
home.widget.load('Clock')
assert home.widget.module is not None,home.widget.error
assert home.widget.step() and home.widget.draw.width==320
home.draw()
vm.draw.screenshot('/private/tmp/picoware-dashboard-clock.bmp')
home.widget.load('Calculator Widget')
assert home.widget.module is not None,home.widget.error
home.focus='widget'; home.widget.focused=True
key(k.BUTTON_2); key(k.BUTTON_PLUS); key(k.BUTTON_3); key(k.BUTTON_CENTER)
from engtools.calculator import app as calculator
assert calculator._active.answer==5
assert calculator._active.compact and not calculator._active.history
assert home.widget.draw.width==184 and home.widget.draw.height==184
assert vm.current_view.name=='desktop_view' and vm._view_count==1
assert not calculator._active.show_hints
key(k.BUTTON_2)
from engtools.calculator.editor import source
draft=source(calculator._active.editor.root,False)
key(k.BUTTON_F9)
assert calculator._active.show_hints and home.focus=='widget'
assert source(calculator._active.editor.root,False)==draft
vm.draw.screenshot('/private/tmp/picoware-dashboard-calculator-help.bmp')
key(k.BUTTON_F9)
assert not calculator._active.show_hints
old_color=vm.selected_color
vm.selected_color=0xFD20
assert calculator._active.accent==0xFD20
calculator._active.draw()
vm.selected_color=old_color
key(k.BUTTON_F5)
vm.draw.screenshot('/private/tmp/picoware-dashboard-calculator.bmp')
key(k.BUTTON_F3)
assert calculator._active.page=='options', 'Focused F3 should reach the calculator'
key(vm.input_manager._key_esc)
assert calculator._active.page=='calc'
key(vm.input_manager._key_esc)
assert home.focus=='menu' and home.widget.module is not None
home.widget.stop()
assert calculator._active is None
assert vm.storage.write('picoware/apps/screensavers/LabWidget.py',
                        'WIDGET_SIZE=(320,320)\nfrom PicoLAB import start,run,stop\n')
home.widget.load('LabWidget')
assert home.widget.module is not None,home.widget.error
home.focus='widget'; home.widget.focused=True
import PicoLAB
for _ in range(len(PicoLAB.TOOLS)+4): key(k.BUTTON_DOWN)
key(k.BUTTON_CENTER)
assert home.widget.context.current_view.name=='eng_calculator'
assert len(home.widget.context.stack)==1 and vm._view_count==1
key(vm.input_manager._key_esc)
assert home.widget.context.current_view.name=='__widget_root' and home.focus=='widget'
key(k.BUTTON_ESCAPE)
assert home.focus=='menu'
home.widget.load('LabWidget')
from gc import mem_alloc,mem_free
import gc
# Reject oversized declared surfaces before allocating an offscreen buffer.
assert vm.storage.write('picoware/apps/screensavers/HugeWidget.py',
                        'WIDGET_SIZE=(640,640)\ndef start(vm): return True\ndef run(vm): pass\ndef stop(vm): pass\n')
home.widget.load('HugeWidget')
assert home.widget.module is None and 'limit' in home.widget.error
home.widget.load('does-not-exist')
assert home.widget.module is None and home.widget.error
home.draw()
key(k.BUTTON_F3); assert home.focus=='menu'
# Failed selection writes retain the original widget preference.
old_write=Storage.serialize
Storage.serialize=lambda self,*args,**kwargs: False
try:
    selector.start(vm)
    selector._selected=0
    vm._button=k.BUTTON_CENTER
    selector.run(vm)
    assert selector._error and Settings(vm.storage).screensaver=='WidgetTest'
finally: Storage.serialize=old_write
vm._button=-1
home.widget.load('WidgetTest')
home.error=''
vm.background_color,vm.foreground_color=0xFFFF,0
key(k.BUTTON_NONE)
vm.draw.screenshot('/private/tmp/picoware-dashboard-light.bmp')
assert vm.draw._framebuffer.pixel(0,200)==0xFFFF
# Deterministic simulator launch routes execute against the new direct tabs.
vm.input_manager.reset()
sim_runtime.request_open('Settings')
queued=sim_runtime._keys[:]
assert queued
for raw in queued:
    key(vm.input_manager._key_to_button(raw))
sim_runtime._keys=[]
assert vm.current_view.name=='settings'
vm.back(); key(k.BUTTON_NONE)
desktop.stop(vm)
assert desktop._dashboard is None
print('PASS: dashboard tabs, exact artwork/themes, info focus, help, app return and simulator routes')
print('PASS: saved selection, offscreen glyphs/bitmaps, real Clock, isolated input, aspect ratio and failure handling')
