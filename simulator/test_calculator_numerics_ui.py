"""Numerical diagnostics/cancellation and the actual device-report UI route."""
import os,sys
from time import ticks_ms
root=os.getcwd();apps=sys.argv[1] if len(sys.argv)>1 else 'builds/MicroPython/apps_unfrozen'
for path in ('src/MicroPython','simulator/hardware',apps):sys.path.insert(0,root+'/'+path)
import sim_runtime
sim_runtime.configure(root,'/private/tmp/gungos-calc-numerics-'+str(ticks_ms()),root+'/'+apps,1,'picocalc-pico2w',0,
                      True,False,False,False,'',_network_mode='offline',_audio_mode='silent')
from picoware.system.view_manager import ViewManager
from picoware.system.view import View
from picoware.system.input import Input
from picoware.system import buttons as k
from engtools.calculator import app
from engtools.calculator.editor import source
import PicoLAB
Input.button=property(lambda self:self._last_button)
vm=ViewManager();vm.alert=lambda message,*args:(_ for _ in ()).throw(AssertionError(message))
vm.add(View('parent',lambda vm:None,lambda vm:True,lambda vm:None));vm.switch_to('parent')
app.show(vm);calc=app._active

def key(button):vm.input_manager._last_button=button;vm.run()
def text(s):
    for ch in s:key(vm.input_manager._key_to_button(ord(ch)))
calc.angle='RAD';text('int(0,1,exp(-((x-0.12345)/0.0001)^2))');key(k.BUTTON_F6)
assert not calc.error and calc.calculation_info and 'samples' in calc.notice
assert abs(calc.answer-.000177245385)<1e-7
saved=(calc.answer,dict(calc.variables),len(calc.history));text('a=sum(k,1,1024,k^2)');draft=source(calc.editor.root)
normal=calc.calculation_progress

def cancel(record):vm.input_manager._last_button=vm.input_manager._key_esc;normal(record)
calc.calculation_progress=cancel;key(k.BUTTON_F6);calc.calculation_progress=normal
assert calc.error=='Cancelled' and source(calc.editor.root)==draft
assert (calc.answer,calc.variables,len(calc.history))==saved
key(k.BUTTON_F10);calc.choose_mode(2);solver=calc.workspace();solver.page='polynomial';solver.coefficients=[1,-4,6,-4,1]
key(k.BUTTON_F6)
for _ in range(100):
    key(k.BUTTON_NONE)
    if solver.job is None:break
assert solver.page=='results' and any(row[0]=='Conditioning' for row in solver.results)
assert any(row[0]=='Multiplicity' for row in solver.results)
vm.back();vm.add(View('lab',PicoLAB.run,PicoLAB.start,PicoLAB.stop));vm.switch_to('lab')
PicoLAB._enter('checks');PicoLAB._selected=next(i for i,row in enumerate(PicoLAB.MENUS['checks']) if row[0]=='calcbench')
key(k.BUTTON_CENTER);assert vm.current_view.name=='calculator_check'
key(k.BUTTON_F6)
path=sim_runtime.host_path('picoware/calculator-check.txt')
for _ in range(600):
    key(k.BUTTON_NONE)
    try:os.stat(path);break
    except OSError:pass
else:raise AssertionError('report was not saved')
with open(path) as f:report=f.read()
from engtools.bench.calculator import HEADER,FIXED_CHECKS
assert 'passed=%d failed=0'%FIXED_CHECKS in report and 'END '+HEADER in report,report
assert 'screen_mode=' in report and 'heap_min_sampled=' in report
key(vm.input_manager._key_esc);assert vm.current_view.name=='lab'
print('PASS: integral diagnostics, ESC cancellation/draft/state, repeated-root warning and full benchmark route/report')
