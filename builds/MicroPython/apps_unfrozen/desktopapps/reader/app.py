"""PicoReader: SD library, paginated EPUB/TXT text, positions and bookmarks."""
from picoware.system import buttons as k
from picoware.system.font import FONT_XTRA_SMALL,FONT_SMALL,FONT_MEDIUM
from engtools.ui import theme
from engtools.calculator.render import Renderer
from .epub import open_book
from .pager import Session
from .state import State
from gc import collect

DIRECTORY='picoware/documents/picoreader'
FONTS=(FONT_XTRA_SMALL,FONT_SMALL,FONT_MEDIUM)
FONT_NAMES=('XS','S','M')
DEFAULT_FONT=0
SAVE_EVERY=20


class PicoReader:
    def __init__(self):
        self.vm=None;self.book=None;self.files=[];self.selected=0;self.equations=None;self.navigation=None;self.jump_target=None
        self.library=True;self.help=False;self.error='';self.message=''
        self.chapter=0;self.page=0;self.lines=[];self.bookmarks=[];self.bm_list=False;self.bm_selected=0
        self.state=None;self.name='';self.size=0;self.font=DEFAULT_FONT;self.pages=[];self.index_dirty=False
        self.shown_page=None;self.session=None;self.reflow=None;self.cache_number=0;self.previous_mode=None
        self.blocks=[];self.math_selected=0
        self.turns=0;self.images=[];self.image_list=False;self.image_selected=0;self.viewer=None;self.image_anchor=None

    def start(self,vm):
        self.vm=vm;vm.input_manager.reset()
        try:
            if not vm.storage.active:raise OSError('SD card unavailable')
            if not vm.storage.vfs_mounted and not vm.storage.mount_vfs():raise OSError('Cannot mount SD card')
            vm.storage.mkdir('picoware/documents');vm.storage.mkdir(DIRECTORY)
            self.state=State(vm.storage);self.font=min(self.state.font,len(FONTS)-1)
            self.refresh()
        except (OSError,ValueError,MemoryError) as exc:self.error=str(exc) or 'Not enough memory to open reader'
        self.draw();return True

    def refresh(self):
        self.files=sorted(n for n in self.vm.storage.listdir(DIRECTORY)
                          if n.lower().endswith('.epub') or n.lower().endswith('.txt'))
        self.selected=min(self.selected,max(0,len(self.files)-1))
        # An empty listing may also mean a transient read failure; keep state.
        if self.state and self.files:self.state.prune(self.files)

    def stop(self,vm):
        try:self.save_position()
        finally:
            self.release_book()
            self.state=None;self.vm=None

    def release_book(self):
        """The library must not retain the previous chapter and ZIP index."""
        if self.navigation:self.navigation.close();self.navigation=None
        self.jump_target=None
        if self.equations:self.equations.close();self.equations=None
        if self.viewer:self.viewer.close();self.viewer=None
        self.images=[];self.image_list=False;self.image_anchor=None
        if self.reflow:self.reflow[1].close();self.reflow=None
        if self.session:self.session.close();self.session=None
        if self.book:self.book.close()
        if self.previous_mode is not None:
            self.vm.draw.set_mode(self.previous_mode);self.previous_mode=None
        self.book=None;self.shown_page=None;self.lines=[];self.bookmarks=[];self.pages=[]
        self.name='';self.size=0;self.index_dirty=False;self.blocks=[];self.math_selected=0
        collect()

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
        if not self.session or not self.session.current:return
        self.state.set_position(self.name,self.size,self.chapter,self.page,self.page_word(),self.page_offset())
        if self.index_dirty:
            self.state.set_index(self.name,self.size,self.pages);self.index_dirty=False
        self.persist()

    def cache_path(self):
        self.vm.storage.mkdir('picoware/cache');self.vm.storage.mkdir('picoware/cache/picoreader')
        self.cache_number=1-self.cache_number
        return self.vm.storage.vfs_prefix+'/picoware/cache/picoreader/pages%d.bin'%self.cache_number

    def load_chapter(self,index,last=False,target=None):
        self.session.seek(index,-1 if last else (target or 0))
        self.sync_page()

    def make_session(self,book,counts=None,font=None):
        path=self.cache_path();rich=None
        if hasattr(book,'archive'):
            from .rich import RichPages
            rich=RichPages(self.vm.draw,FONTS[self.font if font is None else font],self.height,path)
        try:
            if rich:
                from .rich import RichSession
                return RichSession(book,self.width,self.rows,path,counts,rich)
            return Session(book,self.width,self.rows,path,counts)
        except Exception:
            if rich:rich.close()
            raise

    def page_lines(self,page):
        if page[6].startswith('\x1e'):
            import json
            self.blocks=json.loads(page[6][1:]);self.math_selected=0
            return [b[1] for b in self.blocks if b[0]=='t']
        self.blocks=[];return page[6].split('\n')

    def open_selected(self):
        if not self.files:return
        collect();name=self.files[self.selected]
        path=self.vm.storage.vfs_prefix+'/'+DIRECTORY+'/'+name
        mode=self.vm.draw.mode;self.vm.draw.set_mode(self.vm.draw.MODE_PSRAM)
        candidate=None;session=None
        try:
            candidate=open_book(path);size=self.vm.storage.size(path)
            record=self.state.book(name,size) if self.state else None
            chapter=record['chapter'] if record else 0;page=record['page'] if record else 0
            if chapter>=len(candidate.chapters):chapter=0;page=0;record=None
            self.layout();index=self.state.index(name,size) if self.state else None
            counts=index['pages'] if index and len(index['pages'])==len(candidate.chapters) else None
            session=self.make_session(candidate,counts)
            session.seek(chapter,page,record.get('offset',-1) if record else -1,record.get('word',-1) if record else -1)
        except Exception:
            if session:session.close()
            if candidate:candidate.close()
            self.vm.draw.set_mode(mode);raise
        self.save_position();self.release_book()
        self.previous_mode=mode;self.vm.draw.set_mode(self.vm.draw.MODE_PSRAM)
        self.book=candidate;self.session=session;self.name=name;self.size=size
        self.chapter=chapter;self.page=0;self.lines=[];self.pages=session.counts
        self.bookmarks=self.state.bookmarks(name,size) if self.state else []
        self.library=False;self.bm_list=False;self.turns=0;self.message=''

    def sync_page(self):
        if not self.session or not self.session.current:return
        page=self.session.current
        if page is self.shown_page:return
        lines=self.page_lines(page)
        self.shown_page=page
        self.chapter=page[0];self.page=page[1];self.lines=lines;self.pages=self.session.counts
        self.index_dirty=True

    def background(self):
        try:return self._background()
        except (OSError,ValueError,MemoryError,UnicodeError) as exc:
            self.error=str(exc) or 'Not enough memory'
            if self.reflow:self.reflow[1].close();self.reflow=None
            if self.session:
                self.session.stop_source();self.session.pending=None;self.session.queue=0;self.session.failed=True
                self.session.current=self.shown_page
            collect();return True

    def _background(self):
        if self.library or self.help or self.bm_list or self.image_list or self.viewer:return False
        if self.reflow:
            font,session=self.reflow;session.step()
            if session.error:
                self.error=session.error;session.close();self.reflow=None;return True
            if session.current:
                page=session.current;lines=self.page_lines(page)
                self.session.close();self.session=session;self.reflow=None;self.font=font
                self.layout();self.state.set_font(font)
                self.shown_page=page;self.chapter=page[0];self.page=page[1]
                self.lines=lines;self.pages=session.counts;self.index_dirty=True
                self.message='Font: '+FONT_NAMES[font];self.save_position();return True
            return False
        if not self.session:return False
        changed=self.session.step();self.index_dirty=True
        if self.jump_target:
            chapter,page=self.jump_target
            if self.session.pending and self.session.pending[0]!=chapter:
                count=self.session.counts[chapter]
                self.session.seek(chapter,max(0,count-1));self.sync_page()
                self.message='Chapter has %d pages; showing last'%count;self.jump_target=None
            elif not self.session.pending:
                if not self.session.error and self.session.counts[chapter] and self.session.current and self.session.current[0]==chapter and self.session.current[1]<page:
                    self.message='Chapter has %d pages; showing last'%self.session.counts[chapter]
                self.jump_target=None

        if self.session.error:self.error=self.session.error;self.session.error=''
        if changed:self.sync_page()
        return changed

    def turn(self,step):
        if not self.session or self.reflow:return
        self.jump_target=None
        self.session.turn(step);self.sync_page();self.turns+=1
        if self.turns%SAVE_EVERY==0:self.save_position()

    def page_word(self):
        return self.session.current[2] if self.session and self.session.current else 0

    def page_offset(self):
        return self.session.current[4] if self.session and self.session.current else 0

    def page_range(self):
        page=self.session.current if self.session else None
        return (page[2],page[3]) if page else (0,0)

    def cycle_font(self):
        if not self.state or self.reflow:return
        font=(self.font+1)%len(FONTS)
        if not self.book:
            self.font=font;self.state.set_font(font);self.message='Font: '+FONT_NAMES[font];self.persist();return
        if not self.session.current:return
        previous=self.font;self.font=font;self.layout();self.font=previous
        self.session.stop_source();collect()
        try:
            session=self.make_session(self.book,font=font)
            session.seek(self.chapter,self.page,self.page_offset())
            self.reflow=(font,session)
        finally:self.layout()

    def bookmark_word(self,mark):
        return mark[3] if len(mark)>3 and mark[3]>=0 else None

    def bookmark_here(self):
        low,high=self.page_range()
        for mark in self.bookmarks:
            if mark[0]!=self.chapter:continue
            if len(mark)>4 and mark[4]>=0:
                page=self.session.current
                if page and (page[4]<=mark[4]<page[5] or page[4]==mark[4]):return True
                continue
            saved=self.bookmark_word(mark)
            if saved is None:
                if mark[1]==self.page:return True
            elif low<=saved<high:return True
        return False

    def bookmark_label(self):
        for line in self.lines:
            if line.strip():return line.strip()[:40]
        return 'Page %d'%(self.page+1)

    def toggle_bookmark(self):
        if not (self.state and self.book and self.session.current):return
        word=self.page_word();low,high=self.page_range()
        for index,mark in enumerate(self.bookmarks):
            if mark[0]!=self.chapter:continue
            saved=self.bookmark_word(mark)
            offset=mark[4] if len(mark)>4 else -1
            here=(self.session.current[4]<=offset<self.session.current[5] or self.session.current[4]==offset) if offset>=0 else ((saved is None and mark[1]==self.page) or (saved is not None and low<=saved<high))
            if here:
                self.bookmarks=self.state.remove_bookmark(self.name,self.size,index)
                self.message='Bookmark removed';self.persist();return
        if len(self.bookmarks)>=24:self.message='Bookmark limit reached';return
        self.bookmarks=self.state.add_bookmark(self.name,self.size,self.chapter,self.page,self.bookmark_label(),word,self.page_offset())
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
        self.session.seek(mark[0],mark[1],mark[4] if len(mark)>4 else -1,mark[3] if len(mark)>3 else -1)
        self.sync_page()
        self.bm_list=False;self.message='Bookmark opened';self.save_position()

    def list_images(self):
        if not hasattr(self.book,'image_refs'):
            self.message='Text files have no images';return
        images=self.book.image_refs(self.chapter)
        self.images=images;self.image_selected=0;self.image_list=True;self.message=''

    def open_image(self):
        if not self.images:return
        if self.image_anchor is None:
            self.save_position();self.image_anchor=self.page_word();self.lines=[];self.shown_page=None;collect()
        if self.viewer is None:
            from .images import ImageViewer
            self.viewer=ImageViewer(self.vm)
        path,label=self.images[self.image_selected]
        self.viewer.open(self.book,path,theme.system_palette(self.vm).BG)
        self.image_list=False;self.message=''

    def return_to_text(self):
        # Keep the saved anchor until chapter restoration actually succeeds.
        if self.viewer:self.viewer.close();self.viewer=None
        if self.image_anchor is not None:
            self.sync_page();self.image_anchor=None
        self.image_list=False;self.images=[];self.message=''

    def open_equations(self):
        if not self.book or not hasattr(self.book,'archive'):
            self.message='Equations require an EPUB book';return
        # Keep the cached reading page and anchors, release its inflate window.
        self.session.stop_source();collect()
        from .equationview import EquationView
        self.equations=EquationView(self.vm,self.book,self.chapter)
        on_page=[b for b in self.blocks if b[0]=='m']
        if on_page:
            block=on_page[self.math_selected%len(on_page)]
            try:
                self.equations.node=self.session.rich.read(block[1]);self.equations.ordinal=block[2]
                self.equations.target=block[2]+1;self.equations.loading=False
                self.equations.restart(block[2]);self.equations.loading=False
                if block[4]:self.equations.error=block[4]
                else:self.equations.layout()
            except (OSError,ValueError,MemoryError) as exc:
                self.equations.error=str(exc) or 'Not enough memory';self.equations.loading=False


    def open_navigation(self):
        if not self.book or self.reflow:return
        self.session.stop_source();collect()
        from .navigation import Navigation
        self.navigation=Navigation(self.vm,self.book,self.chapter,self.page,self.pages)

    def navigation_key(self,button):
        nav=self.navigation
        if button==self.vm.input_manager._key_esc:
            if nav.help:nav.help=False
            elif nav.mode!='list':nav.mode='list';nav.error=''
            else:nav.close();self.navigation=None
        elif button==k.BUTTON_NONE:
            if nav.step():self.draw()
            return
        else:
            nav.key(button)
            if nav.target:
                target=nav.target;nav.close();self.navigation=None
                self.save_position();self.jump_target=target
                self.session.seek(*target);self.sync_page()
        self.draw()

    def run(self,vm):
        button=vm.button
        if self.navigation:
            try:self.navigation_key(button)
            except (OSError,ValueError,MemoryError,UnicodeError) as exc:
                self.error=str(exc) or 'Navigation failed';self.navigation.close();self.navigation=None;self.draw()
            return
        if self.equations:
            if button==vm.input_manager._key_esc:
                self.equations.close();self.equations=None;self.draw()
            elif button==k.BUTTON_NONE:
                if self.equations.step():self.draw()
            else:self.equations.key(button);self.draw()
            return
        if button==k.BUTTON_NONE:
            if self.background():self.draw()
            return
        self.error=''
        try:
            if button==vm.input_manager._key_esc:
                if self.reflow:self.reflow[1].close();self.reflow=None
                elif self.help:self.help=False
                elif self.viewer and not self.image_list:self.image_list=True
                elif self.image_list:self.return_to_text()
                elif self.bm_list:self.bm_list=False
                elif not self.library:
                    self.save_position();self.release_book();self.library=True;self.bm_list=False;self.message=''
                else:vm.back();return
            elif button==k.BUTTON_F9:self.help=not self.help
            elif self.help:return
            elif self.reflow:pass
            elif self.image_list:
                if button==k.BUTTON_UP:self.image_selected=max(0,self.image_selected-1)
                elif button==k.BUTTON_DOWN:self.image_selected=min(max(0,len(self.images)-1),self.image_selected+1)
                elif button==k.BUTTON_CENTER:self.open_image()
            elif self.viewer:
                if button in (k.BUTTON_LEFT,k.BUTTON_RIGHT):
                    step=-1 if button==k.BUTTON_LEFT else 1
                    target=self.image_selected+step
                    if 0<=target<len(self.images):
                        self.image_selected=target;self.open_image()
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
                if button in (k.BUTTON_RIGHT,k.BUTTON_DOWN,k.BUTTON_CENTER,k.BUTTON_RIGHT_BRACKET):self.turn(1)
                elif button in (k.BUTTON_LEFT,k.BUTTON_UP,k.BUTTON_LEFT_BRACKET):self.turn(-1)
                elif button==k.BUTTON_F1:self.toggle_bookmark()
                elif button==k.BUTTON_F2:
                    self.save_position();self.release_book();self.library=True;self.bm_list=False;self.message='';self.refresh()
                elif button==k.BUTTON_F3 and self.chapter:
                    self.load_chapter(self.chapter-1);self.save_position()
                elif button==k.BUTTON_F4 and self.chapter+1<len(self.book.chapters):
                    self.load_chapter(self.chapter+1);self.save_position()
                elif button==k.BUTTON_F5:self.bm_list=True;self.bm_selected=0;self.message=''
                elif button==k.BUTTON_F6:self.cycle_font()
                elif button==k.BUTTON_F7:self.list_images()
                elif button==k.BUTTON_F8:self.open_equations()
                elif button==k.BUTTON_F10:self.open_navigation()
                elif button==k.BUTTON_TAB:
                    self.math_selected+=1
        except (OSError,ValueError,MemoryError,UnicodeError) as exc:
            self.error=str(exc) or 'Not enough memory'
            if self.image_anchor is not None:self.image_list=True
        self.draw()

    def draw(self):
        if self.navigation:self.navigation.draw();return
        if self.equations:self.equations.draw();return
        self.layout();vm=self.vm;d=vm.draw;p=theme.system_palette(vm)
        if self.image_list and not self.help:
            rows=[(label,path.rsplit('/',1)[-1]) for path,label in self.images]
            theme.menu(d,rows or [('No images in this chapter','ESC returns to reading')],self.image_selected,
                       'Chapter images','PicoReader',self.error or 'ENTER opens / ESC returns',palette=p,error=bool(self.error),vm=vm)
            return
        if self.viewer and not self.help:
            d.fill_screen(p.BG);self.viewer.draw()
            r=Renderer(d,(0,280,320,320),vm.selected_color)
            r.text(8,284,self.images[self.image_selected][1][:48],p.TEXT,0)
            r.text(8,302,self.error or '%d/%d  LEFT/RIGHT images  ESC list'%(self.image_selected+1,len(self.images)),p.MUTED,0)
            d.swap();return
        if self.library and not self.help and not self.bm_list:
            rows=[(name,self.saved_detail(name)) for name in self.files] or [('No books','Copy EPUB or TXT to documents/picoreader')]
            theme.menu(d,rows,self.selected,'PicoReader','PicoDESK',self.error or self.message,palette=p,error=bool(self.error),vm=vm)
            return
        if self.bm_list and not self.help:
            rows=[(mark[2] or 'Page %d'%(mark[1]+1),'Chapter %d, page %d'%(mark[0]+1,mark[1]+1)) for mark in self.bookmarks]
            rows=rows or [('No bookmarks','F1 marks the current page')]
            theme.menu(d,rows,self.bm_selected,'Bookmarks','PicoDESK',self.error or self.message,palette=p,error=bool(self.error),vm=vm)
            return
        d.fill_screen(p.BG);theme.status(vm,p)
        theme.header(d,'PicoReader','PicoDESK',p,height=18,top=theme.STRIP)
        top=theme.STRIP+24;w,h=int(d.size.x),int(d.size.y)
        r=Renderer(d,(0,top,w,h-12),vm.selected_color)
        if self.help:
            lines=('PicoReader','UP/DOWN or ENTER: open / next page','LEFT/UP: previous page',
                   'F3 / F4: previous / next chapter','F1: add or remove bookmark',
                   'F5: bookmarks (ENTER opens, F2 removes)','F6: reading font: XS, S, M','F7: images in this chapter',
                   'F8: page equation / TAB selects','F10: chapters / Go to chapter or page','[ / ]: previous / next reading page','F2: library / refresh','ESC: close list / library / exit','F9: help',
                   'Books: documents/picoreader/*.epub, *.txt','Position, bookmarks and font are saved.')
            for i,line in enumerate(lines):r.text(8,top+i*14,line,p.TEXT,0)
        elif self.book:
            r.text(8,top,self.book.title[:self.width],p.ACCENT,self.font)
            if self.blocks:
                y=top+20;ordinal=0
                from .mathlayout import MathRenderer
                math= MathRenderer(d,(8,y,w-8,h-40),vm.selected_color,p)
                for block in self.blocks:
                    if block[0]=='t':r.text(8,y,block[1],p.TEXT,self.font);y+=self.height;continue
                    selected=ordinal==self.math_selected%max(1,sum(b[0]=='m' for b in self.blocks));ordinal+=1
                    if block[4]:
                        r.text(8,y,'Equation %d unsupported - F8'%(block[2]+1),p.MUTED,0)
                    elif block[5]:
                        r.text(8,y,'Equation %d - F8 to pan'%(block[2]+1),p.ACCENT,0)
                    else:
                        try:
                            node=self.session.rich.read(block[1]);box=math.layout_math(node,FONTS[self.font])
                            math.paint(box,8+max(0,(304-box.w)//2),y+2)
                            node=None;box=None
                        except (OSError,ValueError,MemoryError) as exc:
                            r.text(8,y,'Equation unavailable - F8',p.MUTED,0)
                    if selected:math.line(8,y,10,y,p.ACCENT)
                    y+=block[3]
            else:
                for i,line in enumerate(self.lines):r.text(8,top+20+i*self.height,line,p.TEXT,self.font)
            marked=' *' if self.bookmark_here() else ''
            count=self.pages[self.chapter] if self.pages else 0
            status='Ch %d/%d  Pg %d/%s  %s%s'%(self.chapter+1,len(self.book.chapters),self.page+1,str(count) if count else '?',FONT_NAMES[self.font],marked)
            progress=self.book_progress()
            if progress:status+='  %d%%'%(100*progress[0]//progress[1])
            r.text(8,h-27,status,p.MUTED,0)
        loading='Preparing font...' if self.reflow else ('Loading page...' if self.session and self.session.pending else '')
        theme.footer(d,self.error or loading or self.message or ('TAB selects equation  F8 opens' if any(b[0]=='m' for b in self.blocks) else 'F10 Chapters / Go to' if self.book else ''),error=bool(self.error),palette=p);d.swap()
