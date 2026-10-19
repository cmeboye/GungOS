"""Explicit nodes, live geometry editing, F6-only solves and safe topology tools."""
import os,sys,json
from time import ticks_ms
root=os.getcwd()
for part in ('src/MicroPython','simulator/hardware','builds/MicroPython/apps_unfrozen'):
    sys.path.insert(0,root+'/'+part)
import sim_runtime
sim_runtime.configure(root,'/private/tmp/gungos-beam-nodes-test-'+str(ticks_ms()),
    root+'/builds/MicroPython/apps_unfrozen',1,'picocalc-pico2w',0,True,False,False,False,'',
    _network_mode='offline',_audio_mode='silent',_sd_profile='clean')
from picoware.system.view_manager import ViewManager
from picoware.system.view import View
from picoware.system.input import Input
from picoware.system import buttons as k
from engtools.beamlab import app,model as bm,structure as st,items as bi
from engtools import session,cases
Input.button=property(lambda self:self._last_button)
session.kept.clear();vm=ViewManager();vm._wifi=None
vm.add(View('parent',lambda vm:None,lambda vm:True,lambda vm:None));vm.switch_to('parent')
app.show(vm);a=app._active

def key(button):
    vm.input_manager._last_button=button;vm.run()
    vm.input_manager._was_capitalized=False

def char(c):key(vm.input_manager._key_to_button(ord(c)))
def value(ref,field,text):
    a.focus(ref,field);key(k.BUTTON_CENTER)
    assert a.edit is not None,(ref,field,a.message)
    for _ in range(len(a.edit.text)):key(k.BUTTON_BACKSPACE)
    for c in text:char(c)
    key(k.BUTTON_CENTER)
    assert a.edit is None,a.message

def near(got,want):assert abs(got-want)<1e-5*max(1,abs(want)),(got,want)
def rejects(m,words):
    try:bm.Solution(m)
    except bm.ModelError as e:assert words in str(e),(words,str(e));return e
    raise AssertionError('Solver accepted '+words)

key(k.BUTTON_CENTER)
assert a.solution is None and a.model_tab==0
for page,button in (('diagrams',k.BUTTON_F4),('results',k.BUTTON_F5)):
    key(button);assert a.page==page and a.solution is None
key(k.BUTTON_ESCAPE)
assert a.page=='model'
# Catch ANY implicit solve, including drawing, choice previews and undo.
original=bm.Solution
calls=[]
def forbidden(model):calls.append(1);raise AssertionError('Background solve')
bm.Solution=forbidden
try:
    a.replace_model(bm.empty_model([],[]));a.draw()
    key(k.BUTTON_F1);assert len(a.model['joints'])==1
    value(('joint',0),'X','0');value(('joint',0),'Y','0')
    key(k.BUTTON_F1);value(('joint',1),'X','6*cos(30)');value(('joint',1),'Y','6*sin(30)')
    near(a.model['joints'][1][0],5.19615242);near(a.model['joints'][1][1],3)
    a.focus(('joint',1),'type');char(']');assert a.model['joint_types'][1]=='pin'
    char('[');assert a.model['joint_types'][1]=='rigid'
    key(k.BUTTON_RIGHT);assert a.model_tab==1
    key(k.BUTTON_F1);assert len(a.model['members'])==1 and a.sel[1]=='a'
    # Endpoint choices render instantly; cancel restores the whole model.
    a.focus(('member',0),'b');before=bi.copy(a.model);undo=len(a.undo)
    key(k.BUTTON_CENTER);assert a.choice_edit is not None
    char(']');assert a.model['members'][0]['b']==a.model['members'][0]['a']
    key(k.BUTTON_ESCAPE);assert a.model==before and len(a.undo)==undo
    a.focus(('member',0),'section');char('E');assert a.page=='section'
    key(k.BUTTON_ESCAPE);assert a.page=='model'
    a.focus(('member',0));key(k.BUTTON_F2)
    assert not a.model['members'] and len(a.model['joints'])==2
    char('z');assert len(a.model['members'])==1
    a.draw();assert not calls
finally:bm.Solution=original
print('PASS: degree expressions, independent nodes, contextual F1, live brackets/cancel, Shift+E, undo; zero background solves')
# Attach from a branching node; use a reversed incident member and signed XY settlements.
m=bm.empty_model(((0,0),(2,0),(4,0)),((0,1),(2,1)))
a.replace_model(m);a.focus(('joint',1));a.model_tab=2
for idx,kind in enumerate(bm.SUPPORTS):
    n=len(a.model['supports']);key(k.BUTTON_F1);a.popup[2]=idx;key(k.BUTTON_CENTER)
    assert len(a.model['supports'])==n+1 and a.model['supports'][-1]['kind']==kind
    char('z');assert len(a.model['supports'])==n
key(k.BUTTON_F1);key(k.BUTTON_CENTER);support=a.model['supports'][-1];ref=('support',support)
assert support['node']==1
assert 'along' in [f[0] for f in bi.fields(a.model,ref)]
a.focus(ref,'along');char(']');assert support['m']==1
value(ref,'x','1/2');near(support['x'],1.5);assert st.item_point(a.model,support)==(2.5,0)
value(ref,'settle_x','-2');value(ref,'settle_y','3')
near(support['settle_x'],-.002);near(support['settle_y'],.003)
a.focus(ref,'kind');char(']');assert support['kind']=='Roller' and support['settle_x']==0
# Terminal loads start at the node, but their inward offset remains editable.
a.focus(('joint',2));a.model_tab=3
key(k.BUTTON_F1);key(k.BUTTON_CENTER);load=a.model['loads'][-1]
assert load['node']==2 and load['m']==1 and load['x']==0
assert next(f for f in bi.fields(a.model,('load',load)) if f[0]=='x')[4]
value(('load',load),'x','.5');near(load['x'],.5)
near(st.item_point(a.model,load)[0],3.5)
a.resolve();near(load['offset'],.5)
value(('load',load),'x','0')
# Angle input, non-finite refusal, normal vector and persistence.
value(('load',load),'angle','-45');near(load['angle'],315)
from engtools.beamlab import render
ux,uy=render.screen_direction(a.model,load);near(ux,2**-.5);near(uy,2**-.5)
path=cases.save_case(vm.storage,'node-roundtrip',a.model)
saved=cases.load_case(vm.storage,'node-roundtrip','beams');saved=bm.upgrade(saved)
assert saved['schema']==3 and saved['joint_types']==a.model['joint_types']
assert saved['loads'][-1]['angle']==315
# Deleting a member keeps unattached node loads editable, rather than losing them.
a.focus(('member',1));key(k.BUTTON_F2);a.draw()
assert a.model['loads'][-1]['node']==2 and a.model['loads'][-1]['m']==-1
assert not a.evaluate() and 'Load 1 / J3: no member' in str(a.problem)
assert a.problem.where==(4,0) and a.sel[0][1] is a.model['loads'][-1] and a.sel[1]=='node'
a.draw()
assert any(f[0]=='along' and not f[4] for f in bi.fields(a.model,a.sel[0]))
print('PASS: branch-relative attachments, reversed offsets, six support types, XY settlement, endpoint offsets, force angles, orphan recovery and persistence')
# Actual pins are releases of every incident end; triangular structure stays stable.
a.replace_model(bm.template(1))
value(('joint',1),'X','6')
assert a.model['loads'][0]['node']==1 and a.model['loads'][0]['x']==6
assert a.evaluate();near(a.solution.reactions(a.view)[0][3],60000)
a.replace_model(st.bridge());key(k.BUTTON_F6);assert a.solution is not None and a.problem is None
sol=a.solution
near(sol.reactions(a.view)[0][2],10000);near(sol.reactions(a.view)[1][2],10000)
for m in range(9):
    near(sol.at(m,0,a.view)[1],0);near(sol.at(m,bm.member_length(a.model,m),a.view)[1],0)
for button in (k.BUTTON_RIGHT,k.BUTTON_DOWN,k.BUTTON_LEFT,k.BUTTON_F4,k.BUTTON_F5,k.BUTTON_ESCAPE):
    key(button);assert a.solution is sol
value(('joint',5),'Y','2.1');assert a.solution is None
key(k.BUTTON_F5);assert a.solution is None and 'Not evaluated' in str(a.result_rows())
key(k.BUTTON_F6);assert a.solution is not None
print('PASS: pinned bridge reactions/moments, navigation retains results, edits clear them, F6 works from Results')
# Overlaps fail in the API even when the editor is bypassed, then normalize explicitly.
def overlap(reverse=False):
    m=bm.empty_model(((0,0),(1,0),(2,0)),((0,1),(2,0) if reverse else (0,2)))
    m['supports']=[bm.support(0,0,'Fixed')];m['loads']=[bm.point_load(1,0 if reverse else 2,1000)]
    return m
for reverse in (False,True):
    m=overlap(reverse);e=rejects(m,'overlaps');assert e.pair==(0,1)
    before=bi.copy(m);out=st.normalize(m)
    assert m==before and len(out['members'])==2 and len(out['joints'])==3
    sol=bm.Solution(out);near(sol.reactions(0)[0][2],1000);near(sol.reactions(0)[0][3],2000)
    sol.free()
# Resolve dialog cancellation and acceptance are transactional, undoable and do not solve.
a.replace_model(overlap());key(k.BUTTON_F6);assert a.problem and a.solution is None
before=bi.copy(a.model);n=len(a.undo);a.normalize_menu();a.draw()
assert len(a.model['members'])==2 and a.solution is None
key(k.BUTTON_ESCAPE);assert a.model==before and len(a.undo)==n
a.normalize_menu();key(k.BUTTON_CENTER);assert not st.overlaps(a.model)
char('z');assert st.overlaps(a.model)
# Conflicting sections/loads cannot be silently discarded or doubled.
m=overlap();m['sections'].append(bm.new_section('S2'));m['members'][1]['section']=1
try:st.normalize(m)
except ValueError as e:assert 'sections differ' in str(e)
else:raise AssertionError('Conflicting sections were merged')
m=overlap();m['loads'][0]['x']=.5;m['loads'].append(bm.point_load(0,.5,1000))
try:st.normalize(m)
except ValueError as e:assert 'carry loads' in str(e)
else:raise AssertionError('Ambiguous loads were merged')
# Distributed loading is split with interpolated endpoints, preserving resultant.
m=overlap();m['loads']=[bm.dist_load(1,0,2,1000,3000)]
out=st.normalize(m);sol=bm.Solution(out);near(sol.applied(0)[1],-4000);sol.free()
# Touching endpoints are valid; an unsplit used T-junction needs explicit joining.
m=bm.empty_model(((0,0),(1,0),(2,0)),((0,1),(1,2)))
m['supports']=[bm.support(0,0,'Fixed')];bm.Solution(m).free()
m=bm.empty_model(((0,0),(2,0),(1,0),(1,1)),((0,1),(2,3)))
m['supports']=[bm.support(0,0,'Fixed')];rejects(m,'inside L1')
st.split_at(m,0,2);assert len(m['joints'])==4 and len(m['members'])==3
bm.Solution(m).free()
# Duplicate nodes do not become silently welded; explicit merge remaps attachments.
m=bm.empty_model(((0,0),(1,0),(1,0),(1,1)),((0,1),(2,3)))
m['supports']=[bm.support(0,0,'Fixed')];rejects(m,'coincide')
out,j=st.merge(m,2,1);assert j==1 and len(out['joints'])==3
assert out['members'][1]['a']==1;bm.Solution(out).free()
# Interior stations on crossing members MUST remain separate even at identical coords.
m=bm.empty_model(((-1,0),(1,0),(0,-1),(0,1)),((0,1),(2,3)))
m['supports']=[bm.support(0,0,'Fixed'),bm.support(1,0,'Fixed')]
m['loads']=[bm.point_load(0,1,1000),bm.point_load(1,1,0)]
sol=bm.Solution(m)
assert len(sol.nodes)==6
near(sol.reactions(0)[0][2],1000);near(sol.reactions(0)[1][2],0);sol.free()
# Geometric validity errors occur on F6, leaving the editor alive.
a.replace_model(bm.empty_model(((0,0),(1,0)),((0,1),)))
key(k.BUTTON_F6);assert a.problem is not None and a.page=='model';a.draw()
value(('joint',1),'X','0');key(k.BUTTON_F6)
assert 'zero length' in str(a.problem) and a.solution is None;a.draw()
print('PASS: solver-side overlap, coincidence and T-junction checks; transactional normalize/split/merge; load preservation, independent crossings and graceful F6 failures')
# Global settlement convention and schema-2 downward compatibility: an old
# downward 'settle' is converted once on loading, then dropped. A value its
# support type ignored (no Y restraint) stays ignored; the solver refuses an
# unconverted one.
m=bm.template(0);m['loads']=[]
for s,kind in zip(m['supports'],('Roller x','Roller')):
    s['kind']=kind;del s['settle_x'],s['settle_y'];s['settle']=.002
rejects(m,"old 'settle'")
st.ensure(m);near(m['supports'][1]['settle_y'],-.002);assert m['supports'][0]['settle_y']==0
assert not any('settle' in s for s in m['supports'])
m['supports'][0]['kind']='Pin'
sol=bm.Solution(m);near(sol.at(0,6,0)[3],-.002);sol.free()
m['supports'][0]['settle_x']=.001;m['supports'][1]['settle_y']=.003
sol=bm.Solution(m);near(sol.at(0,0,0)[5],.001);near(sol.at(0,6,0)[3],.003);sol.free()
for field,bad in (('x',float('nan')),('P',float('inf'))):
    m=bm.template(1);m['loads'][0][field]=bad;rejects(m,'finite')
m=bm.template(1);m['joints'][1]=['bad',0];rejects(m,'finite')
print('PASS: signed global XY settlement, old downward settlement migration and native numerical solve')

# F1 on an isolated draft node must explain the connection before creating an item.
a.replace_model(bm.empty_model(((0,0),(2,0),(4,0)),((0,1),)))
a.focus(('joint',2));a.model_tab=3
n=len(a.undo);key(k.BUTTON_F1);key(k.BUTTON_CENTER)
assert a.error and 'J3 has no member' in a.message and 'Split at node' in a.message
assert not a.model['loads'] and len(a.undo)==n
# Point/moment offsets at both ends (including old locked metadata) preserve
# native positions, drawn positions and correct closed-form cantilever reactions.
for node in (0,1):
    for kind in ('point','moment'):
        m=bm.template(1);m['loads']=[];a.replace_model(m)
        a.focus(('joint',node));a.add_attachment(kind)
        load=a.model['loads'][0];load['at_node']=True
        value(('load',load),'x','.5')
        x=.5 if node==0 else 2.5
        near(load['x'],x);near(st.item_point(a.model,load)[0],x)
        load['at_node']=True  # A schema-3 file made before the offset fix.
        a.resolve();near(load['offset'],.5);near(load['x'],x)
        assert a.evaluate()
        r=a.solution.reactions(a.view)[0]
        near(r[2],10000 if kind=='point' else 0)
        near(r[3],10000*x if kind=='point' else -10000)
        a.focus(('load',load),'x');key(k.BUTTON_CENTER)
        key(k.BUTTON_F9);key(k.BUTTON_ESCAPE);assert a.edit is not None
        key(k.BUTTON_ESCAPE);assert a.solution is not None
        path=cases.save_case(vm.storage,'offset-case',a.model)
        saved=bm.upgrade(cases.load_case(vm.storage,'offset-case','beams'))
        near(saved['loads'][0]['offset'],.5);near(saved['loads'][0]['x'],x)
        # Moving an endpoint must keep the measured offset from that endpoint.
        value(('joint',1),'X','4')
        near(load['x'],.5 if node==0 else 3.5)
        assert a.solution is None
        # Off-member distances remain drafting edits until F6 reports them.
        value(('load',load),'x','5');assert not a.evaluate()
        assert 'Position must stay within L1' in str(a.problem)
        char('z');near(a.model['loads'][0]['offset'],.5)
# A member endpoint edit can orphan an existing load. F6 points to that load;
# choosing a connected reference node restores it without another load or solve.
m=bm.empty_model(((0,0),(2,0),(4,0),(6,0)),((0,1),(1,2)))
m['supports']=[bm.support(0,0,'Fixed')]
a.replace_model(m);a.focus(('joint',2));a.add_attachment('point')
load=a.model['loads'][0];value(('load',load),'x','.25')
bi.set_choice(a.model,('member',1),'b',3);a.changed(('member',1),'b')
assert load['node']==2 and load['m']==-1 and load['offset']==.25
assert not a.evaluate() and 'Load 1 / J3: no member' in str(a.problem)
assert a.sel[0][1] is load and a.sel[1]=='node'
char(']');assert load['node']==3 and load['m']==1 and a.solution is None
value(('load',load),'x','.25');assert a.evaluate()
near(a.solution.reactions(a.view)[0][3],57500)
# Reattaching that same draft node via a new member also repairs the reference.
a.replace_model(bm.empty_model(((0,0),(2,0),(4,0)),((0,1),)))
load=bm.point_load(-1,0);load.update(node=2,offset=.25,at_node=True)
a.model['loads'].append(load);a.resolve();a.focus(('joint',2));a.add_member()
assert load['m']==1 and load['offset']==.25 and a.solution is None
print('PASS: endpoint point/moment offsets, old lock migration, reaction/drawing/save parity, bounds/undo, isolated-node Add guard and targeted orphan repair')

# Reproduce the reported workflow: add an interior draft node, explicitly
# split/join it into the beam, then add and offset its load using the UI.
m=bm.empty_model(((0,0),(3,0),(1,0)),((0,1),))
m['supports']=[bm.support(0,0,'Fixed')]
a.replace_model(m);a.focus(('joint',2));a.model_tab=3
key(k.BUTTON_F1);key(k.BUTTON_CENTER);assert not a.model['loads'] and a.error
a.split_menu();key(k.BUTTON_CENTER);key(k.BUTTON_CENTER)
assert len(a.model['members'])==2 and len(a.model['joints'])==3
assert a.node_cursor==2 and a.solution is None
a.model_tab=3;key(k.BUTTON_F1);key(k.BUTTON_CENTER)
load=a.model['loads'][0];assert load['node']==2 and load['m']==1
value(('load',load),'x','.5');assert a.evaluate()
near(a.solution.reactions(a.view)[0][3],15000)
print('PASS: new interior node -> explicit split/join -> offset load -> correct cantilever reaction')

# Section edits share the 12-step undo limit with every other edit.
a.replace_model(bm.template(0));a.undo=[]
a.open_section(a.model['sections'][0])
a.section_row=[r[0] for r in a.section_rows()].index('dim:h')
for i in range(app.UNDO_LIMIT+3):
    key(k.BUTTON_CENTER);assert a.edit is not None,a.message
    for _ in range(len(a.edit.text)):key(k.BUTTON_BACKSPACE)
    for c in str(300+i):char(c)
    key(k.BUTTON_CENTER);assert a.edit is None,a.message
assert len(a.undo)==app.UNDO_LIMIT,len(a.undo)
key(k.BUTTON_ESCAPE);assert a.page=='model'
# A load case used only by a horizontal settlement cannot be removed.
m=bm.template(0);st.ensure(m);bi.add_case(m,'Settle')
m['supports'][0].update(settle_x=.005,case=1)
try:bi.remove_case(m,1)
except ValueError as e:assert 'use this case' in str(e),str(e)
else:raise AssertionError('Removed the case of a settlement')
# Orphans stay at their own node through Split at node and Resolve overlaps.
m=bm.empty_model(((0,0),(4,0),(2,0),(9,0)),((0,1),))
m['supports']=[bm.support(0,0,'Fixed')];st.ensure(m)
orphan=bm.point_load(-1,0);orphan.update(node=3,offset=0.0,at_node=False);m['loads'].append(orphan)
st.split_at(m,0,2);assert orphan['node']==3 and orphan['m']==-1,orphan
m=overlap();m['joints'].append([5,5]);m['joint_types'].append('rigid')
orphan=bm.point_load(-1,0);orphan.update(node=3,offset=0.0,at_node=False);m['loads'].append(orphan)
out=st.normalize(m);assert out['loads'][-1]['node']==3 and out['loads'][-1]['m']==-1,out['loads'][-1]
# An endpoint hinge from an older model, orphaned by removing its member,
# draws at its node, including when no member is left.
m=bm.empty_model(((0,0),(4,0),(8,0),(0,3)),((0,1),(1,2),(0,3)))
m['supports']=[bm.support(0,0,'Fixed')];m['hinges']=[{'m':1,'x':4.0}]
a.replace_model(m);hinge=a.model['hinges'][0];assert hinge['node']==2
for member in (1,0,0):a.focus(('member',member));key(k.BUTTON_F2)
assert not a.model['members'] and hinge['m']==-1 and hinge['node']==2
a.draw()
a.model['members'].append({'a':0,'b':1,'section':0});a.resolve()
assert not a.evaluate() and 'Hinge 1 / J3: no member; connect J3 or remove it' in str(a.problem),a.problem
a.draw()
# Results are built once per view and pins, but follow a renamed load case.
a.replace_model(bm.template(0));assert a.evaluate();a.view=0
rows=a.result_rows();assert a.result_rows() is rows and rows[0][1]=='Dead'
a.rename_case(0);a.prompt['apply']('Permanent');a.prompt=None
assert a.solution is not None and a.result_rows()[0][1]=='Permanent'
print('PASS: section undo limit, settlement case guard, orphans kept through split/resolve, orphaned hinge drawing, cached results follow renames')
