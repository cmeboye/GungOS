"""On-device engineering benchmark: real renders, checkpoints and recovery."""
import os, sys, gc, json
from time import ticks_ms
root=os.getcwd()
for part in ('src/MicroPython','simulator/hardware','builds/MicroPython/apps_unfrozen'):
    sys.path.insert(0,root+'/'+part)
import sim_runtime
sim_runtime.configure(root,'/private/tmp/gungos-engtool-benchmark-'+str(ticks_ms()),
                      root+'/builds/MicroPython/apps_unfrozen',1,'picocalc-pico2w',
                      0,True,False,False,False,'',_network_mode='offline',_audio_mode='silent',_sd_profile='clean')
from picoware.system.view_manager import ViewManager
from picoware.system import buttons as k
from engtools.bench import render as b, models
from engtools import session
vm=ViewManager();vm._wifi=None
left=[];vm.back=lambda:left.append(True)
original_mode=vm.draw.mode
saved_case={'model':{'benchmark_must_not_touch':'user model'},'view':0}
session.kept['beam']=saved_case
app=b.Benchmark(vm)
app.full=False
app.run(k.BUTTON_F9);assert app.help
for _ in range(40):app.run(k.BUTTON_DOWN)
assert app.help_first>0
app.run(k.BUTTON_F9);assert not app.help
app.run(k.BUTTON_CENTER)
assert app.phase=='run'
for _ in range(20000):
    app.run(k.BUTTON_NONE)
    if app.phase!='run':break
assert app.phase=='done', (app.phase,app.error,app.title)
rows=[json.loads(s) for s in vm.storage.read(b.RESULT_PATH).splitlines()]
assert rows[0]['version']=='1.32' and rows[-1]['status']=='complete'
results=[row for row in rows if 'work_us' in row]
assert len(results)==len(models.cases(False))*2
assert sum(row['status']=='expected refusal' for row in results)==6
assert all(row['status'] in ('ok','expected refusal') for row in results),results
assert all(row['pages'] for row in results if row['status']=='ok')
assert all(len(row['pages'])==3 for row in results if row['kind'] in ('beam','frame'))
assert all('build_active_us' in row and row['segments']>0 for row in results if row['kind']=='Cylinder')
assert vm.draw.mode==original_mode
assert session.kept['beam'] is saved_case
assert all('START' in [r['status'] for r in rows if r.get('case')==row['case']] for row in results)
for row in results:
    for page in row.get('pages',()):
        assert page['frame_median_us']>=page['compose_median_us']
        assert len(page['dirty_rows'])==3
print('PASS: real Beam model/diagram/overview and analytic PicoCAD frames in both screen modes; expected CAD refusals; user-session isolation')

# The full ladder includes actual editor maxima and explicit synthetic models.
assert ('beam',128,1,1) in models.cases(True)
assert ('Cylinder',8,24,5) in models.cases(True)
from engtools.beamlab import model as bm
from engtools.picocad import model as dm
for case in models.cases(True):
    kind,n,q,cycles=case
    if kind in ('beam','frame'):bm.check(models.beam(n,kind=='frame',q))
    elif kind not in ('limit','invalid','unsupported'):dm.validate(models.cad(kind,n,q))
print('PASS: full stress factories respect geometry validity, with labelled synthetic Beam models beyond editor limits')

# Cancel mid-build: saved START survives; generator finally frees resources.
app=b.Benchmark(vm);app.full=False;app.mode=1;app.begin();app.run(k.BUTTON_NONE)
app.run(k.BUTTON_NONE);assert app.job is not None
app.run(k.BUTTON_ESCAPE)
assert left and app.job is None and vm.draw.mode==original_mode
assert json.loads(vm.storage.read(b.RESULT_PATH).splitlines()[-1])['status']=='cancelled'
assert session.kept['beam'] is saved_case

# An OOM is reported; heavier cases in that family are skipped, CAD still runs.
original=b._case_job
def oom(vm,case,meter):
    if case[0]=='beam':raise MemoryError('injected heap exhaustion')
    for value in original(vm,case,meter):yield value
b._case_job=oom
app=b.Benchmark(vm);app.full=False;app.mode=1;app.begin()
for _ in range(10000):
    app.run(k.BUTTON_NONE)
    if app.phase!='run':break
assert app.phase=='done'
rows=[json.loads(s) for s in vm.storage.read(b.RESULT_PATH).splitlines()]
results=[row for row in rows if 'work_us' in row]
assert results[0]['status']=='memory' and results[1]['status']=='skipped after failure'
assert any(row['kind']=='Cylinder' and row['status']=='ok' for row in results)
b._case_job=original
print('PASS: cancellation checkpoint, native cleanup, mode restoration and controlled OOM isolation')

# Soft deadline closes a running generator; skip advances without a back action.
app=b.Benchmark(vm);app.full=False;app.mode=1;app.begin();app.step()
app.work=b.WORK_LIMIT_US+1;app.step()
assert app.counts['timeout']==1 and app.job is None
app=b.Benchmark(vm);app.full=False;app.mode=1;app.begin();app.step();app.run(k.BUTTON_F5)
assert app.index==1 and app.counts['user skipped']==1
app.close_job();app.restore()

# SD write failure must stop, rather than running uncheckpointed stress tests.
store=vm.storage
class Fail:
    def write(self,*args):return False
vm._storage=Fail()
app=b.Benchmark(vm);app.run(k.BUTTON_CENTER)
assert app.phase=='stopped' and app.error and app.job is None
vm._storage=store
print('PASS: deadline, skip and failed-checkpoint stop; no unlogged stress run')
