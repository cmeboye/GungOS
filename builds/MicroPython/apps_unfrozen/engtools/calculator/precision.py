"""Decimal rounding of stored numbers; exact ties, then float32 quantization."""
import math


def _bits(n):
    if n==0:return 0
    h=hex(abs(n));top=int(h[2],16)
    return (len(h)-3)*4+(1 if top<2 else 2 if top<4 else 3 if top<8 else 4)


def _fraction(x):
    if isinstance(x,int):return x,1
    m,e=math.frexp(x);n=int(m*16777216);e-=24
    return (n<<e,1) if e>=0 else (n,1<<(-e))


def _nearest(n,d):
    q,r=divmod(abs(n),d)
    if 2*r>d or (2*r==d and q%2):q+=1
    return -q if n<0 else q


def _float32(n,d,negative=False):
    if n==0:return math.copysign(0.0,-1 if negative else 1)
    negative=n<0;n=abs(n);b=_bits(n)-_bits(d)
    below=(n<d<<b) if b>=0 else (n<<(-b)<d)
    if below:b-=1
    exponent=max(b-23,-149)
    q=_nearest(n<<(-exponent),d) if exponent<0 else _nearest(n,d<<exponent)
    try:value=math.ldexp(float(q),exponent)
    except OverflowError:raise ValueError('Rounded result exceeds float32 range')
    if math.isinf(value):raise ValueError('Rounded result exceeds float32 range')
    return math.copysign(value,-1 if negative else 1)


def _places(x,digits):
    n,d=_fraction(x)
    if digits>=0:
        scale=10**digits;q=_nearest(n*scale,d)
        return _float32(q,scale,math.copysign(1,x)<0)
    scale=10**(-digits);q=_nearest(n,d*scale)*scale
    if isinstance(x,int):
        from .scientific import RESULT_LIMIT
        if abs(q)>RESULT_LIMIT:raise ValueError('Rounded result exceeds float32 range')
        return q
    return _float32(q,1,math.copysign(1,x)<0)


def decimal_round(x,digits):
    from .scientific import integer,real
    real(x,'round');digits=integer(digits,'round digits',45,-45)
    if isinstance(x,int) and digits>=0:return x
    return _places(x,digits)


def significant(x,digits):
    from .scientific import integer,real
    real(x,'sigfig');digits=integer(digits,'significant digits',7,1)
    if x==0:return x
    n,d=_fraction(x);e=_exponent(abs(n),d,x)
    return _places(x,digits-1-e)


def _exponent(n,d,x):
    e=int(math.floor(math.log10(abs(x))))
    def less(power):return n<d*10**power if power>=0 else n*10**(-power)<d
    # log10 can round to the next decade in float32: fix the exponent exactly.
    while less(e):e-=1
    while not less(e+1):e+=1
    return e


def format_subnormal(x,engineering=False):
    # Native float32 %g formatting mishandles subnormals on this build. Round
    # the exact binary fraction to decimal digits without normalizing in float.
    n,d=_fraction(x);e=_exponent(abs(n),d,x);digits=6 if engineering else 7
    q=abs(_nearest(n*10**(digits-1-e),d))
    if q>=10**digits:q//=10;e+=1
    exponent=e-e%3 if engineering else e
    text=str(q);before=e-exponent+1
    mantissa=text[:before]+('.'+text[before:] if before<len(text) else '')
    if '.' in mantissa:mantissa=mantissa.rstrip('0').rstrip('.')
    return ('-' if n<0 else '')+mantissa+('e%+d'%exponent)
