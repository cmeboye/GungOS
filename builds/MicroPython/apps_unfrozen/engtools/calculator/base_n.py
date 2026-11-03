"""Fixed-width integer parser; no floating arithmetic or Python eval."""
RADICES=(2,8,10,16)
LABELS=('BIN','OCT','DEC','HEX')

def normalize(value,bits=32,signed=True):
    if bits not in (8,16,32): raise ValueError('Word width: 8, 16 or 32 bits')
    value=int(value)&((1<<bits)-1)
    return value-(1<<bits) if signed and value&(1<<(bits-1)) else value

def display(value,base,bits=32,signed=True):
    value=normalize(value,bits,signed)
    if base==10: return str(value)
    if base not in RADICES: raise ValueError('Unsupported base')
    unsigned=value&((1<<bits)-1)
    digits='0123456789ABCDEF'
    result=''
    while unsigned:
        result=digits[unsigned%base]+result; unsigned//=base
    return result or '0'

class IntegerParser:
    def __init__(self,text,variables=None,base=10,bits=32,signed=True):
        if base not in RADICES or bits not in (8,16,32): raise ValueError('Invalid Base-N configuration')
        if len(text)>512: raise ValueError('Base-N expression is too long')
        self.base,self.bits,self.signed=base,bits,signed
        self.variables,self.items,self.index,self.depth={} if variables is None else variables,[],0,0
        i=0
        while i<len(text):
            ch=text[i]
            if ch.isspace(): i+=1; continue
            if text[i:i+2] in ('<<','>>'):
                self.items.append(text[i:i+2]); i+=2; continue
            if ch in '+-*/%()&|^~=':
                self.items.append(ch); i+=1; continue
            if ch.isalpha() or ch.isdigit() or ch=='_':
                start=i
                while i<len(text) and (text[i].isalpha() or text[i].isdigit() or text[i]=='_'): i+=1
                word=text[start:i]
                operator={'AND':'&','OR':'|','XOR':'^','NOT':'~'}.get(word.upper())
                if operator: self.items.append(operator); continue
                self.items.append(word)
                continue
            raise ValueError('Base-N accepts integers and bitwise operators')
        if len(self.items)>192: raise ValueError('Too many Base-N terms')
        self.items.append('END')

    def word(self,value): return normalize(value,self.bits,self.signed)
    def take(self):
        value=self.items[self.index]; self.index+=1; return value
    def peek(self): return self.items[self.index]
    def literal(self,word):
        if word in self.variables or word.lower()=='ans':
            value=self.variables.get('Ans',0) if word.lower()=='ans' else self.variables[word]
            if isinstance(value,complex) or value!=int(value): raise ValueError('Variable must be an integer')
            return self.word(value)
        radix=self.base
        if word[:2].lower() in ('0x','0o','0b'):
            radix={'0x':16,'0o':8,'0b':2}[word[:2].lower()]; word=word[2:]
        if not word or len(word)>64: raise ValueError('Invalid or oversized integer literal')
        try: value=int(word,radix)
        except ValueError: raise ValueError('Invalid digit or unknown variable')
        return self.word(value)
    def expression(self,minimum=0):
        self.depth+=1
        if self.depth>24: raise ValueError('Base-N nesting limit')
        token=self.take()
        if token in ('-','+','~'):
            value=self.expression(70)
            value=-value if token=='-' else (~value if token=='~' else value)
        elif token=='(':
            value=self.expression()
            if self.take()!=')': raise ValueError('Missing closing parenthesis')
        elif token in ('END',')','=','&','|','^','*','/','%','<<','>>'):
            raise ValueError('Expected an integer')
        else: value=self.literal(token)
        value=self.word(value)
        while True:
            op=self.peek()
            precedence={'|':10,'^':20,'&':30,'<<':40,'>>':40,'+':50,'-':50,'*':60,'/':60,'%':60}.get(op,-1)
            if precedence<minimum: break
            self.take(); right=self.expression(precedence+1)
            if op=='+': value+=right
            elif op=='-': value-=right
            elif op=='*': value*=right
            elif op in ('/','%'):
                if right==0: raise ZeroDivisionError('Division by zero')
                quotient=abs(value)//abs(right)
                if (value<0)!=(right<0): quotient=-quotient
                value=quotient if op=='/' else value-quotient*right
            elif op in ('<<','>>'):
                if not 0<=right<self.bits: raise ValueError('Shift count must be 0..word width-1')
                value=value<<right if op=='<<' else value>>right
            elif op=='&': value&=right
            elif op=='|': value|=right
            else: value^=right
            value=self.word(value)
        self.depth-=1
        return value
    def calculate(self):
        name=None
        if len(self.items)>2 and self.items[1]=='=':
            name=self.take(); self.take()
            if len(name)>16 or not name[0].isalpha() or not all(c.isalpha() or c.isdigit() or c=='_' for c in name) or name.lower()=='ans':
                raise ValueError('Invalid assignment name')
            from .evaluate import RESERVED
            if name in RESERVED: raise ValueError('This name is reserved')
            if self.base==16 and all(c.upper() in 'ABCDEF0123456789' for c in name):
                raise ValueError('Use a name distinguishable from hex digits')
        value=self.expression()
        if self.peek()!='END': raise ValueError('Unexpected Base-N input')
        if name and name not in self.variables and len(self.variables)>=25: raise ValueError('Variable limit')
        if name: self.variables[name]=value
        self.variables['Ans']=value
        return value,name
