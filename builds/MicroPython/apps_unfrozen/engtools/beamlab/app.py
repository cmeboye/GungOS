"""BeamView: model editor, section editor, diagrams, results and options in PicoLAB.

F1 Add, F2 Remove, F3 Options, F4 Plot, F5 Results and F6 Evaluate.
Editing changes only geometry; only F6 invokes the solver. It stays in RAM while
PicoLAB runs; saving to the SD card is explicit.
"""
from picoware.system import buttons as keys
from engtools.ui import theme
from engtools.ui.forms import LineEdit, erase_key
from engtools import units, cases
from . import model as bm
from . import items
from . import render
from . import structure as st

OPTIONS = ('New beam', 'New blank structure', 'Merge nodes', 'Split at node', 'Resolve overlaps', 'Load cases', 'Combinations', 'Self-weight', 'Save', 'Open', 'Export CSV (Eggcel)', 'Export full CSV',
           'Conventions and keys')
UNDO_LIMIT = 12
MENU_PAGES = ('start', 'options', 'cases', 'combos', 'open')
ZOOMS = (1.0, 2.0, 4.0)
MODEL_TABS = ('Node', 'Member', 'Support', 'Load')
ADD_OPTIONS = (
    (('Node','node'),), (('Member','member'),),
    tuple((name,'support') for name in bm.SUPPORTS),
    (('Point load','point'),('Moment','moment'),('Distributed load','dist')),
)

HELP = (
    'BeamView / NODE EDITOR',
    'UP/DOWN scroll; LEFT/RIGHT page',
    'F9 / ESC close help; edits stay intact',
    'F1 Add at cursor  F2 Remove item',
    'F3 Options  F4 Plots  F5 Results',
    'F6 Evaluate: the ONLY solve command',
    'ESC returns; Z undoes (12 steps)',
    '', 'Node / Member / Support / Load:',
    'LEFT/RIGHT changes the tab',
    'UP/DOWN items; ENTER opens properties',
    'ENTER edits; ESC collapses properties',
    '[ / ] cycles the selected choice',
    'ENTER on choice: live preview list',
    '[ / ] or UP/DOWN previews choices',
    'ENTER accepts; ESC restores the choice',
    'TAB next member; , / . steps points',
    '+ / - preview zoom; I result summary',
    '', 'Nodes:',
    'X,Y in metres; Type Rigid / Pinned',
    'Expressions: 6*cos(30), 6*sin(30)',
    'All Beam expression angles use DEGREES',
    'Trig mode is independent of Calculator',
    'Nodes can exist before their members',
    'Pinned: member ends rotate independently',
    'Rigid: attached members share rotation',
    'A node inside a member connects to it;',
    'that member stays continuous through it',
    'Type only matters where members meet',
    'Fixed/rotation support holds all members',
    '', 'Members:',
    'Start J#, End J#, Section',
    'F1 needs at least two existing nodes',
    '[ / ] changes the highlighted property',
    'Shift+E opens the member section editor',
    'Section choices retain unused sections',
    'Preview updates without evaluation',
    '', 'Supports and loads:',
    'From node selects the reference J#',
    'Along member appears at branches',
    'Arrow shows positive distance from J#',
    'Load offset is editable at endpoints too',
    'Positive offset points into the member',
    'Connect new nodes before adding loads',
    'Inside a member: offset + toward its end',
    'Distributed loads use Start/End distances',
    'Settlement X/Y in mm, right/up positive',
    'Only restrained directions allow movement',
    'Point force angle: 0 right, 90 up',
    '', 'Evaluation:',
    'Edits clear results and displacement',
    'F4/F5 stay empty until a successful F6',
    'Navigation does not invalidate results',
    'No background solves, including on Open',
    'F6 checks overlap and connectivity first',
    'Coincident nodes: F3 Merge nodes',
    'Member hinge: F3 Split at a Pinned node',
    'Crossing lines need an explicit node/join',
    'Overlapping lengths cannot be evaluated',
    'F3 Resolve overlaps previews normalization',
    'Conflicting sections/loads need editing',
    '', 'Plots:',
    '[ / ] next/previous member; indicator L#',
    'LEFT/RIGHT cursor; UP/DOWN stops',
    'TAB peaks; ENTER pins (up to 8)',
    'V / SPACE next case or combination',
    'D changes quantity; F whole-frame view',
    '', 'Text and files:',
    'ENTER apply; ESC cancel; TAB apply',
    'UP/DOWN apply and move to next value',
    'BACK and DEL erase before the caret',
    'F3 Save/Open; models use schema 3',
    'Older cases migrate; settlement signs kept',
    'Export needs a successful F6 first',
    'Eggcel CSV <=511 cells; full CSV optional',
    'Euler-Bernoulli, small displacements',
)


def beam_number(text):
    from engtools.calculator.evaluate import calculate
    value,assignment=calculate(text,{'Ans':0},'DEG')
    if assignment is not None or isinstance(value,complex) or not bm.isfinite(value):
        raise ValueError('Enter a finite real number')
    return float(value)

_active = None


class BeamLab:
    def __init__(self, vm):
        self.vm = vm
        from engtools import session
        kept = session.kept.get('beam') or {}
        self.model = kept.get('model')
        self.undo = []
        self.view = kept.get('view', 0)
        self.pins, self.pin_beams = [], {}
        self.page = 'model' if self.model else 'start'
        self.line, self.s = 0, 0.0
        self.member = 0
        self.sel = None  # (ref, field id or None)
        self.model_tab = 0
        self.tab_selections = [None] * len(MODEL_TABS)
        self.edit = None
        self.popup = None  # [title, options, index, apply]
        self.prompt = None  # dict(title, detail, edit, apply, message)
        self.message, self.error = '', False
        self.menu_index = 0
        self.files = []
        self.combo = None
        self.section, self.section_row = None, 0
        self.help_first = 0
        self.zoom = 0
        self.help_open = False
        self.info = False  # result summary box over the preview (I)
        self.solution, self.problem = None, None
        self.peaks = {}
        self.shape = self.result_cache = None  # (key, value) per solution; see picture()
        self.normalization = None
        self.dline, self.ds, self.third, self.cache = 0, 0.0, 'W', None
        self.dmember = 0
        self.tab, self.note, self.whole, self.quantity = -1, '', False, 0
        self.confirm = None
        self.node_cursor=0
        self.choice_edit=None
        self.node_pick=None
        self.preview_nodes=()
        if self.model:
            self.resolve()  # also completes node metadata
            self.select_point(0, 0.0)


    def remember(self,before):
        """Push a copy of the model taken before a change; keep the last 12."""
        self.undo.append(before)
        if len(self.undo)>UNDO_LIMIT:del self.undo[0]

    def drop_solution(self):
        if self.solution is not None:self.solution.free()
        self.solution,self.problem,self.cache,self.peaks=None,None,None,{}
        self.shape=self.result_cache=None

    def evaluate(self):
        if self.model is None:raise ValueError('Create a model first')
        self.drop_solution()
        try:self.solution=bm.Solution(self.model)
        except (bm.ModelError,ValueError,MemoryError,RuntimeError,ZeroDivisionError) as exc:
            self.problem=exc if isinstance(exc,bm.ModelError) else bm.ModelError(str(exc) or 'Not enough memory')
            item=getattr(self.problem,'item',None)
            if item is not None:
                group,index=item
                kind={'supports':'support','hinges':'hinge','loads':'load'}[group]
                obj=self.model[group][index]
                self.focus((kind,obj),'node' if 'node' in obj else None)
            self.say(str(self.problem),True);return False
        if self.model['members']:self.inspect_member(min(self.dmember,len(self.model['members'])-1),self.ds)
        self.say('Evaluated / F4 plots / F5 results')
        return True

    def cursor_position(self):
        if self.node_cursor is not None and self.model['joints']:return tuple(self.model['joints'][self.node_cursor])
        if self.model['members']:return items.cursor_point(self.model,self.line,self.s)
        return (0.0,0.0)

    def add_node(self):
        if len(self.model['joints'])>=st.MAX_NODES:raise ValueError('Up to %d nodes'%st.MAX_NODES)
        self.snapshot();self.model['joints'].append(list(self.cursor_position()));self.model['joint_types'].append('rigid')
        self.resolve();self.focus(('joint',len(self.model['joints'])-1),'X')
        self.say('New node / type X,Y / angles in degrees')

    def add_member(self):
        if len(self.model['joints'])<2:raise ValueError('Define at least two nodes first')
        if len(self.model['members'])>=bm.MAX_MEMBERS or bm.item_count(self.model)>=bm.MAX_ITEMS:raise ValueError('Member/item limit reached')
        self.snapshot();a=self.node_cursor or 0;b=(a+1)%len(self.model['joints'])
        section=self.model['members'][self.member]['section'] if self.model['members'] else 0
        self.model['members'].append({'a':a,'b':b,'section':section})
        self.resolve();self.focus(('member',len(self.model['members'])-1),'a')
        self.say('[ ] chooses Start / End / Section')

    def add_attachment(self,kind,support_type=None):
        node=self.node_cursor
        if node is None or not self.model['joints']:raise ValueError('Select a reference node first')
        if bm.item_count(self.model)>=bm.MAX_ITEMS:raise ValueError('Item limit reached')
        connected=st.attached(self.model,node)
        if not connected:raise ValueError('J%d has no member: connect it in Member, or place it on one'%(node+1))
        m=next((i for i in connected if self.model['members'][i]['a']==node),self.member if self.member in connected else connected[0] if connected else -1)
        x=st.place(self.model,m,node)[0] if m>=0 else 0.0
        before=items.copy(self.model)
        if kind=='support':obj=bm.support(m,x,bm.SUPPORTS[support_type] if support_type is not None else 'Pin');group='supports'
        elif kind=='dist':
            if m<0:raise ValueError('A distributed load needs a member')
            obj=bm.dist_load(m,0.0,bm.member_length(self.model,m));group='loads'
        else:obj=bm.point_load(m,x) if kind=='point' else bm.moment_load(m,x);group='loads'
        st.bind(self.model,obj,node,m,True)
        self.model[group].append(obj);self.remember(before);self.resolve()
        self.focus(('support' if kind=='support' else 'load',obj),'kind' if kind=='support' else 'P' if kind=='point' else 'M' if kind=='moment' else 'x')
        self.say('At J%d / F6 evaluates'%(node+1))

    def cycle_choice(self,step):
        row=self.current()
        if not row[3]:raise ValueError('No member: connect this node or change From node')
        ref,field=row[4],row[5][0]
        options=items.choices(self.model,ref,field)
        if not options:raise ValueError('No choices defined')
        index=(items.choice_index(self.model,ref,field)+step)%len(options)
        # The explicit section editor shortcut creates a new section; bracket
        # browsing cycles defined sections only.
        if field=='section':index=(items.choice_index(self.model,ref,field)+step)%len(self.model['sections'])
        before=items.copy(self.model);items.set_choice(self.model,ref,field,index);self.remember(before)
        self.changed(ref,field);self.say('Geometry updated / F6 evaluates')

    def preview_choice(self,button,esc):
        q=self.choice_edit
        if esc:
            self.model=q['before'];self.choice_edit=None;self.resolve()
            ref=q['ref']
            if ref[0] not in ('joint','member'):
                group='supports' if ref[0]=='support' else 'loads' if ref[0]=='load' else 'hinges'
                old=q['object_index'];ref=(ref[0],self.model[group][old])
            self.focus(ref,q['field']);return
        c=self.char(button)
        if button in (keys.BUTTON_UP,keys.BUTTON_DOWN) or c in ('[',']'):
            q['index']=(q['index']+(-1 if button==keys.BUTTON_UP or c=='[' else 1))%len(q['options'])
            if not (q['field']=='section' and q['index']==len(self.model['sections'])):
                items.set_choice(self.model,q['ref'],q['field'],q['index']);self.resolve();self.focus(q['ref'],q['field'])
        elif button==keys.BUTTON_CENTER:
            if q['field']=='section' and q['index']==len(self.model['sections']):items.set_choice(self.model,q['ref'],q['field'],q['index'])
            self.remember(q['before']);self.choice_edit=None;self.resolve();self.focus(q['ref'],q['field'])
            if q['field']=='section' and q['index']==len(q['options'])-1:self.open_section(self.model['sections'][q['index']])

    def accept_structure(self,model,node=None):
        before=items.copy(self.model);self.model=model;self.remember(before)
        self.sel=None;self.tab_selections=[None]*4;self.resolve()
        if self.model['joints']:self.focus(('joint',min(node or 0,len(self.model['joints'])-1)))
        self.page='model';self.preview_nodes=();self.node_pick=None

    def pick_node(self,title,nodes,apply):
        if not nodes:raise ValueError('No eligible nodes')
        self.page='model';self.node_pick=nodes
        labels=[items.joint_label(self.model,j) for j in nodes]
        def chosen(index):
            self.preview_nodes=();self.node_pick=None;apply(nodes[index])
        self.popup=[title,labels,0,chosen]

    def merge_menu(self):
        if len(self.model['joints'])<2:raise ValueError('Define two nodes first')
        def source(j):
            self.pick_node('Merge J%d into:'%(j+1),[k for k in range(len(self.model['joints'])) if k!=j],lambda k:self.commit_merge(j,k))
        self.pick_node('Merge: source node',list(range(len(self.model['joints']))),source)

    def commit_merge(self,j,k):
        model,node=st.merge(self.model,j,k)
        self.accept_structure(model,node);self.say('Nodes merged / Z undo / F6 evaluate')

    def split_menu(self):
        if not self.model['members']:raise ValueError('Define a member first')
        self.page='model'
        def member(i):
            candidates=[j for j in range(len(self.model['joints'])) if st.point_on(self.model,j,i) is not None]
            def node(j):
                model=items.copy(self.model);st.split_at(model,i,j);self.accept_structure(model,j)
                self.say('Member split and joined / F6 evaluate')
            self.pick_node('Split L%d at node:'%(i+1),candidates,node)
        self.popup=['Split member', ['L%d'%(i+1) for i in range(len(self.model['members']))],0,member]

    def normalize_menu(self):
        model=st.normalize(self.model)
        # A complete geometry copy is shown before any changes are accepted.
        self.normalization={'before':self.model,'candidate':model}
        self.model=model;self.page='model';self.sel=None;self.preview_nodes=();self.resolve()
        self.say('Preview resolved overlaps / ENTER apply / ESC cancel')

    # ------------------------------------------------------------ state

    def keep(self):
        """What survives closing Beam view while PicoLAB stays open. The undo
        history is left behind: each step is a copy of the whole model. So is
        the solution, and with it the pinned points."""
        from engtools import session
        session.kept['beam'] = {'model': self.model, 'view': self.view}

    def close(self):
        self.keep()
        if self.solution is not None:
            self.solution.free()
            self.solution = None

    def palette(self):
        return theme.system_palette(self.vm)

    def say(self, message, error=False):
        self.message, self.error = message, error

    def snapshot(self):
        self.remember(items.copy(self.model))

    def undo_last(self):
        if not self.undo:
            raise ValueError('Nothing to undo')
        self.model = self.undo.pop()
        self.tab_selections = [None] * len(MODEL_TABS)
        self.resolve()
        self.sel = None
        self.select_point(self.line, self.s)
        self.say('Undone')

    def resolve(self):
        """Invalidate computed response after editing; NEVER call the solver."""
        self.drop_solution()
        self.pins=[];self.pin_beams={}
        if self.model is None:return
        st.ensure(self.model)
        self.view=min(max(0,self.view),max(0,len(self.model['cases'])+len(self.model['combos'])-1))
        runs=bm.lines(self.model)
        self.node_cursor=min(max(0,self.node_cursor),max(0,len(self.model['joints'])-1)) if self.node_cursor is not None else None
        if not runs:
            self.line,self.dline,self.member,self.dmember,self.s,self.ds=0,0,0,0,0.0,0.0
            return
        self.line=min(max(0,self.line),len(runs)-1);self.dline=min(max(0,self.dline),len(runs)-1)
        self.member=min(max(0,self.member),len(self.model['members'])-1)
        self.dmember=min(max(0,self.dmember),len(self.model['members'])-1)
        self.s=min(max(0,self.s),self.line_length(self.line))
        self.inspect_member(self.dmember,self.ds)

    def line_length(self, line):
        return bm.line_offsets(self.model, bm.lines(self.model)[line])[1]

    def extremes(self, line):
        k = (line, self.view)
        if k not in self.peaks:
            self.peaks[k] = self.solution.extremes(line, self.view)
        return self.peaks[k]

    def replace_model(self, model):
        if self.model is not None:
            self.snapshot()
        self.model = model
        self.model_tab, self.tab_selections = 0, [None] * len(MODEL_TABS)
        self.pin_beams = {}
        self.view, self.pins, self.ds, self.dline, self.zoom = len(model['cases']), [], 0.0, 0, 0
        self.line, self.s, self.sel, self.member, self.dmember = 0, 0.0, None, 0, 0
        self.resolve()
        self.select_point(0, 0.0)
        self.page = 'model'

    # ------------------------------------------------------------ model rows

    @staticmethod
    def ref_tab(ref):
        return {'joint':0,'member':1,'hinge':1,'support':2,'load':3}[ref[0]]

    def tab_refs(self,tab=None):
        tab=self.model_tab if tab is None else tab
        if tab==0:return [('joint',i) for i in range(len(self.model['joints']))]
        if tab==1:return [('member',i) for i in range(len(self.model['members']))]+[('hinge',h) for h in self.model['hinges']]
        return [('support' if tab==2 else 'load',v) for v in self.model['supports' if tab==2 else 'loads']]

    def switch_model_tab(self, step):
        self.tab_selections[self.model_tab] = self.sel
        self.model_tab = (self.model_tab + step) % len(MODEL_TABS)
        refs = self.tab_refs()
        selected = self.tab_selections[self.model_tab]
        if selected is None or not any(items.same(selected[0], ref) for ref in refs):
            selected = (refs[0], None) if refs else None
        # A category change restores its row, but never moves the Add target.
        self.sel = selected

    def cursor_member(self):
        if not self.model['members']:return None
        if self.node_cursor is not None:
            connected=st.attached(self.model,self.node_cursor)
            if self.member in connected:return self.member
            if connected:return connected[0]
        return min(max(0,self.member),len(self.model['members'])-1)

    def cursor_label(self):
        if self.node_cursor is not None and self.model['joints']:
            return 'J%d'%(self.node_cursor+1)
        m=self.cursor_member()
        return 'L%d x=%s'%(m+1,units.number(self.s-items.line_of(self.model,m)[1],4)) if m is not None else 'No nodes'

    def cycle_member(self,step):
        if not self.model['members']:return
        member=((self.cursor_member() or 0)+step)%len(self.model['members'])
        line,offset=items.line_of(self.model,member)
        self.member=member;self.select_point(line,offset)
        if self.model_tab==1:self.focus(('member',member))

    def move_point(self,step):
        if not self.model['members']:return
        runs=bm.lines(self.model);member=self.cursor_member()
        line,offset=items.line_of(self.model,member,runs);end=offset+bm.member_length(self.model,member)
        points=[s for s in items.stops(self.model,line,runs) if offset-st.EPS<=s<=end+st.EPS]
        i=min(range(len(points)),key=lambda j:abs(points[j]-self.s))
        self.member=member;self.select_point(line,points[min(max(i+step,0),len(points)-1)])

    def rows(self):
        """(kind, label, value, editable, ref, field) in the selected tab."""
        out = []
        expanded = self.sel[0] if self.sel and self.sel[1] is not None else None
        refs = self.tab_refs()
        if expanded is not None:
            refs = [ref for ref in refs if items.same(ref, expanded)]
        for ref in refs:
            out.append(('head', items.title(self.model, ref), '', True, ref, None))
            if items.same(ref, expanded):
                for f in items.fields(self.model, ref):
                    out.append(('field', f[1], items.text(self.model, ref, f), f[4], ref, f))
        return out

    def row_index(self, rows):
        if not self.sel:
            return -1
        ref, field = self.sel
        for i, row in enumerate(rows):
            if items.same(row[4], ref) and (row[5][0] if row[5] else None) == field:
                return i
        for i, row in enumerate(rows):
            if items.same(row[4], ref):
                return i
        return 0 if rows else -1

    def select_point(self,line,s):
        runs=bm.lines(self.model)
        if not runs:
            refs=self.tab_refs();self.sel=(refs[0],None) if refs else None
            return
        line=min(max(line,0),len(runs)-1);points=items.stops(self.model,line,runs)
        self.line=line;self.s=min(points,key=lambda p:abs(p-s))
        m,x=items.locate(self.model,line,self.s,runs);self.member=m
        here=bm.point(self.model,m,x)
        self.node_cursor=next((j for j,p in enumerate(self.model['joints']) if items.same_point(p,here)),None)
        refs=self.tab_refs();local=items.items_at(self.model,line,self.s,runs)
        if self.model_tab==0 and self.node_cursor is not None:self.sel=(('joint',self.node_cursor),None)
        elif not self.sel or not any(items.same(self.sel[0],r) for r in refs):
            chosen=next((r for r in refs if any(items.same(r,q) for q in local)),refs[0] if refs else None)
            self.sel=(chosen,None) if chosen else None
        self.tab_selections[self.model_tab]=self.sel

    def focus(self,ref,field=None):
        kind,obj=ref;tab=self.ref_tab(ref)
        if tab!=self.model_tab:self.tab_selections[self.model_tab]=self.sel;self.model_tab=tab
        self.sel=(ref,field);self.tab_selections[self.model_tab]=self.sel
        if kind=='joint':
            self.node_cursor=obj;connected=st.attached(self.model,obj)
            if not connected:return
            m=self.member if self.member in connected else connected[0]
            x=st.place(self.model,m,obj)[0]
        elif kind=='member':
            m=obj;edge=self.model['members'][m];self.node_cursor=edge['b'] if field=='b' else edge['a']
            x=bm.member_length(self.model,m) if field=='b' else 0.0
        else:
            self.node_cursor=obj.get('node');m=obj['m'];x=obj['x2'] if field=='x2' else obj['x']
            if not 0<=m<len(self.model['members']):return
        self.member=m;self.line,offset=items.line_of(self.model,m);self.s=offset+x

    def move_row(self, step):
        rows = self.rows()
        if not rows:
            return
        index = min(max(self.row_index(rows) + step, 0), len(rows) - 1)
        row = rows[index]
        self.focus(row[4], row[5][0] if row[5] else None)

    def current(self):
        rows = self.rows()
        index = self.row_index(rows)
        return rows[index] if index >= 0 else None

    def begin_edit(self,first=None):
        row=self.current()
        if row is None or row[0]!='field' or not row[3]:raise ValueError('Choose an editable property')
        ref,field=row[4],row[5]
        if field[2]=='choice':
            group='supports' if ref[0]=='support' else 'loads' if ref[0]=='load' else 'hinges'
            object_index=next((i for i,o in enumerate(self.model.get(group,())) if o is ref[1]),0)
            self.choice_edit={'ref':ref,'object_index':object_index,'field':field[0],'before':items.copy(self.model),
                              'index':items.choice_index(self.model,ref,field[0]),'options':items.choices(self.model,ref,field[0])}
            self.say('[ ] preview / ENTER apply / ESC cancel');return
        if first is None:
            value=items.get(self.model,ref,field[0]);shown=value if field[3]=='deg' else units.from_si(value,field[3])
            self.edit=LineEdit(units.number(shown,7),64)
        else:
            self.edit=LineEdit('',64);self.edit.key(self.vm,first)

    def commit_edit(self):
        row = self.current()
        ref, f = row[4], row[5]
        value = beam_number(self.edit.text)
        before = items.copy(self.model)
        items.set_number(self.model, ref, f[0], f[3], value)
        self.remember(before)
        self.edit = None
        self.changed(ref, f[0])

    def changed(self, ref, field=None):
        self.resolve()
        self.focus(ref, field)

    def open_section(self, section):
        self.section, self.section_row, self.page = section, 1, 'section'

    # ------------------------------------------------------------ keys

    def run(self, button):
        if button == keys.BUTTON_NONE:
            return False
        try:
            self.handle(button)
        except (ValueError, TypeError, KeyError, IndexError, ZeroDivisionError, OverflowError, RuntimeError, OSError, MemoryError) as exc:
            self.say(str(exc) or 'Not possible here', True)
        return True

    @property
    def footer_height(self):
        return 12

    def properties_rect(self):
        top = render.MODEL_PROPERTIES_TOP if self.page == 'model' else render.PROPERTIES_TOP
        return (8,top,int(self.vm.draw.size.x)-16,int(self.vm.draw.size.y)-self.footer_height-top-3)

    def menu_rect(self):
        """Add/choice menus and prompts replace the lower box; the preview stays visible."""
        return self.properties_rect() if self.page in ('model','section') else None

    def handle(self, button):
        if button==keys.BUTTON_F9:
            if self.help_open:self.help_open=False
            else:self.open_help()
            return
        esc = button == self.vm.input_manager._key_esc
        if self.help_open:
            self.key_help(button,esc)
            return
        if self.prompt is not None:
            result = self.prompt['edit'].key(self.vm, button)
            if result == 'cancel':
                self.prompt = None
            elif result == 'commit':
                try:
                    self.prompt['apply'](self.prompt['edit'].text)
                    self.prompt = None
                except ValueError as exc:
                    self.prompt['message'] = str(exc)
            return
        if self.normalization is not None:
            q=self.normalization
            if esc:self.model=q['before'];self.normalization=None;self.resolve();self.say('Resolution cancelled')
            elif button==keys.BUTTON_CENTER:
                self.model=q['before'];self.normalization=None;self.accept_structure(q['candidate']);self.say('Overlap resolved / F6 evaluates')
            return
        if self.choice_edit is not None:
            self.preview_choice(button,esc);return
        if self.popup is not None:
            title, options, index, apply = self.popup
            if esc:
                self.popup = None
                self.node_pick=None;self.preview_nodes=()
            elif button in (keys.BUTTON_UP, keys.BUTTON_DOWN) or self.char(button) in ('[',']'):
                self.popup[2]=(index+(1 if button==keys.BUTTON_DOWN or self.char(button)==']' else -1))%len(options)
            elif button == keys.BUTTON_CENTER:
                self.popup = None
                apply(index)
            return
        if self.edit is not None:
            result = self.edit.key(self.vm, button)
            if result == 'cancel':
                self.edit = None
            elif result is not None:
                if self.page == 'section':
                    self.commit_section()
                else:
                    self.commit_edit()
                if result in ('up', 'down'):
                    if self.page == 'section':
                        self.move_section(-1 if result == 'up' else 1)
                    else:
                        self.move_row(-1 if result == 'up' else 1)
            return
        self.message, self.error = '', False
        if button==keys.BUTTON_F6:
            self.evaluate();return
        page = {keys.BUTTON_F3: 'options', keys.BUTTON_F4: 'diagrams',
                keys.BUTTON_F5: 'results'}.get(button)
        if page and self.model is not None:
            if page in ('options', 'results'):
                self.menu_index = 0
            if page == 'diagrams' and self.page == 'model' and self.model['members']:
                self.inspect_member(self.cursor_member(), self.s)
            self.page = page
            return
        if self.vm.input_manager.button_to_char(button) == '?':
            self.open_help()
            return
        if button==keys.BUTTON_F1 and self.page=='model':
            if self.model_tab==0:self.add_node()
            elif self.model_tab==1:self.add_member()
            else:
                choices=ADD_OPTIONS[self.model_tab]
                def add(index):self.add_attachment(choices[index][1],index if self.model_tab==2 else None)
                self.popup=['Add '+MODEL_TABS[self.model_tab]+' / '+self.cursor_label(),[v[0] for v in choices],0,add]
            return
        getattr(self, 'key_' + self.page)(button, esc)

    def char(self, button):
        c = self.vm.input_manager.button_to_char(button)
        return c.lower() if c else ''

    def remove_selected(self):
        if self.sel is None:raise ValueError('Nothing selected')
        before=items.copy(self.model)
        items.delete(self.model,self.sel[0]);self.remember(before)
        self.tab_selections=[None]*len(MODEL_TABS);self.sel=None
        self.resolve()
        refs=self.tab_refs()
        if refs:self.focus(refs[0])
        self.say('Removed / Z undo / F6 evaluate')

    def key_model(self,button,esc):
        if esc:
            if self.sel and self.sel[1] is not None:self.focus(self.sel[0])
            else:self.vm.back()
            return
        c=self.char(button)
        if button==keys.BUTTON_F2:self.remove_selected()
        elif button in (keys.BUTTON_LEFT,keys.BUTTON_RIGHT):self.switch_model_tab(-1 if button==keys.BUTTON_LEFT else 1)
        elif button in (keys.BUTTON_UP,keys.BUTTON_DOWN):self.move_row(-1 if button==keys.BUTTON_UP else 1)
        elif c in ('[',']'):
            row=self.current()
            if row and row[0]=='field' and row[5][2]=='choice':self.cycle_choice(-1 if c=='[' else 1)
            else:self.cycle_member(-1 if c=='[' else 1)
        elif button==keys.BUTTON_TAB:self.cycle_member(1)
        elif c in (',','.','<','>'):self.move_point(1 if c in ('.','>') else -1)
        elif button==keys.BUTTON_CENTER:
            row=self.current()
            if row is not None and row[0]=='head':
                fields=items.fields(self.model,row[4]);self.focus(row[4],fields[0][0])
            else:self.begin_edit()
        elif c=='e' and self.vm.input_manager.was_capitalized:
            m=self.sel[0][1] if self.sel and self.sel[0][0]=='member' else self.cursor_member()
            if m is None:raise ValueError('Select a member first')
            self.open_section(self.model['sections'][self.model['members'][m]['section']])
        elif c=='z':self.undo_last()
        elif c=='i':self.info=not self.info
        elif c in ('+','='):self.zoom=min(self.zoom+1,len(ZOOMS)-1)
        elif c=='-':self.zoom=max(0,self.zoom-1)
        elif erase_key(self.vm,button):
            row=self.current()
            if row and row[0]=='field' and row[5][2]=='num':self.begin_edit();self.edit.key(self.vm,button)
        elif c and (c.isdigit() or c in '-.('):self.begin_edit(button)

    # ------------------------------------------------------------ section editor

    def section_rows(self):
        return items.section_fields(self.section)

    def move_section(self, step):
        rows = self.section_rows()
        self.section_row = min(max(self.section_row + step, 0), len(rows) - 1)

    def commit_section(self):
        row = self.section_rows()[self.section_row]
        value = beam_number(self.edit.text)
        before = items.copy(self.model)
        items.section_number(self.section, row[0], row[3], value)
        self.remember(before)
        self.edit = None
        self.resolve()

    def key_section(self, button, esc):
        if esc:
            self.page = 'model'
            return
        rows = self.section_rows()
        self.section_row = min(self.section_row, len(rows) - 1)
        row = rows[self.section_row]
        c = self.char(button)
        if button in (keys.BUTTON_UP, keys.BUTTON_DOWN):
            self.move_section(-1 if button == keys.BUTTON_UP else 1)
        elif button == keys.BUTTON_CENTER or (c and (c.isdigit() or c in '.(') and row[2] == 'num') or \
                (erase_key(self.vm, button) and row[2] == 'num'):
            if not row[4]:
                raise ValueError('Set by the material: choose Custom to type it')
            if row[2] == 'text':
                section = self.section

                def apply(value):
                    self.snapshot()
                    items.rename_section(self.model, section, value)
                self.prompt = {'title': 'Section name', 'detail': 'Up to 8 letters, for example IPE300 or Col.',
                               'edit': LineEdit(section['name'], 8), 'apply': apply, 'message': ''}
            elif row[2] == 'choice':
                section = self.section

                def choose(index, field=row[0]):
                    self.snapshot()
                    items.section_choice(section, field, index)
                    self.resolve()
                options = items.section_choices(row[0])
                current = section['material'] if row[0] == 'material' else bm.SHAPES.index(section['shape'])
                self.popup = [row[1], options, current, choose]
            elif button == keys.BUTTON_CENTER:
                value = units.from_si(items.section_get(self.section, row[0]), row[3])
                self.edit = LineEdit(units.number(value, 7), 16)
            else:
                self.edit = LineEdit(units.number(units.from_si(items.section_get(self.section, row[0]), row[3]), 7)
                                     if erase_key(self.vm, button) else '', 16)
                self.edit.key(self.vm, button)

    # ------------------------------------------------------------ diagrams

    def plot_bounds(self):
        line, start = items.line_of(self.model, self.dmember)
        return start, start + bm.member_length(self.model, self.dmember)

    def inspect_member(self, member, s=None):
        self.dmember = member
        self.dline, start = items.line_of(self.model, member)
        end = start + bm.member_length(self.model, member)
        self.ds = start if s is None else min(max(s, start), end)
        self.cache, self.tab, self.note = None, -1, ''

    def cycle_plot_member(self, step):
        self.inspect_member((self.dmember + step) % len(self.model['members']))

    def plot_title(self):
        start, end = self.plot_bounds()
        return 'L%d/%d  x=%s' % (self.dmember+1, len(self.model['members']), units.show(self.ds-start,'m'))

    def key_diagrams(self, button, esc):
        if esc:
            self.page = 'model'
            return
        if self.solution is None:
            self.say('F6 Evaluate computes plots',True);return
        start, end = self.plot_bounds()
        c = self.char(button)
        step = (end-start) / (render.RIGHT - render.LEFT)
        if button in (keys.BUTTON_LEFT, keys.BUTTON_RIGHT) or c in (',', '.', '<', '>'):
            sign = -1 if button == keys.BUTTON_LEFT or c in (',', '<') else 1
            self.ds = min(max(self.ds + sign * step * (10 if c else 1), start), end)
            self.note, self.tab = '', -1
        elif button in (keys.BUTTON_UP, keys.BUTTON_DOWN):
            points = [s for s in items.stops(self.model, self.dline) if start <= s <= end]
            if button == keys.BUTTON_DOWN:
                later = [p for p in points if p > self.ds + 1e-9]
                self.ds = later[0] if later else end
            else:
                earlier = [p for p in points if p < self.ds - 1e-9]
                self.ds = earlier[-1] if earlier else start
            self.note, self.tab = '', -1
        elif button == keys.BUTTON_TAB:
            peaks = self.peak_list()
            self.tab = (self.tab + 1) % len(peaks)
            label, s, q = peaks[self.tab]
            self.ds, self.note = s, label
        elif button == keys.BUTTON_CENTER:
            if len(self.pins) >= 8:
                raise ValueError('Up to 8 pinned points; remove some in F5')
            if not any(line == self.dline and abs(s - self.ds) < 1e-9 for line, s in self.pins):
                self.pins.append((self.dline, self.ds))
                self.pins.sort()
            self.pin_beams[(self.dline,self.ds)] = self.dmember
            self.note = 'Pinned: see F5 Results'
        elif c == 'v' or button == keys.BUTTON_SPACE:
            self.next_view()
        elif c == 'd':
            if self.whole:
                self.quantity = (self.quantity + 1) % len(render.OVERVIEW)
            else:
                order = ('W', 'T', 'N', 'U') if not bm.is_straight_beam(self.model) else ('W', 'T', 'U')
                self.third = order[(order.index(self.third) + 1) % len(order)] if self.third in order else 'W'
                self.cache = None
        elif c in ('m', '[', ']'):
            self.cycle_plot_member(-1 if c == '[' else 1)
        elif c == 'f':
            self.whole = not self.whole

    def next_view(self):
        self.view = (self.view + 1) % (len(self.model['cases']) + len(self.model['combos']))
        self.cache = None
        self.tab = -1

    def peak_list(self):
        key = (self.dline,self.view,self.dmember)
        if key not in self.peaks:
            self.peaks[key] = self.solution.extremes(self.dline,self.view,self.dmember)
        ext = self.peaks[key]
        start, end = self.plot_bounds()
        out = []
        names = (('M', 'moment', 'kNm'), ('V', 'shear', 'kN'), ('N', 'normal', 'kN'), ('W', 'deflection', 'mm'),
                 ('U', 'axial displ.', 'mm'), ('T', 'slope', 'mrad'))
        for q, name, unit in names:
            hi, sh, lo, sl = ext[q]
            if abs(hi) > 1e-6:
                out.append(('max %s %s at %s m' % (name, units.show(hi, unit), units.number(sh-start)), sh, q))
            if abs(lo) > 1e-6:
                out.append(('min %s %s at %s m' % (name, units.show(lo, unit), units.number(sl-start)), sl, q))
        return out or [('No load effects in this view', start, 'M')]

    # ------------------------------------------------------------ results

    def key_results(self, button, esc):
        if esc:
            self.page = 'model'
            return
        rows = self.result_rows()
        selectable = self.result_index(rows)
        if not selectable:
            return
        if button in (keys.BUTTON_UP, keys.BUTTON_DOWN):
            at = selectable.index(self.menu_index) + (1 if button == keys.BUTTON_DOWN else -1)
            self.menu_index = selectable[at % len(selectable)]
            return
        action = rows[self.menu_index][4]
        if self.char(button) == 'v':
            self.next_view()
        elif button == keys.BUTTON_CENTER and action:
            if action[0] == 'view':
                self.next_view()
            elif action[0] in ('goto', 'pin'):
                member = action[3] if len(action)>3 else items.locate(self.model,action[1],action[2])[0]
                self.inspect_member(member,action[2])
                self.page, self.whole = 'diagrams', False
        elif (button == keys.BUTTON_F2 or erase_key(self.vm, button)) and action and action[0] == 'pin':
            self.pins.remove((action[1], action[2]))
            self.pin_beams.pop((action[1],action[2]),None)

    def result_index(self, rows):
        """Selectable rows (headings are not); keeps menu_index on one."""
        selectable = [i for i, r in enumerate(rows) if r[1] is not None or r[2]]
        if selectable and self.menu_index not in selectable:
            self.menu_index = selectable[0]
        return selectable

    def where(self, X, Y):
        if bm.is_straight_beam(self.model):
            return 'x = ' + units.show(X - bm.bounds(self.model)[0], 'm')
        return '(%s, %s) m' % (units.number(X), units.number(Y))

    def result_rows(self):
        """(label, value, detail, color, action) rows for F5. Both the keys
        and the frame read them, so they are built once per solution, view
        and set of pinned points."""
        sol = self.solution
        if sol is None:
            return [('Not evaluated',None,'F6 Evaluate computes results' if self.problem is None else str(self.problem),None,None)]
        key = (self.view, sol.view_names()[self.view], tuple(self.pins), tuple(self.pin_beams.get(p) for p in self.pins))
        if self.result_cache is None or self.result_cache[0] != key:
            self.result_cache = (key, self.build_result_rows(sol))
        return self.result_cache[1]

    def build_result_rows(self, sol):
        straight = bm.is_straight_beam(self.model)
        rows = [('View', sol.view_names()[self.view][:16], 'ENTER or V: next case or combination', None, ('view',)),
                ('Reactions', None, '', None, None)]
        reactions = sol.reactions(self.view)
        for n, (support, fx, fy, mz) in enumerate(reactions):
            X, Y = bm.point(self.model, support['m'], support['x'])
            detail = support['kind'] + ' at ' + self.where(X, Y)
            flags = bm.SUPPORT_FLAGS[support['kind']]
            if 'x' in flags or (support['kind'] == 'Spring' and support['kx'] > 0):
                if not straight or abs(fx) > 1e-6:
                    detail += '  H ' + units.show(fx, 'kN')
            if 'r' in flags or (support['kind'] == 'Spring' and support['kr'] > 0):
                detail += '  M ' + units.show(mz, 'kNm')
            value = units.show(fy, 'kN') if 'y' in flags or support['kind'] == 'Spring' else '--'
            line, offset = items.line_of(self.model, support['m'])
            rows.append(('R%d' % (n + 1), value, detail, None, ('goto', line, offset + support['x'])))
        ax, ay = sol.applied(self.view)
        tx = sum(r[1] for r in reactions)
        ty = sum(r[2] for r in reactions)
        size = max(1.0, abs(ax), abs(ay))
        ok = abs(tx + ax) <= 1e-4 * size and abs(ty + ay) <= 1e-4 * size
        detail = 'Sum R %s, loads %s' % (units.show(ty, 'kN'), units.show(-ay, 'kN'))
        if not straight:
            detail = 'R (%s, %s) kN, loads (%s, %s)' % (units.number(tx / 1e3), units.number(ty / 1e3),
                                                         units.number(-ax / 1e3), units.number(-ay / 1e3))
        rows.append(('Equilibrium', 'OK' if ok else 'CHECK', detail, None if ok else theme.ERROR, None))
        names = (('M', 'moment', 'kNm'), ('V', 'shear', 'kN'), ('W', 'deflection', 'mm'), ('T', 'slope', 'mrad'))
        if not straight:
            names = (('M', 'moment', 'kNm'), ('V', 'shear', 'kN'), ('N', 'normal force', 'kN'), ('W', 'deflection', 'mm'),
                     ('U', 'axial displacement', 'mm'))
        for line in range(len(sol.lines)):
            run = sol.lines[line]
            heading = 'Peaks' if straight else 'Members ' + ', '.join(str(m + 1) for m in run)
            rows.append((heading, None, '', None, None))
            ext = self.extremes(line)
            shown = names
            if straight and max(abs(ext['U'][0]), abs(ext['U'][2])) > 1e-9:
                shown = names + (('U', 'axial displacement', 'mm'),)  # axial loads on a straight beam
            for q, name, unit in shown:
                hi, sh, lo, sl = ext[q]
                rows.append(('Max ' + name, units.show(hi, unit), 'at s = ' + units.show(sh, 'm'), None, ('goto', line, sh)))
                rows.append(('Min ' + name, units.show(lo, unit), 'at s = ' + units.show(sl, 'm'), None, ('goto', line, sl)))
            sigma, ss, m = sol.stress(line, self.view)
            rows.append(('Max stress', units.show(sigma, 'MPa', 3), 'N/A + M/W at s = %s, member %d' % (units.show(ss, 'm'), m + 1),
                         None, ('goto', line, ss)))
        ratio = sol.deflection_ratio(self.view)
        if ratio:
            rows.append(('Span / deflection', 'L/%d' % int(ratio[0]), 'worst span ' + units.show(ratio[1], 'm'), None, None))
        if self.pins:
            rows.append(('Pinned points', None, '', None, None))
            for line, s in self.pins:
                if line >= len(sol.lines):
                    continue
                member = self.pin_beams.get((line,s))
                if member is None or member not in sol.lines[line]:
                    member = items.locate(self.model,line,s)[0]
                member_line, offset = items.line_of(self.model,member)
                x = min(max(s-offset,0.0),bm.member_length(self.model,member))
                V, M, T, W, N, U = sol.at(member,x,self.view)
                label = 'B%d x = ' % (member+1) + units.show(x, 'm')
                rows.append((label, units.show(M, 'kNm'), 'V ' + units.show(V, 'kN') + '  w ' + units.show(W, 'mm') +
                             ('' if straight else '  N ' + units.show(N, 'kN')) + '  F2 unpins', None, ('pin', line, s, member)))
        info = sol.info
        rows.append(('Solver', None, '', None, None))
        rows.append(('Equations', str(info['equations']), '%s precision, %d KB' % (info['precision'], info['bytes'] // 1024 + 1),
                     None, None))
        return rows

    # ------------------------------------------------------------ menus

    def key_options(self,button,esc):
        if esc:self.page='model';return
        if self.menu(button,len(OPTIONS)) or button!=keys.BUTTON_CENTER:return
        option=OPTIONS[self.menu_index]
        if option=='New beam':self.page,self.menu_index='start',0
        elif option=='New blank structure':self.replace_model(bm.empty_model([],[]))
        elif option=='Merge nodes':self.merge_menu()
        elif option=='Split at node':self.split_menu()
        elif option=='Resolve overlaps':self.normalize_menu()
        elif option in ('Load cases','Combinations'):self.page,self.menu_index=('cases' if option=='Load cases' else 'combos'),0
        elif option=='Self-weight':
            self.snapshot();current=self.model.get('selfweight');n=0 if current is None else current+1
            self.model['selfweight']=n if n<len(self.model['cases']) else None;self.resolve()
        elif option=='Save':self.ask_save()
        elif option=='Open':self.files=cases.list_cases(self.vm.storage);self.page,self.menu_index='open',0
        elif option in ('Export CSV (Eggcel)','Export full CSV'):self.export(compact=option=='Export CSV (Eggcel)')
        else:self.open_help()

    def menu(self, button, count):
        if button in (keys.BUTTON_UP, keys.BUTTON_DOWN) and count:
            self.menu_index = (self.menu_index + (1 if button == keys.BUTTON_DOWN else -1)) % count
            return True
        return False

    def key_start(self,button,esc):
        count=len(bm.TEMPLATES)+3
        if esc:
            if self.model is None:self.vm.back()
            else:self.page='options'
            return
        if self.menu(button,count) or button!=keys.BUTTON_CENTER:return
        if self.menu_index==len(bm.TEMPLATES)+2:
            self.files=cases.list_cases(self.vm.storage);self.page='open';self.menu_index=0
        else:
            m=bm.template(self.menu_index) if self.menu_index<len(bm.TEMPLATES) else st.bridge() if self.menu_index==len(bm.TEMPLATES) else bm.empty_model([],[])
            self.replace_model(m)
            self.say('Geometry only / F6 evaluates')

    def key_open(self, button, esc):
        if esc:
            self.page = 'options' if self.model else 'start'
            self.menu_index = 0
            return
        if self.menu(button, len(self.files)) or button != keys.BUTTON_CENTER or not self.files:
            return
        name = self.files[self.menu_index]
        loaded = bm.upgrade(cases.load_case(self.vm.storage, name, 'beams'))
        loaded['name'] = name
        loaded.setdefault('selfweight', None)
        self.replace_model(loaded)  # resolve() completes node metadata
        self.say('Opened ' + name)

    def key_cases(self, button, esc):
        names = self.model['cases']
        if esc:
            self.page, self.menu_index = 'options', OPTIONS.index('Load cases')
            return
        if self.menu(button, len(names) + 1):
            return
        index = self.menu_index = min(self.menu_index, len(names))
        if button == keys.BUTTON_CENTER:
            if index == len(names):
                self.snapshot()
                items.add_case(self.model, 'Case %d' % (len(names) + 1))
                if self.view >= len(names) - 1:
                    self.view += 1  # stay on the same combination
                self.resolve()
                self.rename_case(len(names) - 1)
            else:
                self.rename_case(index)
        elif (button == keys.BUTTON_F2 or erase_key(self.vm, button)) and index < len(names):
            self.snapshot()
            try:
                items.remove_case(self.model, index)
            except ValueError:
                self.undo.pop()
                raise
            if self.view > index:
                self.view -= 1
            elif self.view == index:
                self.view = 0
            self.resolve()
            self.menu_index = min(index, len(self.model['cases']))

    def rename_case(self, index):
        def apply(value):
            value = value.strip()
            if not value:
                raise ValueError('Type a name')
            self.model['cases'][index] = value[:16]
        self.prompt = {'title': 'Load case name', 'detail': 'For example Dead, Live, Snow or Wind.',
                       'edit': LineEdit(self.model['cases'][index], 16), 'apply': apply, 'message': ''}

    def key_combos(self, button, esc):
        combos = self.model['combos']
        if esc:
            self.page, self.menu_index = 'options', OPTIONS.index('Combinations')
            return
        if self.menu(button, len(combos) + 1):
            return
        index = self.menu_index = min(self.menu_index, len(combos))
        if button == keys.BUTTON_CENTER:
            if index == len(combos):
                self.snapshot()
                items.add_combo(self.model)
                self.resolve()
            self.combo, self.page, self.menu_index = self.model['combos'][index], 'combo', 0
        elif (button == keys.BUTTON_F2 or erase_key(self.vm, button)) and index < len(combos):
            self.snapshot()
            del combos[index]
            self.resolve()
            self.menu_index = min(index, len(combos))

    def combo_rows(self):
        combo = self.combo
        rows = [('head', 'Combination', '', True, None, None),
                ('field', 'Name', combo['name'], True, None, ('name',))]
        for i, name in enumerate(self.model['cases']):
            rows.append(('field', name + ' factor', units.number(combo['factors'][i], 4), True, None, ('factor', i)))
        return rows

    def key_combo(self, button, esc):
        rows = self.combo_rows()
        if esc:
            self.page = 'combos'
            self.menu_index = self.model['combos'].index(self.combo)
            return
        index = min(max(self.menu_index, 1), len(rows) - 1)
        if button in (keys.BUTTON_UP, keys.BUTTON_DOWN):
            self.menu_index = min(max(index + (1 if button == keys.BUTTON_DOWN else -1), 1), len(rows) - 1)
            return
        field = rows[index][5]
        c = self.char(button)
        if field[0] == 'name' and button == keys.BUTTON_CENTER:
            def apply(value, combo=self.combo):
                value = value.strip()
                if not value:
                    raise ValueError('Type a name')
                combo['name'] = value[:16]
            self.prompt = {'title': 'Combination name', 'detail': 'For example ULS or SLS.',
                           'edit': LineEdit(self.combo['name'], 16), 'apply': apply, 'message': ''}
        elif field[0] == 'factor' and (button == keys.BUTTON_CENTER or (c and (c.isdigit() or c in '-.'))):
            i = field[1]
            if button == keys.BUTTON_CENTER:
                edit = LineEdit(units.number(self.combo['factors'][i], 7), 16)
            else:
                edit = LineEdit('', 16)
                edit.key(self.vm, button)

            def apply(value, combo=self.combo, i=i):
                factor = beam_number(value)
                self.snapshot()
                combo['factors'][i] = factor
                self.resolve()
            self.prompt = {'title': self.model['cases'][i] + ' factor',
                           'detail': 'Multiplies every load in this case. 0 leaves it out.',
                           'edit': edit, 'apply': apply, 'message': ''}

    def open_help(self):
        self.help_open, self.help_first = True, 0

    def key_help(self, button, esc):
        if esc or button in (keys.BUTTON_F9, keys.BUTTON_CENTER):
            self.help_open = False
            return
        capacity = render.help_capacity(int(self.vm.draw.size.y)-self.footer_height)
        last = max(0, len(HELP) - capacity)
        if button in (keys.BUTTON_UP, keys.BUTTON_DOWN):
            self.help_first += 1 if button == keys.BUTTON_DOWN else -1
        elif button in (keys.BUTTON_LEFT, keys.BUTTON_RIGHT):
            self.help_first += capacity if button == keys.BUTTON_RIGHT else -capacity
        elif button == keys.BUTTON_CTRL_UP:self.help_first = 0
        elif button in (keys.BUTTON_END,keys.BUTTON_CTRL_DOWN):self.help_first = last
        self.help_first = min(max(self.help_first, 0), last)

    # ------------------------------------------------------------ files

    def ask_save(self):
        def apply(value):
            name = cases.clean_name(value)
            if name != self.model.get('name') and cases.exists(self.vm.storage, name) and self.confirm != name:
                self.confirm = name
                raise ValueError(name + ' exists: ENTER again replaces it')
            self.model['name'] = name
            cases.save_case(self.vm.storage, name, self.model)
            self.confirm = None
            self.say('Saved ' + name)
        self.confirm = None
        self.prompt = {'title': 'Save beam as', 'detail': 'Saved to ' + cases.CASE_DIRECTORY + '. Letters, digits, - and _.',
                       'edit': LineEdit(self.model.get('name') or 'beam-1', cases.NAME_LIMIT), 'apply': apply, 'message': ''}

    def export(self, compact=True):
        if self.solution is None:
            raise ValueError('Press F6 Evaluate before exporting')
        sol = self.solution

        def rows():
            for line in range(len(sol.lines)):
                S, V, M, T, W, N, U, starts = sol.samples(line, self.view)
                # Seven columns plus a header fit Eggcel's 512-cell budget:
                # 72 data rows + 1 header = 511 cells, shared across all runs.
                count = min(len(S), 72 // len(sol.lines) + (line < 72 % len(sol.lines))) if compact else len(S)
                for j in range(count):
                    i = j * (len(S) - 1) // (count - 1) if count > 1 else 0
                    yield (line + 1, S[i], V[i] / 1e3, M[i] / 1e3, N[i] / 1e3, T[i] * 1e3, W[i] * 1e3)
        stem = (self.model.get('name') or 'beam') + ('-eggcel' if compact else '-full')
        path = cases.free_path(self.vm.storage, cases.EXPORT_DIRECTORY, stem, 'csv')
        cases.export_csv(self.vm.storage, path, ('line', 's_m', 'V_kN', 'M_kNm', 'N_kN', 'slope_mrad', 'w_mm'), rows())
        self.say('Exported ' + path.rsplit('/', 1)[1] + (' (sampled)' if compact else ' (full)'))

    # ------------------------------------------------------------ drawing

    def draw(self):
        draw=self.vm.draw;p=self.palette()
        bottom=int(draw.size.y)-self.footer_height
        draw.fill_screen(p.BG)
        if self.help_open:
            render.chrome(draw,p,'Help',title='BeamView',fallback=('modules','structural','BeamView'))
            render.help_box(draw,p,HELP,self.help_first,bottom)
            draw.swap()
            return
        if self.page in MENU_PAGES:
            rows,subtitle=self.menu_rows()
            render.menu(draw,p,rows,self.menu_index,subtitle,bottom)
        elif self.page=='model':
            subtitle=self.draw_model(draw,p)
        elif self.page=='section':
            subtitle=self.draw_section(draw,p)
        else:
            subtitle='Beam / '+self.page
            render.panel(draw,p,(8,43,int(draw.size.x)-16,bottom-46),'' if self.page=='diagrams' else self.page.upper())
            bounded=render.Viewport(draw,(10,44,int(draw.size.x)-10,bottom-5))
            if self.page=='diagrams':
                subtitle=self.draw_diagrams(bounded,p)
            elif self.page=='results':
                rows=self.result_rows();self.result_index(rows)
                render.results(bounded,p,[r[:4] for r in rows],self.menu_index,67,bottom-7)
            elif self.page=='combo':
                render.form(bounded,p,[r[:4] for r in self.combo_rows()],max(1,self.menu_index),None,70,bottom-7)

        render.chrome(draw,p,subtitle.replace('Beam / ',''),self.message,self.error,
                      title='BeamView',fallback=('modules','structural','BeamView'),
                      title_bar=self.page!='model')
        box=self.menu_rect()
        if self.popup is not None:
            title,options,index,apply=self.popup
            render.popup(draw,p,title,options,index,box)
        if self.choice_edit is not None:
            q=self.choice_edit
            render.popup(draw,p,q['field'].upper()+' / [ ] preview',q['options'],q['index'],box)
        if self.prompt is not None:self.draw_prompt(draw,p)
        draw.swap()

    def draw_prompt(self,draw,p):
        q=self.prompt
        box=self.menu_rect()
        render.prompt(draw,p,q['title'],q['detail'],q['edit'],q['message'] or 'ENTER saves  ESC cancels',
                      bool(q['message']),box)

    def menu_rows(self):
        if self.page=='start':
            return [(n,d) for n,d in bm.TEMPLATES]+[('Triangular bridge','Six pinned nodes / nine members'),('Blank structure','Define nodes, then connect members'),('Open saved beam','Saved models on SD')],'Beam / new'
        if self.page=='options':
            details={'New beam':'Templates / bridge / blank / Open','New blank structure':'Keep current setup in undo',
                     'Merge nodes':'Reconnect members to a chosen destination node','Split at node':'Connect an existing node inside a member',
                     'Resolve overlaps':'Preview one member per interval; reject conflicts',
                     'Load cases':', '.join(self.model['cases']),'Combinations':'Factored sums of load cases',
                     'Self-weight':'Off' if self.model.get('selfweight') is None else self.model['cases'][self.model['selfweight']],
                     'Save':'Write setup to SD; solving is optional','Open':'Load geometry without evaluating',
                     'Export CSV (Eggcel)':'Evaluated results / <=511 cells','Export full CSV':'Every evaluated diagram sample',
                     'Conventions and keys':'F9 help'}
            return [(name,details.get(name,'')) for name in OPTIONS],'Beam / options'
        if self.page=='cases':
            return [(n,'%d loads / ENTER rename / F2 remove'%sum(l['case']==i for l in self.model['loads'])) for i,n in enumerate(self.model['cases'])]+[('+ Add load case','Up to %d'%bm.MAX_CASES)],'Beam / load cases'
        if self.page=='combos':return [(c['name'],items.combo_text(self.model,c)) for c in self.model['combos']]+[('+ Add combination','Factored sum')],'Beam / combinations'
        return [(n,'ENTER opens without evaluating') for n in self.files] or [('No saved models','F3 Save creates one')],'Beam / open'

    def summary(self):
        """Two short lines about the current view, or the problem."""
        if self.problem is not None:
            return render.wrap(str(self.problem), 52), True
        sol = self.solution
        if sol is None:return ['Not evaluated / F6 Evaluate'],False
        name = sol.view_names()[self.view][:18]
        if bm.is_straight_beam(self.model):
            ext = self.extremes(0)
            w = max(abs(ext['W'][0]), abs(ext['W'][2]))
            v = max(abs(ext['V'][0]), abs(ext['V'][2]))
            first = '%s:  M %s / %s kNm' % (name, units.number(ext['M'][0] / 1e3), units.number(ext['M'][2] / 1e3))
            return [first, '|V| %s   |w| %s' % (units.show(v, 'kN'), units.show(w, 'mm'))], False
        peak = {'M': 0.0, 'N': 0.0, 'W': 0.0}
        for line in range(len(sol.lines)):
            ext = self.extremes(line)
            for q in peak:
                peak[q] = max(peak[q], abs(ext[q][0]), abs(ext[q][2]))
        return ['%s: |M| %s' % (name[:18],units.show(peak['M'],'kNm',3)),
                '|N| %s   |w| %s' % (units.show(peak['N'],'kN',3),units.show(peak['W'],'mm',3))],False

    def picture(self,key,build):
        """The deflected preview or the whole-frame overview for key, built
        once rather than on every key press. One is kept, while the solution
        stands; drop_solution() clears it."""
        if self.shape is None or self.shape[0]!=key:
            self.shape=None  # release the previous picture first
            self.shape=(key,build())
        return self.shape[1]

    def draw_model(self,draw,p):
        x,y,w,h=render.MODEL_PREVIEW
        here=self.cursor_position();member=self.cursor_member();runs=bm.lines(self.model)
        evaluated=self.solution is not None
        render.panel(draw,p,render.MODEL_PREVIEW,'FRAME PREVIEW',self.cursor_label()+' / '+('evaluated' if evaluated else 'geometry'),p.PANEL)
        preview=render.Viewport(draw,(x+5,y+17,x+w-5,y+h-15))
        pp=theme.colors(p.PANEL,p.TEXT,p.ACCENT)
        view=render.View(self.model,render.MODEL_BOX,ZOOMS[self.zoom],here)
        shape=self.picture(('deflected',self.view,view.scale,view.ox,view.oy),
                           lambda:render.deflected(self.model,self.solution,view,self.view)) if evaluated else None
        run=runs[self.line] if runs else []
        render.sketch(preview,pp,self.model,view,self.sel[0] if self.sel else None,(here,self.s),
                      self.problem,shape,run,y+h-16,member)
        # Real node and member IDs make closing triangles and selecting ends
        # visible. Crossing lines without a node get no connection marker.
        # Once there are several sections, each member ID names its section.
        highlighted=set(self.preview_nodes)
        if self.node_cursor is not None:highlighted.add(self.node_cursor)
        if self.node_pick is not None and self.popup is not None:highlighted.add(self.node_pick[self.popup[2]])
        for i,point in enumerate(self.model['joints']):
            px,py=view.p(*point);color=p.ACCENT if i in highlighted else p.TEXT
            if self.model['joint_types'][i]=='pin':
                preview._fill_circle(px,py,3,pp.BG);preview._circle(px,py,3,color)
            else:preview._fill_rectangle(px-2,py-2,5,5,color)
            render.text(preview,px+5,py-10,'J%d'%(i+1),color)
        sections=self.model['sections'] if len(self.model['sections'])>1 else None
        for i,edge in enumerate(self.model['members']):
            a,b=view.p(*self.model['joints'][edge['a']]),view.p(*self.model['joints'][edge['b']])
            label='L%d'%(i+1)+(' '+sections[edge['section']]['name'] if sections else '')
            render.text(preview,(a[0]+b[0])//2+3,(a[1]+b[1])//2+5,label,p.ACCENT if member==i else p.MUTED)
        if self.sel and self.sel[0][0] in ('support','load'):
            obj=self.sel[0][1];m=obj.get('m',-1);node=obj.get('node')
            if node is not None and m in st.attached(self.model,node):
                ux,uy,length=st.axis(self.model,m,node);px,py=view.p(*self.model['joints'][node])
                render.clip(preview,px,py,px+ux*20,py-uy*20,p.ACCENT,64,y+h-16)
                render.head(preview,px+ux*20,py-uy*20,ux,-uy,p.ACCENT,3)
        if self.problem is not None and getattr(self.problem,'pair',None):
            for i in self.problem.pair:
                edge=self.model['members'][i]
                render.thick(preview,view.p(*self.model['joints'][edge['a']]),view.p(*self.model['joints'][edge['b']]),p.ERROR,64,y+h-16)
        if self.problem is not None:
            render.summary_box(draw,p,render.wrap(str(self.problem),47),True,render.MODEL_PREVIEW)
        elif self.info and evaluated:
            lines,bad=self.summary();render.summary_box(draw,p,lines,bad,render.MODEL_PREVIEW)
        else:render.right_text(draw,x+w-8,y+h-12,'I displacement results' if evaluated else 'F6 Evaluate / no response computed',p.MUTED)
        rect=self.properties_rect();rows=self.rows();index=self.row_index(rows)
        render.model_tabs(draw,p,rect,MODEL_TABS,self.model_tab,[len(self.model['joints']),len(self.model['members']),len(self.model['supports']),len(self.model['loads'])],font=render.XS,height=render.MODEL_TAB_HEIGHT)
        if rows:render.form(draw,p,[r[:4] for r in rows],index,self.edit,rect[1]+render.MODEL_TAB_HEIGHT+4,rect[1]+rect[3]-5,font=render.XS,row_height=render.MODEL_ROW_HEIGHT)
        else:
            render.text(draw,rect[0]+10,rect[1]+render.MODEL_TAB_HEIGHT+8,'No '+MODEL_TABS[self.model_tab].lower()+' yet',p.MUTED)
            render.text(draw,rect[0]+10,rect[1]+render.MODEL_TAB_HEIGHT+22,'F1 adds / LEFT-RIGHT changes tab',p.MUTED)
        return 'Beam / model'

    def draw_section(self,draw,p):
        section=self.section;rows=self.section_rows()
        self.section_row=min(self.section_row,len(rows)-1)
        field=rows[self.section_row][0]
        render.section_preview(draw,p,section,field,render.PREVIEW_RECT,
                               lambda target,pp,x,y:render.section_panel(target,pp,self.model,section,x,y),
                               section['shape']+'  |  dimensions in mm')
        rect=self.properties_rect()
        render.panel(draw,p,rect,'SECTION PROPERTIES','%d/%d'%(self.section_row+1,len(rows)))
        form_rows=[('field',r[1],items.section_text(section,r),r[4]) for r in rows]
        render.form(draw,p,form_rows,self.section_row,self.edit,217,rect[1]+rect[3]-5)
        return 'Section '+section['name']

    def draw_diagrams(self, draw, p):
        subtitle = 'Beam / diagrams'
        if self.solution is None:
            for i, line in enumerate(render.wrap(str(self.problem) if self.problem is not None else 'Not evaluated / press F6 Evaluate', 48)):
                render.text(draw, 10, 70 + 11 * i, line, p.ERROR)
            render.text(draw, 10, 110, 'F6 evaluates / ESC opens the model.', p.MUTED)
            return subtitle
        sol = self.solution
        straight = bm.is_straight_beam(self.model)
        start, end = self.plot_bounds()
        left = sol.at(self.dmember, self.ds-start, self.view, -1)
        right = sol.at(self.dmember, self.ds-start, self.view, 1)

        def pair(q, unit):
            a, b = units.number(units.from_si(left[q], unit), 3), units.number(units.from_si(right[q], unit), 3)
            return a if a == b else a + '|' + b
        if straight:
            readout = 'V %s kN  M %s kNm  w %s mm  rot %s mrad' % (pair(0, 'kN'), pair(1, 'kNm'), pair(3, 'mm'),
                                                                 units.number(right[2] * 1e3, 3))
        else:
            readout = 'V %s kN  M %s kNm  N %s kN  w %s mm' % (pair(0, 'kN'), pair(1, 'kNm'), pair(4, 'kN'), pair(3, 'mm'))
        if self.third == 'U' and not self.whole:
            # The axial displacement panel reads u in place of the last value.
            readout = readout.rsplit('  ', 1)[0] + '  u %s mm' % pair(5, 'mm')
        title = self.plot_title()
        if self.whole:
            render.diagram_header(draw,p,title,sol.view_names()[self.view],readout)
            quantity=render.OVERVIEW[self.quantity]
            shapes=self.picture(('overview',self.view,quantity),
                                lambda:render.overview_shapes(self.model,sol,self.view,quantity,render.OVERVIEW_BOX))
            render.overview(draw, p, self.model, sol, quantity, shapes,
                            bm.point(self.model, self.dmember, self.ds-start), self.dline, render.OVERVIEW_BOX, self.dmember)
            return subtitle
        panels = ('V', 'M', self.third)
        if self.cache is None:
            self.cache = render.diagram_cache(sol, self.dline, self.view, panels,int(draw.size.y)-self.footer_height-6,self.dmember)
        marks = []
        if self.tab >= 0:
            label, s, q = self.peak_list()[self.tab]
            marks.append((s, q))
        render.diagrams(draw, p, sol, self.dline, self.view, panels, self.cache, self.ds, readout, self.note, marks,
                        title,int(draw.size.y)-self.footer_height-6,self.dmember)
        return subtitle


class BeamLabView:
    def __init__(self):
        self.app = None

    def start(self, vm):
        global _active
        self.app = _active = BeamLab(vm)
        vm.input_manager.reset()
        self.app.draw()
        return True

    def run(self, vm):
        if self.app is not None and self.app.run(vm.button) and self.app is not None:
            self.app.draw()

    def stop(self, vm):
        global _active
        if self.app is not None:
            self.app.close()
        self.app = _active = None
        from gc import collect
        collect()


def show(vm):
    from engtools.plots.view import open_view
    return open_view(vm, 'beam_lab', BeamLabView())
