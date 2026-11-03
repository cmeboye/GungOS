"""Bounded adaptive Gauss 7/Kronrod 15 integration of finite real functions.

The error is an estimate, not proof: finite sampling can miss arbitrary narrow
features. Use explicit break points and check the reported samples/error.
"""
import math
# Quadrature nodes/weights from QUADPACK qk15 (Netlib).
X=(0.9914553711208126,0.9491079123427585,0.8648644233597691,0.7415311855993945,
   0.5860872354676911,0.4058451513773972,0.2077849550078985)
K=(0.02293532201052922,0.06309209262997855,0.1047900103222502,0.1406532597155259,
   0.1690047266392679,0.1903505780647854,0.2044329400752989,0.2094821410847278)
G=(0.1294849661688697,0.2797053914892767,0.3818300505051189,0.4179591836734694)
MAX_EVALUATIONS=8192
MAX_INTERVALS=256


def _finite(v):return isinstance(v,(int,float)) and not math.isnan(v) and not math.isinf(v)


def _sum(values):
    total=0.0;correction=0.0
    for v in values:
        updated=total+v
        correction+=(total-updated)+v if abs(total)>=abs(v) else (v-updated)+total
        total=updated
    return total+correction


def validate(lower,upper,atol,rtol,points):
    if not all(_finite(v) for v in (lower,upper,atol,rtol)):
        raise ValueError('Integral bounds/tolerances must be finite real values')
    if atol<0 or not 2e-6<=rtol<=0.1:raise ValueError('Integral: atol >= 0, rtol 2e-6..0.1')
    if len(points)>8:raise ValueError('Integral limit: 8 split points')
    sign=1
    if lower>upper:lower,upper=upper,lower;sign=-1
    if not all(_finite(p) and lower<p<upper for p in points) or len(set(points))!=len(points):
        raise ValueError('Integral splits must be distinct points inside the interval')
    return lower,upper,sign


def integrate_job(function,lower,upper,atol=1e-7,rtol=2e-5,points=()):
    """Yield progress dictionaries followed by value/error/evaluation diagnostics."""
    lower,upper,sign=validate(lower,upper,atol,rtol,points)
    if lower==upper:
        yield dict(value=0.0,error=0.0,evaluations=0,intervals=0,estimated=True);return
    width=upper-lower
    if not _finite(width):raise ValueError('Integral interval exceeds float32 range')
    count=0;nonzero=False
    def sample(x):
        nonlocal count,nonzero
        count+=1
        if count>MAX_EVALUATIONS:raise ValueError('Integral work limit: 8192 samples; add splits')
        value=function(x)
        if not _finite(value):raise ValueError('Integrand must return a finite real scalar')
        if value!=0:nonzero=True
        return value
    def panel(a,b):
        mid=a+(b-a)/2;half=(b-a)/2
        if mid==a or mid==b:raise ValueError('Integral reached float32 interval resolution')
        center=sample(mid);values=[center];weighted=[K[7]*center];gauss=[G[3]*center]
        absolute=[K[7]*abs(center)]
        for i,x in enumerate(X):
            offset=half*x;left,right=sample(mid-offset),sample(mid+offset)
            values.extend((left,right));weighted.extend((K[i]*left,K[i]*right))
            absolute.extend((K[i]*abs(left),K[i]*abs(right)))
            if i%2:gauss.extend((G[i//2]*left,G[i//2]*right))
        average=_sum(weighted)/2
        asc=K[7]*abs(center-average)
        for i in range(7):asc+=K[i]*(abs(values[1+i*2]-average)+abs(values[2+i*2]-average))
        value=_sum(weighted)*half;absolute=_sum(absolute)*half;asc*=half
        error=abs(value-_sum(gauss)*half)
        if asc and error:error=asc*min(1,(200*error/asc)**1.5)
        error=max(error,8*1.1920929e-7*absolute)
        # Endpoint probes discover a narrow feature placed at an explicit split.
        # They also reject endpoint singularities instead of hiding them.
        edge=max(abs(sample(a)),abs(sample(b)))
        magnitudes=sorted([abs(v) for v in values]+[edge])
        peak=magnitudes[-1]
        concentrated=peak>0 and magnitudes[-3]<peak*0.001
        if edge>100*max(max(abs(v) for v in values),1e-37):
            error=max(error,edge*(b-a))
        if not _finite(value) or not _finite(error):raise ValueError('Integral values exceed float32 range')
        return (a,b,value,error,peak,concentrated)
    boundaries=[lower]+sorted(points)+[upper];panels=[]
    for a,b in zip(boundaries[:-1],boundaries[1:]):
        n=max(1,int(math.ceil(32*((b-a)/width))))
        for i in range(n):
            left=a+(b-a)*(i/n);right=b if i==n-1 else a+(b-a)*((i+1)/n)
            panels.append(panel(left,right))
            yield {'progress':count}
    while True:
        value=_sum(p[2] for p in panels);error=_sum(p[3] for p in panels)
        if not nonzero:raise ValueError('All integral samples zero; add splits or use a constant zero')
        peak=max(p[4] for p in panels)
        unresolved=[i for i,p in enumerate(panels) if p[5] and p[4]>=peak*1e-6]
        if not unresolved and error<=max(atol,rtol*abs(value)):
            yield dict(value=sign*value,error=error,evaluations=count,intervals=len(panels),estimated=True);return
        if len(panels)>=MAX_INTERVALS:raise ValueError('Integral interval limit: 256; relax tolerance or add splits')
        index=max(unresolved,key=lambda i:panels[i][4]) if unresolved else max(range(len(panels)),key=lambda i:panels[i][3])
        a,b=panels[index][:2]
        mid=a+(b-a)/2
        left,right=panel(a,mid),panel(mid,b)
        # A roundoff floor cannot be improved by unbounded subdivision. Other
        # intervals may still dominate; the global work/interval caps terminate.
        panels[index]=left;panels.append(right)
        yield {'progress':count}
