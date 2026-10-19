"""Small exact-case CSG planner. Uses analytic supports, never volume sampling.

Each component is a convex primitive with disjoint enclosed voids or bores.
Partial intersections outside the explicitly supported cases are diagnosed,
not approximated. This is not a general boundary-representation kernel.
"""
from math import sqrt
from . import model as dm
from .issues import Issue


def dot(a,b):return sum(a[i]*b[i] for i in range(3))
def sub(a,b):return tuple(a[i]-b[i] for i in range(3))
def add(a,b):return tuple(a[i]+b[i] for i in range(3))
def mul(a,s):return tuple(x*s for x in a)
def cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def position(f):return tuple(f[k] for k in ('x','y','z'))
def axes(f):
    cached=f.get('_cad_axes')
    if cached is not None:return cached
    m=dm.matrix(f);return tuple(tuple(m[j][i] for j in range(3)) for i in range(3))


def support(f,n):
    """Exact max(n dot (point-centre)) for each primitive; n need not be unit."""
    shape=f['shape']
    if shape=='Sphere':return f['a']*sqrt(dot(n,n))
    u,v,w=axes(f);x,y,z=dot(n,u),dot(n,v),dot(n,w)
    if shape=='Box':return abs(x)*f['a']/2+abs(y)*f['b']/2+abs(z)*f['c']/2
    radial=f['a']*sqrt(x*x+y*y)
    if shape=='Cylinder':return radial+abs(z)*f['c']/2
    return max(radial-z*f['c']/2,z*f['c']/2)


def interval(f,n):
    centre=dot(position(f),n)
    return centre-support(f,mul(n,-1)),centre+support(f,n)


def same(a,b):
    if a['shape']!=b['shape'] or position(a)!=position(b):return False
    if a['a']!=b['a']:return False
    if a['shape']=='Sphere':return True
    if a['c']!=b['c'] or (a['shape']=='Box' and a['b']!=b['b']):return False
    return all(a[k]==b[k] for k in ('rx','ry','rz'))


def margin(f,p):
    """Signed inside clearance; conservative near a cone's side/cap junction."""
    x,y,z=dm.local(f,p);shape=f['shape']
    if shape=='Box':return min(f['a']/2-abs(x),f['b']/2-abs(y),f['c']/2-abs(z))
    if shape=='Sphere':return f['a']-sqrt(x*x+y*y+z*z)
    radial=sqrt(x*x+y*y)
    if shape=='Cylinder':return min(f['a']-radial,f['c']/2-abs(z))
    slope=f['a']/f['c']
    return min((f['a']*(.5-z/f['c'])-radial)/sqrt(1+slope*slope),f['c']/2-abs(z))


def contains(a,b,eps,strict=False):
    if same(a,b):return not strict
    if a['shape']=='Box':
        delta=sub(position(b),position(a));clear=[]
        for i,n in enumerate(axes(a)):
            lo=dot(delta,n)-support(b,mul(n,-1));hi=dot(delta,n)+support(b,n)
            half=(a['a'],a['b'],a['c'])[i]/2
            clear.extend((lo+half,half-hi))
        return min(clear)>eps if strict else min(clear)>=0
    if a['shape']=='Sphere' and b['shape']=='Sphere':
        d=sub(position(a),position(b));clear=a['a']-sqrt(dot(d,d))-b['a']
        return clear>eps if strict else clear>=0
    # Convexity makes containment of an enclosing box a sufficient proof.
    hx,hy,hz=dm.half_size(b)
    clear=min(margin(a,dm.world(b,(x,y,z))) for x in (-hx,hx) for y in (-hy,hy) for z in (-hz,hz))
    return clear>eps if strict else clear>=0


def relation(a,b,eps):
    if same(a,b):return 'equal'
    delta=sub(position(b),position(a))
    if a['shape']==b['shape']=='Sphere':
        distance=sqrt(dot(delta,delta));gap=distance-a['a']-b['a']
        if gap>eps:return 'disjoint'
        if gap==0:return 'point_contact'
        if abs(gap)<=eps:return 'near'
    if contains(a,b,eps):return 'contains'
    if contains(b,a,eps):return 'inside'
    aa,bb=axes(a),axes(b)
    candidates=[delta]+list(aa)+list(bb)+[cross(x,y) for x in aa for y in bb]
    for n in candidates:
        norm=sqrt(dot(n,n))
        if norm<1e-6:continue
        # Work relative to A's origin to avoid loss from distant world origins.
        hi_a=support(a,n);lo_a=-support(a,mul(n,-1))
        centre=dot(delta,n);lo_b=centre-support(b,mul(n,-1));hi_b=centre+support(b,n)
        if max(lo_b-hi_a,lo_a-hi_b)>eps*norm:return 'disjoint'
    return 'overlap'


def aligned_boxes(a,b,operation,eps):
    """Intersection, slab cut and rectangular union in a shared local frame."""
    if a['shape']!=b['shape'] or a['shape']!='Box':return None
    aa,bb=axes(a),axes(b)
    if any(abs(dot(aa[i],bb[j])-(1 if i==j else 0))>2e-6 for i in range(3) for j in range(3)):return None
    centre=dm.local(a,position(b));ha=dm.half_size(a);hb=dm.half_size(b)
    alo=[-x for x in ha];ahi=list(ha)
    blo=[centre[i]-hb[i] for i in range(3)];bhi=[centre[i]+hb[i] for i in range(3)]
    low=[max(alo[i],blo[i]) for i in range(3)];high=[min(ahi[i],bhi[i]) for i in range(3)]
    widths=[high[i]-low[i] for i in range(3)]
    def box(lo,hi):
        f=dict(a);f['a'],f['b'],f['c']=(hi[i]-lo[i] for i in range(3))
        p=dm.world(a,tuple((hi[i]+lo[i])/2 for i in range(3)))
        for key,value in zip(('x','y','z'),p):f[key]=value
        return f
    if any(0<abs(w)<=eps for w in widths):raise Issue('precision','Box contact near tolerance')
    if operation=='Intersect':
        if min(widths)<=0:return []
        if min(widths)<=eps:raise Issue('precision','Intersection thinner than tolerance')
        return [box(low,high)]
    if operation=='Add':
        zeros=sum(w==0 for w in widths)
        if min(widths)>=0 and zeros>=2:raise Issue('non_manifold','Bodies touch at an edge/point')
        for axis in range(3):
            if all(alo[i]==blo[i] and ahi[i]==bhi[i] for i in range(3) if i!=axis) and widths[axis]>=0:
                return [box([min(alo[i],blo[i]) for i in range(3)],[max(ahi[i],bhi[i]) for i in range(3)])]
        return None
    if min(widths)<=0:return [a]
    for axis in range(3):
        if all(blo[i]<=alo[i] and bhi[i]>=ahi[i] for i in range(3) if i!=axis):
            result=[]
            for lo,hi in ((alo[axis],low[axis]),(high[axis],ahi[axis])):
                if hi<=lo:continue
                if hi-lo<=eps:raise Issue('precision','Remaining wall below tolerance')
                left,right=list(alo),list(ahi);left[axis],right[axis]=lo,hi
                result.append(box(left,right))
            return result
    return None


def bore(box,cutter,eps):
    """Analytic circular/elliptic rim loops and clipped cylinder side planes.

Supports all drilling directions whose complete rim loops lie on two opposite
box faces, or on one face and a fully internal cylinder end cap. No curve is
sampled to decide whether the construction is supported.
"""
    if box['shape']!='Box' or cutter['shape']!='Cylinder':return None
    u,v,w=axes(cutter);rotation=axes(box);centre=dm.local(box,position(cutter))
    axis=tuple(dot(n,w) for n in rotation)
    face=max(range(3),key=lambda i:abs(axis[i]));n=rotation[face]
    if axis[face]<0:n=mul(n,-1)
    den=dot(n,w);half=dm.half_size(box)[face];r=cutter['a'];h=cutter['c']/2
    # Coordinates below are relative to the cutter centre. Opposed box planes
    # yield ellipses C+axis*t + r*(u-axis*n.u/den)*cos + ... .
    offset=centre[face]*(1 if axis[face]>0 else -1)
    result=[]
    for sign in (-1,1):
        t=(sign*half-offset)/den
        tu,tv=-dot(n,u)/den,-dot(n,v)/den
        spread=r*sqrt(tu*tu+tv*tv)
        cap=-h if sign<0 else h
        entirely_outside=(cap<t-spread-eps if sign<0 else cap>t+spread+eps)
        entirely_inside=(cap>t+spread+eps if sign<0 else cap<t-spread-eps)
        if entirely_outside:
            ec=add(position(cutter),mul(w,t));eu=add(u,mul(w,tu));ev=add(v,mul(w,tv))
            for i,m in enumerate(rotation):
                if i==face:continue
                cc=dot(sub(ec,position(box)),m);extent=r*sqrt(dot(eu,m)**2+dot(ev,m)**2)
                clearance=dm.half_size(box)[i]-abs(cc)-extent
                if clearance==0:raise Issue('non_manifold','Bore tangent to a side face')
                if abs(clearance)<=eps:raise Issue('precision','Bore rim near a side face')
                if clearance<0:return None
            result.append((ec,eu,ev,n,dot(n,ec)))
        elif entirely_inside:
            ec=add(position(cutter),mul(w,cap))
            if margin(box,ec)<=eps:return None
            for i,m in enumerate(rotation):
                extent=r*sqrt(dot(u,m)**2+dot(v,m)**2)
                if dm.half_size(box)[i]-abs(dm.local(box,ec)[i])-extent<=eps:return None
            result.append((ec,u,v,w,dot(w,ec)))
        else:
            # Exact coaxial coincident caps are well-defined, but a tilted cap
            # crossing a face requires trimmed arcs and additional vertices.
            if spread==0 and cap==t:
                ec=add(position(cutter),mul(w,t));result.append((ec,u,v,w,dot(w,ec)))
            elif abs(cap-t)<=spread+eps:raise Issue('unsupported','Cylinder cap crosses a box face')
            else:return None
    if dot(sub(result[1][0],result[0][0]),w)<=eps:return None
    return result


def tools(part):
    return part['voids']+[x[0] for x in part['bores']]+[x[0] for x in part.get('notches',())]


def plan(model):
    """Yield (parts, status) after each step; all edits stay in the input model."""
    size=max([max(dm.half_size(f))*2 for f in model['features']] or [1])
    eps=1e-5+2e-6*size;parts=[]
    for index,feature in enumerate(model['features']):
        step=index+1;operation=feature['op'];status='success'
        try:
            thin=min(dm.half_size(feature))*2
            if thin<=4*eps:raise Issue('precision','Feature smaller than model tolerance')
            if not parts:
                if operation=='Add':parts=[dict(base=feature,voids=[],bores=[])]
                else:status='no_change'
                yield parts,status;continue
            if operation=='Add':
                relations=[relation(p['base'],feature,eps) for p in parts]
                if all(r=='disjoint' for r in relations):parts.append(dict(base=feature,voids=[],bores=[]));status='multiple'
                elif len(parts)==1:
                    p=parts[0];r=relations[0]
                    if r in ('equal','inside'):
                        status='no_change' if r=='equal' and not p['voids'] and not p['bores'] and not p.get('notches') else 'success'
                        parts=[dict(base=feature,voids=[],bores=[])]
                    elif r=='contains' and not p['voids'] and not p['bores'] and not p.get('notches'):status='no_change'
                    elif r=='point_contact':raise Issue('non_manifold','Solids meet at one point')
                    elif r=='near':raise Issue('precision','Spheres almost tangent')
                    else:
                        merged=aligned_boxes(p['base'],feature,'Add',eps) if not p['voids'] and not p['bores'] and not p.get('notches') else None
                        if merged is None:raise Issue('unsupported','Union needs boundary trimming')
                        parts=[dict(base=f,voids=[],bores=[]) for f in merged]
                else:raise Issue('unsupported','Union overlaps multiple bodies')
            else:
                updated=[];changed=False
                for p in parts:
                    base=p['base'];r=relation(base,feature,eps)
                    if r=='near':raise Issue('precision','Spheres almost tangent')
                    if r in ('disjoint','point_contact'):
                        if operation=='Cut':updated.append(p)
                        else:changed=True
                        continue
                    if r in ('equal','inside'):
                        if operation=='Intersect':updated.append(p)
                        else:changed=True
                        continue
                    if operation=='Intersect' and r=='contains' and all(relation(v,feature,eps)=='disjoint' for v in tools(p)):
                        updated.append(dict(base=feature,voids=[],bores=[]));changed=True;continue
                    if any(contains(v,feature,eps) for v in tools(p)):
                        if operation=='Cut':updated.append(p)
                        else:changed=True
                        continue
                    if any(relation(v,feature,eps)!='disjoint' for v in tools(p)):
                        raise Issue('unsupported','Operation intersects existing void')
                    if operation=='Cut':
                        from .trim import side_notch
                        notch=side_notch(base,feature,eps)
                        if notch is not None:
                            if notch['status']=='no_change':updated.append(p);continue
                            q=dict(p);q['notches']=list(p.get('notches',()))+[(notch['tool'],notch)]
                            updated.append(q);changed=True;continue
                        drilling=bore(base,feature,eps)
                        if drilling is not None:
                            # Prove new bores/voids disjoint using their tools.
                            q=dict(p);q['voids']=list(p['voids']);q['bores']=list(p['bores'])
                            q['bores'].append((feature,drilling));updated.append(q);changed=True;continue
                        if contains(base,feature,eps,True):
                            q=dict(p);q['voids']=p['voids']+[feature];q['bores']=list(p['bores'])
                            updated.append(q);changed=True;continue
                    if not p['voids'] and not p['bores'] and not p.get('notches'):
                        clipped=aligned_boxes(base,feature,operation,eps)
                        if clipped is not None:
                            updated.extend(dict(base=f,voids=[],bores=[]) for f in clipped)
                            changed=changed or not (len(clipped)==1 and same(clipped[0],base));continue
                    raise Issue('unsupported',operation+' needs boundary trimming')
                parts=updated
                if not changed:status='no_change'
            if len(parts)>16:raise Issue('limit','16 result bodies')
            if not parts:status='empty'
            elif len(parts)>1 and status!='no_change':status='multiple'
            yield parts,status
        except Issue as exc:
            if exc.step is None:exc.step=step;raise Issue(exc.kind,exc.detail,step)
            raise
