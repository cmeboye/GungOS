"""Analytic primitive silhouettes, exact-case CSG and typed geometry diagnostics."""
import os,sys
from math import sqrt,sin,cos,pi
root=os.getcwd();sys.path.insert(0,root+'/builds/MicroPython/apps_unfrozen')
from engtools.picocad import model as dm
from engtools.picocad.geometry import Build,curve_point
from engtools.picocad.solid import support,axes,position,dot,sub,add,mul,bore
from engtools.picocad.issues import Issue
# Camera/Viewport only need existing simulator draw bindings.
sys.path.insert(0,root+'/src/MicroPython');sys.path.insert(0,root+'/simulator/hardware')
import sim_runtime
sim_runtime.configure(root,'/private/tmp/gungos-picocad-kernel',root+'/builds/MicroPython/apps_unfrozen',1,'picocalc-pico2w',0,True,False,False,False,'',_network_mode='offline',_audio_mode='silent',_sd_profile='clean')
from engtools.picocad.draw import Camera


def close(a,b,tol=3e-5):assert abs(a-b)<=tol*max(1,abs(a),abs(b)),(a,b)
def build(features):
    model=dm.blank();model['features']=features
    b=Build(model)
    for _ in b.job():pass
    assert b.done and b.geometry is not None
    return b

def issue(features,kind):
    try:build(features)
    except Issue as exc:assert exc.kind==kind,(exc.kind,str(exc));return exc
    raise AssertionError('Expected '+kind)

# Four real primitive outlines, rigid transforms and both camera projections.
for shape in dm.SHAPES:
    f=dm.primitive(shape);f.update(x=23,y=-14,z=9,rx=27,ry=-31,rz=42)
    b=build([f]);g=b.geometry
    assert b.status=='success' and b.body_count==1
    for projection in ('Perspective','Isometric'):
        camera=Camera();camera.projection=projection;camera.fit(b.bounds,(12,64,296,135),g)
        lines=list(g.projected(camera));assert lines and len(lines)<300,(shape,projection,len(lines))
        # Fit keeps complete outlines inside the viewport, excluding its margin.
        for a,c in lines:
            for p in (a,c):
                x=camera.cx+p[0]*camera.focal;y=camera.cy_screen+p[1]*camera.focal
                assert 11<=x<=309 and 63<=y<=200,(shape,projection,x,y)
        if shape=='Sphere':
            s=g.surfaces;center=tuple(s[1:4]);r=s[13]
            # Points recovered from the projected outline lie on both the
            # sphere and tangent plane. Check independent 3D curve geometry.
            view=(camera.sy*camera.cp,camera.cy*camera.cp,camera.sp)
            eye=mul(view,camera.cam)
            toward=view if projection=='Isometric' else sub(eye,center)
            d=sqrt(dot(toward,toward));normal=mul(toward,1/d)
            cc=center if projection=='Isometric' else add(center,mul(normal,r*r/d))
            rr=r if projection=='Isometric' else r*sqrt(1-r*r/(d*d))
            # Orthogonal tangent circle points on the sphere satisfy n.P=r^2/d.
            ref=(normal[1],-normal[0],0)
            ref=mul(ref,rr/sqrt(dot(ref,ref)))
            point=add(cc,ref);delta=sub(point,center)
            close(dot(delta,delta),r*r)
            close(dot(delta,view) if projection=='Isometric' else dot(delta,sub(eye,point)),0)

# Independent ray/quadric tangency checks use actual rendered endpoints,
# without reconstructing the renderer's chosen circle or tangent angles.
for shape in ('Sphere','Cylinder','Cone'):
    f=dm.primitive(shape);f.update(rx=27,ry=-31,rz=42)
    b=build([f]);g=b.geometry;s=g.surfaces;center=tuple(s[1:4]);r=s[13];h=s[14]
    u,v,w=tuple(s[4:7]),tuple(s[7:10]),tuple(s[10:13])
    for projection in ('Perspective','Isometric'):
        camera=Camera();camera.projection=projection;camera.fit(b.bounds,(12,64,296,135),g)
        view=(camera.sy*camera.cp,camera.cy*camera.cp,camera.sp)
        right=(camera.cy,-camera.sy,0)
        up=(-camera.sy*camera.sp,-camera.cy*camera.sp,camera.cp)
        pairs=list(g.projected(camera));pairs=pairs if shape=='Sphere' else pairs[-2:]
        for pair in pairs:
            for q in pair:
                if projection=='Perspective':origin=mul(view,camera.cam);direction=sub(add(mul(right,q[0]),mul(up,-q[1])),view)
                else:origin=add(mul(right,q[0]*camera.cam),mul(up,-q[1]*camera.cam));direction=mul(view,-1)
                origin=sub(origin,center)
                if shape=='Sphere':
                    distance2=dot(origin,origin)-dot(origin,direction)**2/dot(direction,direction)
                    close(distance2,r*r,1e-4)
                else:
                    x,y,z=dot(origin,u),dot(origin,v),dot(origin,w)
                    dx,dy,dz=dot(direction,u),dot(direction,v),dot(direction,w)
                    if shape=='Cylinder':a=dx*dx+dy*dy;bb=2*(x*dx+y*dy);c0=x*x+y*y-r*r
                    else:
                        z-=h/2;k=r/h
                        a=dx*dx+dy*dy-k*k*dz*dz;bb=2*(x*dx+y*dy-k*k*z*dz);c0=x*x+y*y-k*k*z*z
                    close(bb*bb,4*a*c0,1e-4)
# Input files cannot override the kernel's private compiled transform cache.
metadata=dm.primitive();metadata['_cad_axes']=[[0,0,0]]
assert build([metadata]).status=='success'

# Support functions agree with independently parameterised surface extrema.
for shape in dm.SHAPES:
    f=dm.primitive(shape);f.update(rx=21,ry=-35,rz=17)
    for n in ((1,0,0),(0,1,0),(0,0,1),(.3,-.7,.2)):
        value=support(f,n);assert value>0
        if shape=='Box':
            points=[dm.world(f,(x*f['a']/2,y*f['b']/2,z*f['c']/2)) for x in (-1,1) for y in (-1,1) for z in (-1,1)]
            close(max(dot(p,n) for p in points),value)
        elif shape=='Sphere':close(value,f['a']*sqrt(dot(n,n)))
        else:
            points=[]
            for i in range(720):
                t=i*pi/360
                for z in (-f['c']/2,f['c']/2):
                    radius=f['a'] if shape=='Cylinder' or z<0 else 0
                    points.append(dm.world(f,(radius*cos(t),radius*sin(t),z)))
            close(max(dot(p,n) for p in points),value,1e-4)

box=dm.primitive();cutter=dm.primitive('Cylinder','Cut',2)
for axis in ('x','y','z'):
    f=dict(cutter);f.update(c=60,a=2)
    if axis=='x':f['ry']=90
    elif axis=='y':f['rx']=90
    b=build([box,f]);assert len(b.geometry.circles)==20 and len(b.geometry.surfaces)==23
# Tilted long drilling: all sampled verification points lie exactly on the
# analytic cylinder and one of the box faces. Samples only test the curves.
tilt=dict(cutter);tilt.update(rx=18,ry=23,c=60,a=3)
b=build([box,tilt]);g=b.geometry
for i in (0,10):
    for j in range(40):
        point=curve_point(g.circles[i:i+10],j*pi/20)
        world=add(b.center,mul(point,b.scale));local=dm.local(tilt,world)
        close(local[0]*local[0]+local[1]*local[1],9)
        assert min(abs(abs(world[k])-dm.half_size(box)[k]) for k in range(3))<1e-4
# Blind drilling enters the top face and ends internally at z=0.
blind=dict(cutter);blind.update(z=6,c=12)
b=build([box,blind]);close(b.geometry.circles[2]*b.scale,0);close(b.geometry.circles[12]*b.scale,5)
# Enclosed cavities can be any primitive and remain a single body.
for shape in dm.SHAPES:
    cavity=dm.primitive(shape,'Cut',2);cavity.update(a=2,b=2,c=2,rx=12,ry=18)
    b=build([box,cavity]);assert b.body_count==1 and b.status=='success'
# Non-overlapping bores and a separate interior cavity coexist.
a=dict(cutter);a.update(x=-10,a=2)
c=dict(cutter);c.update(x=10,a=2)
void=dm.primitive('Sphere','Cut',4);void['a']=1
b=build([box,a,c,void]);assert b.body_count==1

# Valid no-op, empty, containment and disconnected-body outcomes.
far=dm.primitive('Sphere','Cut',2);far['x']=100
assert build([box,far]).status=='no_change'
far['op']='Intersect';b=build([box,far]);assert b.status=='empty' and not len(b.geometry)
assert build([]).status=='empty'
far['op']='Add';b=build([box,far]);assert b.status=='multiple' and b.body_count==2
cover=dm.primitive('Box','Cut',2);cover.update(a=100,b=100,c=100)
assert build([box,cover]).status=='empty'
cover['op']='Intersect';assert build([box,cover]).status=='no_change'
inside=dm.primitive('Sphere','Intersect',2);inside['a']=2
b=build([box,inside]);assert b.status=='success' and len(b.geometry.lines)==0
same=dict(box);same['op']='Cut';assert build([box,same]).status=='empty'
same['op']='Add';assert build([box,same]).status=='no_change'
# Re-adding a solid fills its previous cavity, rather than retaining a hole.
void=dm.primitive('Sphere','Cut',2);void['a']=2
b=build([box,void,dict(box)]);assert len(b.geometry.surfaces)==0
# Aligned boxes: intersection, rectangular union and split-through slab cut.
other=dm.primitive('Box','Intersect',2);other.update(x=15,a=20,b=20,c=8)
b=build([box,other]);xs=[b.geometry.lines[i]*b.scale+b.center[0] for i in range(0,len(b.geometry.lines),3)]
close(min(xs),5);close(max(xs),20)
other=dm.primitive('Box','Add',2);other['x']=30
b=build([box,other]);assert b.body_count==1 and len(b.geometry.lines)==72
slab=dm.primitive('Box','Cut',2);slab.update(a=4,b=40,c=20)
b=build([box,slab]);assert b.status=='multiple' and b.body_count==2
# A common rotated frame works equally well for box intersections.
base=dict(box);base.update(x=10,y=-4,z=3,rx=12,ry=23,rz=34)
other=dict(base);other.update(op='Intersect',a=20,b=20,c=8)
p=dm.world(base,(15,0,0))
for k,v in zip(('x','y','z'),p):other[k]=v
assert build([base,other]).status=='success'

# A sphere's unused box/depth fields do not become fake geometry errors.
s=dm.primitive('Sphere');s.update(b=-1,c=0)
assert build([s]).status=='success'
# Several valid slab cuts can exceed our body capacity without becoming an
# invalid mathematical solid. The result must report the application limit.
steps=[box]
for x in (-7,7):
    tool=dm.primitive('Box','Cut');tool.update(a=2,b=100,c=100,x=x);steps.append(tool)
for y in (-5,5):
    tool=dm.primitive('Box','Cut');tool.update(a=100,b=2,c=100,y=y);steps.append(tool)
tool=dm.primitive('Box','Cut');tool.update(a=100,b=100,c=1);steps.append(tool)
issue(steps,'limit')
# Independent point-membership checks compare supported box operations with
# their original Boolean expressions, without using the planner's predicates.
from engtools.picocad.solid import plan

def inside(f,p):
    x,y,z=dm.local(f,p);shape=f['shape']
    if shape=='Box':return abs(x)<f['a']/2 and abs(y)<f['b']/2 and abs(z)<f['c']/2
    if shape=='Sphere':return x*x+y*y+z*z<f['a']*f['a']
    radius=f['a'] if shape=='Cylinder' else f['a']*(.5-z/f['c'])
    return abs(z)<f['c']/2 and x*x+y*y<radius*radius
for operation in dm.OPERATIONS:
    tool=dm.primitive('Box',operation,2);tool.update(a=4,b=40,c=20)
    if operation=='Add':tool.update(a=40,b=30,c=10,x=30)
    model=dm.blank();model['features']=[box,tool]
    parts,status=list(plan(model))[-1]
    for ix in range(13):
        for iy in range(5):
            for iz in range(4):
                p=(-23.17+ix*6.13,-18.11+iy*8.13,-7.23+iz*4.19)
                a,b=inside(box,p),inside(tool,p)
                expected=(a or b) if operation=='Add' else (a and not b) if operation=='Cut' else (a and b)
                actual=any(inside(part['base'],p) and not any(inside(v,p) for v in part['voids']) for part in parts)
                assert actual==expected,(operation,p)

# Typed errors describe the actual reason and preserve original inputs.
wrong=dict(box);wrong['a']=0;issue([wrong],'invalid')
wrong=dict(box);wrong['a']=float('nan');issue([wrong],'invalid')
wrong=dict(box);wrong['a']=.001;issue([wrong],'limit')
partial=dm.primitive('Sphere','Cut',2);partial.update(a=8,x=19)
assert issue([box,partial],'unsupported').step==2
sphere=dm.primitive('Sphere');touch=dm.primitive('Sphere','Add',2);touch['x']=10
issue([sphere,touch],'non_manifold')
touch['x']=10.00001;issue([sphere,touch],'precision')
near=dict(cutter);near['x']=15-1e-5;issue([box,near],'precision')
touch=dict(cutter);touch['x']=15;issue([box,touch],'non_manifold')
edge=dm.primitive('Box','Add',2);edge.update(x=40,y=30)
issue([box,edge],'non_manifold')
print('PASS: four direct primitives, two projections, analytic support/extrema, XYZ/angled/blind bores, cavities, multiple bodies, containment, box CSG and typed diagnostics')

# Repeated subtraction of the same bore is a genuine no-op, not unsupported.
assert build([box,cutter,dict(cutter)]).status=='no_change'
# Boundary arithmetic failures are classified separately from input errors.
fault=Build(dm.example())
def broken():
    yield None
    raise ZeroDivisionError('simulated arithmetic failure')
fault._job=broken
try:
    for _ in fault.job():pass
except Issue as exc:assert exc.kind=='calculation'
else:raise AssertionError('Arithmetic fault escaped classification')

# The user's exact valid half-cylinder side cut, plus non-half notch arcs.
side_cut=dm.primitive('Cylinder','Cut',2);side_cut.update(a=5,c=16,x=0,y=15,z=0)
notch_build=build([box,side_cut]);notch=notch_build.geometry
assert notch_build.status=='success' and notch_build.body_count==1
assert len(notch.lines)==16*6 and not len(notch.circles)
assert len(notch.arcs)==2*12 and len(notch.surfaces)==23
for offset in range(0,len(notch.arcs),12):
    close(notch.arcs[offset+11]-notch.arcs[offset+10],pi)
    for j in range(41):
        angle=notch.arcs[offset+10]+(notch.arcs[offset+11]-notch.arcs[offset+10])*j/40
        p=add(notch_build.center,mul(curve_point(notch.arcs[offset:offset+10],angle),notch_build.scale))
        close(p[0]*p[0]+(p[1]-15)**2,25)
        close(abs(p[2]),5)
        assert 10-1e-4<=p[1]<=15+1e-4
# No surviving box edge may cross the removed cylindrical interior. The two
# new vertical edges meet the side face at x=-5 and +5, y=15.
for i in range(0,len(notch.lines),6):
    a=add(notch_build.center,mul(tuple(notch.lines[i:i+3]),notch_build.scale))
    b=add(notch_build.center,mul(tuple(notch.lines[i+3:i+6]),notch_build.scale))
    for j in range(9):
        p=add(a,mul(sub(b,a),j/8))
        assert p[0]*p[0]+(p[1]-15)**2>=25-1e-3,(a,b,p)
for i in (len(notch.lines)-12,len(notch.lines)-6):
    p=add(notch_build.center,mul(tuple(notch.lines[i:i+3]),notch_build.scale))
    close(abs(p[0]),5);close(p[1],15)
# Partial circle intervals crossing angle zero must not create a fake seam.
shallow=dict(side_cut);shallow['y']=12
b=build([box,shallow]);assert len(b.geometry.arcs)==4*12 and len(b.geometry.lines)==16*6
for i in (len(b.geometry.lines)-12,len(b.geometry.lines)-6):
    p=add(b.center,mul(tuple(b.geometry.lines[i:i+3]),b.scale))
    close(abs(p[0]),4);close(p[1],15)
# Remaining-side arcs and cutout seams also work on mirrored faces and each
# local drilling axis, including a rigidly rotated/translated whole part.
for drill,side in ((0,1),(1,0),(2,1)):
    for sign in (-1,1):
        f=dict(side_cut);f.update(a=2,c=80,x=0,y=0,z=0,rx=0,ry=0)
        if drill==0:f['ry']=90
        elif drill==1:f['rx']=90
        f[('x','y','z')[side]]=sign*dm.half_size(box)[side]
        nb=build([box,f]);assert nb.status=='success' and len(nb.geometry.arcs)>=24
rotbox=dict(box);rotbox.update(x=12,y=-8,z=4,rx=23,ry=-31,rz=42)
rotcut=dict(side_cut);rotcut.update(rx=23,ry=-31,rz=42)
p=dm.world(rotbox,(0,15,0))
for key,value in zip(('x','y','z'),p):rotcut[key]=value
nb=build([rotbox,rotcut]);assert len(nb.geometry.lines)==16*6
for i in range(0,len(nb.geometry.arcs),12):
    for j in range(17):
        arc=nb.geometry.arcs[i:i+12];p=curve_point(arc[:10],arc[10]+(arc[11]-arc[10])*j/16)
        p=dm.local(rotbox,add(nb.center,mul(p,nb.scale)))
        close(p[0]*p[0]+(p[1]-15)**2,25);assert p[1]<=15+1e-4
# Surface silhouette rays may only hit the retained semicylinder, in either
# projection. Reconstruct their endpoints from the cap plane independently.
g=notch;surface=g.surfaces
for projection in ('Perspective','Isometric'):
    cam=Camera();cam.projection=projection;cam.fit(notch_build.bounds,(12,64,296,135),g)
    view=(cam.sy*cam.cp,cam.cy*cam.cp,cam.sp);right=(cam.cy,-cam.sy,0);up=(-cam.sy*cam.sp,-cam.cy*cam.sp,cam.cp)
    pairs=list(g._surface(cam,surface,[(g.spans[i+1],g.spans[i+2]) for i in range(0,len(g.spans),3)]))
    for pair in pairs:
        for end,q in enumerate(pair):
            if projection=='Perspective':origin=mul(view,cam.cam);direction=sub(add(mul(right,q[0]),mul(up,-q[1])),view)
            else:origin=add(mul(right,q[0]*cam.cam),mul(up,-q[1]*cam.cam));direction=mul(view,-1)
            n=tuple(surface[15:18]) if end==0 else tuple(surface[19:22]);d=surface[18] if end==0 else surface[22]
            p=add(origin,mul(direction,(d-dot(n,origin))/dot(n,direction)))
            p=add(notch_build.center,mul(p,notch_build.scale))
            assert p[1]<=15+1e-4;close(p[0]*p[0]+(p[1]-15)**2,25)
# Existing interior bores, enclosed cavities and disjoint side notches coexist.
inner=dict(cutter);inner['a']=2
combined=build([box,inner,side_cut]);assert len(combined.geometry.surfaces)==46 and len(combined.geometry.circles)==20
assert build([box,side_cut,dict(side_cut)]).status=='no_change'
assert len(build([box,side_cut,dict(box)]).geometry.arcs)==0
opposite=dict(side_cut);opposite['y']=-15
assert len(build([box,side_cut,opposite]).geometry.arcs)==48
blindside=dict(side_cut);blindside['c']=8
issue([box,blindside],'unsupported')
corner=dict(side_cut);corner['x']=18
issue([box,corner],'unsupported')
print('PASS: exact user side cut, trimmed arcs and straight edges, no parameter seams, mirrored/XYZ/rigid transforms, clipped silhouettes and disjoint cut combinations')

# Exercise the real view's status/error recovery and capture all primitive
# previews plus useful test projects in the simulator's private SD only.
from picoware.system.view_manager import ViewManager
from picoware.system.view import View
from picoware.system.input import Input
from engtools.picocad import app
Input.button=property(lambda self:self._last_button)
vm=ViewManager();vm._wifi=None;vm.selected_color=0x07E0
vm.add(View('parent',lambda v:None,lambda v:True,lambda v:None));vm.switch_to('parent')
app.show(vm);c=app._active
out='/private/tmp/gungos-picocad-kernel-previews';sim_runtime.mkdir_p(out)
def finish():
    for _ in range(3000):
        if c.job is None:return
        c.pump()
    raise AssertionError('UI build did not finish')
def show(name,features,status):
    model=dm.blank();model['features']=features;c.transact(model,0);c.tab=0;c.build();finish()
    assert c.result_kind==status,(name,c.result_kind,c.message)
    c.draw();sim_runtime.lcd_screenshot(out+'/'+name+'.bmp')
    return model
finish()
for shape in dm.SHAPES:
    f=dm.primitive(shape);f.update(rx=27,ry=-31,rz=42)
    show(shape.lower(),[f],'success')
show('side-notch',[box,side_cut],'success')
show('angled-bore',[box,tilt],'success')
show('blind-bore',[box,blind],'success')
show('split',[box,slab],'multiple')
far=dm.primitive('Sphere','Cut',2);far['x']=100
show('no-change',[box,far],'no_change');assert not c.error
far=dict(far);far['op']='Intersect'
show('empty',[box,far],'empty');assert not c.error and c.show_built and not len(c.geometry)
old=c.geometry
show('unsupported',[box,partial],'unsupported');assert c.error and c.geometry is old and not c.show_built
show('precision',[box,near],'precision');assert c.error and c.model['features'][1]==near
show('point-contact',[sphere,dict(sphere,op='Add',x=10)],'non_manifold')
# Recovery after every failed build retains view and editable model.
show('recovered',[box,cutter],'success');assert not c.error and vm.current_view.name=='picocad_view'
app._active.discard=True;vm.back();assert app._active is None
print('PASS: typed UI outcomes, successful empty/no-op, failed-build recovery and all primitive/operation preview captures')
print('Screenshots: '+out)
