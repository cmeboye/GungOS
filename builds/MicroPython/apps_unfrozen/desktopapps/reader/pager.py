"""Cooperative chapter pagination with fixed RAM and SD page caches."""
import os
import struct
from .epub import stream_tokens,utf8_chunks,TxtBook

PAGE_BYTES=4096
RAM_BYTES=16*1024
RAM_PAGES=7
DISK_PAGES=64
HEADER=28
STRIDE=HEADER+PAGE_BYTES
PREFETCH=3
# page: chapter, number, first word, word end, first character, character end, text


def words(book,chapter):
    stream=book.stream(chapter)
    source=utf8_chunks(stream) if isinstance(book,TxtBook) else stream_tokens(stream)
    hidden=[];word='';number=0;offset=0;start=0;continued=False;had_word=False;paragraph=False
    try:
        for token in source:
            if token is None:yield None;continue
            if not isinstance(token,str):
                name,attrs,closing=token
                if name in ('head','script','style'):
                    if closing:
                        if hidden and hidden[-1]==name:hidden.pop()
                    elif len(hidden)<16:hidden.append(name)
                    else:raise ValueError('EPUB nesting too deep')
                if hidden or name not in ('p','div','br','hr','li','h1','h2','h3','h4','h5','h6','section','blockquote','tr'):continue
                token='\n'
            if hidden:continue
            for char in token:
                if char.isspace():
                    if word:
                        yield (number,start,word,continued);word='';continued=False;number+=1
                    elif continued:continued=False;number+=1
                    if char in '\n\r' and paragraph:
                        yield (number,offset,None,False);paragraph=False
                else:
                    if not word and not continued:
                        if had_word:offset+=1
                        start=offset;had_word=True
                    if not word:start=offset
                    word+=char;offset+=1;paragraph=True
                    if len(word)==128:
                        yield (number,start,word,continued);word='';continued=True
            # TXT chunks also give the scheduler a chance to service keys.
            if isinstance(book,TxtBook):yield None
        if word:yield (number,start,word,continued);number+=1
        elif continued:number+=1
        if paragraph:yield (number,offset,None,False)
    finally:
        source.close();stream.close()


def lines(book,chapter,width):
    source=words(book,chapter);line='';first=0;begin=0;last=0;end=0
    try:
        for event in source:
            if event is None:yield None;continue
            number,offset,text,continued=event
            if text is None:
                if line:yield (first,last,begin,end,line);line=''
                yield (number,number,offset,offset,'');continue
            if not continued and line and len(line)+1+len(text)>width:
                yield (first,last,begin,end,line);line=''
            pos=0
            while pos<len(text):
                if not line:first=number;begin=offset+pos
                elif not continued and pos==0:line+=' '
                take=min(width-len(line),len(text)-pos)
                line+=text[pos:pos+take];pos+=take;last=number+1;end=offset+pos
                if len(line)==width:
                    yield (first,last,begin,end,line);line=''
        if line:yield (first,last,begin,end,line)
    finally:source.close()


def paginate(book,chapter,width,rows):
    if hasattr(book,'prepare'):
        for _ in book.prepare(chapter):yield None
    source=lines(book,chapter,width);page=0;batch=[]
    try:
        for line in source:
            if line is None:yield None;continue
            batch.append(line)
            if len(batch)==rows:
                text='\n'.join(row[4] for row in batch)
                yield (chapter,page,batch[0][0],batch[-1][1],batch[0][2],batch[-1][3],text)
                batch=[];page+=1
        if batch or not page:
            text='\n'.join(row[4] for row in batch) if batch else '(No readable text in this chapter)'
            yield (chapter,page,batch[0][0] if batch else 0,batch[-1][1] if batch else 0,
                   batch[0][2] if batch else 0,batch[-1][3] if batch else 0,text)
    finally:source.close()


class PageCache:
    """At most 16 KiB of UTF-8 payload in RAM and 64 page slots on SD."""
    def __init__(self,path):
        self.path=path;self.file=None;self.ram=[];self.bytes=0;self.slots=[];self.next=0
        try:self.file=open(path,'w+b')
        except OSError:pass  # Reading can continue with the bounded RAM cache.

    def put(self,page):
        data=page[6].encode('utf-8')
        if len(data)>PAGE_BYTES:raise ValueError('Reader page exceeds cache slot')
        self.remember(page,len(data))
        if self.file:
            key=page[:2]
            slot=self.slots.index(key) if key in self.slots else self.next
            header=struct.pack('<6IH',*(page[:6]+(len(data),)))+b'\0\0'
            try:
                self.file.seek(slot*STRIDE)
                if self.file.write(header)!=HEADER or self.file.write(data)!=len(data):raise OSError('Page cache write failed')
                if slot==len(self.slots):self.slots.append(key)
                else:self.slots[slot]=key
                if slot==self.next:self.next=(self.next+1)%DISK_PAGES
            except OSError:self.disable_disk()

    def remember(self,page,size=None):
        size=len(page[6].encode('utf-8')) if size is None else size
        for old,n in self.ram:
            if old[:2]==page[:2]:self.ram.remove((old,n));self.bytes-=n;break
        while self.ram and (len(self.ram)>=RAM_PAGES or self.bytes+size>RAM_BYTES):
            old,n=self.ram.pop(0);self.bytes-=n
        self.ram.append((page,size));self.bytes+=size

    def get(self,chapter,page):
        key=(chapter,page)
        for value,n in self.ram:
            if value[:2]==key:return value
        if not self.file or key not in self.slots:return None
        slot=self.slots.index(key);self.file.seek(slot*STRIDE)
        header=self.file.read(HEADER)
        if len(header)!=HEADER:return None
        fields=struct.unpack('<6IH',header[:26]);n=fields[-1]
        if fields[:2]!=key or n>PAGE_BYTES:return None
        text=self.file.read(n)
        if len(text)!=n:return None
        value=fields[:6]+(text.decode('utf-8'),);self.remember(value,n);return value

    def disable_disk(self):
        if self.file:
            try:self.file.close()
            except OSError:pass
            self.file=None
        self.slots=[]

    def close(self):
        self.disable_disk();self.ram=[];self.bytes=0
        try:os.remove(self.path)
        except OSError:pass


class Session:
    def __init__(self,book,width,rows,path,counts=None):
        self.book=book;self.width=width;self.rows=rows;self.cache=PageCache(path)
        self.counts=list(counts) if counts else [0]*len(book.chapters)
        self.current=None;self.pending=None;self.source=None;self.source_chapter=-1;self.produced=0
        self.ended=False;self.changed=False;self.error='';self.queue=0;self.failed=False

    def stop_source(self):
        if self.source:self.source.close();self.source=None
        self.source_chapter=-1

    def close(self):self.stop_source();self.cache.close()

    def seek(self,chapter,page=0,offset=-1,word=-1):
        self.pending=(chapter,page,offset,word);self.queue=0;self.error='';self.ended=False;self.failed=False
        if self.current and self.matches(self.current,self.pending):
            self.accept(self.current);return
        found=self.cache.get(chapter,page) if page>=0 else None
        if found and self.matches(found,self.pending):self.accept(found)
        elif offset>=0 or word>=0:self.stop_source()

    def matches(self,page,target):
        chapter,number,offset,word=target
        if page[0]!=chapter:return False
        if offset>=0:return page[4]<=offset<page[5] or offset==page[4]
        if word>=0:return page[2]<=word<page[3] or word==page[2]
        return page[1]==number

    def accept(self,page):
        self.current=page;self.pending=None;self.changed=True

    def turn(self,step):
        if self.pending:self.queue=max(-8,min(8,self.queue+step));return
        if not self.current:return
        chapter,page=self.current[:2];page+=step
        if page<0:
            if chapter==0:return
            chapter-=1;page=self.counts[chapter]-1 if self.counts[chapter] else -1
        elif self.counts[chapter] and page>=self.counts[chapter]:
            if chapter+1==len(self.counts):self.ended=True;return
            chapter+=1;page=0
        self.seek(chapter,page)

    def start_source(self,chapter):
        self.stop_source()
        # A cache miss reopens the inflater's contiguous 32 KiB window. Drop
        # optional RAM pages first; the visible page and SD cache stay intact.
        self.cache.ram=[];self.cache.bytes=0
        self.source=paginate(self.book,chapter,self.width,self.rows)
        self.source_chapter=chapter;self.produced=0

    def step(self):
        """At most one 512-byte source chunk or one completed page per idle tick."""
        self.changed=False
        if self.failed:return False
        try:
            if not self.pending and self.queue:
                step=1 if self.queue>0 else -1;queued=self.queue-step;self.queue=0
                self.turn(step);self.queue+=queued
                if self.changed:return True
            target=self.pending
            if target:
                chapter,number,offset,word=target
                cached=self.cache.get(chapter,number) if number>=0 else None
                if cached and self.matches(cached,target):self.accept(cached);return True
                # Continue a forward scan; replay only when the requested passage is behind it.
                if self.source_chapter!=chapter or not self.source:
                    self.start_source(chapter)
                elif number>=0 and offset<0 and word<0 and number<self.produced:
                    self.start_source(chapter)
            else:
                if not self.current:return False
                chapter,number=self.current[:2];number+=PREFETCH
                while self.counts[chapter] and number>=self.counts[chapter]:
                    number-=self.counts[chapter];chapter+=1
                    if chapter==len(self.counts):return False
                if self.cache.get(chapter,number):return False
                if self.source_chapter!=chapter:self.start_source(chapter)
                elif not self.source:return False
            try:page=next(self.source)
            except StopIteration:
                chapter=self.source_chapter;self.counts[chapter]=self.produced;self.stop_source()
                if self.pending:
                    target=self.pending
                    if target[0]==chapter:
                        if target[1]>=self.produced and target[2]<0 and target[3]<0 and chapter+1<len(self.counts):
                            self.pending=(chapter+1,0,-1,-1)
                        else:
                            last=self.cache.get(chapter,max(0,self.produced-1))
                            if last:self.accept(last)
                return True
            if page is None:return False
            self.produced=page[1]+1
            # During a long seek retain a rolling tail, never every page's metadata.
            self.cache.put(page)
            if self.pending and self.matches(page,self.pending):self.accept(page)
            return self.changed
        except (OSError,ValueError,MemoryError,UnicodeError) as exc:
            self.stop_source();self.pending=None;self.queue=0;self.error=str(exc) or 'Not enough memory';self.failed=True;return True
