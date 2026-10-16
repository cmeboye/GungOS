"""Engineering-computer desktop: category tabs, resource panel and widget."""
from time import ticks_ms,ticks_diff
from picoware.system import buttons as keys
from picoware.system.font import FONT_XTRA_SMALL,FONT_SMALL
from picoware.system.resource_info import snapshot,lines
from .widget import WidgetHost


class Dashboard:
    def __init__(self,vm,state=None):
        from picoware.applications.library import CATEGORIES,SECTIONS
        from picoware.system.settings import Settings
        self.vm,self.categories,self.sections=vm,CATEGORIES,SECTIONS
        self.category,self.indices=(state[0],state[1][:]) if state else (0,[0]*4)
        self.focus,self.scroll='menu',0
        self.info,self.info_lines,self.next_info=None,[],0
        self.logo,self.theme=None,None
        self.status,self.error=None,''
        self.widget_rect=(132,114,184,184)
        self.widget=WidgetHost(vm,self.widget_rect)
        self.widget.load(Settings(vm.storage).screensaver)
        self.dirty=True
    def stop(self): self.widget.stop(); self.logo=None
    def update(self):
        now=ticks_ms()
        # Re-sample every five seconds only while the user is reading counters.
        # Otherwise idle heap fluctuations do not continually redraw the home.
        if self.info is None or (self.focus=='info' and ticks_diff(now,self.next_info)>=0):
            self.info=snapshot(self.vm); self.info_lines=lines(self.info)
            self.next_info=now+5000
            self.dirty=True
        current=self.vm.time.rtc.datetime() if self.vm.time.is_set else None
        connected=self.vm.has_wifi and self.vm.wifi.is_connected()
        status=(current[:6] if current else None,self.vm.battery.percentage,connected,
                self.vm.foreground_color,self.vm.background_color,self.vm.selected_color)
        if status!=self.status: self.status=status; self.dirty=True
        button=self.vm.button
        previous_focus=self.focus
        if button!=-1 and self.key(button): return
        widget_button=button if self.focus=='widget' and previous_focus=='widget' else -1
        if self.widget.step(widget_button): self.dirty=True
        if self.focus=='widget' and not self.widget.focused:
            self.focus='menu'; self.dirty=True
        if self.dirty: self.draw()
    def key(self,button):
        self.dirty=True
        if button==keys.BUTTON_F1:
            self.focus='menu' if self.focus=='info' else 'info'
            self.widget.focused=False
            if self.focus=='info': self.next_info=0
            return
        if self.focus=='widget': return
        if button==keys.BUTTON_I:
            from picoware.applications.library import launch
            launch(self.vm,'About')
            return True
        if button==keys.BUTTON_F3:
            if self.widget.module:
                self.focus='widget'; self.widget.focused=True
            else: self.error=self.widget.error or 'Choose a screensaver in Settings'
            return
        if button==keys.BUTTON_H:
            self.focus='menu' if self.focus=='help' else 'help'
            return
        if button == keys.BUTTON_ESCAPE:
            if self.focus!='menu': self.focus='menu'
            else: self.category=0; self.indices[0]=0
            self.error=''
            return
        if self.focus=='info':
            if button==keys.BUTTON_UP: self.scroll=max(0,self.scroll-1)
            elif button==keys.BUTTON_DOWN: self.scroll=min(max(0,len(self.info_lines)-7),self.scroll+1)
            return
        if self.focus=='help': return
        self.error=''
        if button in (keys.BUTTON_LEFT,keys.BUTTON_RIGHT):
            self.category=(self.category+(-1 if button==keys.BUTTON_LEFT else 1))%4
        elif button in (keys.BUTTON_UP,keys.BUTTON_DOWN):
            self.indices[self.category]=(self.indices[self.category]+(-1 if button==keys.BUTTON_UP else 1))%len(self.sections[self.category])
        elif button==keys.BUTTON_CENTER:
            from picoware.applications.library import launch
            launch(self.vm,self.sections[self.category][self.indices[self.category]])
            return True
    def draw(self):
        vm=self.vm; draw=vm.draw
        fg,bg=vm.foreground_color,vm.background_color
        accent=vm.selected_color if vm.selected_color!=0x001F else 0x4B7E
        theme=(fg,bg)
        if theme!=self.theme:
            from picoware.assets import dashboard_logo
            self.logo=dashboard_logo.decode(bg==0,bg)
            self.theme=theme
        draw.fill_screen(bg)
        from picoware.assets import dashboard_logo
        draw._bytearray(dashboard_logo.X,dashboard_logo.Y,dashboard_logo.WIDTH,dashboard_logo.HEIGHT,self.logo)
        # Battery/Wi-Fi/clock are compact and leave the logo artwork untouched.
        time=self.status[0] if self.status else None
        top=('%02d:%02d' % (time[4],time[5])) if time else '--:--'
        top+='  %d%%' % vm.battery.percentage
        if self.status and self.status[2]: top+=' WiFi'
        draw._text(10,5,top,fg,FONT_XTRA_SMALL)
        draw._rectangle(150,18,166,70,accent if self.focus=='info' else fg)
        for i,text in enumerate(self.info_lines[self.scroll:self.scroll+7]):
            draw._text(154,20+i*9,text[:26],fg,FONT_XTRA_SMALL)
        draw._fill_rectangle(0,92,320,18,accent)
        for i,label in enumerate(self.categories):
            draw._text(i*80+(80-draw.len(label,FONT_SMALL))//2,95,label,fg,FONT_SMALL)
        draw._fill_rectangle(self.category*80+5,108,70,2,fg)
        draw._rectangle(4,114,124,184,accent if self.focus=='menu' else fg)
        items=self.sections[self.category]
        selected=self.indices[self.category]
        for i,label in enumerate(items):
            y=122+i*22
            if i==selected: draw._fill_rectangle(7,y-3,118,20,accent)
            font=FONT_SMALL if draw.len(label,FONT_SMALL)<=110 else FONT_XTRA_SMALL
            draw._text(10,y,label,fg,font)
        x,y,n,_=self.widget_rect
        if self.widget.draw: self.widget.paint()
        elif self.widget.error:
            message='Widget: '+self.widget.error
            for i in range(0,min(len(message),125),28): draw._text(x+4,y+6+(i//28)*10,message[i:i+28],fg,FONT_XTRA_SMALL)
        draw._rectangle(x,y,n,n,accent if self.focus=='widget' else fg)
        draw._fill_rectangle(0,304,320,16,accent)
        if self.error:
            draw._text(4,294,self.error[:51],fg,FONT_XTRA_SMALL)
        draw._text(8,308,'H: Help   I: Info',fg,FONT_XTRA_SMALL)
        if self.focus=='help':
            draw._fill_rectangle(12,117,296,181,bg)
            draw._rectangle(12,117,296,181,accent)
            help_lines=('GungOS CONTROLS','Left/Right: choose category','Up/Down: choose menu item','Enter: open the selected item',
                        'Esc: return; root resets Apps','F1: focus system info; arrows scroll','F3: send input to the widget',
                        'Widget Esc returns to the menu','Settings > Screensaver selects widget',
                        'I: version, features and credits',
                        'H or Esc closes help')
            for i,text in enumerate(help_lines): draw._text(18,124+i*11,text[:47],fg,FONT_XTRA_SMALL)
        draw.swap(); self.dirty=False
