"""Bounded real-equation jobs and degree 2..4 complex polynomial roots."""
import math
from engtools.calculator.evaluate import Parser,Evaluator,finite,native_function

def equation(text,variables=None,angle='DEG'):
    if text.count('=')>1: raise ValueError('Use one equation or expression in x')
    parts=text.split('=')
    left=Parser(parts[0]).parse()
    right=Parser(parts[1] if len(parts)>1 else '0').parse()
    if left[0] or right[0]: raise ValueError('Assignments are not allowed in equations')
    constants=dict(variables or {})
    native=native_function(left[1],constants,angle),native_function(right[1],constants,angle)
    if native[0] is not None and native[1] is not None:
        fl,fr=native
        def evaluate(x):
            a,b=fl(x),fr(x)
            if a is None or b is None: raise ValueError('Equation is not finite and real here')
            value,scale=a-b,1+abs(a)+abs(b)
            if not finite(value) or not finite(scale): raise ValueError('Equation scaling exceeds float32 range')
            return value,scale
        return evaluate
    def evaluate(x):
        evaluator=Evaluator(constants,angle)
        a,b=evaluator.run(left[1],{'x':x}),evaluator.run(right[1],{'x':x})
        if isinstance(a,complex) or isinstance(b,complex) or not finite(a) or not finite(b):
            raise ValueError('Equation is not finite and real here')
        value,scale=a-b,1+abs(a)+abs(b)
        if not finite(value) or not finite(scale): raise ValueError('Equation scaling exceeds float32 range')
        return value,scale
    return evaluate

def root_job(text,lower=-10,upper=10,guess=0,variables=None,angle='DEG'):
    """Yield progress and a verified root; Escape can cancel between steps."""
    if not all(finite(v) for v in (lower,upper,guess)) or lower>=upper or not lower<=guess<=upper:
        raise ValueError('Use lower < upper and a guess inside the interval')
    f=equation(text,variables,angle)
    fa,sa=f(lower); fb,sb=f(upper)
    if fa==0: yield {'root':lower,'residual':0.0,'iterations':0}; return
    if fb==0: yield {'root':upper,'residual':0.0,'iterations':0}; return
    bracket=(fa<0)!=(fb<0)
    # A fixed absolute residual accepts any sufficiently small equation, even
    # a nonzero constant. Normalize to this problem and require x convergence.
    reference=max(abs(fa),abs(fb))
    x=guess
    for iteration in range(1,97):
        if bracket: x=lower+(upper-lower)*0.5
        value,scale=f(x)
        residual_ok=abs(value)<=2e-6*reference
        position_ok=bracket and abs(upper-lower)<=4e-6*max(1,abs(x))
        if value==0 or (residual_ok and position_ok):
            # A pole can look like a sign crossing, but cannot pass this check.
            yield {'root':x,'residual':abs(value),'iterations':iteration}; return
        if bracket:
            if (fa<0)!=(value<0): upper,fb=x,value
            else: lower,fa=x,value
            if upper==lower or x==lower+(upper-lower)*0.5:
                raise ValueError('No converged root; possible discontinuity')
        else:
            step=max(1e-4,abs(x)*4e-4)
            a,b=max(lower,x-step),min(upper,x+step)
            va,_=f(a); vb,_=f(b)
            derivative=(vb-va)/(b-a) if b>a else 0
            if derivative==0: raise ValueError('Flat derivative: change the guess or interval')
            candidate=x-value/derivative
            if not finite(candidate) or not lower<=candidate<=upper:
                raise ValueError('Newton step left the interval; change the guess')
            if residual_ok and abs(candidate-x)<=2e-6*max(1,abs(x)):
                yield {'root':x,'residual':abs(value),'iterations':iteration}; return
            if candidate==x: raise ValueError('Root did not converge at float32 precision')
            x=candidate
        if iteration%4==0: yield {'progress':iteration}
    raise ValueError('No root converged within 96 iterations')

def polynomial_job(coefficients):
    from .polynomials import polynomial_job as solve
    return solve(coefficients)
