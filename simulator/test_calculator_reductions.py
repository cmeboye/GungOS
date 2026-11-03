"""Rendered Sigma/Pi entry, bounded reductions and review regression cases."""
import os, sys, math
from time import ticks_ms
root = os.getcwd()
for part in ('src/MicroPython', 'simulator/hardware', 'builds/MicroPython/apps_unfrozen'):
    sys.path.insert(0, root+'/'+part)
from engtools.calculator.evaluate import calculate, format_value, Evaluator, Parser
from engtools.calculator.editor import Editor, Node, source, clone, SLOTS
from engtools.calculator.base_n import IntegerParser
from engtools.calculator.app import Calculator
from engtools.calculator.workspaces import MatrixWorkspace
from engtools.numerics.equations import root_job
from engtools.numerics.statistics import Dataset
from engtools.numerics import matrices


def close(a, b, tolerance=2e-5):
    assert abs(a-b) <= tolerance*max(1, abs(b)), (a, b)


def value(text, variables=None, complex_mode=False):
    return calculate(text, variables if variables is not None else {}, 'RAD', complex_mode)[0]


def reject(text, contains=None, variables=None):
    variables = variables if variables is not None else {'Ans': 42}
    before = dict(variables)
    try:
        value(text, variables)
    except (ValueError, TypeError, ZeroDivisionError, OverflowError) as exc:
        if contains: assert contains in str(exc), (text, str(exc))
    else:
        raise AssertionError('Accepted invalid input: '+text)
    assert variables == before, text


for text, expected in (
    ('sum(k,1,10,k^2)', 385), ('prod(k,1,5,k)', 120),
    ('sum(k,-2,2,k)', 0), ('sum(k,3,2,k)', 0), ('prod(k,3,2,k)', 1),
    ('sum(k,2,2,k^2)', 4), ('sum()', 0), ('prod()', 1),
    ('sum(1,2,3,4)', 10), ('prod(2,3,4)', 24),
    ('sum(100000000,1,-100000000)', 1),
    ('sum(k,1,1000,0.001)', 1), ('sum(k,1,3,sum(m,1,k,m))', 10),
    ('sum(k,1,2,sum(k,1,3,k)+k)', 15),
    ('int(0,1,sum(k,1,3,k*x))', 3),
    ('sum(k,1,3,int(0,1,k*x))', 3),
    ('2sum(k,1,3,k)+prod(k,1,3,k)', 18),
    ('sum(k,16777215,16777216,k)', 33554431),
):
    close(value(text), expected)
variables = {'k': 99, 'Ans': 7}
assert value('sum(k,1,3,k)', variables) == 6 and variables['k'] == 99
close(value('sum(k,1,3,k*i)', complex_mode=True), 6j)
close(value('prod(k,1,2,i*k)', complex_mode=True), -2)
for text, message in (
    ('sum(k,1,1025,k)', '1024'), ('prod(k,1,1.5,k)', 'integers'),
    ('sum(k,1,i,k)', None), ('sum(pi,1,3,pi)', 'reserved'),
    ('sum(k,16777216,16777218,k)', 'integers'),
    ('prod(1e-30,1e-20)', 'underflow'), ('prod(1e30,1e30)', 'range'),
    ('sum(k,1,1024,sum(m,1,1024,1))', 'work limit'),
    ('sum(k,1,2,1/0)', None), ('int(0,1,int(0,1,x))', 'Nested'),
    ('1 2', 'operator'), ('2.5 .5', 'operator'),
):
    reject(text, message)
close(value('2pi'), 2*math.pi)
assert value('2(3+4)') == 14
assert '1e-08' in format_value(value('1e-8*i', complex_mode=True))
assert format_value(complex(1000,2000), True) == '1e+3+2e+3i'
close(value('logb(2,-8)', complex_mode=True), complex(3, math.pi/math.log(2)))
close(value('sqrt(i)', complex_mode=True)**2, 1j)
close(value('asin(2)', complex_mode=True), complex(math.pi/2,math.acosh(2)))
for name in ('pi','sin','i','j','X','Y','sum','prod','mean'):
    variables = {'Ans': 7}
    try: IntegerParser(name+'=3', variables).calculate()
    except ValueError: pass
    else: raise AssertionError('Base-N accepted reserved name: '+name)
    assert variables == {'Ans': 7}
for text, expected in (('x=3',3), ('1e-12*x=1e-12',1), ('1e-12*(x-3)=0',3),
                       ('1e12*(x-3)=0',3), ('x^2=0',0)):
    record = list(root_job(text,-10,10,0.3,angle='RAD'))[-1]
    close(record['root'],expected)
for text in ('1e-12=0', '1e-12*(x^2+1)=0', '1/x=0', '1e-12/x=0'):
    try: list(root_job(text,-10,10,0.3,angle='RAD'))
    except (ValueError,ZeroDivisionError): pass
    else: raise AssertionError('False root: '+text)

# Dataset products follow frequency and retain sum(X)'s existing semantics.
data = Dataset(True)
data.set(0,'X',2); data.set(0,'Y',3); data.set(0,'Freq',2)
data.insert_row(1); data.set(1,'X',5); data.set(1,'Y',7)
assert calculate('sum(X)',{},statistics=data)[0] == 7
assert calculate('prod(X)',{},statistics=data)[0] == 10
data.set_frequency(True)
assert calculate('sum(X)',{},statistics=data)[0] == 9
assert calculate('prod(X)',{},statistics=data)[0] == 20
assert calculate('prod(Y)',{},statistics=data)[0] == 63
data.set(0,'Freq',0)
assert calculate('prod(X)',{},statistics=data)[0] == 5
large = Dataset();large.set(0,'X',1);large.set(0,'Freq',1025);large.set_frequency(True)
try: calculate('prod(X)',{},statistics=large)
except ValueError as exc: assert '1024' in str(exc)
else: raise AssertionError('Dataset product ignored its term limit')
c = Calculator(); c.angle='RAD'
w = MatrixWorkspace(c)
close(w.evaluate('int(0,1,x^2)'), 1/3)
assert w.evaluate('sum(k,1,10,k)') == 55
assert w.evaluate('sqrt(det(identity(3)))') == 1
w.matrices['MatA'] = matrices.identity(2)
assert w.evaluate('sum(k,1,3,k)*MatA')[0,0] == 6
print('PASS: reductions, frequency, scope/budgets, matrix scalar functions and correctness regressions')


def type_editor(editor, text):
    for char in text:
        if char == ' ' and editor.expand(): continue
        editor.insert(char)


for kind in ('sum','prod'):
    editor = Editor(); type_editor(editor,kind+'() ')
    assert editor.root[0].kind == kind and editor.parents[-1][2] == 1
    assert editor.root[0].rows[0] == ['k']
    assert editor.focus_missing() and editor.hint().startswith('lower bound')
    type_editor(editor,'1'); editor.tab(); type_editor(editor,'5'); editor.tab()
    type_editor(editor,'k^ '); type_editor(editor,'2'); editor.move(1)
    assert source(editor.root) == kind+'(k,1,5,k^(2))'
    close(value(source(editor.root)), 55 if kind=='sum' else 14400)
    editor.load(clone(editor.root)); editor.move(-1)
    assert editor.parents and editor.row is editor.root[0].rows[3]
    editor.tab(); editor.tab()  # visits nested exponent then root
    assert editor.row is editor.root
    editor.tab(); assert editor.row is editor.root[0].rows[0]
    editor.template('sum'); assert len(editor.parents) == 2
for text in ('sum(X)', 'prod(Y)', 'sum(1,2,3)', 'sum(1,2,3,4)'):
    editor = Editor(); type_editor(editor,text)
    assert not editor.expand() and source(editor.root) == text
for text in ('sum(k,1,10,k^2)', 'prod(n,1,5,n)'):
    editor=Editor(); type_editor(editor,text+' ')
    assert isinstance(editor.root[0],Node) and source(editor.root)==text
print('PASS: Sigma/Pi shorthand, four editable slots, filled expansion and dataset/scalar text preservation')

# Actual physical key routing, history, help, F7, widget and clipped rendering.
import sim_runtime
sim_runtime.configure(root,'/private/tmp/gungos-reductions-'+str(ticks_ms()),
                      root+'/builds/MicroPython/apps_unfrozen',1,'picocalc-pico2w',0,
                      True,False,False,False,'',_network_mode='offline',_audio_mode='silent')
from picoware.system.view_manager import ViewManager
from picoware.system.view import View
from picoware.system.input import Input
from picoware.system import buttons as keys
from engtools.calculator import app
from engtools.calculator.render import Renderer
Input.button=property(lambda self:self._last_button)
vm=ViewManager()
vm.add(View('parent',lambda vm:None,lambda vm:True,lambda vm:None));vm.switch_to('parent')
app.show(vm); calc=app._active

def key(button):
    vm.input_manager._last_button=button
    vm.run()

def text(string):
    for ch in string: key(vm.input_manager._key_to_button(ord(ch)))

for kind, expected in (('sum',55),('prod',14400)):
    text(kind+'() ')
    assert calc.editor.parents[-1][2]==1
    key(keys.BUTTON_F6); assert calc.error=='Complete the highlighted slot'
    text('1'); key(keys.BUTTON_TAB); text('5'); key(keys.BUTTON_TAB)
    text('k^ '); text('2')
    snapshot=source(calc.editor.root)
    key(keys.BUTTON_F9); key(keys.BUTTON_F9)
    assert source(calc.editor.root)==snapshot
    calc.draw()
    sim_runtime.lcd_screenshot('/private/tmp/gungos-calculator-'+kind+'.bmp')
    key(keys.BUTTON_F6); assert calc.answer==expected and not calc.error
    key(keys.BUTTON_UP); assert source(calc.editor.root)==snapshot
    key(keys.BUTTON_F10)
from engtools.calculator.catalogue import location
group,item=location('sum')
key(keys.BUTTON_F7);calc.selected=group;key(keys.BUTTON_CENTER);calc.selected=item;key(keys.BUTTON_CENTER)
assert calc.editor.root[0].kind=='sum' and calc.editor.parents[-1][2]==1
key(keys.BUTTON_F10)
text('sum() ');text('1');key(keys.BUTTON_TAB);text('5');key(keys.BUTTON_TAB)
text('frac() ');text('k');key(keys.BUTTON_TAB);text('2')
calc.draw(); sim_runtime.lcd_screenshot('/private/tmp/gungos-calculator-sum-fraction.bmp')

class Surface:
    def get_font(self,size): return vm.draw.get_font(size)
    def _text(self,x,y,char,color,font):
        f=self.get_font(font)
        assert 40<=x and x+f.width+f.spacing<=303 and 215<=y and y+f.height<=284
    def _line(self,x1,y1,x2,y2,color):
        assert 40<=x1<303 and 40<=x2<303 and 215<=y1<284 and 215<=y2<284
    def _fill_rectangle(self,x,y,w,h,color):
        assert 40<=x and x+w<=303 and 215<=y and y+h<=284
for kind in ('sum','prod'):
    for font in (0,1,2):
        editor=Editor();type_editor(editor,kind+'() ')
        r=Renderer(Surface(),(40,215,303,284))
        for _ in range(5):
            box=r.expression(editor.root,20,190,font,editor=editor,follow=True)
            assert 40<=r.cursor[0]<303 and 215<=r.cursor[1]<284
            editor.tab()
widget=Calculator(True);widget.start(vm);widget.editor.load(clone(calc.editor.root))
widget.draw();sim_runtime.lcd_screenshot('/private/tmp/gungos-calculator-sum-widget.bmp')
widget.stop(vm)
key(vm.input_manager._key_esc)
assert vm.current_view.name=='parent'
print('PASS: Sigma/Pi keys, F7, history, help preservation, nested rendering, clipping and widget')
