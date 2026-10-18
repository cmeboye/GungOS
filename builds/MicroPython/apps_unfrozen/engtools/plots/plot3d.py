"""Shared 3D viewer for explicit and implicit engineering surfaces."""

from micropython import const
from math import sin, cos, sqrt, exp, log, log10, tan, pi, e, floor, ceil
from math import asin, acos, atan, atan2, sinh, cosh, tanh, isnan, isinf
import math
from time import ticks_ms, ticks_diff
from gc import collect
from ..ui import theme

from picoware.system.font import FONT_SMALL, FONT_MEDIUM
from picoware.system.buttons import (
    BUTTON_ESCAPE,
    BUTTON_LEFT,
    BUTTON_RIGHT,
    BUTTON_UP,
    BUTTON_DOWN,
    BUTTON_CENTER,
    BUTTON_START,
    BUTTON_PLUS,
    BUTTON_MINUS,
    BUTTON_EQUAL,
    BUTTON_A,
    BUTTON_H,
    BUTTON_R,
    BUTTON_W,
    BUTTON_S,
    BUTTON_G,
    BUTTON_Z,
    BUTTON_SPACE,
    BUTTON_QUESTION,
    BUTTON_P,
    BUTTON_F,
    BUTTON_C,
    BUTTON_BACKSPACE,
)

ST_MENU = const(0)
ST_PRESETS = const(1)
ST_INPUT = const(2)
ST_PLOT = const(3)
ST_HELP = const(4)
ST_SETTINGS = const(5)
ST_ERROR = const(6)
ST_SAVED = const(7)
ST_INPUT2 = const(8)
ST_SLICE = const(9)
ST_RESOLUTION = const(10)
ST_RES_WARNING = const(11)
ST_SAMPLING = const(12)

C_BG = theme.BG
C_PLOT = theme.BG
C_PANEL = theme.PANEL
C_FRAME = theme.AXIS
C_ACCENT = theme.ACCENT
C_AMBER = theme.AMBER
C_TITLE = theme.TEXT
C_MUTED = theme.MUTED
C_DIM = const(0x4208)
C_OK = const(0x07E8)
C_ERR = theme.ERROR
C_AXIS_X = const(0xF800)
C_AXIS_Y = const(0x07E0)
C_AXIS_Z = const(0x051F)
C_WIRE = const(0x1CE7)
C_SEL = theme.SELECT

HEAD_H = const(23)
FOOT_H = const(36)

RANGES = (2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0)
GRIDS = (8, 12, 16, 20, 24, 32, 48, 64)
DIR_APP = "picoware/settings/graph3d"
FILE_SAVED = "picoware/settings/graph3d/saved.txt"
C_WIRE2 = const(0xA11E)
C_LINE2 = const(0xFC9F)

PRESETS = (
    ("Wave", "0.6*sin(x)*cos(y)"),
    ("Paraboloid", "0.12*(x*x+y*y)"),
    ("Saddle", "0.12*(x*x-y*y)"),
    ("Ripple", "sin(sqrt(x*x+y*y))"),
    ("Sombrero", "sin(sqrt(x*x+y*y)+0.001)/(sqrt(x*x+y*y)+0.4)"),
    ("Hyperbolic", "0.18*x*y"),
    ("Gaussian", "1.6*exp(-(x*x+y*y)/3)"),
    ("Twin peaks", "1.4*(exp(-((x-2)**2+y*y)/2)+exp(-((x+2)**2+y*y)/2))"),
    ("Bowl", "-0.1*(x*x+y*y)"),
    ("Checker", "0.5*sin(2*x)*sin(2*y)"),
    ("Helix bowl", "0.15*(x*x+y*y)+0.4*sin(3*atan2(y,x))"),
    ("Volcano", "1.2*exp(-(x*x+y*y)/4)-0.6*exp(-(x*x+y*y)/0.6)"),
    ("Sphere", "x^2+y^2+z^2=1"),
    ("Ellipsoid", "x^2/4+y^2+z^2=1"),
    ("Torus", "(sqrt(x^2+y^2)-1.2)^2+z^2=0.25"),
    ("Cone", "z^2=x^2+y^2"),
)

_SAFE = {
    "abs": abs,
    "min": min,
    "max": max,
    "pow": pow,
    "round": round,
    "int": int,
    "float": float,
    "sin": sin,
    "cos": cos,
    "tan": tan,
    "asin": asin,
    "acos": acos,
    "atan": atan,
    "atan2": atan2,
    "log": log,
    "log10": log10,
    "exp": exp,
    "sqrt": sqrt,
    "pi": pi,
    "e": e,
    "floor": floor,
    "ceil": ceil,
    "sinh": sinh,
    "cosh": cosh,
    "tanh": tanh,
    "math": math,
}

_state = ST_MENU
_menu = None
_preset_menu = None
_help_box = None
_dirty = True
_error_msg = ""
_expr = "0.6*sin(x)*cos(y)"
_expr2 = ""
_range = 4.0
_grid_n = 12
_style = 1
_auto = False
_pitch = 0.55
_yaw = 0.70
_zoom = 1.0
_pan_x = 0.0
_pan_y = 0.0
_navigation = "pan"
_preview_at = None
_last_spin_ms = 0
_zmin = 0.0
_zmax = 1.0
_zscale = 1.0
_zs = None
_zs2 = None
_need_eval = True
_saved_menu = None
_saved = []
_slice_axis = 0
_slice_idx = 0
_toast = ""
_storage = None
_sw = 320
_sh = 320
_cx = 160
_cy = 150
_focal = 220.0
_cam = 9.0
_px0 = 0
_py0 = 0
_px1 = 320
_py1 = 320
_set_row = 0
_hint_flash = 0
_mesh = None
_mesh_colors = None
_mesh_limit = 6000
_has_implicit = False
_sampling = None
_sampling_progress = ("sampling",0,1)
_sampling_draw_ms = 0
_pending_resolution = 12
_resolution_return = ST_SETTINGS
_fit_pending = False
_embedded = False
_brand = "GRAPH 3D"
_plot_title = ""


def _palette():
    return theme.colors(C_BG,C_TITLE,C_ACCENT)


def _rgb565(r, g, b):
    if r < 0:
        r = 0
    elif r > 255:
        r = 255
    if g < 0:
        g = 0
    elif g > 255:
        g = 255
    if b < 0:
        b = 0
    elif b > 255:
        b = 255
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


def _heat(t):
    if t < 0.0:
        t = 0.0
    elif t > 1.0:
        t = 1.0
    stops = (
        (0.00, 18, 28, 130),
        (0.22, 0, 170, 210),
        (0.42, 16, 200, 70),
        (0.62, 220, 210, 16),
        (0.82, 236, 110, 8),
        (1.00, 220, 28, 36),
    )
    for i in range(len(stops) - 1):
        t0, r0, g0, b0 = stops[i]
        t1, r1, g1, b1 = stops[i + 1]
        if t <= t1:
            u = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
            return (
                int(r0 + (r1 - r0) * u),
                int(g0 + (g1 - g0) * u),
                int(b0 + (b1 - b0) * u),
            )
    return (220, 28, 36)


def _shade_color(t, shade, cool=False):
    if cool:
        r, g, b = _cool(t)
    else:
        r, g, b = _heat(t)
    r = int(r * shade)
    g = int(g * shade)
    b = int(b * shade)
    return _rgb565(r, g, b)


def _cool(t):
    if t < 0.0:
        t = 0.0
    elif t > 1.0:
        t = 1.0
    stops = (
        (0.00, 20, 16, 80),
        (0.30, 80, 20, 180),
        (0.55, 200, 40, 160),
        (0.80, 240, 140, 200),
        (1.00, 255, 220, 240),
    )
    for i in range(len(stops) - 1):
        t0, r0, g0, b0 = stops[i]
        t1, r1, g1, b1 = stops[i + 1]
        if t <= t1:
            u = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
            return (
                int(r0 + (r1 - r0) * u),
                int(g0 + (g1 - g0) * u),
                int(b0 + (b1 - b0) * u),
            )
    return (255, 220, 240)


def _clean_expr(s):
    s = (s or "").strip()
    s = s.replace("^", "**")
    s = s.replace("×", "*")
    s = s.replace("÷", "/")
    return s.strip()


def _short_expr(n=22):
    s = _clean_expr(_expr)
    if len(s) <= n:
        return s
    return s[: n - 2] + ".."


def _cycle(seq, cur, step):
    idx = 0
    best = 1e9
    for i, v in enumerate(seq):
        d = abs(v - cur)
        if d < best:
            best = d
            idx = i
    return seq[(idx + step) % len(seq)]


def _compile_arithmetic(text):
    text = text.replace('math.', '').replace('^', '**').strip()
    if not text or len(text) > 240:
        raise ValueError('Use 1 to 240 characters')
    i = 0
    while i < len(text):
        c = text[i]
        if c.isdigit() or c == '.':
            end = i+1
            while end < len(text) and (text[end].isdigit() or text[end] == '.'):
                end += 1
            if end < len(text) and text[end] in 'eE':
                end += 1
                if end < len(text) and text[end] in '+-': end += 1
                while end < len(text) and text[end].isdigit(): end += 1
            float(text[i:end])
            i = end
        elif c.isalpha() or c == '_':
            end = i+1
            while end < len(text) and (text[end].isalpha() or text[end].isdigit() or text[end] == '_'):
                end += 1
            name = text[i:end]
            if name.startswith('_') or name not in _SAFE and name not in ('x','y','z','r'):
                raise ValueError('Unknown name: '+name)
            i = end
        elif c in ' +-*/%(),\t': i += 1
        else: raise ValueError('Unsupported character: '+c)
    return compile(text,'<surface>','eval')


def _surface_expression(text):
    """Return explicit z=f(x,y), or a general F(x,y,z)=0 expression."""
    text = _clean_expr(text)
    if any(c in text for c in '<>!'):
        raise ValueError('Use = for a 3D boundary surface')
    if '=' in text:
        sides = text.split('=')
        if len(sides) != 2 or not all(s.strip() for s in sides):
            raise ValueError('Use one equality: left = right')
        left,right = (s.strip() for s in sides)
        if left.lower() == 'z' and not _uses_z(right):
            return False,_compile_arithmetic(right)
        if right.lower() == 'z' and not _uses_z(left):
            return False,_compile_arithmetic(left)
        return True,_compile_arithmetic('('+left+')-('+right+')')
    return _uses_z(text),_compile_arithmetic(text)


def _uses_z(text):
    # Distinguish variable z from names such as "degrees".
    import re
    return re.search(r'(^|[^A-Za-z0-9_])z([^A-Za-z0-9_]|$)',text) is not None


def _finite(value):
    return isinstance(value,(int,float)) and not isnan(value) and not isinf(value) and abs(value)<=1e12


def _field(code, env, x, y, z=0):
    env['x'],env['y'],env['z'] = x,y,z
    env['r'] = sqrt(x*x+y*y+z*z)
    try:
        value = eval(code, {'__builtins__':{}}, env)
        return float(value) if _finite(value) else None
    except Exception:
        return None


def _resolution_warning(n):
    if not isinstance(n,int) or not 4<=n<=64:
        raise ValueError('Resolution must be an integer: 4..64')
    kinds = [_surface_expression(e)[0] for e in (_expr,_expr2) if _clean_expr(e)]
    implicit = any(kinds)
    samples = sum(n**3 if kind else n*n for kind in kinds)
    warning = n>16 if implicit else n>24
    return warning,implicit,samples


def _apply_resolution(n):
    global _grid_n,_need_eval
    _resolution_warning(n)
    _grid_n=n
    _need_eval=True


# Six tetrahedra share the same cube diagonal, avoiding ambiguous cube cases.
_TETRA = ((0,1,2,6),(0,2,3,6),(0,3,7,6),(0,7,4,6),(0,4,5,6),(0,5,1,6))


def _tetra_triangles(points,values):
    inside=[i for i,v in enumerate(values) if v<0]
    outside=[i for i,v in enumerate(values) if v>=0]
    if not inside or not outside: return ()
    def edge(i,j):
        a,b=points[i],points[j]
        va,vb=values[i],values[j]
        t=va/(va-vb)
        return (a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1]),a[2]+t*(b[2]-a[2]))
    if len(inside)==1:
        a=inside[0]
        return ((edge(a,outside[0]),edge(a,outside[1]),edge(a,outside[2])),)
    if len(outside)==1:
        a=outside[0]
        return ((edge(a,inside[0]),edge(a,inside[2]),edge(a,inside[1])),)
    a,b=inside; c,d=outside
    ac,ad,bc,bd=edge(a,c),edge(a,d),edge(b,c),edge(b,d)
    return ((ac,ad,bc),(ad,bd,bc))


def _mesh_triangle(triangle,cool):
    # Compact floats leave memory for the interpreter and projected draw order.
    if len(_mesh_colors)>=_mesh_limit:
        raise ValueError('Mesh too detailed; lower resolution/range')
    a,b,c=triangle
    cross=((b[1]-a[1])*(c[2]-a[2])-(b[2]-a[2])*(c[1]-a[1]),
           (b[2]-a[2])*(c[0]-a[0])-(b[0]-a[0])*(c[2]-a[2]),
           (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]))
    if sum(v*v for v in cross)<1e-20: return
    for vertex in triangle:
        _mesh.extend(vertex)
    _mesh_colors.append(1 if cool else 0)


def _geometry():
    """The firmware's C mesh builder (picosolve), or None on older firmware."""
    try:
        import picosolve
    except ImportError:
        return None
    return picosolve if hasattr(picosolve, 'iso_slab') else None


def _sample_job(native=True):
    """Yield bounded work units; stream two volume planes instead of N cubed RAM."""
    global _zs,_zs2,_zmin,_zmax,_zscale,_has_implicit,_mesh,_mesh_colors,_mesh_limit
    from array import array
    from gc import mem_free
    geom=_geometry() if native else None
    _zs,_zs2=None,None
    _mesh=array('f'); _mesh_colors=bytearray()
    collect()
    _mesh_limit=min(6000,max(128,(mem_free()-80000)//64))
    expressions=[_expr]+([_expr2] if _clean_expr(_expr2) else [])
    specs=[_surface_expression(text) for text in expressions]
    _has_implicit=any(kind for kind,_ in specs)
    _zmin,_zmax=1e30,-1e30
    n,r=_grid_n,_range
    step=2*r/(n-1)
    coords=[-r+i*step for i in range(n)]
    if geom:
        # Formulas are evaluated here; the C code builds the triangles.
        xs=array('f',coords)
        strip=array('f',[0.0]*(18*(n-1)))
        tris,centres,limits=array('f',[0.0]*(9*256)),array('f',[0.0]*(3*256)),array('f',[0.0]*256)
    for surface,(implicit,code) in enumerate(specs):
        env=dict(_SAFE)
        if not implicit:
            rows=[]
            for y in coords:
                row=array('f')
                for x in coords:
                    z=_field(code,env,x,y)
                    row.append(z if z is not None else float('nan'))
                    if z is not None:
                        _zmin,_zmax=min(_zmin,z),max(_zmax,z)
                rows.append(row)
                yield ('sampling function',len(rows),n)
            if surface==0: _zs=rows
            else: _zs2=rows
            if geom:
                for j in range(n-1):
                    count=geom.grid_strip(rows[j],rows[j+1],xs,coords[j],coords[j+1],strip)
                    if len(_mesh_colors)+count>_mesh_limit:
                        raise ValueError('Mesh too detailed; lower resolution/range')
                    _mesh.extend(strip[:9*count])
                    _mesh_colors.extend(bytes((surface,))*count)
                    yield ('building mesh',j+1,n-1)
                continue
            for j in range(n-1):
                for i in range(n-1):
                    a=(coords[i],coords[j],rows[j][i]); b=(coords[i+1],coords[j],rows[j][i+1])
                    c=(coords[i],coords[j+1],rows[j+1][i]); d=(coords[i+1],coords[j+1],rows[j+1][i+1])
                    for triangle in ((a,b,c),(b,d,c)):
                        if all(_finite(v[2]) for v in triangle): _mesh_triangle(triangle,surface)
                yield ('building mesh',j+1,n-1)
        else:
            previous=None
            for k,z in enumerate(coords):
                current=array('f')
                for y in coords:
                    for x in coords:
                        value=_field(code,env,x,y,z)
                        current.append(value if value is not None else float('nan'))
                    yield ('sampling volume',k*n+len(current)//n,n*n)
                if previous is not None and geom:
                    cube,cubes=0,(n-1)*(n-1)
                    while cube<cubes:
                        count,cube=geom.iso_slab(previous,current,xs,coords[k-1],z,tris,centres,limits,cube)
                        for t in range(count):
                            # Avoid joining sign changes across undefined poles.
                            middle=_field(code,env,centres[3*t],centres[3*t+1],centres[3*t+2])
                            if middle is None or abs(middle)>limits[t]: continue
                            if len(_mesh_colors)>=_mesh_limit:
                                raise ValueError('Mesh too detailed; lower resolution/range')
                            o=9*t
                            _mesh.extend(tris[o:o+9])
                            _mesh_colors.append(surface)
                            for zz in (tris[o+2],tris[o+5],tris[o+8]):
                                if zz<_zmin:_zmin=zz
                                if zz>_zmax:_zmax=zz
                        yield ('extracting surface',k*(n-1)+cube//(n-1),(n-1)**2)
                elif previous is not None:
                    for j in range(n-1):
                        for i in range(n-1):
                            indices=(j*n+i,j*n+i+1,(j+1)*n+i+1,(j+1)*n+i)
                            values=tuple(previous[index] for index in indices)+tuple(current[index] for index in indices)
                            if not all(_finite(v) for v in values): continue
                            if all(v>=0 for v in values) or all(v<0 for v in values): continue
                            x0,x1,y0,y1,z0,z1=coords[i],coords[i+1],coords[j],coords[j+1],coords[k-1],z
                            points=((x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0),
                                    (x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1))
                            for tetra in _TETRA:
                                vertices=tuple(points[index] for index in tetra)
                                field=tuple(values[index] for index in tetra)
                                for triangle in _tetra_triangles(vertices,field):
                                    # Avoid joining sign changes across undefined poles.
                                    center=tuple(sum(v[axis] for v in triangle)/3 for axis in (0,1,2))
                                    middle=_field(code,env,*center)
                                    if middle is None or abs(middle)>max(abs(v) for v in field)*2+1e-8: continue
                                    _mesh_triangle(triangle,surface)
                                    for vertex in triangle:
                                        _zmin,_zmax=min(_zmin,vertex[2]),max(_zmax,vertex[2])
                        yield ('extracting surface',k*(n-1)+j,(n-1)**2)
                previous=current
    if not _mesh_colors:
        raise ValueError('No surface found; adjust range/resolution')
    if _zmax-_zmin<1e-9: _zmax=_zmin+1
    _zscale=1.0 if _has_implicit else (_range*.72)/(_zmax-_zmin)
    yield ('complete',1,1)


def _eval_grid():
    """Synchronous adapter for regression tools; UI uses the incremental job."""
    global _need_eval,_error_msg
    try:
        for _ in _sample_job(): pass
        _need_eval=False; _error_msg=''
        return True
    except Exception as exc:
        _error_msg=str(exc)[:80]
        return False


def _world_point(vertex):
    x,y,z=vertex
    center=0 if _has_implicit else (_zmin+_zmax)/2
    return _xform(x,(z-center)*_zscale,y)


def _mesh_vertex(index):
    return (_mesh[index],_mesh[index+1],_mesh[index+2])


_ramp=None


def _mesh_ramp():
    """The heat and cool colour scales as 256-step RGB tables for the C renderer."""
    global _ramp
    if _ramp is None:
        _ramp=bytearray(1536)
        for i in range(256):
            t=i/255
            for k,rgb in enumerate((_heat(t),_cool(t))):
                offset=k*768+i*3
                for c in range(3):_ramp[offset+c]=max(0,min(255,rgb[c]))
    return _ramp


def _draw_mesh(draw,preview=False,native=True):
    from array import array
    draw.fill_screen(C_BG)
    style=0 if preview else _style
    count=len(_mesh_colors)
    stride=max(1,count//1200) if preview else 1
    mesh3d=getattr(draw,'_mesh3d',None) if native else None
    if mesh3d:
        # One C call projects, sorts, clips, shades and outlines every triangle.
        center=0 if _has_implicit else (_zmin+_zmax)/2
        mesh3d(_mesh,_mesh_colors,(_yaw,_pitch,_cam,_focal*_zoom,_cx+_pan_x,_cy+_pan_y,center,_zscale,
                                   _zmin,_zmax,_px0,_py0,_px1,_py1,style,C_WIRE,C_WIRE2,stride),_mesh_ramp())
    else:
        _draw_mesh_python(draw,style,count,stride)
    _draw_gizmo(draw)
    draw._rectangle(_px0,_py0,_px1-_px0,_py1-_py0,C_FRAME)
    status='preview' if preview else 'ready'
    sub=(_plot_title+' '+status) if _plot_title else '{} {:.2f}x {} {}'.format(status,_zoom,_navigation,'implicit' if _has_implicit else '')
    _paint_chrome(draw,_toast or sub,'ARROWS {}  +/- zoom  SPACE mode'.format(_navigation),'F fit  W settings  ESC return' if _embedded else 'F fit  W settings  ENTER edit  ESC menu')
    draw.swap()


def _draw_mesh_python(draw,style,count,stride):
    """Python renderer, for firmware without the C one."""
    from array import array
    depths=array('f')
    for i in range(count):
        offset=i*9
        center=tuple((_mesh[offset+a]+_mesh[offset+3+a]+_mesh[offset+6+a])/3 for a in (0,1,2))
        p=_world_point(center)
        depths.append(p[2] if p else -1)
    order=list(range(count))
    order.sort(key=lambda i:depths[i],reverse=True)
    for index in order[::stride]:
        offset=index*9
        a,b,c=(_world_point(_mesh_vertex(offset+i)) for i in (0,3,6))
        if not all(_pt_ok(p) for p in (a,b,c)): continue
        if not _tri_in_plot(a,b,c): continue
        z=(_mesh[offset+2]+_mesh[offset+5]+_mesh[offset+8])/3
        height=(z-_zmin)/max(1e-9,_zmax-_zmin)
        cool=bool(_mesh_colors[index])
        if style:
            _fill_clipped_triangle(draw,a,b,c,_shade_color(height,_face_shade(a,b,c),cool))
        wire=(_shade_color(height,1,cool) if not style else (C_WIRE2 if cool else C_WIRE))
        _clip_line(draw,a,b,wire); _clip_line(draw,b,c,wire); _clip_line(draw,c,a,wire)


def _draw_sampling(draw,progress):
    draw.fill_screen(C_BG)
    name,done,total=progress
    percent=min(100,int(done*100/max(1,total)))
    draw._text(18,100,name,C_ACCENT,FONT_MEDIUM)
    draw._text(18,132,'{}%  N={}  {} triangles'.format(percent,_grid_n,len(_mesh_colors or ())),C_MUTED,FONT_SMALL)
    draw._fill_rectangle(18,160,_sw-36,10,C_PANEL)
    draw._fill_rectangle(18,160,int((_sw-36)*percent/100),10,C_ACCENT)
    _paint_chrome(draw,'sampling','Building surface in small batches','ESC cancel  ENTER after errors to edit')
    draw.swap()


def _begin_resolution(view_manager):
    global _state,_resolution_return
    _resolution_return=_state
    _state=ST_RESOLUTION
    kb=view_manager.keyboard
    kb.reset(); kb.title='Resolution N (4..64)'; kb.response=str(_grid_n)
    view_manager.input_manager.reset(); kb.run(force=True)


def _draw_resolution_warning(draw):
    _,implicit,samples=_resolution_warning(_pending_resolution)
    draw.fill_screen(C_BG)
    lines=('High resolution may be slow',
           'N={}  {} samples'.format(_pending_resolution,samples),
           'Implicit: N x N x N' if implicit else 'Function: N x N',
           'More detail uses more RAM.',
           'Dense meshes may exceed memory.',
           'Sampling can be cancelled with ESC.')
    for i,line in enumerate(lines): draw._text(12,64+i*25,line,C_AMBER if i==0 else C_TITLE,FONT_SMALL)
    _paint_chrome(draw,'performance warning','ENTER apply resolution','ESC keep current resolution')
    draw.swap()


def _ensure_dir(storage):
    if not storage:
        return False
    try:
        if not storage.exists(DIR_APP):
            storage.mkdir(DIR_APP)
        return True
    except Exception:
        return False


def _load_saved(storage):
    global _saved
    _saved = []
    if not storage:
        return
    try:
        if storage.exists(FILE_SAVED):
            raw = storage.read(FILE_SAVED, "r")
            if raw:
                for line in str(raw).split("\n"):
                    line = line.strip()
                    if line:
                        _saved.append(line)
    except Exception:
        _saved = []


def _write_saved(storage):
    if not storage or not _ensure_dir(storage):
        return False
    try:
        return storage.write(FILE_SAVED, "\n".join(_saved) + "\n", "w")
    except Exception:
        return False


def _pack_entry():
    a = _clean_expr(_expr)
    b = _clean_expr(_expr2)
    if b:
        return a + " | " + b
    return a


def _unpack_entry(line):
    if " | " in line:
        a, b = line.split(" | ", 1)
        return a.strip(), b.strip()
    return line.strip(), ""


def _next_shot_path(storage):
    if not _ensure_dir(storage):
        return None
    n = 1
    while n < 100:
        path = "picoware/settings/graph3d/shot{:02d}.bmp".format(n)
        try:
            if not storage.exists(path):
                return path
        except Exception:
            return path
        n += 1
    return "picoware/settings/graph3d/shot99.bmp"


def _xform(x, y_up, z_depth):
    cy = cos(_yaw)
    sy = sin(_yaw)
    x1 = x * cy - z_depth * sy
    z1 = x * sy + z_depth * cy
    cp = cos(_pitch)
    sp = sin(_pitch)
    y2 = y_up * cp - z1 * sp
    z2 = y_up * sp + z1 * cp
    zc = _cam - z2
    if zc < 0.45:
        return None
    s = (_focal * _zoom) / zc
    sx = int(_cx + _pan_x + x1 * s)
    sy = int(_cy + _pan_y - y2 * s)
    return (sx, sy, zc, x1, y2, z2)


def _pt_ok(p):
    # Keep offscreen vertices for proper clipped zoom/pan rendering.
    return p is not None and abs(p[0]) < 1000000 and abs(p[1]) < 1000000


def _outcode(x, y):
    c = 0
    if x < _px0:
        c |= 1
    elif x > _px1:
        c |= 2
    if y < _py0:
        c |= 4
    elif y > _py1:
        c |= 8
    return c


def _clip_line(draw, a, b, color):
    if a is None or b is None:
        return
    x0 = a[0]
    y0 = a[1]
    x1 = b[0]
    y1 = b[1]
    c0 = _outcode(x0, y0)
    c1 = _outcode(x1, y1)
    xmin = _px0
    xmax = _px1
    ymin = _py0
    ymax = _py1
    while True:
        if not (c0 | c1):
            draw._line(int(x0), int(y0), int(x1), int(y1), color)
            return
        if c0 & c1:
            return
        c = c0 if c0 else c1
        if c & 8:
            x = x0 + (x1 - x0) * (ymax - y0) / (y1 - y0) if y1 != y0 else x0
            y = ymax
        elif c & 4:
            x = x0 + (x1 - x0) * (ymin - y0) / (y1 - y0) if y1 != y0 else x0
            y = ymin
        elif c & 2:
            y = y0 + (y1 - y0) * (xmax - x0) / (x1 - x0) if x1 != x0 else y0
            x = xmax
        else:
            y = y0 + (y1 - y0) * (xmin - x0) / (x1 - x0) if x1 != x0 else y0
            x = xmin
        if c == c0:
            x0, y0 = x, y
            c0 = _outcode(x0, y0)
        else:
            x1, y1 = x, y
            c1 = _outcode(x1, y1)


def _tri_in_plot(p0, p1, p2):
    return not (_outcode(p0[0],p0[1]) & _outcode(p1[0],p1[1]) & _outcode(p2[0],p2[1]))


def _fill_clipped_triangle(draw, a, b, c, color):
    points = [(a[0],a[1]),(b[0],b[1]),(c[0],c[1])]
    for axis, edge, greater in ((0,_px0,True),(0,_px1,False),(1,_py0,True),(1,_py1,False)):
        if not points:
            return
        clipped = []
        last = points[-1]
        last_inside = last[axis] >= edge if greater else last[axis] <= edge
        for current in points:
            inside = current[axis] >= edge if greater else current[axis] <= edge
            if inside != last_inside:
                ratio = (edge-last[axis])/(current[axis]-last[axis])
                q = (last[0]+ratio*(current[0]-last[0]), last[1]+ratio*(current[1]-last[1]))
                clipped.append(q)
            if inside:
                clipped.append(current)
            last, last_inside = current, inside
        points = clipped
    if len(points) < 3:
        return
    for i in range(1,len(points)-1):
        vertices = (points[0],points[i],points[i+1])
        coords = []
        for x,y in vertices:
            coords.extend((max(_px0,min(_px1,int(x))),max(_py0,min(_py1,int(y)))))
        draw._fill_triangle(coords[0],coords[1],coords[2],coords[3],coords[4],coords[5],color)


def _area2(p0, p1, p2):
    return (p1[0] - p0[0]) * (p2[1] - p0[1]) - (p2[0] - p0[0]) * (p1[1] - p0[1])


def _face_shade(p0, p1, p2):
    ux = p1[3] - p0[3]
    uy = p1[4] - p0[4]
    uz = p1[5] - p0[5]
    vx = p2[3] - p0[3]
    vy = p2[4] - p0[4]
    vz = p2[5] - p0[5]
    nx = uy * vz - uz * vy
    ny = uz * vx - ux * vz
    nz = ux * vy - uy * vx
    ln = sqrt(nx * nx + ny * ny + nz * nz)
    if ln < 1e-8:
        return 0.55
    nd = (nx * 0.35 + ny * 0.82 + nz * 0.25) / ln
    if nd < 0.0:
        nd = -nd
    return 0.38 + 0.62 * nd


def _layout(draw):
    global _sw, _sh, _cx, _cy, _focal, _cam, _px0, _py0, _px1, _py1
    _sw = int(draw.size.x)
    _sh = int(draw.size.y)
    _px0 = 6
    _py0 = 28
    _px1 = _sw - 7
    _py1 = _sh - 43
    _cx = (_px0 + _px1) // 2
    _cy = (_py0 + _py1) // 2
    short = min(_px1 - _px0, _py1 - _py0)
    _focal = short * 0.78
    _cam = max(7.6 + _range * 0.22, _range * 2.4)


def _paint_chrome(draw, subtitle, footer1, footer2):
    theme.chrome(draw,subtitle,footer1,footer2,_brand,_palette())


class _PanelMenu:
    """Small Graph-style menu; no dependency on Graph.py on the SD."""
    def __init__(self, draw, title, *unused):
        self.display = draw
        self.title = title
        self.items = []
        self.selected_index = 0

    def add_item(self, text):
        self.items.append(text)

    def set_selected(self, index):
        self.selected_index = min(max(0, index), max(0, len(self.items)-1))
        self.draw()

    def scroll_up(self):
        if self.items:
            self.set_selected((self.selected_index-1)%len(self.items))

    def scroll_down(self):
        if self.items:
            self.set_selected((self.selected_index+1)%len(self.items))

    def draw(self):
        rows = [tuple(item.split(" | ",1)) if " | " in item else (item,"") for item in self.items]
        theme.menu(self.display,rows,self.selected_index,self.title,_brand,'UP/DOWN choose  ENTER select','ESC returns   H help',palette=_palette())


class _HelpPanel:
    def __init__(self, draw, *unused):
        self.display = draw
        self.lines = []
        self.row = 0

    def set_text(self, text):
        self.lines = text.split("\n")
        self.draw()

    def scroll_up(self):
        self.row = max(0, self.row-1)
        self.draw()

    def scroll_down(self):
        self.row = min(max(0, len(self.lines)-16), self.row+1)
        self.draw()

    def draw(self):
        draw = self.display
        draw.fill_screen(C_BG)
        for i, line in enumerate(self.lines[self.row:self.row+16]):
            draw._text(11, 32+i*15, line[:48], C_MUTED if not line.isupper() else C_ACCENT, FONT_SMALL)
        _paint_chrome(draw, "help", "UP/DOWN scroll", "ESC menu")
        draw.swap()


def _draw_gizmo(draw):
    """Small XYZ triad in the plot's top-left — not through the mesh."""
    ox = _px0 + 20
    oy = _py0 + 20
    L = 16
    cy = cos(_yaw)
    sy = sin(_yaw)
    cp = cos(_pitch)
    sp = sin(_pitch)

    def tip(x, yup, zd):
        x1 = x * cy - zd * sy
        z1 = x * sy + zd * cy
        y2 = yup * cp - z1 * sp
        return ox + int(x1 * L), oy - int(y2 * L)

    axes = (
        (tip(1, 0, 0), C_AXIS_X, "X"),
        (tip(0, 0, 1), C_AXIS_Y, "Y"),
        (tip(0, 1, 0), C_AXIS_Z, "Z"),
    )
    for (tx, ty), col, ch in axes:
        draw._line(ox, oy, tx, ty, col)
        lx = tx + 2
        ly = ty - 4
        if _px0 <= lx <= _px1 - 6 and _py0 <= ly <= _py1 - 6:
            draw._text(lx, ly, ch, col, FONT_SMALL)


def _draw_plot(draw, preview=False):
    _draw_mesh(draw, preview)


def _draw_error(draw):
    draw.fill_screen(C_BG)
    draw._fill_rectangle(draw.scale_x(14), draw.scale_y(70), _sw - draw.scale_x(28), draw.scale_y(132), C_PANEL)
    draw._rectangle(draw.scale_x(14), draw.scale_y(70), _sw - draw.scale_x(28), draw.scale_y(132), C_ERR)
    draw._text(draw.scale_x(26), draw.scale_y(84), "Could not plot", C_ERR, FONT_MEDIUM)
    msg = _error_msg or "Unknown error"
    if len(msg) > 34:
        draw._text(draw.scale_x(26), draw.scale_y(114), msg[:34], C_TITLE, FONT_SMALL)
        draw._text(draw.scale_x(26), draw.scale_y(128), msg[34:68], C_TITLE, FONT_SMALL)
    else:
        draw._text(draw.scale_x(26), draw.scale_y(114), msg, C_TITLE, FONT_SMALL)
    draw._text(draw.scale_x(26), draw.scale_y(156), "ENTER  fix equation", C_ACCENT, FONT_SMALL)
    draw._text(draw.scale_x(26), draw.scale_y(172), "ESC   main menu", C_MUTED, FONT_SMALL)
    _paint_chrome(draw, "error", "ENTER edit   G resolution", "ESC menu")
    draw.swap()


def _draw_settings(draw):
    draw.fill_screen(C_BG)
    rows = (
        ("XYZ range" if _has_implicit else "XY range", "{:.1f} to {:.1f}".format(-_range, _range)),
        ("Resolution", "N={}   ENTER type (4..64)".format(_grid_n)),
        ("Style", "Solid + wire" if _style == 1 else "Wireframe"),
        ("Auto spin", "On" if _auto else "Off"),
        ("Arrow controls", "Pan" if _navigation == "pan" else "Orbit"),
        ("Fit surface", "center + zoom; keep orientation"),
        ("Reset camera", "pan / pitch / yaw / zoom"),
        ("Return to plot", ""),
    )
    theme.menu(draw,rows,_set_row,'settings',_brand,'UP/DOWN choose  LEFT/RIGHT change','ENTER activate   ESC plot',palette=_palette())


def _reset_camera():
    global _pitch, _yaw, _zoom, _pan_x, _pan_y, _auto, _preview_at
    _pitch, _yaw, _zoom = 0.55, 0.70, 1.0
    _pan_x, _pan_y, _auto, _preview_at = 0.0, 0.0, False, None


def _fit_surface():
    global _zoom, _pan_x, _pan_y
    if not _mesh_colors:
        return False
    old = (_zoom, _pan_x, _pan_y)
    _zoom, _pan_x, _pan_y = 1.0, 0.0, 0.0
    bounds = None
    for i in range(0,len(_mesh),3):
        p = _world_point(_mesh_vertex(i))
        if p is None: continue
        if bounds is None: bounds = [p[0],p[0],p[1],p[1]]
        else:
            bounds[0],bounds[1] = min(bounds[0],p[0]),max(bounds[1],p[0])
            bounds[2],bounds[3] = min(bounds[2],p[1]),max(bounds[3],p[1])
    if bounds is None:
        _zoom, _pan_x, _pan_y = old
        return False
    _zoom = min(8.0, max(0.2, min((_px1-_px0-20)/max(1,bounds[1]-bounds[0]), (_py1-_py0-20)/max(1,bounds[3]-bounds[2]))))
    _pan_x = -((bounds[0]+bounds[1])/2-_cx)*_zoom
    _pan_y = -((bounds[2]+bounds[3])/2-_cy)*_zoom
    return True


def _kill_menu(obj_name):
    global _menu, _preset_menu, _help_box, _saved_menu
    if obj_name == "menu" and _menu:
        del _menu
        _menu = None
    elif obj_name == "preset" and _preset_menu:
        del _preset_menu
        _preset_menu = None
    elif obj_name == "help" and _help_box:
        del _help_box
        _help_box = None
    elif obj_name == "saved" and _saved_menu:
        del _saved_menu
        _saved_menu = None


def _make_saved(view_manager):
    global _saved_menu
    Menu = _PanelMenu

    _kill_menu("saved")
    _load_saved(_storage)
    draw = view_manager.draw
    _saved_menu = Menu(
        draw,
        "saved plots",
        0,
        draw.size.y,
        view_manager.foreground_color,
        view_manager.background_color,
        view_manager.selected_color,
        view_manager.foreground_color,
    )
    _saved_menu.add_item("Save current plot")
    if _saved:
        for line in _saved:
            shown = line if len(line) <= 28 else line[:26] + ".."
            _saved_menu.add_item(shown)
    else:
        _saved_menu.add_item("(empty)")
    _saved_menu.set_selected(0)


def _make_menu(view_manager):
    global _menu
    Menu = _PanelMenu

    _kill_menu("menu")
    draw = view_manager.draw
    _menu = Menu(
        draw,
        "menu",
        0,
        draw.size.y,
        view_manager.foreground_color,
        view_manager.background_color,
        view_manager.selected_color,
        view_manager.foreground_color,
    )
    g2 = _clean_expr(_expr2)
    _menu.add_item("Plot | " + _short_expr(35))
    _menu.add_item("Edit surface | Function or general equation")
    if g2:
        gs = g2 if len(g2) <= 14 else g2[:12] + ".."
        _menu.add_item("Second surface | g=" + gs)
    else:
        _menu.add_item("Second surface | Off")
    _menu.add_item("Presets | Functions and implicit surfaces")
    _menu.add_item("Saved plots | Save or load equations")
    _menu.add_item("Settings | range / mesh / camera")
    _menu.add_item("Help")
    _menu.add_item("Quit")
    _menu.set_selected(0)


def _make_presets(view_manager):
    global _preset_menu
    Menu = _PanelMenu

    _kill_menu("preset")
    draw = view_manager.draw
    _preset_menu = Menu(
        draw,
        "presets",
        0,
        draw.size.y,
        view_manager.foreground_color,
        view_manager.background_color,
        view_manager.selected_color,
        view_manager.foreground_color,
    )
    for name, expr in PRESETS:
        _preset_menu.add_item(name + " | " + expr)
    _preset_menu.set_selected(0)


def _make_help(view_manager):
    global _help_box
    TextBox = _HelpPanel

    _kill_menu("help")
    draw = view_manager.draw
    _help_box = TextBox(
        draw,
        0,
        draw.size.y,
        view_manager.foreground_color,
        view_manager.background_color,
    )
    _help_box.set_text(
        "GRAPH 3D\n"
        "Plot z = f(x, y) as a surface.\n"
        "\n"
        "MAIN MENU\n"
        "  Plot      draw current equation\n"
        "  Type      keyboard editor\n"
        "  Preset    functions / implicit shapes\n"
        "  Settings  range, grid, style\n"
        "\n"
        "ON THE PLOT\n"
        "  Arrows    pan by default\n"
        "  SPACE     switch pan / orbit\n"
        "  F         fit surface to view\n"
        "  +  -      zoom\n"
        "  ENTER     edit equation\n"
        "  ESC      menu\n"
        "  C         2D slice\n"
        "  P         screenshot to SD\n"
        "  A         auto-spin on/off\n"
        "  W         settings\n"
        "  S         wire / solid toggle\n"
        "  G         enter grid resolution N\n"
        "  Z         next XY range\n"
        "  R         reset camera\n"
        "  ? or H    this help\n"
        "\n"
        "EQUATIONS\n"
        "  z=f(x,y), or F(x,y,z)=0\n"
        "  x^2+y^2+z^2=1 draws a sphere.\n"
        "  Range bounds implicit XYZ cube.\n"
        "  ^ is allowed (becomes **).\n"
        "  sin cos tan exp log sqrt\n"
        "  abs min max pow atan2 pi e\n"
        "\n"
        "  0.6*sin(x)*cos(y)\n"
        "  0.12*(x*x-y*y)\n"
        "  sin(sqrt(x*x+y*y))\n"
        "\n"
        "TIPS\n"
        "  Functions: N x N samples.\n"
        "  Implicit: N x N x N samples.\n"
        "  High N requires confirmation.\n"
        "  ESC cancels sampling.\n"
        "  Wire mode is faster.\n"
        "  Solid uses height + lighting.\n"
        "  Two surfaces: f heat, g pink.\n"
        "  Camera movement reuses mesh.\n"
        "  Movement preview is wireframe.\n"
        "  Saved list stores f | g.\n"
        "  Tiny XYZ gizmo is top-left.\n"
        "  Shots: picoware/settings/graph3d/\n"
        "\n"
        "ESC returns to the menu."
    )


def _begin_input(view_manager, second=False):
    kb = view_manager.keyboard
    view_manager.input_manager.reset()
    kb.reset()
    if second:
        kb.title = "g(x,y)  empty clears"
        kb.response = _clean_expr(_expr2)
    else:
        kb.title = "Surface: z=f(x,y) or F(x,y,z)=0"
        kb.response = _clean_expr(_expr)
    kb.run(force=True)


def _draw_slice(draw):
    draw.fill_screen(C_BG)
    draw._fill_rectangle(
       _px0, _py0,
       _px1 - _px0 + 1, _py1 - _py0 + 1,
        C_PLOT,
    )
    if _zs is None:
        _paint_chrome(draw, "slice", "no data", "ESC  3D")
        draw.swap()
        return

    n = _grid_n
    r = _range
    step = (2.0 * r) / (n - 1) if n > 1 else 1.0
    idx = _slice_idx
    idx = max(idx, 0)
    idx = min(idx, n - 1)
    zspan = _zmax - _zmin
    if zspan < 1e-9:
        zspan = 1.0

    left = _px0 + draw.scale_x(18)
    right = _px1 - draw.scale_x(8)
    top = _py0 + draw.scale_y(8)
    bot = _py1 - draw.scale_y(10)
    draw._line(left, top, left, bot, C_FRAME)
    draw._line(left, bot, right, bot, C_FRAME)
    # zero line
    if _zmin < 0.0 < _zmax:
        zy = int(bot - (0.0 - _zmin) / zspan * (bot - top))
        draw._line(left, zy, right, zy, C_DIM)

    def _poly(zs, color):
        last = None
        for i in range(n):
            if _slice_axis == 0:
                z = zs[idx][i]
            else:
                z = zs[i][idx]
            if not _finite(z):
                last = None
                continue
            t = i / float(n - 1) if n > 1 else 0.0
            px = int(left + t * (right - left))
            py = int(bot - (z - _zmin) / zspan * (bot - top))
            if last is not None:
                draw._line(last[0], last[1], px, py, color)
            last = (px, py)

    _poly(_zs, C_ACCENT)
    if _zs2 is not None:
        _poly(_zs2, C_LINE2)

    if _slice_axis == 0:
        val = -r + idx * step
        title = "slice  y={:.2f}".format(val)
    else:
        val = -r + idx * step
        title = "slice  x={:.2f}".format(val)
    f1 = "LEFT/RIGHT  move cut"
    f2 = "C  other axis    ESC  3D"
    _paint_chrome(draw, title, f1, f2)
    draw.swap()


def _take_shot(view_manager):
    global _toast, _dirty
    storage = view_manager.storage
    path = _next_shot_path(storage)
    if not path:
        _toast = "shot failed (SD?)"
        _dirty = True
        return
    try:
        view_manager.draw.screenshot(path)
        _toast = "saved " + path.split("/")[-1]
    except Exception:
        _toast = "screenshot failed"
    _dirty = True


def _goto_plot(view_manager):
    global _state, _dirty, _need_eval, _slice_idx, _toast, _preview_at, _sampling, _sampling_progress
    _layout(view_manager.draw)
    _preview_at = None
    if _need_eval or not _mesh_colors:
        _sampling = _sample_job()
        _sampling_progress = ("sampling",0,1)
        _state = ST_SAMPLING
        _draw_sampling(view_manager.draw,_sampling_progress)
    else:
        _state = ST_PLOT
        _dirty = True
    _slice_idx = _grid_n // 2
    _toast = ""


def _apply_setting(step):
    global _range, _grid_n, _style, _auto, _need_eval, _navigation
    row = _set_row
    if row == 0:
        _range = _cycle(RANGES, _range, step)
        _need_eval = True
    elif row == 1:
        return False  # Resolution is entered and confirmed by the UI.
    elif row == 2:
        _style = 1 - _style
    elif row == 3:
        _auto = not _auto
    elif row == 4:
        _navigation = "orbit" if _navigation == "pan" else "pan"
    elif row == 5:
        if _need_eval:
            return False
        _fit_surface()
    elif row == 6:
        _reset_camera()
    return True


def start(view_manager, plot_spec=None) -> bool:
    global _state, _dirty, _need_eval, _auto, _zs, _zs2
    global _pitch, _yaw, _zoom, _set_row, _hint_flash
    global _menu, _preset_menu, _help_box, _saved_menu
    global _storage, _grid_n, _toast, _navigation, _mesh, _mesh_colors, _sampling
    global _embedded,_brand,_plot_title,_expr,_expr2,_range,_style,_pending_resolution,_resolution_return

    global C_BG,C_PLOT,C_PANEL,C_FRAME,C_ACCENT,C_TITLE,C_MUTED,C_SEL,C_ERR
    palette=theme.system_palette(view_manager)
    C_BG=C_PLOT=palette.BG;C_PANEL=palette.PANEL;C_FRAME=palette.AXIS
    C_ACCENT=palette.ACCENT;C_TITLE=palette.TEXT;C_MUTED=palette.MUTED
    C_SEL=palette.SELECT;C_ERR=palette.ERROR
    _embedded = plot_spec is not None
    _brand = 'PicoLAB' if _embedded else 'GRAPH 3D'
    _plot_title = str(plot_spec.get('title','Surface')) if _embedded else ''
    requested_resolution = None
    if _embedded:
        validate_spec(plot_spec)
        expressions = [item['expression'] for item in plot_spec['surfaces']]
        _expr,_expr2 = expressions[0],expressions[1] if len(expressions)>1 else ''
        _range = float(plot_spec.get('range',2.0))
        _style = 0 if plot_spec.get('style','solid') == 'wire' else 1
        requested_resolution = int(plot_spec.get('resolution',12))
        _grid_n = requested_resolution
    _storage = None if _embedded else view_manager.storage
    if not isinstance(_grid_n,int) or not 4<=_grid_n<=64:
        _grid_n = 12
    _layout(view_manager.draw)
    _state = ST_MENU
    _menu = None
    _preset_menu = None
    _help_box = None
    _saved_menu = None
    _dirty = True
    _need_eval = True
    _auto = False
    _zs = None
    _zs2 = None
    _mesh = None
    _mesh_colors = None
    _sampling = None
    _pitch = 0.55
    _yaw = 0.70
    _zoom = 1.0
    _reset_camera()
    _navigation = "pan"
    _set_row = 0
    _hint_flash = 0
    _toast = ""
    view_manager.input_manager.reset()
    _ensure_dir(_storage)
    _load_saved(_storage)
    if requested_resolution is not None and _resolution_warning(requested_resolution)[0]:
        _pending_resolution = requested_resolution
        _grid_n = 12
        _resolution_return = ST_PLOT
        _state = ST_RES_WARNING
        _draw_resolution_warning(view_manager.draw)
    else:
        _goto_plot(view_manager)
    return True


def run(view_manager) -> None:
    global _state, _dirty, _expr, _expr2, _need_eval, _zs2
    global _pitch, _yaw, _zoom, _auto, _style
    global _range, _grid_n, _set_row, _slice_axis, _slice_idx, _toast
    global _pan_x, _pan_y, _navigation, _preview_at, _last_spin_ms
    global _sampling,_sampling_progress,_sampling_draw_ms,_error_msg,_pending_resolution,_fit_pending

    inp = view_manager.input_manager
    button = view_manager.button
    draw = view_manager.draw

    if _state == ST_SAMPLING:
        if button == BUTTON_ESCAPE:
            inp.reset()
            if _embedded:
                view_manager.back()
                return
            _sampling.close(); _sampling=None
            _release_mesh()
            _need_eval=True; _fit_pending=False; _state=ST_MENU
            _make_menu(view_manager)
            return
        started=ticks_ms()
        try:
            for _ in range(8):
                _sampling_progress=next(_sampling)
                if ticks_diff(ticks_ms(),started)>=12: break
        except StopIteration:
            _sampling=None; _need_eval=False; _error_msg=''
            _state=ST_PLOT; _dirty=True
            if _has_implicit or _fit_pending: _fit_surface()
            _fit_pending=False
        except Exception as exc:
            _sampling=None; _error_msg=("Out of RAM; press G to lower resolution" if isinstance(exc,MemoryError) else str(exc))[:80]
            _release_mesh(); _need_eval=True
            _fit_pending=False; _state=ST_ERROR; _dirty=True
        if _state==ST_SAMPLING and ticks_diff(ticks_ms(),_sampling_draw_ms)>=100:
            _draw_sampling(draw,_sampling_progress); _sampling_draw_ms=ticks_ms()
        return

    elif _state == ST_RESOLUTION:
        kb=view_manager.keyboard
        if button==BUTTON_ESCAPE or not kb.run():
            inp.reset(); kb.reset()
            _state=_resolution_return; _dirty=True
        elif kb.is_finished:
            result=kb.response.strip(); kb.reset(); inp.reset()
            try:
                n=int(result)
                warning,_,_=_resolution_warning(n)
                if warning:
                    _pending_resolution=n; _state=ST_RES_WARNING
                    _draw_resolution_warning(draw)
                else:
                    _apply_resolution(n); _state=_resolution_return; _dirty=True
                    if _state in (ST_PLOT,ST_ERROR): _goto_plot(view_manager)
            except Exception as exc:
                _state=ST_RESOLUTION
                kb.title=str(exc)[:46]; kb.response=result; kb.run(force=True)
        if _state==ST_SETTINGS and _dirty: _draw_settings(draw); _dirty=False
        return

    elif _state == ST_RES_WARNING:
        if button==BUTTON_ESCAPE:
            inp.reset()
            if _embedded and not _mesh_colors:
                view_manager.back()
                return
            _state=_resolution_return; _dirty=True
            if _state==ST_SETTINGS: _draw_settings(draw); _dirty=False
        elif button==BUTTON_CENTER:
            inp.reset(); _apply_resolution(_pending_resolution)
            _state=_resolution_return; _dirty=True
            if _state in (ST_PLOT,ST_ERROR): _goto_plot(view_manager)
            else: _draw_settings(draw); _dirty=False
        return

    if _state == ST_MENU:
        if _menu is None:
            _make_menu(view_manager)
        if button == BUTTON_UP:
            inp.reset()
            _menu.scroll_up()
        elif button == BUTTON_DOWN:
            inp.reset()
            _menu.scroll_down()
        elif button == BUTTON_ESCAPE:
            inp.reset()
            view_manager.back()
        elif button == BUTTON_CENTER:
            inp.reset()
            idx = _menu.selected_index
            if idx == 0:
                _goto_plot(view_manager)
            elif idx == 1:
                _state = ST_INPUT
                _begin_input(view_manager, False)
            elif idx == 2:
                _state = ST_INPUT2
                _begin_input(view_manager, True)
            elif idx == 3:
                _state = ST_PRESETS
                _make_presets(view_manager)
            elif idx == 4:
                _state = ST_SAVED
                _make_saved(view_manager)
            elif idx == 5:
                _state = ST_SETTINGS
                _set_row = 0
                _dirty = True
            elif idx == 6:
                _state = ST_HELP
                _make_help(view_manager)
            elif idx == 7:
                view_manager.back()

    elif _state == ST_PRESETS:
        if _preset_menu is None:
            _make_presets(view_manager)
        if button == BUTTON_UP:
            inp.reset()
            _preset_menu.scroll_up()
        elif button == BUTTON_DOWN:
            inp.reset()
            _preset_menu.scroll_down()
        elif button == BUTTON_ESCAPE:
            inp.reset()
            _kill_menu("preset")
            _state = ST_MENU
            _make_menu(view_manager)
        elif button == BUTTON_CENTER:
            inp.reset()
            idx = _preset_menu.selected_index
            if 0 <= idx < len(PRESETS):
                _expr = PRESETS[idx][1]
                if idx >= 12:
                    _expr2 = ""
                    _range = 2.0
                _need_eval = True
                _kill_menu("preset")
                _goto_plot(view_manager)

    elif _state == ST_SAVED:
        if _saved_menu is None:
            _make_saved(view_manager)
        if button == BUTTON_UP:
            inp.reset()
            _saved_menu.scroll_up()
        elif button == BUTTON_DOWN:
            inp.reset()
            _saved_menu.scroll_down()
        elif button == BUTTON_ESCAPE:
            inp.reset()
            _kill_menu("saved")
            _state = ST_MENU
            _make_menu(view_manager)
        elif button == BUTTON_BACKSPACE:
            inp.reset()
            idx = _saved_menu.selected_index
            if idx >= 1 and idx - 1 < len(_saved):
                _saved.pop(idx - 1)
                _write_saved(_storage)
                _make_saved(view_manager)
        elif button == BUTTON_CENTER:
            inp.reset()
            idx = _saved_menu.selected_index
            if idx == 0:
                entry = _pack_entry()
                if entry and entry not in _saved:
                    _saved.insert(0, entry)
                    _write_saved(_storage)
                _make_saved(view_manager)
            elif idx >= 1 and idx - 1 < len(_saved):
                _expr, _expr2 = _unpack_entry(_saved[idx - 1])
                _need_eval = True
                _kill_menu("saved")
                _goto_plot(view_manager)

    elif _state == ST_SETTINGS:
        if button in (BUTTON_UP, BUTTON_DOWN):
            inp.reset()
            _set_row = (_set_row + (-1 if button == BUTTON_UP else 1)) % 8
            _dirty = True
        elif button in (BUTTON_LEFT, BUTTON_RIGHT, BUTTON_CENTER):
            inp.reset()
            if _set_row == 7:
                _goto_plot(view_manager)
                return
            if _set_row == 1:
                _begin_resolution(view_manager)
                return
            if _set_row == 5 and _need_eval:
                _fit_pending=True
                _goto_plot(view_manager)
                return
            _apply_setting(-1 if button == BUTTON_LEFT else 1)
            _dirty = True
        elif button == BUTTON_ESCAPE:
            inp.reset()
            _goto_plot(view_manager)
            return
        if _dirty:
            _draw_settings(draw)
            _dirty = False

    elif _state == ST_HELP:
        if _help_box is None:
            _make_help(view_manager)
        if button in (BUTTON_ESCAPE,):
            inp.reset()
            _kill_menu("help")
            if _embedded: _goto_plot(view_manager)
            else:
                _state = ST_MENU
                _make_menu(view_manager)
        elif button == BUTTON_UP:
            inp.reset()
            _help_box.scroll_up()
        elif button == BUTTON_DOWN:
            inp.reset()
            _help_box.scroll_down()

    elif _state == ST_INPUT:
        kb = view_manager.keyboard
        if button == BUTTON_ESCAPE:
            inp.reset()
            kb.reset()
            if _embedded: _goto_plot(view_manager)
            else:
                _state = ST_MENU
                _make_menu(view_manager)
        elif not kb.run():
            inp.reset()
            kb.reset()
            if _embedded: _goto_plot(view_manager)
            else:
                _state = ST_MENU
                _make_menu(view_manager)
        elif kb.is_finished:
            result = (kb.response or "").strip()
            kb.reset()
            inp.reset()
            if result:
                _expr = result
                _need_eval = True
                _goto_plot(view_manager)
            else:
                _state = ST_MENU
                _make_menu(view_manager)

    elif _state == ST_INPUT2:
        kb = view_manager.keyboard
        if button == BUTTON_ESCAPE:
            inp.reset()
            kb.reset()
            if _embedded: _goto_plot(view_manager)
            else:
                _state = ST_MENU
                _make_menu(view_manager)
        elif not kb.run():
            inp.reset()
            kb.reset()
            if _embedded: _goto_plot(view_manager)
            else:
                _state = ST_MENU
                _make_menu(view_manager)
        elif kb.is_finished:
            result = (kb.response or "").strip()
            kb.reset()
            inp.reset()
            _expr2 = result
            _need_eval = True
            if result:
                _goto_plot(view_manager)
            else:
                _zs2 = None
                _state = ST_MENU
                _make_menu(view_manager)

    elif _state == ST_ERROR:
        if _dirty:
            _draw_error(draw)
            _dirty = False
        if button == BUTTON_ESCAPE:
            inp.reset()
            if _embedded:
                view_manager.back()
                return
            _state = ST_MENU
            _make_menu(view_manager)
        elif button == BUTTON_G:
            inp.reset()
            _begin_resolution(view_manager)
        elif button == BUTTON_CENTER:
            inp.reset()
            _state = ST_INPUT
            _begin_input(view_manager, False)

    elif _state == ST_SLICE:
        n = _grid_n
        if button == BUTTON_ESCAPE:
            inp.reset()
            _state = ST_PLOT
            _dirty = True
        elif button == BUTTON_C:
            inp.reset()
            _slice_axis = 1 - _slice_axis
            _dirty = True
        elif button == BUTTON_LEFT:
            inp.reset()
            _slice_idx -= 1
            if _slice_idx < 0:
                _slice_idx = 0
            _dirty = True
        elif button == BUTTON_RIGHT:
            inp.reset()
            _slice_idx += 1
            if _slice_idx > n - 1:
                _slice_idx = n - 1
            _dirty = True
        elif button == BUTTON_P:
            inp.reset()
            _take_shot(view_manager)
        if _dirty:
            _layout(draw)
            _draw_slice(draw)
            _dirty = False

    elif _state == ST_PLOT:
        moved = False
        if button == BUTTON_ESCAPE:
            inp.reset()
            _auto = False
            if _embedded:
                view_manager.back()
                return
            _state = ST_MENU
            _make_menu(view_manager)
            return
        if button in (BUTTON_LEFT, BUTTON_RIGHT, BUTTON_UP, BUTTON_DOWN):
            inp.reset()
            _auto = False
            if _navigation == "pan":
                dx = (_px1-_px0)*0.08
                dy = (_py1-_py0)*0.08
                if button == BUTTON_LEFT: _pan_x -= dx
                elif button == BUTTON_RIGHT: _pan_x += dx
                elif button == BUTTON_UP: _pan_y -= dy
                else: _pan_y += dy
                _pan_x = max(-_sw*2, min(_sw*2, _pan_x))
                _pan_y = max(-_sh*2, min(_sh*2, _pan_y))
            else:
                if button == BUTTON_LEFT: _yaw -= 0.16
                elif button == BUTTON_RIGHT: _yaw += 0.16
                elif button == BUTTON_UP: _pitch = min(1.45, _pitch+0.11)
                else: _pitch = max(-1.45, _pitch-0.11)
                _yaw %= 2*pi
            _preview_at = ticks_ms()
            moved = True
        elif button in (BUTTON_PLUS, BUTTON_EQUAL, BUTTON_MINUS):
            inp.reset()
            scale = 0.8 if button == BUTTON_MINUS else 1.25
            new_zoom = max(0.2, min(8.0, _zoom*scale))
            # Keep the world point under the view center fixed during zoom.
            ratio = new_zoom/_zoom
            _pan_x *= ratio
            _pan_y *= ratio
            _zoom = new_zoom
            _preview_at = ticks_ms()
            moved = True
        elif button == BUTTON_SPACE:
            inp.reset()
            _navigation = "orbit" if _navigation == "pan" else "pan"
            moved = True
        elif button == BUTTON_F:
            inp.reset()
            _auto = False
            _fit_surface()
            _preview_at = None
            moved = True
        elif button in (BUTTON_A, BUTTON_START):
            inp.reset()
            _auto = not _auto
            _preview_at = None if not _auto else ticks_ms()
            moved = True
        elif button == BUTTON_W:
            inp.reset()
            _auto = False
            _state = ST_SETTINGS
            _set_row = 0
            _dirty = True
            _preview_at = None
            return
        elif button == BUTTON_S:
            inp.reset()
            _style = 1 - _style
            moved = True
        elif button == BUTTON_R:
            inp.reset()
            _reset_camera()
            moved = True
        elif button in (BUTTON_H, BUTTON_QUESTION):
            inp.reset()
            _auto = False
            _state = ST_HELP
            _make_help(view_manager)
            return
        elif button == BUTTON_CENTER:
            inp.reset()
            _auto = False
            _state = ST_INPUT
            _begin_input(view_manager, False)
            return
        elif button == BUTTON_C:
            inp.reset()
            if _has_implicit:
                _toast = "Slices available for z=f(x,y) only"
                _dirty = True
                return
            _auto = False
            _slice_idx = _grid_n // 2
            _state = ST_SLICE
            _dirty = True
            return
        elif button == BUTTON_P:
            inp.reset()
            _take_shot(view_manager)
            moved = True
        elif button == BUTTON_G:
            inp.reset()
            _auto = False
            _begin_resolution(view_manager)
            return
        elif button == BUTTON_Z:
            inp.reset()
            _range = _cycle(RANGES, _range, 1)
            _need_eval = True
            _goto_plot(view_manager)
            return

        if _auto and ticks_diff(ticks_ms(), _last_spin_ms) >= 50:
            _yaw = (_yaw + 0.040) % (2*pi)
            _last_spin_ms = ticks_ms()
            _preview_at = ticks_ms()
            moved = True
        if _preview_at is not None and not _auto and ticks_diff(ticks_ms(), _preview_at) >= 250:
            _preview_at = None
            _dirty = True
        if moved or _dirty:
            _layout(draw)
            _draw_plot(draw, _preview_at is not None)
            _dirty = False


def stop(view_manager) -> None:
    global _menu, _preset_menu, _help_box, _zs
    global _state, _auto, _dirty

    global _saved_menu, _zs2, _sampling, _fit_pending
    if _menu:
        del _menu
        _menu = None
    if _preset_menu:
        del _preset_menu
        _preset_menu = None
    if _help_box:
        del _help_box
        _help_box = None
    if _saved_menu:
        del _saved_menu
        _saved_menu = None
    if _sampling is not None:
        _sampling.close(); _sampling=None
    _release_mesh()
    _fit_pending=False
    _zs = None
    _zs2 = None
    _auto = False
    _dirty = True
    _state = ST_MENU
    try:
        view_manager.keyboard.reset()
    except Exception:
        pass
    collect()

def _release_mesh():
    global _mesh,_mesh_colors,_zs,_zs2
    _mesh,_mesh_colors,_zs,_zs2=None,None,None,None
    collect()


def validate_spec(spec):
    if not isinstance(spec,dict): raise ValueError('Plot specification must be a dictionary')
    surfaces = spec.get('surfaces',())
    if not 1<=len(surfaces)<=2: raise ValueError('Use one or two surfaces')
    for item in surfaces:
        if not isinstance(item,dict) or item.get('type','expression')!='expression':
            raise ValueError('3D surfaces currently use expressions')
        _surface_expression(item.get('expression',''))
    extent = spec.get('range',2.0)
    if not isinstance(extent,(int,float)) or not _finite(extent) or not .01<=extent<=100:
        raise ValueError('3D range must be 0.01 to 100')
    resolution = spec.get('resolution',12)
    if not isinstance(resolution,int) or not 4<=resolution<=64:
        raise ValueError('Resolution must be an integer: 4..64')
    if spec.get('style','solid') not in ('solid','wire'):
        raise ValueError('Style must be solid or wire')
    return spec


class _PlotView:
    def __init__(self,spec):
        self.spec,self.previous = spec,None

    def start(self,vm):
        self.previous = (_expr,_expr2,_range,_grid_n,_style)
        return start(vm,self.spec)

    def run(self,vm):
        run(vm)

    def stop(self,vm):
        global _expr,_expr2,_range,_grid_n,_style,_embedded,_brand,_plot_title
        stop(vm)
        if self.previous is not None:
            _expr,_expr2,_range,_grid_n,_style = self.previous
        self.spec,self.previous = None,None
        _embedded,_brand,_plot_title = False,'GRAPH 3D',''


def show(view_manager,plot_spec):
    """Open a tool-owned 3D plot and restore standalone equation settings on exit."""
    validate_spec(plot_spec)
    from .view import open_view
    return open_view(view_manager,'eng_plot3d',_PlotView(plot_spec))
