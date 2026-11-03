"""CPython cmath oracle for the calculator's float32 inverse trig helpers."""
from pathlib import Path
import cmath,math,random,struct,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[2]
def f32(x):return struct.unpack('<f',struct.pack('<f',x))[0]
points=[(x,y) for x in (-3.,-1.,-.99999994,-.5,-0.,0.,.5,.99999994,1.,3.)
        for y in (-3.,-1.,-1e-8,-1e-30,-0.,0.,1e-30,1e-8,1.,3.)]
points += [(x,y) for x in (-3e38,-1e30,-1e15,-1e-38,0.,1e-38,1e15,1e30,3e38)
           for y in (-3e38,-1e30,-1e-38,0.,1e-38,1e30,3e38)]
random.seed(4821)
for _ in range(100):
    points.append((random.uniform(-3,3)*10**random.randint(-35,35),random.uniform(-3,3)*10**random.randint(-35,35)))
with tempfile.TemporaryDirectory(prefix='gungos-calc-inverse-') as tmp:
    path=Path(tmp)/'inverse.tsv';count=0
    with path.open('w') as out:
        for name in ('asin','acos','atan','sqrt','ln','log'):
            for x,y in points:
                x,y=f32(x),f32(y)
                try:value=getattr(cmath,{'ln':'log','log':'log10'}.get(name,name))(complex(x,y))
                except ValueError:continue
                out.write('%s\t%r\t%r\t%.17g\t%.17g\n'%(name,x,y,value.real,value.imag));count+=1
    binary=str(ROOT/'builds/MicroPython/desktop/micropython')
    subprocess.run([binary,'-X','heapsize=32M','simulator/test_calculator_scientific.py',str(path)],cwd=ROOT,check=True)
    staging=ROOT/'.build/calculator-functions-2026-11-03/sd-app-staging'
    if not staging.is_dir():staging=ROOT/'.build/calculator-numerics-2026-11-03/sd-app-staging'
    if not staging.is_dir():staging=ROOT/'.build/calculator-followup-2026-11-03/sd-app-staging'
    if staging.is_dir():
        subprocess.run([binary,'-X','heapsize=32M','simulator/test_calculator_scientific.py',str(path),str(staging.relative_to(ROOT))],cwd=ROOT,check=True)
print('PASS:',count,'complex function references from CPython cmath on float32 inputs')
