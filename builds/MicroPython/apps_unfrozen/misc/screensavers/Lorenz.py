"""Paced Lorenz attractor: a bounded trail and no plotting-app dependency."""
from array import array
from time import ticks_ms,ticks_diff,ticks_add
from picoware.system import buttons as k

WIDGET_NATIVE=True
POINTS=192
_trail=None
_count=_head=0
_x,_y,_z=0.1,0.0,0.0
_next=0
_paused=False

def start(vm):
    global _trail,_count,_head,_x,_y,_z,_next,_paused
    _trail=array('h',[0]*(POINTS*2))
    _count,_head,_x,_y,_z,_next,_paused=0,0,0.1,0.0,0.0,0,False
    return True

def run(vm):
    global _count,_head,_x,_y,_z,_next,_paused
    if vm.button == k.BUTTON_ESCAPE: vm.back(); return
    if vm.button==k.BUTTON_SPACE: _paused=not _paused; _next=0
    if vm.button==k.BUTTON_F5: start(vm)
    now=ticks_ms()
    if ticks_diff(now,_next)<0: return
    _next=ticks_add(now,125)
    draw=vm.draw
    width,height=int(draw.size.x),int(draw.size.y)
    left,right,top,bottom=24,width-10,34,height-22
    if not _paused:
        # Midpoint integration is stable at this fixed small step. Four new
        # samples per frame keep motion visible while drawing remains 8 Hz.
        for _ in range(4):
            for step in range(12):
                dt=0.006
                dx,dy,dz=10*(_y-_x),_x*(28-_z)-_y,_x*_y-(8/3)*_z
                x,y,z=_x+dx*dt/2,_y+dy*dt/2,_z+dz*dt/2
                _x+=10*(y-x)*dt; _y+=(x*(28-z)-y)*dt; _z+=(x*y-(8/3)*z)*dt
            px=max(left,min(right,int(left+(_x+25)*(right-left)/50)))
            py=max(top,min(bottom,int(bottom-_z*(bottom-top)/55)))
            _trail[_head*2],_trail[_head*2+1]=px,py
            _head=(_head+1)%POINTS; _count=min(POINTS,_count+1)
    fg,bg=vm.foreground_color,vm.background_color
    draw.fill_screen(bg)
    draw._text(8,8,'GungOS / LORENZ',fg,0)
    draw._text(8,21,'sigma=10 rho=28 beta=8/3',0x7BEF,0)
    draw._line(left,top,left,bottom,0x7BEF)
    draw._line(left,bottom,right,bottom,0x7BEF)
    draw._text(8,top,'z',fg,0); draw._text(right-6,bottom+3,'x',fg,0)
    from picoware.gui.style import system_palette
    palette=system_palette(vm)
    colors=(palette.PANEL,palette.SELECT,palette.AXIS,palette.ACCENT,palette.TEXT)
    first=(_head-_count)%POINTS
    for i in range(1,_count):
        a,b=(first+i-1)%POINTS,(first+i)%POINTS
        draw._line(_trail[a*2],_trail[a*2+1],_trail[b*2],_trail[b*2+1],colors[min(4,i*5//max(1,_count))])
    draw._text(8,height-9,'SPACE pause  F5 reset  ESC exit',fg,0)
    draw.swap()

def stop(vm):
    global _trail
    _trail=None
