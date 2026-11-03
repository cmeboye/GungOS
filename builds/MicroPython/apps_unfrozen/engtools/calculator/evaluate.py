"""Small arithmetic parser: no Python eval, attribute access or arbitrary calls."""
import math
# Read runtime constants, avoiding host-double folding/decimal reload in mpy-cross.
PI=getattr(math,'pi')
E=getattr(math,'e')

EXTRA_FUNCTIONS=('atan2','phase','radius','rect','gcd','lcm','asinh','acosh','atanh',
                 'log1p','expm1','hypot','sigfig','trunc','gamma','lgamma','erf','erfc')

STAT_FUNCTIONS = ('mean', 'std', 'pstd', 'var', 'pvar', 'sum', 'prod', 'sum2', 'n', 'median',
                  'q1', 'q3', 'iqr', 'range', 'cov', 'pcov', 'corr', 'slope', 'intercept', 'r2', 'predict')
FUNCTIONS = ('sin', 'cos', 'tan', 'asin', 'acos', 'atan', 'sinh', 'cosh', 'tanh',
             'sqrt', 'ln', 'log', 'logb', 'exp', 'abs', 'floor', 'ceil', 'round',
             're', 'im', 'conj', 'int', 'min', 'max', 'ncr', 'npr', 'cbrt', 'root')+STAT_FUNCTIONS+EXTRA_FUNCTIONS
RESERVED = FUNCTIONS+('pi', 'e', 'i', 'ans', 'Ans', 'j', 'X', 'Y')
REDUCTION_LIMIT = 1024


def finite(value):
    parts = (value.real, value.imag) if isinstance(value, complex) else (value,)
    return all(not math.isnan(p) and not math.isinf(p) for p in parts)


def tokens(text):
    if len(text) > 1400: raise ValueError('Expression too long')
    result, i = [], 0
    while i < len(text):
        char = text[i]
        if char.isspace(): i += 1; continue
        if char.isdigit() or char == '.':
            start = i
            while i < len(text) and (text[i].isdigit() or text[i] == '.'): i += 1
            if i < len(text) and text[i] in 'eE':
                end = i+1
                if end < len(text) and text[end] in '+-': end += 1
                exponent = end
                while end < len(text) and text[end].isdigit(): end += 1
                if end > exponent: i = end
            try: value = float(text[start:i])
            except ValueError: raise ValueError('Invalid number')
            if not finite(value): raise ValueError('Number out of range')
            if result and result[-1][0] == 'number':
                raise ValueError('Separate numbers with an operator')
            result.append(('number', value))
        elif char.isalpha():
            start = i
            while i < len(text) and (text[i].isalpha() or text[i].isdigit() or text[i] == '_'): i += 1
            name = text[start:i]
            if len(name) > 16: raise ValueError('Variable names: up to 16 characters')
            result.append(('name', name))
        elif char in '+-*/^%!(),=':
            if char == '*' and i+1 < len(text) and text[i+1] == '*':
                result.append(('^', '^')); i += 2
            else: result.append((char, char)); i += 1
        else: raise ValueError('Unsupported character: '+char)
    if len(result) > 384: raise ValueError('Expression limit exceeded')
    result.append(('end', ''))
    return result


class Parser:
    def __init__(self, text, functions=FUNCTIONS):
        self.items, self.index, self.depth = tokens(text), 0, 0
        self.functions=functions

    def peek(self): return self.items[self.index][0]

    def take(self):
        value = self.items[self.index]
        self.index += 1
        return value

    def expression(self, minimum=0):
        self.depth += 1
        if self.depth > 40: raise ValueError('Expression nesting limit')
        kind, value = self.take()
        if kind == 'number': node = ('value', value)
        elif kind in ('+', '-'):
            node = ('unary', kind, self.expression(25))
        elif kind == '(':
            node = self.expression()
            if self.peek() != ')': raise ValueError('Missing closing parenthesis')
            self.take()
        elif kind == 'name':
            if self.peek() == '(' and value in self.functions:
                self.take(); args = []
                if self.peek() != ')':
                    while True:
                        args.append(self.expression())
                        if self.peek() != ',': break
                        self.take()
                if self.peek() != ')': raise ValueError('Missing closing parenthesis')
                self.take()
                node = ('call', value, args)
            else: node = ('name', value)
        else: raise ValueError('Expected a number or expression')
        while True:
            kind = self.peek()
            if kind == '!':
                if 40 < minimum: break
                self.take(); node = ('factorial', node); continue
            implicit = kind in ('number', 'name', '(')
            priority = 20 if implicit else {'+':10, '-':10, '*':20, '/':20, '%':20, '^':30}.get(kind, -1)
            if priority < minimum: break
            if not implicit: self.take()
            operator = '*' if implicit else kind
            right = self.expression(priority if operator == '^' else priority+1)
            node = ('binary', operator, node, right)
        self.depth -= 1
        return node

    def parse(self):
        assignment = None
        if self.peek() == 'name' and self.items[1][0] == '=':
            assignment = self.take()[1]; self.take()
            if assignment in RESERVED: raise ValueError('This name is reserved')
        node = self.expression()
        if self.peek() != 'end': raise ValueError('Unexpected '+str(self.items[self.index][1]))
        return assignment, node


# Use the firmware's formula compiler for repeated evaluation (tests switch it off).
NATIVE_FORMULA = True
_DIRECT = {'sqrt': 'sqrt', 'exp': 'exp', 'abs': 'abs', 'floor': 'floor', 'ceil': 'ceil',
           'round': 'round', 'sinh': 'sinh', 'cosh': 'cosh', 'tanh': 'tanh', 'ln': 'log',
           'log': 'log10', 'sin': 'sin', 'cos': 'cos', 'tan': 'tan', 'asin': 'asin',
           'acos': 'acos', 'atan': 'atan', 're': '', 'conj': ''}


class _Unsupported(Exception):
    pass


def _formula_text(node, variables, angle, local, constants):
    """Python text that follows Evaluator.run step for step on real values."""
    def constant(value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise _Unsupported
        if isinstance(value, int):
            if abs(value) >= 1 << 24: raise _Unsupported
            return '(%d)' % value
        name = '_c%d' % len(constants)
        constants[name] = value
        return name

    def text(node):
        kind = node[0]
        if kind == 'value': return constant(node[1])
        if kind == 'name':
            name = node[1]
            if name == local: return 'x'
            if name == 'pi': return constant(PI)
            if name == 'e': return constant(E)
            if name in ('ans', 'Ans'): return constant(variables.get('Ans', 0))
            if name in ('i', 'j') or name not in variables: raise _Unsupported
            return constant(variables[name])
        if kind == 'unary':
            inner = text(node[2])
            return '(-%s)' % inner if node[1] == '-' else inner
        if kind == 'binary':
            op = '**' if node[1] == '^' else node[1]
            # Evaluator.run checks every operation's result is finite.
            return '_finite(%s%s%s)' % (text(node[2]), op, text(node[3]))
        if kind != 'call': raise _Unsupported
        # The calculator now rejects exact represented tangent poles. Older
        # native Formula firmware does not, so retain the Python policy here.
        if node[1]=='tan':raise _Unsupported
        name, args = node[1], [text(arg) for arg in node[2]]
        if name in ('min', 'max'):
            if not args: raise _Unsupported
            return args[0] if len(args) == 1 else '%s(%s)' % (name, ','.join(args))
        if name == 'logb' and len(args) == 2:
            return '_finite(log(%s)/log(%s))' % (args[1], args[0])
        if name not in _DIRECT or len(args) != 1: raise _Unsupported
        a = args[0]
        if name in ('sin', 'cos', 'tan') and angle == 'DEG': a = '%s*%s' % (a, constant(PI/180))
        value = '%s(%s)' % (_DIRECT[name], a)
        if name in ('asin', 'acos', 'atan') and angle == 'DEG': value = '%s*%s' % (value, constant(180/PI))
        return '_finite(%s)' % value
    return text(node)


def native_function(node, variables, angle='DEG', local='x'):
    """node as a compiled function of local (picosolve.Formula), or None.

    Gives Evaluator.run's results for real values; None covers complex
    values, statistics, factorials, nested integrals and older firmware.
    Call it as f(x): a float, or None where Evaluator.run would raise.
    """
    if not NATIVE_FORMULA: return None
    constants = {}

    def python(x):
        # Points whose whole numbers outgrow float32 come back here.
        try:
            value = Evaluator(variables, angle).run(node, {local: x})
            return None if isinstance(value, complex) else value
        except Exception:
            return None
    try:
        text = _formula_text(node, variables, angle, local, constants)
        from picosolve import Formula
        return Formula(text, ('x',), constants, fallback=python)
    except (_Unsupported, ImportError, ValueError, TypeError):
        return None


class Evaluator:
    def __init__(self, variables, angle='DEG', complex_mode=False, statistics=None, diagnostics=None, progress=None):
        self.variables, self.angle, self.complex_mode = variables, angle, complex_mode
        self.steps = 0
        self.statistics = statistics
        self.diagnostics=[] if diagnostics is None else diagnostics
        self.progress=progress

    def charge(self):
        self.steps+=1
        if self.steps>60000:raise ValueError('Calculation work limit')
        if self.progress and self.steps%64==0:self.progress({'steps':self.steps})

    def reduction(self, name, values):
        """Bounded streaming reduction; Neumaier compensation for sums."""
        total, correction = (0.0 if name == 'sum' else 1.0), 0.0
        for count, value in enumerate(values):
            if count >= REDUCTION_LIMIT: raise ValueError('Sum/product limit: 1024 terms')
            self.charge()
            if not finite(value): raise ValueError('Sum/product term out of range')
            if name == 'sum':
                updated = total+value
                correction += (total-updated)+value if abs(total) >= abs(value) else (value-updated)+total
            else:
                updated = total*value
                if updated == 0 and total != 0 and value != 0:
                    raise ValueError('Product underflow; scale the terms')
            if not finite(updated) or not finite(correction): raise ValueError('Sum/product out of range')
            total = updated
        value = total+correction
        if not finite(value): raise ValueError('Sum/product out of range')
        return value

    def series(self, name, args, local):
        # Four arguments beginning with a name bind an index, rather than
        # evaluating it as a stored scalar. Other arities reduce scalar args.
        if len(args) == 4 and args[0][0] == 'name':
            index = args[0][1]
            if index in RESERVED: raise ValueError('Sum/product index is reserved')
            lower, upper = self.run(args[1], local), self.run(args[2], local)
            for bound in (lower, upper):
                if isinstance(bound, complex) or not finite(bound) or bound != int(bound) or abs(bound) > 16777216:
                    raise ValueError('Sum/product bounds: exact integers within +/-16777216')
            lower, upper = int(lower), int(upper)
            if upper-lower+1 > REDUCTION_LIMIT: raise ValueError('Sum/product limit: 1024 terms')
            scope = dict(local or {})
            def terms():
                for n in range(lower, upper+1):
                    scope[index] = n
                    yield self.run(args[3], scope)
            return self.reduction(name, terms())
        return self.reduction(name, (self.run(arg, local) for arg in args))

    def run(self, node, local=None):
        self.charge()
        kind = node[0]
        if kind == 'value': return node[1]
        if kind == 'name':
            name = node[1]
            if local is not None and name in local: return local[name]
            if name in ('i', 'j'):
                if not self.complex_mode: raise ValueError('Select Complex mode to use i')
                return complex(0, 1)
            if name == 'pi': return PI
            if name == 'e': return E
            if name in ('ans', 'Ans'): return self.variables.get('Ans', 0)
            if name not in self.variables: raise ValueError('Unknown variable: '+name)
            return self.variables[name]
        if kind == 'unary':
            value = self.run(node[2], local)
            return -value if node[1] == '-' else value
        if kind == 'factorial':
            value = self.run(node[1], local)
            if isinstance(value, complex) or value != int(value) or value < 0 or value > 34:
                raise ValueError('Factorial accepts integers 0..34')
            result = 1.0
            for n in range(2, int(value)+1): result *= n
            return result
        if kind == 'binary':
            a, b = self.run(node[2], local), self.run(node[3], local)
            op = node[1]
            if op == '+': value = a+b
            elif op == '-': value = a-b
            elif op == '*': value = a*b
            elif op == '/': value = a/b
            elif op == '%': value = a%b
            else: value = a**b
        else:
            name, args = node[1], node[2]
            dataset_reduction = name in ('sum','prod') and len(args) == 1 and args[0] in (('name','X'),('name','Y'))
            if name in ('sum','prod') and not dataset_reduction:
                return self.series(name, args, local)
            column_call = name in ('min','max') and len(args) == 1 and args[0][0] == 'name' and args[0][1] in ('X','Y')
            if name in STAT_FUNCTIONS or column_call:
                if self.statistics is None: raise ValueError('Choose a Statistics dataset first')
                if name in ('slope','intercept','r2'):
                    if args: raise ValueError(name+' takes no arguments')
                    value = self.statistics.fit()[name]
                elif name in ('cov','pcov','corr'):
                    if len(args) != 2 or args[0] != ('name','X') or args[1] != ('name','Y'):
                        raise ValueError(name+' uses (X,Y)')
                    value = self.statistics.pair_statistics()[name]
                elif name == 'predict':
                    if len(args) != 1: raise ValueError('predict needs one X value')
                    value = self.statistics.predict(self.run(args[0],local))
                elif name == 'prod':
                    value = self.reduction('prod', self.statistics.observations(args[0][1]))
                else:
                    if len(args) != 1 or args[0][0] != 'name' or args[0][1] not in ('X','Y'):
                        raise ValueError(name+' uses (X) or (Y)')
                    value = self.statistics.statistic(name,args[0][1])
                if value is None: raise ValueError('Undefined for this dataset')
                return value
            if name == 'int':
                if not 3<=len(args)<=13:raise ValueError('int(lower,upper,expr[,atol,rtol,split...])')
                if getattr(self,'_integrating',False):raise ValueError('Nested integrals are not available yet')
                lower,upper=self.run(args[0],local),self.run(args[1],local)
                controls=[self.run(arg,local) for arg in args[3:]]
                atol=controls[0] if controls else 1e-7
                rtol=controls[1] if len(controls)>1 else 2e-5
                points=controls[2:]
                if not all(isinstance(v,(int,float)) and finite(v) for v in (lower,upper)):
                    raise ValueError('Integral bounds must be finite real scalars')
                from engtools.numerics.integration import integrate_job
                constants=dict(self.variables);constants.update(local or {})
                native=None if self.complex_mode else native_function(args[2],constants,self.angle)
                def integrand(x):
                    if native is not None:
                        self.charge();value=native(x)
                        if value is None:raise ValueError('Integrand undefined in the interval')
                    else:
                        scope=dict(local or {});scope['x']=x
                        value=self.run(args[2],scope)
                    if not isinstance(value,(int,float)) or not finite(value):
                        raise ValueError('Integrand must return a finite real scalar')
                    return value
                def depends(node):
                    kind=node[0]
                    if kind=='name':return node[1]=='x'
                    if kind=='unary':return depends(node[2])
                    if kind=='factorial':return depends(node[1])
                    if kind=='binary':return depends(node[2]) or depends(node[3])
                    if kind=='call':return any(depends(arg) for arg in node[2])
                    return False
                self._integrating=True
                try:
                    # The job still validates every control, including degenerate
                    # intervals. Constant zero is known, unlike missed samples.
                    if not depends(args[2]):
                        from engtools.numerics.integration import validate
                        validate(lower,upper,atol,rtol,points)
                        value=0.0 if lower==upper else integrand(lower)*(upper-lower)
                        if not finite(value):raise ValueError('Integral out of range')
                        record=dict(value=value,error=0.0,evaluations=0 if lower==upper else 1,intervals=0,estimated=True,constant=True)
                    else:
                        record=None
                        for step in integrate_job(integrand,lower,upper,atol,rtol,points):
                            if 'value' in step:record=step
                            elif self.progress:self.progress({'integral_samples':step['progress']})
                finally:self._integrating=False
                self.diagnostics.append(record)
                # Keep diagnostics bounded even in sums of many integrals.
                if len(self.diagnostics)>8:del self.diagnostics[0]
                return record['value']
            values = [self.run(arg, local) for arg in args]
            if name in ('min', 'max'):
                if not values: raise ValueError('Enter at least one argument')
                return min(values) if name == 'min' else max(values)
            if name in EXTRA_FUNCTIONS or name=='round':
                from .scientific import function
                value=function(name,values,self.angle,self.complex_mode,self.charge)
                if not finite(value):raise ValueError(name+' result out of range')
                if isinstance(value,complex) and not self.complex_mode:raise ValueError('Select Complex mode for this result')
                return value
            expected = 2 if name in ('logb','ncr','npr','root') else 1
            if len(values) != expected: raise ValueError(name+' needs '+str(expected)+' argument(s)')
            a = values[0]
            if name in ('ncr','npr'):
                from .scientific import combinatorial
                value=combinatorial(name,values[0],values[1],self.charge)
            elif name in ('cbrt','root'):
                from .scientific import real_root
                value=real_root(3,a) if name=='cbrt' else real_root(*values)
            elif name == 'logb':
                if self.complex_mode and any(isinstance(v, complex) or v < 0 for v in values):
                    from .scientific import complex_log
                    value = complex_log(complex(values[1]))/complex_log(complex(a))
                else: value = math.log(values[1])/math.log(a)
            elif name == 'abs':
                if isinstance(a,complex):
                    from .scientific import hypot
                    value=hypot(a.real,a.imag)
                else:value=abs(a)
            elif name == 're': value = a.real if isinstance(a, complex) else a
            elif name == 'im': value = a.imag if isinstance(a, complex) else 0
            elif name == 'conj':
                if isinstance(a,complex):
                    from .scientific import _complex
                    value=_complex(a.real,-a.imag)
                else:value=a
            elif name == 'round': value = round(a)
            else:
                if name=='tan':
                    from .scientific import tangent_pole
                    if tangent_pole(a,self.angle):raise ValueError('tan is undefined at this angle')
                if name in ('sin', 'cos', 'tan') and self.angle == 'DEG': a *= PI/180
                actual = {'ln':'log', 'log':'log10'}.get(name, name)
                extend = self.complex_mode and not isinstance(a, complex) and ((name in ('sqrt', 'ln', 'log') and a < 0) or
                                               (name in ('asin','acos') and abs(a) > 1))
                if isinstance(a, complex) or extend:
                    import cmath
                    if name in ('sqrt','ln','log'):
                        from .scientific import complex_sqrt,complex_log
                        value=complex_sqrt(complex(a)) if name=='sqrt' else complex_log(complex(a))
                    elif name in ('asin','acos','atan'):
                        from .scientific import complex_inverse
                        value=complex_inverse(name,complex(a))
                    else:
                        function = getattr(cmath, 'log' if name in ('ln', 'log') else actual, None)
                        if function is None:raise ValueError('This function requires a real argument')
                        value = function(a)
                    if name == 'log': value /= math.log(10)
                else: value = getattr(math, actual)(a)
                if name in ('asin', 'acos', 'atan') and self.angle == 'DEG':
                    if isinstance(value,complex):
                        from .scientific import _complex
                        value=_complex(value.real*(180/PI),value.imag*(180/PI))
                    else:value *= 180/PI
        if not finite(value): raise ValueError('Result out of range')
        if isinstance(value, complex) and not self.complex_mode:
            raise ValueError('Select Complex mode for this result')
        return value


def calculate(text, variables, angle='DEG', complex_mode=False, statistics=None, diagnostics=None, progress=None):
    assignment, tree = Parser(text).parse()
    value = Evaluator(variables, angle, complex_mode, statistics, diagnostics, progress).run(tree)
    if not finite(value): raise ValueError('Result out of range')
    if isinstance(value, complex) and not complex_mode:
        raise ValueError('Select Complex mode for this result')
    if assignment is not None:
        if assignment not in variables and len(variables) >= 25: raise ValueError('Variable limit: 24 names')
        variables[assignment] = value
    variables['Ans'] = value
    return value, assignment


def format_value(value, engineering=False):
    if isinstance(value, complex):
        if value.imag == 0: return format_value(value.real, engineering)
        return '%s%s%si' % (format_value(value.real, engineering), '+' if value.imag >= 0 else '-', format_value(abs(value.imag), engineering))
    if value and abs(value)<math.ldexp(1.0,-126):
        from .precision import format_subnormal
        return format_subnormal(value,engineering)
    if engineering and value:
        exponent = int(math.floor(math.log10(abs(value))/3))*3
        return '%.6ge%+d' % (value/(10**exponent), exponent)
    return '%.7g' % value
