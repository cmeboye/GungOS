"""PicoCAD: a small, keyboard-driven direct-geometry modeller in PicoLAB."""
from time import ticks_us,ticks_diff
from picoware.system import buttons as k
from engtools.ui import theme
from engtools.ui.forms import LineEdit
from engtools.ui import lab
from . import model as dm
from . import draw as dd

PATH=('tools','PicoCAD')
PREVIEW=(8,43,304,160)
CANVAS=(12,64,296,135)
EDITOR=(8,210,304,96)
OPTIONS=('Save','Save as','Open','New','Curve Quality','Projection')
PRIMITIVES=('Box','Cylinder','Cone','Sphere')
VIEWS=('Isometric','Front','Top','Right','Fit','Reset camera')
HELP=(
    'PicoCAD / first version:',
    'Units: mm; angles: degrees.',
    'Construction steps run top to bottom.',
    'First step must be Add.',
    'Add = union, Cut = subtraction,',
    'Intersect keeps the overlap.',
    'F1 Add: Box / Cylinder / Cone / Sphere.',
    'F2 Remove: Z can undo the removal.',
    'F3: Save / Save as / Open / New (blank).',
    'F3 also sets curve quality and projection.',
    'Choose Add / Cut / Intersect in Properties.',
    'F4 Build: calculate the combined part.',
    'F5 View: standard views, fit, reset.',
    'F9: scrollable help; Esc closes it.',
    'Editing:',
    'Left/Right: Features / Properties.',
    'Up/Down: select a step or property.',
    'Enter on a step: open Properties.',
    'Enter on a number: edit; type replaces.',
    'Enter/Tab commits; Esc cancels.',
    'Decimal/scientific numbers supported.',
    'Back and Del erase before the cursor.',
    'Enter cycles the Operation property.',
    '[ / ]: previous/next feature.',
    'Z: undo (six model edits).',
    'Camera:',
    'Tab: focus the preview / return to list.',
    'Arrows: orbit; Space toggles Pan/Orbit.',
    '+/-: zoom; F fits; R isometric reset.',
    'Esc in preview returns to the editor.',
    'XYZ at top left follows camera rotation.',
    'Projection: Perspective or Isometric.',
    'Isometric uses parallel projection;',
    'it starts at an equal-axis view. Orbit',
    'can then rotate that parallel view.',
    'Geometry:',
    'Shapes are centred at X,Y,Z.',
    'Box: width X, depth Y, height Z.',
    'Cylinder/cone axis: local Z.',
    'Cone tip at +height/2; base at -height/2.',
    'Rotation order: X, then Y, then Z.',
    'Cut/intersect primitives use dashed lines.',
    'Edits show primitives immediately.',
    'Build generates supported part boundaries.',
    'Camera movement reuses cached geometry.',
    'Only direct lines and circles are stored.',
    'No volume sampling or mesh generation.',
    'Esc cancels Build; no partial result replaces',
    'the last successful result.',
    'Limits and files:',
    'Eight construction steps.',
    'Q or Options > Curve Quality sets detail.',
    'Box / cylinder / cone / sphere render',
    'directly at any position and rotation.',
    'Cylinders: angled and blind box bores.',
    'Through side-notches: one box side,',
    'parallel to a local box axis.',
    'Enclosed disjoint cavities are supported.',
    'Separated Add steps create multiple bodies.',
    'Matching-axis boxes: intersection, slab',
    'cut and simple rectangular union.',
    'Invalid: malformed/nonpositive inputs.',
    'Unsupported: boundary trimming not ready.',
    'Precision: geometry near float tolerance.',
    'Non-manifold: known edge/point contacts.',
    'Calculation: kernel failed internally.',
    'Empty and No change are valid outcomes.',
    'Limit: input/heap capacity exceeded.',
    'Rear edges show; no solid shading yet.',
    'No general exact Boolean CAD kernel.',
    'Projects: picoware/engineering/cad/*.pcad',
    'JSON stores the editable construction steps.',
    'No STL/STEP import or export in v1.',
    'Unsaved changes: Save/Discard/Cancel.',
    'Save before firmware Home/reset/power off.',
    'Help: arrows scroll/page; Ctrl-Up/Down',
    'jump to start/end. Home exits the tool.',
)
_active=None


class CAD:
    def __init__(self,vm):
        self.vm=vm
        from engtools import session
        kept=session.kept.get('picocad') or {}
        self.model=dm.clone(kept.get('model') or dm.example())
        self.filename=kept.get('filename');self.dirty=kept.get('dirty',False)
        self.selected=min(kept.get('selected',0),max(0,len(self.model['features'])-1))
        self.tab=0;self.row=0;self.focus='editor';self.camera=dd.Camera()
        self.built_model=self.geometry=None;self.show_built=False
        self.builder=self.job=None;self.progress=None;self.result_kind=None
        self.popup=None;self.menu_index=0;self.menu_kind='';self.prompt_kind=None
        self.edit=None;self.edit_key=None;self.replace=True
        self.help_open=False;self.help_first=0;self.message='F4 Build / Tab camera';self.error=False
        self.undo=[];self.pending=None;self.discard=False;self.redraw=True
        self.sync()
        if self.model['features']:self.build()

    def tell(self,message,error=False):self.message,self.error,self.redraw=str(message),error,True

    def fail(self,exc):
        self.result_kind=getattr(exc,'kind','limit' if isinstance(exc,MemoryError) else 'input')
        self.tell('Memory limit; model retained' if isinstance(exc,MemoryError) else exc,True)

    def refit(self):self.camera.fit(self.box,CANVAS,self.geometry if self.show_built else None)

    def sync(self):
        """Derived state after the model changes: bounds, cached-build match, camera."""
        self.box=dm.bounds(self.model);self.row=0;self.show_built=self.built_model==self.model
        self.result_kind=self.geometry.status if self.show_built and self.geometry is not None else None
        self.refit()

    def transact(self,candidate,selected=None):
        dm.validate(candidate)
        self.undo.append((dm.clone(self.model),self.dirty,self.selected))
        if len(self.undo)>6:self.undo.pop(0)
        self.model=candidate;self.dirty=True
        if selected is not None:self.selected=selected
        self.selected=max(0,min(self.selected,len(self.model['features'])-1))
        self.sync()
        self.tell('Changed; F4 rebuild' if not self.show_built else 'Previous build restored')

    def undo_edit(self):
        if not self.undo:self.tell('Nothing to undo');return
        self.model,self.dirty,self.selected=self.undo.pop()
        self.sync();self.tell('Undo')

    def properties(self):
        if not self.model['features']:return []
        f=self.model['features'][self.selected]
        rows=[('op','Operation',f['op'])]
        dims=(('a','Width X'),('b','Depth Y'),('c','Height Z')) if f['shape']=='Box' else (('a','Radius'),) if f['shape']=='Sphere' else (('a','Base radius' if f['shape']=='Cone' else 'Radius'),('c','Height Z'))
        for key,label in dims:rows.append((key,label,'%.5g mm'%f[key]))
        rows.extend((key,label,'%.5g %s'%(f[key],'deg' if key.startswith('r') else 'mm')) for key,label in (('x','Position X'),('y','Position Y'),('z','Position Z'),('rx','Rotate X'),('ry','Rotate Y'),('rz','Rotate Z')))
        return rows

    def select_feature(self,delta):
        count=len(self.model['features'])
        if count:self.selected=(self.selected+delta)%count;self.row=0;self.redraw=True

    def change(self,key,value):
        candidate=dm.clone(self.model);candidate['features'][self.selected][key]=value
        self.transact(candidate)

    def build(self):
        if self.job is not None:return
        from .geometry import Build
        # Keep the last successful boundaries until a complete result is ready.
        try:
            self.builder=Build(self.model);self.job=self.builder.job();self.progress=('Preparing',0,1)
            self.result_kind='building';self.tell('Building / Esc cancel')
        except (ValueError,MemoryError) as exc:self.builder=None;self.fail(exc)

    def cancel_build(self):
        if self.job is not None:self.job.close()
        self.job=None
        if self.builder is not None:self.builder.release()
        self.builder=None;self.progress=None
        self.result_kind='cancelled';self.tell('Build cancelled; model retained')

    def progress_text(self):
        name,done,total=self.progress
        return '%s %d%% / Esc cancels'%(name,min(100,done*100//max(1,total)))

    def draw_progress(self,d,p):
        d._fill_rectangle(18,180,284,15,p.PANEL);lab.text(d,22,184,self.progress_text(),p.ACCENT)

    def pump(self):
        if self.job is None:return
        started=ticks_us();shown=self.progress_text()
        try:
            for _ in range(64):
                next(self.job)
                if ticks_diff(ticks_us(),started)>=8000:break
            # Repaint only the progress strip, and only when its text changes:
            # a full frame per slice would cost more than the build itself.
            self.progress=self.builder.progress
            if not self.redraw and self.progress_text()!=shown:
                d=self.vm.draw;self.draw_progress(d,theme.system_palette(self.vm));d.swap()
        except StopIteration:
            # The builder's own clone is exactly what was built.
            self.geometry=self.builder.geometry;self.built_model=self.builder.model
            self.show_built=self.built_model==self.model
            self.builder=None;self.job=None;self.progress=None
            self.refit()
            self.result_kind=self.geometry.status
            label={'success':'Built','multiple':'Multiple bodies','no_change':'No change','empty':'Empty result'}[self.result_kind]
            count=self.geometry.body_count
            self.tell(label if not count else ('Multiple bodies: %d'%count if self.result_kind=='multiple' else '%s / %d %s'%(label,count,'body' if count==1 else 'bodies')))
        except (ValueError,MemoryError) as exc:
            self.job=None
            if self.builder is not None:self.builder.release()
            self.builder=None;self.progress=None;self.fail(exc)

    def menu(self,kind,options):
        self.menu_kind=kind;self.popup=tuple(options);self.menu_index=0;self.redraw=True

    def quality_menu(self):self.menu('quality',tuple('Curve %.2gpx'%(4.0/n) for n in dm.QUALITIES))

    def guard(self,action):
        if self.dirty:
            self.pending=action;self.menu('confirm',('Save','Discard','Cancel'));self.menu_index=2
        else:self.perform(action)

    def perform(self,action):
        if action=='exit':self.vm.back();return
        if action=='open':
            files=dm.files(self.vm.storage)
            if not files:self.tell('No saved PicoCAD projects');return
            self.menu('open',files);return
        replacement=dm.blank()
        self.transact(replacement,0);self.dirty=False;self.filename=None;self.tab=0;self.focus='editor'
        self.tell('Blank model / F1 adds a primitive')

    def save(self,as_new=False):
        if self.filename and not as_new:
            dm.save(self.vm.storage,self.filename,self.model);self.dirty=False;self.tell('Saved '+self.filename)
            action=self.pending;self.pending=None
            if action:self.perform(action)
        else:
            self.prompt_kind='save';self.edit=LineEdit(self.filename[:-5] if self.filename else 'Part',32)
            self.replace=True;self.popup=None;self.tell('Project name / Enter save')

    def menu_action(self):
        kind,value=self.menu_kind,self.popup[self.menu_index]
        self.popup=None;self.redraw=True
        if kind=='add':
            candidate=dm.clone(self.model);candidate['features'].append(dm.primitive(value,'Add',len(candidate['features'])+1))
            self.transact(candidate,len(candidate['features'])-1);self.tab=1;self.focus='editor'
        elif kind=='quality':
            candidate=dm.clone(self.model);candidate['resolution']=dm.QUALITIES[self.menu_index]
            self.transact(candidate);self.tell('Curve target %.2gpx / F4 applies'%(4.0/candidate['resolution']))
        elif kind=='view':
            if value in ('Isometric','Reset camera'):
                self.camera.yaw,self.camera.pitch=dd.ISO_YAW,dd.ISO_PITCH
            elif value=='Front':self.camera.yaw,self.camera.pitch=0.0,0.0
            elif value=='Top':self.camera.yaw,self.camera.pitch=0.0,1.570796
            elif value=='Right':self.camera.yaw,self.camera.pitch=1.570796,0.0
            self.refit()
            if self.job is None:self.tell(value)
        elif kind=='options':
            if value=='Save':self.save()
            elif value=='Save as':self.save(True)
            elif value=='Open':self.guard('open')
            elif value=='New':self.guard('blank')
            elif value=='Curve Quality':self.quality_menu()
            elif value=='Projection':
                self.menu('projection',dd.PROJECTIONS);self.menu_index=dd.PROJECTIONS.index(self.camera.projection)
        elif kind=='projection':
            self.camera.projection=value
            if value=='Isometric':self.camera.yaw,self.camera.pitch=dd.ISO_YAW,dd.ISO_PITCH
            self.refit()
            self.tell('Projection: '+value)
        elif kind=='open':
            replacement=dm.load(self.vm.storage,value)
            self.transact(replacement,0);self.filename=value;self.dirty=False;self.tab=0;self.build()
        elif kind=='confirm':
            if value=='Cancel':self.pending=None
            elif value=='Save':self.save()
            else:
                action=self.pending;self.pending=None
                if action=='exit':self.discard=True
                self.perform(action)

    def edit_input(self,button):
        char=self.vm.input_manager.button_to_char(button)
        if self.replace and char and char not in ('\n','\t'):
            self.edit=LineEdit('',32 if self.prompt_kind else 24);self.replace=False
        elif button in (k.BUTTON_LEFT,k.BUTTON_RIGHT,k.BUTTON_BACKSPACE,k.BUTTON_DELETE):self.replace=False
        action=self.edit.key(self.vm,button)
        if action=='cancel':
            self.edit=None;self.prompt_kind=None;self.pending=None;self.tell('Edit cancelled');return
        if action=='commit':
            if self.prompt_kind:
                name=dm.filename(self.edit.text)
                if (not self.filename or name!=self.filename) and self.vm.storage.exists(dm.DIRECTORY+'/'+name):
                    raise ValueError('Name exists; choose another or open it')
                dm.save(self.vm.storage,name,self.model)
                self.filename=name;self.dirty=False;self.edit=None;self.prompt_kind=None;self.tell('Saved '+name)
                pending=self.pending;self.pending=None
                if pending:self.perform(pending)
            else:
                value=float(self.edit.text)
                index=self.row
                self.change(self.edit_key,value);self.row=index;self.edit=None;self.edit_key=None
        self.redraw=True

    def input(self,button):
        if button==k.BUTTON_NONE:return
        self.redraw=True
        if self.help_open:
            capacity=lab.help_capacity(308)
            if button in (k.BUTTON_F9,k.BUTTON_ESCAPE):self.help_open=False
            elif button in (k.BUTTON_UP,k.BUTTON_DOWN,k.BUTTON_LEFT,k.BUTTON_RIGHT):
                step=capacity if button in (k.BUTTON_LEFT,k.BUTTON_RIGHT) else 1
                self.help_first=max(0,min(max(0,len(HELP)-capacity),self.help_first+(-step if button in (k.BUTTON_UP,k.BUTTON_LEFT) else step)))
            elif button in (k.BUTTON_HOME,k.BUTTON_CTRL_UP):self.help_first=0
            elif button in (k.BUTTON_END,k.BUTTON_CTRL_DOWN):self.help_first=max(0,len(HELP)-capacity)
            return
        if button==k.BUTTON_F9:self.help_open=True;return
        if self.job is not None:
            if button==k.BUTTON_ESCAPE:self.cancel_build()
            return
        if self.edit is not None:self.edit_input(button);return
        if self.popup is not None:
            if button==k.BUTTON_ESCAPE:self.popup=None;self.pending=None
            elif button in (k.BUTTON_UP,k.BUTTON_DOWN):self.menu_index=(self.menu_index+(-1 if button==k.BUTTON_UP else 1))%len(self.popup)
            elif button==k.BUTTON_CENTER:self.menu_action()
            return
        if button==k.BUTTON_F1:self.menu('add',PRIMITIVES);return
        if button==k.BUTTON_F2:
            if self.model['features']:
                candidate=dm.clone(self.model);candidate['features'].pop(self.selected);self.transact(candidate)
            return
        if button==k.BUTTON_F3:self.menu('options',OPTIONS);return
        if button==k.BUTTON_F4:self.build();return
        if button==k.BUTTON_F5:self.menu('view',VIEWS);return
        if button==k.BUTTON_TAB:
            self.focus='preview' if self.focus=='editor' else 'editor';return
        if button==k.BUTTON_Z:self.undo_edit();return
        # On a numeric property row '-' starts a negative value instead of zooming.
        numeric=self.focus=='editor' and self.tab and self.model['features'] and self.row>0
        if button in (k.BUTTON_PLUS,k.BUTTON_EQUAL,k.BUTTON_MINUS) and not (numeric and button==k.BUTTON_MINUS):
            self.camera.zoom=max(.2,min(8.0,self.camera.zoom*(1/1.15 if button==k.BUTTON_MINUS else 1.15)));return
        if button==k.BUTTON_F:self.refit();return
        if button==k.BUTTON_R:
            self.camera.yaw,self.camera.pitch=dd.ISO_YAW,dd.ISO_PITCH;self.refit();return
        char=self.vm.input_manager.button_to_char(button)
        if char in ('[',']'):self.select_feature(-1 if char=='[' else 1);return
        if self.focus=='preview':
            if button==k.BUTTON_ESCAPE:self.focus='editor'
            elif button==k.BUTTON_SPACE:self.camera.mode='Pan' if self.camera.mode=='Orbit' else 'Orbit'
            elif button in (k.BUTTON_LEFT,k.BUTTON_RIGHT,k.BUTTON_UP,k.BUTTON_DOWN):
                if self.camera.mode=='Orbit':
                    if button in (k.BUTTON_LEFT,k.BUTTON_RIGHT):self.camera.yaw+=-.12 if button==k.BUTTON_LEFT else .12
                    else:self.camera.pitch=max(-1.5,min(1.5,self.camera.pitch+(.12 if button==k.BUTTON_UP else -.12)))
                elif button in (k.BUTTON_LEFT,k.BUTTON_RIGHT):self.camera.pan_x+=-8 if button==k.BUTTON_LEFT else 8
                else:self.camera.pan_y+=-8 if button==k.BUTTON_UP else 8
            return
        if button==k.BUTTON_ESCAPE:
            if self.tab:self.tab=0;self.row=0
            else:self.guard('exit')
        elif button==k.BUTTON_Q:self.quality_menu()
        elif button in (k.BUTTON_LEFT,k.BUTTON_RIGHT):self.tab=1-self.tab;self.row=0
        elif button in (k.BUTTON_UP,k.BUTTON_DOWN):
            if self.tab:
                count=len(self.properties())
                if count:self.row=(self.row+(-1 if button==k.BUTTON_UP else 1))%count
            else:self.select_feature(-1 if button==k.BUTTON_UP else 1)
        elif button==k.BUTTON_CENTER:
            if not self.tab:self.tab=1;self.row=0
            elif self.model['features']:
                name=self.properties()[self.row][0]
                f=self.model['features'][self.selected]
                if name=='op':self.change(name,dm.OPERATIONS[(dm.OPERATIONS.index(f[name])+1)%3])
                else:self.edit=LineEdit('%.8g'%f[name]);self.edit_key=name;self.replace=True
        elif self.tab and self.model['features'] and char and char in '0123456789.-':
            name=self.properties()[self.row][0]
            if name!='op':self.edit=LineEdit(char);self.edit_key=name;self.replace=False

    def run(self,button):
        try:self.input(button)
        except (ValueError,OSError,MemoryError) as exc:self.fail(exc)
        if self.vm is None:return
        if not self.help_open:self.pump()
        if self.redraw:
            try:self.draw()
            except MemoryError:
                self.tell('Low heap; save and reopen tool',True)
                lab.chrome(self.vm.draw,theme.system_palette(self.vm),'Model',self.message,True,title='PICOCAD',fallback=PATH)
                self.vm.draw.swap();self.redraw=False

    def draw(self):
        d=self.vm.draw;p=theme.system_palette(self.vm);d.fill_screen(p.BG)
        page='Camera / '+self.camera.mode if self.focus=='preview' else 'Model'
        if self.help_open:
            lab.chrome(d,p,page,self.message,self.error,title='PICOCAD',fallback=PATH)
            lab.help_box(d,p,HELP,self.help_first,308);d.swap();self.redraw=False;return
        body_label=('%d %s'%(self.geometry.body_count,'body' if self.geometry.body_count==1 else 'bodies')) if self.show_built and self.geometry is not None else 'Guides'
        status=body_label+' / '+('ISO' if self.camera.projection=='Isometric' else 'PERSP')
        lab.panel(d,p,PREVIEW,'PART PREVIEW',status)
        if self.focus=='preview':d._rectangle(*PREVIEW,p.ACCENT)
        self.camera.setup(self.box,CANVAS)
        if self.show_built and self.geometry is not None:
            dd.built(d,self.camera,self.geometry,p)
            if not len(self.geometry):lab.centre_text(d,160,135,'Empty result',p.MUTED)
            if self.model['features'] and self.tab==1 and self.focus=='editor':
                bounded=lab.Viewport(d,(CANVAS[0],CANVAS[1],CANVAS[0]+CANVAS[2],CANVAS[1]+CANVAS[3]))
                feature=self.model['features'][self.selected]
                dd.primitive(bounded,self.camera,feature,p.TEXT,feature['op']!='Add')
        else:dd.preview(d,self.camera,self.model,self.selected,p)
        dd.axes(d,self.camera,p)
        if self.progress:self.draw_progress(d,p)
        x,y,w,h=EDITOR
        lab.panel(d,p,EDITOR,'')
        from picoware.gui.status_bar import foreground
        for index,label in enumerate(('Features','Properties')):
            left=x+1+index*(w-2)//2;right=x+1+(index+1)*(w-2)//2
            color=p.ACCENT if self.tab==index else p.PANEL
            d._fill_rectangle(left,y+1,right-left,17,color)
            lab.text(d,left+9,y+5,label,foreground(color) if self.tab==index else p.MUTED)
        area=lab.Viewport(d,(x+4,y+20,x+w-4,y+h-3))
        if not self.tab:
            rows=[('%d %s %s'%(i+1,f['op'],f['name']),f['shape']) for i,f in enumerate(self.model['features'])]
            if not rows:lab.text(area,18,240,'F1 adds the first primitive',p.MUTED)
            first=max(0,self.selected-3)
            for index in range(first,min(len(rows),first+4)):
                yy=234+(index-first)*17
                if index==self.selected:area._fill_rectangle(12,yy-3,296,16,p.SELECT);area._rectangle(12,yy-3,296,16,p.ACCENT)
                lab.text(area,18,yy,rows[index][0],p.TEXT)
        else:
            rows=self.properties();first=max(0,self.row-3)
            for index in range(first,min(len(rows),first+4)):
                name,label,value=rows[index];yy=234+(index-first)*17
                if index==self.row:area._fill_rectangle(12,yy-3,296,16,p.SELECT);area._rectangle(12,yy-3,296,16,p.ACCENT)
                lab.text(area,18,yy,label,p.MUTED)
                if index==self.row and self.edit is not None and not self.prompt_kind:self.edit.draw(area,169,yy,132,p.TEXT,p.ACCENT,0)
                else:lab.right_text(area,301,yy,value,p.TEXT)
        if self.popup is not None:
            height=28+17*min(8,len(self.popup))
            lab.popup(d,p,{'add':'ADD PRIMITIVE','options':'OPTIONS','view':'VIEW','open':'OPEN PROJECT','confirm':'UNSAVED CHANGES','quality':'CURVE QUALITY','projection':'PROJECTION'}[self.menu_kind],self.popup,self.menu_index,(20,max(43,(320-height)//2),280,height))
        if self.prompt_kind:lab.prompt(d,p,'SAVE PROJECT','Project name (.pcad) / SD',self.edit,self.message,self.error)
        # Chrome last so the error/footer box stays above the panels.
        lab.chrome(d,p,page,self.message,self.error,title='PICOCAD',fallback=PATH)
        d.swap();self.redraw=False

    def stop(self):
        if self.job is not None:self.cancel_build()
        from engtools import session
        if self.discard:session.kept.pop('picocad',None)
        else:session.kept['picocad']=dict(model=dm.clone(self.model),filename=self.filename,dirty=self.dirty,selected=self.selected)
        self.built_model=self.geometry=None;self.builder=self.job=None;self.vm=None


class Controller:
    def start(self,vm):
        global _active
        _active=CAD(vm);_active.draw();return True
    def run(self,vm):
        if _active is not None:_active.run(vm.button)
    def stop(self,vm):
        global _active
        if _active is not None:_active.stop()
        _active=None


def show(vm):
    from engtools.plots.view import open_view
    return open_view(vm,'picocad_view',Controller())
