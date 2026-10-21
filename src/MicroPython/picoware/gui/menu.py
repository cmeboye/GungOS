"""Shared compact GungOS menu, retaining the system menu API."""
from picoware.gui import style


class Menu:
    def __init__(self,draw,title,y,height,text_color=0xFFFF,background_color=0,
                 selected_color=0x001F,border_color=0xFFFF,border_width=2,
                 brand='GungOS'):
        from picoware.system.vector import Vector
        self.display=draw;self._title=title;self.brand=brand
        self.position=Vector(0,y);self.size=Vector(draw.size.x,height)
        self.text_color=text_color;self.background_color=background_color
        self.selected_color=selected_color;self.border_color=border_color;self.border_width=border_width
        self.items=[];self._selected_index=0
        self.list=self
    @property
    def current_item(self):return self.get_item(self._selected_index)
    @property
    def item_count(self):return len(self.items)
    @property
    def list_height(self):return max(0,int(self.size.y)-style.HEAD_HEIGHT-style.FOOT_HEIGHT)
    @property
    def selected_index(self):return self._selected_index
    @property
    def title(self):return self._title
    @title.setter
    def title(self,value):self._title=value
    def add_item(self,item):self.items.append(item)
    def clear(self):self.items=[];self._selected_index=0
    def get_item(self,index):return self.items[index] if 0<=index<len(self.items) else ''
    def item_exists(self,item):return item in self.items
    def remove_item(self,index):
        if 0<=index<len(self.items):self.items.pop(index)
        self._selected_index=min(self._selected_index,max(0,len(self.items)-1))
    def set_selected(self,index,*args):self._selected_index=max(0,min(index,len(self.items)-1))
    def scroll_down(self,*args):
        if self.items:self._selected_index=(self._selected_index+1)%len(self.items)
        self.draw()
    def scroll_up(self,*args):
        if self.items:self._selected_index=(self._selected_index-1)%len(self.items)
        self.draw()
    def draw(self,*args):
        palette=style.colors(self.background_color,self.text_color,self.selected_color)
        rows=[(str(item),'') for item in self.items] or [('No entries available','')]
        style.menu(self.display,rows,self._selected_index,self.title,self.brand,palette=palette)
    def refresh(self):self.draw()
    def draw_title(self):self.draw()
