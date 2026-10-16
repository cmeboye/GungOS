"""Bounded rich paragraphs and structured equations, with one-level undo."""
import json
from engtools.calculator.editor import Node,SLOTS,count,depth,source

MAX_TEXT,MAX_BLOCKS,MAX_MATH,MAX_FILE=8192,96,1536,49152


def paragraph(text='',font=1,color=None,align=0):
    return {'type':'text','text':text,'font':font,'color':color,'align':align}


def pack_tree(row):
    return [item if isinstance(item,str) else [item.kind,[pack_tree(child) for child in item.rows]] for item in row]


def unpack_tree(data,level=0,budget=None):
    if budget is None:budget=[384]
    if level>10 or not isinstance(data,list):raise ValueError('Invalid equation nesting')
    result=[]
    for item in data:
        budget[0]-=1
        if budget[0]<0:raise ValueError('Equation limit: 384 items')
        if isinstance(item,str):
            if len(item)!=1 or ord(item)<32:raise ValueError('Invalid equation character')
            result.append(item)
        else:
            if not isinstance(item,list) or len(item)!=2:raise ValueError('Invalid equation node')
            kind,rows=item
            if kind not in SLOTS and kind!='pi':raise ValueError('Unknown equation template')
            if not isinstance(rows,list) or len(rows)!=len(SLOTS.get(kind,())):raise ValueError('Invalid equation slots')
            result.append(Node(kind,[unpack_tree(child,level+1,budget) for child in rows]))
    return result


class Document:
    def __init__(self):self.blocks=[paragraph()];self.dirty=False;self.undo=None
    def apply(self,blocks):
        if not 1<=len(blocks)<=MAX_BLOCKS:raise ValueError('Document limit: 96 blocks')
        text_size=math_size=0
        for block in blocks:
            if type(block.get('font'))!=int or not 0<=block['font']<=4:raise ValueError('Invalid font size')
            color=block.get('color')
            if color is not None and (type(color)!=int or not 0<=color<=65535):raise ValueError('Invalid colour')
            if block.get('align') not in (0,1,2):raise ValueError('Invalid alignment')
            if block.get('type')=='text':
                text=block.get('text')
                if not isinstance(text,str) or any(c in text for c in '\x00\r\n'):raise ValueError('Invalid paragraph')
                text_size+=len(text)
            elif block.get('type')=='equation':
                row=block.get('row',[])
                if count(row)>384 or depth(row)>10:raise ValueError('Equation limit')
                math_size+=count(row)
            else:raise ValueError('Invalid document block')
        if text_size>MAX_TEXT or math_size>MAX_MATH:raise ValueError('Document text/equation budget reached')
        self.undo=(self.blocks,self.dirty)
        self.blocks,self.dirty=blocks,True
    def set_block(self,index,block):
        blocks=list(self.blocks);blocks[index]=block;self.apply(blocks)
    def mark_saved(self):
        if self.undo is not None:self.undo=(self.undo[0],True)
    def restore(self):
        if self.undo is None:return False
        self.blocks,self.dirty=self.undo;self.undo=None;return True
    def document(self):
        records=[]
        for block in self.blocks:
            record=dict(block)
            if record['type']=='equation':record['row']=pack_tree(record['row'])
            records.append(record)
        text=json.dumps({'picoword':1,'blocks':records})
        if len(text.encode('utf-8'))>MAX_FILE:raise ValueError('Document exceeds 48 KiB')
        return text
    def plain(self):
        return '\n'.join(block['text'] if block['type']=='text' else 'eq('+source(block['row'],False)+')' for block in self.blocks)+'\n'
    @classmethod
    def parse(cls,text):
        if len(text)>MAX_FILE:raise ValueError('Document exceeds 48 KiB')
        data=json.loads(text)
        if not isinstance(data,dict) or data.get('picoword')!=1:raise ValueError('Not a PicoWord document')
        blocks=data.get('blocks')
        if not isinstance(blocks,list) or len(blocks)>MAX_BLOCKS:raise ValueError('Invalid block list')
        decoded=[]
        for block in blocks:
            if not isinstance(block,dict):raise ValueError('Invalid document block')
            block=dict(block)
            if block.get('type')=='equation':block['row']=unpack_tree(block.get('row'))
            decoded.append(block)
        result=cls();result.apply(decoded);result.dirty=False;result.undo=None;return result


def example():
    d=Document()
    d.apply([paragraph('Field notes',3),paragraph('PicoWord',1,None,2),
             paragraph('A pocket notebook for text and equations. Choose fonts with F3 and colours with F4.'),
             {'type':'equation','row':['x',Node('pow',[['2']]),'+','y',Node('pow',[['2']]),'=',
                                      'r',Node('pow',[['2']])],'font':2,'color':None,'align':1},
             paragraph('Type eq() then SPACE to insert an equation box. Powers, roots, fractions and integrals use the calculator editor.',1),
             paragraph('Write. Calculate. Explore.',1,0x0410)])
    return d
