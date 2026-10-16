"""Exercise native numerical APIs, workspace guards and the lab check page."""
import os
import sys
from time import ticks_ms

root = os.getcwd()
sys.path.insert(0, root + '/src/MicroPython')
sys.path.insert(0, root + '/simulator/hardware')
sys.path.insert(0, root + '/builds/MicroPython/apps_unfrozen')
from ulab import numpy as np, scipy as sp
import ulab
from engtools.numerics import backend, bench

assert ulab.__version__ == '6.12.1-2D-c'
assert backend.information()['float_bits'] == 32
assert np.zeros(1).itemsize == 4 and np.zeros(1, dtype=np.complex).itemsize == 8
assert list(np.sort(np.array([3,1,2]))) == [1,2,3]
for module, excluded in (
    (np, ('random', 'load', 'save', 'loadtxt', 'savetxt', 'polyfit', 'vectorize')),
    (np.linalg, ('inv', 'det', 'eig')),
    (sp, ('special',)),
    (sp.optimize, ('fmin', 'curve_fit')),
    (sp.integrate, ('simpson', 'romberg', 'tanhsinh')),
):
    for name in excluded:
        assert not hasattr(module, name), name
try:
    np.zeros((2, 2, 2))
    raise AssertionError('Higher-dimensional arrays were included')
except (TypeError, ValueError):
    pass
for matrix in (np.zeros((2, 3)), np.zeros((65, 2)), np.zeros((2, 2), dtype=np.complex),
               np.array([[float('nan')]]), np.zeros(2)):
    try:
        backend.guarded_qr(matrix)
        raise AssertionError('Unsafe QR input was accepted')
    except ValueError:
        pass
import gc
old_reserve = backend.HEAP_RESERVE
backend.HEAP_RESERVE = gc.mem_alloc() + gc.mem_free()
try:
    try:
        backend.guarded_qr(np.eye(2))
        raise AssertionError('QR ignored its memory reserve')
    except MemoryError:
        pass
finally:
    backend.HEAP_RESERVE = old_reserve
try:
    np.fft.fft(np.zeros(150))
    raise AssertionError('FFT accepted an unsupported length')
except ValueError:
    pass
try:
    sp.linalg.cho_solve(np.linalg.cholesky(np.array([[1, 2], [2, 1]])), np.ones(2))
    raise AssertionError('Cholesky accepted an indefinite matrix')
except ValueError:
    pass
try:
    sp.optimize.bisect(lambda x: x*x+1, -1, 1)
    raise AssertionError('Bisection accepted a bracket without a sign change')
except ValueError:
    pass
records = list(bench.checks())
assert len(records) == len(bench.CASES)
for record in records:
    assert record['passed'], record
    print('PASS: %s (%d us; allocation delta %d B)' %
          (record['name'], record['elapsed_us'], record['heap_delta_bytes']))

import sim_runtime
sim_runtime.configure(root, '/private/tmp/picoware-ulab-regression-' + str(ticks_ms()),
                      root + '/builds/MicroPython/apps_unfrozen', 1, 'picocalc-pico2w',
                      0, True, False, False, False, '', _network_mode='offline', _audio_mode='silent')
from picoware.system.view_manager import ViewManager
from picoware.system.view import View
from picoware.system.buttons import BUTTON_CENTER, BUTTON_ESCAPE, BUTTON_NONE
import PicoLAB as lab
vm = ViewManager()
vm.add(View('parent', lambda vm: None, lambda vm: True, lambda vm: None))
vm.switch_to('parent')
vm.add(View('lab', lab.run, lab.start, lab.stop))
vm.switch_to('lab')
lab._selected = len(lab.TOOLS)+3
vm._button = BUTTON_CENTER
lab.run(vm)
assert lab._page == 'bench'
vm._button = BUTTON_NONE
for _ in range(len(bench.CASES)):
    lab.run(vm)
assert lab._bench is None and all(record['passed'] for record in lab._bench_rows)
vm.draw.screenshot('/private/tmp/picoware-ulab-checks.bmp')
vm._button = BUTTON_CENTER
lab.run(vm)
assert lab._bench is not None and len(lab._bench_rows) == 1
vm._button = BUTTON_ESCAPE
lab.run(vm)
assert lab._page == 'tools' and lab._bench is None
# Existing device firmware gets a useful message rather than an app failure.
old_require = backend.require
def unavailable():
    raise RuntimeError('This firmware needs the configured ulab build.')
backend.require = unavailable
try:
    lab._selected = len(lab.TOOLS)+3
    vm._button = BUTTON_CENTER
    lab.run(vm)
    assert lab._page == 'bench' and lab._bench is None and 'ulab' in lab._error
finally:
    backend.require = old_require
vm._button = BUTTON_ESCAPE
lab.run(vm)
lab.stop(vm)
assert lab._bench is None and not lab._bench_rows
print('PASS: selected capabilities, float32, input errors and QR workspace limits')
print('PASS: numerical check page, rerun/cancel/cleanup and missing-firmware message')
