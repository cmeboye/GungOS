"""Analytic lines, ellipse/circle rims and view-dependent primitive silhouettes.

No volume samples or triangles. Supported Boolean topology is planned by
solid.py; unsupported constructions never install a partial result.
"""
from array import array
from math import cos,sin,pi,sqrt,atan2,acos,isfinite
from . import model as dm
from .solid import dot,sub,add,mul,cross,axes,position,plan
from .issues import Issue
from .trim import cut_segment


def curve_point(curve,angle):
    co,si=cos(angle)*curve[9],sin(angle)*curve[9]
    return tuple(curve[j]+curve[3+j]*co+curve[6+j]*si for j in range(3))


class Boundaries:
    """Packed lines (6 floats), plane curves (10), analytic surfaces (23)."""
    def __init__(self,tolerance):
        self.lines=array('f');self.circles=array('f');self.surfaces=array('f');self.arcs=array('f');self.spans=array('f');self.tolerance=tolerance
        self.status='success';self.body_count=0

    def __len__(self):return len(self.lines)//6+len(self.circles)//10+len(self.surfaces)//23+len(self.arcs)//12

    def curve(self,center,u,v,r):
        self.circles.extend(center);self.circles.extend(u);self.circles.extend(v);self.circles.append(r)

    def arc(self,center,u,v,r,start,end):
        self.arcs.extend(center+u+v+(r,start,end))

    def circle_point(self,i,angle):return curve_point(self.circles[i:i+10],angle)

    def fit_points(self):
        for i in range(0,len(self.lines),3):yield tuple(self.lines[i:i+3])
        for i in range(0,len(self.circles),10):
            for n in range(16):yield self.circle_point(i,n*pi/8)
        for i in range(0,len(self.arcs),12):
            curve=self.arcs[i:i+10];start,end=self.arcs[i+10:i+12]
            for j in range(17):yield curve_point(curve,start+(end-start)*j/16)
        for i in range(0,len(self.surfaces),23):
            kind=self.surfaces[i];c=tuple(self.surfaces[i+1:i+4]);r=self.surfaces[i+13]
            if kind==0:
                # Enclose a sphere conservatively even in perspective.
                for x in (-r,r):
                    for y in (-r,r):
                        for z in (-r,r):yield add(c,(x,y,z))
            elif kind==2:yield add(c,mul(tuple(self.surfaces[i+10:i+13]),self.surfaces[i+14]/2))

    def _arc(self,camera,curve,start,end,p,q,depth):
        middle=(start+end)/2;m=camera.ratio(curve_point(curve,middle))
        if p is None or q is None or m is None:split=True
        else:
            dx=(m[0]-(p[0]+q[0])/2)*camera.focal*camera.zoom
            dy=(m[1]-(p[1]+q[1])/2)*camera.focal*camera.zoom
            split=dx*dx+dy*dy>self.tolerance*self.tolerance
        if split and depth<5:
            for pair in self._arc(camera,curve,start,middle,p,m,depth+1):yield pair
            for pair in self._arc(camera,curve,middle,end,m,q,depth+1):yield pair
        elif p is not None and q is not None:yield p,q

    def _curve(self,camera,curve,start=0.0,end=2*pi):
        span=end-start;origin=start;count=max(1,int(span/(pi/4)+.99999));p=camera.ratio(curve_point(curve,start))
        for n in range(1,count+1):
            end=origin+span*n/count;q=camera.ratio(curve_point(curve,end))
            for pair in self._arc(camera,curve,start,end,p,q,0):yield pair
            start,p=end,q

    def _surface(self,camera,s,windows=None):
        kind=s[0];center=tuple(s[1:4]);u,v,w=tuple(s[4:7]),tuple(s[7:10]),tuple(s[10:13]);r,h=s[13:15]
        view=(camera.sy*camera.cp,camera.cy*camera.cp,camera.sp)
        parallel=camera.projection=='Isometric'
        eye=mul(view,camera.cam);toward=view if parallel else sub(eye,center)
        if kind==0:
            distance=sqrt(dot(toward,toward))
            if distance<=r and not parallel:return
            n=mul(toward,1/distance)
            if parallel:cc,rr=center,r
            else:cc,rr=add(center,mul(n,r*r/distance)),r*sqrt(max(0,1-r*r/(distance*distance)))
            ref=(0,0,1) if abs(n[2])<.9 else (0,1,0)
            uu=cross(n,ref);uu=mul(uu,1/sqrt(dot(uu,uu)));vv=cross(n,uu)
            curve=cc+uu+vv+(rr,)
            for pair in self._curve(camera,curve):yield pair
            return
        a,b=dot(toward,u),dot(toward,v);distance=sqrt(a*a+b*b)
        if distance<1e-9:return
        # Cylinder: n dot (eye - surface) = 0. Cone's tangent plane passes
        # through its apex. Orthographic directions remove the eye offset.
        target=0.0 if parallel else r
        if kind==2:
            apex=add(center,mul(w,h/2))
            target=-(r/h)*dot(w,view if parallel else sub(eye,apex))
        if abs(target)>distance:return
        phi=atan2(b,a);angle=acos(max(-1,min(1,target/distance)))
        for theta in (phi-angle,phi+angle):
            if windows is not None and not any(lo+1e-6<theta%(2*pi)<hi-1e-6 for lo,hi in windows):continue
            radial=add(mul(u,r*cos(theta)),mul(v,r*sin(theta)));base=add(center,radial)
            if kind==2:p,q=add(base,mul(w,-h/2)),add(center,mul(w,h/2))
            else:
                n1,d1=tuple(s[15:18]),s[18];n2,d2=tuple(s[19:22]),s[22]
                p=add(base,mul(w,(d1-dot(n1,base))/dot(n1,w)))
                q=add(base,mul(w,(d2-dot(n2,base))/dot(n2,w)))
            a2,b2=camera.ratio(p),camera.ratio(q)
            if a2 is not None and b2 is not None:yield a2,b2

    def projected(self,camera):
        for i in range(0,len(self.lines),6):
            p=camera.ratio(tuple(self.lines[i:i+3]));q=camera.ratio(tuple(self.lines[i+3:i+6]))
            if p is not None and q is not None:yield p,q
        for i in range(0,len(self.circles),10):
            for pair in self._curve(camera,self.circles[i:i+10]):yield pair
        for i in range(0,len(self.arcs),12):
            for pair in self._curve(camera,self.arcs[i:i+10],self.arcs[i+10],self.arcs[i+11]):yield pair
        for i in range(0,len(self.surfaces),23):
            windows=[(self.spans[j+1],self.spans[j+2]) for j in range(0,len(self.spans),3) if int(self.spans[j])==i//23]
            for pair in self._surface(camera,self.surfaces[i:i+23],windows if windows else None):yield pair


class Build:
    def __init__(self,model):
        dm.validate(model);self.model=dm.clone(model)
        # Compute topology around a local origin, keeping small features
        # independent of large world translations as far as float32 allows.
        self.origin=position(model['features'][0]) if model['features'] else (0,0,0)
        self.work=dm.clone(model)
        for f in self.work['features']:
            for i,k in enumerate(('x','y','z')):f[k]-=self.origin[i]
            f.pop('_cad_axes',None);f['_cad_axes']=axes(f)
        bounds=dm.bounds(self.work)
        self.relative_center=tuple((bounds[2*i]+bounds[2*i+1])/2 for i in range(3))
        self.center=add(self.relative_center,self.origin)
        self.scale=max((bounds[2*i+1]-bounds[2*i])/2 for i in range(3))
        self.bounds=tuple(bounds[i]+self.origin[i//2] for i in range(6))
        self.geometry=None;self.done=False;self.status='empty';self.body_count=0
        self.progress=('Checking geometry',0,max(1,len(model['features'])))

    def normal(self,p):return mul(sub(p,self.relative_center),1/self.scale)

    def surface(self,result,kind,f,planes=None):
        u,v,w=axes(f);center=self.normal(position(f));r=f['a']/self.scale;h=0.0 if kind==0 else f['c']/self.scale
        if kind==0:planes=[(w,0.0),(w,0.0)]
        if planes is None:
            ends=[add(position(f),mul(w,sign*f['c']/2)) for sign in (-1,1)]
            planes=[(w,dot(w,self.normal(p))) for p in ends]
        result.surfaces.extend((kind,)+center+u+v+w+(r,h)+planes[0][0]+(planes[0][1],)+planes[1][0]+(planes[1][1],))

    def feature(self,result,f,cutters=()):
        shape=f['shape'];u,v,w=axes(f)
        if shape=='Box':
            vertices=[dm.world(f,(x*f['a']/2,y*f['b']/2,z*f['c']/2)) for z in (-1,1) for y in (-1,1) for x in (-1,1)]
            for i in range(8):
                for bit in (1,2,4):
                    if not i&bit:
                        pieces=cut_segment(vertices[i],vertices[i|bit],cutters,1e-6) if cutters else [(vertices[i],vertices[i|bit])]
                        for a,b in pieces:result.lines.extend(self.normal(a));result.lines.extend(self.normal(b))
                        yield None
        elif shape=='Sphere':self.surface(result,0,f);yield None
        else:
            for sign in ((-1,1) if shape=='Cylinder' else (-1,)):
                result.curve(self.normal(add(position(f),mul(w,sign*f['c']/2))),u,v,f['a']/self.scale);yield None
            self.surface(result,1 if shape=='Cylinder' else 2,f);yield None

    def job(self):
        try:
            for step in self._job():yield step
        except Issue:raise
        except (ValueError,ZeroDivisionError,OverflowError) as exc:
            raise Issue('calculation','Boundary calculation failed')

    def _job(self):
        parts=[]
        for index,(parts,status) in enumerate(plan(self.work)):
            self.status=status;self.progress=('Checking operations',index+1,len(self.work['features']));yield None
        self.body_count=len(parts)
        if not parts:self.status='empty'
        result=Boundaries(4.0/self.model['resolution'])
        for index,part in enumerate(parts):
            for _ in self.feature(result,part['base'],[x[0] for x in part.get('notches',())]):yield None
            for f in part['voids']:
                for _ in self.feature(result,f):yield None
            for f,rims in part['bores']:
                planes=[]
                for center,u,v,n,d in rims:
                    result.curve(self.normal(center),u,v,f['a']/self.scale)
                    planes.append((n,dot(n,self.normal(center))));yield None
                self.surface(result,1,f,planes);yield None
            for f,notch in part.get('notches',()):
                low,high=notch['centers'];u,v,n=notch['u'],notch['v'],notch['n'];r=f['a']
                for lo,hi in notch['windows']:
                    for center in (low,high):result.arc(self.normal(center),u,v,r/self.scale,lo,hi)
                # Only true face intersections become vertical edges. A curve
                # split at angle zero is just a parameter seam.
                for angle in notch['joins']:
                    radial=add(mul(u,r*cos(angle)),mul(v,r*sin(angle)))
                    result.lines.extend(self.normal(add(low,radial)))
                    result.lines.extend(self.normal(add(high,radial)))
                surface_index=len(result.surfaces)//23
                planes=[(n,dot(n,self.normal(p))) for p in (low,high)]
                self.surface(result,1,f,planes)
                for lo,hi in notch['windows']:result.spans.extend((surface_index,lo,hi))
                yield None
            self.progress=('Direct boundaries',index+1,len(parts))
        if not all(isfinite(value) for data in (result.lines,result.circles,result.surfaces,result.arcs,result.spans) for value in data):raise Issue('calculation','Non-finite boundary coordinates')
        result.status=self.status;result.body_count=self.body_count
        self.geometry=result;self.done=True

    def release(self):self.geometry=None;self.work=None
