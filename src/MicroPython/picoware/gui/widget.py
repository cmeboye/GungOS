"""Offscreen Picoware widget context; the desktop owns composition and input."""
import framebuf
from time import ticks_ms,ticks_diff
from picoware.system.vector import Vector
from picoware.system.font import Font,FontSize


def rgb332(color):
    return ((int(color)&0xE000)>>8)|((int(color)&0x0700)>>6)|((int(color)&0x0018)>>3)


class WidgetDraw:
    FONT_DEFAULT=0
    use_lvgl=False
    def __init__(self, master, width, height):
        self.width,self.height = width,height
        self._size = Vector(width,height)
        self._foreground,self._background = master.foreground_color,master.background_color
        self.font=0
        self.buffer=bytearray(width*height)
        self.fb=framebuf.FrameBuffer(self.buffer,width,height,framebuf.GS8)
        self._font_source,self._glyphs=Font(),{}
        self._palette_data=bytearray(2)
        self._palette=framebuf.FrameBuffer(self._palette_data,2,1,framebuf.GS8)
        self.changed=True
        self.erase()

    @property
    def font(self): return self._font_default.size
    @font.setter
    def font(self,value): self._font_default=FontSize(value)
    @property
    def size(self): return self._size
    @property
    def foreground(self): return self._foreground
    @foreground.setter
    def foreground(self,value): self._foreground=value
    @property
    def background(self): return self._background
    @background.setter
    def background(self,value): self._background=value
    @property
    def font_size(self): return Vector(self.get_font().width+self.get_font().spacing,self.get_font().height)
    def get_font(self,size=-1): return FontSize(self.font if size<0 else size)
    def len(self,text,font_size=-1):
        font=self.get_font(font_size)
        return len(str(text))*(font.width+font.spacing)
    def scale_x(self,value): return int(value*self.width/320)
    def scale_y(self,value): return int(value*self.height/320)
    def erase(self): self._clear(self.background)
    def fill_screen(self,color=None): self._clear(self.background if color is None else color)
    def _clear(self,color): self.fb.fill(rgb332(color)); self.changed=True
    def swap(self): self.changed=True
    def _pixel(self,x,y,color): self.fb.pixel(int(x),int(y),rgb332(color)); self.changed=True
    def _fill_rectangle(self,x,y,w,h,color): self.fb.fill_rect(int(x),int(y),int(w),int(h),rgb332(color)); self.changed=True
    def _rectangle(self,x,y,w,h,color): self.fb.rect(int(x),int(y),int(w),int(h),rgb332(color)); self.changed=True
    def _line(self,x1,y1,x2,y2,color): self.fb.line(int(x1),int(y1),int(x2),int(y2),rgb332(color)); self.changed=True
    def _circle(self,x,y,r,color): self.fb.ellipse(int(x),int(y),int(r),int(r),rgb332(color)); self.changed=True
    def _fill_circle(self,x,y,r,color): self.fb.ellipse(int(x),int(y),int(r),int(r),rgb332(color),True); self.changed=True
    def _fill_round_rectangle(self,x,y,w,h,r,color):
        x,y,w,h= int(x),int(y),int(w),int(h)
        if w<=0 or h<=0: return
        r=max(0,min(int(r),(w-1)//2,(h-1)//2))
        color=rgb332(color)
        self.fb.fill_rect(x+r,y,w-2*r,h,color)
        self.fb.fill_rect(x,y+r,w,h-2*r,color)
        if r:
            for cx,cy in ((x+r,y+r),(x+w-r-1,y+r),(x+r,y+h-r-1),(x+w-r-1,y+h-r-1)):
                self.fb.ellipse(cx,cy,r,r,color,True)
        self.changed=True
    def _triangle(self,x1,y1,x2,y2,x3,y3,color): self._poly((x1,y1,x2,y2,x3,y3),color,False)
    def _fill_triangle(self,x1,y1,x2,y2,x3,y3,color): self._poly((x1,y1,x2,y2,x3,y3),color,True)
    def _poly(self,points,color,fill):
        from array import array
        self.fb.poly(0,0,array('h',(int(value) for value in points)),rgb332(color),fill)
        self.changed=True
    def _polygon(self,points,color): self._poly(points,color,False)
    def _text(self,x,y,text,color=None,font_size=-1):
        size=self.font if font_size<0 else font_size
        font=self.get_font(size)
        color=rgb332(self.foreground if color is None else color)
        key=(color+1)&255
        self._palette_data[0],self._palette_data[1]=key,color
        origin=int(x)
        for char in str(text):
            if char=='\n': x=origin; y+=font.height; continue
            if not 32<=ord(char)<=126: char='?'
            cache=(size,char)
            if cache not in self._glyphs:
                if len(self._glyphs)>=64: self._glyphs.clear()
                bits=self._font_source.get_character(size,ord(char))
                self._glyphs[cache]=framebuf.FrameBuffer(bytearray(bits),font.width,font.height,framebuf.MONO_HLSB,((font.width+7)//8)*8)
            self.fb.blit(self._glyphs[cache],int(x),int(y),key,self._palette)
            x+=font.width+font.spacing
        self.changed=True
    def _bytearray(self,x,y,w,h,data,invert=False):
        w,h=int(w),int(h)
        if len(data)==w*h:
            if invert:
                palette=framebuf.FrameBuffer(bytearray(255-v for v in range(256)),256,1,framebuf.GS8)
                self.fb.blit((data,w,h,framebuf.GS8),int(x),int(y),-1,palette)
            else: self.fb.blit((data,w,h,framebuf.GS8),int(x),int(y))
        else:
            image=framebuf.FrameBuffer(bytearray(data),w,h,framebuf.RGB565)
            for row in range(h):
                for col in range(w):
                    pixel=image.pixel(col,row)
                    self.fb.pixel(int(x)+col,int(y)+row,rgb332(pixel^0xFFFF if invert else pixel))
        self.changed=True
    def _char(self,x,y,char,color,font_size=-1): self._text(x,y,char,color,font_size)

    def __getattr__(self,name):
        # High-level Vector drawing helpers can use this object's primitives.
        from picoware.gui.draw import Draw
        allowed=('char','circle','clear','fill_circle','fill_rectangle','fill_round_rectangle',
                 'fill_triangle','image_bytearray','line','line_custom','pixel','rect','text','triangle','polygon')
        if name in allowed:
            method=getattr(Draw,name)
            return lambda *args,**kwargs: method(self,*args,**kwargs)
        raise AttributeError('Widget drawing API unavailable: '+name)


class WidgetInput:
    def __init__(self,source): self.source,self._last_button=source,-1
    @property
    def button(self): return self._last_button
    def reset(self): self._last_button=-1
    def is_pressed(self): return self._last_button!=-1
    def is_held(self,duration=3): return self.is_pressed() and self.source.is_held(duration)
    @property
    def was_capitalized(self): return self.is_pressed() and self.source.was_capitalized
    @property
    def _was_pressed(self): return self.is_pressed()
    def button_to_char(self,button): return self.source.button_to_char(button)
    def __getattr__(self,name): return getattr(self.source,name)


class WidgetContext:
    def __init__(self,host,draw):
        self.host,self.master,self.draw=host,host.master,draw
        self.input_manager=WidgetInput(self.master.input_manager)
        self.views,self.stack,self.current_view={},[],None
        self.keyboard=None
    @property
    def button(self): return self.input_manager.button
    def get_view(self,name): return self.views.get(name)
    def add(self,view):
        if view.name in self.views or len(self.views)>=12: return False
        self.views[view.name]=view
        return True
    def switch_to(self,name,clear_stack=False,push_view=True):
        view=self.views[name]
        if self.current_view:
            if clear_stack: self.stack=[]
            if push_view: self.stack.append(self.current_view)
            self.current_view.stop(self)
        self.current_view=view
        self.draw.erase()
        if not view.start(self): self.back()
    def back(self,*args,**kwargs):
        if not self.stack:
            self.host.focused=False
            return
        if self.current_view:
            old=self.current_view
            old.stop(self)
            self.views.pop(old.name,None)
            self.current_view=self.stack.pop() if self.stack else None
            if self.current_view:
                self.draw.erase(); self.current_view.start(self)
                return
        self.host.focused=False
    def alert(self,message,*args,**kwargs): raise RuntimeError(str(message))
    def clear(self): self.draw.erase()
    def __getattr__(self,name):
        if name in ('storage','time','battery','wifi','system','foreground_color','background_color',
                    'selected_color','has_wifi','gmt_offset','log'):
            return getattr(self.master,name)
        raise AttributeError('Widget context API unavailable: '+name)


class WidgetHost:
    def __init__(self,master,rect):
        self.master,self.rect=master,rect
        self.module,self.context,self.draw=None,None,None
        self.focused,self.error,self.started=False,'',False
        self.next_frame=0
    def load(self,name):
        self.stop()
        self.error=''
        self.next_frame=0
        if not name: return
        try:
            if '/' in name or '\\' in name or name.startswith('.'): raise ValueError('Invalid widget name')
            from picoware.system.features import SCREENSAVER_DIRECTORIES
            directory=next((path for path in SCREENSAVER_DIRECTORIES
                            if name in self.master.app_loader.list_available_apps(path)),None)
            if directory is None:raise ValueError('Widget not found on SD')
            module=self.master.app_loader.load_app(name,directory)
            if module is None: raise RuntimeError(self.master.app_loader.error or 'Widget could not load')
            n=self.rect[2]
            size=(n,n) if getattr(module,'WIDGET_NATIVE',False) else getattr(module,'WIDGET_SIZE',(320,320))
            w,h=int(size[0]),int(size[1])
            if w<16 or h<16 or w*h>102400: raise ValueError('Widget surface limit: 102400 pixels')
            from gc import collect,mem_free
            collect()
            if mem_free()<w*h+80*1024: raise MemoryError('Not enough heap for this widget surface')
            self.draw=WidgetDraw(self.master,w,h)
            self.module=module
            self.context=WidgetContext(self,self.draw)
            self.started=True
            from picoware.system.view import View
            root=View('__widget_root',module.run,module.start,module.stop)
            self.context.add(root)
            self.context.switch_to(root.name,push_view=False)
            if not root.active: raise RuntimeError('Widget refused to start')
        except Exception as exc:
            self.stop()
            self.error=str(exc)
    def step(self,button=-1):
        if not self.module: return False
        now=ticks_ms()
        if button==-1 and ticks_diff(now,self.next_frame)<0: return False
        self.next_frame=now+125
        try:
            self.context.input_manager._last_button=button if self.focused else -1
            if self.context.current_view: self.context.current_view.run(self.context)
            else: self.module.run(self.context)
            self.context.input_manager.reset()
            return self.draw.changed
        except Exception as exc:
            self.stop(); self.error=str(exc)
            return True
    def paint(self):
        if not self.draw: return
        x,y,n,_=self.rect
        w,h=self.draw.width,self.draw.height
        scale=min(n/w,n/h)
        dw,dh=max(1,int(w*scale)),max(1,int(h*scale))
        target=self.master.draw
        try:
            target.set_scaling((dw+.001)/w,(dh+.001)/h,False)
            target._bytearray(x+(n-dw)//2,y+(n-dh)//2,w,h,self.draw.buffer)
        finally: target.set_scaling(1,1,False)
        self.draw.changed=False
    def stop(self):
        if self.module and self.started:
            try:
                for view in list(self.context.views.values()):
                    if view.active: view.stop(self.context)
            except Exception: pass
        self.module,self.context,self.draw,self.started=None,None,None,False
        self.focused=False
