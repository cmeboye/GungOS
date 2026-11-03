"""Bounded scalar helpers, including float32-safe complex inverse trig."""
import math
PI=getattr(math,'pi')

INTEGER_LIMIT=16777216
RESULT_LIMIT=340282346638528859811704183484516925440


def integer(value,label,limit=INTEGER_LIMIT,minimum=0):
    if isinstance(value,complex) or value!=int(value) or not minimum<=value<=limit:
        raise ValueError(label+' must be an integer %d..%d'%(minimum,limit))
    return int(value)


def combinatorial(name,n,r,charge=None):
    n=integer(n,name+' n');r=integer(r,name+' r')
    if r>n:raise ValueError(name+' requires 0 <= r <= n')
    if name=='ncr':r=min(r,n-r)
    if r>1024:raise ValueError(name+' work limit: 1024 factors')
    result=1
    for k in range(1,r+1):
        if charge:charge()
        result=result*(n-r+k)//k if name=='ncr' else result*(n-k+1)
        if result>RESULT_LIMIT:raise ValueError(name+' result exceeds float32 range')
    return result


def real_root(n,x):
    if isinstance(n,complex) or n!=int(n) or not 1<=abs(n)<=1024:
        raise ValueError('root degree: nonzero integer -1024..1024')
    if isinstance(x,complex):raise ValueError('Real roots require a real argument')
    n=int(n)
    if x<0 and n%2==0:raise ValueError('Even real roots need a nonnegative argument')
    if x==0:
        if n<0:raise ValueError('Negative root degree requires a nonzero argument')
        return x
    value=math.copysign(abs(x)**(1.0/n),x)
    if value==0:raise ValueError('Root underflow; rescale the argument')
    return value


def tangent_pole(a,angle):
    """Reject canonical represented poles, with no neighbourhood epsilon."""
    if isinstance(a,complex):
        if a.imag!=0:return False
        a=a.real
    if angle=='DEG':return a%180==90
    # mpy-cross folds math.pi with host-double arithmetic; its decimal
    # serialization can round a float32 ULP differently on load. The policy
    # must use exactly the same runtime pi as the evaluator's pi constant.
    half_pi=PI/2
    q=a/half_pi
    # Past this size, float32 cannot distinguish adjacent integer multiples.
    if abs(q)>INTEGER_LIMIT:return False
    n=int(q)
    return q==n and n%2!=0 and a==n*half_pi


def hypot(x,y):
    x,y=max(abs(x),abs(y)),min(abs(x),abs(y))
    if x==0:return 0.0
    return x*math.sqrt(1+(y/x)**2)


def log1p(x):
    # MicroPython has no math.log1p. Correct log(1+x)'s rounded increment;
    # return x directly when it is below the representable increment at 1.
    u=1+x
    if u==1:return x
    return math.log(u)*(x/(u-1))


def _sqrt(x,y):
    """Cartesian square root without x*x+y*y or cancellation on either axis."""
    if x==0 and y==0:return 0.0,y
    scale=max(abs(x),abs(y));xx=x/scale;yy=y/scale
    t=math.sqrt(scale)*math.sqrt((hypot(xx,yy)+abs(xx))/2)
    if x>=0:return t,y/(2*t)
    return abs(y)/(2*t),math.copysign(t,y)


def _complex(real,imag):
    # MicroPython's two-argument constructor adds +0 to imag, erasing -0.
    return -complex(-real,-imag) if imag==0 and math.copysign(1,imag)<0 else complex(real,imag)


def complex_inverse(name,z):
    """Principal values; preserve the side of a cut using signed zero."""
    x,y=z.real,z.imag
    scale=max(abs(x),abs(y))
    if name in ('asin','acos'):
        if scale>1e10:
            # At this scale the omitted relative correction is below float32
            # resolution. Log the scaled magnitude, never square large inputs.
            real=math.atan2(x,abs(y)) if name=='asin' else math.atan2(abs(y),x)
            imag=math.log(scale)+0.5*log1p((min(abs(x),abs(y))/scale)**2)+math.log(2)
            imag=math.copysign(imag,y)
        else:
            ar,ai=_sqrt(1-x,-y);br,bi=_sqrt(1+x,y)
            p=ar*br-ai*bi;q=ar*bi-ai*br
            real=math.atan2(x,p) if name=='asin' else math.atan2(p,x)
            imag=math.asinh(q)
        return _complex(real,imag if name=='asin' else -imag)
    if x==0 and abs(y)==1:raise ValueError('atan is singular at +i and -i')
    # atan's imaginary part is 1/4 log1p(4|y| / (x*x+(|y|-1)^2)).
    # Scale the ratio before squaring; keep tiny imaginary parts near zero.
    ay=abs(y);dscale=max(abs(x),abs(ay-1))
    dsum=(x/dscale)**2+((ay-1)/dscale)**2
    ratio=(4*(ay/dscale)/dsum)/dscale
    if math.isinf(ratio):
        imag=0.5*(math.log(hypot(x,ay+1))-math.log(dscale)-0.5*math.log(dsum))
    else:imag=0.25*log1p(ratio)
    if scale>1e10:
        inv=1/scale;xx=x/scale;yy=y/scale
        real=0.5*math.atan2(2*xx*inv,inv*inv-xx*xx-yy*yy)
    else:real=0.5*math.atan2(2*x,(1-y)*(1+y)-x*x)
    return _complex(real,math.copysign(imag,y))


def complex_sqrt(z):
    return _complex(*_sqrt(z.real,z.imag))


def complex_log(z):
    x,y=z.real,z.imag;scale=max(abs(x),abs(y))
    if scale==0:raise ValueError('Log is undefined at zero')
    real=math.log(scale)+0.5*log1p((min(abs(x),abs(y))/scale)**2)
    return _complex(real,math.atan2(y,x))


def real(value,name):
    if not isinstance(value,(int,float)) or math.isnan(value) or math.isinf(value):
        raise ValueError(name+' requires a finite real argument')
    return value


def integer_reduce(name,values,charge):
    if len(values)>32:raise ValueError(name+' accepts up to 32 integers')
    values=[integer(real(v,name),name+' argument',INTEGER_LIMIT,-INTEGER_LIMIT) for v in values]
    result=0 if name=='gcd' else 1
    for value in values:
        a,b=abs(result),abs(value)
        while b:
            charge();a,b=b,a%b
        result=a if name=='gcd' else (abs(result//a*value) if a else 0)
        if result>RESULT_LIMIT:raise ValueError(name+' result exceeds float32 range')
    return result


def complex_hyperbolic(name,z):
    if name=='acosh':
        a=complex_inverse('acos',z)
        return _complex(-a.imag,a.real) if math.copysign(1,z.imag)>0 else _complex(a.imag,-a.real)
    if name=='atanh' and z.imag==0 and abs(z.real)==1:
        raise ValueError('atanh is singular at +1 and -1')
    a=complex_inverse('asin' if name=='asinh' else 'atan',_complex(-z.imag,z.real))
    return _complex(a.imag,-a.real)


def _rect(radius,angle,unit):
    radius=float(real(radius,'rect'));angle=real(angle,'rect')
    quadrant=None
    if unit=='DEG':
        reduced=math.fmod(angle,360)
        if math.fmod(reduced,90)==0:quadrant=int(reduced/90)%4
        angle=reduced*(PI/180)
    else:
        half_pi=PI/2;q=angle/half_pi
        if abs(q)<=INTEGER_LIMIT and q==int(q) and angle==int(q)*half_pi:quadrant=int(q)%4
    if quadrant is None:cosine,sine=math.cos(angle),math.sin(angle)
    else:
        cosine=(1,0,-1,0)[quadrant];sine=(0,1,0,-1)[quadrant]
        if sine==0:sine=math.copysign(0.0,angle)
    return _complex(radius*cosine,radius*sine)


def function(name,values,angle,complex_mode,charge):
    """Additional scalar functions; all domains/arity checked before dispatch."""
    count=len(values)
    if name in ('gcd','lcm'):return integer_reduce(name,values,charge)
    if name=='round':
        if count not in (1,2):raise ValueError('round(x[,digits])')
        real(values[0],name)
        if count==1:return round(values[0])
        from .precision import decimal_round
        return decimal_round(*values)
    expected=2 if name in ('atan2','rect','hypot','sigfig') else 1
    if count!=expected:raise ValueError(name+' needs '+str(expected)+' argument(s)')
    a=values[0]
    if name in ('phase','radius'):
        if isinstance(a,complex):x,y=a.real,a.imag
        else:x,y=real(a,name),0.0
        real(x,name);real(y,name)
        if name=='radius':return hypot(x,y)
        value=math.atan2(y,x)
        return value*(180/PI) if angle=='DEG' else value
    if name=='rect':return _rect(*values,angle)
    if name in ('asinh','acosh','atanh'):
        extend=complex_mode and not isinstance(a,complex) and ((name=='acosh' and a<1) or (name=='atanh' and abs(a)>1))
        if isinstance(a,complex) or extend:return complex_hyperbolic(name,complex(a))
        real(a,name)
        if name=='acosh' and a<1:raise ValueError('acosh needs x >= 1; use Complex mode otherwise')
        if name=='atanh' and not -1<a<1:raise ValueError('atanh needs -1 < x < 1; +/-1 are singular')
        return getattr(math,name)(a)
    for value in values:real(value,name)
    if name=='atan2':
        value=math.atan2(*values)
        return value*(180/PI) if angle=='DEG' else value
    if name=='hypot':return hypot(*values)
    if name=='log1p':
        if a<=-1:raise ValueError('log1p needs x > -1')
        return log1p(a)
    if name=='sigfig':
        from .precision import significant
        return significant(*values)
    if name in ('gamma','lgamma') and a<=0 and a==int(a):
        raise ValueError(name+' is undefined at nonpositive integers')
    native=getattr(math,name,None)
    if native is None:raise ValueError(name+' requires the matching scientific firmware')
    try:return native(a)
    except (ValueError,OverflowError):raise ValueError(name+' argument or result out of range')
