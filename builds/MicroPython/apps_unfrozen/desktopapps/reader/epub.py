"""Bounded EPUB text loader and streamed extraction of selected images."""
import struct
import binascii
import io
import os
from gc import collect

LIMIT=192*1024
TEXT_LIMIT=8*1024*1024
TEXT_CHUNK=96*1024
STREAM_LIMIT=64*1024*1024
STREAM_CHUNK=512


def decode_entities(text):
    named={'amp':'&','lt':'<','gt':'>','quot':'"','apos':"'",'nbsp':' '}
    # Most book text has no entities. Never build a pointer list per character.
    if '&' not in text:return text
    result=io.StringIO();pos=0
    while pos<len(text):
        start=text.find('&',pos)
        if start<0:result.write(text[pos:]);break
        result.write(text[pos:start]);end=text.find(';',start+1,start+14)
        value=None
        if end>=0:
            key=text[start+1:end];value=named.get(key)
            if key.startswith('#'):
                try:value=chr(int(key[2:],16) if key.startswith('#x') else int(key[1:]))
                except (ValueError,OverflowError):pass
        if value is None:result.write('&');pos=start+1
        else:result.write(value);pos=end+1
    return result.getvalue()


def tokens(text,paired=False):
    """Yield (local tag name, attributes, closing) or plain text tokens."""
    pos=0
    while pos<len(text):
        start=text.find('<',pos)
        if start<0:yield text[pos:];return
        if start>pos:yield text[pos:start]
        if text.startswith('<!--',start):
            end=text.find('-->',start+4)
            if end<0:raise ValueError('Unclosed XML comment')
            pos=end+3;continue
        end=start+1;quote=''
        while end<len(text):
            c=text[end]
            if quote:
                if c==quote:quote=''
            elif c in ('"',"'"):quote=c
            elif c=='>':break
            end+=1
        if end==len(text):raise ValueError('Unclosed XML tag')
        raw=text[start+1:end].strip();pos=end+1
        if not raw or raw[0] in ('!','?'):continue
        closing=raw.startswith('/');raw=raw.lstrip('/');i=0
        while i<len(raw) and raw[i] not in ' \t\r\n/':i+=1
        name=raw[:i].split(':')[-1].lower();attrs={}
        while i<len(raw):
            while i<len(raw) and raw[i] in ' \t\r\n/':i+=1
            begin=i
            while i<len(raw) and raw[i] not in '= \t\r\n':i+=1
            key=raw[begin:i]
            if not (paired and key.startswith('xmlns:')):key=key.split(':')[-1]
            while i<len(raw) and raw[i].isspace():i+=1
            if i>=len(raw) or raw[i]!='=':break
            i+=1
            while i<len(raw) and raw[i].isspace():i+=1
            if i>=len(raw) or raw[i] not in ('"',"'"):break
            q=raw[i];i+=1;begin=i
            while i<len(raw) and raw[i]!=q:i+=1
            attrs[key]=decode_entities(raw[begin:i]);i+=1
        yield (name,attrs,closing)
        if paired and not closing and raw.endswith('/'):yield (name,{},True)


def resolve(base,href):
    href=href.split('#')[0]
    # EPUB manifest paths are URI references, often with encoded spaces.
    data=bytearray();i=0
    while i<len(href):
        if href[i]=='%' and i+2<len(href):
            try:data.append(int(href[i+1:i+3],16));i+=3;continue
            except ValueError:pass
        data.extend(href[i].encode('utf-8'));i+=1
    href=data.decode('utf-8')
    if ':' in href or href.startswith('/') or '\\' in href:raise ValueError('Unsupported book path')
    parts=base.split('/')[:-1] if base else []
    for part in href.split('/'):
        if part=='..':
            if not parts:raise ValueError('Invalid book path')
            parts.pop()
        elif part not in ('','.'):parts.append(part)
    return '/'.join(parts)


class Archive:
    def __init__(self,path):
        self.path=path;self.file=open(path,'rb');self.entries=None
        try:
            f=self.file;f.seek(0,2);size=f.tell()
            if size>0x7fffffff:raise ValueError('Book exceeds 2 GiB ZIP support')
            # Scan the ZIP footer backwards in small overlapping blocks. A real
            # illustrated book must not allocate a 64 KiB tail just to open it.
            end=size;footer=None
            while end>max(0,size-65557):
                start=max(0,size-65557,end-1024);f.seek(start);tail=f.read(end-start)
                at=tail.rfind(b'PK\x05\x06')
                while at>=0:
                    if len(tail)-at>=22:
                        fields=struct.unpack('<4H2IH',tail[at+4:at+22])
                        if start+at+22+fields[-1]==size:footer=(start+at,fields);break
                    at=tail.rfind(b'PK\x05\x06',0,at)
                if footer or start==max(0,size-65557):break
                end=start+21
            if footer is None:raise ValueError('Invalid EPUB ZIP')
            cd_end,fields=footer
            disk,cd_disk,n_disk,count,cd_size,offset,comment=fields
            if disk or cd_disk or n_disk!=count or count>4096 or count==65535 or offset==0xffffffff or offset+cd_size>cd_end:raise ValueError('Unsupported EPUB ZIP')
            self.data_end=offset
            self.entries=EntryIndex(self,offset,cd_size,count)
            # Validate the directory without retaining one Python object per asset.
            for name,entry in self.entries.scan():pass
        except Exception:
            self.close();raise

    def close(self):
        if self.file:self.file.close();self.file=None

    def read(self,name,limit=LIMIT):
        if name not in self.entries:raise ValueError('Missing EPUB document')
        flags,method,compressed,plain,offset,crc=self.entries[name]
        if flags&1:raise ValueError('Encrypted books are unsupported')
        if method not in (0,8):raise ValueError('Unsupported ZIP compression')
        if plain>limit or compressed>LIMIT:raise ValueError('EPUB section too large')
        f=self.file;f.seek(offset);row=f.read(30)
        if len(row)!=30 or row[:4]!=b'PK\x03\x04':raise ValueError('Invalid EPUB section')
        nl,el=struct.unpack('<HH',row[26:30]);f.seek(nl+el,1);data=f.read(compressed)
        if len(data)!=compressed:raise ValueError('Truncated EPUB section')
        if method==8:
            # Earlier metadata/chapter loads leave large deflate windows for GC.
            # Reclaim them before allocating the next window, not after failure.
            collect()
            try:import deflate
            except ImportError:
                import zlib
                decoder=zlib.decompressobj(-15);data=decoder.decompress(data,plain+1)
                if not decoder.eof:raise ValueError('Invalid or oversized EPUB section')
            else:
                # MicroPython read(n) allocates n bytes up front. LIMIT is a
                # validation ceiling, not the size of this particular section.
                # ZIP entries have no preset dictionary: a backward reference
                # cannot exceed this entry's uncompressed length. Small sample
                # chapters therefore do not require a 32 KiB history window.
                bits=5
                while bits<15 and (1<<bits)<plain:bits+=1
                with deflate.DeflateIO(io.BytesIO(data),deflate.RAW,bits) as stream:data=stream.read(plain+1)
        if len(data)!=plain or len(data)>limit:raise ValueError('Invalid EPUB section size')
        if binascii.crc32(data)&0xffffffff!=crc:raise ValueError('Damaged EPUB section')
        return data.decode('utf-8')


    def stream(self,name,limit=STREAM_LIMIT):
        return EntryStream(self,name,limit)

    def extract(self,name,path,limit=4*1024*1024):
        """Extract only this resource, streaming to our private temporary file."""
        if name not in self.entries:raise ValueError('Missing EPUB image')
        flags,method,compressed,plain,offset,crc=self.entries[name]
        if flags&1 or method not in (0,8):raise ValueError('Unsupported EPUB image compression')
        if plain>limit or compressed>limit:raise ValueError('EPUB image exceeds 4 MiB')
        f=self.file;f.seek(offset);row=f.read(30)
        if len(row)!=30 or row[:4]!=b'PK\x03\x04':raise ValueError('Invalid EPUB image entry')
        nl,el=struct.unpack('<HH',row[26:30]);start=offset+30+nl+el
        if start+compressed>self.data_end:raise ValueError('Truncated EPUB image entry')
        f.seek(start);collect()
        try:
            with open(path,'wb') as out:
                if method==8:
                    try:from pngdec import inflate_zip
                    except ImportError:
                        # Host tooling only. On PicoCalc, use the native bounded
                        # inflater: Python callbacks per compressed byte are slow.
                        import zlib
                        decoder=zlib.decompressobj(-15);left=compressed;total=0;check=0
                        while left:
                            data=f.read(min(left,1024));left-=len(data)
                            if not data:raise ValueError('Truncated EPUB image')
                            pending=data
                            while pending:
                                data=decoder.decompress(pending,1024);pending=decoder.unconsumed_tail
                                total+=len(data)
                                if total>plain:raise ValueError('Invalid EPUB image size')
                                check=binascii.crc32(data,check);out.write(data)
                        if not decoder.eof or decoder.unused_data or total!=plain or check&0xffffffff!=crc:
                            raise ValueError('Damaged EPUB image')
                    else:inflate_zip(f,out,compressed,plain,crc)
                else:
                    if compressed!=plain:raise ValueError('Invalid stored EPUB image')
                    left=plain;check=0
                    while left:
                        data=f.read(min(left,1024))
                        if not data:raise ValueError('Truncated EPUB image')
                        left-=len(data);check=binascii.crc32(data,check)
                        if out.write(data)!=len(data):raise OSError('Cannot write EPUB image')
                    if check&0xffffffff!=crc:raise ValueError('Damaged EPUB image')
        except Exception:
            try:os.remove(path)
            except OSError:pass
            raise
        return plain


def plain_text(html):
    out=[];hidden=[]
    blocks=('p','div','br','hr','li','h1','h2','h3','h4','h5','h6','section','blockquote','tr')
    for token in tokens(html):
        if isinstance(token,str):
            if not hidden:out.append(decode_entities(token))
        else:
            name,attrs,closing=token
            if name in ('head','script','style'):
                if closing:
                    if hidden and hidden[-1]==name:hidden.pop()
                else:hidden.append(name)
            if not hidden and name in blocks:out.append('\n')
    # Collapse HTML whitespace while retaining paragraph breaks.
    return '\n'.join(' '.join(line.split()) for line in ''.join(out).split('\n') if line.strip())


def wrap(text,width):
    lines=[]
    for paragraph in text.split('\n'):
        line=''
        for word in paragraph.split():
            if line and len(line)+1+len(word)>width:lines.append(line);line=''
            while len(word)>width:
                if line:lines.append(line);line=''
                lines.append(word[:width]);word=word[width:]
            if word:line+=((' ' if line else '')+word)
        if line:lines.append(line)
        lines.append('')
    return lines or ['(No readable text in this chapter)']


class ChapterIndex:
    """Keep paths in one string, avoiding scattered long-lived XML strings."""
    def __init__(self,paths):
        self.offsets=[0];self.text=''.join(paths)
        for path in paths:self.offsets.append(self.offsets[-1]+len(path))
    def __len__(self):return len(self.offsets)-1
    def __getitem__(self,index):
        if index<0:index+=len(self)
        if index<0 or index>=len(self):raise IndexError(index)
        return self.text[self.offsets[index]:self.offsets[index+1]]


class Book:
    def __init__(self,path):
        self.archive=Archive(path);self.title=path.rsplit('/',1)[-1];self.chapters=[]
        try:
            if self.archive.read('mimetype',128).strip()!='application/epub+zip':raise ValueError('Not an EPUB book')
            if 'META-INF/encryption.xml' in self.archive.entries:raise ValueError('Encrypted EPUB resources unsupported')
            package=None
            for token in self.metadata('META-INF/container.xml',16384):
                if token is not None and not isinstance(token,str) and token[0]=='rootfile' and package is None:
                    package=resolve('',token[1].get('full-path',''))
            if not package:raise ValueError('Missing EPUB package')
            # Read the spine first. Keep only its IDs, never the entire manifest
            # (illustrated books can list thousands of scripts and images).
            spine=[];needed={};in_title=False;title='';budget=0
            for token in self.metadata(package):
                if token is None:continue
                if isinstance(token,str):
                    if in_title:title=(title+token)[:256]
                    continue
                name,attrs,closing=token
                if name=='title':in_title=not closing
                if not closing and name=='itemref' and attrs.get('linear')!='no':
                    item=attrs.get('idref','')
                    budget+=len(item)
                    if not item:raise ValueError('Missing EPUB spine ID')
                    if len(spine)>=512 or budget>32768:raise ValueError('EPUB reading order exceeds index budget')
                    spine.append(item);needed[item]=None
            if title:self.title=' '.join(title.split())
            seen=set()
            for token in self.metadata(package):
                if token is None or isinstance(token,str):continue
                name,attrs,closing=token
                if closing or name!='item':continue
                item=attrs.get('id')
                if item not in needed:continue
                if item in seen:raise ValueError('Duplicate EPUB manifest ID')
                seen.add(item)
                if attrs.get('media-type','') in ('application/xhtml+xml','text/html'):
                    path=resolve(package,attrs.get('href',''))
                    budget+=len(path)
                    if budget>32768:raise ValueError('EPUB reading order exceeds index budget')
                    needed[item]=path
            for item in spine:
                if item not in seen:raise ValueError('Broken EPUB reading order')
                if needed[item] is not None:self.chapters.append(needed[item])
            if not self.chapters:raise ValueError('No readable chapters')
            self.chapters=ChapterIndex(self.chapters)
            self.archive.entries.cache.clear();self.archive.entries.order=[]
        except Exception:self.close();raise

    def metadata(self,name,limit=2*1024*1024):
        entry=self.archive.entries[name]
        if entry[3]>limit:
            raise ValueError('EPUB metadata too large: %s (%d bytes; limit %d)'%(name,entry[3],limit))
        stream=self.archive.stream(name,limit)
        try:
            for token in stream_tokens(stream):yield token
        finally:stream.close()

    def chapter(self,index):return plain_text(self.archive.read(self.chapters[index]))

    def prepare(self,index):
        # Spread a cache miss in a large ZIP directory across idle ticks too.
        try:
            for entry in self.archive.entries.lookup(self.chapters[index]):
                if entry is None:yield None
        except KeyError:raise ValueError('Missing EPUB chapter')

    def stream(self,index):return self.archive.stream(self.chapters[index])

    def image_refs(self,index):
        base=self.chapters[index];images=[];seen=set()
        for token in stream_tokens(self.stream(index)):
            if token is None or isinstance(token,str):continue
            name,attrs,closing=token
            if closing or name not in ('img','image'):continue
            href=attrs.get('src') if name=='img' else attrs.get('href')
            if not href:continue
            try:path=resolve(base,href)
            except ValueError:continue
            if path in seen:continue
            seen.add(path)
            label=attrs.get('alt') or attrs.get('title') or path.rsplit('/',1)[-1]
            images.append((path,' '.join(label.split())[:80]))
            if len(images)>=32:break
        return images

    def close(self):self.archive.close()


class TxtBook:
    """UTF-8 text split into bounded parts at line or character boundaries."""

    def __init__(self,path):
        self.path=path;self.file=open(path,'rb')
        self.title=path.rsplit('/',1)[-1].rsplit('.',1)[0] or 'Text file'
        try:
            self.file.seek(0,2);self.size=self.file.tell()
            if self.size>TEXT_LIMIT:raise ValueError('Text file exceeds 8 MiB')
            self.chapters=self._starts()
        except Exception:self.close();raise

    def _starts(self):
        starts=[0];target=TEXT_CHUNK;f=self.file
        while target<self.size:
            f.seek(target);window=f.read(4096)
            at=window.find(b'\n')
            if at>=0:boundary=target+at+1
            else:
                # Never split a multi-byte UTF-8 character.
                boundary=target;f.seek(boundary);byte=f.read(1)
                while byte and byte[0]&0xc0==0x80:
                    boundary+=1;f.seek(boundary);byte=f.read(1)
            if boundary<=starts[-1]:boundary=min(self.size,target+4096)
            if boundary>=self.size:break
            starts.append(boundary);target=boundary+TEXT_CHUNK
        return starts

    def stream(self,index):
        start=self.chapters[index]
        end=self.chapters[index+1] if index+1<len(self.chapters) else self.size
        return TextStream(self.path,start,end-start)

    def chapter(self,index):
        start=self.chapters[index]
        end=self.chapters[index+1] if index+1<len(self.chapters) else self.size
        self.file.seek(start);data=self.file.read(end-start)
        text=data.decode('utf-8')
        if start==0 and text[:1]=='\ufeff':text=text[1:]
        return text.replace('\r\n','\n').replace('\r','\n')

    def close(self):
        if self.file:self.file.close();self.file=None


def open_book(path):
    return TxtBook(path) if path.lower().endswith('.txt') else Book(path)


class EntryIndex:
    """A small directory cache, independent of the number of ZIP assets."""
    def __init__(self,archive,offset,size,count):
        self.archive=archive;self.offset=offset;self.end=offset+size;self.count=count
        self.cache={};self.order=[]

    def __len__(self):return self.count

    def scan(self):
        f=self.archive.file;pos=self.offset
        for _ in range(self.count):
            if pos+46>self.end:raise ValueError('Invalid EPUB index bounds')
            f.seek(pos);row=f.read(46)
            if len(row)!=46 or row[:4]!=b'PK\x01\x02':raise ValueError('Invalid EPUB index')
            flags,method=struct.unpack('<HH',row[8:12])
            compressed,plain=struct.unpack('<II',row[20:28])
            nl,el,cl=struct.unpack('<HHH',row[28:34]);local=struct.unpack('<I',row[42:46])[0]
            if nl>1024 or not nl:raise ValueError('Invalid EPUB path length')
            if struct.unpack('<H',row[34:36])[0]:raise ValueError('Multi-disk EPUB entry unsupported')
            pos+=46+nl+el+cl
            if pos>self.end or local>=self.offset or 0xffffffff in (compressed,plain,local):
                raise ValueError('Unsupported EPUB ZIP bounds / ZIP64')
            name=f.read(nl)
            if len(name)!=nl:raise ValueError('Truncated EPUB index')
            yield name.decode('utf-8'),(flags,method,compressed,plain,local,struct.unpack('<I',row[16:20])[0])
        if pos!=self.end:raise ValueError('Invalid EPUB directory size')

    def lookup(self,name):
        if name in self.cache:yield self.cache[name];return
        found=None;count=0
        for key,entry in self.scan():
            if key==name:
                if found is not None:raise ValueError('Duplicate EPUB path')
                found=entry
            count+=1
            if count%32==0:yield None
        if found is None:raise KeyError(name)
        self[name]=found;yield found

    def __getitem__(self,name):
        for entry in self.lookup(name):
            if entry is not None:return entry

    def __setitem__(self,name,entry):
        if name not in self.cache:
            if len(self.order)>=16:del self.cache[self.order.pop(0)]
            self.order.append(name)
        self.cache[name]=entry

    def __contains__(self,name):
        try:self[name];return True
        except KeyError:return False


class _BoundedInput(io.IOBase):
    """Compatibility for older firmware; new firmware buffers this in C."""
    def __init__(self,source,size):self.source=source;self.left=size;self.data=b'';self.at=0
    def readinto(self,buffer):
        n=0
        while n<len(buffer):
            if self.at==len(self.data):
                if not self.left:break
                want=min(self.left,1024);self.data=self.source.read(want);self.at=0
                if len(self.data)!=want:raise OSError('Truncated EPUB input')
                self.left-=want
            take=min(len(buffer)-n,len(self.data)-self.at)
            buffer[n:n+take]=self.data[self.at:self.at+take];self.at+=take;n+=take
        return n
    def remaining(self):return self.left+len(self.data)-self.at


class EntryStream:
    """One independently seekable ZIP member, with a bounded inflate window."""
    def __init__(self,archive,name,limit):
        self.file=None;self.decoder=None;self.source=None;self.done=False;self.total=0;self.check=0
        try:
            flags,self.method,self.left,self.plain,offset,self.crc=archive.entries[name]
            if flags&1 or self.method not in (0,8):raise ValueError('Unsupported EPUB compression / encryption')
            if self.plain>limit:raise ValueError('EPUB text section exceeds 64 MiB')
            if self.method==0 and self.left!=self.plain:raise ValueError('Invalid stored EPUB size')
            self.file=open(archive.path,'rb');f=self.file;f.seek(offset);row=f.read(30)
            if len(row)!=30 or row[:4]!=b'PK\x03\x04':raise ValueError('Invalid EPUB section')
            if struct.unpack('<HH',row[6:10])!=(flags,self.method):raise ValueError('Inconsistent EPUB section')
            nl,el=struct.unpack('<HH',row[26:30]);start=offset+30+nl+el
            if start+self.left>archive.data_end:raise ValueError('Truncated EPUB section')
            f.seek(start);self.native=False;self.pending=b''
            if self.method==8:
                # Directory scan results can pin small objects across the heap.
                # Drop this optional cache before allocating a contiguous window.
                archive.entries.cache.clear();archive.entries.order=[]
                collect()
                try:import deflate
                except ImportError:
                    import zlib
                    self.decoder=zlib.decompressobj(-15)
                else:
                    try:from pngdec import BoundedReader
                    except ImportError:BoundedReader=_BoundedInput
                    self.source=BoundedReader(f,self.left);bits=5
                    while bits<15 and (1<<bits)<self.plain:bits+=1
                    self.decoder=deflate.DeflateIO(self.source,deflate.RAW,bits);self.native=True
        except Exception:self.close();raise

    def read(self,size=STREAM_CHUNK):
        if self.done:return b''
        try:
            if self.method==0:
                want=min(size,self.left);data=self.file.read(want);self.left-=len(data)
                if len(data)!=want:raise ValueError('Truncated EPUB text')
                eof=not self.left
            elif self.native:
                data=self.decoder.read(size);eof=not data
            else:
                data=b''
                while not data and not self.decoder.eof:
                    if not self.pending and self.left:
                        want=min(self.left,1024);self.pending=self.file.read(want);self.left-=len(self.pending)
                        if len(self.pending)!=want:raise ValueError('Truncated EPUB text')
                    data=self.decoder.decompress(self.pending,size);self.pending=self.decoder.unconsumed_tail
                    if not data and not self.decoder.eof and not self.pending and not self.left:raise ValueError('Truncated EPUB deflate')
                eof=self.decoder.eof
            self.total+=len(data);self.check=binascii.crc32(data,self.check)&0xffffffff
            if self.total>self.plain:raise ValueError('Invalid EPUB text size')
            if eof:
                remaining=self.source.remaining() if self.native else self.left
                if (self.method==8 and not self.native and (self.decoder.unused_data or self.pending)) or remaining:
                    raise ValueError('Trailing EPUB compressed data')
                if self.total!=self.plain or self.check!=self.crc:raise ValueError('Damaged EPUB text')
                self.done=True;self.close()
            return data
        except Exception:self.close();raise

    def close(self):
        if self.decoder and self.native:self.decoder.close()
        self.decoder=None;self.source=None
        if self.file:self.file.close();self.file=None


class TextStream:
    def __init__(self,path,start,size):
        self.file=open(path,'rb');self.file.seek(start);self.left=size
    def read(self,size=STREAM_CHUNK):
        data=self.file.read(min(size,self.left));self.left-=len(data)
        if not data and self.left:raise ValueError('Truncated text file')
        return data
    def close(self):
        if self.file:self.file.close();self.file=None


def utf8_chunks(stream):
    """Decode with at most three trailing bytes carried between reads."""
    pending=b'';first=True
    try:
        while True:
            data=stream.read()
            if not data:
                if pending:yield pending.decode('utf-8')
                return
            data=pending+data;end=len(data)
            # Locate an incomplete final UTF-8 character, without hiding invalid bytes.
            at=end-1
            while at>=0 and data[at]&0xc0==0x80:at-=1
            if at>=0:
                c=data[at];need=1 if c<128 else 2 if c&0xe0==0xc0 else 3 if c&0xf0==0xe0 else 4 if c&0xf8==0xf0 else 1
                if end-at<need:end=at
            text=data[:end].decode('utf-8');pending=data[end:]
            if first:text=text.lstrip('\ufeff');first=False
            yield text
    finally:stream.close()


def stream_tokens(stream,paired=False):
    """Bounded XHTML tokenizer. None marks one chunk of cooperative work."""
    pending='';comment=False
    for text in utf8_chunks(stream):
        pending+=text
        while pending:
            if comment:
                at=pending.find('-->')
                if at<0:pending=pending[-2:];break
                pending=pending[at+3:];comment=False;continue
            at=pending.find('<')
            if at!=0:
                end=len(pending) if at<0 else at
                # Retain a potentially split entity until its following chunk.
                amp=pending.rfind('&',0,end)
                if at<0 and amp>=max(0,end-16) and ';' not in pending[amp:end]:end=amp
                if end:yield decode_entities(pending[:end]);pending=pending[end:]
                if at<0:break
                continue
            if pending.startswith('<!--'):pending=pending[4:];comment=True;continue
            if len(pending)<4 and '<!--'.startswith(pending):break
            end=1;quote=''
            while end<len(pending):
                c=pending[end]
                if quote:
                    if c==quote:quote=''
                elif c in ('"',"'"):quote=c
                elif c=='>':break
                end+=1
            if end==len(pending):
                if len(pending)>2048:raise ValueError('EPUB tag exceeds 2 KiB')
                break
            if end>2048:raise ValueError('EPUB tag exceeds 2 KiB')
            for token in tokens(pending[:end+1],paired):yield token
            pending=pending[end+1:]
        yield None
    if comment or pending.startswith('<'):raise ValueError('Unclosed EPUB markup')
    if pending:yield decode_entities(pending)
