"""Bounded Presentation MathML discovery; no evaluation or EPUB scripts."""
from .epub import stream_tokens

MAX_NODES=768
MAX_TEXT=4096
MAX_DEPTH=24

class MathNode:
    def __init__(self,tag,attrs=None):
        self.tag=tag;self.attrs=attrs or {};self.children=[]

def equations(book,chapter):
    """Yield None per source chunk, or (zero-based ordinal, node, error).

    Oversized equations are skipped to their end, allowing the next one to load.
    Only one equation tree is retained at a time; no whole chapter allocation.
    """
    stream=book.stream(chapter);source=stream_tokens(stream,paired=True)
    stack=[];root=None;level=0;nodes=0;size=0;ordinal=0;error='';hidden=0
    try:
        for token in source:
            if token is None:yield None;continue
            if isinstance(token,str):
                if level and not error:
                    # Formatting whitespace between structural tags is not text.
                    if stack and stack[-1].tag in ('mi','mn','mo','mtext','ms'):
                        size+=len(token)
                        if size>MAX_TEXT:error='Equation text exceeds 4096 characters';stack=[];root=None
                        else:stack[-1].children.append(token)
                    elif token.strip():error='Text outside a MathML token';stack=[];root=None
                continue
            tag,attrs,closing=token
            if not level:
                if tag in ('script','style'):
                    hidden=max(0,hidden+(-1 if closing else 1))
                if tag!='math' or closing or hidden:continue
                level=1;nodes=1;size=0;error='';root=MathNode(tag,attrs);stack=[root];continue
            if closing:
                level-=1
                if not error:
                    if not stack or stack[-1].tag!=tag:error='Mismatched MathML closing tag';stack=[];root=None
                    else:stack.pop()
                if level==0:
                    yield ordinal,root,error
                    ordinal+=1;root=None;stack=[];error=''
            else:
                level+=1;nodes+=1
                if level>MAX_DEPTH or nodes>MAX_NODES:
                    error='Equation exceeds depth/node budget';stack=[];root=None
                elif not error:
                    child=MathNode(tag,attrs);stack[-1].children.append(child);stack.append(child)
        if level:raise ValueError('Unclosed MathML equation')
    finally:
        source.close();stream.close()
