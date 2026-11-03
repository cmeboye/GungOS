"""Numeric-core MPY heap check; excludes UI/framework and physical-device timing."""
import sys,gc
sys.path.insert(0,sys.argv[1])
from engtools.calculator.evaluate import calculate
from engtools.numerics.equations import polynomial_job
from engtools.calculator.catalogue import groups
assert len(groups())==10
retained=[]
for cycle in range(15):
    for coefficients in ([1,-4,6,-4,1],[1,0,-5,0,4],[1,1e20,1]):
        for record in polynomial_job(coefficients):pass
    info=[]
    value=calculate('int(0,1,exp(-((x-0.12345)/0.0001)^2))',{},'RAD',diagnostics=info)[0]
    assert abs(value-.000177245385)<1e-7
    extra=calculate('log1p(1e-8)/expm1(1e-8)+gcd(48,18)+round(1.25,1)',{},'RAD')[0]
    assert abs(extra-8.2)<1e-5
    gc.collect();retained.append(gc.mem_alloc())
assert max(retained[4:])-min(retained[4:])<2048,retained
print('PASS: 15 polynomial/integral cycles, bounded numeric-core heap; retained drift',max(retained[4:])-min(retained[4:]),'bytes; free',gc.mem_free())
