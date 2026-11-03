"""PicoReader: SD library, paginated EPUB/TXT text, positions and bookmarks."""
from picoware.system import buttons as k
from picoware.system.font import FONT_XTRA_SMALL,FONT_SMALL,FONT_MEDIUM
from engtools.ui import theme
from engtools.calculator.render import Renderer
from .epub import open_book,wrap
from .state import State

DIRECTORY='picoware/documents/picoreader'
FONTS=(FONT_XTRA_SMALL,FONT_SMALL,FONT_MEDIUM)
FONT_NAMES=('XS','S','M')
DEFAULT_FONT=0
SAVE_EVERY=20


class PicoReader:
    def __init__(self):
        self.vm=None;self.book=None;self.files=[];self.selected=0
        self.library=True;self.help=False;self.error='';self.message=''
        self.chapter=0;self.page=0;self.lines=[];self.bookmarks=[];self.bm_list=False;self.bm_selected=0
        self.state=None;self.name='';self.size=0;self.font=DEFAULT_FONT;self.pages=[];self.index_dirty=False
        self.turns=0

    def start(self,vm):
        self.vm=vm;vm.input_manager.reset()
        try:
            if not vm.storage.active:raise OSError('SD card unavailable')
            if not vm.storage.vfs_mounted and not vm.storage.mount_vfs():raise OSError('Cannot mount SD card')
            vm.storage.mkdir('picoware/documents');vm.storage.mkdir(DIRECTORY)
            self.state=State(vm.storage);self.font=min(self.state.font,len(FONTS)-1)
            self.refresh()
        except (OSError,ValueError) as exc:self.error=str(exc)
        self.draw();return True

    def refresh(self):
        self.files=sorted(n for n in self.vm.storage.listdir(DIRECTORY)
                          if n.lower().endswith('.epub') or n.lower().endswith('.txt'))
        self.selected=min(self.selected,max(0,len(self.files)-1))
        # An empty listing may also mean a transient read failure; keep state.
        if self.state and self.files:self.state.prune(self.files)

    def stop(self,vm):
        self.save_position()
        if self.book:self.book.close()
        self.book=None;self.lines=[];self.bookmarks=[];self.state=None;self.vm=None

    def layout(self):
        d=self.vm.draw;font=d.get_font(FONTS[self.font])
        self.width=max(1,(int(d.size.x)-16)//(font.width+font.spacing))
        self.height=font.height+3
        self.rows=max(1,(int(d.size.y)-theme.STRIP-24-20-36)//self.height)

    def kind(self,name):
        return 'Text file' if name.lower().endswith('.txt') else 'EPUB book'

    def saved_detail(self,name):
        record=self.state.books.get(name) if self.state else None
        if record and (record['chapter'] or record['page']):
            detail='Continue ch %d, page %d'%(record['chapter']+1,record['page']+1)
            index=record.get('index')
            pages=index.get('pages') if index else None
            if pages and all(count>0 for count in pages):detail+=' / %d pages'%sum(pages)
            return detail
        return self.kind(name)

    def book_progress(self):
        if not self.pages or any(count<=0 for count in self.pages):return None
        total=sum(self.pages)
        return (sum(self.pages[:self.chapter])+self.page+1,total) if total else None

    def persist(self):
        if not self.state:return False
        if not self.state.save():
            self.message='Could not save reader state';return False
        return True

    def save_position(self):
        if not (self.state and self.book and self.name):return
        self.state.set_position(self.name,self.size,self.chapter,self.page,self.page_word())
        if self.index_dirty:
            self.state.set_index(self.name,self.size,self.pages);self.index_dirty=False
        self.persist()

    def load_chapter(self,index,last=False,target=None):
        # Commit navigation only after a complete section loads successfully.
        lines=wrap(self.book.chapter(index),self.width)
        self.chapter=index;self.lines=lines
        pages=(len(lines)+self.rows-1)//self.rows
        if 0<=index<len(self.pages):
            self.pages[index]=pages;self.index_dirty=True
        if target is None:self.page=pages-1 if last else 0
        else:self.page=max(0,min(target,pages-1))

    def open_selected(self):
        if not self.files:return
        name=self.files[self.selected]
        path=self.vm.storage.vfs_prefix+'/'+DIRECTORY+'/'+name
        candidate=open_book(path)
        try:
            size=self.vm.storage.size(path)
            record=self.state.book(name,size) if self.state else None
            chapter=record['chapter'] if record else 0
            page=record['page'] if record else 0
            if chapter>=len(candidate.chapters):chapter=0;page=0
            self.layout()
            lines=wrap(candidate.chapter(chapter),self.width)
            pages=(len(lines)+self.rows-1)//self.rows
            if record and record.get('word',-1)>=0:page=self.page_for_word(record['word'],lines)
            page=max(0,min(page,pages-1))
        except Exception:
            candidate.close();raise
        self.save_position()
        if self.book:self.book.close()
        self.book=candidate;self.name=name;self.size=size
        self.chapter=chapter;self.page=page;self.lines=lines
        if self.state:
            self.bookmarks=self.state.bookmarks(name,size)
            index=self.state.index(name,size)
            if index and len(index['pages'])==len(candidate.chapters):self.pages=index['pages']
            else:self.pages=[0]*len(candidate.chapters)
            self.pages[chapter]=pages;self.index_dirty=True
        else:
            self.bookmarks=[];self.pages=[0]*len(candidate.chapters)
            self.pages[chapter]=pages;self.index_dirty=True
        self.library=False;self.bm_list=False;self.turns=0;self.message=''

    def turn(self,step):
        pages=(len(self.lines)+self.rows-1)//self.rows
        target=self.page+step;chapter=self.chapter
        if 0<=target<pages:self.page=target
        elif target>=pages and self.chapter+1<len(self.book.chapters):self.load_chapter(self.chapter+1)
        elif target<0 and self.chapter:self.load_chapter(self.chapter-1,True)
        self.turns+=1
        if self.chapter!=chapter or self.turns%SAVE_EVERY==0:self.save_position()

    def page_word(self):
        return sum(len(line.split()) for line in self.lines[:self.page*self.rows])

    def page_range(self):
        start=self.page*self.rows;word=self.page_word()
        return word,word+sum(len(line.split()) for line in self.lines[start:start+self.rows])

    def page_for_word(self,anchor,lines=None):
        lines=self.lines if lines is None else lines
        count=0
        for i,line in enumerate(lines):
            if count>=anchor:return i//self.rows
            count+=len(line.split())
        return max(0,(len(lines)-1)//self.rows)

    def cycle_font(self):
        if not self.state:return
        anchor=self.page_word() if self.book else 0
        self.font=(self.font+1)%len(FONTS);self.state.set_font(self.font)
        if self.book:
            self.layout()
            self.pages=[0]*len(self.book.chapters);self.index_dirty=True
            self.load_chapter(self.chapter)
            self.page=self.page_for_word(anchor)
        self.message='Font: '+FONT_NAMES[self.font]
        if self.book:self.save_position()
        else:self.persist()

    def bookmark_word(self,mark):
        return mark[3] if len(mark)>3 and mark[3]>=0 else None

    def bookmark_here(self):
        low,high=self.page_range()
        for mark in self.bookmarks:
            if mark[0]!=self.chapter:continue
            saved=self.bookmark_word(mark)
            if saved is None:
                if mark[1]==self.page:return True
            elif low<=saved<high:return True
        return False

    def bookmark_label(self):
        start=self.page*self.rows
        for line in self.lines[start:start+self.rows]:
            if line.strip():return line.strip()[:40]
        return 'Page %d'%(self.page+1)

    def toggle_bookmark(self):
        if not (self.state and self.book):return
        word=self.page_word();low,high=self.page_range()
        for index,mark in enumerate(self.bookmarks):
            if mark[0]!=self.chapter:continue
            saved=self.bookmark_word(mark)
            if (saved is None and mark[1]==self.page) or (saved is not None and low<=saved<high):
                self.bookmarks=self.state.remove_bookmark(self.name,self.size,index)
                self.message='Bookmark removed';self.persist();return
        if len(self.bookmarks)>=24:self.message='Bookmark limit reached';return
        self.bookmarks=self.state.add_bookmark(self.name,self.size,self.chapter,self.page,self.bookmark_label(),word)
        self.message='Bookmark added';self.persist()

    def delete_bookmark(self):
        if not (self.state and self.bookmarks):return
        self.bookmarks=self.state.remove_bookmark(self.name,self.size,self.bm_selected)
        self.bm_selected=min(self.bm_selected,max(0,len(self.bookmarks)-1))
        self.message='Bookmark removed';self.persist()

    def open_bookmark(self):
        if not self.bookmarks:return
        mark=self.bookmarks[self.bm_selected]
        if mark[0]>=len(self.book.chapters):self.message='Bookmark is outside this book';return
        self.load_chapter(mark[0])
        saved=self.bookmark_word(mark)
        if saved is not None:self.page=self.page_for_word(saved)
        else:self.page=max(0,min(mark[1],(len(self.lines)+self.rows-1)//self.rows-1))
        self.bm_list=False;self.message='Bookmark opened';self.save_position()

    def run(self,vm):
        button=vm.button
        if button==k.BUTTON_NONE:return
        self.error=''
        try:
            if button==vm.input_manager._key_esc:
                if self.help:self.help=False
                elif self.bm_list:self.bm_list=False
                elif not self.library:
                    self.save_position();self.library=True;self.bm_list=False;self.message=''
                else:vm.back();return
            elif button==k.BUTTON_F9:self.help=not self.help
            elif self.help:return
            elif self.bm_list:
                if button==k.BUTTON_UP:self.bm_selected=max(0,self.bm_selected-1)
                elif button==k.BUTTON_DOWN:self.bm_selected=min(max(0,len(self.bookmarks)-1),self.bm_selected+1)
                elif button==k.BUTTON_CENTER:self.open_bookmark()
                elif button==k.BUTTON_F2:self.delete_bookmark()
            elif self.library:
                if button in (k.BUTTON_UP,k.BUTTON_DOWN):self.selected=(self.selected+(-1 if button==k.BUTTON_UP else 1))%max(1,len(self.files))
                elif button==k.BUTTON_CENTER:self.open_selected()
                elif button==k.BUTTON_F5:
                    self.message='Open a book to use bookmarks'
                elif button==k.BUTTON_F6:self.cycle_font()
            else:
                if button in (k.BUTTON_RIGHT,k.BUTTON_DOWN,k.BUTTON_CENTER):self.turn(1)
                elif button in (k.BUTTON_LEFT,k.BUTTON_UP):self.turn(-1)
                elif button==k.BUTTON_F1:self.toggle_bookmark()
                elif button==k.BUTTON_F2:
                    self.save_position();self.library=True;self.bm_list=False;self.message='';self.refresh()
                elif button==k.BUTTON_F3 and self.chapter:
                    self.load_chapter(self.chapter-1);self.save_position()
                elif button==k.BUTTON_F4 and self.chapter+1<len(self.book.chapters):
                    self.load_chapter(self.chapter+1);self.save_position()
                elif button==k.BUTTON_F5:self.bm_list=True;self.bm_selected=0;self.message=''
                elif button==k.BUTTON_F6:self.cycle_font()
        except (OSError,ValueError,MemoryError,UnicodeError) as exc:self.error=str(exc) or 'Not enough memory'
        self.draw()

    def draw(self):
        self.layout();vm=self.vm;d=vm.draw;p=theme.system_palette(vm)
        if self.library and not self.help and not self.bm_list:
            rows=[(name,self.saved_detail(name)) for name in self.files] or [('No books','Copy EPUB or TXT to documents/picoreader')]
            theme.menu(d,rows,self.selected,'PicoReader','PicoDESK',self.message or self.error,palette=p,error=bool(self.error),vm=vm)
            return
        if self.bm_list and not self.help:
            rows=[(mark[2] or 'Page %d'%(mark[1]+1),'Chapter %d, page %d'%(mark[0]+1,mark[1]+1)) for mark in self.bookmarks]
            rows=rows or [('No bookmarks','F1 marks the current page')]
            theme.menu(d,rows,self.bm_selected,'Bookmarks','PicoDESK',self.message or self.error,palette=p,error=bool(self.error),vm=vm)
            return
        d.fill_screen(p.BG);theme.status(vm,p)
        theme.header(d,'PicoReader','PicoDESK',p,height=18,top=theme.STRIP)
        top=theme.STRIP+24;w,h=int(d.size.x),int(d.size.y)
        r=Renderer(d,(0,top,w,h-12),vm.selected_color)
        if self.help:
            lines=('PicoReader','UP/DOWN or ENTER: open / next page','LEFT/UP: previous page',
                   'F3 / F4: previous / next chapter','F1: add or remove bookmark',
                   'F5: bookmarks (ENTER opens, F2 removes)','F6: reading font: XS, S, M',
                   'F2: library / refresh','ESC: close list / library / exit','F9: help',
                   'Books: picoware/documents/','picoreader/*.epub, *.txt','Position, bookmarks and font are saved.')
            for i,line in enumerate(lines):r.text(8,top+i*17,line,p.TEXT,0)
        elif self.book:
            r.text(8,top,self.book.title[:self.width],p.ACCENT,self.font)
            start=self.page*self.rows
            for i,line in enumerate(self.lines[start:start+self.rows]):r.text(8,top+20+i*self.height,line,p.TEXT,self.font)
            marked=' *' if self.bookmark_here() else ''
            status='Ch %d/%d  Pg %d/%d  %s%s'%(self.chapter+1,len(self.book.chapters),self.page+1,(len(self.lines)+self.rows-1)//self.rows,FONT_NAMES[self.font],marked)
            progress=self.book_progress()
            if progress:status+='  %d%%'%(100*progress[0]//progress[1])
            r.text(8,h-27,status,p.MUTED,0)
        theme.footer(d,self.message or self.error,error=bool(self.error),palette=p);d.swap()
