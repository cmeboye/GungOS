"""Analytic segment and angular trimming for single-side cylindrical notches.

Intersection parameters partition edges/curves into intervals. A midpoint
classifies each interval; no spatial grid or volume samples are involved.
"""
from math import sqrt,atan2,acos,cos,sin,pi
from . import model as dm
from .solid import axes,position,dot,sub,add,mul
from .issues import Issue

TAU=2*pi


def inside_angles(center,u,v,r,box,eps):
    """Exact angle intervals of a planar circle/ellipse inside a box."""
    rotation=axes(box);half=dm.half_size(box);delta=sub(center,position(box))
    roots=[0.0,TAU]
    for i,n in enumerate(rotation):
        a,b=r*dot(n,u),r*dot(n,v);amplitude=sqrt(a*a+b*b)
        if amplitude<=eps:continue
        offset=dot(n,delta);phase=atan2(b,a)
        for sign in (-1,1):
            value=(sign*half[i]-offset)/amplitude
            if -1<value<1:
                angle=acos(value)
                for t in ((phase-angle)%TAU,(phase+angle)%TAU):
                    if 1e-6<t<TAU-1e-6:roots.append(t)
    roots.sort();unique=[]
    for value in roots:
        if not unique or value-unique[-1]>1e-6:unique.append(value)
    kept=[]
    for lo,hi in zip(unique,unique[1:]):
        theta=(lo+hi)/2;p=add(delta,add(mul(u,r*cos(theta)),mul(v,r*sin(theta))))
        if all(abs(dot(n,p))<=half[i]+eps for i,n in enumerate(rotation)):
            if kept and abs(kept[-1][1]-lo)<1e-6:kept[-1]=(kept[-1][0],hi)
            else:kept.append((lo,hi))
    return kept


def side_notch(box,cutter,eps):
    """Recognise a through-cylinder crossing exactly one lateral box face.

The cylinder may be parallel to any local box axis, including reversed axes.
Cuts crossing multiple sides or ending inside a side face need later topology.
"""
    if box['shape']!='Box' or cutter['shape']!='Cylinder':return None
    rotation=axes(box);direction=axes(cutter)[2]
    components=[dot(n,direction) for n in rotation]
    axis=max(range(3),key=lambda i:abs(components[i]))
    if any(abs(components[i])>2e-6 for i in range(3) if i!=axis):return None
    half=dm.half_size(box);c=dm.local(box,position(cutter));r=cutter['a']
    other=[i for i in range(3) if i!=axis]
    # A radial tangent outside the rectangle removes no positive volume.
    distance2=sum(max(0,abs(c[i])-half[i])**2 for i in other)
    if distance2>=r*r:return dict(status='no_change')
    crossings=[]
    for i in other:
        for sign in (-1,1):
            if c[i]-r<sign*half[i]<c[i]+r:crossings.append((i,sign))
    if len(crossings)>1:raise Issue('unsupported','Notch crosses multiple box sides')
    if len(crossings)!=1:return None
    face,sign=crossings[0]
    remaining=next(i for i in other if i!=face)
    clearance=min(half[remaining]-abs(c[remaining])-r,sign*(c[face]-sign*half[face])+2*half[face]-r)
    if abs(clearance)<=eps:raise Issue('precision','Notch near another side/corner')
    if clearance<0:return None
    overlap=r-abs(c[face]-sign*half[face])
    if overlap<=eps:raise Issue('precision','Notch depth near tolerance')
    if cutter['c']/2-abs(c[axis])-half[axis]<=eps:
        raise Issue('unsupported','Side notch needs a through cutter')
    # Canonicalise axial spin (irrelevant to a cylinder) and right-angle
    # floating-point roundoff into the box's shared local frame.
    a,b=(axis+1)%3,(axis+2)%3;sgn=1 if components[axis]>0 else -1
    u,v,w=rotation[a],mul(rotation[b],sgn),mul(rotation[axis],sgn)
    tool=dict(cutter);tool['_cad_axes']=(u,v,w)
    n=mul(rotation[axis],sgn);offset=c[axis]*sgn
    centers=[add(position(cutter),mul(w,sign*half[axis]-offset)) for sign in (-1,1)]
    windows=inside_angles(centers[0],u,v,r,box,eps)
    if not windows:raise Issue('calculation','Notch lost its boundary arcs')
    face_normal=rotation[face];aa=r*dot(face_normal,u);bb=r*dot(face_normal,v)
    phase=atan2(bb,aa);angle=acos(max(-1,min(1,(sign*half[face]-c[face])/sqrt(aa*aa+bb*bb))))
    joins=((phase-angle)%TAU,(phase+angle)%TAU)
    return dict(status='success',tool=tool,centers=centers,u=u,v=v,n=n,windows=windows,joins=joins)


def cut_segment(a,b,tools,eps):
    """Subtract finite cylindrical interiors using analytic ray intervals."""
    pieces=[(a,b)]
    for f in tools:
        kept=[];u,v,w=axes(f);center=position(f)
        for start,end in pieces:
            p=sub(start,center);d=sub(end,start)
            x,y,z=dot(p,u),dot(p,v),dot(p,w)
            dx,dy,dz=dot(d,u),dot(d,v),dot(d,w)
            radial=dx*dx+dy*dy
            if radial<1e-16:
                if x*x+y*y>=f['a']*f['a']:kept.append((start,end));continue
                lo,hi=0.0,1.0
            else:
                closest=-(x*dx+y*dy)/radial
                px,py=x+closest*dx,y+closest*dy
                gap=f['a']*f['a']-px*px-py*py
                if gap<=0:kept.append((start,end));continue
                spread=sqrt(gap/radial);lo,hi=max(0,closest-spread),min(1,closest+spread)
            if abs(dz)<1e-12:
                if abs(z)>=f['c']/2:kept.append((start,end));continue
            else:
                z1,z2=(-f['c']/2-z)/dz,(f['c']/2-z)/dz
                lo,hi=max(lo,min(z1,z2)),min(hi,max(z1,z2))
            if hi<=lo:kept.append((start,end));continue
            length=sqrt(dot(d,d))
            if lo*length>eps:kept.append((start,add(start,mul(d,lo))))
            if (1-hi)*length>eps:kept.append((add(start,mul(d,hi)),end))
        pieces=kept
    return pieces
