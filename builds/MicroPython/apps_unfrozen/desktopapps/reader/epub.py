"""Bounded, read-only EPUB text loader; no extraction onto the SD card."""
import struct
import binascii
import io

LIMIT=192*1024
TEXT_LIMIT=8*1024*1024
TEXT_CHUNK=96*1024


def decode_entities(text):
    named={'amp':'&','lt':'<','gt':'>','quot':'"','apos':"'",'nbsp':' '}
    result=[];pos=0
    while pos<len(text):
        if text[pos]=='&':
            end=text.find(';',pos+1,pos+14)
            if end>=0:
                key=text[pos+1:end];value=named.get(key)
                if key.startswith('#'):
                    try:value=chr(int(key[2:],16) if key.startswith('#x') else int(key[1:]))
                    except (ValueError,OverflowError):pass
                if value is not None:result.append(value);pos=end+1;continue
        result.append(text[pos]);pos+=1
    return ''.join(result)


def tokens(text):
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
            key=raw[begin:i].split(':')[-1]
            while i<len(raw) and raw[i].isspace():i+=1
            if i>=len(raw) or raw[i]!='=':break
            i+=1
            while i<len(raw) and raw[i].isspace():i+=1
            if i>=len(raw) or raw[i] not in ('"',"'"):break
            q=raw[i];i+=1;begin=i
            while i<len(raw) and raw[i]!=q:i+=1
            attrs[key]=decode_entities(raw[begin:i]);i+=1
        yield (name,attrs,closing)


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
        self.file=open(path,'rb');self.entries={}
        try:
            f=self.file;f.seek(0,2);size=f.tell()
            if size>32*1024*1024:raise ValueError('Book exceeds 32 MiB')
            f.seek(max(0,size-65557));tail=f.read();at=tail.rfind(b'PK\x05\x06')
            if at<0 or len(tail)-at<22:raise ValueError('Invalid EPUB ZIP')
            disk,cd_disk,n_disk,count,cd_size,offset,comment=struct.unpack('<4H2IH',tail[at+4:at+22])
            if disk or cd_disk or n_disk!=count or count>1024 or offset+cd_size>size:raise ValueError('Unsupported EPUB ZIP')
            f.seek(offset)
            for _ in range(count):
                row=f.read(46)
                if len(row)!=46 or row[:4]!=b'PK\x01\x02':raise ValueError('Invalid EPUB index')
                flags,method=struct.unpack('<HH',row[8:12])
                compressed,plain=struct.unpack('<II',row[20:28])
                nl,el,cl=struct.unpack('<HHH',row[28:34]);local=struct.unpack('<I',row[42:46])[0]
                if nl>1024:raise ValueError('Book path too long')
                name=f.read(nl).decode('utf-8');f.seek(el+cl,1)
                if name in self.entries:raise ValueError('Duplicate EPUB path')
                crc=struct.unpack('<I',row[16:20])[0]
                self.entries[name]=(flags,method,compressed,plain,local,crc)
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
            try:import deflate
            except ImportError:
                import zlib
                decoder=zlib.decompressobj(-15);data=decoder.decompress(data,limit+1)
                if not decoder.eof:raise ValueError('Invalid or oversized EPUB section')
            else:
                with deflate.DeflateIO(io.BytesIO(data),deflate.RAW,15) as stream:data=stream.read(limit+1)
        if len(data)!=plain or len(data)>limit:raise ValueError('Invalid EPUB section size')
        if binascii.crc32(data)&0xffffffff!=crc:raise ValueError('Damaged EPUB section')
        return data.decode('utf-8')


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


class Book:
    def __init__(self,path):
        self.archive=Archive(path);self.title=path.rsplit('/',1)[-1];self.chapters=[]
        try:
            if self.archive.read('mimetype',128).strip()!='application/epub+zip':raise ValueError('Not an EPUB book')
            if 'META-INF/encryption.xml' in self.archive.entries:raise ValueError('Encrypted EPUB resources unsupported')
            package=None
            for token in tokens(self.archive.read('META-INF/container.xml',16384)):
                if not isinstance(token,str) and token[0]=='rootfile':package=resolve('',token[1].get('full-path',''));break
            if not package:raise ValueError('Missing EPUB package')
            manifest={};spine=[];in_title=False;title=[]
            for token in tokens(self.archive.read(package,65536)):
                if isinstance(token,str):
                    if in_title:title.append(decode_entities(token))
                    continue
                name,attrs,closing=token
                if name=='title':in_title=not closing
                if not closing and name=='item':manifest[attrs.get('id')]=(attrs.get('href',''),attrs.get('media-type',''))
                if not closing and name=='itemref' and attrs.get('linear')!='no':spine.append(attrs.get('idref'))
            if title:self.title=' '.join(''.join(title).split())
            for item in spine:
                if item not in manifest:raise ValueError('Broken EPUB reading order')
                href,media=manifest[item]
                if media in ('application/xhtml+xml','text/html'):self.chapters.append(resolve(package,href))
            if not self.chapters:raise ValueError('No readable chapters')
        except Exception:self.close();raise

    def chapter(self,index):return plain_text(self.archive.read(self.chapters[index]))
    def close(self):self.archive.close()


class TxtBook:
    """UTF-8 text split into bounded parts at line or character boundaries."""

    def __init__(self,path):
        self.file=open(path,'rb')
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
