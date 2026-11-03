"""Keyboard-driven single-word translation on the native PicoCalc screen."""
from picoware.system import buttons as k
from engtools.ui import theme
from engtools.calculator.render import Renderer
from .local import Dictionary


class PicoDict:
    def __init__(self):
        self.vm=None
        self.query='';self.cursor=0;self.direction='en-it'
        self.result='';self.message='Type a word, then ENTER';self.help=False

    def start(self,vm):
        self.vm=vm;self.dictionary=Dictionary(vm.storage)
        vm.input_manager.reset();self.draw();return True

    def stop(self,vm):
        self.dictionary=None;self.vm=None

    def search(self):
        self.result=''
        try:
            result=self.dictionary.lookup(self.query,self.direction)
            self.result=result or ''
            self.message='Translation found' if result else 'Word not found'
        except (ValueError,OSError) as exc:self.message=str(exc)

    def run(self,vm):
        button=vm.button
        if button==k.BUTTON_NONE:return
        if button==vm.input_manager._key_esc:
            if self.help:self.help=False
            else:vm.back();return
        elif button==k.BUTTON_F9:self.help=not self.help
        elif self.help:return
        elif button==k.BUTTON_F2:
            self.direction='it-en' if self.direction=='en-it' else 'en-it'
            self.result='';self.message='Type a word, then ENTER'
        elif button==k.BUTTON_F5:
            self.query='';self.cursor=0;self.result='';self.message='Type a word, then ENTER'
        elif button==k.BUTTON_CENTER:self.search()
        elif button==k.BUTTON_LEFT:self.cursor=max(0,self.cursor-1)
        elif button==k.BUTTON_RIGHT:self.cursor=min(len(self.query),self.cursor+1)
        else:
            changed=False
            if button in (k.BUTTON_BACKSPACE,k.BUTTON_DELETE,vm.input_manager._key_back):
                if self.cursor:
                    self.query=self.query[:self.cursor-1]+self.query[self.cursor:];self.cursor-=1;changed=True
            else:
                char=vm.input_manager.button_to_char(button)
                if char and len(char)==1 and char>=' ' and char!='\x7f' and len(self.query)<48:
                    self.query=self.query[:self.cursor]+char+self.query[self.cursor:];self.cursor+=1;changed=True
            if changed:self.result='';self.message='ENTER to translate'
        self.draw()

    def draw(self):
        vm=self.vm;d=vm.draw;w,h=int(d.size.x),int(d.size.y)
        p=theme.system_palette(vm)
        d.fill_screen(p.BG);theme.status(vm,p)
        theme.header(d,'PicoDict','PicoDESK',p,height=18,top=theme.STRIP)
        r=Renderer(d,(0,theme.STRIP+18,w,h),vm.selected_color)
        if self.help:
            lines=('PicoDict','ENTER: translate','F2: switch EN/IT direction','F5: clear word','LEFT/RIGHT: move cursor',
                   'BACK/DEL: erase before cursor','F9 / ESC: close help','Exact words; accents matter.',
                   'No match: try the infinitive.','WikDict / Wiktionary / DBnary','Data: CC BY-SA 4.0')
            for i,line in enumerate(lines):r.text(9,45+i*20,line,p.TEXT,0)
        else:
            label='English > Italian' if self.direction=='en-it' else 'Italian > English'
            r.text(9,48,label,p.ACCENT,1)
            r.rect(8,76,w-16,32,p.ACCENT)
            cw=r.metrics[1][0];capacity=max(1,(w-32)//cw-1)
            first=max(0,self.cursor-capacity)
            r.text(16,86,self.query[first:first+capacity],p.TEXT,1)
            x=16+(self.cursor-first)*cw;r.line(x,84,x,101,p.ACCENT)
            if self.result:
                r.text(9,133,'Translation',p.MUTED,0)
                capacity=max(1,(w-20)//cw)
                for i in range(0,len(self.result),capacity):
                    r.text(9,155+(i//capacity)*20,self.result[i:i+capacity],p.TEXT,1)
            # Wrap bounded status text, including missing/corrupt SD data errors.
            for i in range(0,len(self.message),45):
                r.text(9,h-70+(i//45)*12,self.message[i:i+45],p.MUTED,0)
            r.text(9,h-28,'F2 Direction   F5 Clear   ENTER Search',p.MUTED,0)
        theme.footer(d,'',palette=p);d.swap()
