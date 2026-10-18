"""Lenia FFT correctness, stable seed, atomic updates and native widget controls."""
import os,sys
from time import ticks_ms
root=os.getcwd()
for path in ('src/MicroPython','simulator/hardware','builds/MicroPython/apps_unfrozen','builds/MicroPython/apps_unfrozen/misc/screensavers'):
    sys.path.insert(0,root+'/'+path)
import sim_runtime
sd='/private/tmp/gungos-lenia-test-'+str(ticks_ms())
preview='/private/tmp/gungos-lenia-previews'
sim_runtime.configure(root,sd,root+'/builds/MicroPython/apps_unfrozen',1,'picocalc-pico2w',0,True,False,False,False,'',_network_mode='offline',_audio_mode='silent',_sd_profile='clean')
sim_runtime.mkdir_p(preview)
from engtools.system.lenia import Field,DEFAULTS,clean,validate,fft2,np
from picoware.system.view_manager import ViewManager
from picoware.system.settings import Settings
from picoware.system.storage import Storage
from picoware.system import buttons as k
from picoware.gui.widget import WidgetDraw,WidgetContext
import Lenia

# Round trip includes strided column transforms and the 1/N^2 inverse scaling.
n=16
real=np.zeros((n,n));imag=np.zeros((n,n))
for y in range(n):
    for x in range(n):real[y,x]=((x*7+y*11)%19)/19
original=real.copy()
for _ in fft2(real,imag):pass
for _ in fft2(real,imag,True):pass
assert float(np.max(abs(real-original)))<2e-6
assert float(np.max(abs(imag)))<2e-6

# Compare the actual FFT update against a direct circular convolution. This
# checks centering, normalization, wraparound, growth and clipping together.
o=DEFAULTS.copy();o.update(size=16,radius=4.0)
f=Field(o);f.a[:]=original
kr=f.kernel.copy();ki=np.zeros((n,n))
for _ in fft2(kr,ki,True):pass
from math import exp
expected=np.zeros((n,n))
for y in range(n):
    for x in range(n):
        density=0.0
        for yy in range(n):
            for xx in range(n):density+=float(original[yy,xx])*float(kr[(y-yy)%n,(x-xx)%n])
        growth=2*exp(-0.5*((density-o['mu'])/o['sigma'])**2)-1
        expected[y,x]=min(1,max(0,float(original[y,x])+o['dt']*growth))
job=f.step()
for _ in range(20):next(job)
assert f.generation==0 and bool(np.all(f.a==original))
job.close()
for _ in f.step():pass
assert f.generation==1 and float(np.max(abs(f.a-expected)))<1e-5

# The default small-grid Orbium remains alive without auto-resetting its rules.
f=Field(DEFAULTS);masses=[]
for generation in range(400):
    for _ in f.step():pass
    if generation%50==49:masses.append(float(np.sum(f.a)))
assert all(20<m<40 for m in masses),masses
assert bool(np.all(np.isfinite(f.a))) and float(np.min(f.a))>=0 and float(np.max(f.a))<=1
for shape in ('Polynomial','Gaussian','Step'):
    o.update(kernel=shape,growth=shape,rings=3)
    field=Field(o)
    for _ in field.step():pass
    assert bool(np.all(np.isfinite(field.a)))
assert clean({'size':64,'mu':float('nan'),'sigma':True,'fps':100,'stats':'yes'})['mu']==DEFAULTS['mu']
for key,value in (('sigma',0),('radius',99),('dt',float('inf'))):
    invalid=DEFAULTS.copy();invalid[key]=value
    try:validate(invalid)
    except ValueError:pass
    else:raise AssertionError(key)
invalid=DEFAULTS.copy();invalid['b1']=0
try:Field(invalid)
except ValueError:pass
else:raise AssertionError('Zero kernel accepted')
print('PASS: FFT round trip, direct convolution agreement, periodic edges, atomic generations, 400-step Orbium and parameter guards')

vm=ViewManager();vm._wifi=None
assert Settings(vm.storage).update({'untouched':'keep'})
clock=[0]
Lenia.ticks_ms=lambda:clock[0]
app=Lenia.App(vm)
def key(button,advance=125):
    clock[0]+=advance
    app.run(button)
def finish():
    for _ in range(20):
        if app.job is None:return
        key(k.BUTTON_NONE)
    raise AssertionError('Generation never completed')
def snap(name):sim_runtime.lcd_screenshot(preview+'/'+name+'.bmp')
for _ in range(40):key(k.BUTTON_NONE);finish()
snap('fullscreen')
key(k.BUTTON_SPACE);assert app.paused
before=app.field.a.copy();generation=app.field.generation
key(k.BUTTON_NONE);assert bool(np.all(before==app.field.a))
key(k.BUTTON_N);finish();assert app.paused and app.field.generation==generation+1
options=app.options.copy();key(k.BUTTON_F3)
assert app.options==options and app.field.generation==0 and app.paused
assert not bool(np.all(before==app.field.a))
key(k.BUTTON_F5);assert app.field.generation==0
key(k.BUTTON_F2);assert app.page=='settings'
original=app.options.copy();old_field=app.field
app.row=3;key(k.BUTTON_CENTER)
for char in '0.155':key(vm.input_manager._key_to_button(ord(char)))
key(k.BUTTON_CENTER);assert app.draft['mu']==0.155 and app.options==original
snap('settings')
key(k.BUTTON_F9);assert app.page=='help'
key(k.BUTTON_END);assert app.help_first>0
key(k.BUTTON_HOME);snap('help')
key(k.BUTTON_F9);assert app.page=='settings' and app.row==3
# A failed save or allocation leaves the old live simulation/options intact.
serialize=Storage.serialize
for result in (False,True):
    Storage.serialize=lambda *args,**kwargs:result
    key(k.BUTTON_F2)
    assert app.page=='settings' and app.field is old_field and app.options==original and app.error
    assert 'lenia' not in Settings(vm.storage).settings
Storage.serialize=serialize
factory=Lenia.Field
Lenia.Field=lambda options:(_ for _ in ()).throw(MemoryError())
app.draft['size']=64
assert not app.apply() and app.field is old_field and app.options==original
Lenia.Field=factory;app.draft['size']=32
key(k.BUTTON_F2)
assert app.page=='view' and app.options['mu']==0.155
saved=Settings(vm.storage).settings
assert saved['lenia']['mu']==0.155 and saved['untouched']=='keep'
fresh=Lenia.App(vm);assert fresh.options['mu']==0.155;fresh.stop()
# Editing and canceling settings is transactional; random rules are draft-only.
key(k.BUTTON_F2);key(k.BUTTON_F3)
assert app.options['mu']==0.155 and app.draft!=app.options
key(k.BUTTON_ESCAPE);assert app.options['mu']==0.155
key(k.BUTTON_F2);app.draft['gamma']=1.2
assert app.apply(False) and app.options['gamma']==1.2
assert Settings(vm.storage).settings['lenia']['gamma']==DEFAULTS['gamma']
# Startup fallback retains the saved configuration rather than persisting a
# temporary low-memory choice. A larger grid is available for experimentation.
original_factory=Lenia.Field
Lenia.Field=lambda options:Field(options) if options['size']==16 else (_ for _ in ()).throw(MemoryError())
fallback=Lenia.App(vm)
assert fallback.options['size']==16 and fallback.notice
assert Settings(vm.storage).settings['lenia']['size']==32
fallback.stop();Lenia.Field=original_factory
large=DEFAULTS.copy();large['size']=64
large_field=Field(large)
for _ in large_field.step():pass
assert large_field.generation==1 and large_field.a.itemsize==4
assert float(np.sum(large_field.a))>0
large_field=None
print('PASS: pause/single-step/random/reset, numeric editing, help scrolling, SD failure, allocation failure, cancel and saved/session settings')

# Same entry point adapts to the actual native widget dimensions without scaling.
class Host:
    def __init__(self):self.master,self.focused=vm,True
host=Host();widget=WidgetContext(host,WidgetDraw(vm,238,238))
small=Lenia.App(widget)
assert small.widget and small.field.size==32
small.options['fps']=16;assert small.effective_fps()==8
for _ in range(50):
    clock[0]+=125;small.run(k.BUTTON_NONE)
vm.draw.fill_screen(0);vm.draw._bytearray(0,0,238,238,widget.draw.buffer);snap('widget')
small.run(k.BUTTON_F2)
for index in range(len(Lenia.ROWS)):
    small.row=index;small.dirty=True;small.draw()
small.row=6;small.draw()
vm.draw.fill_screen(0);vm.draw._bytearray(0,0,238,238,widget.draw.buffer);snap('widget-settings')
small.run(k.BUTTON_ESCAPE);small.run(k.BUTTON_ESCAPE)
assert not host.focused and small.field is not None
small.stop();assert small.field is None and small.job is None
app.stop();assert app.field is None
# Managed standalone exit must stop cleanly, without running a freed field.
from picoware.system.view import View
vm.add(View('lenia_parent',lambda v:None,lambda v:True,lambda v:None));vm.switch_to('lenia_parent')
vm.add(View('lenia_test',Lenia.run,Lenia.start,Lenia.stop));vm.switch_to('lenia_test')
assert Lenia._app is not None
vm._button=k.BUTTON_ESCAPE;Lenia.run(vm)
assert vm.current_view.name=='lenia_parent' and Lenia._app is None
assert vm.draw.mode==vm.draw.MODE_PSRAM
print('PASS: 238px native widget, host rate cap, every settings row, focus return and managed standalone cleanup')
print('Screenshots: '+preview)
# Discovery and actual desktop composition use the same SD module, with F3
# focus kept separate from the app's Random button.
from picoware.system.input import Input
from picoware.applications import desktop
Input.button=property(lambda self:self._last_button)
assert Settings(vm.storage).update({'screensaver':'Lenia','theme_color':0x07E0})
vm.selected_color=0x07E0
vm.add(View('desktop_view',desktop.run,desktop.start,desktop.stop));vm.switch_to('desktop_view')
home=desktop._dashboard
assert home.widget.module is not None,home.widget.error
assert home.widget.draw.width==238 and home.widget.draw.height==238
native=home.widget.module._app
assert native.widget and native.vm.selected_color==0x07E0
vm.input_manager._last_button=k.BUTTON_F3;vm.run()
assert home.focus=='widget' and home.widget.focused and native.notice==''
vm.input_manager._last_button=k.BUTTON_F3;vm.run()
assert native.notice=='Random seed'
vm.input_manager._last_button=k.BUTTON_ESCAPE;vm.run()
assert home.focus=='menu' and home.widget.module is not None
home.widget.next_frame=0;home.draw();snap('desktop-widget')
from picoware.applications.applications import screensavers
assert screensavers.start(vm)
assert screensavers._screensavers.item_exists('Lenia')
screensavers.stop(vm)
vm.input_manager._last_button=k.BUTTON_NONE
home.widget.stop();assert native.field is None
print('PASS: standalone menu discovery, real desktop composition, theme propagation and first/subsequent F3 focus/random routing')
