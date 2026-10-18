import gc, os, sys
sys.path.insert(0, os.getcwd() + "/src/MicroPython")
import picoware_psram as native
from picoware.system.psram import PSRAM
p=PSRAM()
# Public methods must be reachable on the real C-backed type.
assert p.is_ready()
payload=p.malloc(b'keep this across system-counter samples')
free=p.mem_free()
q=PSRAM()
assert p.mem_free()==free, 'constructing another interface reset the live allocator'
assert payload.value()==b'keep this across system-counter samples'
p.write8(0, 0xA5)  # the display reserves the beginning of the chip
q=None
gc.collect()
assert p.is_ready(), 'collecting another interface shut down the shared bus'
assert p.mem_free()==free and p.read8(0)==0xA5
raw=native.PSRAM()
assert raw.is_ready() and raw.mem_free()==free
raw.__del__()
assert not raw.initialized and p.is_ready()
from picoware.system.system import System
for i in range(10):
    assert System().total_psram==native.SIZE
    assert System().free_psram==free
    assert System().used_psram==native.SIZE-free
    gc.collect()
    assert p.is_ready() and payload.value()==b'keep this across system-counter samples'
print('PASS: real native PSRAM methods, shared allocator, GC and repeated resource sampling')
