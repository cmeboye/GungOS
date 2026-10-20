"""Core benchmark: every stage completes, cleans up and leaves the system as found."""
import os,sys
from time import ticks_ms
root=os.getcwd()
sys.path.insert(0,root+'/src/MicroPython')
sys.path.insert(0,root+'/simulator/hardware')
import sim_runtime
sim_runtime.configure(root,'/private/tmp/gungos-core-benchmark-test-'+str(ticks_ms()),
                      root+'/builds/MicroPython/apps_unfrozen',1,'picocalc-pico2w',
                      0,True,False,False,False,'',_network_mode='offline',_audio_mode='silent')
sim_runtime.mkdir_p(sim_runtime.sd_root)
from picoware.system.view_manager import ViewManager
from picoware.system import buttons as k
vm=ViewManager();vm._wifi=None
sys.path.insert(0,root+'/builds/MicroPython/apps_unfrozen')  # engtools, as on the SD card
from engtools.bench import core as bench
import picoware.gui.alert,picoware.gui.list,picoware.system.settings
before={name:sys.modules[name] for name in ('picoware.gui.alert','picoware.gui.list','picoware.system.settings')}
mode=vm.draw.mode
def step(button=-1):
    vm._button=button;bench.run(vm)
def finish():
    for _ in range(len(bench._plan)+2):step()
    assert bench._stage>len(bench._plan)
    return vm.storage.read(bench.RESULT_PATH)
assert bench.start(vm)
step();assert bench._stage==-1,'Nothing runs before Enter'
assert bench._rounds==10 and not bench._sd_writes,'Defaults: 10 rounds, no SD writes'
step(k.BUTTON_F2);assert bench._rounds==3
step(k.BUTTON_F3);assert bench._sd_writes
step(k.BUTTON_CENTER)
plan=bench._plan
assert plan[:2]==((1,0),(1,1)) and plan[-1]==(3,bench.LAST),'System first, memory last'
assert plan.count((1,bench.SD_STAGE))==1 and sum(1 for _,i in plan if i==bench.SD_STAGE)==1,'SD step once'
assert sum(1 for _,i in plan if i==2)==3,'Timing steps every round'
report=finish()
assert 'Status: complete, 3 rounds' in report
assert 'failed:' not in report and 'ran out of memory' not in report,report
for line in ('Processor clock, reported','Heap total','Largest free block at start','Python method call',
             'Garbage collection, full','Import picoware.gui.list (frozen)','Import engtools.bench.models (SD .mpy)',
             'Fill rectangle 32x32, SRAM','Swap, nothing changed, PSRAM','Menu of 30 entries, draw',
             'Home screen, idle frame','On-screen keyboard frame, draw','Resource snapshot','Settings load from SD',
             'PSRAM write, 4 KB pieces','PSRAM copy 32 KB','SD write 64 KB file in one call','SD append 512 bytes',
             'SD read 64 KB in 4 KB pieces','SD rename','SD delete small file','Heap free at end'):
    assert line in report,line
line=[l for l in report.split('\n') if l.startswith('Python method call: ')][0]
assert ' ns (min ' in line and 'spread ' in line and '3 rounds' in line,line
line=[l for l in report.split('\n') if l.startswith('Swap, nothing changed, PSRAM: ')][0]
assert '3 rounds, 0 rows' in line,line
line=[l for l in report.split('\n') if l.startswith('SD rename (there and back): ')][0]
assert 'rounds' not in line,line
assert report.count('Heap total:')==1 and 'Heap total: ' in report
print('PASS: %d steps over 3 rounds, %d result lines with mean, min, max and spread'%(len(plan),report.count('\n')-2))
assert not vm.storage.exists(bench.SCRATCH),'Scratch folder is removed'
assert vm.draw.mode==mode,'Screen mode is restored'
assert vm._keyboard is None,'The benchmark does not keep a keyboard'
for name,module in before.items():
    assert sys.modules[name] is module,name
    parent,child=name.rsplit('.',1)
    assert getattr(sys.modules[parent],child) is module,name
assert 'engtools.bench.models' not in sys.modules
print('PASS: scratch folder removed; screen mode, keyboard and re-imported modules restored')
# Default run: no SD writes, and the report says so.
assert bench.start(vm)
step(k.BUTTON_F2);step(k.BUTTON_F2);assert bench._rounds==1
step(k.BUTTON_CENTER)
assert all(i!=bench.SD_STAGE for _,i in bench._plan)
report=finish()
assert 'SD card: skipped (writes off' in report and 'SD write 64 KB' not in report
print('PASS: SD writes are off by default and reported as skipped')
# Cancelling mid-run keeps what was measured.
assert bench.start(vm)
step(k.BUTTON_CENTER);step();step();step()
vm.back=lambda *a,**kw:None
step(k.BUTTON_ESCAPE)
report=vm.storage.read(bench.RESULT_PATH)
assert 'Status: cancelled in round 1 of 10' in report and 'Heap total' in report and 'Python method call' in report
assert vm.draw.mode==mode
print('PASS: Esc keeps completed stages and restores the screen mode')
