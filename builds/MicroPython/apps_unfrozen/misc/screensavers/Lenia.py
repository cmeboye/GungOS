"""Native-size Lenia screensaver/widget; all controls and numerics live on SD."""
from time import ticks_ms, ticks_us, ticks_diff, ticks_add
from random import randint
from picoware.system import buttons as k
from engtools.ui import theme
from engtools.ui.forms import LineEdit
from engtools.system.lenia import Field, DEFAULTS, CHOICES, LIMITS, clean, validate, estimate

WIDGET_NATIVE = True
# Label, key, section. Every exposed model/display parameter has a menu row.
ROWS = (('Grid', 'size', 'Simulation'), ('Target steps/s', 'fps', 'Simulation'),
        ('Time step dt', 'dt', 'Simulation'), ('Growth centre mu', 'mu', 'Growth'),
        ('Growth width sigma', 'sigma', 'Growth'), ('Growth shape', 'growth', 'Growth'),
        ('Radius R', 'radius', 'Kernel'), ('Kernel shape', 'kernel', 'Kernel'),
        ('Ring centre', 'center', 'Kernel'), ('Ring width', 'width', 'Kernel'),
        ('Rings', 'rings', 'Kernel'), ('Weight b1', 'b1', 'Kernel'),
        ('Weight b2', 'b2', 'Kernel'), ('Weight b3', 'b3', 'Kernel'),
        ('Seed', 'seed', 'Seed'), ('Noise density', 'density', 'Seed'),
        ('Seed amplitude', 'amplitude', 'Seed'), ('Display gamma', 'gamma', 'Display'),
        ('Grid lines', 'grid', 'Display'), ('Statistics', 'stats', 'Display'),
        ('Apply this session', 'apply', 'Actions'), ('Apply & save', 'save', 'Actions'),
        ('Random rules', 'random', 'Actions'), ('Defaults', 'defaults', 'Actions'))
MODEL = ('size','radius','kernel','center','width','rings','b1','b2','b3')
SEED = ('seed','density','amplitude')
HELP = (
    'LENIA / single channel',
    'A smooth cellular automaton by Bert Chan.',
    'F2: settings (animation pauses).',
    'F3: random seed position/orientation; Noise gets fresh random values.',
    'F4: show/hide statistics for this session.',
    'F5: restart the configured seed.',
    'Space or P: pause/resume.',
    'N: one generation while paused.',
    'F9: open/close this help.',
    'Esc: return; widget releases focus.',
    'SETTINGS',
    'Up/Down: select; Left/Right: adjust.',
    'Enter: type a numeric value or cycle a choice. Enter again commits it.',
    'Back/Del erase before the cursor.',
    'F2: apply and save to SD.',
    'Esc: cancel entry, then discard settings.',
    'Apply this session does not write to SD.',
    'Random rules changes the draft only; apply when ready. Life is not guaranteed.',
    'Grid: simulation resolution, not screen pixels. 64 uses more RAM/work.',
    'Target steps/s: generations per second. Widget host caps updates at 8 Hz.',
    'dt: simulated time per generation; large values may destabilize organisms.',
    'mu/sigma: preferred density and growth tolerance.',
    'Growth: Gaussian, Polynomial or Step.',
    'R: neighbourhood radius in grid cells.',
    'Kernel: normalized radial weights, with up to three concentric rings.',
    'Ring centre/width: profile within each ring. b1/b2/b3 set ring strength.',
    'At least one active ring must have nonzero weight.',
    'Seed: Orbium, Twin Orbium, Ring or Noise.',
    'Density affects Noise only. Amplitude affects every seed.',
    'Gamma changes brightness, not simulation.',
    'Colours follow the system theme.',
    'Edges wrap around (a torus). Only one field/channel is supported.',
    'Changed grids and seed controls restart. Growth/kernel edits at the same grid retain the field.',
    'Blank/frozen patterns can be valid outcomes. F5 resets; Defaults restores Orbium rules.',
    'Timing reports measured steps/s and compute time, not guaranteed Pico performance.',
    'Help: Up/Down scroll; Left/Right page; Home/End jump.',
)


def value_text(name, value):
    if name=='size':return '%dx%d' % (value,value)
    if type(value) is bool:return 'On' if value else 'Off'
    return '%.4g' % value if type(value) in (float,int) else str(value)


def load_options(vm):
    try:
        from picoware.system.settings import Settings
        return clean(Settings(vm.storage).settings.get('lenia'))
    except (OSError, ValueError, TypeError, MemoryError):
        return DEFAULTS.copy()


class App:
    def __init__(self, vm):
        self.vm = vm
        self.widget = getattr(vm,'host',None) is not None
        self.options = load_options(vm)
        self.notice = self.error = ''
        try:
            self.field = Field(self.options)
        except (MemoryError,ValueError):
            self.options = DEFAULTS.copy();self.options.update(size=16,radius=4.0,fps=2)
            self.field = Field(self.options)
            self.notice = 'Small-grid fallback; settings kept.'
        self.page='view';self.draft=None;self.editor=None;self.row=self.first=self.help_first=0
        self.help_return='view';self.paused=False;self.single=False
        self.job=None;self.next=0;self.dirty=True;self.last_draw=None
        self.actual=0.0;self.work_us=0;self.last_step=None;self.job_work=0
        self.draw()

    def effective_fps(self):return min(8,self.options['fps']) if self.widget else self.options['fps']

    def reset(self, randomize=False):
        self.job=None;self.single=False;self.field.reseed(randomize)
        self.next=0;self.actual=0.0;self.last_step=None;self.work_us=0
        self.notice='Random seed' if randomize else 'Seed restarted'
        self.error='';self.dirty=True

    def open_settings(self):
        self.draft=self.options.copy();self.page='settings';self.editor=None
        self.error='';self.dirty=True

    def close_settings(self):
        self.draft=None;self.editor=None;self.page='view'
        self.next=0;self.last_step=None;self.actual=0.0;self.dirty=True

    def apply(self, save=False):
        try:
            validate(self.draft)
            changed = any(self.draft[key]!=self.options[key] for key in MODEL)
            seeded = any(self.draft[key]!=self.options[key] for key in SEED)
            replacement = Field(self.draft) if changed else None
            if replacement is not None and replacement.size==self.field.size and not seeded:
                replacement.a[:] = self.field.a
                replacement.generation = self.field.generation
            if save:
                from picoware.system.settings import Settings
                if not Settings(self.vm.storage).update({'lenia':self.draft.copy()}):
                    raise OSError('SD save failed; F2 retries')
            self.job=None;self.single=False
            self.options=self.draft.copy()
            if replacement is not None:self.field=replacement
            else:
                self.field.options=self.options.copy()
                if seeded:self.field.reseed()
            self.notice='Settings saved' if save else 'Session settings applied'
            self.error='';self.close_settings()
            return True
        except MemoryError:
            self.error='Low heap; choose smaller grid'
        except (OSError,ValueError,TypeError) as exc:
            self.error=str(exc)
        self.dirty=True
        return False

    def random_rules(self):
        # Exploration only: keep allocation/refresh unchanged and constrain choices.
        self.draft.update(mu=randint(110,180)/1000,sigma=randint(10,35)/1000,
                          dt=randint(5,15)/100,kernel='Polynomial',growth='Gaussian',
                          rings=1,b1=1.0,center=0.5,width=0.5)
        self.draft['radius']=float(randint(4,min(13,self.draft['size']//2-1)))
        self.error='';self.notice='Random rules staged';self.dirty=True

    def setting_input(self, button):
        if self.editor is not None:
            # Replace the prefilled number on the first printable keystroke.
            char=self.vm.input_manager.button_to_char(button)
            if self.replace and char and char not in ('\n','\t'):
                self.editor=LineEdit('',16);self.replace=False
            elif button in (k.BUTTON_LEFT,k.BUTTON_RIGHT,k.BUTTON_BACKSPACE,k.BUTTON_DELETE):
                self.replace=False
            action=self.editor.key(self.vm,button)
            if action=='cancel':self.editor=None;self.error=''
            elif action=='commit':
                try:
                    from math import isfinite
                    number=float(self.editor.text)
                    name=ROWS[self.row][1];low,high,_=LIMITS[name]
                    if name=='radius':high=min(high,self.draft['size']/2-1)
                    if not isfinite(number) or not low<=number<=high:
                        raise ValueError('Allowed %.4g .. %.4g' % (low,high))
                    self.draft[name]=number;self.editor=None;self.error=''
                except ValueError as exc:self.error=str(exc)
            self.dirty=True;return
        if button==k.BUTTON_ESCAPE:self.close_settings();return
        if button==k.BUTTON_F2:self.apply(True);return
        if button==k.BUTTON_F3:self.random_rules();return
        if button in (k.BUTTON_UP,k.BUTTON_DOWN):
            self.row=(self.row+(-1 if button==k.BUTTON_UP else 1))%len(ROWS)
        elif button in (k.BUTTON_LEFT,k.BUTTON_RIGHT,k.BUTTON_CENTER):
            name=ROWS[self.row][1];direction=-1 if button==k.BUTTON_LEFT else 1
            if name in CHOICES:
                choices=CHOICES[name];self.draft[name]=choices[(choices.index(self.draft[name])+direction)%len(choices)]
                self.draft['radius']=min(self.draft['radius'],self.draft['size']/2-1)
                self.error=''
            elif name in LIMITS:
                if button==k.BUTTON_CENTER:
                    self.editor=LineEdit(value_text(name,self.draft[name]),16);self.replace=True
                else:
                    low,high,step=LIMITS[name]
                    if name=='radius':high=min(high,self.draft['size']/2-1)
                    self.draft[name]=round(max(low,min(high,self.draft[name]+direction*step)),4)
                    self.error=''
            elif button==k.BUTTON_CENTER:
                if name in ('apply','save'):self.apply(name=='save');return
                elif name=='random':self.random_rules()
                elif name=='defaults':self.draft=DEFAULTS.copy();self.error=''
        self.dirty=True

    def help_lines(self):
        width=int(self.vm.draw.size.x)-18
        lines=[]
        for paragraph in HELP:
            line=''
            for word in paragraph.split():
                candidate=(line+' '+word).strip()
                if line and self.vm.draw.len(candidate,0)>width:lines.append(line);line=word
                else:line=candidate
            lines.append(line)
        return lines

    def input(self, button):
        if button==k.BUTTON_NONE:return
        self.dirty=True
        if self.page=='help':
            lines=self.help_lines();capacity=max(1,(int(self.vm.draw.size.y)-56)//13)
            if button in (k.BUTTON_F9,k.BUTTON_ESCAPE):
                self.page=self.help_return;self.next=0;self.last_step=None;self.actual=0.0
            elif button in (k.BUTTON_UP,k.BUTTON_DOWN,k.BUTTON_LEFT,k.BUTTON_RIGHT):
                distance=capacity if button in (k.BUTTON_LEFT,k.BUTTON_RIGHT) else 1
                self.help_first=max(0,min(len(lines)-capacity,self.help_first+(-distance if button in (k.BUTTON_UP,k.BUTTON_LEFT) else distance)))
            elif button in (k.BUTTON_HOME,k.BUTTON_CTRL_UP):self.help_first=0
            elif button in (k.BUTTON_END,k.BUTTON_CTRL_DOWN):self.help_first=max(0,len(lines)-capacity)
            return
        if button==k.BUTTON_F9 and self.editor is None:
            self.help_return=self.page;self.page='help';self.help_first=0;return
        if self.page=='settings':self.setting_input(button);return
        if button==k.BUTTON_ESCAPE:self.vm.back();return
        if button==k.BUTTON_F2:self.open_settings();return
        if button==k.BUTTON_F3:self.reset(True)
        elif button==k.BUTTON_F5:self.reset()
        elif button==k.BUTTON_F4:self.options['stats']=not self.options['stats']
        elif button in (k.BUTTON_SPACE,k.BUTTON_P):
            self.paused=not self.paused;self.job=None;self.single=False;self.next=0;self.last_step=None;self.actual=0.0
        elif button==k.BUTTON_N and self.paused:self.single=True;self.next=0

    def pump(self):
        if self.paused and not self.single:return
        now=ticks_ms()
        if self.job is None:
            if self.next and ticks_diff(now,self.next)<0:return
            self.job=self.field.step();self.job_start=now;self.job_work=0
        started=ticks_us()
        try:
            # One generation maximum per call; never accrue catch-up work. Each
            # FFT is small, and we yield back to keyboard handling after 6 ms.
            for count in range(256):
                next(self.job)
                if ticks_diff(ticks_us(),started)>=6000:break
        except StopIteration:
            self.job=None;self.single=False;self.dirty=True
            finished=ticks_ms()
            if self.last_step is not None:
                elapsed=ticks_diff(finished,self.last_step)
                if elapsed>0:
                    rate=1000/elapsed;self.actual=rate if not self.actual else self.actual*0.8+rate*0.2
            self.last_step=finished
            self.next=ticks_add(self.job_start,max(1,1000//self.effective_fps()))
        self.job_work+=ticks_diff(ticks_us(),started)
        if self.job is None:self.work_us=self.job_work

    def run(self, button):
        self.input(button)
        if self.field is None:return
        if self.page=='view':
            try:self.pump()
            except (MemoryError,ValueError,ArithmeticError) as exc:
                self.job=None;self.single=False;self.paused=True
                self.error='Low heap; lower grid in F2' if isinstance(exc,MemoryError) else str(exc)
                self.dirty=True
        if self.dirty:self.draw()

    def text(self,x,y,text,color,available=None):
        d=self.vm.draw
        if available is None:available=int(d.size.x)-x-5
        while text and d.len(text,0)>available:text=text[:-1]
        d._text(x,y,text,color,0)

    def draw_settings(self,d,p,w,h):
        theme.header(d,'Lenia / Settings',palette=p,height=18)
        label,name,section=ROWS[self.row]
        self.text(7,25,section+' / '+str(self.row+1)+' of '+str(len(ROWS)),p.MUTED)
        capacity=max(1,(h-104)//18)
        self.first=max(0,min(self.first,self.row))
        if self.row>=self.first+capacity:self.first=self.row-capacity+1
        for index in range(self.first,min(len(ROWS),self.first+capacity)):
            label,key,_=ROWS[index];y=45+(index-self.first)*18
            selected=index==self.row
            if selected:
                d._fill_rectangle(4,y-3,w-8,17,p.SELECT)
                d._rectangle(4,y-3,w-8,17,p.ACCENT)
            self.text(9,y,label,p.TEXT, w-105)
            if selected and self.editor is not None:
                self.editor.draw(d,w-91,y,82,p.TEXT,p.ACCENT,0)
            elif key in self.draft:
                value=value_text(key,self.draft[key])
                self.text(w-9-d.len(value,0),y,value,p.ACCENT if selected else p.MUTED)
        if self.error:self.text(6,h-50,self.error,p.ERROR)
        else:
            warning=('64 grid: benchmark on Pico' if self.draft['size']==64 else 'Grid bytes: %d KiB + work' % (16*self.draft['size']**2//1024))
            self.text(6,h-50,warning,p.MUTED)
        self.text(6,h-35,'Enter number; arrows adjust' if self.editor is None else 'Enter set; Esc cancel entry',p.MUTED)
        self.text(6,h-20,'F2 save  F3 random rules',p.ACCENT)
        self.text(6,h-9,'F9 help  Esc discard',p.MUTED)

    def draw_help(self,d,p,w,h):
        theme.header(d,'Lenia / Help',palette=p,height=18)
        lines=self.help_lines();capacity=max(1,(h-56)//13)
        self.text(7,25,'%d-%d / %d' % (self.help_first+1,min(len(lines),self.help_first+capacity),len(lines)),p.MUTED)
        for i,line in enumerate(lines[self.help_first:self.help_first+capacity]):self.text(8,41+i*13,line,p.TEXT)
        self.text(6,h-10,'Arrows scroll   F9/Esc close',p.ACCENT)

    def draw_widget_overlay(self,d,p,w,h):
        # The desktop supplies the frame. Draw the field across the whole native
        # square, then put compact labels on top without an inner plot border.
        d._fill_rectangle(0,0,w,13,p.BG)
        d._fill_rectangle(0,h-25,w,25,p.BG)
        self.text(4,3,'Lenia',p.TEXT)
        if self.options['stats']:
            rate='%.1f' % self.actual if self.actual else '--'
            generation=self.field.generation
            gen='%.1fk' % (generation/1000) if generation>=10000 else str(generation)
            stats='%sHz %.1fms G%s' % (rate,self.work_us/1000,gen)
            available=w-12-d.len('Lenia',0)
            if d.len(stats,0)>available:
                stats='%sHz %dms G%s' % (rate,self.work_us//1000,gen)
            self.text(max(4+d.len('Lenia',0)+8,w-6-d.len(stats,0)),3,stats,p.MUTED)
        info='%dx%d R%.1f mu%.3f' % (self.field.size,self.field.size,self.options['radius'],self.options['mu'])
        if self.error:self.text(4,h-22,self.error,p.ERROR)
        else:self.text(4,h-22,info,p.MUTED)
        help_text='F9 Help';help_x=w-6-d.len(help_text,0)
        species=self.options['seed']+(' / paused' if self.paused else '')
        self.text(4,h-10,species,p.TEXT,help_x-12)
        self.text(help_x,h-10,help_text,p.ACCENT)

    def draw(self):
        d=self.vm.draw;p=theme.system_palette(self.vm);w,h=int(d.size.x),int(d.size.y)
        d.fill_screen(p.BG)
        if self.page=='settings':self.draw_settings(d,p,w,h)
        elif self.page=='help':self.draw_help(d,p,w,h)
        else:
            n=self.field.size
            if self.widget:
                square=min(w,h);left=(w-square)//2;top=(h-square)//2
            else:
                theme.header(d,'Lenia'+(' / Paused' if self.paused else ''),palette=p,height=18)
                if self.options['stats']:
                    rate='%.1f' % self.actual if self.actual else '--'
                    self.text(6,23,'%s/%d Hz  %.1f ms  G%d' % (rate,self.effective_fps(),self.work_us/1000,self.field.generation),p.MUTED)
                else:self.text(6,23,'%s / %dx%d' % (self.options['seed'],n,n),p.MUTED)
                square=min(w-12,h-68);left=(w-square)//2;top=37
                d._rectangle(left-1,top-1,square+2,square+2,p.AXIS)
            colors=[]
            for index in range(16):
                level=(index/15)**self.options['gamma']
                a,b,t=(p.BG,p.ACCENT,level/0.8) if level<=0.8 else (p.ACCENT,p.TEXT,(level-0.8)/0.2)
                r=round(((a>>11)&31)*(1-t)+((b>>11)&31)*t)
                g=round(((a>>5)&63)*(1-t)+((b>>5)&63)*t)
                blue=round((a&31)*(1-t)+(b&31)*t)
                colors.append((r<<11)|(g<<5)|blue)
            grid=self.options['grid'] and square//n>=3
            for y in range(n):
                x=0;yy=top+y*square//n;hh=(y+1)*square//n-y*square//n
                while x<n:
                    level=max(0,min(15,int(float(self.field.a[y,x])*15+0.5)))
                    end=x+1
                    if not grid:
                        while end<n and max(0,min(15,int(float(self.field.a[y,end])*15+0.5)))==level:end+=1
                    if level:
                        xx=left+x*square//n;ww=end*square//n-x*square//n
                        d._fill_rectangle(xx,yy,max(1,ww-int(grid)),max(1,hh-int(grid)),colors[level])
                    x=end
            if self.widget:self.draw_widget_overlay(d,p,w,h)
            else:
                if self.error:self.text(6,h-23,self.error,p.ERROR)
                elif self.notice:self.text(6,h-23,self.notice,p.MUTED)
                elif self.paused:self.text(6,h-23,'Space resume / N single step',p.MUTED)
                else:self.text(6,h-23,'%s  R%.1f  mu%.3f' % (self.options['seed'],self.options['radius'],self.options['mu']),p.MUTED)
                self.text(6,h-9,'F2 Settings F3 Random F9 Help',p.ACCENT)
        d.swap();self.dirty=False;self.last_draw=ticks_ms()

    def stop(self):
        self.job=None;self.field=None;self.draft=None;self.editor=None


_app=None

def start(vm):
    global _app
    _app=App(vm)
    if not _app.widget:
        fast=getattr(vm,'request_fast_drawing',None)
        if fast is not None:fast()
        _app.draw()
    return True


def run(vm):
    if _app is not None:_app.run(vm.button)


def stop(vm):
    global _app
    if _app is not None:_app.stop()
    _app=None
