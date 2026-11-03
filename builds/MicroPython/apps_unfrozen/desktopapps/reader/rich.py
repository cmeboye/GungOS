"""Bounded equation blocks and disk-backed mixed text/math page payloads."""
import json,os
from .mathml import MathNode,MAX_NODES,MAX_DEPTH,MAX_TEXT
from .epub import stream_tokens,utf8_chunks,TxtBook

class Equation:
    def __init__(self,index,node,error=''):
        self.index=index;self.node=node;self.error=error;self.end=0

def tokens(book,chapter):
    stream=book.stream(chapter);source=stream_tokens(stream,paired=True)
    level=0;stack=[];root=None;error='';ordinal=0;count=0;size=0;hidden=0
    try:
        for token in source:
            if token is None:yield None;continue
            if not level:
                if not isinstance(token,str) and token[0] in ('head','script','style'):
                    hidden=max(0,hidden+(-1 if token[2] else 1))
                if hidden or isinstance(token,str) or token[0]!='math' or token[2]:yield token;continue
                level=1;root=MathNode('math',token[1]);stack=[root];count=1;size=0;error=''
                yield ('__math_start',{},False);continue
            # Preserve the old visible-text anchor accounting inside expressions.
            yield token
            if isinstance(token,str):
                if not error:
                    size+=len(token)
                    if size>MAX_TEXT:error='Equation text limit';stack=[];root=None
                    elif stack[-1].tag in ('mi','mn','mo','mtext','ms'):stack[-1].children.append(token)
                    elif token.strip():error='Invalid MathML text';stack=[];root=None
                continue
            tag,attrs,closing=token
            if closing:
                level-=1
                if not error:
                    if not stack or stack[-1].tag!=tag:error='Invalid MathML nesting';stack=[];root=None
                    else:stack.pop()
                if not level:
                    yield Equation(ordinal,root,error);ordinal+=1;root=None;stack=[]
            else:
                level+=1;count+=1
                if level>MAX_DEPTH or count>MAX_NODES:error='Equation depth/node limit';stack=[];root=None
                elif not error:
                    node=MathNode(tag,attrs);stack[-1].children.append(node);stack.append(node)
        if level:raise ValueError('Unclosed MathML equation')
    finally:source.close();stream.close()

def words(book,chapter,rich=True):
    source=tokens(book,chapter)
    in_math=False;math_begin=0
    hidden=[];word='';number=0;offset=0;start=0;continued=False;had_word=False;paragraph=False
    try:
        for token in source:
            if token is None:yield None;continue
            if rich and isinstance(token,Equation):
                if word:word='';continued=True
                in_math=False;token.end=offset
                yield (number,math_begin,token,False)
                continue
            if rich and not isinstance(token,str) and token[0]=='__math_start':
                if word:
                    yield (number,start,word,continued);word='';continued=True
                in_math=True;math_begin=offset;continue
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
                        if not in_math:yield (number,start,word,continued)
                        word='';continued=False;number+=1
                    elif continued:continued=False;number+=1
                    if char in '\n\r' and paragraph:
                        if not in_math:yield (number,offset,None,False)
                        paragraph=False
                else:
                    if not word and not continued:
                        if had_word:offset+=1
                        start=offset;had_word=True
                    if not word:start=offset
                    word+=char;offset+=1;paragraph=True
                    if len(word)==128:
                        if not in_math:yield (number,start,word,continued)
                        word='';continued=True
            # TXT chunks also give the scheduler a chance to service keys.
            if isinstance(book,TxtBook):yield None
        if word:yield (number,start,word,continued);number+=1
        elif continued:number+=1
        if paragraph:yield (number,offset,None,False)
    finally:
        source.close()


def lines(book,chapter,width,rich=False):
    if rich:
        from .rich import words as rich_words
        source=rich_words(book,chapter)
    else:source=words(book,chapter)
    line='';first=0;begin=0;last=0;end=0
    try:
        for event in source:
            if event is None:yield None;continue
            number,offset,text,continued=event
            if rich:
                from .rich import Equation
                if isinstance(text,Equation):
                    if line:yield (first,last,begin,end,line);line=''
                    yield (number,number+1,offset,text.end,text);continue
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


def pack(node):return [node.tag,node.attrs,[c if isinstance(c,str) else pack(c) for c in node.children]]
def unpack(data):
    node=MathNode(data[0],data[1]);node.children=[c if isinstance(c,str) else unpack(c) for c in data[2]];return node

class RichPages:
    def __init__(self,draw,font,height,path):
        from .mathlayout import MathRenderer
        self.renderer=MathRenderer(draw,(0,0,320,320));self.font=font;self.lineheight=height
        self.path=path+'.math';self.file=open(self.path,'w+b');self.size=0
    def store(self,chapter,item):
        data=(json.dumps(pack(item.node)) if item.node else 'null').encode('utf-8')
        if len(data)>32768:raise ValueError('Equation storage limit')
        if self.size+len(data)>16*1024*1024:raise ValueError('Equation cache full; reopen the book')
        offset=self.size;self.file.seek(offset)
        if self.file.write(data)!=len(data):raise OSError('Equation cache write failed')
        self.size+=len(data);return [offset,len(data)]
    def close(self):
        self.file.close()
        try:os.remove(self.path)
        except OSError:pass
    def read(self,ref):
        self.file.seek(ref[0]);data=self.file.read(ref[1])
        if len(data)!=ref[1]:raise OSError('Incomplete equation cache')
        data=json.loads(data.decode('utf-8'));return unpack(data) if data else None
    def pages(self,book,chapter,width,rows):
        source=lines(book,chapter,width,True);page=0;batch=[];used=0;first=None;last=None;limit=rows*self.lineheight
        try:
            for line in source:
                if line is None:yield None;continue
                value=line[4]
                if isinstance(value,Equation):
                    error=value.error;box=None
                    if not error:
                        try:box=self.renderer.layout_math(value.node,self.font)
                        except ValueError as exc:error=str(exc)
                    height=min(limit,max(self.lineheight,(box.h+4) if box else self.lineheight*2))
                    path=self.store(chapter,value)
                    block=['m',path,value.index,height,error, bool(box and (box.w>304 or box.h+4>limit))]
                    box=None;value.node=None
                else:height=self.lineheight;block=['t',value]
                # JSON is a page-cache envelope, bounded independently of trees.
                if batch and (used+height>limit or len(json.dumps(batch))+len(json.dumps(block))>3500):
                    yield (chapter,page,first[0],last[1],first[2],last[3],'\x1e'+json.dumps(batch))
                    page+=1;batch=[];used=0;first=None
                if first is None:first=line
                batch.append(block);used+=height;last=line
            if batch or not page:
                yield (chapter,page,first[0] if first else 0,last[1] if last else 0,first[2] if first else 0,last[3] if last else 0,'\x1e'+json.dumps(batch))
        finally:source.close()

from .pager import Session
class RichSession(Session):
    def __init__(self,book,width,rows,path,counts,rich):
        super().__init__(book,width,rows,path,counts);self.rich=rich
    def start_source(self,chapter):
        self.stop_source();self.source=self.rich.pages(self.book,chapter,self.width,self.rows)
        self.source_chapter=chapter;self.produced=0
    def close(self):
        super().close();self.rich.close()
