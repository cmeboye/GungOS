"""Benchmark recovery: default skip, partial reports, blind N and timeout."""
import os,sys
from time import ticks_ms
root=os.getcwd()
sys.path.insert(0,root+'/src/MicroPython')
sys.path.insert(0,root+'/simulator/hardware')
import sim_runtime
sim_runtime.configure(root,'/private/tmp/gungos-benchmark-recovery-test-'+str(ticks_ms()),
                      root+'/builds/MicroPython/apps_unfrozen',1,'picocalc-pico2w',
                      0,True,False,False,False,'',_network_mode='offline',_audio_mode='silent')
sim_runtime.mkdir_p(sim_runtime.sd_root)
from picoware.system.view_manager import ViewManager
from picoware.system import buttons as k
vm=ViewManager();vm._wifi=None
sys.path.insert(0,sys.argv[1] if len(sys.argv)>1 else root+'/builds/MicroPython/apps_unfrozen/misc')
import Benchmark as bench
# A black status screen previously produced a cheap partial first sample,
# paired with the row count from a later full transfer. Model that exact case.
class Size:
    y=320
class Display:
    size=Size()
    def __init__(self):
        self.current=self.next=bench.BLACK
        self.clock=0
        self.rows=[]
    def _clear(self,colour):self.next=colour
    def swap(self):
        rows=0 if self.current==self.next else 320
        self.clock+=25 if rows else 1
        self.current=self.next
        self.rows.append(rows)
        return rows
fake=Display()
real_clock=bench.ticks_us
bench.ticks_us=lambda:fake.clock
try:
    elapsed,rows=bench._swap_full(fake)
finally:
    bench.ticks_us=real_clock
assert elapsed==25 and rows==320
assert fake.rows==[0]+[320]*6, 'Timed samples must all be full-screen changes'
print('PASS: partial warm-up is excluded and every timed full-screen sample sends 320 rows')
def step(button=-1):
    vm._button=button;bench.run(vm)
def finish():
    for _ in range(len(bench.STAGES)+3):step()
    assert bench._stage>len(bench.STAGES)
original=vm.draw.set_panel_bits
formats=[]
def setting(bits):
    formats.append(bits);return original(bits)
vm.draw.set_panel_bits=setting
assert bench.start(vm) and not bench._panel_test
step(k.BUTTON_CENTER);finish()
assert not bench._waiting and 12 not in formats
report=vm.storage.read(bench.RESULT_PATH)
assert 'Status: complete' in report and 'disabled by default' in report
assert 'Free heap, SRAM screen' in report and 'Free heap, PSRAM screen' in report
assert 'Python / C speed ratio' in report
print('PASS: default run skips experimental format and saves complete memory/timing results')

assert bench.start(vm)
step(k.BUTTON_F2);assert bench._panel_test
step(k.BUTTON_CENTER)
for _ in range(len(bench.STAGES)):
    step()
    if bench._waiting:break
assert bench._waiting
report=vm.storage.read(bench.RESULT_PATH)
assert 'Status: waiting for Y/N' in report
assert 'Free heap, SRAM screen' in report and 'Free heap, PSRAM screen' in report
step(k.BUTTON_A);assert bench._waiting
step(k.BUTTON_N);assert not bench._waiting and formats[-1]==16
finish()
assert '12-bit colours looked right: no' in vm.storage.read(bench.RESULT_PATH)
print('PASS: optional experiment checkpoints first and N restores normal transfers')

assert bench.start(vm)
step(k.BUTTON_F2);step(k.BUTTON_CENTER)
for _ in range(len(bench.STAGES)):
    step()
    if bench._waiting:break
assert bench._waiting
clock=bench.ticks_ms
bench.ticks_ms=lambda:20000
bench._prompt_started=0
step();assert not bench._waiting and formats[-1]==16
bench.ticks_ms=clock
finish()
assert 'timed out; restored 16-bit' in vm.storage.read(bench.RESULT_PATH)
print('PASS: unanswered experiment restores 16-bit mode after twenty seconds')

assert bench.start(vm)
step(k.BUTTON_F2);step(k.BUTTON_CENTER)
for _ in range(3):step()
def failed_format(bits):
    if bits==12:raise RuntimeError('simulated native display failure')
    return original(bits)
vm.draw.set_panel_bits=failed_format
try:step()
except RuntimeError:pass
else:raise AssertionError('Failed format was not attempted')
report=vm.storage.read(bench.RESULT_PATH)
assert 'running step 4' in report
assert 'Free heap, SRAM screen' in report and 'Free heap, PSRAM screen' in report
assert 'Draw 26 text rows, PSRAM' in report
vm.draw.set_panel_bits=original
bench.stop(vm)
print('PASS: completed measurements survive a failure before the colour prompt')
