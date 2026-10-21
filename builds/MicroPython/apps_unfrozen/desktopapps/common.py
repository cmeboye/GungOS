"""Shared native-size application chrome and verified explicit SD documents."""
from picoware.system import buttons as k
from engtools.calculator.render import Renderer
from engtools.ui.theme import system_palette,header,status,STRIP
from .icons import TOP,page_name

COLORS=(('Black',0),('White',0xFFFF),('Red',0xF800),('Orange',0xFD20),
        ('Yellow',0xFFE0),('Green',0x07E0),('Cyan',0x07FF),('Blue',0x001F),
        ('Navy',0x0010),('Purple',0x8010),('Pink',0xF81F),('Brown',0x8200),
        ('Gray',0x8410),('Silver',0xC618),('Teal',0x0410),('Olive',0x8400))


def name_for(text,extension):
    text=text.strip()
    if text.lower().endswith(extension): text=text[:-len(extension)]
    if not text or len(text)>32 or text.startswith('.') or any(
            not (c.isalpha() or c.isdigit() or c in ' _-.') for c in text):
        raise ValueError('Use 1..32 letters/numbers/spaces/_/-')
    return text+extension


def write_chunks(storage,path,chunks,limit=100000):
    """Verify bounded chunks before replacing any existing document."""
    if not storage.active: raise OSError('SD card unavailable')
    storage.mkdir('picoware/documents')
    storage.mkdir(path.rsplit('/',1)[0])
    temporary,backup=path+'.tmp',path+'.bak'
    if not storage.write(temporary,''): raise OSError('Cannot create temporary file')
    offset=0
    for chunk in chunks:
        if isinstance(chunk,str): chunk=chunk.encode('utf-8')
        if offset+len(chunk)>limit: raise ValueError('Document size limit reached')
        # Binary Storage.write appends. The temporary file was truncated above.
        if not storage.write(temporary,chunk,'wb') or storage.read(temporary,'rb',offset,len(chunk))!=bytes(chunk):
            raise OSError('Write verification failed; original kept')
        offset+=len(chunk)
    if storage.size(temporary)!=offset: raise OSError('File size verification failed')
    existed=storage.exists(path)
    if existed:
        if storage.exists(backup): raise OSError('Keep/recover the existing .bak first')
        if not storage.rename(path,backup): raise OSError('Cannot back up original')
    if not storage.rename(temporary,path):
        if existed: storage.rename(backup,path)
        raise OSError('Replacement failed; original in file/.bak')
    if existed: storage.remove(backup)


def chunks(data,size=1024):
    if isinstance(data,str): data=data.encode('utf-8')
    view=memoryview(data)
    for index in range(0,len(data),size): yield view[index:index+size]


# F9 help shared by the PicoDESK document apps; each app adds its own keys.
FILE_HELP=('File:','F2\tfile menu: new, open, save, export',
           'Menus:','UP/DOWN\tchoose','ENTER\tconfirm','ESC\tclose the menu')


class FileApp:
    title='App';extension='.json';export_extension='.txt';directory='picoware/documents'
    theme_option=False;HELP=FILE_HELP;ICON=None
    def __init__(self):
        self.vm=None;self.model=self.fresh()
        self.page,self.return_page,self.selected='edit','edit',0
        self.filename,self.error,self.message='','',''
        self.buffer,self.cursor='',0
        self.files=[];self.purpose='';self.pending=self.after_save=self.overwrite=None
    def start(self,vm):
        self.vm=vm;vm.input_manager.reset();self.draw();return True
    def stop(self,vm): self.vm=self.model=None
    def reset_cursor(self): pass
    def menu(self,page,selected=0,return_page='edit'):
        self.page,self.selected,self.return_page=page,selected,return_page
    def guard(self,action):
        if self.model.dirty: self.pending=action;self.menu('confirm')
        else:self.perform(action)
    def perform(self,action):
        self.pending=None
        if action=='quit':self.vm.back();return
        if action in ('new','example'):
            model=self.fresh() if action=='new' else self.example()
            self.model,self.filename,self.page=model,'','edit';self.message='';self.reset_cursor()
        elif action=='open':
            self.files=sorted(n for n in self.vm.storage.listdir(self.directory) if n.lower().endswith(self.extension))
            self.menu('files')
    def prompt(self,purpose,text):
        self.page,self.purpose,self.buffer,self.cursor='dialog',purpose,text,len(text)
    def save(self,as_new=False):
        if self.filename and not as_new:self.write(self.filename)
        else:self.prompt('save',self.filename.rsplit('/',1)[-1][:-len(self.extension)] if self.filename else 'Untitled')
    def write(self,path,export=False):
        write_chunks(self.vm.storage,path,self.encode(export))
        self.page,self.message='edit','Saved '+path.rsplit('/',1)[-1]
        if not export:
            self.filename,self.model.dirty=path,False
            # Undo after a successful save must still prompt for unsaved changes.
            if self.model.undo is not None:self.model.mark_saved()
            if self.after_save:
                action,self.after_save=self.after_save,None;self.perform(action)
    def rows(self):
        if self.page=='file':return ('New','Open','Save','Save as','Export '+self.export_extension,'Load example')
        if self.page=='files':return self.files
        if self.page=='confirm':return ('Save then continue','Discard changes','Keep editing')
        if self.page=='overwrite':return ('Replace existing file','Cancel')
        return ()
    def palette(self):return (('Theme text',None),)+COLORS if self.theme_option else COLORS
    def choose(self):
        i=self.selected
        if self.page=='file':
            if i==0:self.guard('new')
            elif i==1:self.guard('open')
            elif i==2:self.save()
            elif i==3:self.save(True)
            elif i==4:self.prompt('export','Untitled')
            else:self.guard('example')
        elif self.page=='files' and self.files:
            path=self.directory+'/'+self.files[i]
            model=self.load(path)
            self.model,self.filename,self.page=model,path,'edit';self.reset_cursor()
        elif self.page=='confirm':
            if i==0:self.after_save=self.pending;self.save()
            elif i==1:self.perform(self.pending)
            else:self.page='edit';self.pending=self.after_save=None
        elif self.page=='overwrite':
            if i==0:self.write(*self.overwrite)
            else:self.page='dialog'
    def common(self,button):
        if self.page=='edit':
            if button==k.BUTTON_F2:self.menu('file');return True
            return False
        if self.page=='equation':return False
        if self.page=='dialog':
            if button==self.vm.input_manager._key_esc:self.page,self.after_save='edit',None
            elif button==k.BUTTON_CENTER:
                export=self.purpose=='export'
                path=self.directory+'/'+name_for(self.buffer,self.export_extension if export else self.extension)
                if self.vm.storage.exists(path):self.overwrite=(path,export);self.menu('overwrite',1)
                else:self.write(path,export)
            elif button==k.BUTTON_F5:self.buffer,self.cursor='',0
            elif button==k.BUTTON_LEFT:self.cursor=max(0,self.cursor-1)
            elif button==k.BUTTON_RIGHT:self.cursor=min(len(self.buffer),self.cursor+1)
            elif button in (k.BUTTON_BACKSPACE,self.vm.input_manager._key_back):
                if self.cursor:self.buffer=self.buffer[:self.cursor-1]+self.buffer[self.cursor:];self.cursor-=1
            elif button==k.BUTTON_DELETE:self.buffer=self.buffer[:self.cursor]+self.buffer[self.cursor+1:]
            else:
                char=self.vm.input_manager.button_to_char(button)
                if char and char not in ('\n','\r','\t') and len(self.buffer)<40:
                    self.buffer=self.buffer[:self.cursor]+char+self.buffer[self.cursor:];self.cursor+=1
        elif button==self.vm.input_manager._key_esc:
            if self.page=='confirm':self.pending=self.after_save=None
            self.page=self.return_page
        elif button in (k.BUTTON_UP,k.BUTTON_DOWN,k.BUTTON_LEFT,k.BUTTON_RIGHT):
            total=len(self.palette()) if self.page=='color' else len(self.rows())
            step=(-4 if button==k.BUTTON_UP else 4) if self.page=='color' and button in (k.BUTTON_UP,k.BUTTON_DOWN) else (-1 if button in (k.BUTTON_UP,k.BUTTON_LEFT) else 1)
            self.selected=(self.selected+step)%max(1,total)
        elif button==k.BUTTON_CENTER:self.choose()
        return True
    def tick(self):return False
    def run(self,vm):
        button=vm.button
        if button==k.BUTTON_NONE:
            try:
                if self.tick():self.draw()
            except (ValueError,OSError,MemoryError) as exc:self.error=str(exc);self.draw()
            return
        try:
            self.error=''
            if not self.common(button):self.input(button)
        except (ValueError,OSError,MemoryError) as exc:self.error=str(exc) or 'Not enough memory'
        if self.vm is not None:self.draw()
    @property
    def bottom(self):return int(self.vm.draw.size.y)-12
    def renderer(self,clip=None):
        d=self.vm.draw
        return Renderer(d,clip or (0,TOP,int(d.size.x),int(d.size.y)),self.vm.selected_color)
    def chrome(self):
        d=self.vm.draw;w,h=int(d.size.x),int(d.size.y)
        p=system_palette(self.vm);r=self.renderer()
        d.fill_screen(p.BG)
        status(self.vm,p)
        # App / document / page: the header names the open file.
        name=(self.filename.rsplit('/',1)[-1] if self.filename else 'Untitled')+(' *' if self.model.dirty else '')
        page='' if self.page in ('edit','equation') else ' / '+page_name(self.page)
        header(d,self.title+' / '+name+page,'PicoDESK',p,height=18,top=STRIP,rows=self.ICON)
        return r,p,w,h
    def draw_footer(self,r,p,w,h):
        r.fill(0,self.bottom,w,h-self.bottom,p.PANEL)
        r.text(6,self.bottom+2,'F9 Help',p.ACCENT,0)
        message=self.error or self.message
        if message:r.text(54,self.bottom+2,message[:(w-60)//6],p.ERROR if self.error else p.MUTED,0)
    def draw_menu(self,r,p,w,h):
        title={'file':'FILE','files':'OPEN','confirm':'UNSAVED CHANGES','overwrite':'REPLACE FILE?',
               'dialog':self.purpose.upper(),'color':'COLOUR'}.get(self.page,self.page.upper())
        r.text(9,45,title,p.ACCENT,1)
        if self.page=='dialog':
            r.rect(8,78,w-16,32,p.ACCENT)
            start=max(0,self.cursor-(w-44)//8)
            r.text(16,88,self.buffer[start:start+(w-32)//8],p.TEXT,1)
            x=16+(self.cursor-start)*8;r.line(x,88,x,100,p.ACCENT)
            r.text(9,126,'ENTER saves  F5 clears  ESC cancels',p.MUTED,0)
        elif self.page=='color':
            for i,(label,color) in enumerate(self.palette()):
                x,y=10+(i%4)*77,68+(i//4)*41
                r.fill(x,y,67,22,p.TEXT if color is None else color)
                r.rect(x-2,y-2,71,26,p.ACCENT if i==self.selected else p.GRID)
                if i==self.selected:r.rect(x-3,y-3,73,28,p.TEXT)
                r.text(x,y+25,label[:11],p.TEXT,0)
        else:
            rows=self.rows();capacity=max(1,(self.bottom-80)//27)
            first=max(0,self.selected-capacity+1)
            for i in range(first,min(len(rows),first+capacity)):
                y=75+(i-first)*27
                if i==self.selected:r.fill(7,y-4,w-14,25,p.SELECT);r.rect(7,y-4,w-14,25,p.ACCENT)
                r.text(14,y,rows[i][:max(1,(w-28)//8)],p.TEXT,1)
            if not rows:r.text(10,78,'No saved documents yet',p.MUTED,0)
    def draw(self):
        r,p,w,h=self.chrome()
        if self.page in ('edit','equation'):self.draw_document(r,p,w,h)
        else:self.draw_menu(r,p,w,h)
        self.draw_footer(r,p,w,h);self.vm.draw.swap()
