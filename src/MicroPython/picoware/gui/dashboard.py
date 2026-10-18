"""Engineering-computer desktop: category tabs, resource panel and widget."""
from time import ticks_ms,ticks_diff
from picoware.system import buttons as keys
from picoware.system.font import FONT_XTRA_SMALL,FONT_SMALL
from picoware.system.features import FIRMWARE_VERSION
from picoware.system.resource_info import snapshot,lines
from .widget import WidgetHost
from .status_bar import StatusBar, foreground


# Coordinates use width/height, including one-pixel box outlines.
INFO_RECT=(93,17,226,25)
CATEGORY_RECT=(1,43,318,18)
MENU_RECT=(1,62,77,240)
WIDGET_RECT=(79,62,240,240)
WIDGET_SURFACE=(80,63,238,238)
FOOTER_RECT=(1,303,318,16)
INFO_CAPACITY=20


def outline(draw,rect,color):
    # Native rectangle uses endpoint deltas; use explicit pixel bounds here.
    x,y,w,h=rect
    draw._line(x,y,x+w-1,y,color)
    draw._line(x,y+h-1,x+w-1,y+h-1,color)
    draw._line(x,y,x,y+h-1,color)
    draw._line(x+w-1,y,x+w-1,y+h-1,color)


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
        self.status_bar=StatusBar(vm)
        self.widget_rect=WIDGET_RECT
        self.widget=WidgetHost(vm,WIDGET_SURFACE)
        self.widget_name=Settings(vm.storage).screensaver
        self.widget.load(self.widget_name)
        self.dirty=True
    def stop(self): self.widget.stop(); self.logo=None
    def update(self):
        now=ticks_ms()
        # Compact usage bars share the detailed resource snapshot, sampled at 5s.
        if self.info is None or ticks_diff(now,self.next_info)>=0:
            self.info=snapshot(self.vm); self.info_lines=lines(self.info)
            self.next_info=now+5000
            self.dirty=True
        status=self.status_bar.sample()
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
            elif button==keys.BUTTON_DOWN: self.scroll=min(max(0,len(self.info_lines)-INFO_CAPACITY),self.scroll+1)
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
        accent=vm.selected_color
        accent_fg=foreground(accent)
        theme=(fg,bg)
        if theme!=self.theme:
            from picoware.assets import dashboard_logo
            self.logo=dashboard_logo.decode(bg==0,bg)
            self.theme=theme
        draw.fill_screen(bg)
        from picoware.assets import dashboard_logo
        draw._bytearray(dashboard_logo.X,dashboard_logo.Y,dashboard_logo.WIDTH,dashboard_logo.HEIGHT,self.logo)
        self.status_bar.draw(self.status or self.status_bar.sample())
        self.draw_info_summary()
        draw._fill_rectangle(*CATEGORY_RECT,accent)
        tab_x,tab_y,tab_width,tab_height=CATEGORY_RECT
        count=len(self.categories)
        for i,label in enumerate(self.categories):
            left=tab_x+i*tab_width//count
            right=tab_x+(i+1)*tab_width//count
            draw._text(left+(right-left-draw.len(label,FONT_SMALL))//2,tab_y+3,label,accent_fg,FONT_SMALL)
            if i==self.category:
                draw._fill_rectangle(left+5,tab_y+tab_height-2,right-left-10,2,accent_fg)
        outline(draw,MENU_RECT,accent if self.focus=='menu' else fg)
        items=self.sections[self.category]
        selected=self.indices[self.category]
        font=FONT_XTRA_SMALL
        line_height=draw.get_font(font).height
        capacity=(MENU_RECT[2]-12)//max(1,draw.len('M',font))
        menu_x,menu_y,menu_width,_=MENU_RECT
        y=menu_y+6
        for i,label in enumerate(items):
            wrapped=[]
            while len(label)>capacity:
                cut=label.rfind(' ',0,capacity+1)
                if cut<1: cut=capacity
                wrapped.append(label[:cut])
                label=label[cut:].lstrip()
            wrapped.append(label)
            row_height=max(23,len(wrapped)*(line_height+1)+6)
            if i==selected: draw._fill_rectangle(menu_x+3,y,menu_width-6,row_height-1,accent)
            text_y=y+(row_height-len(wrapped)*(line_height+1))//2
            for line in wrapped:
                draw._text(menu_x+6,text_y,line,accent_fg if i==selected else fg,font)
                text_y+=line_height+1
            y+=row_height
        x,y,w,h=self.widget_rect
        if self.widget.draw: self.widget.paint()
        elif self.widget.error:
            message='Widget: '+self.widget.error
            for i in range(0,min(len(message),150),33):
                draw._text(x+6,y+8+(i//33)*11,message[i:i+33],fg,FONT_XTRA_SMALL)
        else:
            draw._text(x+9,y+94,'Select a widget in',fg,FONT_XTRA_SMALL)
            draw._text(x+9,y+108,'Settings > Screensaver',fg,FONT_XTRA_SMALL)
        outline(draw,(x,y,w,h),accent if self.focus=='widget' else fg)
        draw._fill_rectangle(*FOOTER_RECT,accent)
        if self.error:
            draw._fill_rectangle(2,284,316,17,bg)
            draw._text(5,288,self.error[:51],fg,FONT_XTRA_SMALL)
        draw._text(FOOTER_RECT[0]+7,FOOTER_RECT[1]+4,'H: Help   I: Info',foreground(accent),FONT_XTRA_SMALL)
        version='v'+FIRMWARE_VERSION
        version_x=FOOTER_RECT[0]+FOOTER_RECT[2]-7-draw.len(version,FONT_XTRA_SMALL)
        draw._text(version_x,FOOTER_RECT[1]+4,version,accent_fg,FONT_XTRA_SMALL)
        if self.focus=='info':
            draw._fill_rectangle(4,65,312,235,bg)
            outline(draw,(4,65,312,235),accent)
            draw._text(10,72,'SYSTEM RESOURCES / F1 or ESC closes',fg,FONT_XTRA_SMALL)
            for i,text in enumerate(self.info_lines[self.scroll:self.scroll+INFO_CAPACITY]):
                draw._text(10,87+i*10,text[:50],fg,FONT_XTRA_SMALL)
            draw._text(10,289,'UP/DOWN scroll',fg,FONT_XTRA_SMALL)
        if self.focus=='help':
            draw._fill_rectangle(4,65,312,235,bg)
            outline(draw,(4,65,312,235),accent)
            help_lines=('GungOS CONTROLS','Left/Right: choose category','Up/Down: choose menu item','Enter: open the selected item',
                        'Esc: return; root resets Apps','F1: resource details; arrows scroll','F3: send input to the widget',
                        'Widget Esc returns to the menu','Settings > Screensaver selects widget',
                        'Usage bars: heap / PSRAM / SD used',
                        'I: version, features and credits','Alt+S: save a screenshot to SD',
                        'H or Esc closes help')
            for i,text in enumerate(help_lines): draw._text(10,74+i*16,text[:49],fg,FONT_XTRA_SMALL)
        draw.swap(); self.dirty=False

    def draw_info_summary(self):
        draw=self.vm.draw
        fg,bg=self.vm.foreground_color,self.vm.background_color
        accent=self.vm.selected_color
        outline(draw,INFO_RECT,accent if self.focus=='info' else fg)
        board=self.info['board'].replace('Raspberry Pi ','')
        heading=board+' / %d MHz' % self.info['frequency']
        panel_x,panel_y,panel_width,_=INFO_RECT
        start_x=panel_x+4
        stride=(panel_width-8)//3
        bar_width=stride-44
        draw._text(start_x,panel_y+3,heading[:35],fg,FONT_XTRA_SMALL)
        for index,(name,label) in enumerate((('Heap','H'),('PSRAM','P'),('SD','SD'))):
            row=next((row for row in self.info['rows'] if row[0]==name),None)
            percent=None
            if row and row[2] is not None and row[3]:
                percent=max(0,min(100,int(row[2]*100/row[3])))
            x=start_x+index*stride
            text=label+('--' if percent is None else '%d%%' % percent)
            draw._text(x,panel_y+14,text,fg,FONT_XTRA_SMALL)
            outline(draw,(x+37,panel_y+15,bar_width,6),fg)
            if percent is not None:
                fill=((bar_width-2)*percent+50)//100
                if fill: draw._fill_rectangle(x+38,panel_y+16,fill,4,accent)
