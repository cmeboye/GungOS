"""Navigation labels, keyboard workflows, precise jumps and cancel cleanup."""
import os,sys
from time import ticks_ms
root=os.getcwd();apps=sys.argv[2] if len(sys.argv)>2 else 'builds/MicroPython/apps_unfrozen'
for path in ('src/MicroPython','simulator/hardware',apps):sys.path.insert(0,path if path.startswith('/') else root+'/'+path)
import sim_runtime
sim_runtime.configure(root,'/private/tmp/reader-navigation-'+str(ticks_ms()),root+'/'+apps,1,'picocalc-pico2w',0,True,False,False,False,'',_network_mode='offline',_audio_mode='silent')
from picoware.system.view_manager import ViewManager
from picoware.system.view import View
from picoware.system.input import Input
from picoware.system import buttons as k
from desktopapps.reader.app import PicoReader,DIRECTORY
from desktopapps.reader.navigation import Navigation
Input.button=property(lambda self:self._last_button)
vm=ViewManager();vm.add(View('parent',lambda vm:None,lambda vm:True,lambda vm:None));vm.switch_to('parent')
app=PicoReader();vm.add(View('reader',app.run,app.start,app.stop));vm.switch_to('reader')
with open(sys.argv[1],'rb') as f:assert vm.storage.write(DIRECTORY+'/Navigation.epub',f.read(),'wb')
app.refresh()
def key(b):vm.input_manager._last_button=b;vm.run()
def settle():
 for _ in range(200000):
  if app.navigation:
   if not app.navigation.job:break
  elif not app.session.pending:break
  key(k.BUTTON_NONE)
 else:raise AssertionError('Navigation did not settle')
def number(text):
 for c in text:key(vm.input_manager._key_to_button(ord(c)))
key(k.BUTTON_CENTER);settle();assert not app.error
original=app.session.current
key(k.BUTTON_F10);settle();nav=app.navigation
sim_runtime.lcd_screenshot('/private/tmp/gungos-reader-chapters.bmp')
assert nav.label(0)=='Start café' and nav.label(1)=='Middle' and nav.label(2)=='Finish',nav.labels
# Cancellation/help preserve the actual reading page and state.
key(k.BUTTON_F9);assert nav.help
key(vm.input_manager._key_esc);assert not nav.help
key(k.BUTTON_F1);number('2');key(vm.input_manager._key_esc);assert nav.mode=='list'
key(vm.input_manager._key_esc);assert app.navigation is None and app.session.current is original
# Direct chapter selection, with visible menu moving by ten when applicable.
key(k.BUTTON_F10);key(k.BUTTON_DOWN);key(k.BUTTON_CENTER);settle()
assert app.chapter==1 and app.page==0 and app.navigation is None
key(k.BUTTON_F10);key(k.BUTTON_F2);number('2');sim_runtime.lcd_screenshot('/private/tmp/gungos-reader-goto.bmp');key(k.BUTTON_CENTER);settle();assert app.chapter==1 and app.page==1
key(k.BUTTON_RIGHT_BRACKET);settle();assert app.page==2
key(k.BUTTON_LEFT_BRACKET);settle();assert app.page==1
# Numeric chapter typing and out-of-range rejection do not alter the passage.
key(k.BUTTON_F10);number('0');key(k.BUTTON_CENTER);assert app.navigation.error
key(k.BUTTON_BACKSPACE);number('3');key(k.BUTTON_CENTER);settle();assert app.chapter==2 and app.page==0
# A not-yet-counted page beyond chapter end must stay in the requested chapter.
key(k.BUTTON_F10);key(k.BUTTON_F1);number('2');key(k.BUTTON_CENTER);settle()
app.pages[1]=0
key(k.BUTTON_F10);key(k.BUTTON_F2);number('999');key(k.BUTTON_CENTER);settle()
assert app.chapter==1 and app.page==app.pages[1]-1,(app.chapter,app.page,app.pages)
assert 'showing last' in app.message
# Known totals reject impossible page numbers before starting a seek.
key(k.BUTTON_F10);key(k.BUTTON_F2);number('999');key(k.BUTTON_CENTER);assert app.navigation and app.navigation.error
key(vm.input_manager._key_esc);key(vm.input_manager._key_esc)
key(k.BUTTON_F10);vm.back();assert app.navigation is None and app.book is None
# Missing/damaged optional contents metadata keeps navigation usable.
app=PicoReader();vm.add(View('fallback',app.run,app.start,app.stop));vm.switch_to('fallback');app.refresh()
key(k.BUTTON_CENTER);settle();app.book.metadata=lambda *args: (_ for _ in ())
key(k.BUTTON_F10);settle();assert app.navigation.label(0)=='a'
key(vm.input_manager._key_esc);vm.back()
# TXT has the same chapter-local page entry and bracket bindings.
app=PicoReader();vm.add(View('txt',app.run,app.start,app.stop));vm.switch_to('txt')
assert vm.storage.write(DIRECTORY+'/Navigation.txt','A text passage for page navigation.\n'*400,'w')
app.refresh();app.selected=app.files.index('Navigation.txt');key(k.BUTTON_CENTER);settle()
key(k.BUTTON_F10);assert app.navigation.label(0)=='Text part 1'
key(k.BUTTON_F2);number('2');key(k.BUTTON_CENTER);settle();assert app.page==1
key(k.BUTTON_LEFT_BRACKET);settle();assert app.page==0
vm.back()
print('PASS: TOC labels, chapter/page menus, help/cancel, input validation, bracket turns, out-of-range chapter confinement and cleanup')
