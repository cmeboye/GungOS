"""F8 chapter equation prototype. Read-only; keeps the text page unchanged."""
from picoware.system import buttons as k
from engtools.ui import theme
from engtools.calculator.render import Renderer
from .mathml import equations
from gc import collect

class EquationView:
    def __init__(self,vm,book,chapter):
        self.vm=vm;self.book=book;self.chapter=chapter;self.source=None
        self.ordinal=-1;self.target=0;self.node=None;self.box=None;self.error='';self.loading=False
        self.font=2;self.x=0;self.y=0;self.help=False;self.ended=False;self.changed=True
        self.restart(0)
    def restart(self,target):
        self.close_source();self.source=equations(self.book,self.chapter)
        self.target=max(0,target);self.loading=True;self.ended=False;self.error='';self.changed=True
    def close_source(self):
        if self.source:self.source.close();self.source=None
    def close(self):
        self.close_source();self.box=None;self.node=None;collect()
    def layout(self):
        self.box=None;collect()
        if self.node:
            from .mathlayout import MathRenderer
            self.box=MathRenderer(self.vm.draw,(8,58,312,272),self.vm.selected_color,
                                  theme.system_palette(self.vm)).layout_math(self.node,self.font)
        self.x=0;self.y=0
    def step(self):
        if not self.loading or self.help:return False
        try:
            event=next(self.source)
            if event is None:return False
            number,node,error=event
            if number!=self.target:return False
            self.node=node;self.ordinal=number;self.loading=False;self.error=error
            if not error:self.layout()
            else:self.box=None
        except StopIteration:
            self.close_source();self.loading=False;self.ended=True
            self.error='No equations in this chapter' if self.ordinal<0 else 'End of chapter equations'
        except (OSError,ValueError,MemoryError,UnicodeError) as exc:
            self.loading=False;self.box=None;self.error=str(exc) or 'Not enough memory for equation'
            # A layout error does not invalidate the streaming scanner. ] can
            # still advance to the next independently supported expression.
        return True
    def key(self,button):
        if button==k.BUTTON_F9:self.help=not self.help;return
        if self.help:return
        if button==k.BUTTON_RIGHT_BRACKET and not self.loading and not self.ended:
            self.target=self.ordinal+1;self.loading=True;self.error=''
            self.box=None;self.node=None;collect()
        elif button==k.BUTTON_LEFT_BRACKET and not self.loading and self.ordinal>0:
            target=self.ordinal-1;self.box=None;self.node=None;collect();self.restart(target)
        elif button==k.BUTTON_F6 and not self.loading and self.node:
            self.font=(self.font+1)%3
            try:self.layout();self.error=''
            except (ValueError,MemoryError) as exc:self.box=None;self.error=str(exc) or 'Not enough memory'
        elif self.box and not self.loading:
            if button==k.BUTTON_LEFT:self.x=max(0,self.x-24)
            elif button==k.BUTTON_RIGHT:self.x=min(max(0,self.box.w-304),self.x+24)
            elif button==k.BUTTON_UP:self.y=max(0,self.y-24)
            elif button==k.BUTTON_DOWN:self.y=min(max(0,self.box.h-214),self.y+24)
    def draw(self):
        vm=self.vm;d=vm.draw;p=theme.system_palette(vm);d.fill_screen(p.BG);theme.status(vm,p)
        theme.header(d,'Equations - prototype','PicoReader',p,height=18,top=theme.STRIP)
        text=Renderer(d,(0,42,320,320),vm.selected_color,p)
        if self.help:
            lines=('Chapter MathML prototype','[ / ]: previous / next equation','Arrows: pan a wide or tall equation',
                   'F6: change equation font','F9: close help','ESC: return to the same text page',
                   'Fractions, scripts, roots, limits,','fences, matrices and Greek symbols.',
                   'Unsupported structures show an error.','No formula evaluation or EPUB scripts.')
            for i,line in enumerate(lines):text.text(8,48+i*18,line,p.TEXT,0)
        else:
            text.text(8,45,'Ch %d / Equation %s'%(self.chapter+1,str(self.ordinal+1) if self.ordinal>=0 else '?'),p.ACCENT,0)
            if self.box:
                from .mathlayout import MathRenderer
                renderer=MathRenderer(d,(8,58,312,272),vm.selected_color,p)
                xx=8-self.x+max(0,(304-self.box.w)//2);yy=64-self.y
                renderer.paint(self.box,xx,yy)
                text.text(8,278,'%dx%d px  pan %d,%d'%(self.box.w,self.box.h,self.x,self.y),p.MUTED,0)
            elif self.error:
                # Never draw a partial/flattened equation as if it were valid.
                for i in range(0,len(self.error),48):text.text(8,86+(i//48)*15,self.error[i:i+48],p.TEXT,0)
            text.text(8,296,'[ ] equations   Arrows pan   F9 Help',p.MUTED,0)
        theme.footer(d,'Scanning equation... ESC cancels' if self.loading else 'ESC returns to reading',palette=p)
        d.swap()
