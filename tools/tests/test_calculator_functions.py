"""Independent math/cmath/Decimal references for the next scientific functions."""
from pathlib import Path
from decimal import Decimal,localcontext,ROUND_HALF_EVEN
import cmath,math,random,struct,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[2]
FMAX=struct.unpack('<f',bytes.fromhex('ffff7f7f'))[0]
def f32(x):return struct.unpack('<f',struct.pack('<f',x))[0]
def exact_f32(d):
    if not d:return math.copysign(0.0,-1 if d.is_signed() else 1)
    sign=-1 if d<0 else 1;d=abs(d)
    if d>Decimal.from_float(FMAX):raise OverflowError
    value=f32(float(d));bits=struct.unpack('<I',struct.pack('<f',value))[0]
    choices=[b for b in (bits-1,bits,bits+1) if 0<=b<=0x7f7fffff]
    best=min(choices,key=lambda b:(abs(Decimal.from_float(struct.unpack('<f',struct.pack('<I',b))[0])-d),b%2))
    return sign*struct.unpack('<f',struct.pack('<I',best))[0]
cases=[]
def add(name,args,want,mask=0,degrees=False,exact=False):
    want=complex(want)
    if not (math.isfinite(want.real) and math.isfinite(want.imag)) or max(abs(want.real),abs(want.imag))>FMAX:return
    cases.append((name,args,want,mask,degrees,exact))
xs=[-3e38,-1e20,-100.,-20.,-10.,-3.,-1.,-.99999994,-.5,-1e-8,-1e-30,-1e-38,-0.,0.,1e-38,1e-30,1e-8,.5,1.,2.,3.,10.,20.,35.,1e20,3e38]
for name in ('asinh','acosh','atanh','log1p','expm1','gamma','lgamma','erf','erfc','trunc'):
    for x in xs:
        x=f32(x)
        try:want=getattr(math,name)(x)
        except (ValueError,OverflowError):continue
        add(name,[(x,0)],want)
for x in (-3e30,-4.,-1e-30,-0.,0.,1e-30,3.,3e30):
    for y in (-4e30,-3.,-1e-30,-0.,0.,1e-30,4.,4e30):
        x,y=f32(x),f32(y)
        add('hypot',[(x,0),(y,0)],math.hypot(x,y))
        for deg in (False,True):
            add('atan2',[(y,0),(x,0)],math.degrees(math.atan2(y,x)) if deg else math.atan2(y,x),degrees=deg)
            add('phase',[(x,y)],math.degrees(cmath.phase(complex(x,y))) if deg else cmath.phase(complex(x,y)),mask=1,degrees=deg)
        add('radius',[(x,y)],abs(complex(x,y)),mask=1)
points=[(x,y) for x in (-3.,-1.,-1e-8,-0.,0.,1e-8,1.,3.) for y in (-3.,-1.,-1e-30,-0.,0.,1e-30,1.,3.)]
points += [(x,y) for x in (-3e38,-1e20,-1e-38,0.,1e-38,1e20,3e38) for y in (-3e38,-1e20,-1e-38,-0.,0.,1e-38,1e20,3e38)]
for name in ('asinh','acosh','atanh'):
    for x,y in points:
        x,y=f32(x),f32(y)
        try:want=getattr(cmath,name)(complex(x,y))
        except ValueError:continue
        # Hyperbolic functions are unchanged by DEG/RAD selection.
        for deg in (False,True):add(name,[(x,y)],want,mask=1,degrees=deg)
for radius in (0.,-2.,1e-30,2.,3e30):
    for angle in (-1e10,-450.,-180.,-90.,-1e-30,-0.,0.,1e-30,30.,90.,180.,270.,1e10):
        radius,angle=f32(radius),f32(angle);a=math.fmod(angle,360.)
        if math.fmod(a,90.)==0:
            q=int(a/90)%4;c=(1,0,-1,0)[q];s=(0,1,0,-1)[q]
            if s==0:s=math.copysign(0.,a)
            want=complex(radius*c,radius*s)
        else:want=cmath.rect(radius,f32(a*f32(f32(math.pi)/180)))
        add('rect',[(radius,0),(angle,0)],want,mask=0,degrees=True)
random.seed(2951)
round_values=[-3e38,-9999999.,-1250.,-2.675,-1.25,-.5,-1e-38,-1e-45,-0.,0.,1e-45,1e-38,.5,1.25,2.675,1250.,9999999.,3e38]
round_values += [random.uniform(-9,9)*10**random.randint(-43,37) for _ in range(100)]
with localcontext() as context:
    context.prec=200
    for x in round_values:
        x=f32(x);d=Decimal.from_float(x)
        for places in (-45,-38,-10,-3,-1,0,1,2,7,20,38,45):
            try:want=exact_f32(d.quantize(Decimal(1).scaleb(-places),rounding=ROUND_HALF_EVEN))
            except OverflowError:continue
            add('round',[(x,0),(places,0)],want,exact=True)
        for digits in (1,3,7):
            rounded=d.quantize(Decimal(1).scaleb(d.adjusted()-digits+1),rounding=ROUND_HALF_EVEN) if d else d
            try:want=exact_f32(rounded)
            except OverflowError:continue
            add('sigfig',[(x,0),(digits,0)],want,exact=True)
for raw in (1,2,3,7,8,15,16,127,128,1023,1024,65535,65536,0x3fffff,0x400000,0x7ffffe,0x7fffff):
    for sign in (1,-1):
        x=sign*struct.unpack('<f',struct.pack('<I',raw))[0]
        for engineering in (False,True):add('format',[(x,0)],0,degrees=engineering)
with tempfile.TemporaryDirectory(prefix='gungos-extra-functions-') as temp:
    path=Path(temp)/'references.bin'
    with path.open('wb') as f:
        for name,args,want,mask,deg,exact in cases:
            f.write(bytes([len(name),len(args),mask,int(deg),int(exact)]));f.write(name.encode())
            for x,y in args:f.write(struct.pack('<ff',x,y))
            f.write(struct.pack('<ff',want.real,want.imag))
            if name=='format':
                with localcontext() as ctx:
                    ctx.prec=200;d=Decimal.from_float(args[0][0]);digits=6 if deg else 7
                    rounded=d.quantize(Decimal(1).scaleb(d.adjusted()-digits+1),rounding=ROUND_HALF_EVEN)
                    exponent=rounded.adjusted();exponent=exponent-exponent%3 if deg else exponent
                    mantissa=format(rounded.scaleb(-exponent),'f')
                    if '.' in mantissa:mantissa=mantissa.rstrip('0').rstrip('.')
                    text=(mantissa+'e%+d'%exponent).encode();f.write(bytes([len(text)]));f.write(text)
    binary=str(ROOT/'builds/MicroPython/desktop/micropython')
    subprocess.run([binary,'-X','heapsize=16M','simulator/test_calculator_functions.py',str(path)],cwd=ROOT,check=True)
    staging=ROOT/'.build/sd-app-staging'
    if staging.is_dir():subprocess.run([binary,'-X','heapsize=16M','simulator/test_calculator_functions.py',str(path),str(staging.relative_to(ROOT))],cwd=ROOT,check=True)
print('PASS:',len(cases),'additional function references from math/cmath and exact Decimal rounding')
