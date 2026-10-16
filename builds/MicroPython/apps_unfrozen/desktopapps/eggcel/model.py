"""Sparse sheet, bounded editing, verified SD documents and plain-data CSV."""
import json
from .formulas import ROWS, COLS, MAX_TEXT, CellError, Evaluation, address, reference, shifted, literal

MAX_CELLS, MAX_CHARS, MAX_FILE = 512, 16384, 49152
DIRECTORY = 'picoware/documents/eggcel'


def format_value(value, style='general'):
    if value is None: return ''
    if isinstance(value,CellError): return value.code
    if isinstance(value,bool): return 'TRUE' if value else 'FALSE'
    if isinstance(value,str): return value
    if style == 'fixed2' and abs(value)<1e10: return '%.2f'%value
    if style == 'scientific': return '%.4e'%value
    return '%.7g'%value


class Sheet:
    def __init__(self):
        self.cells, self.cache, self.widths = {}, {}, {}
        self.dirty, self.style = False, 'general'
        self.undo=None;self.last_errors=0;self.problem=None

    def apply(self, changes):
        # Validate the entire edit before changing the live document.
        cells = dict(self.cells)
        for position,raw in changes.items():
            row,col = position
            if not 0<=row<ROWS or not 0<=col<COLS: raise ValueError('Outside A1:Z200')
            if not isinstance(raw,str) or len(raw)>MAX_TEXT: raise ValueError('Cell limit: 256 characters')
            if '\x00' in raw or '\n' in raw or '\r' in raw: raise ValueError('Cells use a single line')
            if raw: cells[position] = raw
            else: cells.pop(position,None)
        if len(cells)>MAX_CELLS: raise ValueError('Limit: 512 populated cells')
        if sum(len(raw) for raw in cells.values())>MAX_CHARS: raise ValueError('Cell text limit: 16 KiB')
        if cells != self.cells:
            self.undo=(self.cells,self.style,self.dirty)
            self.cells, self.cache, self.dirty = cells, {}, True
            self.problem=None

    def restore(self):
        if self.undo is None:return False
        self.cells,self.style,self.dirty=self.undo;self.cache={};self.undo=None;self.problem=None;return True

    def mark_saved(self):
        self.dirty=False
        if self.undo is not None:self.undo=(self.undo[0],self.undo[1],True)

    def peek(self,position):
        raw=self.cells.get(position,'')
        if raw.startswith('='):return self.cache.get(position,'...')
        try:return literal(raw)
        except CellError as error:return error

    def recalculate_job(self,clear=True):
        if clear:self.cache={}
        self.last_errors=0;self.problem=None
        for index,pos in enumerate(sorted(self.cells)):
            if pos not in self.cache:
                engine=Evaluation(self)
                try:
                    for _ in engine.job(pos):yield index
                except CellError as error:
                    self.cache[pos]=error;self.last_errors+=1
                    if self.problem is None:self.problem=engine.problem or pos
                except Exception:
                    self.problem=engine.problem or pos;raise
            if index%8==0:yield index
        self.last_errors=sum(isinstance(self.cache.get(pos),CellError) for pos in self.cells)

    def fill(self,bounds,direction=None):
        top,left,bottom,right=bounds
        if not (0<=top<=bottom<ROWS and 0<=left<=right<COLS):raise ValueError('Range outside A1:Z200')
        if top==bottom and left==right:raise ValueError('Select more than one cell')
        if (bottom-top+1)*(right-left+1)>512:raise ValueError('Fill up to 512 cells')
        if direction is None:
            if left==right:direction='down'
            elif top==bottom:direction='right'
            else:raise ValueError('Choose Fill down or Fill right')
        if direction not in ('down','right'):raise ValueError('Invalid fill direction')
        changes={}
        for row in range(top,bottom+1):
            for col in range(left,right+1):
                source=(top,col) if direction=='down' else (row,left)
                if source==(row,col):continue
                changes[(row,col)]=shifted(self.cells.get(source,''),row-source[0],col-source[1])
        self.apply(changes);return len(changes)

    def convert_job(self,bounds):
        top,left,bottom,right=bounds
        if not (0<=top<=bottom<ROWS and 0<=left<=right<COLS):raise ValueError('Range outside A1:Z200')
        self.cache={};changes={};digits=9 if 1.0+2.0**-40==1.0 else 17
        positions=[pos for pos,raw in self.cells.items() if top<=pos[0]<=bottom and left<=pos[1]<=right and raw.startswith('=')]
        if not positions:raise ValueError('No formulas in the selection')
        for index,pos in enumerate(sorted(positions)):
            engine=Evaluation(self)
            try:
                for _ in engine.job(pos):yield index
            except CellError as error:
                self.problem=engine.problem or pos
                raise ValueError(address(*pos)+': '+error.code+'; nothing converted')
            except Exception:
                self.problem=engine.problem or pos;raise
            value=engine.result
            if value is None:raw=''
            elif isinstance(value,bool):raw='TRUE' if value else 'FALSE'
            elif isinstance(value,str):raw="'"+value
            else:raw=('%.'+str(digits)+'g')%value
            changes[pos]=raw
            yield index+1
        self.apply(changes)

    def value(self, position):
        try: return Evaluation(self).cell(position)
        except CellError as exc: return exc

    def text(self, position): return format_value(self.value(position),self.style)

    def copied(self, bounds):
        top,left,bottom,right = bounds
        if (bottom-top+1)*(right-left+1)>512: raise ValueError('Copy up to 512 cells at once')
        return (bounds, {(row-top,col-left):self.cells.get((row,col),'')
                        for row in range(top,bottom+1) for col in range(left,right+1)})

    def paste(self, clipboard, position):
        bounds,cells = clipboard
        row,col = position
        if row+bounds[2]-bounds[0]>=ROWS or col+bounds[3]-bounds[1]>=COLS:
            raise ValueError('Paste would leave A1:Z200')
        self.apply({(row+dr,col+dc):shifted(raw,row-bounds[0],col-bounds[1])
                    for (dr,dc),raw in cells.items()})

    def document(self):
        return json.dumps({'eggcel':1,'sheet':'Sheet1','style':self.style,
                           'widths':[[col,width] for col,width in sorted(self.widths.items())],
                           'cells':[[row,col,raw] for (row,col),raw in sorted(self.cells.items())]})

    @classmethod
    def from_document(cls, text):
        if len(text)>MAX_FILE: raise ValueError('Document too large')
        data = json.loads(text)
        if not isinstance(data,dict) or data.get('eggcel')!=1: raise ValueError('Not an Eggcel v1 document')
        entries = data.get('cells')
        if not isinstance(entries,list) or len(entries)>MAX_CELLS: raise ValueError('Invalid cell list')
        changes = {}
        for entry in entries:
            if not isinstance(entry,list) or len(entry)!=3: raise ValueError('Invalid cell record')
            row,col,raw = entry
            if type(row)!=int or type(col)!=int or (row,col) in changes:
                raise ValueError('Invalid/duplicate cell address')
            changes[(row,col)] = raw
        result = cls(); result.apply(changes)
        style = data.get('style','general')
        if style not in ('general','fixed2','scientific'): raise ValueError('Invalid number format')
        widths = data.get('widths',[])
        if not isinstance(widths,list) or len(widths)>COLS: raise ValueError('Invalid column widths')
        for entry in widths:
            if not isinstance(entry,list) or len(entry)!=2: raise ValueError('Invalid column width')
            col,width=entry
            if type(col)!=int or type(width)!=int or not 0<=col<COLS or not 40<=width<=140:
                raise ValueError('Invalid column width')
            result.widths[col] = width
        result.style, result.dirty = style, False
        result.undo=None
        return result

    def csv(self):
        if not self.cells: return ''
        last_row = max(row for row,col in self.cells)
        last_col = max(col for row,col in self.cells)
        lines = []
        for row in range(last_row+1):
            fields = []
            for col in range(last_col+1):
                value = self.value((row,col))
                text = format_value(value,self.style)
                if any(char in text for char in ',"\r\n'): text='"'+text.replace('"','""')+'"'
                fields.append(text)
            lines.append(','.join(fields))
        text = '\r\n'.join(lines)+'\r\n'
        if len(text)>MAX_FILE: raise ValueError('CSV exceeds 48 KiB')
        return text

    @classmethod
    def from_csv(cls,text):
        if len(text)>MAX_FILE: raise ValueError('CSV exceeds 48 KiB')
        result,changes = cls(),{}
        row,col,i,field,quoted,closed = 0,0,0,'',False,False
        while i<=len(text):
            end = i==len(text)
            char = '' if end else text[i]
            if quoted:
                if end: raise ValueError('Unclosed CSV quote')
                if char=='"':
                    if i+1<len(text) and text[i+1]=='"': field+='"';i+=2;continue
                    quoted,closed=False,True
                else: field+=char
            elif char=='"' and not field and not closed: quoted=True
            elif end or char in ',\r\n':
                if row>=ROWS or col>=COLS:
                    if field or not end: raise ValueError('CSV exceeds A1:Z200')
                elif field:
                    # CSV is data: never execute imported formulas. Preserve
                    # literal apostrophes and values beginning with '='.
                    changes[(row,col)] = "'"+field if field.startswith("'") or field.startswith('=') else field
                    if len(changes)>MAX_CELLS: raise ValueError('CSV limit: 512 populated cells')
                field,closed='',False
                if char==',': col+=1
                else:
                    row+=1; col=0
                    if char=='\r' and i+1<len(text) and text[i+1]=='\n': i+=1
                if end: break
            elif closed: raise ValueError('Unexpected text after CSV quote')
            else: field+=char
            if len(field)>MAX_TEXT: raise ValueError('CSV cell limit: 256 characters')
            i+=1
        result.apply(changes); result.dirty=True
        return result


def safe_name(name, extension):
    name = name.strip()
    if name.lower().endswith(extension): name = name[:-len(extension)]
    if not name or len(name)>40 or name.startswith('.') or any(
            not (char.isalpha() or char.isdigit() or char in ' _-.') for char in name):
        raise ValueError('Use 1..40 letters, numbers, spaces, _ or -')
    return name+extension


def write_verified(storage,path,text):
    if len(text.encode('utf-8'))>MAX_FILE: raise ValueError('File exceeds 48 KiB')
    if not storage.active: raise OSError('SD card unavailable')
    storage.mkdir('picoware/documents'); storage.mkdir(DIRECTORY)
    temporary,backup = path+'.tmp',path+'.bak'
    if not storage.write(temporary,text) or storage.read(temporary)!=text:
        raise OSError('Write verification failed; original kept')
    # A failed replacement keeps the prior document or its .bak recovery copy.
    existed=storage.exists(path)
    if existed:
        if storage.exists(backup): raise OSError('Recovery .bak exists; keep it before saving')
        if not storage.rename(path,backup): raise OSError('Cannot back up original')
    if not storage.rename(temporary,path):
        if existed: storage.rename(backup,path)
        raise OSError('Cannot replace document; original kept in file or .bak')
    if existed: storage.remove(backup)


def read_sheet(storage,path,csv=False):
    if not storage.active or not storage.exists(path): raise OSError('File unavailable')
    if storage.size(path)>MAX_FILE: raise ValueError('File exceeds 48 KiB')
    text=storage.read(path)
    if not text and storage.size(path)>0: raise OSError('Could not read file')
    return Sheet.from_csv(text) if csv else Sheet.from_document(text)


def demo():
    result=Sheet()
    rows=[['Part','Qty','Unit','Total'],['Resistor','8','0.25','=B2*C2'],
          ['Capacitor','4','0.85','=B3*C3'],['Sensor','2','3.5','=B4*C4'],
          [],['Total','','','=SUM(D2:D4)'],[],['Average','','','=AVERAGE(D2:D4)'],
          [],['Budget','','','15'],['Remaining','','','=D10-D6'],
          ['Status','','','=IF(D11>=0,"Within","Over")']]
    result.apply({(r,c):text for r,row in enumerate(rows) for c,text in enumerate(row) if text})
    return result
