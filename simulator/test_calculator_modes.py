"""Six-mode calculator numerics, transactional errors and physical input routes."""
import os,sys,math
from time import ticks_ms
root=os.getcwd()
sys.path.insert(0,root+'/src/MicroPython')
sys.path.insert(0,root+'/simulator/hardware')
sys.path.insert(0,root+'/builds/MicroPython/apps_unfrozen')
from engtools.numerics import matrices as m,equations as eq
from engtools.calculator.base_n import IntegerParser,display
from engtools.calculator.app import Calculator

def close(a,b,tolerance=3e-4): assert abs(a-b)<=tolerance*(1+abs(b)),(a,b)
def result(job):
    records=list(job)
    return records[-1]

for expression,lower,upper,guess,expected in (
    ('x^2=2',0,2,1,math.sqrt(2)),('sin(x)=0.5',0,90,30,30),
    ('x=3',-10,10,0,3),('x^2=0',-2,2,0.3,0),('2x+a=0',-10,10,0,-2)):
    record=result(eq.root_job(expression,lower,upper,guess,{'a':4}))
    close(record['root'],expected,0.002)
    assert record['residual']<1e-4
for expression in ('1/x=0','x^2=-1','__import__(x)=0'):
    try: result(eq.root_job(expression,-2,2,1))
    except (ValueError,ZeroDivisionError): pass
    else: raise AssertionError('Invalid equation accepted: '+expression)
for coefficients,expected in (([1,0,-1],[-1,1]),([1,0,1],[-1j,1j]),
                              ([1,-6,11,-6],[1,2,3]),([1,0,-5,0,4],[-2,-1,1,2]),
                              ([1,10000,1],[-9999.9999,-0.0001])):
    roots=result(eq.polynomial_job(coefficients))['roots']
    assert len(roots)==len(expected)
    remaining=list(expected)
    for value in roots:
        nearest=min(range(len(remaining)),key=lambda i:abs(value-remaining[i]))
        close(value,remaining.pop(nearest))
a=m.matrix([[4,1],[1,3]])
b=m.matrix([[1],[2]])
x=m.solve(a,b)
close(x[0,0],1/11); close(x[1,0],7/11)
close(m.determinant(a),11)
inverse=m.inverse(a)
from ulab import numpy as np
product=np.dot(a,inverse)
for i in range(2):
    for j in range(2): close(product[i,j],1 if i==j else 0)
assert m.power(a,0)[0,0]==1
for values in ([[1,2],[2,4]],[[0,0],[0,1]]):
    try: m.inverse(m.matrix(values))
    except ValueError: pass
    else: raise AssertionError('Singular matrix accepted')
try: m.matrix([[0]*5]*5)
except ValueError: pass
else: raise AssertionError('Oversized matrix accepted')
for text,base,bits,signed,expected in (
    ('0xFFFFFFFF+1',10,32,True,0),('0x80000000',10,32,True,-2147483648),
    ('0xFFFFFFFF',10,32,False,4294967295),('FF AND 0F',16,32,False,15),
    ('1010 XOR 0011',2,8,False,9),('NOT 0',10,8,False,255),
    ('-7/3',10,32,True,-2),('-7%3',10,32,True,-1),
    ('0x80000000>>1',10,32,True,-1073741824),('0x80000000>>1',10,32,False,1073741824),
    ('(2+3)*4',10,16,True,20)):
    assert IntegerParser(text,{'Ans':0},base,bits,signed).calculate()[0]==expected,text
assert display(-1,16,32,True)=='FFFFFFFF'
for text in ('1.2','1<<32','1/0','1<<-1','__import__(x)'):
    variables={'Ans':42}
    try: IntegerParser(text,variables).calculate()
    except (ValueError,ZeroDivisionError): pass
    else: raise AssertionError('Invalid Base-N input accepted: '+text)
    assert variables=={'Ans':42}
print('PASS: equation/polynomial roots, native QR/inverse and exact 32-bit Base-N')

import sim_runtime
sim_runtime.configure(root,'/private/tmp/picoware-six-modes-'+str(ticks_ms()),root+'/builds/MicroPython/apps_unfrozen',1,'picocalc-pico2w',0,True,False,False,False,'',_network_mode='offline',_audio_mode='silent')
from picoware.system.view_manager import ViewManager
from picoware.system.view import View
from picoware.system.input import Input
from picoware.system import buttons as k
from engtools.calculator import app
Input.button=property(lambda self:self._last_button)
vm=ViewManager()
vm.add(View('parent',lambda vm:None,lambda vm:True,lambda vm:None));vm.switch_to('parent')
app.show(vm)
calc=app._active
def key(button): vm.input_manager._last_button=button;vm.run()
def text(value):
    for char in value: key(vm.input_manager._key_to_button(ord(char)))
def mode(index):
    key(k.BUTTON_F2);calc.selected=index;key(k.BUTTON_CENTER)
mode(2)
solver=calc.workspace()
key(k.BUTTON_CENTER)
assert solver.page=='equation'
key(k.BUTTON_F5)
for _ in range(80):
    key(k.BUTTON_NONE)
    if solver.job is None: break
assert solver.page=='results';close(calc.answer,math.sqrt(2))
vm.draw.screenshot('/private/tmp/picoware-solver-results.bmp')
key(vm.input_manager._key_esc)
solver.expression='x^2=3';key(k.BUTTON_F5)
key(vm.input_manager._key_esc)
assert solver.job is None and 'Cancelled' in calc.error
mode(4)
base=calc.workspace()
text('0xFFFFFFFF');key(k.BUTTON_CENTER)
assert base.value==-1 and calc.variables['Ans']==-1
key(k.BUTTON_F3);key(k.BUTTON_RIGHT)
assert base.base==16
key(vm.input_manager._key_esc)
text('FF AND 0F');key(k.BUTTON_CENTER)
assert base.value==15
vm.draw.screenshot('/private/tmp/picoware-base-n.bmp')
mode(5)
matrix=calc.workspace()
key(k.BUTTON_F3);key(k.BUTTON_CENTER);key(k.BUTTON_CENTER)
assert matrix.page=='cells' and matrix.matrices['MatA'].shape==(2,2)
key(k.BUTTON_CENTER);key(k.BUTTON_F5);text('4');key(k.BUTTON_CENTER)
assert matrix.matrices['MatA'][0,0]==4
matrix.matrices['MatA']=a
key(vm.input_manager._key_esc)
text('inv(MatA)');key(k.BUTTON_CENTER)
assert matrix.page=='result'
close(matrix.result[0,0],3/11)
vm.draw.screenshot('/private/tmp/picoware-matrix-result.bmp')
key(k.BUTTON_CENTER);text('det(MatA)+1');key(k.BUTTON_CENTER)
close(calc.answer,12)
old=np.array(matrix.result) if matrix.result is not None else None
text('MatB=inv(identity(2)*0)');key(k.BUTTON_CENTER)
assert calc.error and 'MatB' not in matrix.matrices
mode(0)
assert calc.mode==0 and calc.page=='calc'
key(vm.input_manager._key_esc)
assert app._active is None and vm.current_view.name=='parent'
print('PASS: all six mode routes, solver cancellation, matrix cells/results and Base-N controls')
