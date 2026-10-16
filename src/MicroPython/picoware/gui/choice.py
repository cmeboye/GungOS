"""Choice dialogs use the shared compact menu styling."""
from picoware.gui.menu import Menu


class Choice:
    def __init__(self,draw,position,size,title,options,initial_state=0,
                 foreground_color=0xFFFF,background_color=0,selected_color=None):
        self.display=draw;self.position=position;self.size=size;self.title=title
        self.options=options;self._state=initial_state
        self.foreground_color=foreground_color;self.background_color=background_color
        self.selected_color=getattr(draw,'theme_color',0x001F) if selected_color is None else selected_color
        self.use_lvgl=False
    @property
    def state(self):return self._state
    @state.setter
    def state(self,value):self._state=max(0,min(value,len(self.options)-1));self.draw()
    def clear(self):self.display.fill_screen(self.background_color)
    def draw(self):
        menu=Menu(self.display,self.title,self.position.y,self.size.y,self.foreground_color,
                  self.background_color,self.selected_color)
        for option in self.options:menu.add_item(option)
        menu.set_selected(self._state);menu.draw()
    def scroll_up(self):
        if self.options:self._state=(self._state-1)%len(self.options)
        self.draw()
    def scroll_down(self):
        if self.options:self._state=(self._state+1)%len(self.options)
        self.draw()
