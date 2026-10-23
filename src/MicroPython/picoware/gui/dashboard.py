"""Engineering-computer desktop: category tabs, resource panel and widget."""
from time import ticks_ms,ticks_diff
from picoware.system import buttons as keys
from picoware.system.font import FONT_XTRA_SMALL,FONT_SMALL
from picoware.system.features import FIRMWARE_VERSION
from picoware.system.resource_info import snapshot,lines
from .widget import WidgetHost
from .status_bar import StatusBar, foreground


# Coordinates use width/height, including one-pixel box outlines.
INFO_RECT=(139,17,180,25)
CATEGORY_RECT=(1,43,318,18)
MENU_RECT=(1,62,77,240)
WIDGET_RECT=(79,62,240,240)
WIDGET_SURFACE=(80,63,238,238)

HELP=('Desktop:','LEFT/RIGHT\tchoose a category','UP/DOWN\tchoose a menu item',
      'ENTER\topen the chosen item','ESC\tgo back to the first category',
      'F1\tsystem resources in detail','F3\tsend keys to the widget; its ESC returns',
      'Status:','Bars show heap, PSRAM and SD card in use',
      'Settings > Screensaver chooses the widget')


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
        self.focus='menu'
        self.info,self.next_info=None,0
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
            self.info=snapshot(self.vm)
            self.next_info=now+5000
            self.dirty=True
        status=self.status_bar.sample()
        if status!=self.status: self.status=status; self.dirty=True
        # F9 shows the desktop's help, except while the widget has the keys.
        self.vm.help=None if self.focus=='widget' else HELP
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
        if self.focus=='widget': return
        if button==keys.BUTTON_F1:
            self.vm.show('SYSTEM RESOURCES',lines(snapshot(self.vm)))
            self.dirty=False
            return True
        if button==keys.BUTTON_F3:
            if self.widget.module:
                self.focus='widget'; self.widget.focused=True
            else: self.error=self.widget.error or 'Choose a screensaver in Settings'
            return
        if button == keys.BUTTON_ESCAPE:
            self.category=0; self.indices[0]=0
            self.error=''
            return
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
        theme=(fg,bg,accent)
        if theme!=self.theme:
            from picoware.assets import dashboard_logo
            self.logo=dashboard_logo.decode(bg==0,bg,accent,fg)
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
        from .style import footer,system_palette
        footer(draw,self.error,bool(self.error),system_palette(vm),'v'+FIRMWARE_VERSION)
        draw.swap(); self.dirty=False

    def draw_info_summary(self):
        draw=self.vm.draw
        fg,bg=self.vm.foreground_color,self.vm.background_color
        accent=self.vm.selected_color
        outline(draw,INFO_RECT,fg)
        board=self.info['board'].replace('Raspberry Pi ','')
        heading=board+' / %d MHz' % self.info['frequency']
        panel_x,panel_y,panel_width,_=INFO_RECT
        # Labels sized for their widest value ("SD100%"), right-aligned to their bar; equal bars share the rest.
        gap=2
        labels=(('Heap','H'),('PSRAM','P'),('SD','SD'))
        label_widths=[draw.len(label+'100%',FONT_XTRA_SMALL)+2 for _,label in labels]
        bar_width=(panel_width-6-2*gap-sum(label_widths))//3
        draw._text(panel_x+4,panel_y+3,heading[:35],fg,FONT_XTRA_SMALL)
        x=panel_x+3
        for (name,label),label_width in zip(labels,label_widths):
            row=next((row for row in self.info['rows'] if row[0]==name),None)
            percent=None
            if row and row[2] is not None and row[3]:
                percent=max(0,min(100,int(row[2]*100/row[3])))
            text=label+('---%' if percent is None else '%03d%%' % percent)
            draw._text(x+label_width-2-draw.len(text,FONT_XTRA_SMALL),panel_y+14,text,fg,FONT_XTRA_SMALL)
            outline(draw,(x+label_width,panel_y+14,bar_width,8),fg)
            if percent is not None:
                fill=((bar_width-2)*percent+50)//100
                if fill: draw._fill_rectangle(x+label_width+1,panel_y+15,fill,6,accent)
            x+=label_width+bar_width+gap
