"""The system keyboard below a PicoLAB breadcrumb, without a framebuffer."""
from . import breadcrumbs,theme


class BodyDraw:
    def __init__(self,draw,palette,path):
        from picoware.system.vector import Vector
        self.draw,self.palette,self.path=draw,palette,path
        self.top=theme.HEAD_HEIGHT
        self.size=Vector(int(draw.size.x),int(draw.size.y)-self.top)
    def __getattr__(self,name):return getattr(self.draw,name)
    def scale_y(self,value):return max(1,int(value*self.size.y/320))
    def erase(self):self.draw._fill_rectangle(0,self.top,int(self.size.x),int(self.size.y),self.palette.BG)
    def _text(self,x,y,*args):return self.draw._text(x,y+self.top,*args)
    def _rectangle(self,x,y,*args):return self.draw._rectangle(x,y+self.top,*args)
    def _fill_rectangle(self,x,y,*args):return self.draw._fill_rectangle(x,y+self.top,*args)
    def _line(self,x1,y1,x2,y2,*args):return self.draw._line(x1,y1+self.top,x2,y2+self.top,*args)
    def swap(self):
        breadcrumbs.paint(self.draw,self.palette,self.top,self.path)
        self.draw.swap()


def create(vm,fallback):
    from picoware.gui.keyboard import Keyboard
    palette=theme.system_palette(vm)
    path=breadcrumbs.current(vm)
    if path is None:path=fallback
    return Keyboard(BodyDraw(vm.draw,palette,path),vm.input_manager,palette.TEXT,palette.BG,palette.ACCENT)
