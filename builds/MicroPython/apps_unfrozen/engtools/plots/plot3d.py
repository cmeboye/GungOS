"""Shared 3D viewer for explicit and implicit engineering surfaces."""

from micropython import const
from math import sin, cos, sqrt, exp, log, log10, tan, pi, e, floor, ceil
from math import asin, acos, atan, atan2, sinh, cosh, tanh, isnan, isinf
import math
import re
# Imported once here: on the device each import of an "extensible" built-in
# such as array searches every sys.path directory on the SD card first.
from array import array
from time import ticks_ms, ticks_diff
from gc import collect
from ..ui import theme, lab
from ..ui.forms import LineEdit, erase_key, parse_number

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
    BUTTON_R,
    BUTTON_W,
    BUTTON_S,
    BUTTON_G,
    BUTTON_Z,
    BUTTON_SPACE,
    BUTTON_P,
    BUTTON_F,
    BUTTON_C,
    BUTTON_BACKSPACE,
    BUTTON_F9,
    BUTTON_L,
    BUTTON_NONE,
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
FILE_SESSION = "picoware/settings/graph3d/session.json"
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

HELP_LINES = (
    'Menu:', 'Plot, edit f or a second surface g,', 'presets, saved plots, settings, help',
    'On the plot:', 'ARROWS pan (SPACE: orbit)   + - zoom', 'F fit   R reset camera   A auto spin',
    'S style: wire, solid, heat map', 'W settings: ranges, aspect, N, style',
    'G resolution N   Z next symmetric range', 'C 2D slice   P screenshot to SD',
    'ENTER edit the equation   ESC menu',
    'Heat map (style):', 'Height shown as colour, bar on the right', 'ARROWS move the probe: x, y, z on top',
    'L contours on/off   + - zoom the range', 'Needs z = f(x, y); implicit surfaces stay 3D',
    'Settings (W):', 'UP/DOWN choose   ENTER edit or change', 'Type a number to replace a value',
    'UP/DOWN while typing applies it', 'LEFT/RIGHT change a choice',
    'X, Y ranges; Z Auto fits f, Fixed clips it', 'and bounds the volume of F(x,y,z)=0',
    'Aspect Equal keeps proportions; Box fills', 'Typing a Z value sets Z range Fixed',
    'Equations:', 'z=f(x,y), or F(x,y,z)=0', 'x^2+y^2+z^2=1 draws a sphere', '^ is power; sin cos tan exp log sqrt',
    'abs min max pow atan2 pi e', '0.6*sin(x)*cos(y)   sin(sqrt(x*x+y*y))',
    'Tips:', 'Functions use N x N samples,', 'implicit surfaces N x N x N', 'High N asks first; ESC cancels sampling',
    'Wire is faster; movement previews wire', 'Two surfaces: f heat colours, g pink',
    'Shots go to picoware/settings/graph3d/', 'F9 opens this help; ESC closes',
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
_viewer_active = False
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
# Ranges: None means the symmetric +/-_range (the Z key's presets).
_bounds = None        # [x0, x1, y0, y1]
_zrange = None        # fixed [z0, z1]; None fits z (functions) or follows x/y (implicit)
_aspect = "equal"     # "equal": true proportions; "box": every axis fills the cube
_H = 4.0              # half-size of the displayed box
_sx = _sy = _sz = 1.0
# Heatmap (style 2): f(x, y) as colour on fine cells, with optional contours.
_need_heat = True
_heat_values = None
_heat_info = None     # (cols, rows, left, top, cell_w, cell_h, lo, hi)
_heat_lines = None
_contours = True
_probe = [0, 0]
HEAT_CELL = 3
HEAT_IMPLICIT = "Heatmap needs z = f(x, y); this is an implicit surface F(x,y,z)=0"
STYLES = ("Wireframe", "Solid + wire", "Heatmap")
# Inline editing (no on-screen keyboard) and the shared help box.
_edit = None
_edit_note = ""
_edit_error = False
_toast_error = False
_help_first = 0
_help_return = ST_MENU


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
    from .arithmetic import compile_expression
    code = compile_expression(text, _SAFE, ('x', 'y', 'z', 'r'), 240, '<surface>')
    return _formula(text, code) or code


# Use the firmware's formula compiler when present (tests switch it off).
NATIVE_FORMULA = True
_CODE = type(compile('0','<t>','eval'))


def _formula(text, code=None):
    """text compiled to C (picosolve.Formula), or None to keep using eval.

    Its results are identical to eval's through _field, including r and the
    1e12 limit; points whose whole numbers outgrow float32 are handed back to
    eval. None also covers older firmware and the rare formula the compiler
    cannot reproduce exactly.
    """
    if not NATIVE_FORMULA:
        return None
    if code is None:
        code = compile(text,'<surface>','eval')
    env = dict(_SAFE)
    try:
        from picosolve import Formula
        return Formula(text, ('x','y','z'), {'pi':pi,'e':e}, {'r':'sqrt(x*x+y*y+z*z)'}, 1e12,
                       lambda x,y,z: _field(code,env,x,y,z))
    except (ImportError, ValueError, TypeError):
        return None


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
    return re.search(r'(^|[^A-Za-z0-9_])z([^A-Za-z0-9_]|$)',text) is not None


def _finite(value):
    return isinstance(value,(int,float)) and not isnan(value) and not isinf(value) and abs(value)<=1e12


def _field(code, env, x, y, z=0):
    if type(code) is not _CODE:
        return code(x, y, z)
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
    n=_grid_n
    x0,x1,y0,y1=_xy_bounds()
    cx,cy,hx,hy=(x0+x1)/2,(y0+y1)/2,(x1-x0)/2,(y1-y0)/2
    cz,hz=0.0,0.0
    if _has_implicit:
        z0,z1=_implicit_z()
        cz,hz=(z0+z1)/2,(z1-z0)/2
    _set_scales(hx,hy,hz)
    # Real coordinates for the formula, display coordinates for the mesh.
    coords=[x0+(x1-x0)*i/(n-1) for i in range(n)]
    ycoords=[y0+(y1-y0)*i/(n-1) for i in range(n)]
    zcoords=[cz-hz+2*hz*i/(n-1) for i in range(n)]
    xs=array('f',coords)
    xd=array('f',[(x-cx)*_sx for x in coords])
    yd=[(y-cy)*_sy for y in ycoords]
    clip=_zrange if not _has_implicit else None
    plane=array('f',bytes(4*n))
    unit=[-1+2*i/(n-1) for i in range(n)]
    grid=array('f',unit)
    ax,ay,az=hx*_sx,hy*_sy,hz*_sz
    if geom:
        # Formulas are evaluated here; the C code builds the triangles.
        strip=array('f',[0.0]*(18*(n-1)))
        tris,centres,limits=array('f',[0.0]*(9*256)),array('f',[0.0]*(3*256)),array('f',[0.0]*256)
        middles=array('f',[0.0]*256)
    for surface,(implicit,code) in enumerate(specs):
        env=dict(_SAFE)
        native=type(code) is not _CODE
        if not implicit:
            rows=[]
            for y in ycoords:
                if native:
                    # One call per row; NaN marks undefined points.
                    row=array('f',bytes(4*n))
                    code.map(row,xs,y,0.0)
                else:
                    row=array('f')
                    for x in coords:
                        z=_field(code,env,x,y)
                        row.append(z if z is not None else float('nan'))
                for i in range(n):
                    z=row[i]
                    if z==z:
                        if clip and not clip[0]<=z<=clip[1]:
                            row[i]=float('nan')  # a fixed z range clips the surface
                            continue
                        if z<_zmin:_zmin=z
                        if z>_zmax:_zmax=z
                rows.append(row)
                yield ('sampling function',len(rows),n)
            if surface==0: _zs=rows
            else: _zs2=rows
            if geom:
                for j in range(n-1):
                    count=geom.grid_strip(rows[j],rows[j+1],xd,yd[j],yd[j+1],strip)
                    if len(_mesh_colors)+count>_mesh_limit:
                        raise ValueError('Mesh too detailed; lower resolution/range')
                    _mesh.extend(strip[:9*count])
                    _mesh_colors.extend(bytes((surface,))*count)
                    yield ('building mesh',j+1,n-1)
                continue
            for j in range(n-1):
                for i in range(n-1):
                    a=(xd[i],yd[j],rows[j][i]); b=(xd[i+1],yd[j],rows[j][i+1])
                    c=(xd[i],yd[j+1],rows[j+1][i]); d=(xd[i+1],yd[j+1],rows[j+1][i+1])
                    for triangle in ((a,b,c),(b,d,c)):
                        if all(_finite(v[2]) for v in triangle): _mesh_triangle(triangle,surface)
                yield ('building mesh',j+1,n-1)
        else:
            previous=None
            for k,z in enumerate(zcoords):
                current=array('f')
                for y in ycoords:
                    if native:
                        code.map(plane,xs,y,z)
                        current.extend(plane)
                    else:
                        for x in coords:
                            value=_field(code,env,x,y,z)
                            current.append(value if value is not None else float('nan'))
                    yield ('sampling volume',k*n+len(current)//n,n*n)
                if previous is not None and geom:
                    cube,cubes=0,(n-1)*(n-1)
                    while cube<cubes:
                        # Marching tetrahedra on the unit grid; then real and display units.
                        count,cube=geom.iso_slab(previous,current,grid,unit[k-1],unit[k],tris,centres,limits,cube)
                        for t in range(count):
                            o=3*t
                            centres[o]=cx+centres[o]*hx; centres[o+1]=cy+centres[o+1]*hy; centres[o+2]=cz+centres[o+2]*hz
                        if native: code.points(middles,centres,count)
                        for t in range(count):
                            # Avoid joining sign changes across undefined poles.
                            if native:
                                middle=middles[t]
                                if middle!=middle: continue
                            else:
                                middle=_field(code,env,centres[3*t],centres[3*t+1],centres[3*t+2])
                                if middle is None: continue
                            if abs(middle)>limits[t]: continue
                            if len(_mesh_colors)>=_mesh_limit:
                                raise ValueError('Mesh too detailed; lower resolution/range')
                            o=9*t
                            for v in (o,o+3,o+6):
                                tris[v]*=ax; tris[v+1]*=ay; tris[v+2]*=az
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
                            xa,xb,ya,yb,za,zb=coords[i],coords[i+1],ycoords[j],ycoords[j+1],zcoords[k-1],z
                            points=((xa,ya,za),(xb,ya,za),(xb,yb,za),(xa,yb,za),
                                    (xa,ya,zb),(xb,ya,zb),(xb,yb,zb),(xa,yb,zb))
                            for tetra in _TETRA:
                                vertices=tuple(points[index] for index in tetra)
                                field=tuple(values[index] for index in tetra)
                                for triangle in _tetra_triangles(vertices,field):
                                    # Avoid joining sign changes across undefined poles.
                                    center=tuple(sum(v[axis] for v in triangle)/3 for axis in (0,1,2))
                                    middle=_field(code,env,*center)
                                    if middle is None or abs(middle)>max(abs(v) for v in field)*2+1e-8: continue
                                    triangle=tuple(((v[0]-cx)*_sx,(v[1]-cy)*_sy,(v[2]-cz)*_sz) for v in triangle)
                                    _mesh_triangle(triangle,surface)
                                    for vertex in triangle:
                                        _zmin,_zmax=min(_zmin,vertex[2]),max(_zmax,vertex[2])
                        yield ('extracting surface',k*(n-1)+j,(n-1)**2)
                previous=current
    if not _mesh_colors:
        raise ValueError('No surface found; adjust range/resolution')
    if clip:
        _zmin,_zmax=clip  # colours and height follow the fixed range
    if _zmax-_zmin<1e-9: _zmax=_zmin+1
    _zscale=1.0 if _has_implicit else (_H*.72)/(_zmax-_zmin)
    yield ('complete',1,1)


def _xy_bounds():
    return list(_bounds) if _bounds else [-_range,_range,-_range,_range]


def _implicit_z():
    """The sampled z range of an implicit surface."""
    if _zrange: return list(_zrange)
    x0,x1,y0,y1=_xy_bounds()
    h=max(x1-x0,y1-y0)/2
    return [-h,h]


def _set_scales(hx,hy,hz=0.0):
    """Display scale per axis: 1 keeps true proportions; Box stretches each
    axis to the largest half-size."""
    global _H,_sx,_sy,_sz
    _H=max(hx,hy,hz)
    if _aspect=="box":
        _sx,_sy=_H/hx,_H/hy
        _sz=_H/hz if hz else 1.0
    else:
        _sx=_sy=_sz=1.0


def _any_implicit():
    try:
        return any(_surface_expression(e)[0] for e in (_expr,_expr2) if _clean_expr(e))
    except Exception:
        return False


def _heat_rect():
    """Screen rectangle of the heat map, leaving room for the colour bar and labels."""
    return _px0+30, _py0+6, _px1-52, _py1-14


def _heat_job():
    """Sample f(x, y) on screen cells, then trace contour lines; yields progress."""
    global _heat_values,_heat_info,_heat_lines,_need_heat,_probe
    implicit,code=_surface_expression(_expr)
    if implicit:
        raise ValueError(HEAT_IMPLICIT)
    _heat_values=_heat_lines=None
    collect()
    x0,x1,y0,y1=_xy_bounds()
    left,top,right,bottom=_heat_rect()
    w,h=right-left,bottom-top
    if _aspect=="equal":
        # True proportions: the map keeps x and y at the same scale.
        scale=min(w/(x1-x0),h/(y1-y0))
        w,h=max(2*HEAT_CELL,int((x1-x0)*scale)),max(2*HEAT_CELL,int((y1-y0)*scale))
        left,top=left+(right-left-w)//2,top+(bottom-top-h)//2
    cols,rows=max(2,w//HEAT_CELL),max(2,h//HEAT_CELL)
    cell_w,cell_h=w/cols,h/rows
    xs=array('f',[x0+(i+0.5)*(x1-x0)/cols for i in range(cols)])
    values=array('f',bytes(4*cols*rows))
    row=array('f',bytes(4*cols))
    env=dict(_SAFE)
    native=type(code) is not _CODE
    lo,hi=1e30,-1e30
    for j in range(rows):
        y=y1-(j+0.5)*(y1-y0)/rows
        if native:
            code.map(row,xs,y,0.0)
        else:
            for i in range(cols):
                z=_field(code,env,xs[i],y)
                row[i]=z if z is not None else float('nan')
        o=j*cols
        for i in range(cols):
            z=row[i]
            values[o+i]=z
            if z==z:
                if z<lo:lo=z
                if z>hi:hi=z
        yield ('sampling heat map',j+1,rows)
    if lo>hi:
        raise ValueError('f(x, y) is undefined everywhere in this range')
    if _zrange:
        lo,hi=_zrange
    if hi-lo<1e-12:
        hi=lo+1.0
    _heat_values=values
    _heat_info=(cols,rows,left,top,cell_w,cell_h,lo,hi)
    _probe=[cols//2,rows//2]
    # Contours at nine levels by marching squares between cell centres.
    lines=array('h')
    levels=[lo+(hi-lo)*(k+1)/10 for k in range(9)]
    for j in range(rows-1):
        for i in range(cols-1):
            a,b=values[j*cols+i],values[j*cols+i+1]
            c,d=values[(j+1)*cols+i+1],values[(j+1)*cols+i]
            if not (a==a and b==b and c==c and d==d):
                continue
            low,high=min(a,b,c,d),max(a,b,c,d)
            for level in levels:
                if not low<level<high:
                    continue
                points=[]
                for (p,q,px,py,qx,qy) in ((a,b,0,0,1,0),(b,c,1,0,1,1),(c,d,1,1,0,1),(d,a,0,1,0,0)):
                    if (p<level)!=(q<level):
                        t=(level-p)/(q-p)
                        points.append((left+(i+0.5+px+(qx-px)*t)*cell_w,top+(j+0.5+py+(qy-py)*t)*cell_h))
                for k in range(0,len(points)-1,2):
                    lines.extend((int(points[k][0]),int(points[k][1]),int(points[k+1][0]),int(points[k+1][1])))
        yield ('tracing contours',j+1,rows-1)
    _heat_lines=lines
    _need_heat=False
    yield ('complete',1,1)


_heat_ramp=None


def _heat_colors():
    """64 RGB565 steps of the height colour scale."""
    global _heat_ramp
    if _heat_ramp is None:
        _heat_ramp=[_rgb565(*_heat(i/63)) for i in range(64)]
    return _heat_ramp


def _probe_point():
    cols,rows,left,top,cell_w,cell_h,lo,hi=_heat_info
    x0,x1,y0,y1=_xy_bounds()
    i,j=_probe
    return x0+(i+0.5)*(x1-x0)/cols, y1-(j+0.5)*(y1-y0)/rows


def _draw_heatmap(draw):
    draw.fill_screen(C_BG)
    p=_palette()
    cols,rows,left,top,cell_w,cell_h,lo,hi=_heat_info
    ramp=_heat_colors()
    span=hi-lo
    for j in range(rows):
        y=int(top+j*cell_h)
        h=int(top+(j+1)*cell_h)-y
        o=j*cols
        for i in range(cols):
            z=_heat_values[o+i]
            x=int(left+i*cell_w)
            w=int(left+(i+1)*cell_w)-x
            if z==z:
                k=int((z-lo)/span*63)
                color=ramp[0 if k<0 else 63 if k>63 else k]
            else:
                color=p.PANEL  # undefined
            draw._fill_rectangle(x,y,w,h,color)
    if _contours and _heat_lines:
        lines=_heat_lines
        for k in range(0,len(lines),4):
            draw._line(lines[k],lines[k+1],lines[k+2],lines[k+3],C_BG)
    w,h=int(cols*cell_w),int(rows*cell_h)
    draw._rectangle(left-1,top-1,w+2,h+2,C_FRAME)
    # Axis limits at the corners.
    x0,x1,y0,y1=_xy_bounds()
    lab.text(draw,left,top+h+3,'{:g}'.format(x0),C_MUTED)
    lab.right_text(draw,left+w,top+h+3,'{:g}'.format(x1),C_MUTED)
    lab.right_text(draw,left-3,top,'{:g}'.format(y1),C_MUTED)
    lab.right_text(draw,left-3,top+h-8,'{:g}'.format(y0),C_MUTED)
    # Colour bar with its range: the bar, then its labels to the right.
    bx=_px1-46
    for k in range(h):
        draw._line(bx,top+k,bx+7,top+k,ramp[63-k*63//max(1,h-1)])
    draw._rectangle(bx-1,top-1,9,h+2,C_FRAME)
    for value,y in ((hi,top),((hi+lo)/2,top+h//2-4),(lo,top+h-8)):
        label='{:.3g}'.format(value)
        if len(label)>6:label='{:.0e}'.format(value)
        lab.text(draw,bx+11,y,label,C_MUTED)
    # Probe and its reading.
    i,j=_probe
    px,py=int(left+(i+0.5)*cell_w),int(top+(j+0.5)*cell_h)
    draw._line(px-5,py,px+5,py,C_TITLE)
    draw._line(px,py-5,px,py+5,C_TITLE)
    x,y=_probe_point()
    z=_field(_surface_expression(_expr)[1],dict(_SAFE),x,y)
    reading='x {:.3g}  y {:.3g}  z {}'.format(x,y,'--' if z is None else '{:.4g}'.format(z))
    _paint_chrome(draw,reading,'','')
    draw.swap()


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
    _paint_chrome(draw,sub)  # a toast shows in the footer (errors in a box)
    draw.swap()


def _draw_mesh_python(draw,style,count,stride):
    """Python renderer, for firmware without the C one."""
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
    p=_palette()
    name,done,total=progress
    percent=min(100,int(done*100/max(1,total)))
    bottom=int(draw.size.y)-lab.FOOT
    lab.panel(draw,p,(8,43,_sw-16,bottom-46),'BUILDING','%d%%'%percent)
    lab.text(draw,18,100,name,C_ACCENT,FONT_MEDIUM)
    detail='N={}  {} triangles'.format(_grid_n,len(_mesh_colors or ())) if _style!=2 else 'heat map cells'
    lab.text(draw,18,130,detail,C_MUTED,FONT_SMALL)
    draw._fill_rectangle(18,156,_sw-36,10,C_PANEL)
    draw._fill_rectangle(18,156,int((_sw-36)*percent/100),10,C_ACCENT)
    lab.text(draw,18,180,'ESC cancels',C_MUTED,FONT_SMALL)
    _paint_chrome(draw,'sampling')
    draw.swap()


def _begin_resolution(view_manager):
    """G: the settings form with the resolution being typed."""
    global _state,_set_row,_edit,_edit_note,_edit_error
    _state=ST_SETTINGS
    _set_row=[r[0] for r in _settings_rows()].index('res')
    _edit=LineEdit(str(_grid_n),8)
    _edit_note,_edit_error='',False
    _draw_settings(view_manager.draw)


def _draw_resolution_warning(draw):
    _,implicit,samples=_resolution_warning(_pending_resolution)
    draw.fill_screen(C_BG)
    lines=('High resolution may be slow',
           'N={}  {} samples'.format(_pending_resolution,samples),
           'Implicit: N x N x N' if implicit else 'Function: N x N',
           'More detail uses more RAM.',
           'Dense meshes may exceed memory.',
           'Sampling can be cancelled with ESC.')
    bottom=int(draw.size.y)-lab.FOOT
    lab.panel(draw,_palette(),(8,43,_sw-16,bottom-46),'PERFORMANCE WARNING')
    for i,line in enumerate(lines): lab.text(draw,18,70+i*20,line,C_AMBER if i==0 else C_TITLE,FONT_SMALL)
    lab.text(draw,18,206,'ENTER apply   ESC keep N={}'.format(_grid_n),C_MUTED,FONT_SMALL)
    _paint_chrome(draw,'warning')
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
    _py0 = lab.HEAD + 4
    _px1 = _sw - 7
    _py1 = _sh - lab.FOOT - 4
    _cx = (_px0 + _px1) // 2
    _cy = (_py0 + _py1) // 2
    short = min(_px1 - _px0, _py1 - _py0)
    _focal = short * 0.78
    _cam = max(7.6 + _H * 0.22, _H * 2.4)


def _paint_chrome(draw, subtitle, footer1='', footer2=''):
    """The shared PicoLAB title bar and footer; footers are in F9 help now."""
    title=(_plot_title or 'SURFACE').upper()[:20] if _embedded else 'GRAPH 3D'
    lab.chrome(draw,_palette(),subtitle,_toast,_toast_error,title,() if _embedded else ('tools','Graph3D'))


class _PanelMenu:
    """A list of "label | detail" rows in the shared PicoLAB panel."""
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

    def rows(self):
        return [tuple(item.split(" | ",1)) if " | " in item else (item,"") for item in self.items]

    def draw(self, prompt=False):
        draw = self.display
        draw.fill_screen(C_BG)
        lab.menu(draw,_palette(),self.rows(),self.selected_index,self.title.upper(),int(draw.size.y)-lab.FOOT)
        if prompt:
            _draw_prompt(draw)
        _paint_chrome(draw,self.title)
        draw.swap()


class _HelpPanel:
    """The shared F9 help box."""
    def __init__(self, draw, *unused):
        self.display = draw
        self.lines = []
        self.row = 0

    def set_text(self, text):
        self.lines = text if isinstance(text, (tuple, list)) else text.split("\n")
        self.draw()

    def capacity(self):
        return lab.help_capacity(int(self.display.size.y)-lab.FOOT)

    def scroll(self, step):
        self.row = min(max(0, self.row+step), max(0, len(self.lines)-self.capacity()))
        self.draw()

    def scroll_up(self):
        self.scroll(-1)

    def scroll_down(self):
        self.scroll(1)

    def draw(self):
        draw = self.display
        draw.fill_screen(C_BG)
        lab.help_box(draw,_palette(),self.lines,self.row,int(draw.size.y)-lab.FOOT)
        _paint_chrome(draw, "help")
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
    if _style == 2 and _heat_info is not None:
        _draw_heatmap(draw)
    else:
        _draw_mesh(draw, preview)


def _draw_error(draw):
    draw.fill_screen(C_BG)
    p=_palette()
    bottom=int(draw.size.y)-lab.FOOT
    lab.panel(draw,p,(8,43,_sw-16,bottom-46),'COULD NOT PLOT')
    for i,line in enumerate(lab.wrap(_error_msg or "Unknown error",44)[:6]):
        lab.text(draw,18,70+12*i,line,C_ERR,FONT_SMALL)
    for i,line in enumerate(("ENTER  fix the equation","W      ranges and resolution","ESC    "+("return" if _embedded else "main menu"))):
        lab.text(draw,18,160+16*i,line,C_MUTED,FONT_SMALL)
    _paint_chrome(draw, "error")
    draw.swap()


def _settings_rows():
    """(key, label, value, kind) for the settings form; kind num, choice or action."""
    x0,x1,y0,y1=_xy_bounds()
    implicit=_any_implicit()
    if _zrange:
        z=_zrange
    elif implicit:
        z=_implicit_z()
    else:
        z=[_zmin,_zmax] if _mesh_colors else None
    zt=lambda v:'{:.4g}'.format(v) if z else 'auto'
    return [('x0','X minimum','{:g}'.format(x0),'num'),('x1','X maximum','{:g}'.format(x1),'num'),
            ('y0','Y minimum','{:g}'.format(y0),'num'),('y1','Y maximum','{:g}'.format(y1),'num'),
            ('zmode','Z range','Fixed' if _zrange else 'Auto','choice'),
            ('z0','Z minimum',zt(z[0] if z else 0),'num'),('z1','Z maximum',zt(z[1] if z else 0),'num'),
            ('aspect','Aspect','Equal' if _aspect=='equal' else 'Box','choice'),
            ('res','Resolution N',str(_grid_n),'num'),
            ('style','Style',STYLES[_style],'choice'),
            ('contours','Heat map contours','On' if _contours else 'Off','choice'),
            ('spin','Auto spin','On' if _auto else 'Off','choice'),
            ('nav','Arrow controls','Pan' if _navigation=='pan' else 'Orbit','choice'),
            ('fit','Fit surface to view','ENTER','action'),
            ('camera','Reset camera','ENTER','action')]


def _draw_settings(draw):
    draw.fill_screen(C_BG)
    p=_palette()
    rows=_settings_rows()
    bottom=int(draw.size.y)-lab.FOOT
    lab.panel(draw,p,(8,43,_sw-16,bottom-46),'SETTINGS','%d/%d'%(_set_row+1,len(rows)))
    lab.form(draw,p,[('field',label,value,True) for key,label,value,kind in rows],_set_row,_edit,67,bottom-24)
    note=_edit_note or ('Type a number   ENTER edit   ESC plot' if rows[_set_row][3]=='num' else
                        'ENTER or LEFT/RIGHT change   ESC plot')
    lab.text(draw,16,bottom-18,note[:46],C_ERR if _edit_error else C_MUTED)
    _paint_chrome(draw, "settings")
    draw.swap()


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
    _menu.add_item("Settings | ranges / heat map / mesh / camera")
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
    _help_box.set_text(HELP_LINES)


def _begin_input(view_manager, second=False):
    """Edit an equation in place: the menu stays behind a prompt panel."""
    global _edit,_edit_note,_edit_error
    _edit=LineEdit(_clean_expr(_expr2 if second else _expr).replace('**','^'),80)
    _edit_note,_edit_error='',False
    _draw_input(view_manager.draw, second)


def _draw_prompt(draw):
    second=_state==ST_INPUT2
    bottom=int(draw.size.y)-lab.FOOT
    title='Second surface g' if second else 'Surface'
    detail=('g(x,y); empty clears it' if second else 'z = f(x,y) or F(x,y,z) = 0')
    lab.prompt(draw,_palette(),title,detail,_edit,_edit_note or 'ENTER plot   ESC cancel',_edit_error,
               (8,bottom-110,_sw-16,106))


def _draw_input(draw, second=False):
    if _menu is not None and not _embedded:
        _menu.draw(True)
        return
    draw.fill_screen(C_BG)
    _draw_prompt(draw)
    _paint_chrome(draw,'equation')
    draw.swap()


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
    x0, x1, y0, y1 = _xy_bounds()
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
        title = "slice  y={:.3g}".format(y0 + (y1 - y0) * idx / (n - 1))
    else:
        title = "slice  x={:.3g}".format(x0 + (x1 - x0) * idx / (n - 1))
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
    global _state, _dirty, _need_eval, _slice_idx, _toast, _toast_error, _preview_at, _sampling, _sampling_progress, _style
    _layout(view_manager.draw)
    _preview_at = None
    _toast, _toast_error = "", False
    if _style == 2 and _any_implicit():
        # A heat map needs one height per (x, y): keep the 3D view and say why.
        _style, _toast, _toast_error = 1, HEAT_IMPLICIT, True
    if _style == 2:
        job = _heat_job() if _need_heat or _heat_info is None else None
    else:
        job = _sample_job() if _need_eval or not _mesh_colors else None
    if job is not None:
        _sampling = job
        _sampling_progress = ("sampling",0,1)
        _state = ST_SAMPLING
        _draw_sampling(view_manager.draw,_sampling_progress)
    else:
        _state = ST_PLOT
        _dirty = True
    _slice_idx = _grid_n // 2


def _changed_ranges():
    global _need_eval,_need_heat
    _need_eval=_need_heat=True


def _set_style(style):
    """Change the style; a heat map of an implicit surface is refused with a reason."""
    global _style,_toast,_toast_error
    if style == 2 and _any_implicit():
        _toast,_toast_error = HEAT_IMPLICIT,True
        return False
    _style=style
    return True


def _apply_setting(step):
    """Change the choice or run the action on the current settings row."""
    global _zrange, _aspect, _contours, _auto, _navigation
    key = _settings_rows()[_set_row][0]
    if key == 'zmode':
        if _zrange:
            _zrange = None
        else:
            z = [_zmin,_zmax] if _mesh_colors and not _has_implicit else _implicit_z()
            _zrange = [z[0], z[1] if z[1] > z[0] else z[0]+1]
        _changed_ranges()
    elif key == 'aspect':
        _aspect = 'box' if _aspect == 'equal' else 'equal'
        _changed_ranges()
    elif key == 'style':
        order = (1, 0, 2)
        target = order[(order.index(_style) + (1 if step > 0 else -1)) % 3]
        if not _set_style(target) and target == 2:
            _set_style(order[(order.index(target) + (1 if step > 0 else -1)) % 3])
    elif key == 'contours':
        _contours = not _contours
    elif key == 'spin':
        _auto = not _auto
    elif key == 'nav':
        _navigation = "orbit" if _navigation == "pan" else "pan"
    elif key == 'fit':
        if _need_eval:
            return False
        _fit_surface()
    elif key == 'camera':
        _reset_camera()
    return True


def _set_number(key, text):
    """Apply a typed settings value; raises ValueError and changes nothing."""
    global _bounds, _zrange, _pending_resolution
    if key == 'res':
        value = parse_number(text)
        if value != int(value):
            raise ValueError('Resolution must be an integer: 4..64')
        return int(value)
    value = parse_number(text)
    if not abs(value) <= 1e6:
        raise ValueError('Values must be within 1e6')
    if key in ('x0','x1','y0','y1'):
        b = _xy_bounds()
        b[('x0','x1','y0','y1').index(key)] = value
        if not (b[1]-b[0] > 1e-6 and b[3]-b[2] > 1e-6):
            raise ValueError('Minimum must be below maximum')
        _bounds = b
    else:
        z = list(_zrange) if _zrange else ([_zmin,_zmax] if _mesh_colors and not _has_implicit else _implicit_z())
        z[0 if key == 'z0' else 1] = value
        if not z[1]-z[0] > 1e-9:
            raise ValueError('Z minimum must be below Z maximum')
        _zrange = z
    _changed_ranges()
    return None


def start(view_manager, plot_spec=None) -> bool:
    global _viewer_active, _aspect, _contours, _probe
    global _state, _dirty, _need_eval, _auto, _zs, _zs2
    global _pitch, _yaw, _zoom, _set_row, _hint_flash
    global _menu, _preset_menu, _help_box, _saved_menu
    global _storage, _grid_n, _toast, _navigation, _mesh, _mesh_colors, _sampling
    global _embedded,_brand,_plot_title,_expr,_expr2,_range,_style,_pending_resolution,_resolution_return
    global _bounds,_zrange,_need_heat,_heat_info,_edit,_toast_error

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
        _bounds = list(plot_spec['bounds']) if 'bounds' in plot_spec else None
        _zrange = plot_spec.get('zrange')
        _aspect = plot_spec.get('aspect', 'equal')
        _contours = plot_spec.get('contours', True)
        _probe = [0, 0]
        _style = {'wire': 0, 'solid': 1, 'heatmap': 2}[plot_spec.get('style','solid')]
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
    _need_heat = True
    _heat_info = None
    _edit = None
    _toast_error = False
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
    _load_session(_storage)
    if requested_resolution is not None and _resolution_warning(requested_resolution)[0]:
        _pending_resolution = requested_resolution
        _grid_n = 12
        _resolution_return = ST_PLOT
        _state = ST_RES_WARNING
        _draw_resolution_warning(view_manager.draw)
    else:
        _goto_plot(view_manager)
    _viewer_active = True
    return True


def run(view_manager) -> None:
    global _state, _dirty, _expr, _expr2, _need_eval, _zs2
    global _pitch, _yaw, _zoom, _auto, _style
    global _range, _grid_n, _set_row, _slice_axis, _slice_idx, _toast
    global _pan_x, _pan_y, _navigation, _preview_at, _last_spin_ms
    global _sampling,_sampling_progress,_sampling_draw_ms,_error_msg,_pending_resolution,_fit_pending
    global _need_heat,_edit,_edit_note,_edit_error,_help_return,_bounds,_contours,_probe,_toast_error,_help_box,_resolution_return

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
            _sampling=None; _error_msg=''
            if _style!=2: _need_eval=False
            _state=ST_PLOT; _dirty=True
            _layout(draw)  # the camera follows the new box size before fitting
            if _style!=2 and (_has_implicit or _fit_pending): _fit_surface()
            _fit_pending=False
        except Exception as exc:
            _sampling=None; _error_msg=("Out of RAM; press G to lower resolution" if isinstance(exc,MemoryError) else str(exc))[:80]
            _release_mesh(); _need_eval=True
            _fit_pending=False; _state=ST_ERROR; _dirty=True
        if _state==ST_SAMPLING and ticks_diff(ticks_ms(),_sampling_draw_ms)>=100:
            _draw_sampling(draw,_sampling_progress); _sampling_draw_ms=ticks_ms()
        return

    elif _state == ST_RES_WARNING:
        if button==BUTTON_ESCAPE:
            inp.reset()
            if _embedded and not _mesh_colors:
                view_manager.back()
                return
            _state=_resolution_return; _dirty=True
            if _state==ST_SETTINGS: _draw_settings(draw); _dirty=False
            elif _state==ST_ERROR: _draw_error(draw); _dirty=False
        elif button==BUTTON_CENTER:
            inp.reset(); _apply_resolution(_pending_resolution)
            _state=_resolution_return; _dirty=True
            if _state in (ST_PLOT,ST_ERROR): _goto_plot(view_manager)
            else: _draw_settings(draw); _dirty=False
        return

    if button == BUTTON_F9 and _edit is None and _state not in (ST_HELP, ST_RES_WARNING):
        inp.reset()
        _auto = False
        _help_return = _state
        _state = ST_HELP
        _make_help(view_manager)
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
                _help_return = ST_MENU
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
                    _range, _bounds = 2.0, None
                _need_eval = _need_heat = True
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
                _need_eval = _need_heat = True
                _kill_menu("saved")
                _goto_plot(view_manager)

    elif _state == ST_SETTINGS:
        rows = _settings_rows()
        key, label, value, kind = rows[_set_row]
        if button == BUTTON_NONE:
            pass
        elif _edit is not None:
            inp.reset()
            result = 'cancel' if button == BUTTON_ESCAPE else _edit.key(view_manager, button)
            if result == 'cancel':
                _edit, _edit_note, _edit_error = None, '', False
            elif result is not None:
                try:
                    n = _set_number(key, _edit.text)
                except ValueError as exc:
                    _edit_note, _edit_error = str(exc), True
                else:
                    _edit, _edit_note, _edit_error = None, '', False
                    if n is not None:
                        warning, _, _ = _resolution_warning(n)
                        if warning:
                            _pending_resolution, _resolution_return, _state = n, ST_SETTINGS, ST_RES_WARNING
                            _draw_resolution_warning(draw)
                            return
                        _apply_resolution(n)
                    if result in ('up', 'down'):
                        _set_row = (_set_row + (-1 if result == 'up' else 1)) % len(rows)
            _dirty = True
        elif button in (BUTTON_UP, BUTTON_DOWN):
            inp.reset()
            _set_row = (_set_row + (-1 if button == BUTTON_UP else 1)) % len(rows)
            _dirty = True
        elif button == BUTTON_ESCAPE:
            inp.reset()
            _goto_plot(view_manager)
            return
        elif kind == 'num':
            char = inp.button_to_char(button)
            if button == BUTTON_CENTER or erase_key(view_manager, button):
                inp.reset()
                start_text = value if value != 'auto' else ''
                _edit = LineEdit(start_text, 16)
                if button != BUTTON_CENTER:
                    _edit.key(view_manager, button)
                _edit_note, _edit_error = '', False
                _dirty = True
            elif char and (char.isdigit() or char in '-.('):
                inp.reset()
                _edit = LineEdit('', 16)
                _edit.key(view_manager, button)
                _edit_note, _edit_error = '', False
                _dirty = True
        elif button in (BUTTON_LEFT, BUTTON_RIGHT, BUTTON_CENTER):
            inp.reset()
            _toast, _toast_error = '', False
            if key == 'fit' and _need_eval:
                _fit_pending = True
                _goto_plot(view_manager)
                return
            _apply_setting(-1 if button == BUTTON_LEFT else 1)
            if key in ('fit', 'camera'):
                _goto_plot(view_manager)
                return
            _dirty = True
        if _state == ST_SETTINGS and _dirty:
            _draw_settings(draw)
            _dirty = False

    elif _state == ST_HELP:
        if _help_box is None:
            _make_help(view_manager)
        if button in (BUTTON_ESCAPE, BUTTON_F9, BUTTON_CENTER):
            inp.reset()
            _kill_menu("help")
            back = _help_return
            if back in (ST_PLOT, ST_SLICE, ST_ERROR) or _embedded:
                _state = back if back in (ST_SLICE, ST_ERROR) else ST_PLOT
                if _state == ST_PLOT: _goto_plot(view_manager)
                else: _dirty = True
            elif back == ST_SETTINGS:
                _state, _dirty = ST_SETTINGS, True
                _draw_settings(draw); _dirty = False
            else:
                _state = ST_MENU
                _make_menu(view_manager)
        elif button in (BUTTON_UP, BUTTON_DOWN):
            inp.reset()
            _help_box.scroll(-1 if button == BUTTON_UP else 1)
        elif button in (BUTTON_LEFT, BUTTON_RIGHT):
            inp.reset()
            step = _help_box.capacity()
            _help_box.scroll(-step if button == BUTTON_LEFT else step)

    elif _state in (ST_INPUT, ST_INPUT2):
        second = _state == ST_INPUT2
        if _edit is None:
            _begin_input(view_manager, second)
        if button != BUTTON_NONE:
            inp.reset()
            result = 'cancel' if button == BUTTON_ESCAPE else _edit.key(view_manager, button)
            if result == 'cancel':
                _edit = None
                if _embedded: _goto_plot(view_manager)
                else:
                    _state = ST_MENU
                    _make_menu(view_manager)
                return
            if result in ('commit', 'up', 'down'):
                text = _edit.text.strip()
                try:
                    if text: _surface_expression(text)
                except Exception as exc:
                    _edit_note, _edit_error = str(exc)[:80], True
                else:
                    _edit = None
                    if second:
                        _expr2 = text
                    elif text:
                        _expr = text
                    _need_eval = _need_heat = True
                    if text:
                        _goto_plot(view_manager)
                        return
                    if second: _zs2 = None
                    _state = ST_MENU
                    _make_menu(view_manager)
                    return
            _draw_input(draw, second)

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
        elif button in (BUTTON_G, BUTTON_W):
            inp.reset()
            if button == BUTTON_G:
                _begin_resolution(view_manager)
            else:
                _state, _set_row = ST_SETTINGS, 0
                _draw_settings(draw)
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
        heat = _style == 2 and _heat_info is not None
        if heat and button in (BUTTON_LEFT, BUTTON_RIGHT, BUTTON_UP, BUTTON_DOWN):
            inp.reset()
            cols, rows = _heat_info[0], _heat_info[1]
            if button == BUTTON_LEFT: _probe[0] = max(0, _probe[0]-1)
            elif button == BUTTON_RIGHT: _probe[0] = min(cols-1, _probe[0]+1)
            elif button == BUTTON_UP: _probe[1] = max(0, _probe[1]-1)
            else: _probe[1] = min(rows-1, _probe[1]+1)
            moved = True
        elif heat and button in (BUTTON_PLUS, BUTTON_EQUAL, BUTTON_MINUS):
            inp.reset()
            # Zoom the x/y range about the probe.
            x, y = _probe_point()
            x0, x1, y0, y1 = _xy_bounds()
            k = 1.25 if button == BUTTON_MINUS else 0.8
            hx, hy = (x1-x0)*k/2, (y1-y0)*k/2
            if hx > 1e-6 and hy > 1e-6 and max(abs(x)+hx, abs(y)+hy) < 1e6:
                _bounds = [x-hx, x+hx, y-hy, y+hy]
                _need_eval = _need_heat = True
                _goto_plot(view_manager)
            return
        elif heat and button == BUTTON_L:
            inp.reset()
            _contours = not _contours
            moved = True
        elif button in (BUTTON_LEFT, BUTTON_RIGHT, BUTTON_UP, BUTTON_DOWN):
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
            _auto = False
            order = (1, 0, 2)
            target = order[(order.index(_style)+1) % 3]
            refused = not _set_style(target)
            if refused:
                target = order[(order.index(target)+1) % 3]
                _set_style(target)
            _goto_plot(view_manager)
            if refused:
                _toast, _toast_error, _dirty = HEAT_IMPLICIT, True, True  # say why the heat map was skipped
            if target == 2 or _state != ST_PLOT:
                return
            moved = True
        elif button == BUTTON_R:
            inp.reset()
            _reset_camera()
            moved = True
        elif button == BUTTON_CENTER:
            inp.reset()
            _auto = False
            _state = ST_INPUT
            _begin_input(view_manager, False)
            return
        elif button == BUTTON_C:
            inp.reset()
            if _has_implicit or _zs is None:
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
            _range = _cycle(RANGES, max(_xy_bounds()[1], _range) if _bounds is None else _range, 1)
            _bounds = None
            _need_eval = _need_heat = True
            _goto_plot(view_manager)
            return

        if _auto and not heat and ticks_diff(ticks_ms(), _last_spin_ms) >= 50:
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


def _save_session(storage):
    """Keep the standalone surface and settings on SD: PicoLAB unloads Graph3D's
    code when it closes, so module globals do not survive."""
    if not storage:
        return
    try:
        import json
        data = json.dumps({'version': 1, 'f': _expr, 'g': _expr2, 'range': _range, 'bounds': _bounds,
                           'zrange': _zrange, 'aspect': _aspect, 'n': _grid_n, 'style': _style,
                           'contours': _contours})
        if not storage.exists(FILE_SESSION) or storage.read(FILE_SESSION) != data:
            storage.write(FILE_SESSION, data)
    except Exception as exc:
        print('[Graph3D] Save session:', exc)


def _load_session(storage):
    global _expr, _expr2, _range, _bounds, _zrange, _aspect, _grid_n, _style, _contours
    if not storage:
        return
    try:
        if not storage.exists(FILE_SESSION):
            return
        import json
        data = json.loads(storage.read(FILE_SESSION))
        for text in (data['f'], data['g']):
            if text: _surface_expression(text)
        n = data['n']
        if not (isinstance(n, int) and 4 <= n <= 64) or data['style'] not in (0, 1, 2) or \
                data['aspect'] not in ('equal', 'box') or not 0.01 <= data['range'] <= 100:
            raise ValueError('settings out of range')
        for box in (data['bounds'], data['zrange']):
            if box is not None and not (len(box) in (2, 4) and box[1] > box[0] and box[-1] > box[-2]):
                raise ValueError('invalid range')
        _expr, _expr2, _range, _bounds = data['f'], data['g'], float(data['range']), data['bounds']
        _zrange, _aspect, _grid_n, _style = data['zrange'], data['aspect'], n, data['style']
        _contours = bool(data['contours'])
    except Exception as exc:
        print('[Graph3D] Load session:', exc)


def stop(view_manager) -> None:
    global _viewer_active
    _viewer_active = False
    global _menu, _preset_menu, _help_box, _zs
    global _state, _auto, _dirty

    global _saved_menu, _zs2, _sampling, _fit_pending, _edit, _heat_values, _heat_info, _heat_lines, _need_heat
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
    if not _embedded:
        _save_session(_storage)
    _release_mesh()
    _fit_pending=False
    _zs = None
    _zs2 = None
    _auto = False
    _dirty = True
    _state = ST_MENU
    _edit = None
    _heat_values = _heat_info = _heat_lines = None
    _need_heat = True
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
    if spec.get('style','solid') not in ('solid','wire','heatmap'):
        raise ValueError('Style must be solid, wire or heatmap')
    bounds = spec.get('bounds')
    if bounds is not None:
        if len(bounds) != 4 or not all(isinstance(v,(int,float)) and _finite(v) for v in bounds) or \
                not (bounds[1] > bounds[0] and bounds[3] > bounds[2]):
            raise ValueError('3D bounds: [x0, x1, y0, y1] with min < max')
    return spec


class _PlotView:
    def __init__(self,spec):
        self.spec,self.previous = spec,None

    def start(self,vm):
        if _viewer_active:
            raise ValueError('This 3D viewer is already open')
        self.previous = (_expr,_expr2,_range,_grid_n,_style,_bounds,_zrange,_aspect,_contours,_saved,_probe)
        return start(vm,self.spec)

    def run(self,vm):
        run(vm)

    def stop(self,vm):
        global _expr,_expr2,_range,_grid_n,_style,_embedded,_brand,_plot_title,_bounds,_zrange,_aspect,_contours,_saved,_probe
        stop(vm)
        if self.previous is not None:
            _expr,_expr2,_range,_grid_n,_style,_bounds,_zrange,_aspect,_contours,_saved,_probe = self.previous
        self.spec,self.previous = None,None
        _embedded,_brand,_plot_title = False,'GRAPH 3D',''


def show(view_manager,plot_spec):
    """Open a tool-owned 3D plot and restore standalone equation settings on exit."""
    validate_spec(plot_spec)
    from .view import open_view
    return open_view(view_manager,'eng_plot3d',_PlotView(plot_spec))
