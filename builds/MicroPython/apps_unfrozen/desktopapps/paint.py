"""PicoPaint: keyboard crosshair, square brushes, shapes and hatched fills."""
from picoware.system import buttons as k
from .common import FileApp,COLORS,FILE_HELP
from .icons import PICOPAINT
from .paint_model import Canvas,WIDTH,HEIGHT,TOOLS,PATTERNS,packed,rgb565,example


class Paint(FileApp):
    title='PicoPaint';extension='.ppaint';export_extension='.bmp';directory='picoware/documents/picopaint'
    ICON=PICOPAINT
    HELP=('Canvas:','Arrows\tmove the cursor','ENTER\tpen on / off; line and box anchor',
          'SPACE\tstamp the brush','BACK\terase under the cursor','F3\ttools','F4\tcolour',
          'F5\tbrush size','F6\tfill pattern','F7\tundo',
          'ESC\tdrop the anchor or pen; then close','ESC (fill)\tcancel a running fill')+FILE_HELP
    def __init__(self):
        super().__init__();self.reset_cursor()
    def fresh(self):return Canvas()
    def example(self):return example()
    def reset_cursor(self):
        self.x,self.y=128,96;self.tool,self.size,self.pattern=0,3,0
        self.ink=0;self.pen=False;self.anchor=None;self.job=None;self.progress=0
    def load(self,path):return Canvas.load(self.vm.storage,path)
    def encode(self,export):return self.model.bmp_chunks() if export else self.model.native_chunks()
    def rows(self):
        if self.page=='tools':return TOOLS
        if self.page=='brush':return ('1 x 1','3 x 3','5 x 5','9 x 9','15 x 15')
        if self.page=='pattern':return PATTERNS
        return super().rows()
    def choose(self):
        if self.page in ('tools','brush','pattern','color'):
            if self.page=='tools':self.tool=self.selected;self.anchor=None;self.pen=False
            elif self.page=='brush':self.size=(1,3,5,9,15)[self.selected]
            elif self.page=='pattern':self.pattern=self.selected
            else:self.ink=packed(self.palette()[self.selected][1])
            self.page='edit'
        else:super().choose()
    def common(self,button):
        if self.job is not None:
            if button==self.vm.input_manager._key_esc:
                self.job.close();self.job=None;self.model.restore();self.message='Fill cancelled'
            return True
        if button==k.BUTTON_F2 and self.page=='edit':self.pen=False
        return super().common(button)
    def stamp(self):
        self.model.brush(self.x,self.y,self.model.paper if self.tool==1 else self.ink,self.size,0 if self.tool==1 else self.pattern)
    def input(self,button):
        self.message=''
        if button==self.vm.input_manager._key_esc:
            if self.anchor is not None:self.anchor=None
            elif self.pen:self.pen=False
            else:self.guard('quit')
        elif button==k.BUTTON_BACKSPACE:
            self.pen=False;self.model.checkpoint()
            self.model.brush(self.x,self.y,self.model.paper,self.size)
        elif button==k.BUTTON_F3:self.pen=False;self.menu('tools',self.tool)
        elif button==k.BUTTON_F4:self.pen=False;self.menu('color')
        elif button==k.BUTTON_F5:self.pen=False;self.menu('brush',(1,3,5,9,15).index(self.size))
        elif button==k.BUTTON_F6:self.pen=False;self.menu('pattern',self.pattern)
        elif button==k.BUTTON_F7:self.pen=False;self.anchor=None;self.model.restore()
        elif button in (k.BUTTON_LEFT,k.BUTTON_RIGHT,k.BUTTON_UP,k.BUTTON_DOWN):
            self.x=max(0,min(WIDTH-1,self.x+(-1 if button==k.BUTTON_LEFT else 1 if button==k.BUTTON_RIGHT else 0)))
            self.y=max(0,min(HEIGHT-1,self.y+(-1 if button==k.BUTTON_UP else 1 if button==k.BUTTON_DOWN else 0)))
            if self.pen:self.stamp()
        elif button==k.BUTTON_SPACE and self.tool in (0,1):
            self.model.checkpoint();self.stamp()
        elif button==k.BUTTON_CENTER:
            if self.tool in (0,1):
                if self.pen:self.pen=False
                else:self.model.checkpoint();self.pen=True;self.stamp()
            elif self.tool in (2,3):
                if self.anchor is None:self.anchor=(self.x,self.y)
                else:
                    self.model.checkpoint()
                    operation=self.model.line if self.tool==2 else self.model.rectangle
                    operation(self.anchor[0],self.anchor[1],self.x,self.y,self.ink,self.size,self.pattern)
                    self.anchor=None
            elif self.tool==4:
                self.model.checkpoint();self.progress=0;self.job=self.model.fill(self.x,self.y,self.ink,self.pattern)
            else:self.ink=self.model.pixels[self.y*WIDTH+self.x]
    def tick(self):
        if self.job is None:return False
        try:
            for _ in range(4):self.progress=next(self.job)
        except StopIteration:self.job=None;self.message='Fill complete'
        except (ValueError,MemoryError):
            self.job=None;self.model.restore();raise
        return True
    def stop(self,vm):
        if self.job is not None:self.job.close()
        self.job=None;super().stop(vm)
    def draw_document(self,r,p,w,h):
        top=63;left=(w-WIDTH)//2
        r.text(8,40,TOOLS[self.tool]+' | '+str(self.size)+'px | '+PATTERNS[self.pattern],p.TEXT,0)
        r.fill(w-27,39,15,13,rgb565(self.ink));r.rect(w-28,38,17,15,p.AXIS)
        self.vm.draw._bytearray(left,top,WIDTH,HEIGHT,self.model.pixels,False)
        r.rect(left-1,top-1,WIDTH+2,HEIGHT+2,p.GRID)
        if self.anchor is not None:
            x0,y0=left+self.anchor[0],top+self.anchor[1];x1,y1=left+self.x,top+self.y
            if self.tool==2:r.line(x0,y0,x1,y1,p.ACCENT)
            else:r.rect(min(x0,x1),min(y0,y1),abs(x1-x0)+1,abs(y1-y0)+1,p.ACCENT)
        cursor=self.renderer((left,top,left+WIDTH,top+HEIGHT))
        x,y=left+self.x,top+self.y
        # Dark/white outlines remain visible on any image colour.
        radius=self.size//2
        cursor.rect(x-radius-1,y-radius-1,self.size+2,self.size+2,0)
        cursor.rect(x-radius,y-radius,self.size,self.size,0xFFFF)
        for color,delta in ((0,1),(0xFFFF,0)):
            cursor.line(x-5,y+delta,x+5,y+delta,color)
            cursor.line(x+delta,y-5,x+delta,y+5,color)
        status=('Filling %d pixels; ESC cancels'%self.progress if self.job else
                '%d,%d | %dx%d | %s'%(self.x,self.y,WIDTH,HEIGHT,'PEN DOWN' if self.pen else 'Pen up'))
        r.text(8,263,status,p.MUTED,0)
