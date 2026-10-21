"""Independent productivity apps; PicoLAB remains an engineering launcher."""
from picoware.system import buttons as k
from engtools.ui import theme

ROWS=(('Eggcel','Spreadsheet and XY plots'),('PicoWord','Formatted notes and equations'),
      ('PicoPaint','Pixel canvas, tools and pattern fills'))


class Launcher:
    HELP=('PicoDESK:','UP/DOWN\tchoose an app','ENTER\topen it','ESC\treturn')
    def __init__(self,from_lab=False):
        self.vm=None;self.selected=0;self.keep=False;self.suspended=False
    def start(self,vm):
        self.vm=vm;self.keep=self.suspended=False;vm.input_manager.reset();self.draw();return True
    def stop(self,vm):
        if self.keep:self.keep=False;self.suspended=True;return
        self.suspended=False;self.vm=None
    def draw(self):
        theme.menu(self.vm.draw,ROWS,self.selected,'','PicoDESK',palette=theme.system_palette(self.vm),vm=self.vm)
    def run(self,vm):
        button=vm.button
        if button==k.BUTTON_NONE:return
        if button==vm.input_manager._key_esc:vm.back();return
        if button in (k.BUTTON_UP,k.BUTTON_DOWN):
            self.selected=(self.selected+(-1 if button==k.BUTTON_UP else 1))%len(ROWS);self.draw()
        elif button==k.BUTTON_CENTER:
            self.keep=True
            try:
                if self.selected==0:
                    from .eggcel.app import show;show(vm)
                elif self.selected==1:
                    from .word import Word
                    from engtools.plots.view import open_view
                    open_view(vm,'picoword',Word())
                elif self.selected==2:
                    from .paint import Paint
                    from engtools.plots.view import open_view
                    open_view(vm,'picopaint',Paint())
            except (ValueError,MemoryError):self.keep=False;raise


def show(vm,from_lab=False):
    from engtools.plots.view import open_view
    return open_view(vm,'picodesk',Launcher())
