"""Stored float32 coefficient roots; adaptive integral controls/diagnostics."""
import os,sys,struct,math,gc
root=os.getcwd();apps=sys.argv[2] if len(sys.argv)>2 else 'builds/MicroPython/apps_unfrozen'
for path in ('src/MicroPython','simulator/hardware',apps):sys.path.insert(0,root+'/'+path)
from engtools.numerics.equations import polynomial_job
from engtools.calculator.evaluate import calculate,Evaluator,Parser
from engtools.calculator.scientific import hypot
from engtools.calculator.editor import Editor,source
count=0
with open(sys.argv[1],'rb') as file:
    while True:
        b=file.read(1)
        if not b:break
        n=b[0];c=struct.unpack('<%df'%n,file.read(n*4));raw=struct.unpack('<%df'%(2*(n-1)),file.read(8*(n-1)))
        expected=[complex(raw[2*i],raw[2*i+1]) for i in range(n-1)]
        try:
            for record in polynomial_job(c):pass
        except Exception as exc:print('polynomial failure',c);raise
        roots=record['roots'];assert len(roots)==len(expected)
        for z in roots:
            index=min(range(len(expected)),key=lambda i:hypot(z.real-expected[i].real,z.imag-expected[i].imag))
            want=expected.pop(index)
            assert hypot(z.real-want.real,z.imag-want.imag)<=1e-5*max(hypot(want.real,want.imag),1e-37),(c,z,want)
        if c==(1.,-4.,6.,-4.,1.):assert record['multiplicities']==[4]*4 and record['warnings']
        count+=1
for invalid in ([0,1,2],[1,math.inf,0],[1,1j,0],[3e38,3e38,1e-45],[1e-45,0,3e38]):
    try:list(polynomial_job(invalid))
    except (ValueError,OverflowError):pass
    else:raise AssertionError(invalid)
for text,want,rel in (('int(0,1,x^2)',1/3,1e-5),('int(1,0,x^2)',-1/3,1e-5),
                      ('int(0,pi,sin(x))',2,1e-5),('int(0,1,sqrt(x))',2/3,1e-5),
                      ('int(0,1,exp(-((x-0.12345)/0.0001)^2))',math.sqrt(math.pi)*.0001,5e-4),
                      ('int(0,1,exp(-((x-0.12345)/0.000001)^2),1e-9,2e-5,0.12345)',math.sqrt(math.pi)*.000001,0.001),
                      ('int(-1,1,abs(x),1e-7,2e-5,0)',1,1e-5),('int(0,1000,1)',1000,1e-6),
                      ('int(0,1,0)',0,0),('int(1,1,x)',0,0)):
    info=[];value=calculate(text,{},'RAD',diagnostics=info)[0]
    assert abs(value-want)<=rel*abs(want),(text,value,want)
    assert info and 'error' in info[-1] and info[-1]['evaluations']<=8192
for text,why in (('int(0,1,x-x)','samples zero'),('int(0,1,x,0,1e-9)','rtol'),
                 ('int(0,1,x,1e-7,2e-5,2)','inside'),('int(0,1,x,1e-7,2e-5,0.5,0.5)','distinct'),
                 ('int(-1,1,1/x)','undefined'),('int(0,1,exp(-((x-0.173234)/0.0000001)^2))','samples zero'),
                 ('int(0,1,int(0,1,x))','Nested')):
    variables={'a':7,'Ans':11};before=dict(variables)
    try:calculate('a='+text,variables,'RAD')
    except (ValueError,ZeroDivisionError) as exc:assert why in str(exc),(text,str(exc))
    else:raise AssertionError(text)
    assert variables==before
# Callback cancellation is transactional for both reductions and integration.
for text in ('a=sum(k,1,1024,k^2)','a=int(0,1,exp(-((x-0.12345)/0.0001)^2))'):
    calls=[];variables={'a':7,'Ans':11}
    def cancel(record):calls.append(record);raise ValueError('Cancelled')
    try:calculate(text,variables,'RAD',progress=cancel)
    except ValueError as e:assert str(e)=='Cancelled'
    else:raise AssertionError('ignored cancellation')
    assert calls and variables=={'a':7,'Ans':11}
# Extra integral controls stay editable as plain function text, not truncated.
e=Editor()
for ch in 'int(0,1,x,1e-7,2e-5,0.5)':e.insert(ch)
saved=source(e.root);assert not e.expand() and source(e.root)==saved
print('PASS:',count,'polynomial references, integral peaks/controls/diagnostics, cancellation and transactionality')
