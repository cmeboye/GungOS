"""Graph regression checks using the real simulator display and SD adapter."""
import os,sys
from time import ticks_ms
root=os.getcwd()
sys.path.insert(0,root+'/src/MicroPython')
sys.path.insert(0,root+'/simulator/hardware')
sys.path.insert(0,root+'/builds/MicroPython/apps_unfrozen')
import sim_runtime
sd='/private/tmp/picoware-graph-test-'+str(ticks_ms())
sim_runtime.configure(root,sd,root+'/builds/MicroPython/apps_unfrozen',1,
                      'picocalc-pico2w',0,True,False,False,False,'',
                      _network_mode='offline',_audio_mode='silent')
sim_runtime.mkdir_p(sd)
from picoware.system.view_manager import ViewManager
from picoware.system.input import Input
from picoware.system.buttons import *
Input.button=property(lambda self:self._last_button)
from engtools.plots import plot2d as Graph
vm=ViewManager()
a=Graph.GraphApp(vm)
def key(button):
    vm.input_manager._last_button=button
    vm._button=button
    a.run()
def finish():
    vm.input_manager._last_button=BUTTON_NONE
    vm._button=BUTTON_NONE
    for i in range(3000):
        a.run()
        if a.job is None and not a.dirty and a.refine is None: return
    raise AssertionError('Renderer failed to complete')
for text,kind in [('sin(x)','y'),('y=x^2','y'),('x=3','x'),('x*y=1','implicit'),('x^2+y^2<=25','implicit'),('y>sin(x)','y'),('cos(t);sin(t)','param')]:
    e=Graph.Expression(text,Graph.COLORS[0]); assert not e.error,(text,e.error); assert e.kind==kind
assert Graph.Expression('sin(x)',0).value(x=0)==0
assert Graph.Expression('x^2+y^2=25',0).value(x=3,y=4)==0
for relation in ('<','<=','>','>='):
    e=Graph.Expression('x*y'+relation+'1',0)
    assert e.inside(-1)==(relation in ('<','<='))
    assert e.inside(0)==(relation in ('<=','>='))
for bad in ('__import__(x)','x.__class__','[x for x in y]','open(x)','x==y','sin(','x=','2x'):
    assert Graph.Expression(bad,0).error,bad
assert Graph.Expression('1/x',0).value(x=0) is None
assert not Graph.valid_bounds([0,0,-1,1])
assert not Graph.valid_bounds([0,float('inf'),-1,1])
finish()
assert all(e.bbox for e in a.items)
vm.draw.screenshot('/private/tmp/graph-default.bmp')
old=a.bounds[:]; key(BUTTON_RIGHT); assert a.bounds[0]>old[0]
key(BUTTON_PLUS); assert a.bounds[1]-a.bounds[0]<old[1]-old[0]
a.refine=None; a.dirty=True; finish()
key(BUTTON_CENTER); assert a.state=='expressions'
key(BUTTON_SPACE); assert not a.items[0].visible
key(BUTTON_SPACE); assert a.items[0].visible
vm.draw.screenshot('/private/tmp/graph-expressions.bmp')
a.begin_edit(('expression',0),'sin(','Equation')
try: a.finish_edit('sin(')
except Exception: pass
else: raise AssertionError('Bad expression accepted')
a.begin_edit(('expression',0),'x^2','Fix equation'); assert a.return_state=='expressions'
a.finish_edit('y=x^2'); a.set_state('plot'); finish()
a.fit('y'); assert a.bounds[2]<0 and a.bounds[3]>50
a.fit('equal'); assert abs((a.bounds[1]-a.bounds[0])/a.pw-(a.bounds[3]-a.bounds[2])/a.ph)<1e-6
old=a.bounds[:]
try: a.finish_edit('0')
except Exception: pass
# Numeric edits reject inverted limits without changing state.
a.edit_target=('number',0)
try: a.finish_edit(str(a.bounds[1]+1))
except ValueError: pass
else: raise AssertionError('Inverted window accepted')
assert a.bounds==old
# Every general-equation and inequality preset completes with finite coordinates.
for i in (0,3,4,5,6):
    a.set_state('presets'); a.row=i; a.activate(); finish()
    assert all(e.bbox for e in a.items),(i,[e.bbox for e in a.items])
    vm.draw.screenshot('/private/tmp/graph-preset-'+str(i)+'.bmp')
# Window values are typed in place (Beam view's form), never on a screen keyboard.
def typed(text):
    for c in text: key(vm.input_manager._key_to_button(ord(c)))
a.bounds=[-10.,10.,-10.,10.]
a.set_state('window'); a.draw_menu()
a.row=1; typed('2*pi')
assert a.state=='input' and a.edit.text=='2*pi' and a.return_state=='window'
vm.draw.screenshot('/private/tmp/graph-window-edit.bmp')
key(BUTTON_DOWN)
assert a.state=='window' and abs(a.bounds[1]-6.283185)<1e-5 and a.row==2
typed('20'); key(BUTTON_CENTER)
assert a.state=='input' and a.edit_error and 'Min' in a.edit_note and a.bounds[2]==-10
vm.draw.screenshot('/private/tmp/graph-window-error.bmp')
key(BUTTON_ESCAPE); assert a.state=='window' and a.bounds[2]==-10
key(BUTTON_BACKSPACE); assert a.state=='input' and a.edit.text=='-1'
key(BUTTON_ESCAPE)
a.row=len(a.window_fields()); grid=a.grid; key(BUTTON_CENTER); assert a.grid!=grid
key(BUTTON_CENTER); assert a.grid==grid
vm.draw.screenshot('/private/tmp/graph-window.bmp')
key(BUTTON_ESCAPE); assert a.state=='plot'
# Expressions are edited in a prompt panel with the hardware keyboard.
key(BUTTON_CENTER); assert a.state=='expressions'
a.row=len(a.items); key(BUTTON_CENTER)
assert a.state=='input' and a.edit.text=='' and a.edit_target==('expression',len(a.items))
typed('cos(x)'); vm.draw.screenshot('/private/tmp/graph-expression-edit.bmp')
count=len(a.items); key(BUTTON_CENTER); assert a.state=='expressions' and a.items[-1].text=='cos(x)' and len(a.items)==count+1
a.row=len(a.items)-1; key(BUTTON_CENTER); typed('+'); key(BUTTON_CENTER)
assert a.state=='input' and a.edit_error
key(BUTTON_ESCAPE); assert a.items[-1].text=='cos(x)'
# F9 opens the shared help box from anywhere and returns where it was.
key(BUTTON_F9); assert a.state=='help'
vm.draw.screenshot('/private/tmp/graph-help.bmp')
key(BUTTON_DOWN); assert a.help_first==1
key(BUTTON_F9); assert a.state=='expressions'
key(BUTTON_ESCAPE); finish(); assert a.state=='plot'
vm.draw.screenshot('/private/tmp/graph-plot.bmp')
a.save(); b=Graph.GraphApp(vm)
assert b.bounds==a.bounds and b.trange==a.trange
assert [e.text for e in b.items]==[e.text for e in a.items]
print('PASS: equations, inequalities, restricted expressions, poles, pan, zoom, editing, fit, presets and SD persistence')
# Failed storage writes must be visible to the caller.
class FailedStorage:
    def mkdir(self,path): return True
    def write(self,path,data): return False
vm._storage=FailedStorage()
try: a.save()
except ValueError: pass
else: raise AssertionError('Failed save reported success')
print('PASS: invalid bounds and failed saves rejected')
