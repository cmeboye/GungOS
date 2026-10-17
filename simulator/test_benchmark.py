"""The device benchmark runs every stage and saves its report.

Run from the repo root with builds/MicroPython/desktop/micropython -X heapsize=16M simulator/test_benchmark.py.
Simulator timings are not meaningful; this checks the flow, keys and report.
"""

import os
import sys
from time import ticks_ms

root = os.getcwd()
sys.path.insert(0, root + '/src/MicroPython')
sys.path.insert(0, root + '/simulator/hardware')
import sim_runtime
sd_root = '/private/tmp/gungos-benchmark-regression-' + str(ticks_ms())
sim_runtime.configure(root, sd_root, root + '/builds/MicroPython/apps_unfrozen',
                      1, 'picocalc-pico2w', 0, True, False, False, False, '',
                      _network_mode='offline', _audio_mode='silent')
sim_runtime.mkdir_p(sd_root)
from picoware.system.view_manager import ViewManager
from picoware.system import buttons as k

vm = ViewManager()
vm._wifi = None
sys.path.insert(0, root + '/builds/MicroPython/apps_unfrozen/misc')
import Benchmark as bench

def step(button=-1):
    """One pass of the app loop with the key the view manager read."""
    vm._button = button
    bench.run(vm)

assert bench.start(vm)
step()                      # waits for Enter
assert bench._stage == -1
step(k.BUTTON_CENTER)
for _ in range(len(bench.STAGES) + 2):
    step()
    if bench._waiting:
        break
assert bench._waiting, 'The 12-bit stage must ask for a verdict'
step(k.BUTTON_A)
assert bench._waiting, 'Other keys must not answer the colour test'
step(k.BUTTON_Y)
for _ in range(len(bench.STAGES) + 2):
    step()
labels = [label for label, _, _ in bench._results]
for expected in ('Free heap, SRAM screen', 'Swap, whole screen changed', 'Swap, one text line changed',
                 'Swap, identical redraw', 'Draw 26 text rows, SRAM', 'Free heap, PSRAM screen',
                 'Swap whole screen, 12-bit', '12-bit colours looked right', 'Python / C speed ratio'):
    assert expected in labels, expected
values = {label: (value, unit) for label, value, unit in bench._results}
assert values['Swap, whole screen changed'][1].endswith('(320 rows)')
assert values['Swap, identical redraw'][1].endswith('(0 rows)')
assert values['12-bit colours looked right'][0] == 'yes'
report = vm.storage.read(bench.RESULT_PATH)
assert 'Swap, one text line changed' in report and bench._saved == bench.RESULT_PATH
assert vm.draw.mode == vm.draw.MODE_SRAM, 'The benchmark must leave the SRAM screen mode on'
print('PASS: benchmark runs every stage, asks for the colour verdict and saves its report')
