"""Explicit nodes, attachments and solve-time topology validation (metres)."""
from math import sqrt, isfinite

TYPES = ('rigid', 'pin')
TYPE_NAMES = ('Rigid', 'Pinned')
MAX_NODES = 40
EPS = 1e-6


class Problem(ValueError):
    def __init__(self, message, where=None, pair=None, item=None):
        super().__init__(message)
        self.where, self.pair, self.item = where, pair, item


def attached(model, node):
    return [i for i,m in enumerate(model['members']) if node in (m['a'],m['b'])]


def ensure(model):
    """Add editable schema-3 metadata without solving or changing load signs."""
    if not isinstance(model.get('joints'),list) or not isinstance(model.get('members'),list):
        raise ValueError('Missing nodes or members')
    for j in model['joints']:
        if len(j)!=2 or any(type(v) not in (int,float) or not isfinite(v) for v in j):
            raise ValueError('Nodes need finite X and Y coordinates')
    types=model.setdefault('joint_types',[])
    if not isinstance(types,list):raise ValueError('Invalid node types')
    while len(types)<len(model['joints']):types.append('rigid')
    del types[len(model['joints']):]
    if any(t not in TYPES for t in types):raise ValueError('Node type must be Rigid or Pinned')
    for m in model['members']:
        if any(type(m.get(k)) is not int or not 0<=m[k]<len(model['joints']) for k in ('a','b')):
            raise ValueError('Member references a missing node')
    for group in ('supports','hinges','loads'):
        model.setdefault(group,[])
        for obj in model[group]:
            if group=='supports':
                if 'settle' in obj:
                    # Older models settled downward in 'settle', only where the
                    # support restrains Y. Keep that as Settlement Y (up +).
                    from .model import SUPPORT_FLAGS
                    legacy=obj.pop('settle')
                    if legacy and 'y' in SUPPORT_FLAGS.get(obj.get('kind'),''):obj['settle_y']=-legacy
                obj.setdefault('settle_x',0.0)
                obj.setdefault('settle_y',0.0)
            m=obj.get('m',-1)
            if 'node' not in obj and 0<=m<len(model['members']):
                member=model['members'][m]
                length=axis(model,m,member['a'])[2]
                # Existing endpoint items follow the actual endpoint node;
                # interior/distributed items retain their measured distance.
                at_start=abs(obj.get('x',0))<=EPS
                at_end=abs(obj.get('x',0)-length)<=EPS
                endpoint='x2' not in obj and (at_start or at_end)
                node=member['b'] if endpoint and at_end and not at_start else member['a']
                bind(model,obj,node,m,endpoint)
    model['schema']=3
    sync(model)
    return model


def axis(model, m, node):
    edge=model['members'][m]
    other=edge['b'] if edge['a']==node else edge['a']
    a,b=model['joints'][node],model['joints'][other]
    dx,dy=b[0]-a[0],b[1]-a[1];length=sqrt(dx*dx+dy*dy)
    return (dx/length,dy/length,length) if length>EPS else (1.0,0.0,length)


def bind(model, obj, node, member=None, lock=True):
    """Keep a native member position, adding a node-relative editing reference."""
    choices=attached(model,node)
    m=obj.get('m',-1) if member is None else member
    if m not in choices:m=choices[0] if choices else -1
    obj['node'],obj['m'],obj['at_node']=node,m,bool(lock) and obj.get('kind') not in ('point','moment')
    if m<0:
        obj['offset']=0.0
        if 'x2' in obj:obj['offset2']=0.0
    else:
        length=axis(model,m,node)[2];reverse=model['members'][m]['b']==node
        obj['offset']=length-obj.get('x',0.0) if reverse else obj.get('x',0.0)
        if 'x2' in obj:
            d=length-obj['x2'] if reverse else obj['x2']
            obj['offset'],obj['offset2']=min(obj['offset'],d),max(obj['offset'],d)
    sync_item(model,obj)


def sync_item(model,obj):
    if 'node' not in obj:return
    node=obj['node']
    if not 0<=node<len(model['joints']):return
    choices=attached(model,node);m=obj.get('m',-1)
    if m not in choices:m=choices[0] if choices else -1
    obj['m']=m
    if m<0:return
    length=axis(model,m,node)[2];reverse=model['members'][m]['b']==node
    if obj.get('at_node') and obj.get('kind') not in ('point','moment') and len(choices)==1 and 'offset2' not in obj:obj['offset']=0.0
    d=obj.get('offset',0.0);obj['x']=length-d if reverse else d
    if 'offset2' in obj:
        e=obj['offset2'];p=length-e if reverse else e
        obj['x'],obj['x2']=min(obj['x'],p),max(obj['x'],p)


def sync(model):
    for group in ('supports','hinges','loads'):
        for obj in model.get(group,()):sync_item(model,obj)


def item_point(model,obj,field='x'):
    if 'node' in obj:
        node=obj['node'];origin=model['joints'][node];m=obj.get('m',-1)
        if m not in attached(model,node):return tuple(origin)
        if obj.get('kind')=='dist':
            from . import model as bm
            return bm.point(model,m,obj[field])
        ux,uy,length=axis(model,m,node)
        d=obj.get('offset2' if field=='x2' else 'offset',0.0)
        return origin[0]+ux*d,origin[1]+uy*d
    from . import model as bm
    return bm.point(model,obj['m'],obj[field])


def point_on(model,j,m):
    edge=model['members'][m];a=model['joints'][edge['a']];p=model['joints'][j]
    ux,uy,length=axis(model,m,edge['a'])
    x=(p[0]-a[0])*ux+(p[1]-a[1])*uy
    distance=abs(-(p[0]-a[0])*uy+(p[1]-a[1])*ux)
    return x if distance<=EPS and EPS<x<length-EPS else None


def overlaps(model):
    out=[]
    for i,edge in enumerate(model['members']):
        ux,uy,length=axis(model,i,edge['a'])
        if length<=EPS:continue
        a=model['joints'][edge['a']]
        for j in range(i+1,len(model['members'])):
            other=model['members'][j]
            b,c=(model['joints'][other[k]] for k in ('a','b'))
            if any(abs(-(p[0]-a[0])*uy+(p[1]-a[1])*ux)>EPS for p in (b,c)):continue
            s,t=((p[0]-a[0])*ux+(p[1]-a[1])*uy for p in (b,c))
            lo,hi=max(0.0,min(s,t)),min(length,max(s,t))
            if hi-lo>EPS:out.append((i,j,(a[0]+ux*lo,a[1]+uy*lo),(a[0]+ux*hi,a[1]+uy*hi)))
    return out


def validate(model):
    """Run from the solve API, including callers which bypass the editor."""
    joints=model['joints'];members=model['members']
    for i,p in enumerate(joints):
        if not isinstance(p,(list,tuple)) or len(p)!=2 or any(type(v) not in (int,float) or not isfinite(v) for v in p):
            raise Problem('J%d needs finite X and Y'%(i+1))
    for i,m in enumerate(members):
        if any(type(m.get(k)) is not int or not 0<=m[k]<len(joints) for k in ('a','b')):
            raise Problem('L%d references a missing node'%(i+1))
        if m['a']==m['b'] or axis(model,i,m['a'])[2]<=EPS:
            raise Problem('L%d has zero length: choose different nodes'%(i+1),tuple(joints[m['a']]))
    for i,p in enumerate(joints):
        for j in range(i):
            q=joints[j]
            if abs(p[0]-q[0])<EPS and abs(p[1]-q[1])<EPS:
                raise Problem('J%d and J%d coincide: F3 Merge nodes'%(j+1,i+1),tuple(p))
    for i,t in enumerate(model.get('joint_types',())):
        if t not in TYPES:raise Problem('J%d has an invalid connection type'%(i+1))
    overlap=overlaps(model)
    if overlap:
        i,j,a,b=overlap[0]
        raise Problem('L%d overlaps L%d: F3 Resolve overlaps'%(i+1,j+1),((a[0]+b[0])/2,(a[1]+b[1])/2),(i,j))
    used=set(j for m in members for j in (m['a'],m['b']))
    for j in used:
        for i,m in enumerate(members):
            if j not in (m['a'],m['b']) and point_on(model,j,i) is not None:
                raise Problem('J%d lies inside L%d: F3 Split at node'%(j+1,i+1),tuple(joints[j]))
    for group in ('supports','hinges','loads'):
        for index,obj in enumerate(model[group]):
            m=obj.get('m',-1)
            if type(m) is not int or not 0<=m<len(members):
                label={'supports':'Support','hinges':'Hinge','loads':'Load'}[group]+' '+str(index+1)
                node=obj.get('node');where=None
                if type(node) is int and 0<=node<len(joints):
                    where=tuple(joints[node]);label+=' / J%d'%(node+1)
                    # Hinges (older models only) have no From node to change.
                    fix='remove it' if group=='hinges' else 'change From node'
                    message=label+': no member; connect J%d or %s'%(node+1,fix) if not attached(model,node) else label+': reselect From node or Along member'
                else:message=label+': select From node on a member'
                raise Problem(message,where,item=(group,index))
            for key in ('x','x2','offset','offset2','P','M','w1','w2','kx','ky','kr'):
                if key in obj and (type(obj[key]) not in (int,float) or not isfinite(obj[key])):
                    raise Problem('%s %d needs finite %s'%(group[:-1],index+1,key))
            if 'node' in obj:
                node=obj['node']
                if type(node) is not int or node not in (members[m]['a'],members[m]['b']):raise Problem('Item references an unconnected node')
                length=axis(model,m,node)[2]
                for key in ('offset','offset2'):
                    if key in obj and (not isfinite(obj[key]) or not -EPS<=obj[key]<=length+EPS):
                        raise Problem('Position must stay within L%d'%(m+1),tuple(joints[node]))
                if 'offset2' in obj and not obj['offset']<obj['offset2']-EPS:raise Problem('Distributed start must be before end')
    from . import model as bm
    for index,obj in enumerate(model['supports']):
        if obj.get('kind') not in bm.SUPPORT_FLAGS:raise Problem('Unknown support type')
        if 'settle' in obj:raise Problem("Support %d has an old 'settle': upgrade the model first"%(index+1))
        if (obj.get('settle_x') or obj.get('settle_y')) and not 0<=obj.get('case',-1)<len(model['cases']):
            raise Problem('Settlement uses a missing load case')
        for flag,key in (('x','settle_x'),('y','settle_y')):
            value=obj.get(key,0.0)
            if type(value) not in (int,float) or not isfinite(value):raise Problem('Settlement must be finite')
            if value and flag not in bm.SUPPORT_FLAGS[obj['kind']]:raise Problem('Settlement '+flag.upper()+' needs a restrained direction')


def merge(model,source,target):
    from .items import copy
    out=copy(model);ensure(out)
    if source==target:raise ValueError('Choose two different nodes')
    for edge in out['members']:
        for key in ('a','b'):
            if edge[key]==source:edge[key]=target
        if edge['a']==edge['b']:raise ValueError('Merge would make a zero-length member')
    if out['joint_types'][source]!=out['joint_types'][target]:
        raise ValueError('Node types differ: set the same type before merging')
    for group in ('supports','hinges','loads'):
        for obj in out[group]:
            if obj.get('node')==source:obj['node']=target
    del out['joints'][source];del out['joint_types'][source]
    for edge in out['members']:
        for key in ('a','b'):edge[key]-=edge[key]>source
    for group in ('supports','hinges','loads'):
        for obj in out[group]:
            if 'node' in obj:obj['node']-=obj['node']>source
    sync(out)
    separate_supports(out,'Merge would place two supports together')
    return out,target-(target>source)


def separate_supports(model,message):
    positions=[]
    for obj in model['supports']:
        p=item_point(model,obj)
        if any(abs(p[0]-q[0])<EPS and abs(p[1]-q[1])<EPS for q in positions):raise ValueError(message)
        positions.append(p)


def split_at(model,member,node):
    from . import items
    x=point_on(model,node,member)
    if x is None:raise ValueError('Choose a node inside the selected member')
    return items.split(model,member,x,node=node)


def normalize(model):
    """Explicit, transactional split/deduplicate; refuse section/load conflicts."""
    from . import items,model as bm
    out=items.copy(model);ensure(out)
    if not overlaps(out):raise ValueError('No overlapping members')
    # Native x positions are the source of truth during the split/remap.
    # An orphan keeps its node: nothing else locates it.
    for group in ('supports','hinges','loads'):
        for obj in out[group]:
            if 0<=obj.get('m',-1)<len(out['members']):
                for key in ('node','offset','offset2','at_node'):obj.pop(key,None)
    used=sorted(set(j for m in out['members'] for j in (m['a'],m['b'])))
    i=0
    while i<len(out['members']):
        for j in used:
            if j not in (out['members'][i]['a'],out['members'][i]['b']) and point_on(out,j,i) is not None:
                split_at(out,i,j)
        i+=1
    i=0
    while i<len(out['members']):
        edge=out['members'][i];j=i+1
        while j<len(out['members']):
            other=out['members'][j]
            if set((edge['a'],edge['b']))!=set((other['a'],other['b'])):j+=1;continue
            if edge['section']!=other['section']:raise ValueError('Overlapping sections differ: choose one section first')
            if any(l['m']==i for l in out['loads']) and any(l['m']==j for l in out['loads']):
                raise ValueError('Both overlapping members carry loads: resolve those loads first')
            reverse=edge['a']!=other['a'];length=bm.member_length(out,i)
            for group in ('supports','hinges','loads'):
                for obj in out[group]:
                    if obj['m']==j:
                        if reverse:
                            if obj.get('kind')=='dist':
                                obj['x'],obj['x2']=length-obj['x2'],length-obj['x']
                                obj['w1'],obj['w2']=obj['w2'],obj['w1']
                                if obj.get('dir')=='normal':obj['w1']=-obj['w1'];obj['w2']=-obj['w2']
                            else:
                                if group=='loads' and obj.get('kind')=='point':
                                    obj['angle']=bm.load_angle(out,obj);obj['dir']='angle'
                                obj['x']=length-obj['x']
                        obj['m']=i
                    elif obj['m']>j:obj['m']-=1
            del out['members'][j]
        i+=1
    ensure(out)
    # Refuse coincident supports here, without invoking the solver or
    # requiring supports while drafting.
    separate_supports(out,'Overlapping supports conflict: remove one first')
    if bm.item_count(out)>bm.MAX_ITEMS:raise ValueError('Resolved model exceeds the item limit')
    return out


def bridge():
    from . import model as bm
    m=bm.empty_model(((0,0),(2,0),(4,0),(6,0),(2,2),(4,2)),
                     ((0,1),(1,2),(2,3),(4,5),(0,4),(4,1),(4,2),(2,5),(5,3)))
    m['joint_types']=['pin']*6
    m['supports']=[bm.support(0,0,'Pin'),bm.support(2,2,'Roller')]
    m['loads']=[bm.point_load(3,0,10000),bm.point_load(3,2,10000)]
    return ensure(m)
