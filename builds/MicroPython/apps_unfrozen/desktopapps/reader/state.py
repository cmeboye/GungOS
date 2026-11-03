"""Bounded PicoReader state: font, reading positions, bookmarks and page index."""
from json import loads,dumps

PATH='picoware/settings/picoreader/state.json'
KIND='picoreader-state'
VERSION=1
LIMIT=32*1024
MAX_BOOKS=48
MAX_BOOKMARKS=24
MAX_CHAPTERS=4096


def _number(value,low,high,default):
    try:value=int(value)
    except (TypeError,ValueError):return default
    return value if low<=value<=high else default


def _text(value,limit):
    if not isinstance(value,str):return ''
    return ' '.join(value.split())[:limit]


class State:
    """One small verified JSON file shared by every book in the library."""

    def __init__(self,storage):
        self.storage=storage;self.font=0;self.books={}
        self.load()

    def load(self):
        # A failed replacement can leave the verified .bak as the only copy.
        for path in (PATH,PATH+'.bak'):
            self.font=0;self.books={}
            if self._load(path):return

    def _load(self,path):
        try:
            if not self.storage.exists(path):return False
            if self.storage.size(path)>LIMIT:return False
            raw=self.storage.read(path)
            if not raw or len(raw)>LIMIT:return False
            data=loads(raw)
            if not isinstance(data,dict) or data.get('kind')!=KIND or data.get('version')!=VERSION:return False
            font=_number(data.get('font'),0,2,0)
            books=data.get('books')
            if not isinstance(books,dict):return False
            self.font=font
            for name,record in books.items():
                clean=self._record(name,record)
                if clean is not None and len(self.books)<MAX_BOOKS:
                    self.books[name]=clean
            return True
        except (OSError,ValueError,TypeError,KeyError,AttributeError):
            return False

    def _record(self,name,record):
        if not isinstance(name,str) or not name or not isinstance(record,dict):return None
        out={'size':_number(record.get('size'),0,0x7fffffff,0),
             'chapter':_number(record.get('chapter'),0,MAX_CHAPTERS-1,0),
             'page':_number(record.get('page'),0,1000000,0),
             'word':_number(record.get('word'),-1,0x7fffffff,-1),
             'offset':_number(record.get('offset'),-1,0x7fffffff,-1),
             'bookmarks':[],'index':None}
        marks=record.get('bookmarks')
        if isinstance(marks,list):
            for mark in marks[:MAX_BOOKMARKS]:
                if not isinstance(mark,(list,tuple)) or len(mark)<2:continue
                out['bookmarks'].append([_number(mark[0],0,MAX_CHAPTERS-1,0),
                                         _number(mark[1],0,1000000,0),
                                         _text(mark[2] if len(mark)>2 else '',40),
                                         _number(mark[3] if len(mark)>3 else -1,-1,0x7fffffff,-1),
                                         _number(mark[4] if len(mark)>4 else -1,-1,0x7fffffff,-1)])
        index=record.get('index')
        if isinstance(index,dict) and index.get('layout')==3 and _number(index.get('font'),0,2,0)==self.font:
            pages=index.get('pages')
            if isinstance(pages,list) and 0<len(pages)<=MAX_CHAPTERS:
                out['index']={'layout':3,'font':self.font,'pages':[_number(n,0,1000000,0) for n in pages]}
        return out

    def book(self,name,size):
        record=self.books.get(name)
        if record is None:
            record={'size':size,'chapter':0,'page':0,'word':-1,'offset':-1,'bookmarks':[],'index':None}
            if len(self.books)>=MAX_BOOKS:
                self.books.pop(next(iter(self.books)))
            self.books[name]=record
        elif size and record.get('size')!=size:
            # The file changed: keep bookmarks, but restart pagination.
            record['size']=size;record['chapter']=0;record['page']=0;record['word']=-1;record['offset']=-1;record['index']=None
        return record

    def prune(self,names):
        keep=set(names)
        for name in list(self.books):
            if name not in keep:self.books.pop(name)

    def set_font(self,font):
        if font==self.font:return
        self.font=font
        # Page counts depend on the font width; rebuild them lazily.
        for record in self.books.values():record['index']=None

    def set_position(self,name,size,chapter,page,word=-1,offset=-1):
        record=self.book(name,size)
        record['chapter']=chapter;record['page']=page;record['word']=word;record['offset']=offset

    def set_index(self,name,size,pages):
        record=self.book(name,size)
        record['index']={'layout':3,'font':self.font,'pages':list(pages)}

    def add_bookmark(self,name,size,chapter,page,label,word=-1,offset=-1):
        record=self.book(name,size);marks=record['bookmarks']
        marks.append([chapter,page,_text(label,40),_number(word,-1,0x7fffffff,-1),_number(offset,-1,0x7fffffff,-1)])
        if len(marks)>MAX_BOOKMARKS:marks.pop(0)
        return marks

    def remove_bookmark(self,name,size,index):
        record=self.book(name,size);marks=record['bookmarks']
        if not 0<=index<len(marks):return marks
        marks.pop(index)
        return marks

    def bookmarks(self,name,size):
        return self.book(name,size)['bookmarks']

    def index(self,name,size):
        record=self.book(name,size)
        return record.get('index')

    def save(self):
        if not self.storage.active:return False
        try:
            data={'kind':KIND,'version':VERSION,'font':self.font,'books':self.books}
            text=dumps(data)
            if len(text)>LIMIT:
                self._trim(data)
                text=dumps(data)
                if len(text)>LIMIT:return False
            self.storage.mkdir('picoware/settings')
            self.storage.mkdir('picoware/settings/picoreader')
            temporary,backup=PATH+'.tmp',PATH+'.bak'
            if not self.storage.write(temporary,text):return False
            if self.storage.read(temporary)!=text:return False
            existed=self.storage.exists(PATH)
            if existed:
                if self.storage.exists(backup) and not self.storage.remove(backup):return False
                if not self.storage.rename(PATH,backup):return False
            if not self.storage.rename(temporary,PATH):
                if existed:self.storage.rename(backup,PATH)
                return False
            if existed or self.storage.exists(backup):self.storage.remove(backup)
            return True
        except (OSError,ValueError,TypeError,MemoryError):
            return False

    def _trim(self,data):
        # Page counts are a cache; positions and bookmarks are the valuable part.
        for record in data['books'].values():record['index']=None
        while len(dumps(data))>LIMIT and data['books']:
            data['books'].pop(next(iter(data['books'])))
