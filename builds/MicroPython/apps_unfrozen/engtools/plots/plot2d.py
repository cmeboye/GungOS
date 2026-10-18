"""Shared 2D viewer for functions, inequalities and sampled engineering data.

Uses bounded, incremental rendering and Graph3D-inspired menu chrome.
Syntax: sin(x), y=x^2, x=3, x^2+y^2=25, y>=sin(x),
        x^2+y^2<=25, or parametric x(t);y(t).
"""
import math
from time import ticks_ms, ticks_diff
from picoware.system.buttons import *
from picoware.system.font import FONT_SMALL
from ..ui import theme

BG, PANEL, TEXT, MUTED = theme.BG, theme.PANEL, theme.TEXT, theme.MUTED
ACCENT, GRID, AXIS, SELECT, ERROR = theme.ACCENT, theme.GRID, theme.AXIS, theme.SELECT, theme.ERROR
COLORS = theme.COLORS
MAX_EXPRESSIONS = 6
SAVE_PATH = 'picoware/settings/graph/session.json'
PRESETS = (
    ('Circle + shaded disk', ('x^2+y^2<=25', 'x^2+y^2=25')),
    ('Waves', ('sin(x)', 'cos(x)')),
    ('Parabola + line', ('y=x^2', 'y=2*x+1')),
    ('Shaded band', ('y>=sin(x)', 'y<=sin(x)+2')),
    ('Hyperbola', ('x*y=1',)),
    ('Implicit waves', ('sin(x)+cos(y)=0',)),
    ('Parametric heart', ('16*sin(t)^3;13*cos(t)-5*cos(2*t)-2*cos(3*t)-cos(4*t)',)),
)
SAFE = {name: getattr(math, name) for name in (
    'sin', 'cos', 'tan', 'asin', 'acos', 'atan', 'atan2', 'sqrt',
    'log', 'log10', 'exp', 'floor', 'ceil', 'sinh', 'cosh', 'tanh',
    'degrees', 'radians')}
SAFE.update({'abs': abs, 'min': min, 'max': max, 'pow': pow,
             'round': round, 'pi': math.pi, 'e': math.e, '__builtins__': {}})


# Use the firmware's C contour tracer and formula compiler when present
# (tests switch them off).
NATIVE_GEOMETRY = True
NATIVE_FORMULA = True


def _geometry():
    try:
        import picosolve
    except ImportError:
        return None
    return picosolve if hasattr(picosolve, 'contour_segments') else None


def native_formula(text):
    """text compiled to C (picosolve.Formula), or None to keep using eval.

    Results are identical to eval's; None also covers older firmware and the
    rare formula the compiler cannot reproduce exactly.
    """
    if not NATIVE_FORMULA:
        return None
    try:
        from picosolve import Formula
        return Formula(text.strip().replace('^', '**'), ('x', 'y', 't'), {'pi': math.pi, 'e': math.e})
    except (ImportError, ValueError):
        return None


def compiled(text, variables):
    return expression_code(text, variables), native_formula(text)


def finite(value):
    return not math.isnan(value) and not math.isinf(value)


def expression_code(text, variables):
    """Restrict eval to arithmetic, known functions and named plot variables."""
    text = text.strip().replace('^', '**')
    if not text or len(text) > 180:
        raise ValueError('Use 1 to 180 characters')
    i = 0
    while i < len(text):
        c = text[i]
        if c.isdigit() or c == '.':
            end = i + 1
            while end < len(text) and (text[end].isdigit() or text[end] == '.'):
                end += 1
            if end < len(text) and text[end] in 'eE':
                end += 1
                if end < len(text) and text[end] in '+-':
                    end += 1
                while end < len(text) and text[end].isdigit():
                    end += 1
            float(text[i:end])
            i = end
        elif c.isalpha() or c == '_':
            end = i + 1
            while end < len(text) and ((text[end].isalpha() or text[end].isdigit()) or text[end] == '_'):
                end += 1
            name = text[i:end]
            if name.startswith('_') or name not in SAFE and name not in variables:
                raise ValueError('Unknown name: ' + name)
            i = end
        elif c in ' +-*/%(),\t':
            i += 1
        else:
            raise ValueError('Unsupported character: ' + c)
    return compile(text, '<graph>', 'eval')


class Expression:
    def __init__(self, text, color, visible=True):
        self.text = text.strip()
        self.color = color
        self.visible = bool(visible)
        self.env = dict(SAFE)
        self.relation = '='
        self.kind = 'implicit'
        self.code2 = None
        self.formula = self.formula2 = None
        self.error = ''
        self.bbox = None
        self.valid = 0
        self.invalid = 0
        try:
            if ';' in self.text:
                parts = self.text.split(';')
                if len(parts) != 2:
                    raise ValueError('Parametric: x(t);y(t)')
                self.kind = 'param'
                self.code, self.formula = compiled(parts[0], ('t',))
                self.code2, self.formula2 = compiled(parts[1], ('t',))
                return
            parts = None
            for relation in ('<=', '>=', '=', '<', '>'):
                if relation in self.text:
                    parts = self.text.split(relation)
                    self.relation = relation
                    break
            if parts is None:
                self.kind = 'y'
                self.code, self.formula = compiled(self.text, ('x',))
                return
            if len(parts) != 2 or not all(part.strip() for part in parts):
                raise ValueError('Use one =, <, >, <= or >=')
            lhs, rhs = (part.strip() for part in parts)
            # Explicit expressions avoid evaluating an entire 2D grid.
            if lhs in ('x', 'y'):
                other = 'x' if lhs == 'y' else 'y'
                try:
                    self.code, self.formula = compiled(rhs, (other,))
                    self.kind = lhs
                    return
                except ValueError:
                    pass
            self.code, self.formula = compiled('(' + lhs + ')-(' + rhs + ')', ('x', 'y'))
        except Exception as exc:
            self.error = str(exc)
            self.code = None

    def value(self, x=0, y=0, t=0):
        if self.formula is not None:
            value = self.formula(x, y, t)
            if value is None: self.invalid += 1
            else: self.valid += 1
            return value
        self.env['x'], self.env['y'], self.env['t'] = x, y, t
        try:
            value = eval(self.code, self.env)
            if isinstance(value, (int, float)) and finite(value):
                self.valid += 1
                return value
        except Exception:
            pass
        self.invalid += 1
        return None

    def second(self, t):
        """y(t) of a parametric pair; value(t=t) has set the environment."""
        if self.formula2 is not None:
            return self.formula2(0, 0, t)
        try:
            second = eval(self.code2, self.env)
            return second if isinstance(second, (int, float)) and finite(second) else None
        except Exception:
            return None

    def row(self, xs, y):
        """Values at world xs (array('f')) and one y, NaN where undefined."""
        from array import array
        out = array('f', bytes(4 * len(xs)))
        kept = self.formula.map(out, xs, y, 0.0)
        self.valid += kept
        self.invalid += len(xs) - kept
        return out

    def inside(self, value):
        if value is None:
            return False
        if self.relation == '<':
            return value < 0
        if self.relation == '<=':
            return value <= 0
        if self.relation == '>':
            return value > 0
        if self.relation == '>=':
            return value >= 0
        return False

    def include(self, x, y):
        if self.bbox is None:
            self.bbox = [x, x, y, y]
        else:
            b = self.bbox
            b[0], b[1] = min(b[0], x), max(b[1], x)
            b[2], b[3] = min(b[2], y), max(b[3], y)


def shade_color(color):
    # Dark color for a stippled fill; overlaps keep both colors visible.
    return (((color >> 11) & 31) // 3 << 11) | (((color >> 5) & 63) // 3 << 5) | ((color & 31) // 3)


def nice_step(span):
    raw = span / 6
    power = 10 ** math.floor(math.log10(raw))
    for multiplier in (1, 2, 5, 10):
        if multiplier * power >= raw:
            return multiplier * power


def valid_bounds(bounds):
    return (len(bounds) == 4 and all(isinstance(v, (int, float)) and finite(v) and abs(v) <= 1e9 for v in bounds)
            and 1e-8 <= bounds[1] - bounds[0] <= 1e9
            and 1e-8 <= bounds[3] - bounds[2] <= 1e9)


class SampleSeries:
    """Retain a caller's point sequence without making a second dataset copy."""
    def __init__(self, spec, color):
        self.text = str(spec.get('name', 'Samples'))
        self.color, self.visible = spec.get('color', color), bool(spec.get('visible', True))
        self.points, self.style = spec['points'], spec.get('style', 'line')
        self.marker = spec.get('marker','square' if self.style=='scatter' else 'none')
        self.kind, self.relation, self.error = 'samples', '=', ''
        self.bbox, self.valid, self.invalid = None, 0, 0

    def include(self, x, y):
        Expression.include(self, x, y)


def validate_spec(spec):
    if not isinstance(spec, dict): raise ValueError('Plot specification must be a dictionary')
    bounds = spec.get('bounds', [-10.,10.,-10.,10.])
    if not valid_bounds(bounds): raise ValueError('Invalid plot bounds')
    series = spec.get('series', ())
    if not 1 <= len(series) <= MAX_EXPRESSIONS: raise ValueError('Use 1 to 6 series')
    sample_count = 0
    for item in series:
        if not isinstance(item, dict): raise ValueError('Series must be dictionaries')
        color = item.get('color', COLORS[0])
        if not isinstance(color, int) or not 0 <= color <= 65535: raise ValueError('Invalid RGB565 color')
        if item.get('type', 'expression') == 'expression':
            e = Expression(item.get('expression', ''), color)
            if e.error: raise ValueError(e.error)
        elif item.get('type') == 'samples':
            points = item.get('points', ())
            sample_count += len(points)
            if not points or sample_count > 4096: raise ValueError('Use at most 4096 sampled points total')
            if item.get('style', 'line') not in ('line', 'scatter'): raise ValueError('Sample style: line or scatter')
            if item.get('marker','none') not in ('none','square','cross','diamond'): raise ValueError('Invalid point marker')
            for point in points:
                if len(point) != 2: raise ValueError('Sample points must be (x,y) pairs')
                for value in point:
                    if value is not None and (not isinstance(value,(int,float)) or not finite(value) or abs(value)>1e12):
                        raise ValueError('Sample coordinates must be finite or None for gaps')
        else: raise ValueError('Unknown series type')
    tr = spec.get('t_range', [0.,2*math.pi])
    if len(tr) != 2 or not all(isinstance(v,(int,float)) and finite(v) for v in tr) or not 1e-8 <= tr[1]-tr[0] <= 1e6:
        raise ValueError('Invalid parameter range')
    axes = spec.get('axes', {})
    if not isinstance(axes, dict): raise ValueError('Axes must be a dictionary')
    for name in ('x','y'):
        axis = axes.get(name, {})
        if not isinstance(axis, dict): raise ValueError('Axis specification must be a dictionary')
        if axis.get('scale','linear') != 'linear': raise ValueError('Logarithmic axes are not implemented yet')
    return spec


class GraphApp:
    def __init__(self, vm, spec=None, persistent=True, embedded=False):
        self.vm = vm
        self.palette=theme.system_palette(vm)
        self.data_only=bool(spec and spec.get('data_only'))
        self.note=str(spec.get('note','')) if spec else ''
        self.persistent, self.embedded = persistent, embedded
        self.brand = 'PicoLAB' if embedded else 'GRAPH'
        if self.data_only: self.brand='Eggcel'
        self.title, self.axes_spec, self.legend = '', {}, False
        self.draw = vm.draw
        self.width, self.height = int(vm.draw.size.x), int(vm.draw.size.y)
        self.left, self.top = 6, 28
        self.right, self.bottom = self.width - 7, self.height - 43
        self.pw, self.ph = self.right - self.left, self.bottom - self.top
        self.bounds = [-10., 10., -10., 10.]
        self.trange = [0., 2 * math.pi]
        self.padding = 10
        self.grid = True
        self.items = [Expression('sin(x)', COLORS[0]), Expression('x^2+y^2<=9', COLORS[1])]
        self.state = 'plot'
        self.row = 0
        self.dirty = True
        self.job = None
        self.refine = None
        self.completed = False
        self.message = ''
        self.edit_target = None
        self.return_state = 'expressions'
        if self.persistent: self.load()
        if spec is not None:
            validate_spec(spec)
            self.title = str(spec.get('title','Plot'))
            self.axes_spec = spec.get('axes',{})
            self.legend = bool(spec.get('legend',False))
            if self.axes_spec:
                self.top, self.bottom = 42, self.height-56
                self.ph = self.bottom-self.top
            self.bounds = list(spec.get('bounds',self.bounds))
            self.trange = list(spec.get('t_range',self.trange))
            self.grid = bool(spec.get('grid',True))
            self.items = []
            for i,item in enumerate(spec['series']):
                if item.get('type','expression') == 'samples':
                    e = SampleSeries(item,COLORS[i])
                else:
                    e = Expression(item['expression'],item.get('color',COLORS[i]),item.get('visible',True))
                    e.text = item['expression']
                    e.name = str(item.get('name',e.text))
                self.items.append(e)
            if spec.get('equal_scale',False): self.fit('equal')

    def xy(self, px, py):
        b = self.bounds
        return (b[0] + (px-self.left)/self.pw*(b[1]-b[0]),
                b[3] - (py-self.top)/self.ph*(b[3]-b[2]))

    def pixel(self, x, y):
        b = self.bounds
        return (self.left + (x-b[0])/(b[1]-b[0])*self.pw,
                self.top + (b[3]-y)/(b[3]-b[2])*self.ph)

    def text(self, x, y, text, color=None):
        if color is None: color=self.palette.TEXT
        self.draw._text(int(x), int(y), str(text), color, FONT_SMALL)

    def chrome(self, subtitle, hint1, hint2):
        theme.chrome(self.draw,subtitle,hint1,hint2,self.brand,self.palette)

    def annotations(self):
        for axis in ('x','y'):
            info = self.axes_spec.get(axis,{})
            label = str(info.get('label',axis))
            unit = str(info.get('unit',''))
            caption = label+(' ['+unit+']' if unit else '')
            caption = caption[:theme.columns(self.draw,self.width-14)]
            if self.axes_spec:
                if axis == 'y': self.text(7,27,caption,self.palette.MUTED)
                else: self.text(max(7,(self.width-self.draw.len(caption,FONT_SMALL))//2),self.bottom+5,caption,self.palette.MUTED)
        if self.legend:
            visible=[e for e in self.items if e.visible]
            cell_width=max(1,(self.right-self.left-10)//max(1,min(3,len(visible))))
            x = self.left+5
            y = self.top+4
            for index,e in enumerate(visible):
                if index and index%3==0: x=self.left+5;y+=15
                name = str(getattr(e,'name',e.text))[:max(1,(cell_width-16)//8)]
                width = self.draw.len(name,FONT_SMALL)
                self.draw._fill_rectangle(x-1,y-1,cell_width,14,self.palette.BG)
                if e.kind=='samples': self.point_marker(x+3,y+5,e.color,e.marker)
                self.text(x+10,y,name,e.color)
                x += cell_width

    def point_marker(self,x,y,color,marker):
        if marker=='cross':
            self.line((x-2,y-2),(x+2,y+2),color)
            self.line((x-2,y+2),(x+2,y-2),color)
        elif marker=='diamond':
            points=((x,y-2),(x+2,y),(x,y+2),(x-2,y))
            for a,b in zip(points,points[1:]+points[:1]): self.line(a,b,color)
        elif marker=='square':
            x0,y0=max(self.left,x-1),max(self.top,y-1)
            self.draw._fill_rectangle(x0,y0,min(3,self.right-x0+1),min(3,self.bottom-y0+1),color)
        else: self.draw._pixel(x,y,color)

    def line(self, a, b, color, dashed=False):
        # Liang-Barsky clipping bounds every native drawing coordinate.
        x, y = a
        dx, dy = b[0]-x, b[1]-y
        lo, hi = 0., 1.
        for p, q in ((-dx,x-self.left),(dx,self.right-x),(-dy,y-self.top),(dy,self.bottom-y)):
            if p == 0:
                if q < 0: return
            else:
                ratio = q/p
                if p < 0: lo = max(lo,ratio)
                else: hi = min(hi,ratio)
        if lo > hi: return
        x0,y0,x1,y1 = x+lo*dx,y+lo*dy,x+hi*dx,y+hi*dy
        if dashed:
            n = max(1, int(math.ceil(max(abs(x1-x0),abs(y1-y0)))))
            for i in range(n+1):
                px,py=int(x0+(x1-x0)*i/n),int(y0+(y1-y0)*i/n)
                if (px+py)%8 < 4: self.draw._pixel(px,py,color)
        else:
            self.draw._line(int(x0),int(y0),int(x1),int(y1),color)

    def axes(self, labels=False):
        b = self.bounds
        for vertical, lower, upper in ((True,b[0],b[1]),(False,b[2],b[3])):
            step = nice_step(upper-lower)
            value = math.ceil(lower/step)*step
            for _ in range(12):
                if value > upper: break
                p = self.pixel(value,0) if vertical else self.pixel(0,value)
                if self.grid:
                    if vertical: self.line((p[0],self.top),(p[0],self.bottom),self.palette.GRID)
                    else: self.line((self.left,p[1]),(self.right,p[1]),self.palette.GRID)
                if labels and abs(value) > step*0.01:
                    if vertical: self.text(max(self.left,min(self.right-34,p[0]+2)),self.bottom-11,'{:g}'.format(value),self.palette.MUTED)
                    else: self.text(self.left+2,max(self.top,min(self.bottom-24,p[1]-10)),'{:g}'.format(value),self.palette.MUTED)
                value += step
        zero = self.pixel(0,0)
        if self.left <= zero[0] <= self.right: self.line((zero[0],self.top),(zero[0],self.bottom),self.palette.AXIS)
        if self.top <= zero[1] <= self.bottom: self.line((self.left,zero[1]),(self.right,zero[1]),self.palette.AXIS)
        self.draw._rectangle(self.left,self.top,self.pw+1,self.ph+1,self.palette.AXIS)

    def redraw(self, moving=False):
        self.job = None
        self.completed = False
        self.draw.fill_screen(self.palette.BG)
        self.axes()
        self.message = ''
        # Shade first, then draw curves, so a fill cannot obscure another curve.
        active = [e for e in self.items if e.visible and not e.error]
        ordered = [e for e in active if e.relation != '='] + [e for e in active if e.relation == '=']
        for e in active:
            e.bbox, e.valid, e.invalid = None, 0, 0
        self.job = {'items': ordered, 'index': 0, 'row': 0, 'previous': None,
                    'step': 10 if moving else 5, 'gridrow': None}
        self.refine = ticks_ms() if moving else None
        self.plot_chrome('preview' if moving else 'drawing')
        self.draw.swap()
        self.dirty = False

    def plot_chrome(self, status):
        b = self.bounds
        subtitle = self.title+' '+status if self.title else '{}  x:{:g}..{:g}'.format(status,b[0],b[1])
        second='W window  F fit  ESC return' if self.embedded else 'W window  F fit  R reset  ESC menu'
        if self.data_only:
            second=self.note or 'F fit all data  ESC sheet'
            self.chrome(subtitle,'ARROWS pan +/- zoom F fit ESC sheet',second)
        else:
            self.chrome(subtitle,'ARROWS pan  +/- zoom  ENTER series' if self.embedded else 'ARROWS pan  +/- zoom  ENTER expressions',second)
        if self.message:
            self.text(8,self.top+5,self.message[:49],self.palette.ERROR)

    def render_batch(self):
        job = self.job
        if not job: return
        started = ticks_ms()
        for _ in range(8):
            if job['index'] >= len(job['items']):
                self.job = None
                self.completed = True
                self.axes(True)
                self.annotations()
                failures = [e for e in self.items if e.visible and e.error]
                undefined = [e for e in job['items'] if not e.valid]
                if failures: self.message = 'Expression error: ENTER to edit'
                elif undefined: self.message = 'Undefined expression: ENTER to edit'
                self.plot_chrome('ready' if self.refine is None else 'preview')
                self.draw.swap()
                return
            e = job['items'][job['index']]
            if e.kind == 'samples': done = self.sample_batch(e,job)
            elif e.kind == 'implicit': done = self.implicit_row(e,job)
            else: done = self.explicit_batch(e,job)
            if done:
                job['index'] += 1
                job['row'],job['previous'],job['gridrow'] = 0,None,None
            if ticks_diff(ticks_ms(),started) >= 12: break
        self.draw.swap()

    def sample_batch(self, e, job):
        pos = job['row']
        for x,y in e.points[pos:pos+20]:
            if x is None or y is None:
                job['previous'] = None
                e.invalid += 1
                continue
            e.valid += 1
            point = self.pixel(x,y)
            if e.style == 'line' and job['previous']:
                self.line(job['previous'],point,e.color)
            if self.left<=point[0]<=self.right and self.top<=point[1]<=self.bottom:
                px,py = int(point[0]),int(point[1])
                self.point_marker(px,py,e.color,e.marker)
                e.include(x,y)
            job['previous'] = point
        job['row'] += 20
        return job['row'] >= len(e.points)

    def explicit_batch(self, e, job):
        param = e.kind == 'param'
        vertical = e.kind == 'x'
        length = self.ph if vertical else self.pw
        n = max(320,self.pw*2) if param else length
        pos = job['row']
        for i in range(pos,min(pos+20,n+1)):
            px = self.left+i if not vertical else self.left
            py = self.top+i if vertical else self.top
            x,y = self.xy(px,py)
            if param:
                t = self.trange[0]+(self.trange[1]-self.trange[0])*i/n
                x,y = e.value(t=t),e.second(t)
            else:
                value = e.value(x=x,y=y)
                if vertical: x = value
                else: y = value
            if x is None or y is None:
                job['previous'] = None
                continue
            # Keep conversion and native drawing bounded for huge finite values.
            if abs(x)>1e12 or abs(y)>1e12:
                job['previous'] = None
                continue
            point = self.pixel(x,y)
            previous = job['previous']
            if e.relation != '=':
                color = shade_color(e.color)
                upper = e.relation in ('>','>=')
                if vertical:
                    a,z = ((point[0],py),(self.right,py)) if upper else ((self.left,py),(point[0],py))
                else:
                    a,z = ((px,self.top),(px,point[1])) if upper else ((px,point[1]),(px,self.bottom))
                if i % 2 == self.items.index(e)%2: self.line(a,z,color)
            if previous:
                jump = max(abs(point[0]-previous[0]),abs(point[1]-previous[1]))
                if jump <= max(self.pw,self.ph)*0.65:
                    if e.relation not in ("<",">") or i%8<4:
                        self.line(previous,point,e.color)
            elif self.left <= point[0] <= self.right and self.top <= point[1] <= self.bottom:
                self.draw._pixel(int(point[0]),int(point[1]),e.color)
            if self.left <= point[0] <= self.right and self.top <= point[1] <= self.bottom:
                e.include(x,y)
            job['previous'] = point
        job['row'] = min(pos+20,n+1)
        return job['row'] > n

    def implicit_row(self, e, job):
        geom = _geometry() if NATIVE_GEOMETRY else None
        if geom is None:
            return self.implicit_row_python(e, job)
        # Formulas are evaluated here; C finds where the curve crosses each cell.
        from array import array
        nan = float('nan')
        step = job['step']
        row = job['row']
        py = self.top+row*step
        if py >= self.bottom: return True
        py2 = min(self.bottom,py+step)
        xs = list(range(self.left,self.right,step))+[self.right]
        cells = len(xs)-1
        if e.formula is not None:
            # Whole rows in one call; world x depends only on the column.
            if job.get('wx') is None:
                job['wx'] = array('f',[self.xy(px,0)[0] for px in xs])
                job['wc'] = array('f',[self.xy((xs[col]+xs[col+1])/2,0)[0] for col in range(cells)])
            values = lambda y: e.row(job['wx'],self.xy(0,y)[1])
            centres = e.row(job['wc'],self.xy(0,(py+py2)/2)[1])
        else:
            def values(y):
                out = array('f')
                for px in xs:
                    v = e.value(*self.xy(px,y))
                    out.append(nan if v is None else v)
                return out
            centres = array('f')
            for col in range(cells):
                v = e.value(*self.xy((xs[col]+xs[col+1])/2,(py+py2)/2))
                centres.append(nan if v is None else v)
        upper = job['gridrow'] if job['gridrow'] is not None else values(py)
        lower = values(py2)
        for col in range(cells):
            x1,x2 = xs[col],xs[col+1]
            if e.relation != '=' and e.inside(centres[col]):
                color = shade_color(e.color)
                # Sparse, stable stipple preserves overlapping inequality colors.
                phase = self.items.index(e)%3
                for sy in range(py,py2):
                    for sx in range(x1+(phase-sy-x1)%3,x2,3):
                        self.draw._pixel(sx,sy,color)
        xsf = array('f',xs)
        queries = array('f',[0.0]*(8*cells))
        q = geom.contour_queries(upper,lower,centres,xsf,py,py2,queries)
        mids = array('f')
        for i in range(q):
            v = e.value(*self.xy(queries[2*i],queries[2*i+1]))
            mids.append(nan if v is None else v)
        segments = array('f',[0.0]*(8*cells))
        dashed = e.relation in ('<','>')
        for i in range(geom.contour_segments(upper,lower,centres,xsf,py,py2,mids,segments)):
            a,b = (segments[4*i],segments[4*i+1]),(segments[4*i+2],segments[4*i+3])
            self.line(a,b,e.color,dashed)
            e.include(*self.xy(*a)); e.include(*self.xy(*b))
        job['gridrow'] = lower
        job['row'] += 1
        return py2 >= self.bottom

    def implicit_row_python(self, e, job):
        """Python contour tracer, for firmware without the C one."""
        step = job['step']
        row = job['row']
        py = self.top+row*step
        if py >= self.bottom: return True
        py2 = min(self.bottom,py+step)
        xs = list(range(self.left,self.right,step))+[self.right]
        def values(y):
            return [e.value(*self.xy(px,y)) for px in xs]
        upper = job['gridrow'] if job['gridrow'] is not None else values(py)
        lower = values(py2)
        for col in range(len(xs)-1):
            x1,x2 = xs[col],xs[col+1]
            corners = ((x1,py,upper[col]),(x2,py,upper[col+1]),
                       (x2,py2,lower[col+1]),(x1,py2,lower[col]))
            cx,cy = self.xy((x1+x2)/2,(py+py2)/2)
            center = e.value(cx,cy)
            if e.relation != '=' and e.inside(center):
                color = shade_color(e.color)
                # Sparse, stable stipple preserves overlapping inequality colors.
                phase = self.items.index(e)%3
                for sy in range(py,py2):
                    for sx in range(x1+(phase-sy-x1)%3,x2,3):
                        self.draw._pixel(sx,sy,color)
            if center is None or any(p[2] is None for p in corners): continue
            crossings = []
            for a,b in zip(corners,corners[1:]+corners[:1]):
                va,vb = a[2],b[2]
                if va == vb: continue
                if (va <= 0 <= vb) or (vb <= 0 <= va):
                    # Reject sign changes across poles / undefined midpoints.
                    mx,my = self.xy((a[0]+b[0])/2,(a[1]+b[1])/2)
                    mid = e.value(mx,my)
                    if mid is None or abs(mid)>max(abs(va),abs(vb))*2+1e-10: continue
                    ratio = abs(va)/(abs(va)+abs(vb))
                    crossings.append((a[0]+ratio*(b[0]-a[0]),a[1]+ratio*(b[1]-a[1])))
            if len(crossings)==2:
                pairs = ((crossings[0],crossings[1]),)
            elif len(crossings)==4:
                # Resolve saddle ambiguity from the center sign.
                pairs = ((crossings[0],crossings[1]),(crossings[2],crossings[3])) if (center>=0)==(corners[0][2]>=0) else ((crossings[0],crossings[3]),(crossings[1],crossings[2]))
            else: pairs = ()
            for a,b in pairs:
                self.line(a,b,e.color,e.relation in ('<','>'))
                e.include(*self.xy(*a)); e.include(*self.xy(*b))
        job['gridrow'] = lower
        job['row'] += 1
        return py2 >= self.bottom

    def set_state(self, state):
        self.state,self.row,self.dirty = state,0,True
        self.job,self.refine = None,None

    def menu_rows(self):
        if self.state == 'menu':
            if self.data_only:
                return [('Plot',''),('Series','show / hide'),('Window','bounds / grid'),
                        ('Help','controls'),('Return to sheet','preserve unsaved changes')]
            return [('Plot',''),('Expressions',str(len(self.items))),('Window','bounds / t / padding'),
                    ('Fit','Y / visible / equal scale'),('Presets','examples'),('Save session','SD card'),('Help','syntax and controls'),('Quit','')]
        if self.state == 'expressions':
            rows=[(('ON ' if e.visible else 'OFF ')+e.text, e.error or ('sampled '+e.style if e.kind=='samples' else 'parametric' if e.kind=='param' else e.relation)) for e in self.items]
            return rows+([] if self.data_only else [('Add expression',str(len(self.items))+'/6')])+[('Return to plot','')]
        if self.state == 'window':
            if self.data_only:
                return [(label,'{:g}'.format(value)) for label,value in zip(
                    ('X minimum','X maximum','Y minimum','Y maximum','Fit padding %'),self.bounds+[self.padding])]+[('Grid','On' if self.grid else 'Off'),('Return to plot','')]
            labels=('X minimum','X maximum','Y minimum','Y maximum','T minimum','T maximum','Fit padding %')
            values=self.bounds+self.trange+[self.padding]
            return [(lab,'{:g}'.format(val)) for lab,val in zip(labels,values)]+[('Grid','On' if self.grid else 'Off'),('Return to plot','')]
        if self.state == 'fit':
            return [('Fit Y','functions in current X window'),('Fit visible curves','current window search only'),('Equal axis scale','circles stay circular'),('Default window','-10 .. 10'),('Return to plot','')]
        if self.state == 'presets': return [(name,'') for name,_ in PRESETS]
        if self.state == 'help':
            if self.data_only:
                return [('ARROWS / +/-','Pan / zoom'),('F fit all data','Restore bounds including offscreen samples'),
                        ('ENTER series; SPACE show/hide','Series use distinct point markers'),
                        ('W window; G grid','Change plot bounds / toggle grid'),
                        ('ESC from plot returns to Eggcel','Unsaved cells and selection are preserved'),
                        ('Blank/text/error pairs are gaps','Edit source cells and redraw to refresh')]
            return [('sin(x) or y=x^2','^ means power; use 2*x'),('x=3 or x*y=1','equations can use x and y'),('x^2+y^2<=25','< > <= >= shade regions'),('cos(t);sin(t)','parametric; set T in Window'),('ARROWS pan / +/- zoom','ENTER expressions; ESC menu'),('SPACE show/hide','D delete; ENTER edit'),('F fit / W window / R reset','Implicit fit searches visible area'),('Save session','equations + bounds on SD'),('ESC returns to menu','')]
        return []

    def draw_menu(self):
        rows = self.menu_rows()
        colors = [(e.color,self.palette.ERROR if e.error else self.palette.MUTED) for e in self.items] if self.state=='expressions' else []
        colors += [(self.palette.TEXT,self.palette.MUTED)]*(len(rows)-len(colors))
        footer = 'SPACE visibility  D delete  ENTER edit' if self.state=='expressions' else 'UP/DOWN choose  ENTER select'
        if self.data_only and self.state=='expressions': footer='ENTER/SPACE visibility  ESC plot'
        theme.menu(self.draw,rows,self.row,self.state,self.brand,footer,self.message or 'ESC returns   H help',colors,self.palette)
        self.dirty = False

    def begin_edit(self, target, initial, title):
        self.edit_target=target
        if self.state != "input": self.return_state=self.state
        self.state='input'
        kb=self.vm.keyboard
        kb.reset(); kb.title=title; kb.response=initial
        self.vm.input_manager.reset()
        kb.run(force=True)

    def finish_edit(self, text):
        target=self.edit_target
        if target[0]=='expression':
            e=Expression(text,COLORS[target[1]%len(COLORS)])
            if e.error: raise ValueError(e.error)
            if target[1]==len(self.items): self.items.append(e)
            else:
                e.visible=self.items[target[1]].visible
                self.items[target[1]]=e
        else:
            value=float(text)
            if not finite(value): raise ValueError('Enter a finite number')
            i=target[1]
            if i<4:
                b=self.bounds[:]; b[i]=value
                if not valid_bounds(b): raise ValueError('Min must be less than max')
                self.bounds=b
            elif i<6:
                tr=self.trange[:]; tr[i-4]=value
                if not 1e-8<=tr[1]-tr[0]<=1e6 or max(abs(v) for v in tr)>1e9: raise ValueError('Invalid T range')
                self.trange=tr
            else:
                if not 0<=value<=50: raise ValueError('Padding: 0 to 50 percent')
                self.padding=value

    def fit(self, mode):
        b=self.bounds[:]
        if mode=='data':
            box=None
            for e in self.items:
                if not e.visible or e.kind!='samples': continue
                for x,y in e.points:
                    if x is None or y is None: continue
                    if box is None: box=[x,x,y,y]
                    else: box=[min(box[0],x),max(box[1],x),min(box[2],y),max(box[3],y)]
            if box is None: raise ValueError('No visible numeric data to fit')
            b=box
            for i in (0,2):
                pad=max((b[i+1]-b[i])*self.padding/100,abs(b[i])*0.05 if b[i]==b[i+1] else 0,1e-6)
                b[i]-=pad;b[i+1]+=pad
        elif mode=='equal':
            cy=(b[2]+b[3])/2; span=(b[1]-b[0])*self.ph/self.pw
            b[2],b[3]=cy-span/2,cy+span/2
        elif mode=='y':
            samples=[]
            for e in self.items:
                if e.visible and e.kind=='samples':
                    samples.extend(y for x,y in e.points if x is not None and y is not None and b[0]<=x<=b[1])
                if e.visible and not e.error and e.kind=='y':
                    for i in range(161):
                        v=e.value(b[0]+(b[1]-b[0])*i/160)
                        if v is not None and abs(v)<1e9: samples.append(v)
            if not samples: raise ValueError('No valid y=f(x) samples')
            samples.sort()
            # Trim a small tail to prevent poles flattening ordinary curves.
            trim=len(samples)//50
            low,high=samples[trim],samples[len(samples)-trim-1]
            pad=max((high-low)*self.padding/100,0.5 if high==low else 1e-6)
            b[2],b[3]=low-pad,high+pad
        else:
            if not self.completed: raise ValueError('Return to plot; wait for ready')
            boxes=[e.bbox for e in self.items if e.visible and not e.error and e.bbox]
            if not boxes: raise ValueError('No visible curves to fit')
            b=[min(a[0] for a in boxes),max(a[1] for a in boxes),min(a[2] for a in boxes),max(a[3] for a in boxes)]
            for i in (0,2):
                pad=max((b[i+1]-b[i])*self.padding/100,0.5 if b[i]==b[i+1] else 1e-6)
                b[i]-=pad; b[i+1]+=pad
        if not valid_bounds(b): raise ValueError('Fit exceeds supported bounds')
        self.bounds=b

    def save(self):
        if not self.persistent: raise ValueError('Save this plot through its engineering tool')
        import json
        storage=self.vm.storage
        payload=json.dumps({'version':1,'expressions':[[e.text,e.visible] for e in self.items],
                            'bounds':self.bounds,'t':self.trange,'padding':self.padding,'grid':self.grid})
        storage.mkdir('picoware/settings'); storage.mkdir('picoware/settings/graph')
        if not storage.write(SAVE_PATH,payload) or storage.read(SAVE_PATH)!=payload:
            raise ValueError('Could not save session to SD')
        self.message='Session saved to SD'

    def load(self):
        import json
        try:
            storage=self.vm.storage
            if not storage.exists(SAVE_PATH): return
            data=json.loads(storage.read(SAVE_PATH))
            b=data['bounds']; tr=data.get('t',[0.,2*math.pi]); padding=data.get('padding',10)
            if not valid_bounds(b) or len(tr)!=2 or not all(isinstance(v,(int,float)) and finite(v) and abs(v)<=1e9 for v in tr) or not 1e-8<=tr[1]-tr[0]<=1e6 or not 0<=padding<=50:
                raise ValueError('Invalid saved window')
            entries=data['expressions']
            if len(entries)>MAX_EXPRESSIONS: raise ValueError('Too many saved expressions')
            items=[Expression(text,COLORS[i],visible) for i,(text,visible) in enumerate(entries)]
            if any(e.error for e in items): raise ValueError('Invalid saved expression')
            self.bounds,self.trange,self.padding,self.grid,self.items=b,tr,padding,bool(data.get('grid',True)),items
        except Exception as exc:
            self.message='Saved session not loaded'
            print('[Graph] Load:',exc)

    def activate(self):
        i=self.row
        if self.state=='menu':
            actions=('plot','expressions','window','help','quit') if self.data_only else ('plot','expressions','window','fit','presets','save','help','quit')
            action=actions[i]
            if action=='save': self.save(); self.dirty=True
            elif action=='quit': self.vm.back()
            else: self.set_state(action)
        elif self.state=='expressions':
            if self.data_only:
                if i<len(self.items): self.items[i].visible=not self.items[i].visible;self.dirty=True
                else: self.set_state('plot')
            elif i<=len(self.items):
                if i==len(self.items) and len(self.items)>=MAX_EXPRESSIONS: raise ValueError('Six expressions maximum')
                if i<len(self.items) and self.items[i].kind=='samples': raise ValueError('Sample data is edited in its source tool')
                text=self.items[i].text if i<len(self.items) else ''
                self.begin_edit(('expression',i),text,'Equation / inequality / x(t);y(t)')
            else: self.set_state('plot')
        elif self.state=='window':
            if self.data_only:
                if i<5:
                    target=i if i<4 else 6
                    self.begin_edit(('number',target),str((self.bounds+[self.padding])[i]),self.menu_rows()[i][0])
                elif i==5: self.grid=not self.grid;self.dirty=True
                else: self.set_state('plot')
            elif i<7:
                val=(self.bounds+self.trange+[self.padding])[i]
                self.begin_edit(('number',i),str(val),self.menu_rows()[i][0])
            elif i==7: self.grid=not self.grid; self.dirty=True
            else: self.set_state('plot')
        elif self.state=='fit':
            if i==3: self.bounds=[-10.,10.,-10.,10.]
            elif i<3: self.fit(('y','visible','equal')[i])
            self.set_state('plot')
        elif self.state=='presets':
            self.items=[Expression(text,COLORS[j]) for j,text in enumerate(PRESETS[i][1])]
            self.bounds=[-10.,10.,-10.,10.]
            if i==6: self.bounds=[-18.,18.,-18.,18.]
            self.set_state('plot')

    def run(self):
        inp=self.vm.input_manager
        button=self.vm.button
        if self.data_only and button==inp._key_esc: button=BUTTON_ESCAPE
        if self.state=='input':
            kb=self.vm.keyboard
            if button==BUTTON_ESCAPE:
                inp.reset(); kb.reset(); self.set_state(self.return_state)
            elif not kb.run():
                kb.reset(); self.set_state(self.return_state)
            elif kb.is_finished:
                result=kb.response.strip(); kb.reset(); inp.reset()
                try:
                    self.finish_edit(result)
                    self.message=''
                except Exception as exc:
                    # Keep the text for correction rather than discard invalid input.
                    self.begin_edit(self.edit_target,result,str(exc)[:46])
                    return
                self.set_state(self.return_state)
            return
        if button!=BUTTON_NONE:
            inp.reset()
            try:
                if self.state=='plot':
                    if button in (BUTTON_LEFT,BUTTON_RIGHT,BUTTON_UP,BUTTON_DOWN):
                        b=self.bounds[:]; dx=(b[1]-b[0])*0.12; dy=(b[3]-b[2])*0.12
                        if button==BUTTON_LEFT: b[0]-=dx; b[1]-=dx
                        elif button==BUTTON_RIGHT: b[0]+=dx; b[1]+=dx
                        elif button==BUTTON_UP: b[2]+=dy; b[3]+=dy
                        else: b[2]-=dy; b[3]-=dy
                        if valid_bounds(b): self.bounds=b; self.redraw(True)
                    elif button in (BUTTON_PLUS,BUTTON_EQUAL,BUTTON_MINUS):
                        b=self.bounds; scale=1.25 if button==BUTTON_MINUS else .8
                        cx,cy=(b[0]+b[1])/2,(b[2]+b[3])/2
                        dx,dy=(b[1]-b[0])*scale/2,(b[3]-b[2])*scale/2
                        b=[cx-dx,cx+dx,cy-dy,cy+dy]
                        if valid_bounds(b): self.bounds=b; self.redraw(True)
                    elif button==BUTTON_CENTER: self.set_state('expressions')
                    elif button==BUTTON_ESCAPE:
                        if self.embedded: self.vm.back(); return
                        self.set_state('menu')
                    elif button==BUTTON_W: self.set_state('window')
                    elif button==BUTTON_F:
                        if self.data_only: self.fit('data');self.dirty=True
                        else: self.set_state('fit')
                    elif button==BUTTON_R:
                        if self.data_only: self.fit('data')
                        else: self.bounds=[-10.,10.,-10.,10.]
                        self.dirty=True
                    elif button in (BUTTON_H,BUTTON_QUESTION): self.set_state('help')
                    elif button==BUTTON_G: self.grid=not self.grid; self.dirty=True
                elif button==BUTTON_ESCAPE:
                    if self.state=='menu' and not self.data_only:self.vm.back();return
                    self.set_state('plot' if self.data_only or self.state in ('expressions','window','fit','menu') else 'menu')
                elif button in (BUTTON_UP,BUTTON_DOWN):
                    self.row=(self.row+(-1 if button==BUTTON_UP else 1))%len(self.menu_rows()); self.dirty=True
                elif button==BUTTON_CENTER: self.activate()
                elif self.state=='expressions' and self.row<len(self.items):
                    if button==BUTTON_SPACE: self.items[self.row].visible=not self.items[self.row].visible; self.dirty=True
                    elif button in (BUTTON_D,BUTTON_DELETE,BUTTON_BACKSPACE) and not self.data_only: self.items.pop(self.row); self.row=min(self.row,len(self.items)); self.dirty=True
            except Exception as exc:
                self.message=str(exc); self.dirty=True
        if self.state=='plot':
            if self.dirty: self.redraw()
            if self.refine is not None and ticks_diff(ticks_ms(),self.refine)>250: self.redraw()
            self.render_batch()
        elif self.dirty: self.draw_menu()


_app=None


def start(view_manager):
    global _app
    _app=GraphApp(view_manager)
    view_manager.input_manager.reset()
    return True


def run(view_manager):
    if _app: _app.run()


def stop(view_manager):
    global _app
    if _app:
        try: _app.save()
        except Exception as exc: print('[Graph] Save:',exc)
    _app=None
    from gc import collect
    collect()


class _PlotView:
    def __init__(self,spec):
        self.spec,self.app = spec,None

    def start(self,vm):
        self.app = GraphApp(vm,self.spec,persistent=False,embedded=True)
        vm.input_manager.reset()
        return True

    def run(self,vm):
        if self.app is not None: self.app.run()

    def stop(self,vm):
        if self.app is not None:
            self.app.job = None
            self.app.items = []
        self.app,self.spec = None,None
        if vm.keyboard is not None: vm.keyboard.reset()
        from gc import collect
        collect()


def show(view_manager,plot_spec):
    """Open a tool-owned plot. Back returns to the caller; no Graph session writes."""
    validate_spec(plot_spec)
    from .view import open_view
    return open_view(view_manager,'eng_plot2d',_PlotView(plot_spec))
