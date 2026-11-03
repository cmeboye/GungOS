"""Lazy F7 families: signatures and examples, including every scalar function."""
CATEGORIES=(
 ('Templates','Rendered structures and symbols',(
  ('pow','Power x^y','Type x^ then Space'),('sub','Subscript x_n','Type x_ then Space'),
  ('frac','Fraction a/b','Stacked numerator / denominator'),('sqrt','Square root','sqrt(9) = 3'),
  ('int','Integral in x','int(0,1,x^2) = 1/3'),('logb','Log with base','logb(2,8) = 3'),
  ('sum','Sum (Sigma)','sum(k,1,10,k) = 55'),('prod','Product (Pi)','prod(k,1,5,k) = 120'),('pi','Pi constant','pi = 3.141593'))),
 ('Trig and angles','DEG/RAD angles; atan2(y,x)',(
  ('sin','sin(x)','sin(30) = 0.5 in DEG'),('cos','cos(x)','cos(60) = 0.5 in DEG'),
  ('tan','tan(x)','Exact poles report an error'),('asin','asin(x)','asin(0.5) = 30 in DEG'),
  ('acos','acos(x)','acos(0.5) = 60 in DEG'),('atan','atan(x)','atan(1) = 45 in DEG'),
  ('atan2','atan2(y,x)','atan2(1,-1) = 135 in DEG'))),
 ('Hyperbolic','Not affected by DEG/RAD setting',(
  ('sinh','sinh(x)','sinh(0) = 0'),('cosh','cosh(x)','cosh(0) = 1'),('tanh','tanh(x)','tanh(0) = 0'),
  ('asinh','asinh(x)','Real or principal complex inverse'),('acosh','acosh(x)','Real x >= 1; Complex extends'),
  ('atanh','atanh(x)','Real |x| < 1; +/-1 singular'))),
 ('Powers and logs','Roots, logarithms and exponential',(
  ('sqrt','sqrt(x)','Complex mode: sqrt(-1) = i'),('cbrt','cbrt(x)','cbrt(-8) = -2 (real root)'),
  ('root','root(n,x)','root(3,-27) = -3'),('ln','ln(x)','Natural logarithm'),('log','log(x)','Base 10 logarithm'),
  ('logb','logb(base,x)','logb(2,8) = 3'),('exp','exp(x)','exp(1) = e'))),
 ('Complex and polar','Radius/phase to rect(r,angle)',(
  ('abs','abs(x)','abs(3+4i) = 5'),('re','re(z)','Real part'),('im','im(z)','Imaginary part'),
  ('conj','conj(z)','Complex conjugate'),('radius','radius(z)','Polar radius; magnitude'),
  ('phase','phase(z)','Polar angle in selected DEG/RAD'),('rect','rect(r,angle)','rect(2,90) = 2i in DEG'))),
 ('Integers','Checked integer domains and range',(
  ('factorial','Factorial x!','Integer x from 0 to 34'),('ncr','ncr(n,r)','ncr(5,2) = 10'),
  ('npr','npr(n,r)','npr(5,2) = 20'),('gcd','gcd(a,b,...)','gcd(-48,18) = 6'),
  ('lcm','lcm(a,b,...)','lcm(12,18) = 36'))),
 ('Stable math','Small increments and scaled norm',(
  ('log1p','log1p(x)','Accurate ln(1+x); x > -1'),('expm1','expm1(x)','Accurate exp(x)-1 near zero'),
  ('hypot','hypot(x,y)','hypot(3,4) = 5; scaled norm'))),
 ('Rounding and bounds','Half-even rounding; finite real x',(
  ('round','round(x[,digits])','round(1.25,1) = 1.2'),('sigfig','sigfig(x,digits)','sigfig(1.23456,4) = 1.235'),
  ('trunc','trunc(x)','trunc(-2.9) = -2'),('floor','floor(x)','floor(-2.9) = -3'),('ceil','ceil(x)','ceil(-2.9) = -2'),
  ('min','min(a,b,...)','Smallest argument; min(X) dataset'),('max','max(a,b,...)','Largest argument; max(X) dataset'))),
 ('Special functions','Real gamma, log-gamma and error',(
  ('gamma','gamma(x)','gamma(5) = 24; poles rejected'),('lgamma','lgamma(x)','ln(abs(gamma(x))); poles rejected'),
  ('erf','erf(x)','erf(0) = 0'),('erfc','erfc(x)','Complementary error function'))),
 ('Statistics','Uses the selected Statistics dataset',(
  ('sum_X','sum(X)','Dataset sum; Y also accepted'),('prod_X','prod(X)','Product with frequency semantics'),
  ('mean_X','mean(X)','Dataset mean'),('std_X','std(X)','Sample standard deviation'),('pstd_X','pstd(X)','Population standard deviation'),
  ('var_X','var(X)','Sample variance'),('pvar_X','pvar(X)','Population variance'),('sum2_X','sum2(X)','Sum of squares'),
  ('n_X','n(X)','Observation count'),('median_X','median(X)','Dataset median'),('q1_X','q1(X)','First quartile'),
  ('q3_X','q3(X)','Third quartile'),('iqr_X','iqr(X)','Interquartile range'),('range_X','range(X)','Maximum minus minimum'),
  ('min_X','min(X)','Dataset minimum'),('max_X','max(X)','Dataset maximum'),
  ('cov_XY','cov(X,Y)','Sample covariance'),('pcov_XY','pcov(X,Y)','Population covariance'),('corr_XY','corr(X,Y)','Correlation'),
  ('slope','slope()','Regression slope'),('intercept','intercept()','Regression intercept'),('r2','r2()','Regression R squared'),
  ('predict','predict(x)','Predicted Y for given X'))),
 ('Matrix','Matrix expression mode only',(
  ('MatA','MatA','Stored matrix A'),('MatB','MatB','Stored matrix B'),('MatC','MatC','Stored matrix C'),
  ('MatD','MatD','Stored matrix D'),('MatAns','MatAns','Latest matrix result'),
  ('det','det(matrix)','Determinant'),('inv','inv(matrix)','Inverse'),('trn','trn(matrix)','Transpose'),
  ('trace','trace(matrix)','Sum of diagonal entries'),('identity','identity(n)','Identity, size 1..4'))),
)


def groups(matrix=False):return CATEGORIES if matrix else CATEGORIES[:-1]


def location(token,matrix=False):
    for i,(_,_,entries) in enumerate(groups(matrix)):
        for j,entry in enumerate(entries):
            if entry[0]==token:return i,j
    raise ValueError('Function not in this catalogue')


def text(token):
    if '_' in token:
        name,column=token.split('_',1)
        return name+'('+('X,Y' if column=='XY' else column)+')',False
    if token.startswith('Mat'):return token,False
    return token+'()',token not in ('slope','intercept','r2')
