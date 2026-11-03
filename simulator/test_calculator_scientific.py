"""Complex branches, integer helpers, matrix scope, work limits and F7 routes."""
import os,sys,math
root=os.getcwd()
apps=sys.argv[2] if len(sys.argv)>2 else 'builds/MicroPython/apps_unfrozen'
for p in ('src/MicroPython','simulator/hardware',apps):sys.path.insert(0,root+'/'+p)
from engtools.calculator.evaluate import calculate,Parser,Evaluator,native_function
from engtools.calculator.scientific import complex_inverse,tangent_pole,complex_sqrt,complex_log
from engtools.calculator.app import Calculator
if len(sys.argv)>2:
    import engtools.calculator.scientific as scientific
    assert scientific.__file__.endswith('.mpy'),scientific.__file__
from engtools.calculator.workspaces import MatrixWorkspace
from engtools.numerics import matrices

def close(a,b,rtol=1e-5):
    assert abs(a-b)<=rtol*abs(b)+5e-38,(a,b)

def value(text,angle='RAD',complex_mode=False,variables=None):
    return calculate(text,variables if variables is not None else {},angle,complex_mode)[0]

def reject(text,contains=None,angle='RAD',complex_mode=False):
    variables={'Ans':37,'a':13};before=dict(variables)
    try:value('a='+text,angle,complex_mode,variables)
    except (ValueError,TypeError,ZeroDivisionError,OverflowError) as e:
        if contains:assert contains in str(e),(text,str(e))
    else:raise AssertionError('Accepted '+text)
    assert variables==before

count=0
with open(sys.argv[1]) as f:
    for line in f:
        name,x,y,re,im=line.rstrip().split('\t');z=complex(x+('' if y.startswith('-') else '+')+y+'j')
        result=complex_sqrt(z) if name=='sqrt' else complex_log(z) if name in ('ln','log') else complex_inverse(name,z)
        if name=='log':result/=math.log(10)
        try:close(result.real,float(re));close(result.imag,float(im))
        except AssertionError:
            print('reference mismatch:',name,x,y,result,re,im);raise
        for a,b in ((result.real,float(re)),(result.imag,float(im))):
            if a==0 and b==0:assert math.copysign(1,a)==math.copysign(1,b),(name,x,y,result,re,im)
        # The actual evaluator extends out-of-domain real arguments too, and
        # scales both result components for DEG.
        for angle in ('RAD','DEG'):
            actual=value(name+'(z)',angle,True,{'z':z});factor=180/math.pi if angle=='DEG' and name in ('asin','acos','atan') else 1
            close(actual.real,float(re)*factor);close(actual.imag,float(im)*factor)
        count+=1
for text in ('atan(i)','atan(-i)'):reject(text,'singular',complex_mode=True)
close(value('asin(2)',complex_mode=True).imag,math.acosh(2))
close(value('sqrt(-1)',complex_mode=True).imag,1)
close(value('ln(-1)',complex_mode=True).imag,math.pi)
close(value('abs(z)',variables={'z':complex(1e-30,1e-30)}),math.sqrt(2)*1e-30)
close(value('logb(2,z)',complex_mode=True,variables={'z':complex(0,1e-30)}).real,math.log(1e-30)/math.log(2))
reject('asin(2)');reject('acos(2)')
for angle,texts in (('DEG',('tan(90)','tan(-90)','tan(270)','tan(90+180*1000)')),
                    ('RAD',('tan(pi/2)','tan(3*pi/2)','tan(-pi/2)'))):
    for text in texts:reject(text,'undefined',angle)
for text,angle in (('tan(89.99999)','DEG'),('tan(90.00001)','DEG'),('tan(1.5707962)','RAD'),('tan(1.5707965)','RAD')):
    assert abs(value(text,angle))>100000,text
assert native_function(Parser('tan(x)').parse()[1],{}) is None
assert not tangent_pole(complex(90,1),'DEG')
for text,want in (('ncr(5,2)',10),('npr(5,2)',20),('ncr(0,0)',1),('npr(0,0)',1),
                  ('ncr(100,98)',4950),('ncr(34,17)',2333606220),('cbrt(-8)',-2),
                  ('root(3,-27)',-3),('root(-3,-8)',-.5),('root(4,16)',2),('cbrt(0)',0),
                  ('ncr(16777216,1)',16777216),('sum(k,1,5,ncr(5,k))',31)):
    got=value(text)
    if want==0:assert got==0
    else:close(got,want)
assert isinstance(value('ncr(34,17)'),int)
for text,why in (('ncr(5,6)','requires'),('npr(5,-1)','integer'),('ncr(1.5,1)','integer'),
                 ('ncr(1000,500)','range'),('npr(100,100)','range'),('ncr(3000,1500)','work limit'),
                 ('npr(3,1,1)','argument'),('root(0,8)','degree'),('root(2,-4)','Even'),
                 ('root(1.5,8)','degree'),('root(-2,0)','nonzero'),('cbrt(i)','real')):
    reject(text,why,complex_mode='i' in text)
# Shared evaluator budget includes helper loops, even when the answer is tiny.
reject('sum(k,1,1024,ncr(128,64)/ncr(128,64))','work limit')
calc=Calculator();calc.angle='RAD';calc.variables={'k':99,'x':77,'Ans':11}
w=MatrixWorkspace(calc);w.matrices['MatA']=matrices.matrix([[2,0],[0,3]])
for text,want in (('sum(k,1,3,k*trace(MatA))',30),('prod(k,1,3,k+det(MatA))',504),
                  ('sum(k,1,2,sum(k,1,3,k*trace(MatA))+k)',63),
                  ('int(0,1,x*trace(MatA))',2.5),('sum(k,1,3,int(0,1,k*x*trace(MatA)))',15),
                  ('int(0,1,sum(k,1,3,k*x*trace(MatA)))',15),
                  ('sum(k,1,3,trace(k*MatA))',30),('sum(k,1,3,trace(identity(k)))',6),('sin(sum(k,1,3,trace(MatA)))',math.sin(15))):
    close(w.evaluate(text),want,3e-5)
assert calc.variables=={'k':99,'x':77,'Ans':11}
for text,why in (('sum(k,1,600,det(MatA))','Matrix operation limit'),
                 ('sum(k,1,3,MatA)','scalars'),('int(0,1,MatA)','real scalar'),
                 ('sum(MatA,1,3,trace(MatA))','reserved'),('sum(trace,1,3,trace(MatA))','reserved'),
                 ('int(0,1,int(0,1,trace(MatA)))','Nested'),('sum(k,1,3,trace(MatA))+k',None)):
    # Last expression uses the original stored k after the reduction, so it is valid.
    if why is None:close(w.evaluate(text),114);continue
    try:w.evaluate(text)
    except (ValueError,TypeError) as e:assert why in str(e),(text,str(e))
    else:raise AssertionError(text)
print('PASS:',count,'complex references, poles/neighbours, real roots, exact combinatorics, matrix scopes and shared limits')

# Catalogue entry through real keys, including nested slots and widget dimensions.
import sim_runtime
from time import ticks_ms
sim_runtime.configure(root,'/private/tmp/gungos-calc-science-'+str(ticks_ms()),root+'/'+apps,
    1,'picocalc-pico2w',0,True,False,False,False,'',_network_mode='offline',_audio_mode='silent')
from picoware.system.view_manager import ViewManager
from picoware.system.view import View
from picoware.system.input import Input
from picoware.system import buttons as keys
from engtools.calculator import app
from engtools.calculator.editor import source
Input.button=property(lambda self:self._last_button)
vm=ViewManager();vm.add(View('parent',lambda vm:None,lambda vm:True,lambda vm:None));vm.switch_to('parent')
app.show(vm);calc=app._active

def key(button):vm.input_manager._last_button=button;vm.run()
def text(s):
    for ch in s:key(vm.input_manager._key_to_button(ord(ch)))
def choose(function):
    from engtools.calculator.catalogue import location
    group,item=location(function)
    key(keys.BUTTON_F7);calc.selected=group;key(keys.BUTTON_CENTER)
    calc.selected=item;calc.draw();key(keys.BUTTON_CENTER)
for function,arguments,want in (('ncr','5,2',10),('npr','5,2',20),('cbrt','-8',-2),('root','3,-27',-3)):
    choose(function);assert source(calc.editor.root)==function+'()'
    text(arguments);assert source(calc.editor.root)==function+'('+arguments+')'
    key(keys.BUTTON_F6);close(calc.answer,want);assert not calc.error
# A function inside an exponent keeps its structured parent and survives help.
text('2^ ');choose('ncr')
text('5,2');saved=source(calc.editor.root);key(keys.BUTTON_F9);key(keys.BUTTON_F9)
assert source(calc.editor.root)==saved and calc.editor.parents
key(keys.BUTTON_F6);assert calc.answer==1024
# Insertion over the size limit must not leave a half-written function.
text('1'*380);saved=source(calc.editor.root)
choose('ncr')
assert calc.error and source(calc.editor.root)==saved
vm.back()
from picoware.gui.widget import WidgetHost
host=WidgetHost(vm,(132,114,184,184));host.load('Calculator Widget');assert not host.error
widget=app._active;widget.open_page('templates')
from engtools.calculator.catalogue import location
group,item=location('root');widget.catalogue_group=group;widget.selected=item;widget.draw()
host.context.input_manager._last_button=keys.BUTTON_CENTER;widget.run(host.context)
assert source(widget.editor.root)=='root()'
host.stop()
print('PASS: F7 scientific functions, evaluation, nested draft/help, size rejection and compact widget')
