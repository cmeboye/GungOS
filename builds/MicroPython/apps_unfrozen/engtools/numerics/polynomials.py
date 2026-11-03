"""Degree <=4 roots: exact binary-coefficient factors and checked iterations.

Integer arithmetic is used only for tiny polynomial factors and Horner/Newton
residuals. Root locations/output remain float32; input conditioning is reported.
"""
import math
from engtools.calculator.evaluate import finite
from engtools.calculator.scientific import hypot
PI=getattr(math,'pi')


def _bits(n):
    if not n:return 0
    h=hex(abs(n));top=int(h[2],16)
    return (len(h)-3)*4+(1 if top<2 else 2 if top<4 else 3 if top<8 else 4)


def _dyadic(x):
    if x==0:return 0,0
    m,e=math.frexp(x)
    return int(m*16777216),e-24


def _parts(n,d):
    if d==0:raise ValueError('Polynomial derivative is zero')
    if n==0:return 0.0,0
    bn,bd=max(0,_bits(n)-24),max(0,_bits(d)-24)
    a=abs(n)>>bn;b=abs(d)>>bd
    return (float(a)/float(b))*(-1 if (n<0)!=(d<0) else 1),bn-bd


def _ratio(n,d,e=0):
    m,p=_parts(n,d)
    try:value=math.ldexp(m,p+e)
    except OverflowError:raise ValueError('Polynomial root exceeds float32 range')
    if not finite(value):raise ValueError('Polynomial root exceeds float32 range')
    return value


def _sqrt_ratio(n,d):
    m,p=_parts(n,d)
    if p%2:m*=2;p-=1
    return math.ldexp(math.sqrt(m),p//2)


def _gcd(a,b):
    while b:a,b=b,a%b
    return abs(a)


def _primitive(p):
    while p and p[0]==0:p=p[1:]
    if not p:return []
    content=0
    for v in p:content=_gcd(content,v)
    if p[0]<0:content=-content
    return [v//content for v in p]


def _remainder(a,b):
    a=list(a)
    while a and len(a)>=len(b):
        x,y=a[0],b[0]
        a=[y*v for v in a]
        for i,v in enumerate(b):a[i]-=x*v
        a=_primitive(a)
        if any(_bits(v)>8192 for v in a):raise ValueError('Polynomial factor work limit')
    return a


def _poly_gcd(a,b):
    while b:a,b=b,_remainder(a,b)
    return _primitive(a)


def _divide(a,b):
    a=list(a);q=[]
    while len(a)>=len(b):
        if a[0]%b[0]:raise ValueError('Polynomial factor division failed')
        c=a[0]//b[0];q.append(c)
        for i,v in enumerate(b):a[i]-=c*v
        a=a[1:]
    if any(a):raise ValueError('Polynomial factor residual')
    return _primitive(q)


def _derivative(c):
    n=len(c)-1
    return [v*(n-i) for i,v in enumerate(c[:-1])]


def _integer_coefficients(coefficients):
    parts=[_dyadic(float(v)) for v in coefficients]
    exponent=min(e for n,e in parts if n)
    return _primitive([n<<(e-exponent) if n else 0 for n,e in parts])


def _factors(c):
    g=_poly_gcd(c,_derivative(c));w=_divide(c,g);i=1;result=[]
    while len(w)>1:
        y=_poly_gcd(w,g);z=_divide(w,y)
        if len(z)>1:result.append((z,i))
        w=y;g=_divide(g,y);i+=1
        if i>5:raise ValueError('Polynomial multiplicity work limit')
    return result


def _horner(c,z):
    """Exact Gaussian-integer numerator; denominator is 2^(shift*degree)."""
    rn,re=_dyadic(z.real);jn,je=_dyadic(z.imag)
    e=min(re if rn else 0,je if jn else 0,0);shift=-e
    r=rn<<(re-e) if rn else 0;j=jn<<(je-e) if jn else 0
    a,b=c[0],0
    for i,v in enumerate(c[1:]):a,b=a*r-b*j+(v<<(shift*(i+1))),a*j+b*r
    return a,b,shift


def _newton(c,d,z):
    a,b,shift=_horner(c,z)
    if a==0 and b==0:return complex(0,0),True
    r,i,_=_horner(d,z);den=r*r+i*i
    if den==0:return None,False
    return complex(_ratio(a*r+b*i,den,-shift),_ratio(b*r-a*i,den,-shift)),False


def _quadratic(c):
    a,b,d=c;disc=b*b-4*a*d
    if disc<0:
        re=_ratio(-b,2*a);im=_sqrt_ratio(-disc,4*a*a)
        return [complex(re,-im),complex(re,im)]
    root=_sqrt_ratio(disc,a*a);beta=_ratio(b,a)
    q=-0.5*beta-math.copysign(0.5*root,beta)
    if q==0:return [complex(0,0),complex(0,0)]
    n,e=_dyadic(q)
    second=_ratio(d,a*n,-e)
    if second==0 and d!=0:raise ValueError('Polynomial root underflow at float32 precision')
    return [complex(q,0),complex(second,0)]


def _solve(c):
    n=len(c)-1
    if n==1:
        value=_ratio(-c[1],c[0])
        if value==0 and c[1]!=0:raise ValueError('Polynomial root underflow at float32 precision')
        return [complex(value,0)]
    if n==2:return _quadratic(c)
    # Power-of-two variable scaling bounds starting points without changing the
    # exact coefficient ratios, or squaring a huge/tiny complex magnitude.
    powers=[(_bits(v)-_bits(c[0])+i-1)//i for i,v in enumerate(c[1:],1) if v]
    exponent=max(powers) if powers else 0
    scaled=_primitive([v<<(exponent*(n-i) if exponent>=0 else -exponent*i) for i,v in enumerate(c)])
    derivative=_derivative(scaled)
    radius=1+max(abs(_ratio(v,scaled[0])) for v in scaled[1:])
    roots=[complex(radius*math.cos(2*PI*(i+0.17)/n),radius*math.sin(2*PI*(i+0.17)/n)) for i in range(n)]
    for iteration in range(192):
        new=[];settled=True
        for i,z in enumerate(roots):
            delta,exact=_newton(scaled,derivative,z)
            if delta is None:delta=complex(0.01*(i+1),0.01)
            elif not exact:
                repulsion=complex(0,0)
                for j,other in enumerate(roots):
                    if j==i:continue
                    gap=z-other
                    if gap==0:raise ValueError('Unresolved clustered polynomial roots')
                    repulsion+=1/gap
                divisor=1-delta*repulsion
                if divisor!=0:delta/=divisor
            candidate=z-delta
            if not finite(candidate):raise ValueError('Polynomial iteration exceeded float32')
            if hypot(delta.real,delta.imag)>3e-7*max(hypot(candidate.real,candidate.imag),1e-30):settled=False
            new.append(candidate)
        roots=new
        if iteration%4==0:yield {'progress':iteration+1}
        if settled:break
    # Verify locations with exact Horner residual/Newton steps, not just a small
    # float32 polynomial value. A zero candidate is valid only for a zero factor.
    result=[]
    for z in roots:
        delta,exact=_newton(scaled,derivative,z)
        if z==0 and scaled[-1]!=0:raise ValueError('Polynomial root dynamic range exceeds float32')
        if not exact and (delta is None or hypot(delta.real,delta.imag)>2e-6*max(hypot(z.real,z.imag),1e-37)):
            raise ValueError('Polynomial root locations did not converge')
        re=math.ldexp(z.real,exponent);im=math.ldexp(z.imag,exponent)
        if not finite(re) or not finite(im):raise ValueError('Polynomial roots exceed float32 range')
        if re==0 and im==0 and c[-1]!=0:raise ValueError('Polynomial root underflow at float32 precision')
        result.append(complex(re,im))
    for i,z in enumerate(result):
        for other in result[:i]:
            gap=z-other
            if hypot(gap.real,gap.imag)<=8*1.1920929e-7*max(hypot(z.real,z.imag),hypot(other.real,other.imag),1e-37):
                raise ValueError('Distinct roots unresolved at float32 precision')
    return result


def polynomial_job(coefficients):
    if not 3<=len(coefficients)<=5 or not all(not isinstance(v,complex) and finite(v) for v in coefficients):
        raise ValueError('Use finite real coefficients for degree 2..4')
    if coefficients[0]==0:raise ValueError('Leading coefficient must be nonzero')
    c=_integer_coefficients(coefficients);roots=[];multiplicities=[];warnings=[]
    for factor,multiplicity in _factors(c):
        # Deflate exact zero roots before selecting a numerical variable scale.
        zeros=0
        while len(factor)>1 and factor[-1]==0:zeros+=1;factor=factor[:-1]
        found=[complex(0,0)]*zeros
        if len(factor)>1:
            solver=_solve(factor)
            if isinstance(solver,list):found+=solver
            else:
                while True:
                    try:yield next(solver)
                    except StopIteration as done:
                        found+=done.value;break
        for z in found:
            if not finite(z):raise ValueError('Polynomial roots exceed float32 range')
            roots.extend([z]*multiplicity);multiplicities.extend([multiplicity]*multiplicity)
        if multiplicity>1 and 'Repeated roots: coefficient-sensitive' not in warnings:
            warnings.append('Repeated roots: coefficient-sensitive')
    order=sorted(range(len(roots)),key=lambda i:(roots[i].real,roots[i].imag))
    roots=[roots[i] for i in order];multiplicities=[multiplicities[i] for i in order]
    if len(roots)!=len(c)-1:raise ValueError('Polynomial root count mismatch')
    for i,z in enumerate(roots):
        for j,other in enumerate(roots[:i]):
            if z!=other and hypot((z-other).real,(z-other).imag)<0.05*max(hypot(z.real,z.imag),hypot(other.real,other.imag),1e-37):
                if 'Clustered roots: coefficient-sensitive' not in warnings:warnings.append('Clustered roots: coefficient-sensitive')
    yield {'roots':roots,'multiplicities':multiplicities,'warnings':warnings,'approximate':True}
