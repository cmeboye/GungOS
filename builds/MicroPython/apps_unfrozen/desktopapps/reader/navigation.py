"""Cooperative chapter labels and chapter-local page navigation."""
from .epub import resolve,TxtBook
from engtools.ui import theme
from picoware.system import buttons as k
from time import ticks_ms,ticks_diff

class Navigation:
    def __init__(self,vm,book,chapter,page,counts):
        self.vm=vm;self.book=book;self.selected=chapter;self.chapter=chapter;self.page=page
        self.counts=counts;self.mode='list';self.digits='';self.error='';self.target=None
        self.labels={};self.label_bytes=0;self.job=self.load_labels() if hasattr(book,'archive') else None
        self.help=False
    def close(self):
        if self.job:self.job.close();self.job=None
    def label(self,index):
        if index in self.labels:return self.labels[index]
        if isinstance(self.book,TxtBook):return 'Text part %d'%(index+1)
        return self.book.chapters[index].rsplit('/',1)[-1].rsplit('.',1)[0]
    def remember(self,path,text):
        text=' '.join(text.split())[:80]
        if not text:return
        for i in range(len(self.book.chapters)):
            if self.book.chapters[i]==path and i not in self.labels:
                if self.label_bytes+len(text.encode('utf-8'))>16384:return
                self.labels[i]=text;self.label_bytes+=len(text.encode('utf-8'))
    def load_labels(self):
        package=None;resource=None;ncx=None
        for token in self.book.metadata('META-INF/container.xml',16384):
            yield None
            if token is not None and not isinstance(token,str) and token[0]=='rootfile' and not token[2] and package is None:
                package=resolve('',token[1].get('full-path',''))
        if not package:return
        for token in self.book.metadata(package):
            yield None
            if token is None or isinstance(token,str) or token[0]!='item' or token[2]:continue
            attrs=token[1]
            if 'nav' in attrs.get('properties','').split():resource=resolve(package,attrs.get('href',''))
            if attrs.get('media-type')=='application/x-dtbncx+xml':ncx=resolve(package,attrs.get('href',''))
        resource=resource or ncx
        if not resource:return
        stack=[];text=False;anchor=None;nav=False
        for token in self.book.metadata(resource):
            yield None
            if token is None:continue
            if isinstance(token,str):
                if anchor is not None:anchor[1]=(anchor[1]+token)[:80]
                if text and stack:stack[-1]=(stack[-1]+token)[:80]
                continue
            tag,attrs,closing=token
            if tag=='navpoint':
                if closing:
                    if stack:stack.pop()
                elif len(stack)<24:stack.append('')
                else:raise ValueError('Navigation nesting exceeds 24 levels')
            elif tag=='text':text=not closing
            elif tag=='content' and not closing and stack:
                self.remember(resolve(resource,attrs.get('src','')),stack[-1])
            elif tag=='nav':
                if closing:nav=False
                else:nav='toc' in attrs.get('type','').split() or 'doc-toc' in attrs.get('role','').split()
            elif tag=='a':
                if closing and anchor is not None:
                    self.remember(resolve(resource,anchor[0]),anchor[1]);anchor=None
                elif not closing and nav:anchor=[attrs.get('href',''),'']
    def step(self):
        if not self.job or self.help:return False
        before=len(self.labels)
        started=ticks_ms()
        try:
            for _ in range(8):
                next(self.job)
                if ticks_diff(ticks_ms(),started)>=8:break
        except StopIteration:self.close();return True
        except (OSError,ValueError,KeyError,MemoryError,UnicodeError):
            self.close();self.error='Titles unavailable; filenames shown';return True
        return len(self.labels)!=before
    def edit(self,mode):self.mode=mode;self.digits='';self.error=''
    def key(self,button):
        if button==k.BUTTON_F9:self.help=not self.help;return
        if self.help:return
        self.error=''
        if button==k.BUTTON_F1:self.edit('chapter');return
        if button==k.BUTTON_F2:self.edit('page');return
        char=self.vm.input_manager.button_to_char(button)
        if char and char.isdigit() and ord(char)<128:
            if self.mode=='list':self.edit('chapter')
            if len(self.digits)<6:self.digits+=char
            return
        if self.mode!='list':
            if button in (k.BUTTON_BACK,k.BUTTON_BACKSPACE,k.BUTTON_DELETE):self.digits=self.digits[:-1]
            elif button==k.BUTTON_CENTER:
                value=int(self.digits) if self.digits else 0
                bound=len(self.book.chapters) if self.mode=='chapter' else self.counts[self.chapter]
                if value<1 or bound and value>bound:self.error='Enter 1..%d'%bound if bound else 'Enter a positive page number'
                else:self.target=(value-1,0) if self.mode=='chapter' else (self.chapter,value-1)
            return
        if button==k.BUTTON_UP:self.selected=max(0,self.selected-1)
        elif button==k.BUTTON_DOWN:self.selected=min(len(self.book.chapters)-1,self.selected+1)
        elif button==k.BUTTON_LEFT:self.selected=max(0,self.selected-10)
        elif button==k.BUTTON_RIGHT:self.selected=min(len(self.book.chapters)-1,self.selected+10)
        elif button==k.BUTTON_CENTER:self.target=(self.selected,0)
    def draw(self):
        d=self.vm.draw;p=theme.system_palette(self.vm)
        if self.mode=='list' and not self.help:
            rows=[('%d. %s'%(i+1,self.label(i)),('Current chapter' if i==self.chapter else '')+(' / %d pages'%n if n else ' / pages not counted')) for i,n in enumerate(self.counts)]
            theme.menu(d,rows,self.selected,'Chapters','PicoReader',self.error or 'F1 Go chapter  F2 Go page  ESC reading',palette=p,error=bool(self.error),vm=self.vm)
        else:
            from engtools.calculator.render import Renderer
            d.fill_screen(p.BG);theme.status(self.vm,p);theme.header(d,'Navigation','PicoReader',p,height=18,top=theme.STRIP)
            r=Renderer(d,(8,42,312,300),self.vm.selected_color,p)
            lines=('Navigation help','Up/Down: select chapter','Left/Right: move ten chapters','Type a number: Go to chapter','F1: Go to chapter','F2: Go to page in current chapter','Page numbers use the reading font.','These are not printed-book pages.','ENTER: confirm  ESC: cancel','F9: return') if self.help else ('Go to '+self.mode,'Chapter %d, reading page %d'%(self.chapter+1,self.page+1),'Number: '+(self.digits or '_'),'ENTER confirms; ESC cancels','Page numbers use the current font.',self.error)
            for i,line in enumerate(lines):r.text(8,50+i*20,line,p.TEXT if i else p.ACCENT,0)
            theme.footer(d,'F9 Help',palette=p);d.swap()
