"""Small real float32 matrices; native QR/dot with bounded UI workspaces."""
from .backend import require, guarded_qr

MAX_SIZE=4

def matrix(values):
    np,_=require()
    result=np.array(values,dtype=np.float)
    validate(result)
    return result

def validate(value):
    np,_=require()
    if not isinstance(value,np.ndarray) or value.ndim!=2:
        raise ValueError('Expected a real 2D matrix')
    if any(n<1 or n>MAX_SIZE for n in value.shape):
        raise ValueError('Matrix dimensions: 1..4')
    if value.dtype!=np.float or not np.all(np.isfinite(value)):
        raise ValueError('Matrix values must be finite real numbers')
    return value

def square(value):
    validate(value)
    if value.shape[0]!=value.shape[1]: raise ValueError('A square matrix is required')
    return value.shape[0]

def identity(size):
    np,_=require()
    if size!=int(size) or not 1<=size<=MAX_SIZE: raise ValueError('Identity size: 1..4')
    result=np.zeros((int(size),int(size)))
    for i in range(int(size)): result[i,i]=1
    return result

def solve(a,b):
    """Native QR solve with row scaling, rank checks and residual verification."""
    np,sp=require()
    size=square(a)
    validate(b)
    if b.shape[0]!=size: raise ValueError('Right-hand side has the wrong row count')
    scaled=np.array(a)
    rhs=np.array(b)
    for i in range(size):
        scale=max(abs(a[i,j]) for j in range(size))
        if scale==0: raise ValueError('Singular system: no unique solution')
        for j in range(size): scaled[i,j]/=scale
        for j in range(b.shape[1]): rhs[i,j]/=scale
    q,r=guarded_qr(scaled)
    if any(abs(r[i,i])<2e-6 for i in range(size)):
        raise ValueError('Singular or ill-conditioned matrix')
    result=np.zeros(b.shape)
    for col in range(b.shape[1]):
        vector=np.array([rhs[i,col] for i in range(size)])
        projected=np.dot(q.transpose(),vector)
        solved=sp.linalg.solve_triangular(r,projected,lower=False)
        for i in range(size): result[i,col]=solved[i]
    validate(result)
    product=np.dot(scaled,result)
    for i in range(size):
        for j in range(b.shape[1]):
            scale=1+abs(rhs[i,j])+sum(abs(scaled[i,k]*result[k,j]) for k in range(size))
            if abs(product[i,j]-rhs[i,j])>2e-5*scale:
                raise ValueError('Solve residual too large for float32')
    return result

def inverse(a): return solve(a,identity(square(a)))

def determinant(a):
    np,_=require()
    n=square(a)
    work=np.array(a)
    result=1.0
    for col in range(n):
        pivot=max(range(col,n),key=lambda row:abs(work[row,col]))
        value=work[pivot,col]
        if value==0: return 0.0
        if pivot!=col:
            for j in range(n): work[col,j],work[pivot,j]=work[pivot,j],work[col,j]
            result=-result
        result*=work[col,col]
        for row in range(col+1,n):
            multiplier=work[row,col]/work[col,col]
            for j in range(col+1,n): work[row,j]-=multiplier*work[col,j]
    from math import isfinite
    if not isfinite(result): raise ValueError('Determinant exceeds float32 range')
    return result

def power(a,exponent):
    n=square(a)
    if exponent!=int(exponent) or abs(exponent)>8: raise ValueError('Matrix exponent: integer -8..8')
    np,_=require()
    work=inverse(a) if exponent<0 else a
    result=identity(n)
    for _ in range(abs(int(exponent))): result=np.dot(result,work)
    return validate(result)
