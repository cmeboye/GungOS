"""PicoCAD direct boundaries, graceful unsupported models, files and keyboard UI."""
import os,sys,json
from math import sqrt
from time import ticks_ms
root=os.getcwd()
for path in ('src/MicroPython','simulator/hardware','builds/MicroPython/apps_unfrozen'):
    sys.path.insert(0,root+'/'+path)
import sim_runtime
sd='/private/tmp/gungos-picocad-test-'+str(ticks_ms())
preview='/private/tmp/gungos-picocad-previews'
sim_runtime.configure(root,sd,root+'/builds/MicroPython/apps_unfrozen',1,'picocalc-pico2w',0,True,False,False,False,'',_network_mode='offline',_audio_mode='silent',_sd_profile='clean')
sim_runtime.mkdir_p(preview)
from engtools.picocad import model as dm

def close(a,b,tol=2e-5):assert abs(a-b)<tol*max(1,abs(a),abs(b)),(a,b)

# Local/world transforms preserve all saved primitive types.
for shape in dm.SHAPES:
    feature=dm.primitive(shape);feature.update(x=3.0,y=-7.0,z=2.0,rx=23.0,ry=-34.0,rz=78.0)
    for local in ((0,0,0),(1,2,3),(8,-6,-12)):
        world=dm.world(feature,local)
        for a,b in zip(dm.local(feature,world),local):close(a,b)
body=dm.example()
original=dm.bounds(body);body['features'][1]['a']=1000
assert dm.bounds(body)==original,'A large cutter enlarged the camera framing'
body=dm.example()
for mutate in ('dimension','nonfinite','firstcut','count','quality'):
    candidate=dm.clone(body)
    if mutate=='dimension':candidate['features'][0]['a']=0
    elif mutate=='nonfinite':candidate['features'][0]['x']=float('nan')
    elif mutate=='firstcut':candidate['features'][0]['op']='Cut'
    elif mutate=='count':candidate['features']*=5
    else:candidate['resolution']=999
    try:dm.validate(candidate)
    except ValueError:pass
    else:raise AssertionError(mutate)

# The same saved model now dispatches to direct, unquantized boundaries.
from engtools.picocad import geometry as analytic
from engtools.picocad.geometry import Build as Geometry
from engtools.picocad.draw import Camera

def direct(model):
    result=Geometry(model)
    for _ in result.job():pass
    assert result.done and result.geometry is not None
    return result

result=direct(dm.example());outline=result.geometry
assert len(outline.lines)==12*6 and len(outline.circles)==2*10
assert len(bytes(outline.lines))+len(bytes(outline.circles))==368
assert len(outline.surfaces)==23
for i in (0,10):
    close(outline.circles[i+9]*result.scale,5)
    close(outline.circles[i+2]*result.scale,-5 if i==0 else 5)
    for angle in (0,.3,1.7,3.1):
        point=outline.circle_point(i,angle)
        close(sqrt(point[0]**2+point[1]**2)*result.scale,5)
# Small holes survive N6 because there is no volume sampling.
small=dm.example();small['resolution']=6;small['features'][1]['a']=.01
assert direct(small).geometry.circles[9]>0
# Rotated/translated parts and offset or reversed-axis bores preserve topology.
rotated=dm.example();rotated['features'][0].update(x=12,y=-8,z=4,rx=25,ry=-30,rz=40)
rotated['features'][1].update(rx=25,ry=-30,rz=40)
pos=dm.world(rotated['features'][0],(3,2,0))
for key,value in zip(('x','y','z'),pos):rotated['features'][1][key]=value
rot=direct(rotated);close(rot.geometry.circles[9]*rot.scale,5)
for i in (0,10):
    for angle in (0,.7,2.1,4.9):
        p=rot.geometry.circle_point(i,angle)
        world=tuple(rot.center[j]+rot.scale*p[j] for j in range(3))
        local=dm.local(rotated['features'][0],world)
        close(abs(local[2]),5)
        close(sqrt((local[0]-3)**2+(local[1]-2)**2),5)
reversed=dm.example();reversed['features'][1]['rx']=180
direct(reversed)
multi=dm.example();multi['features'][1].update(x=-8,a=3)
second=dm.primitive('Cylinder','Cut',3);second.update(x=8,a=3)
multi['features'].append(second)
assert len(direct(multi).geometry.circles)==40
assert len(direct(dm.example(False)).geometry.circles)==0
# Complex intersections remain unsupported, distinctly from bad input.
from engtools.picocad.issues import Issue
candidate=dm.example();candidate['features'][1].update(shape='Sphere',a=8,x=19)
try:
    unsupported_build=Geometry(candidate)
    for _ in unsupported_build.job():pass
except Issue as exc:assert exc.kind=='unsupported' and exc.step==2
else:raise AssertionError('Unsupported partial sphere cut was invented')
empty=direct(dm.blank());assert empty.status=='empty' and not len(empty.geometry)
# Cancellation never publishes partial boundary data.
cancel=Geometry(dm.example());job=cancel.job();next(job)
assert cancel.geometry is None and not cancel.done
job.close();cancel.release();assert cancel.geometry is None
# Camera changes retessellate curves, keeping model/circle data untouched.
camera=Camera();camera.fit(result.bounds,(12,64,296,135),geometry=outline)
segments=list(outline.projected(camera));assert 28<=len(segments)<200
original_circle=bytes(outline.circles);camera.zoom=8
zoomed=list(outline.projected(camera));assert len(zoomed)>len(segments)
assert bytes(outline.circles)==original_circle
for yaw,pitch in ((0,0),(0,1.570796),(1.570796,0),(.7,.55)):
    camera.yaw,camera.pitch=yaw,pitch;camera.fit(result.bounds,(12,64,296,135),geometry=outline)
    for a,b in outline.projected(camera):
        assert all(abs(v)<100 for v in a+b)
# Dense samples of the true projected circles stay close to the display
# polyline, independently of the adaptive midpoint subdivision algorithm.
camera.yaw,camera.pitch=.7,.55;camera.fit(result.bounds,(12,64,296,135),geometry=outline)
from math import pi
for zoom in (.2,1,8):
    camera.zoom=zoom;focal=camera.focal*zoom
    curves=list(outline.projected(camera))[12:]
    for index in (0,10):
        for n in range(256):
            p=camera.ratio(outline.circle_point(index,n*pi/128))
            nearest=1e30
            for a,b in curves:
                dx,dy=b[0]-a[0],b[1]-a[1]
                length=dx*dx+dy*dy
                t=max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/length)) if length else 0
                nearest=min(nearest,((p[0]-a[0]-t*dx)**2+(p[1]-a[1]-t*dy)**2)*focal*focal)
            assert nearest<=(outline.tolerance*1.02)**2,(zoom,nearest)
print('PASS: direct box/bore geometry, tiny holes, rigid transforms, multiple bores, unsupported-operation rejection, cancellation and adaptive projected curves')

from picoware.system.view_manager import ViewManager
from picoware.system.settings import Settings
from picoware.system.storage import Storage
from picoware.system.view import View
from picoware.system.input import Input
from picoware.system import buttons as k
from engtools.ui import breadcrumbs
from engtools.picocad import app
Input.button=property(lambda self:self._last_button)
vm=ViewManager();vm._wifi=None;vm.selected_color=0x07E0
vm.add(View('parent',lambda v:None,lambda v:True,lambda v:None));vm.switch_to('parent')
app.show(vm);c=app._active

def key(button):vm.input_manager._last_button=button;vm.run()
def finish():
    for _ in range(2000):
        if c.job is None:return
        key(k.BUTTON_NONE)
    raise AssertionError('Build never finished')
def snap(name):sim_runtime.lcd_screenshot(preview+'/'+name+'.bmp')
def choose(label):
    assert c.popup is not None,(label,c.menu_kind)
    c.menu_index=c.popup.index(label);key(k.BUTTON_CENTER)

def text(value):
    for char in value:key(vm.input_manager._key_to_button(ord(char)))
finish()
assert c.show_built and not c.error and hasattr(c.geometry,'circles')
assert breadcrumbs.current(vm)==('tools','PicoCAD') or breadcrumbs.current(vm) is None
snap('built-example')
assert c.geometry is not None
assert 'Solid + wire' not in app.VIEWS and 'Wireframe' not in app.VIEWS
# F3 contains the requested file/quality/projection options only.
cached=c.geometry;unchanged=dm.clone(c.model);dirty=c.dirty
key(k.BUTTON_F3)
assert c.popup==('Save','Save as','Open','New','Curve Quality','Projection')
snap('options')
choose('Projection');assert c.popup==('Perspective','Isometric') and c.menu_index==0
choose('Isometric')
assert c.camera.projection=='Isometric' and c.geometry is cached and c.job is None
assert c.model==unchanged and c.dirty==dirty
# The default isometric view has equal foreshortening on all world axes.
lengths=[]
for point in ((1,0,0),(0,1,0),(0,0,1)):
    xy=c.camera.ratio(point);lengths.append(xy[0]**2+xy[1]**2)
close(lengths[0],lengths[1]);close(lengths[0],lengths[2])
# Translating along the viewing direction preserves projected positions only
# in parallel mode; perspective makes the same farther object smaller.
direction=(c.camera.sy*c.camera.cp,c.camera.cy*c.camera.cp,c.camera.sp)
a=(.3,-.2,.1);b=tuple(a[i]+direction[i]*.5 for i in range(3))
p1,p2=c.camera.ratio(a),c.camera.ratio(b)
close(p1[0],p2[0]);close(p1[1],p2[1]);snap('isometric')
key(k.BUTTON_F3);choose('Projection');assert c.menu_index==1
choose('Perspective')
p1,p2=c.camera.ratio(a),c.camera.ratio(b)
assert abs(p1[0]-p2[0])+abs(p1[1]-p2[1])>.001
assert c.geometry is cached and c.model==unchanged and c.dirty==dirty
snap('perspective')
# Axis guide draws exactly three labelled world directions, always inside
# the preview, and remains fixed in size/position when the part is panned.
class AxisDraw:
    def __init__(self,draw):
        self.size=draw.size;self.len=draw.len;self.get_font=draw.get_font
        self.lines=[];self.labels=[]
    def _line(self,*args):self.lines.append(args)
    def _text(self,*args):self.labels.append(args)
    def _fill_rectangle(self,*args):pass
from engtools.picocad import draw as cad_draw
from engtools.ui import theme
palette=theme.system_palette(vm);guide=AxisDraw(vm.draw)
cad_draw.axes(guide,c.camera,palette)
assert len(guide.lines)==3 and [label[2] for label in guide.labels]==['X','Y','Z']
for x1,y1,x2,y2,color in guide.lines:
    assert 12<=min(x1,x2)<=max(x1,x2)<308 and 64<=min(y1,y2)<=max(y1,y2)<199
c.camera.zoom=5;c.camera.pan_x=50;c.camera.pan_y=-15
c.camera.setup(dm.bounds(c.model),app.CANVAS)
panned=AxisDraw(vm.draw);cad_draw.axes(panned,c.camera,palette)
assert panned.lines==guide.lines
c.camera.yaw+=.4;c.camera.setup(dm.bounds(c.model),app.CANVAS)
turned=AxisDraw(vm.draw);cad_draw.axes(turned,c.camera,palette)
assert turned.lines!=guide.lines
key(k.BUTTON_R)
cached=c.geometry;camera=(c.camera.yaw,c.camera.pitch,c.camera.zoom)
key(k.BUTTON_TAB);key(k.BUTTON_RIGHT);key(k.BUTTON_UP);key(k.BUTTON_PLUS)
assert c.geometry is cached and c.job is None and c.camera.yaw!=camera[0] and c.camera.zoom>1
key(k.BUTTON_F);snap('orbit')
key(k.BUTTON_SPACE);before=c.camera.pan_x;key(k.BUTTON_LEFT)
assert c.camera.pan_x<before and c.geometry is cached
key(k.BUTTON_ESCAPE);assert c.focus=='editor'
key(k.BUTTON_F5);choose('Top');assert c.geometry is cached;snap('top')
key(k.BUTTON_F5);choose('Isometric')
# Edit the cutter radius through real keys; dimensions change only on commit.
key(k.BUTTON_DOWN);assert c.selected==1
key(k.BUTTON_CENTER);assert c.tab==1
key(k.BUTTON_DOWN);assert c.properties()[c.row][0]=='a'
key(k.BUTTON_CENTER);text('6');key(k.BUTTON_CENTER)
assert c.model['features'][1]['a']==6 and c.dirty and not c.show_built
snap('properties')
# Typing '-' on a numeric row starts a negative value; it must not zoom.
zoom=c.camera.zoom;key(k.BUTTON_DOWN);key(k.BUTTON_DOWN);assert c.properties()[c.row][0]=='x'
text('-2');key(k.BUTTON_CENTER)
assert c.model['features'][1]['x']==-2 and c.camera.zoom==zoom
key(k.BUTTON_Z);assert c.model['features'][1]['x']==0 and c.model['features'][1]['a']==6
# Partial rebuilds never replace the old cache; Esc retains edited primitives.
c.input(k.BUTTON_F4);assert c.job is not None
c.input(k.BUTTON_ESCAPE);assert c.job is None and c.geometry is cached and c.model['features'][1]['a']==6
key(k.BUTTON_F4);finish();assert c.geometry is not cached and c.show_built
# A finished build is labelled with the model it was given, not the current one.
built=dm.clone(c.model);c.input(k.BUTTON_F4)
edited=dm.clone(c.model);edited['features'][1]['a']=5;c.transact(edited);finish()
assert c.built_model==built and not c.show_built
c.undo_edit();assert c.show_built and c.model==built
key(k.BUTTON_F9);assert c.help_open
key(k.BUTTON_END);assert c.help_first>0
key(k.BUTTON_CTRL_UP);snap('help');key(k.BUTTON_F9)
# Select coarser quality, then undo back to the cached built result.
key(k.BUTTON_Q);choose('Curve 0.67px')
assert c.model['resolution']==6 and not c.show_built
key(k.BUTTON_Z);assert c.model['resolution']==8 and c.show_built
# Add a rotated solid, remove it and undo with a bounded construction history.
key(k.BUTTON_F1);choose('Sphere');assert len(c.model['features'])==3
key(k.BUTTON_F2);assert len(c.model['features'])==2
key(k.BUTTON_Z);assert len(c.model['features'])==3
key(k.BUTTON_Z);assert len(c.model['features'])==2
# New always opens an empty project, with the existing unsaved guard.
prior=dm.clone(c.model);prior_dirty=c.dirty
key(k.BUTTON_F3);choose('New')
assert c.menu_kind=='confirm' and c.popup[c.menu_index]=='Cancel'
choose('Cancel');assert c.model==prior
key(k.BUTTON_F3);choose('New');choose('Discard')
assert c.model==dm.blank() and not c.show_built and c.filename is None
assert c.focus=='editor' and not c.dirty and not c.model['features']
snap('new-blank')
# The four primitives start as Add; Operation is chosen in Properties.
for shape in ('Box','Cylinder','Cone','Sphere'):
    key(k.BUTTON_F1);assert c.popup==('Box','Cylinder','Cone','Sphere')
    if shape=='Box':snap('add-primitives')
    choose(shape)
    assert c.model['features'][c.selected]['shape']==shape
    assert c.model['features'][c.selected]['op']=='Add' and c.tab==1 and c.row==0
    if shape=='Cylinder':
        key(k.BUTTON_CENTER);assert c.model['features'][c.selected]['op']=='Cut'
        key(k.BUTTON_CENTER);assert c.model['features'][c.selected]['op']=='Intersect'
        key(k.BUTTON_CENTER);assert c.model['features'][c.selected]['op']=='Add'
# Restore the earlier model through Open so subsequent file/cancel checks keep
# their independent saved-model expectations.
dm.save(vm.storage,'Restore',prior)
key(k.BUTTON_F3);choose('Open');choose('Discard');choose('Restore.pcad');finish()
assert c.model==prior and c.show_built
c.dirty=prior_dirty
# Unsupported project steps remain editable/saveable; a failed Build keeps
# the old complete cache and never substitutes a sampled or partial result.
unsupported=dm.clone(c.model);bad=dm.primitive('Sphere');bad.update(x=19,a=8);unsupported['features'].append(bad)
old_cache=c.geometry
c.transact(unsupported);c.build();finish()
assert c.result_kind=='unsupported' and c.error and c.job is None and c.geometry is old_cache
assert c.model==unsupported and not c.show_built
unsupported_path=dm.save(vm.storage,'Unsupported',unsupported)
assert dm.load(vm.storage,'Unsupported')==unsupported
c.undo_edit();assert c.show_built and c.geometry is old_cache
# Rejected property changes and failed file operations preserve the model.
previous=dm.clone(c.model)
try:c.change('a',-3)
except ValueError:pass
else:raise AssertionError('Invalid dimension accepted')
assert c.model==previous
path=dm.save(vm.storage,'sample',c.model)
assert dm.load(vm.storage,'sample')==c.model
old_text=vm.storage.read(path)
write=Storage.write
Storage.write=lambda *args,**kwargs:False
try:
    try:dm.save(vm.storage,'sample',dm.example(False))
    except OSError:pass
    else:raise AssertionError('False save reported success')
finally:Storage.write=write
assert vm.storage.read(path)==old_text
rename=Storage.rename
def failed_replace(self,old,new):
    return False if old.endswith('.tmp') else rename(self,old,new)
Storage.rename=failed_replace
try:
    try:dm.save(vm.storage,'sample',dm.example(False))
    except OSError:pass
    else:raise AssertionError('Failed replacement reported success')
finally:Storage.rename=rename
assert vm.storage.read(path)==old_text and not vm.storage.exists(path+'.bak')
vm.storage.write(dm.DIRECTORY+'/broken.pcad','{"picocad":1}')
try:dm.load(vm.storage,'broken')
except ValueError:pass
else:raise AssertionError('Malformed project loaded')
# Save/open through the actual menus, including cancel and existing-name safety.
key(k.BUTTON_F3);choose('Save as');assert c.prompt_kind=='save'
text('Demo');key(k.BUTTON_CENTER)
assert not c.dirty and c.filename=='Demo.pcad' and c.prompt_kind is None
key(k.BUTTON_F3);choose('Open');choose('Demo.pcad');finish()
assert c.model==previous and c.filename=='Demo.pcad' and not c.dirty
# Existing files containing unsupported geometry open into editable guides.
key(k.BUTTON_F3);choose('Open');choose('Unsupported.pcad');finish()
assert c.model==unsupported and c.filename=='Unsupported.pcad' and c.error
assert not c.show_built and not c.dirty and c.geometry is not None
key(k.BUTTON_F3);choose('Open');choose('Demo.pcad');finish()
assert c.show_built and not c.error and c.model==previous
# Unsaved exit defaults to Cancel; discarding exits cleanly and releases direct geometry.
c.change('a',7)
key(k.BUTTON_ESCAPE);assert c.tab==0
assert c.menu_kind=='confirm' and c.popup[c.menu_index]=='Cancel'
key(k.BUTTON_CENTER);assert vm.current_view.name=='picocad_view'
key(k.BUTTON_ESCAPE);choose('Discard')
assert vm.current_view.name=='parent' and app._active is None and c.geometry is None and c.vm is None
assert breadcrumbs.current(vm,'picocad_view') is None
print('PASS: XYZ guide, parallel/perspective projection, six-item options, blank New, primitive Add/properties, cached camera, cancellation, unsupported-model recovery and transactional files')

# Launch the real PicoLAB route and return with its selection/breadcrumb intact.
import PicoLAB as lab
vm.add(View('lab',lab.run,lab.start,lab.stop));vm.switch_to('lab')
lab._enter('tools');lab._selected=next(i for i,row in enumerate(lab.MENUS['tools']) if row[0]=='picocad')
key(k.BUTTON_CENTER);c=app._active
assert vm.current_view.name=='picocad_view' and breadcrumbs.current(vm)==('tools','PicoCAD')
finish();snap('picolab-launch')
key(k.BUTTON_ESCAPE)
assert vm.current_view.name=='lab' and lab._page=='tools'
sim_runtime._keys=[];sim_runtime.request_open('Apps/PicoLAB/tools/PicoCAD');assert sim_runtime._keys
print('PASS: PicoLAB Tools route, logo breadcrumb, selection restoration and managed resource cleanup')
print('Screenshots: '+preview)
