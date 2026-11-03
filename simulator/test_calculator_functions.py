"""New scalar functions: binary reference cases, domains, scope and exact rounding."""
import os,sys,struct,math
root=os.getcwd();apps=sys.argv[2] if len(sys.argv)>2 else 'builds/MicroPython/apps_unfrozen'
for path in ('src/MicroPython','simulator/hardware',apps):sys.path.insert(0,root+'/'+path)
from engtools.calculator.evaluate import calculate,format_value,FUNCTIONS,EXTRA_FUNCTIONS,Parser,native_function
from engtools.calculator.scientific import _complex,hypot

def bits(x):return struct.pack('<f',x)
count=0
with open(sys.argv[1],'rb') as file:
    while True:
        h=file.read(5)
        if not h:break
        length,argc,mask,degree,exact=h;name=file.read(length).decode();values={};args=[]
        for i in range(argc):
            x,y=struct.unpack('<ff',file.read(8));key='v'+str(i);values[key]=_complex(x,y) if mask&(1<<i) else x;args.append(key)
        re,im=struct.unpack('<ff',file.read(8))
        if name=='format':
            expected=file.read(file.read(1)[0]).decode()
            assert format_value(values['v0'],bool(degree))==expected,(values,degree,format_value(values['v0'],bool(degree)),expected)
            count+=1;continue
        text=name+'('+','.join(args)+')'
        try:got=calculate(text,values,'DEG' if degree else 'RAD',True)[0]
        except Exception as exc:print('reference error',text,values,type(exc).__name__,exc);raise
        actual=(got.real,got.imag) if isinstance(got,complex) else (got,0.)
        if exact:
            assert bits(actual[0])==bits(re),(name,values,actual,re)
        else:
            for a,b in zip(actual,(re,im)):
                allowance=(2e-7*abs(values['v0']) if name=='rect' else 0.)
                assert abs(a-b)<=2e-5*abs(b)+allowance+3e-45,(name,values,actual,(re,im))
                if a==0 and b==0 and name!='rect':assert math.copysign(1,a)==math.copysign(1,b),(name,values,actual,(re,im))
        count+=1

def value(text,angle='RAD',cmode=False):return calculate(text,{},angle,cmode)[0]
for text,want in (('gcd()',0),('lcm()',1),('gcd(-48,18,30)',6),('lcm(-12,18)',36),('gcd(0,0)',0),('lcm(0,0)',0),
                  ('gcd(16777216,1024)',1024),('lcm(1000003,1000033)',1000036000099),('round(ncr(34,17),-3)',2333606000),
                  ('sum(k,1,4,gcd(12,k))',10),('hypot(3,4)',5),('trunc(-2.9)',-2),('gamma(5)',24)):
    assert value(text)==want,(text,value(text),want)
assert isinstance(value('lcm(1000003,1000033)'),int)
from engtools.calculator.scientific import RESULT_LIMIT
try:calculate('round(top,-35)',{'top':RESULT_LIMIT})
except ValueError as exc:assert 'range' in str(exc)
else:raise AssertionError('rounded integer overflow accepted')
for text,word in (('atan2(1)','argument'),('atan2(i,1)','real'),('rect(2,1)','Complex'),('hypot(i,1)','real'),
                  ('gcd(1.5,2)','integer'),('gcd(16777218,2)','integer'),('lcm(0,1.5)','integer'),
                  ('lcm('+','.join(['16777213','16777199','16777183','16777153','16777141','16777139'])+')','range'),
                  ('gcd('+','.join(['1']*33)+')','32'),('log1p(-1)','> -1'),('log1p(i)','real'),('atanh(1)','singular'),
                  ('acosh(0)','Complex'),('gamma(0)','undefined'),('lgamma(-2)','undefined'),('gamma(36)','range'),
                  ('erf(i)','real'),('expm1(i)','real'),('round(1,46)','integer'),('sigfig(1,8)','integer'),('round(i,2)','real')):
    variables={'a':7,'Ans':11}
    try:calculate('a='+text,variables,'RAD',text not in ('rect(2,1)','acosh(0)'))
    except (ValueError,TypeError,OverflowError) as exc:assert word in str(exc),(text,str(exc))
    else:raise AssertionError(text)
    assert variables=={'a':7,'Ans':11}
for name in EXTRA_FUNCTIONS:
    try:calculate(name+'=3',{})
    except ValueError:pass
    else:raise AssertionError('unreserved '+name)
assert format_value(struct.unpack('<f',b'\x01\0\0\0')[0])=='1.401298e-45'
assert format_value(1e-38)=='9.999999e-39'
assert format_value(-1e-45,True)=='-1.4013e-45'
assert value('asinh(1)','DEG')==value('asinh(1)','RAD')
assert abs(value('acosh(-2)',cmode=True).imag-math.pi)<1e-5
assert abs(value('atanh(2)',cmode=True).imag-math.pi/2)<1e-5
assert value('atanh(conj(2+0i))',cmode=True).imag<0
assert value('acosh(conj(-2+0i))',cmode=True).imag<0
assert abs(value('atan2(1,-1)','DEG')-135)<1e-5
assert value('rect(2,90)','DEG',True)==2j
assert native_function(Parser('round(x,2)').parse()[1],{}) is None
assert abs(value('int(0,1,log1p(x))')-(2*math.log(2)-1))<1e-5
print('PASS:',count,'new function references, domains, exact decimal ties, reserved names, subnormal text and integration')
