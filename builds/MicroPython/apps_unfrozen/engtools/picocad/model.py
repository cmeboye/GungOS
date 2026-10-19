"""Bounded parametric construction history; dimensions in millimetres."""
import json
from .issues import Issue
from math import sin,cos,pi,isfinite

SHAPES=('Box','Sphere','Cylinder','Cone')
OPERATIONS=('Add','Cut','Intersect')
QUALITIES=(6,8,10,12,16,20,24)
MAX_FEATURES=8
DIRECTORY='picoware/engineering/cad'
MAX_FILE=32768
NUMBERS=('a','b','c','x','y','z','rx','ry','rz')


def primitive(shape='Box',operation='Add',index=1):
    return dict(name=shape+' '+str(index),shape=shape,op=operation,
                a=40.0 if shape=='Box' else 5.0,b=30.0,c=10.0 if shape=='Box' else 16.0,
                x=0.0,y=0.0,z=0.0,rx=0.0,ry=0.0,rz=0.0)


def blank():return dict(picocad=1,units='mm',resolution=8,features=[])

def example(hole=True):
    result=blank();result['features']=[primitive()]
    if hole:result['features'].append(primitive('Cylinder','Cut',2))
    return result


def clone(model):return dict(picocad=1,units='mm',resolution=model['resolution'],features=[dict(f) for f in model['features']])


def validate(model):
    if not isinstance(model,dict) or type(model.get('picocad')) is not int or model['picocad']!=1 or model.get('units')!='mm':
        raise Issue('invalid','Not a PicoCAD v1 mm project')
    if type(model.get('resolution')) is not int or model['resolution'] not in QUALITIES:
        raise Issue('invalid','Resolution: 6, 8, 10, 12, 16, 20 or 24')
    features=model.get('features')
    if not isinstance(features,list):raise Issue('invalid','Features must be a list')
    if len(features)>MAX_FEATURES:raise Issue('limit','8 construction steps')
    for index,f in enumerate(features):
        if not isinstance(f,dict) or f.get('shape') not in SHAPES or f.get('op') not in OPERATIONS:
            raise Issue('invalid','Invalid primitive or operation',index+1)
        if index==0 and f['op']!='Add':raise Issue('invalid','First step must be Add')
        name=f.get('name')
        if not isinstance(name,str) or not 1<=len(name)<=24 or any(ord(c)<32 or ord(c)>126 for c in name):
            raise Issue('invalid','Use a short printable feature name')
        for key in NUMBERS:
            value=f.get(key)
            if type(value) not in (int,float) or not isfinite(value):raise Issue('invalid','Finite numeric values required',index+1)
            if key in (('a','b','c') if f['shape']=='Box' else ('a',) if f['shape']=='Sphere' else ('a','c')):
                if value<=0:raise Issue('invalid','Dimensions must be positive',index+1)
                if not .01<=value<=10000:raise Issue('limit','Dimensions: 0.01 .. 10000 mm',index+1)
            if key in ('x','y','z') and abs(value)>100000:raise Issue('limit','Position: +/-100000 mm',index+1)
            if key in ('rx','ry','rz') and abs(value)>3600:raise Issue('limit','Rotation: +/-3600 degrees',index+1)
    return model


def matrix(f):
    """Local to world: Rz * Ry * Rx, angles in degrees."""
    x,y,z=(f[k]*pi/180 for k in ('rx','ry','rz'))
    cx,sx,cy,sy,cz,sz=cos(x),sin(x),cos(y),sin(y),cos(z),sin(z)
    return ((cz*cy,cz*sy*sx-sz*cx,cz*sy*cx+sz*sx),
            (sz*cy,sz*sy*sx+cz*cx,sz*sy*cx-cz*sx),(-sy,cy*sx,cy*cx))


def world(f,point):
    m=matrix(f)
    return tuple(sum(m[j][i]*point[i] for i in range(3))+f[k] for j,k in enumerate(('x','y','z')))


def local(f,point):
    m=matrix(f);q=tuple(point[i]-f[k] for i,k in enumerate(('x','y','z')))
    return tuple(sum(m[j][i]*q[j] for j in range(3)) for i in range(3))


def half_size(f):
    if f['shape']=='Box':return f['a']/2,f['b']/2,f['c']/2
    if f['shape']=='Sphere':return (f['a'],)*3
    return f['a'],f['a'],f['c']/2


def bounds(model):
    # Cutters/intersections cannot enlarge the body. Use the Add primitives'
    # conservative rotated boxes, plus a small camera-framing margin.
    points=[]
    for f in model['features']:
        if f['op']!='Add':continue
        hx,hy,hz=half_size(f)
        if f['shape']=='Sphere':
            points.extend((f['x']+x,f['y']+y,f['z']+z) for x in (-hx,hx) for y in (-hy,hy) for z in (-hz,hz))
        else:points.extend(world(f,(x,y,z)) for x in (-hx,hx) for y in (-hy,hy) for z in (-hz,hz))
    if not points:return (-1,1,-1,1,-1,1)
    result=[]
    extent=max(max(p[i] for p in points)-min(p[i] for p in points) for i in range(3))
    for i in range(3):
        lo,hi=min(p[i] for p in points),max(p[i] for p in points)
        pad=max((hi-lo)*.08,extent*.02)
        result.extend((lo-pad,hi+pad))
    return tuple(result)


def filename(name):
    name=name.strip()
    if name.lower().endswith('.pcad'):name=name[:-5]
    if not 1<=len(name)<=32 or any(not (c.isalpha() or c.isdigit() or c in ' _-') for c in name):
        raise ValueError('Name: 1..32 letters, digits, space, _ or -')
    return name+'.pcad'


def save(storage,name,model):
    validate(model)
    text=json.dumps(clone(model))
    if len(text.encode())>MAX_FILE:raise ValueError('Project too large')
    if not storage.active:raise OSError('SD card unavailable')
    for path in ('picoware','picoware/engineering',DIRECTORY):
        if not storage.exists(path) and not storage.mkdir(path):raise OSError('Could not create CAD folder')
    path=DIRECTORY+'/'+filename(name);temp,backup=path+'.tmp',path+'.bak'
    if not storage.write(temp,text) or storage.read(temp)!=text:raise OSError('Write verification failed; original kept')
    existed=storage.exists(path)
    if existed:
        if storage.exists(backup):raise OSError('Recover existing .bak before saving')
        if not storage.rename(path,backup):raise OSError('Could not back up original')
    if not storage.rename(temp,path):
        if existed:storage.rename(backup,path)
        raise OSError('Save failed; original kept in file or .bak')
    if existed:storage.remove(backup)
    return path


def load(storage,name):
    path=DIRECTORY+'/'+filename(name)
    if not storage.active or not storage.exists(path):raise OSError('Project unavailable')
    if storage.size(path)>MAX_FILE:raise ValueError('Project exceeds 32 KiB')
    result=json.loads(storage.read(path));validate(result)
    return clone(result)


def files(storage):
    if not storage.active or not storage.exists(DIRECTORY):return []
    return sorted(name for name in storage.listdir(DIRECTORY) if name.lower().endswith('.pcad'))[:64]
