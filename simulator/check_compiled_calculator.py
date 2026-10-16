import os,sys
root=os.getcwd()
for relative in ('src/MicroPython','simulator/hardware','builds/MicroPython/apps'):
    sys.path.insert(0,root+'/'+relative)
import sim_runtime
sim_runtime.configure(root,'/private/tmp/picolab-ui-compiled-sd-'+str(__import__('time').ticks_ms()),root+'/builds/MicroPython/apps',1,'picocalc-pico2w',0,True,False,False,False,'',_network_mode='offline',_audio_mode='silent')
from picoware.system.view_manager import ViewManager
from picoware.system.view import View
from picoware.system.input import Input
from picoware.system import buttons as k
from engtools.calculator import app
from engtools.calculator.editor import source
assert app.__file__.endswith('.mpy'),app.__file__
Input.button=property(lambda self:self._last_button)
vm=ViewManager()
vm.add(View('parent',lambda vm:None,lambda vm:True,lambda vm:None));vm.switch_to('parent')
app.show(vm)
calc=app._active
for mode in range(6):
    calc.choose_mode(mode)
    assert not calc.show_hints
    vm.input_manager._last_button=k.BUTTON_F9;vm.run()
    assert calc.show_hints
    vm.input_manager._last_button=k.BUTTON_F9;vm.run()
    assert not calc.show_hints
calc.choose_mode(0)
for char in '2+3':
    vm.input_manager._last_button=vm.input_manager._key_to_button(ord(char));vm.run()
vm.input_manager._last_button=k.BUTTON_CENTER;vm.run()
assert calc.answer==5
vm.selected_color=0xFD20;calc.draw()
assert calc.accent==0xFD20
vm.draw.screenshot('/private/tmp/picolab-calculator-theme.bmp')
vm.back()
from picoware.gui.widget import WidgetHost
host=WidgetHost(vm,(132,114,184,184));host.load('Calculator Widget')
assert host.module is not None,host.error
assert app._active.compact and not app._active.show_hints
host.context.input_manager._last_button=k.BUTTON_F9
host.module.run(host.context)
assert app._active.show_hints
host.stop()
print('PASS: compiled SD modules, six-mode F9 toggle, arithmetic, theme and native widget')
