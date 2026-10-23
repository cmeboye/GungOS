"""Known statistics, bounded data editing, calculator routes and CSV failures."""
import os,sys,math
from time import ticks_ms
root = os.getcwd()
sys.path.insert(0,root+'/src/MicroPython')
sys.path.insert(0,root+'/simulator/hardware')
sys.path.insert(0,root+'/builds/MicroPython/apps_unfrozen')
from engtools.numerics.statistics import Dataset,MAX_ROWS
from engtools.calculator.evaluate import calculate
from engtools.calculator.editor import source

def close(actual,expected,tolerance=2e-5):
    assert actual is not None and abs(actual-expected) <= tolerance*max(1,abs(expected)), (actual,expected)

def data(xs,ys=None,weights=None):
    d = Dataset(ys is not None)
    d.rows = len(xs)
    for row,x in enumerate(xs):
        d.set(row,'X',x)
        if ys is not None: d.set(row,'Y',ys[row])
        if weights is not None: d.set(row,'Freq',weights[row])
    d.set_frequency(weights is not None)
    return d

d = data([1,2,3,4])
s = d.summary()['X']
for field,value in (('n',4),('sum',10),('sum2',30),('mean',2.5),('median',2.5),('q1',1.75),
                    ('q3',3.25),('iqr',1.5),('pvar',1.25),('var',5/3),('range',3)):
    close(s[field],value)
assert d.summary()['X'] is s
assert list(d.x[:4]) == [1,2,3,4], 'Sorting changed input order'
w = data([1,3],[2,6],[2,1])
s = w.summary()['X']
for field,value in (('n',3),('mean',5/3),('pvar',8/9),('var',4/3),('median',1),('q1',1),('q3',2)):
    close(s[field],value)
close(w.fit()['slope'],2); close(w.predict(4),8)
w.set(0,'Freq',9999); w.set(1,'Freq',9999)
assert w.summary()['n'] == 19998 and len(w.x) == 128
close(w.summary()['X']['median'],2)
w.set_frequency(False)
assert w.summary()['n'] == 2
w.set_frequency(True); w.set(1,'Freq',0)
assert w.summary()['n'] == 9999
single = data([5])
assert single.summary()['X']['std'] is None and single.summary()['X']['pstd'] == 0
pair = data([1,2,3],[3,5,7])
fit = pair.fit()
for field,value in (('slope',2),('intercept',1),('corr',1),('r2',1),('sse',0),('residual_sd',0)):
    close(fit[field],value)
close(pair.pair_statistics()['cov'],2)
close(pair.predict(4),9)
offset = data([1000001,1000002,1000003],[3,5,7])
close(offset.summary()['X']['std'],1)
close(offset.fit()['slope'],2)
close(offset.predict(1000004),9)
negative = data([1,2,3],[7,5,3])
close(negative.fit()['corr'],-1); close(negative.fit()['slope'],-2)
constant_x = data([2,2],[1,3])
assert constant_x.pair_statistics()['cov'] == 0 and constant_x.pair_statistics()['corr'] is None
try: constant_x.fit()
except ValueError: pass
else: raise AssertionError('Singular fit accepted')
constant_y = data([1,2],[3,3])
assert constant_y.fit()['r2'] is None and constant_y.fit()['corr'] is None
close(constant_y.predict(100),3)
two = data([1,2],[3,5])
assert two.fit()['residual_sd'] is None
for text,value in (('mean(X)+2*std(X)',2+2),('slope()',2),('intercept()',1),
                   ('corr(X,Y)',1),('cov(X,Y)',2),('predict(4)',9),('n(X)',3),('min(X)',1),('max(Y)',7)):
    close(calculate(text,{},statistics=pair)[0],value)
variables = {'Ans':1}
close(calculate('a=mean(X)',variables,statistics=pair)[0],2)
assert variables['a'] == 2
for text in ('X=3','Y=4','mean(2)','std(Y)','mean(X)','corr(X,X)'):
    context = single if text in ('std(Y)','corr(X,X)') else None
    before = dict(variables)
    try: calculate(text,variables,statistics=context)
    except ValueError: pass
    else: raise AssertionError('Invalid statistics expression accepted: '+text)
    assert variables == before
before = w.to_csv()
for value in (-1,0.5,10000,float('inf'),complex(1,0)):
    try: w.set(0,'Freq',value)
    except (ValueError,TypeError): pass
    else: raise AssertionError('Invalid frequency accepted')
    assert w.to_csv() == before
for value in (float('nan'),float('inf'),complex(1,0)):
    try: w.set(0,'X',value)
    except (ValueError,TypeError): pass
    else: raise AssertionError('Invalid measurement accepted')
    assert w.to_csv() == before
rows = data([1,2],[3,4])
rows.delete_row(0)
assert rows.rows == 1 and rows.get(0,'X') == 2 and rows.get(0,'Y') == 4
rows.delete_row(0)
assert rows.rows == 1 and rows.get(0,'X') is None
rows.insert_row(0); rows.set(0,'X',2)
try: rows.summary()
except ValueError as exc: assert 'Complete row' in str(exc)
else: raise AssertionError('Incomplete pair was silently ignored')
rows.clear(); assert rows.rows == 1 and rows.get(0,'X') is None
full = Dataset()
full.rows = MAX_ROWS
full.set(127,'X',7)
before = full.to_csv()
try: full.insert_row(128)
except ValueError: pass
else: raise AssertionError('Row limit ignored')
assert full.to_csv() == before
roundtrip = Dataset.from_csv(w.to_csv())
assert roundtrip.to_csv() == w.to_csv()
assert roundtrip.summary() == w.summary()
imported = Dataset.from_csv('x,y,freq\n1,3,2\n2,5,1\n')
assert imported.paired and imported.frequency and imported.summary()['n'] == 3
for csv in ('X\nnan\n','X\ninf\n','X,Freq\n1,-1\n','X,Y\n1,2,3\n',
            'X\n'+'1\n'*129,'# Picoware statistics v1; frequency=9\nX\n1\n'):
    try: Dataset.from_csv(csv)
    except ValueError: pass
    else: raise AssertionError('Invalid CSV accepted')
print('PASS: weighted summaries/quartiles, centred fits, undefined results, row limits and CSV validation')

import sim_runtime
sd = '/private/tmp/picoware-statistics-test-'+str(ticks_ms())
sim_runtime.configure(root,sd,root+'/builds/MicroPython/apps_unfrozen',1,'picocalc-pico2w',
                      0,True,False,False,False,'',_network_mode='offline',_audio_mode='silent')
from picoware.system.view_manager import ViewManager
from picoware.system.view import View
from picoware.system.input import Input
from picoware.system import buttons as k
from picoware.system.storage import Storage
Input.button = property(lambda self:self._last_button)
import PicoLAB as lab
from engtools.calculator import app
from engtools.calculator.statistics import OPTIONS,SAVE_DIRECTORY
vm = ViewManager()
vm.add(View('parent',lambda vm:None,lambda vm:True,lambda vm:None)); vm.switch_to('parent')
vm.add(View('lab',lab.run,lab.start,lab.stop)); vm.switch_to('lab')
lab._enter('tools');lab._selected = next(i for i,row in enumerate(lab.MENUS['tools']) if row[0]=='calculator')

def key(button):
    vm.input_manager._last_button = button
    vm.run()

def text(value):
    for char in value: key(vm.input_manager._key_to_button(ord(char)))

key(k.BUTTON_CENTER)
calc = app._active
key(k.BUTTON_F2); key(k.BUTTON_RIGHT); key(k.BUTTON_CENTER)
assert calc.page == 'stats' and calc.statistics.page == 'start'
ws = calc.statistics
vm.draw.screenshot('/private/tmp/picoware-statistics-start.bmp')
key(k.BUTTON_CENTER)
assert ws.page == 'data' and not ws.dataset.paired
assert not vm.storage.exists(SAVE_DIRECTORY), 'Automatic SD writes occurred'
text('1'); key(k.BUTTON_CENTER)
assert ws.dataset.get(0,'X') == 1 and ws.row == 1
text('sqrt() '); text('4'); key(k.BUTTON_CENTER)
assert ws.dataset.get(1,'X') == 2
text('3'); key(k.BUTTON_CENTER)
assert ws.dataset.get(2,'X') == 3
vm.draw.screenshot('/private/tmp/picoware-statistics-data.bmp')
key(k.BUTTON_F4)
assert ws.page == 'summary'
key(k.BUTTON_DOWN)
vm.draw.screenshot('/private/tmp/picoware-statistics-summary.bmp')
key(k.BUTTON_CENTER)
assert calc.page == 'calc' and calc.variables['Ans'] == 2
text('a=mean(X)+2*std(X)'); key(k.BUTTON_CENTER)
close(calc.answer,4); assert calc.variables['a'] == 4
key(k.BUTTON_F3); assert calc.page == 'stats' and ws.page == 'data'
key(k.BUTTON_UP); key(k.BUTTON_CENTER)
assert ws.editing
key(vm.input_manager._key_esc)
assert not ws.editing and ws.page == 'data'
text('1/ '); text('0'); key(k.BUTTON_CENTER)
assert ws.editing and calc.error and ws.dataset.get(2,'X') == 3
key(vm.input_manager._key_esc)
# F7/F8 act on the cell editor, preserving the calculator's own draft.
calc.editor.load(list('9+9'))
key(k.BUTTON_F7)
assert calc.page == 'templates' and ws.editing
calc.selected = 2; key(k.BUTTON_CENTER)
assert calc.page == 'stats' and ws.editor.root[0].kind == 'sqrt'
text('9'); key(k.BUTTON_CENTER)
assert ws.dataset.get(2,'X') == 3 and not ws.editing
assert source(calc.editor.root) == '9+9'
text('log_ '); text('2'); key(k.BUTTON_TAB)
assert ws.editing and ws.editor.parents[-1][2] == 1 and not ws.editor.row
text('5'); key(k.BUTTON_RIGHT); key(k.BUTTON_TAB)
assert not ws.editing
close(ws.dataset.get(3,'X'),2.321928)
key(k.BUTTON_F6); ws.selected = OPTIONS.index('Frequency'); key(k.BUTTON_CENTER)
assert ws.dataset.frequency and ws.page == 'data'
ws.row,ws.column = 0,1
text('2'); key(k.BUTTON_TAB)
assert ws.dataset.get(0,'Freq') == 2 and ws.row == 1 and ws.column == 0
key(k.BUTTON_F6); ws.selected = OPTIONS.index('Save CSV'); key(k.BUTTON_CENTER)
assert ws.message.startswith('Saved ') and ws.page == 'data'
assert len(vm.storage.listdir(SAVE_DIRECTORY)) == 1
original_csv = ws.dataset.to_csv()
filename = vm.storage.listdir(SAVE_DIRECTORY)[0]
# Falsely successful writes are verified and do not report success or alter RAM.
old_write = Storage.write
Storage.write = lambda self,path,value,mode='w': True
try:
    key(k.BUTTON_F6); ws.selected = OPTIONS.index('Save CSV'); key(k.BUTTON_CENTER)
    assert 'verification' in calc.error and ws.dataset.to_csv() == original_csv
finally: Storage.write = old_write
assert len(vm.storage.listdir(SAVE_DIRECTORY)) == 1
key(k.BUTTON_CENTER)
assert ws.page == 'data' and ws.message.startswith('Saved ') and not calc.error
assert len(vm.storage.listdir(SAVE_DIRECTORY)) == 2
key(vm.input_manager._key_esc)
key(k.BUTTON_F6); ws.selected = OPTIONS.index('Clear dataset'); key(k.BUTTON_CENTER)
assert ws.page == 'confirm'
key(vm.input_manager._key_esc); assert ws.dataset.to_csv() == original_csv
key(k.BUTTON_F6); ws.selected = OPTIONS.index('Load CSV'); key(k.BUTTON_CENTER)
assert ws.page == 'load'
key(k.BUTTON_CENTER)
assert ws.page == 'data' and ws.dataset.to_csv() == original_csv
assert 'Loaded' in ws.message
before = ws.dataset
assert vm.storage.write(SAVE_DIRECTORY+'/bad.csv','X\nnan\n')
try: ws.load('bad.csv')
except ValueError: pass
else: raise AssertionError('Invalid load replaced the dataset')
assert ws.dataset is before
# Failed writes and unavailable SD leave the in-memory dataset usable.
old_write = Storage.write
Storage.write = lambda self,path,value,mode='w': False
try:
    try: ws.save()
    except RuntimeError: pass
    else: raise AssertionError('Failed write reported success')
finally: Storage.write = old_write
old_has_storage = vm.storage._has_storage
vm.storage._has_storage = False
try:
    try: ws.save()
    except RuntimeError: pass
    else: raise AssertionError('Save accepted an unavailable SD card')
finally: vm.storage._has_storage = old_has_storage
assert ws.dataset is before
# Maintain independent 1-variable and 2-variable data across mode/type switches.
saved_one = ws.dataset
key(vm.input_manager._key_esc); assert ws.page == 'start'
key(k.BUTTON_DOWN); key(k.BUTTON_CENTER)
assert ws.dataset.paired and ws.datasets[False] is saved_one
for x,y in ((1,3),(2,5),(3,7)):
    text(str(x)); key(k.BUTTON_TAB)
    text(str(y)); key(k.BUTTON_TAB)
assert ws.dataset.summary()['n'] == 3
vm.draw.screenshot('/private/tmp/picoware-statistics-paired.bmp')
key(k.BUTTON_F5)
assert ws.page == 'fit'
vm.draw.screenshot('/private/tmp/picoware-statistics-fit.bmp')
ws.selected = len(ws.results())-1; key(k.BUTTON_CENTER)
assert ws.predicting and ws.editing
text('4'); key(k.BUTTON_CENTER)
assert not ws.predicting and ws.page == 'fit' and calc.answer == 9
key(k.BUTTON_F2); calc.selected = 0; key(k.BUTTON_CENTER)
assert calc.page == 'calc' and ws.dataset.summary()['n'] == 3
key(k.BUTTON_F2); calc.selected = 1; key(k.BUTTON_CENTER)
assert calc.page == 'stats' and ws.page == 'fit'
key(vm.input_manager._key_esc); key(k.BUTTON_CENTER)
assert ws.dataset is saved_one
# Missing native support is explained in Statistics without breaking the app.
import engtools.numerics.statistics as numeric
old_require = numeric.require
numeric.require = lambda: (_ for _ in ()).throw(RuntimeError('This firmware needs ulab'))
try:
    ws.datasets.pop(True)
    key(vm.input_manager._key_esc); key(k.BUTTON_DOWN); key(k.BUTTON_CENTER)
    assert calc.page == 'stats' and 'ulab' in calc.error
finally: numeric.require = old_require
key(k.BUTTON_F2); calc.selected = 0; key(k.BUTTON_CENTER)
key(vm.input_manager._key_esc)
assert vm.current_view.name == 'lab' and calc.statistics is None and app._active is None
print('PASS: table keys/math slots, summary/fit/Ans, mode retention, explicit CSV save/load and missing firmware')
