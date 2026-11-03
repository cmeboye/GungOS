"""F7 category navigation, mode/cell routing, help/drafts and compact layout."""
import os,sys,math
from time import ticks_ms
root=os.getcwd();apps=sys.argv[1] if len(sys.argv)>1 else 'builds/MicroPython/apps_unfrozen'
for path in ('src/MicroPython','simulator/hardware',apps):sys.path.insert(0,root+'/'+path)
import sim_runtime
sim_runtime.configure(root,'/private/tmp/gungos-functions-ui-'+str(ticks_ms()),root+'/'+apps,1,'picocalc-pico2w',0,
    True,False,False,False,'',_network_mode='offline',_audio_mode='silent')
from picoware.system.view_manager import ViewManager
from picoware.system.view import View
from picoware.system.input import Input
from picoware.system import buttons as k
from engtools.calculator import app,catalogue
from engtools.calculator.editor import source,SLOTS
from engtools.calculator.evaluate import FUNCTIONS
from engtools.calculator.scientific import hypot
from engtools.numerics import matrices
from engtools.numerics.statistics import Dataset
Input.button=property(lambda self:self._last_button)
vm=ViewManager();vm.add(View('parent',lambda vm:None,lambda vm:True,lambda vm:None));vm.switch_to('parent')
app.show(vm);calc=app._active;calc.choose_mode(3)

def key(b):vm.input_manager._last_button=b;vm.run()
def text(s):
    for ch in s:key(vm.input_manager._key_to_button(ord(ch)))
def select(token):
    key(k.BUTTON_F7);assert calc.catalogue_group is None
    group,item=catalogue.location(token,len(calc.math_groups())==len(catalogue.CATEGORIES))
    calc.selected=group;key(k.BUTTON_CENTER);assert calc.catalogue_group==group
    calc.selected=item;calc.draw();key(k.BUTTON_CENTER)
for name,args,want in (('atan2','1,-1',135),('phase','-1+i',135),('radius','3+4i',5),('rect','2,90',2j),
                       ('gcd','-48,18',6),('lcm','12,18',36),('asinh','i',complex(0,math.pi/2)),
                       ('acosh','-2',complex(math.acosh(2),math.pi)),('atanh','0.5',math.atanh(.5)),
                       ('log1p','1e-8',1e-8),('expm1','1e-8',1e-8),('hypot','3,4',5),
                       ('round','1.25,1',1.2),('sigfig','1.23456,4',1.235),('trunc','-2.9',-2),
                       ('gamma','5',24),('lgamma','1',0),('erf','0',0),('erfc','0',1)):
    select(name);assert source(calc.editor.root)==name+'()'
    text(args);key(k.BUTTON_F6);assert not calc.error,(name,calc.error)
    a,b=complex(calc.answer),complex(want)
    assert hypot(a.real-b.real,a.imag-b.imag)<2e-5*max(1,hypot(b.real,b.imag)),(name,a,b)
# Group back/help leaves the active nested row untouched.
text('2^ ');text('3');saved=source(calc.editor.root);parents=calc.editor.parents[:]
key(k.BUTTON_F7);calc.selected=6;key(k.BUTTON_CENTER);calc.selected=1
state=calc.catalogue_group,calc.selected
key(k.BUTTON_F9);key(k.BUTTON_F9);assert (calc.catalogue_group,calc.selected)==state
key(vm.input_manager._key_esc);assert calc.catalogue_group is None and calc.page=='templates'
key(vm.input_manager._key_esc);assert source(calc.editor.root)==saved and calc.editor.parents==parents
key(k.BUTTON_F10)
# Every registered scalar function is discoverable under its own name or X/XY variant.
registered=set()
for _,_,entries in catalogue.groups():
    for token,_,_ in entries:registered.add(token.split('_',1)[0])
assert set(FUNCTIONS)<=registered,set(FUNCTIONS)-registered
# Matrix-specific entries are offered only in a Matrix expression, not a scalar cell.
calc.choose_mode(5);w=calc.workspace();w.matrices['MatA']=matrices.matrix([[2,0],[0,3]])
select('trace');text('MatA');key(k.BUTTON_F6);assert calc.answer==5 and not calc.error
w.page='cells';w.field='cell';w.editing=True;w.selected=0;w.editor.clear()
key(k.BUTTON_F7);assert len(calc.math_groups())==len(catalogue.CATEGORIES)-1
key(vm.input_manager._key_esc);assert calc.page=='matrix'
# Dataset defaults insert complete expressions and leave the calculator draft isolated.
calc.statistics_view().dataset=Dataset();calc.statistics.dataset.set(0,'X',3)
calc.choose_mode(0);select('mean_X');assert source(calc.editor.root)=='mean(X)'
key(k.BUTTON_F6);assert calc.answer==3 and not calc.error
calc.draw();sim_runtime.lcd_screenshot('/private/tmp/gungos-function-answer.bmp')
key(k.BUTTON_F7);calc.selected=6;key(k.BUTTON_CENTER);calc.draw()
sim_runtime.lcd_screenshot('/private/tmp/gungos-functions-menu.bmp')
vm.back()
from picoware.gui.widget import WidgetHost
host=WidgetHost(vm,(132,114,184,184));host.load('Calculator Widget');assert not host.error
widget=app._active;widget.open_page('templates');widget.draw()
group,item=catalogue.location('log1p');widget.catalogue_group=group;widget.selected=item;widget.draw()
host.context.input_manager._last_button=k.BUTTON_CENTER;widget.run(host.context)
assert source(widget.editor.root)=='log1p()'
host.stop()
print('PASS: F7 families, 19 function entries/evaluation, all scalar discovery, help/back/draft, matrix/statistics routing and widget')
