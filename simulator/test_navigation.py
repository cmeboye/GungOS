"""Next firmware hierarchy, fixed preferences, deletion and themed menus."""
import os,sys,json
from time import ticks_ms
root=os.getcwd()
for part in ('src/MicroPython','simulator/hardware','builds/MicroPython/apps_unfrozen'):sys.path.insert(0,root+'/'+part)
import sim_runtime
sd='/private/tmp/gungos-navigation-test-'+str(ticks_ms())
sim_runtime.configure(root,sd,root+'/builds/MicroPython/apps_unfrozen',1,'picocalc-pico2w',0,
                      True,False,False,False,'',_network_mode='offline',_audio_mode='silent')
from picoware.system.storage import Storage
from picoware.system.settings import Settings
from picoware.system.input import Input
from picoware.system.view import View
from picoware.system.view_manager import ViewManager
from picoware.system import buttons as k
store=Storage();store.mkdir('picoware');store.mkdir('picoware/settings')
# Legacy light mode and Back-exit settings cannot override the fixed controls.
assert Settings(store).update({'theme_color':0xFD20})
legacy=json.loads(store.read('picoware/settings/picoware.json'));legacy['dark_mode']=False;legacy['exit_button']=k.BUTTON_BACK
assert store.serialize(legacy,'picoware/settings/picoware.json')
vm=ViewManager()
assert (vm.background_color,vm.foreground_color,vm.selected_color)==(0,0xFFFF,0xFD20)
settings=Settings(store);assert 'dark_mode' not in settings.settings and 'exit_button' not in settings.settings
assert settings.update({'screen_brightness':70})
saved=json.loads(store.read('picoware/settings/picoware.json'))
assert 'dark_mode' not in saved and 'exit_button' not in saved
inp=vm.input_manager
assert inp._key_to_button(k.KEY_ESC)==k.BUTTON_ESCAPE
assert inp._key_to_button(8)==inp._key_to_button(k.KEY_DEL)==k.BUTTON_BACKSPACE
assert Input(k.BUTTON_BACK)._key_esc==k.BUTTON_ESCAPE
for button in (k.BUTTON_BACK,k.BUTTON_DELETE,k.BUTTON_BACKSPACE):assert Input.normalize_button(button)==k.BUTTON_BACKSPACE
Input.button=property(lambda self:self._last_button)
from picoware.applications import desktop,library,settings as config
assert library.APP_ITEMS==('PicoDESK','PicoLAB','Games','Misc')
vm.add(View('desktop_view',desktop.run,desktop.start,desktop.stop));vm.switch_to('desktop_view')
def key(button):vm.input_manager._last_button=button;vm.run()
def text(value):
 for char in value:key(inp._key_to_button(ord(char)))
key(k.BUTTON_NONE)
vm.draw.screenshot('/private/tmp/gungos-nav-home.bmp')
key(k.BUTTON_CENTER);assert vm.current_view.name=='app_PicoDESK'
import PicoDESK
assert [row[0] for row in __import__('desktopapps.launcher',None,None,('ROWS',)).ROWS]==['Eggcel','PicoWord','PicoPaint']
vm.draw.screenshot('/private/tmp/gungos-nav-desk.bmp')
key(k.BUTTON_BACK);key(k.BUTTON_DELETE);assert vm.current_view.name=='app_PicoDESK'
key(k.BUTTON_DOWN);key(k.BUTTON_CENTER);assert vm.current_view.name=='picoword'
text('abcd')
# Both Back and Delete erase before the cursor, including mid-string.
key(k.BUTTON_LEFT);key(k.BUTTON_BACK);key(k.BUTTON_DELETE)
key(k.BUTTON_F2);key(k.BUTTON_DOWN);key(k.BUTTON_DOWN);key(k.BUTTON_CENTER)
text('Navigation');key(k.BUTTON_CENTER)
p='picoware/documents/picoword/UntitledNavigation.pword'
assert 'ad' in vm.storage.read(p)
key(k.BUTTON_ESCAPE);assert vm.current_view.name=='app_PicoDESK'
key(k.BUTTON_ESCAPE);assert vm.current_view.name=='desktop_view'
key(k.BUTTON_DOWN);key(k.BUTTON_CENTER);assert vm.current_view.name=='app_PicoLAB'
import PicoLAB
vm.draw.screenshot('/private/tmp/gungos-nav-lab.bmp')
key(k.BUTTON_BACK);key(k.BUTTON_DELETE);assert vm.current_view.name=='app_PicoLAB' and PicoLAB._page=='tools'
# Standalone Graph returns to the same lab row and follows the system accent.
key(k.BUTTON_CENTER);assert vm.current_view.name=='app_Graph'
from engtools.plots import plot2d
assert plot2d._app.palette.ACCENT==vm.selected_color
key(k.BUTTON_ESCAPE);assert plot2d._app.state=='menu'
key(k.BUTTON_ESCAPE);assert vm.current_view.name=='app_PicoLAB' and PicoLAB._selected==0
key(k.BUTTON_DOWN);key(k.BUTTON_CENTER);assert vm.current_view.name=='app_Graph3D'
from engtools.plots import plot3d
assert plot3d.C_ACCENT==vm.selected_color
vm.draw.screenshot('/private/tmp/gungos-nav-graph3d.bmp')
key(k.BUTTON_ESCAPE);key(k.BUTTON_ESCAPE);assert vm.current_view.name=='app_PicoLAB' and PicoLAB._selected==1
key(k.BUTTON_ESCAPE);assert vm.current_view.name=='desktop_view'
key(k.BUTTON_DOWN);key(k.BUTTON_CENTER);assert vm.current_view.name=='games'
vm.draw.screenshot('/private/tmp/gungos-nav-games.bmp')
key(k.BUTTON_BACK);key(k.BUTTON_DELETE);assert vm.current_view.name=='games'
key(k.BUTTON_ESCAPE);assert vm.current_view.name=='desktop_view'
key(k.BUTTON_DOWN);key(k.BUTTON_CENTER);assert vm.current_view.name=='misc'
key(k.BUTTON_CENTER);assert vm.current_view.name=='screensavers'
vm.draw.screenshot('/private/tmp/gungos-nav-screensavers.bmp')
key(k.BUTTON_CENTER);assert vm.current_view.name=='screensaver_Lorenz'
key(k.BUTTON_NONE);key(k.BUTTON_BACK);key(k.BUTTON_DELETE)
assert vm.current_view.name=='screensaver_Lorenz'
key(k.BUTTON_ESCAPE);assert vm.current_view.name=='screensavers'
key(k.BUTTON_ESCAPE);assert vm.current_view.name=='misc'
key(k.BUTTON_ESCAPE);assert vm.current_view.name=='desktop_view'
key(k.BUTTON_RIGHT);key(k.BUTTON_CENTER);assert vm.current_view.name=='settings'
labels=config._menu.items
assert 'Dark Mode' not in labels and 'Exit Button' not in labels
assert 'Screen Brightness' in labels and 'Theme Color' in labels
vm.draw.screenshot('/private/tmp/gungos-nav-settings.bmp')
config._menu.set_selected(labels.index('Theme Color'));key(k.BUTTON_CENTER)
assert config._choice.selected_color==vm.selected_color
key(k.BUTTON_DOWN);key(k.BUTTON_CENTER)
assert vm.selected_color==Settings(vm.storage).theme_color and vm.draw.theme_color==vm.selected_color
key(k.BUTTON_ESCAPE);assert vm.current_view.name=='desktop_view'
print('PASS: hierarchy, legacy preference migration, Esc-only return, Back/Del editing and live system theme')
