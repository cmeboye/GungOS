"""Small Excel-style formula parser. No eval, imports or Python execution."""
import math

ROWS, COLS = 200, 26
MAX_TEXT = 256
ERRORS = ('#REF!', '#DIV/0!', '#CYCLE!', '#VALUE!', '#NAME?', '#ERROR!', '#NUM!', '#LIMIT!')


class CellError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def finite(value):
    return not math.isnan(value) and not math.isinf(value)


def address(row, col):
    return chr(65+col)+str(row+1)


def reference(text):
    value = text.replace('$', '').upper()
    split = 0
    while split < len(value) and 'A' <= value[split] <= 'Z': split += 1
    if split == 0 or split == len(value) or not value[split:].isdigit():
        raise CellError('#NAME?')
    column = 0
    for char in value[:split]: column = column*26+ord(char)-64
    row, col = int(value[split:])-1, column-1
    if not 0 <= row < ROWS or not 0 <= col < COLS:
        raise CellError('#REF!')
    return row, col


def tokenize(text):
    if len(text) > MAX_TEXT: raise CellError('#LIMIT!')
    items, i = [], 0
    while i < len(text):
        char, start = text[i], i
        if char.isspace(): i += 1; continue
        if char == '"':
            i += 1; value = ''; closed = False
            while i < len(text):
                if text[i] == '"':
                    i += 1
                    if i < len(text) and text[i] == '"': value += '"'; i += 1
                    else: closed = True; break
                else: value += text[i]; i += 1
            if not closed: raise CellError('#ERROR!')
            kind = 'string'
        elif char.isdigit() or char == '.':
            i += 1
            while i < len(text) and (text[i].isdigit() or text[i] == '.'): i += 1
            if i < len(text) and text[i] in 'eE':
                end = i+1
                if end < len(text) and text[end] in '+-': end += 1
                digits = end
                while end < len(text) and text[end].isdigit(): end += 1
                if end > digits: i = end
            try: value = float(text[start:i])
            except ValueError: raise CellError('#ERROR!')
            if not finite(value): raise CellError('#NUM!')
            kind = 'number'
        elif char.isalpha() or char == '$':
            i += 1
            while i < len(text) and (text[i].isalpha() or text[i].isdigit() or text[i] in '$_'): i += 1
            kind, value = 'name', text[start:i].upper()
        elif char == '#':
            value = next((code for code in ERRORS if text.startswith(code, i)), None)
            if value is None: raise CellError('#ERROR!')
            i += len(value); kind = 'error'
        elif char in '+-*/^%(),:=<>&':
            i += 1; kind = value = char
            if char in '<>' and i < len(text) and text[i] in '=>':
                kind = value = char+text[i]; i += 1
        else: raise CellError('#ERROR!')
        items.append((kind, value, start, i))
        if len(items) > 128: raise CellError('#LIMIT!')
    items.append(('end', '', i, i))
    return items


class Parser:
    """Iterative shunting-yard parser: no call-stack growth with expressions."""
    def __init__(self,text):self.items=tokenize(text)
    def parse(self):
        values,ops=[],[];want=True;i=0;groups=0
        priorities={'=':5,'<>':5,'<':5,'>':5,'<=':5,'>=':5,'&':8,'+':10,'-':10,'*':20,'/':20,'^':40}
        def reduce():
            kind,op,priority=ops.pop()
            if kind=='unary':
                if not values:raise CellError('#ERROR!')
                values.append(('unary',op,values.pop()))
            else:
                if len(values)<2:raise CellError('#ERROR!')
                right=values.pop();left=values.pop();values.append(('binary',op,left,right))
        while self.items[i][0]!='end':
            kind,value,_,_=self.items[i]
            if kind in ('number','string','error','name'):
                if not want:raise CellError('#ERROR!')
                if kind=='name' and self.items[i+1][0]=='(':
                    ops.append(['(',value,len(values),0]);groups+=1;i+=2
                    if groups>24:raise CellError('#LIMIT!')
                    continue
                if kind in ('number','string'):node=('value',value)
                elif kind=='error':node=('error',value)
                elif value in ('TRUE','FALSE'):node=('value',value=='TRUE')
                else:
                    first=reference(value)
                    if self.items[i+1][0]==':':
                        i+=2
                        if self.items[i][0]!='name':raise CellError('#ERROR!')
                        node=('range',first,reference(self.items[i][1]))
                    else:node=('ref',first)
                values.append(node);want=False
            elif kind=='(':
                if not want:raise CellError('#ERROR!')
                ops.append(['(',None,len(values),0]);groups+=1
                if groups>24:raise CellError('#LIMIT!')
            elif kind in (',',')'):
                while ops and ops[-1][0]!='(':reduce()
                if not ops:raise CellError('#ERROR!')
                marker=ops[-1];name,start,commas=marker[1:]
                empty=want and name is not None and commas==0 and len(values)==start
                if want and not (kind==')' and empty):raise CellError('#ERROR!')
                if not empty and len(values)!=start+commas+1:raise CellError('#ERROR!')
                if kind==',':
                    if name is None:raise CellError('#ERROR!')
                    marker[3]+=1;want=True
                else:
                    ops.pop();groups-=1
                    if name is None:
                        if commas or len(values)!=start+1:raise CellError('#ERROR!')
                    else:
                        args=values[start:];del values[start:];values.append(('call',name,args))
                    want=False
            elif kind=='%':
                if want:raise CellError('#ERROR!')
                values.append(('percent',values.pop()))
            elif want and kind in ('+','-'):ops.append(('unary',kind,50))
            elif not want and kind in priorities:
                priority=priorities[kind]
                while ops and ops[-1][0]!='(' and ops[-1][2]>=priority:reduce()
                ops.append(('binary',kind,priority));want=True
            else:raise CellError('#ERROR!')
            i+=1
        if want:raise CellError('#ERROR!')
        while ops:
            if ops[-1][0]=='(':raise CellError('#ERROR!')
            reduce()
        if len(values)!=1:raise CellError('#ERROR!')
        return values[0]


def number(value):
    if value is None: return 0
    if isinstance(value,bool):return int(value)
    if not isinstance(value, (int, float)): raise CellError('#VALUE!')
    return value


def literal(raw):
    if not raw:return None
    if raw.startswith("'"):return raw[1:]
    if raw.upper() in ('TRUE','FALSE'):return raw.upper()=='TRUE'
    try:value=float(raw.strip())
    except ValueError:return raw
    if not finite(value):raise CellError('#NUM!')
    return value


def binary(op,left,right):
    if op=='&':
        value=str('' if left is None else left)+str('' if right is None else right)
        if len(value)>MAX_TEXT:raise CellError('#LIMIT!')
        return value
    if op in ('=','<>','<','>','<=','>='):
        if isinstance(left,str) and isinstance(right,str):left,right=left.lower(),right.lower()
        elif isinstance(left,str) or isinstance(right,str):
            if op in ('=','<>'):return op=='<>'
            raise CellError('#VALUE!')
        else:left,right=number(left),number(right)
        if op=='=':return left==right
        if op=='<>':return left!=right
        if op=='<':return left<right
        if op=='>':return left>right
        if op=='<=':return left<=right
        return left>=right
    left,right=number(left),number(right)
    if op=='+':return left+right
    if op=='-':return left-right
    if op=='*':return left*right
    if op=='/':
        if right==0:raise CellError('#DIV/0!')
        return left/right
    if abs(right)>1000:raise CellError('#LIMIT!')
    if left==0 and right<0:raise CellError('#DIV/0!')
    return math.pow(left,right)


def function(name,args):
    if name=='ROUND' and len(args) in (1,2):
        digits=number(args[1]) if len(args)==2 else 0
        if digits!=int(digits) or not -8<=digits<=8:raise CellError('#VALUE!')
        factor=math.pow(10,digits);value=number(args[0])*factor
        return (math.floor(value+0.5) if value>=0 else math.ceil(value-0.5))/factor
    if name=='PI' and not args:return math.pi
    functions={'ABS':abs,'SQRT':math.sqrt,'SIN':math.sin,'COS':math.cos,'TAN':math.tan}
    if name not in functions:raise CellError('#NAME?')
    if len(args)!=1:raise CellError('#VALUE!')
    return functions[name](number(args[0]))


def arguments(args):
    for node in args:
        if node[0]!='range':yield node;continue
        a,b=node[1:];r0,r1=min(a[0],b[0]),max(a[0],b[0]);c0,c1=min(a[1],b[1]),max(a[1],b[1])
        if (r1-r0+1)*(c1-c0+1)>2048:raise CellError('#LIMIT!')
        for row in range(r0,r1+1):
            for col in range(c0,c1+1):yield ('ref',(row,col))


class Evaluation:
    """Explicit task/value stacks; 200-cell chains do not recurse in Python."""
    def __init__(self,sheet):self.sheet=sheet;self.steps=0;self.result=None;self.problem=None
    def cell(self,position):
        for _ in self.job(position):pass
        return self.result
    def run(self,node):
        for _ in self.job(node=node):pass
        return self.result
    def job(self,position=None,node=None):
        tasks=[('cell',position)] if node is None else [('node',node)]
        values=[];active=set();path=[];self.steps=0;self.problem=None
        try:
            while tasks:
                self.steps+=1
                if self.steps>16000 or len(tasks)+len(values)>4096:raise CellError('#LIMIT!')
                task=tasks.pop();kind=task[0]
                if kind=='cell':
                    pos=task[1];raw=self.sheet.cells.get(pos,'')
                    if pos in active:raise CellError('#CYCLE!')
                    if pos in self.sheet.cache:
                        value=self.sheet.cache[pos]
                        if isinstance(value,CellError):raise value
                        values.append(value)
                    elif raw.startswith('='):
                        if len(active)>=512:raise CellError('#LIMIT!')
                        active.add(pos);path.append(pos)
                        tasks.append(('store',pos));tasks.append(('node',Parser(raw[1:]).parse()))
                    else:
                        value=literal(raw);self.sheet.cache[pos]=value;values.append(value)
                elif kind=='store':
                    value=values[-1]
                    if isinstance(value,float) and not finite(value):raise CellError('#NUM!')
                    self.sheet.cache[task[1]]=value;active.remove(task[1]);path.pop()
                elif kind=='node':
                    item=task[1];tag=item[0]
                    if tag=='value':values.append(item[1])
                    elif tag=='error':raise CellError(item[1])
                    elif tag=='ref':tasks.append(('cell',item[1]))
                    elif tag=='range':raise CellError('#VALUE!')
                    elif tag in ('unary','percent'):
                        tasks.append((tag,item[1] if tag=='unary' else None));tasks.append(('node',item[2] if tag=='unary' else item[1]))
                    elif tag=='binary':
                        tasks.append(('binary',item[1]));tasks.append(('node',item[3]));tasks.append(('node',item[2]))
                    else:
                        name,args=item[1:]
                        if name=='IF':
                            if len(args) not in (2,3):raise CellError('#VALUE!')
                            tasks.append(('if',args));tasks.append(('node',args[0]))
                        elif name in ('SUM','AVERAGE','MIN','MAX','COUNT'):
                            tasks.append(('aggregate',arguments(args),[name,0,0,None,None]))
                        else:
                            tasks.append(('call',name,len(args)))
                            for arg in reversed(args):tasks.append(('node',arg))
                elif kind=='binary':
                    right=values.pop();left=values.pop();values.append(binary(task[1],left,right))
                elif kind=='unary':
                    value=number(values.pop());values.append(-value if task[1]=='-' else value)
                elif kind=='percent':values.append(number(values.pop())/100)
                elif kind=='if':
                    condition=values.pop();args=task[1]
                    if isinstance(condition,str):raise CellError('#VALUE!')
                    if condition:tasks.append(('node',args[1]))
                    elif len(args)==3:tasks.append(('node',args[2]))
                    else:values.append(False)
                elif kind=='call':
                    count=task[2];args=values[-count:] if count else []
                    if count:del values[-count:]
                    values.append(function(task[1],args))
                elif kind=='aggregate':
                    iterator,state=task[1:]
                    try:arg=next(iterator)
                    except StopIteration:
                        name,total,count,lo,hi=state
                        if name=='SUM':value=total
                        elif name=='COUNT':value=count
                        elif name=='AVERAGE':
                            if not count:raise CellError('#DIV/0!')
                            value=total/count
                        else:value=(lo if name=='MIN' else hi) if count else 0
                        values.append(value)
                    else:tasks.append(('accumulate',iterator,state));tasks.append(('node',arg))
                elif kind=='accumulate':
                    iterator,state=task[1:];value=values.pop()
                    if value is not None and not isinstance(value,str):
                        value=number(value);state[1]+=value;state[2]+=1
                        state[3]=value if state[3] is None else min(state[3],value)
                        state[4]=value if state[4] is None else max(state[4],value)
                    tasks.append(('aggregate',iterator,state))
                if self.steps%128==0:yield self.steps
            if len(values)!=1:raise CellError('#ERROR!')
            self.result=values[0]
            if isinstance(self.result,float) and not finite(self.result):raise CellError('#NUM!')
        except (ValueError,OverflowError,ZeroDivisionError):
            error=CellError('#NUM!');self.problem=path[-1] if path else position
            for pos in path:self.sheet.cache[pos]=error
            raise error
        except CellError as error:
            self.problem=path[-1] if path else position
            if error.code!='#LIMIT!':
                for pos in path:self.sheet.cache[pos]=error
            raise
        except (RuntimeError,MemoryError):
            self.problem=path[-1] if path else position
            raise
        finally:active.clear()


def shifted(raw, rows, cols):
    """Adjust relative references on copy, preserving strings and $ anchors."""
    if not raw.startswith('='): return raw
    try: items = tokenize(raw[1:])
    except CellError: return raw
    output, last = '=', 0
    text = raw[1:]
    for index, item in enumerate(items[:-1]):
        kind, value, start, end = item
        if kind != 'name' or items[index+1][0] == '(': continue
        try: row,col = reference(value)
        except CellError: continue
        letters_end = 1 if value.startswith('$') else 0
        while letters_end < len(value) and value[letters_end].isalpha(): letters_end += 1
        fixed_col, fixed_row = value.startswith('$'), value[letters_end:].startswith('$')
        row += 0 if fixed_row else rows; col += 0 if fixed_col else cols
        replacement = '#REF!' if not (0<=row<ROWS and 0<=col<COLS) else (
            ('$' if fixed_col else '')+chr(65+col)+('$' if fixed_row else '')+str(row+1))
        output += text[last:start]+replacement; last = end
    return output+text[last:]
