"""Native-size categorical charts, with bounded pie tessellation and paging."""
from math import sin,cos,pi
from picoware.system import buttons as k
from picoware.gui.style import system_palette
from engtools.calculator.render import Renderer


class Chart:
    def __init__(self,spec):
        self.spec=spec;self.vm=None;self.selected=0;self.series=0;self.first=0
        self.groups=6;self.help=False;self.error='';self.grid=True
    def start(self,vm):self.vm=vm;vm.input_manager.reset();self.draw_safe();return True
    def stop(self,vm):self.vm=None;self.spec=None
    def run(self,vm):
        button=vm.button
        if button==k.BUTTON_NONE:return
        if button==vm.input_manager._key_esc:vm.back();return
        try:
            if button==k.BUTTON_F9:self.help=not self.help
            elif self.spec['kind']=='pie':
                if button in (k.BUTTON_LEFT,k.BUTTON_UP,k.BUTTON_RIGHT,k.BUTTON_DOWN):
                    self.selected=(self.selected+(-1 if button in (k.BUTTON_LEFT,k.BUTTON_UP) else 1))%len(self.spec['items'])
            else:
                if button in (k.BUTTON_LEFT,k.BUTTON_RIGHT):self.selected=max(0,min(len(self.spec['labels'])-1,self.selected+(-1 if button==k.BUTTON_LEFT else 1)))
                elif button in (k.BUTTON_UP,k.BUTTON_DOWN):self.series=(self.series+(-1 if button==k.BUTTON_UP else 1))%len(self.spec['series'])
                elif button in (k.BUTTON_PLUS,k.BUTTON_EQUAL,k.BUTTON_MINUS):self.groups=max(2,min(12,self.groups+(1 if button==k.BUTTON_MINUS else -1)))
                elif button==k.BUTTON_F:self.selected,self.first,self.groups=0,0,6
                elif button==k.BUTTON_G:self.grid=not self.grid
            self.draw_safe()
        except Exception as error:self.error=str(error);self.draw_safe()
    def draw_safe(self):
        try:self.draw()
        except Exception as error:
            self.error=str(error)
            d=self.vm.draw;d.fill_screen(self.vm.background_color)
            d._text(8,30,'Chart error / workbook retained',0xF800,0)
            d._text(8,60,self.error[:48],self.vm.foreground_color,0)
            d._text(8,90,'ESC returns to the worksheet',self.vm.foreground_color,0);d.swap()
    def draw(self):
        d=self.vm.draw;p=system_palette(self.vm);w,h=int(d.size.x),int(d.size.y)
        r=Renderer(d,(0,18,w,h),p.ACCENT)
        d.fill_screen(p.BG)
        from engtools.ui import theme
        theme.header(d,'Eggcel / Plot','PicoDESK',p,height=18)
        r.fill(0,18,w,23,p.PANEL);r.text(8,25,'Eggcel / '+('2D pie' if self.spec['kind']=='pie' else '2D column'),p.ACCENT,1)
        r.text(8,49,(self.spec['title']+(' | '+self.spec.get('note','') if self.spec['kind']=='pie' and self.spec.get('note') else ''))[:49],p.TEXT,0)
        if self.spec['kind']=='pie':self.pie(r,p,w,h)
        else:self.columns(r,p,w,h)
        r.fill(0,h-(36 if self.help else 13),w,36 if self.help else 13,p.PANEL)
        r.text(6,h-(32 if self.help else 10),'ARROWS inspect   F9 Help   ESC sheet',p.ACCENT,0)
        if self.help:
            r.text(6,h-21,'Column: +/- zoom  F reset  G grid',p.MUTED,0)
            r.text(6,h-10,'Pie: arrows select a slice and its label',p.MUTED,0)
        d.swap()
    def columns(self,r,p,w,h):
        spec=self.spec;n=len(spec['labels']);self.groups=min(self.groups,max(2,n))
        if self.selected<self.first:self.first=self.selected
        if self.selected>=self.first+self.groups:self.first=self.selected-self.groups+1
        first,last=self.first,min(n,self.first+self.groups);count=last-first
        left,right,top,bottom=36,w-10,89,241 if self.help else 250
        low,high=spec['bounds'];span=high-low;pad=span*.08
        lo=low-pad if low<0 else 0;hi=high+pad if high>0 else 0
        if hi==lo:hi=lo+1
        def ypos(value):return int(bottom-(value-lo)*(bottom-top)/(hi-lo))
        zero=ypos(0)
        r.rect(left,top,right-left+1,bottom-top+1,p.GRID)
        for j in range(5):
            value=lo+(hi-lo)*j/4;y=ypos(value)
            if self.grid:r.line(left,y,right,y,p.GRID)
            if abs(y-zero)>9:r.text(2,y-3,('%.3g'%value)[:6],p.MUTED,0)
        r.line(left,zero,right,zero,p.AXIS);r.text(2,zero-3,'0',p.MUTED,0)
        stride=(right-left)/max(1,count);bar=max(1,int(stride*.78/len(spec['series'])))
        for offset,index in enumerate(range(first,last)):
            gx=int(left+offset*stride+stride*.11)
            for series,item in enumerate(spec['series']):
                value=item['values'][index]
                if value is None:continue
                y=ypos(value);x=gx+series*bar
                r.fill(x,min(zero,y),max(1,bar-1),max(1,abs(zero-y)),item['color'])
                if index==self.selected and series==self.series:r.rect(x-1,min(zero,y)-1,max(2,bar),max(3,abs(zero-y)+2),p.TEXT)
            r.text(int(left+offset*stride+2),bottom+5,spec['labels'][index][:max(1,int(stride)//6)],p.ACCENT if index==self.selected else p.MUTED,0)
        item=spec['series'][self.series];value=item['values'][self.selected]
        r.text(8,65,(spec['labels'][self.selected]+' | '+item['name']+' = '+('gap' if value is None else '%.7g'%value))[:50],p.TEXT,0)
        y=bottom+20
        for i,item in enumerate(spec['series']):
            x=8+i*(w//3);r.fill(x,y+1,6,6,item['color']);r.text(x+10,y,item['name'][:13],p.TEXT if i==self.series else p.MUTED,0)
        r.text(8,y+13,(str(self.selected+1)+'/'+str(n)+' categories '+spec.get('note',''))[:50],p.MUTED,0)
    def pie(self,r,p,w,h):
        items=self.spec['items'];total=self.spec['total'];cx,cy,radius=w//2,155,77
        # At most 96 triangles plus slice boundaries; independent of numeric size.
        hues=(p.ACCENT,)+tuple(color for color in (0xFD20,0xF81F,0x07E0,0xFFE0,0xA51F,0x07FF,0xF800,0xFFFF) if sum(abs(((color>>s)&m)-((p.ACCENT>>s)&m)) for s,m in ((11,31),(5,63),(0,31)))>20)
        angle=-pi/2
        for index,(label,value) in enumerate(items):
            end=angle+2*pi*value/total;segments=max(1,int((end-angle)*12)+1)
            a=angle
            for part in range(segments):
                b=angle+(end-angle)*(part+1)/segments
                x1,y1=int(cx+radius*cos(a)),int(cy+radius*sin(a))
                x2,y2=int(cx+radius*cos(b)),int(cy+radius*sin(b))
                self.vm.draw._fill_triangle(cx,cy,x1,y1,x2,y2,hues[index%len(hues)])
                if index==self.selected:r.line(x1,y1,x2,y2,p.TEXT)
                a=b
            if index==self.selected:
                r.line(cx,cy,int(cx+radius*cos(angle)),int(cy+radius*sin(angle)),p.TEXT)
                r.line(cx,cy,int(cx+radius*cos(end)),int(cy+radius*sin(end)),p.TEXT)
            angle=end
        label,value=items[self.selected]
        r.text(8,65,(label+' = %.7g (%.2f%%)'%(value,100*value/total))[:50],p.TEXT,0)
        capacity=3 if self.help else 5;first=max(0,self.selected-capacity+1)
        for index in range(first,min(len(items),first+capacity)):
            label,value=items[index];y=239+(index-first)*11
            r.fill(8,y+1,6,6,hues[index%len(hues)])
            r.text(20,y,('> ' if index==self.selected else '  ')+label[:29]+' %.1f%%'%(100*value/total),p.TEXT if index==self.selected else p.MUTED,0)
        r.text(w-43,225,str(self.selected+1)+'/'+str(len(items)),p.MUTED,0)


def show(vm,spec):
    from engtools.plots.view import open_view
    return open_view(vm,'eggcel_chart',Chart(spec))
