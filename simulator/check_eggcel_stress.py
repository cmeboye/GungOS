import sys,gc,random
sys.path.insert(0,"builds/MicroPython/apps_unfrozen")
from desktopapps.eggcel.model import Sheet
from desktopapps.eggcel.formulas import CellError
random.seed(42)
s=Sheet()
alphabet='AB12()+-*/^%,:$=<>" '
for i in range(1500):
    raw='='+''.join(alphabet[random.randrange(len(alphabet))] for _ in range(random.randrange(1,35)))
    s.apply({(0,0):raw})
    try:s.value((0,0))
    except Exception as exc:raise AssertionError((raw,exc))
gc.collect();before=gc.mem_alloc()
s=Sheet();s.apply({(i//26,i%26):str(i) for i in range(512)})
for position in s.cells:s.value(position)
gc.collect();delta=gc.mem_alloc()-before
assert delta<150*1024,delta
print('PASS: 1,500 malformed-formula probes; 512-cell host live allocation:',delta,'bytes')
