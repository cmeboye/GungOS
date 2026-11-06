"""Independent high-precision polynomial oracle and integration regressions."""
from pathlib import Path
from decimal import Decimal,localcontext
import cmath,math,random,struct,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[2]
def f32(x):return struct.unpack('<f',struct.pack('<f',x))[0]
class Z:
    def __init__(self,r=0,i=0):self.r=Decimal(r);self.i=Decimal(i)
    def __add__(self,b):return Z(self.r+b.r,self.i+b.i)
    def __sub__(self,b):return Z(self.r-b.r,self.i-b.i)
    def __mul__(self,b):return Z(self.r*b.r-self.i*b.i,self.r*b.i+self.i*b.r)
    def __truediv__(self,b):
        d=b.r*b.r+b.i*b.i
        return Z((self.r*b.r+self.i*b.i)/d,(self.i*b.r-self.r*b.i)/d)
    def square(self):return self.r*self.r+self.i*self.i

def oracle(c):
    with localcontext() as context:
        context.prec=80
        c=[Z(Decimal.from_float(float(v))) for v in c];degree=len(c)-1
        if degree==2:
            a,b,d=[z.r for z in c];disc=b*b-4*a*d
            if disc>=0:
                q=-(b+(disc.sqrt() if b>=0 else -disc.sqrt()))/2
                return [complex(q/a),complex(d/q)] if q else [0j,0j]
            return [complex(-b/(2*a),(-disc).sqrt()/(2*a)),complex(-b/(2*a),-(-disc).sqrt()/(2*a))]
        c=[v/c[0] for v in c];radius=1+max(float(abs(z.r)) for z in c[1:])
        roots=[Z(str(radius*math.cos(2*math.pi*(i+.17)/degree)),str(radius*math.sin(2*math.pi*(i+.17)/degree))) for i in range(degree)]
        for iteration in range(1500):
            next_roots=[];change=Decimal(0)
            for i,z in enumerate(roots):
                p=c[0]
                for v in c[1:]:p=p*z+v
                d=Z(1)
                for j,other in enumerate(roots):
                    if i!=j:d=d*(z-other)
                delta=p/d;next_roots.append(z-delta);change=max(change,delta.square())
            roots=next_roots
            if change<Decimal('1e-100'):break
        else:raise AssertionError(('oracle did not converge',c))
        return [complex(float(z.r),float(z.i)) for z in roots]

cases=[([1,-4,6,-4,1],[1]*4),([1,0,2,0,1],[-1j,-1j,1j,1j]),
       ([16,-32,24,-8,1],[.5]*4),([1,-3,3,-1],[1]*3),([1,0,0,0,0],[0]*4),
       ([1,1e20,1],None),([1e-30,-6e-30,11e-30,-6e-30],None),
       ([1e30,-6e30,11e30,-6e30],None),([1,-4.001,6.003,-4.003,1.001],None),
       ([1,0,1e-30],None),([1,0,-1e30],None),([1,0,0,0,1],None),
       ([1,0,0,0,-1],None),([1,-6,11,-6],None),([1,0,-5,0,4],None)]
random.seed(7313)
for _ in range(70):
    degree=random.choice((2,3,4));cases.append(([random.choice((1,2,3))]+[random.randint(-30,30) for _ in range(degree)],None))
with tempfile.TemporaryDirectory(prefix='gungos-calc-numerics-') as temp:
    fixture=Path(temp)/'roots.bin'
    with fixture.open('wb') as file:
        for c,known in cases:
            c=[f32(v) for v in c];want=known if known is not None else oracle(c)
            file.write(bytes([len(c)]));file.write(struct.pack('<%df'%len(c),*c))
            file.write(struct.pack('<%df'%(2*len(want)),*[part for z in want for part in (complex(z).real,complex(z).imag)]))
    binary=str(ROOT/'builds/MicroPython/desktop/micropython')
    subprocess.run([binary,'-X','heapsize=8M','simulator/test_calculator_numerics.py',str(fixture)],cwd=ROOT,check=True)
    staging=ROOT/'.build/sd-app-staging'
    if staging.is_dir():
        subprocess.run([binary,'-X','heapsize=8M','simulator/test_calculator_numerics.py',str(fixture),str(staging.relative_to(ROOT))],cwd=ROOT,check=True)
        subprocess.run([binary,'-X','heapsize=128K','simulator/check_calculator_heap.py',str(staging)],cwd=ROOT,check=True)
print('PASS:',len(cases),'independent polynomial cases and adaptive integration/control regressions')
