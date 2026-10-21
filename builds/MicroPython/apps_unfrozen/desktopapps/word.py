"""PicoWord: formatted paragraphs and calculator-style equation insertion."""
from picoware.system import buttons as k
from engtools.calculator.editor import Editor,clone
from .common import FileApp,chunks,FILE_HELP
from .icons import PICOWORD
from .word_model import Document,paragraph,example,MAX_FILE

FONTS=('Extra small / 8 px','Small / 12 px','Medium / 16 px','Large / 20 px','Extra large / 24 px')
TEMPLATES=('pow','sub','sqrt','frac','int','logb','sin','cos','tan','ln','pi')
TEMPLATE_LABELS=('Power','Subscript','Square root','Fraction','Integral','Log with base',
                 'Sine','Cosine','Tangent','Natural log','Pi')


class Word(FileApp):
    title='PicoWord';extension='.pword';export_extension='.txt';directory='picoware/documents/picoword';theme_option=True
    ICON=PICOWORD
    HELP=('Document:','Arrows\tmove the cursor','ENTER\tnew paragraph','BACK / DEL\terase','TAB\tindent',
          'F3\tfont and alignment','F4\ttext colour','F5\tinsert an equation','eq() SPACE\tinsert an equation',
          'F6\tundo','F7 / F8\tpage up / down','ESC\tclose; asks to save changes',
          'Equation:','LEFT/RIGHT\tmove','UP/DOWN\tmove between levels','TAB\tnext slot',
          'CTRL+UP\tprevious slot','SPACE\texpand 2^, sqrt(), /, int()','F3 / F4\tfont / colour',
          'F7\tmath symbols','ENTER\tplace the equation','ESC\tcancel the equation')+FILE_HELP
    def __init__(self):super().__init__();self.reset_cursor()
    def fresh(self):return Document()
    def example(self):return example()
    def reset_cursor(self):
        self.block,self.index,self.scroll=0,0,0
        self.eq=None;self.eq_origin=None;self.eq_style=None;self.goal_x=None
    def encode(self,export):return chunks(self.model.plain() if export else self.model.document())
    def load(self,path):
        if self.vm.storage.size(path)>MAX_FILE:raise ValueError('Document exceeds 48 KiB')
        text=self.vm.storage.read(path)
        if not isinstance(text,str):raise OSError('Cannot read document; original kept')
        return Document.parse(text)
    def style(self):return self.eq_style if self.eq is not None else self.model.blocks[self.block]
    def rows(self):
        if self.page=='font':return FONTS+('Align left','Align centre','Align right')
        if self.page=='math':return TEMPLATE_LABELS
        return super().rows()
    def choose(self):
        if self.page in ('font','color','math'):
            if self.page=='math':
                kind=TEMPLATES[self.selected]
                if kind in ('pow','sub') and self.eq.index==0:raise ValueError('Enter a base first')
                self.eq.template(kind)
            else:
                style=dict(self.style())
                if self.page=='font':
                    if self.selected<5:style['font']=self.selected
                    else:style['align']=self.selected-5
                else:style['color']=self.palette()[self.selected][1]
                if self.eq is not None:self.eq_style=style
                else:self.model.set_block(self.block,style)
            self.page=self.return_page
        else:super().choose()
    def change_text(self,text):
        block=dict(self.model.blocks[self.block]);block['text']=text;self.model.set_block(self.block,block)
    def start_equation(self,shorthand=False):
        current=self.model.blocks[self.block]
        self.eq=Editor();self.eq_style=dict(current)
        if current['type']=='equation':self.eq.load(current['row']);self.eq_origin=(self.block,None,None)
        else:self.eq_origin=(self.block,self.index-4 if shorthand else self.index,self.index)
        self.page='equation'
    def commit_equation(self):
        if not self.eq.root:raise ValueError('Enter an equation or ESC cancels')
        if self.eq.focus_missing():raise ValueError('Complete the highlighted slot')
        index,lo,hi=self.eq_origin
        equation={'type':'equation','row':clone(self.eq.root),'font':self.eq_style['font'],
                  'color':self.eq_style['color'],'align':self.eq_style['align']}
        blocks=list(self.model.blocks)
        current=blocks[index]
        if lo is None:
            blocks[index]=equation
            if index+1>=len(blocks) or blocks[index+1]['type']!='text':blocks.insert(index+1,paragraph())
            target=index+1
        else:
            prefix,suffix=current['text'][:lo],current['text'][hi:]
            replacement=[]
            if prefix:
                before=dict(current);before['text']=prefix;replacement.append(before)
            replacement.append(equation)
            after=dict(current);after['text']=suffix;replacement.append(after)
            blocks[index:index+1]=replacement;target=index+len(replacement)-1
        self.model.apply(blocks)
        self.block,self.index,self.page=target,0,'edit';self.eq=None;self.eq_origin=None;self.eq_style=None
    def layout(self):
        width=int(self.vm.draw.size.x)-36;r=self.renderer();lines=[];y=0
        for index,block in enumerate(self.model.blocks):
            font=block['font'];cw,ch=r.metrics[font]
            if block['type']=='equation':
                box=r.layout(block['row'],font)
                while box.w>width and font>0:font-=1;box=r.layout(block['row'],font)
                x=18 if block['align']==0 else 18+max(0,width-box.w)//(2 if block['align']==1 else 1)
                lines.append((index,0,0,y,max(24,box.h+8),x,font));y+=max(24,box.h+8)+5
                continue
            text=block['text'];start=0;capacity=max(1,width//cw)
            while True:
                end=min(len(text),start+capacity)
                if end<len(text):
                    space=text.rfind(' ',start,end)
                    if space>start:end=space+1
                pixels=(end-start)*cw
                x=18 if block['align']==0 else 18+max(0,width-pixels)//(2 if block['align']==1 else 1)
                lines.append((index,start,end,y,ch+3,x,font));y+=ch+3
                if end>=len(text):break
                start=end
            y+=5
        return lines
    def caret_line(self,lines):
        matches=[i for i,line in enumerate(lines) if line[0]==self.block and line[1]<=self.index<=line[2]]
        return matches[-1] if matches else next(i for i,line in enumerate(lines) if line[0]==self.block)
    def vertical(self,direction,amount=1):
        lines=self.layout();index=self.caret_line(lines);current=lines[index]
        if self.goal_x is None:self.goal_x=current[5]+(self.index-current[1])*self.renderer().metrics[current[6]][0]
        target=lines[max(0,min(len(lines)-1,index+direction*amount))]
        self.block=target[0]
        self.index=max(target[1],min(target[2],target[1]+int((self.goal_x-target[5])/self.renderer().metrics[target[6]][0])))
    def math_input(self,button):
        if button==self.vm.input_manager._key_esc:self.eq=None;self.eq_origin=None;self.eq_style=None;self.page='edit'
        elif button==k.BUTTON_CENTER:self.commit_equation()
        elif button==k.BUTTON_F3:self.menu('font',self.eq_style['font'],'equation')
        elif button==k.BUTTON_F4:self.menu('color',0,'equation')
        elif button==k.BUTTON_F7:self.menu('math',0,'equation')
        elif button==k.BUTTON_LEFT:self.eq.move(-1)
        elif button==k.BUTTON_RIGHT:self.eq.move(1)
        elif button in (k.BUTTON_UP,k.BUTTON_DOWN):self.eq.vertical(-1 if button==k.BUTTON_UP else 1)
        elif button in (k.BUTTON_TAB,k.BUTTON_CTRL_DOWN):self.eq.tab()
        elif button==k.BUTTON_CTRL_UP:self.eq.tab(True)
        elif button in (k.BUTTON_BACKSPACE,self.vm.input_manager._key_back):self.eq.delete()
        elif button==k.BUTTON_DELETE:self.eq.delete(True)
        else:
            char=self.vm.input_manager.button_to_char(button)
            if char and char not in ('\n','\r','\t'):
                if char==' ':
                    if not self.eq.expand():self.eq.insert(' ')
                else:self.eq.insert(char)
    def input(self,button):
        self.message=''
        if self.page=='equation':self.math_input(button);return
        current=self.model.blocks[self.block]
        if button==self.vm.input_manager._key_esc:self.guard('quit');return
        if button==k.BUTTON_F3:self.menu('font',current['font']);return
        if button==k.BUTTON_F4:self.menu('color');return
        if button==k.BUTTON_F5:self.start_equation();return
        if button==k.BUTTON_F6:
            self.model.restore();self.block=min(self.block,len(self.model.blocks)-1)
            self.index=min(self.index,len(self.model.blocks[self.block].get('text','')));return
        if button in (k.BUTTON_UP,k.BUTTON_DOWN,k.BUTTON_F7,k.BUTTON_F8):
            self.vertical(-1 if button in (k.BUTTON_UP,k.BUTTON_F7) else 1,8 if button in (k.BUTTON_F7,k.BUTTON_F8) else 1);return
        self.goal_x=None
        text=current.get('text','')
        if button==k.BUTTON_LEFT:
            if self.index:self.index-=1
            elif self.block:self.block-=1;self.index=len(self.model.blocks[self.block].get('text',''))
        elif button==k.BUTTON_RIGHT:
            if self.index<len(text):self.index+=1
            elif self.block<len(self.model.blocks)-1:self.block+=1;self.index=0
        elif button==k.BUTTON_CENTER:
            if current['type']=='equation':self.start_equation()
            else:
                before,after=dict(current),dict(current);before['text'],after['text']=text[:self.index],text[self.index:]
                blocks=list(self.model.blocks);blocks[self.block:self.block+1]=[before,after];self.model.apply(blocks)
                self.block+=1;self.index=0
        elif button in (k.BUTTON_BACKSPACE,self.vm.input_manager._key_back,k.BUTTON_DELETE):
            if current['type']=='equation':
                blocks=list(self.model.blocks);blocks.pop(self.block);self.model.apply(blocks or [paragraph()])
                self.block=min(self.block,len(self.model.blocks)-1);self.index=0
            elif button==k.BUTTON_DELETE:
                if self.index<len(text):self.change_text(text[:self.index]+text[self.index+1:])
                elif self.block+1<len(self.model.blocks) and self.model.blocks[self.block+1]['type']=='text':
                    block=dict(current);block['text']=text+self.model.blocks[self.block+1]['text']
                    blocks=list(self.model.blocks);blocks[self.block:self.block+2]=[block];self.model.apply(blocks)
            elif self.index:self.change_text(text[:self.index-1]+text[self.index:]);self.index-=1
            elif self.block and self.model.blocks[self.block-1]['type']=='text':
                previous=dict(self.model.blocks[self.block-1]);self.index=len(previous['text']);previous['text']+=text
                blocks=list(self.model.blocks);blocks[self.block-1:self.block+1]=[previous];self.model.apply(blocks);self.block-=1
        else:
            char='    ' if button==k.BUTTON_TAB else self.vm.input_manager.button_to_char(button)
            if char and char not in ('\n','\r'):
                if char==' ' and text[max(0,self.index-4):self.index]=='eq()' and (self.index==4 or not text[self.index-5].isalpha()):
                    self.start_equation(True);return
                if current['type']=='equation':
                    blocks=list(self.model.blocks);blocks.insert(self.block+1,paragraph());self.model.apply(blocks)
                    self.block+=1;self.index=0;text=''
                self.change_text(text[:self.index]+char+text[self.index:]);self.index+=len(char)
    def draw_document(self,r,p,w,h):
        if self.page=='equation':
            r.text(9,42,'EQUATION / ENTER sets, ESC cancels',p.ACCENT,0)
            r.rect(8,63,w-16,145,p.GRID)
            er=self.renderer((15,70,w-15,201));style=self.eq_style
            er.expression(self.eq.root,19,83,max(1,style['font']),p.TEXT if style['color'] is None else style['color'],editor=self.eq,follow=True)
            r.text(10,223,self.eq.hint()[:50],p.MUTED,0);return
        lines=self.layout();caret=lines[self.caret_line(lines)]
        viewport=self.bottom-75
        self.scroll=min(self.scroll,caret[3])
        if caret[3]+caret[4]>self.scroll+viewport:self.scroll=caret[3]+caret[4]-viewport
        style=self.model.blocks[self.block]
        r.text(9,41,'FONT '+str(style['font']+1)+' | '+('THEME' if style['color'] is None else 'COLOUR')+' | '+('LEFT','CENTRE','RIGHT')[style['align']],p.MUTED,0)
        r.rect(7,56,w-14,self.bottom-71,p.GRID)
        content=self.renderer((16,61,w-16,self.bottom-16))
        for block,start,end,y,height,x,font in lines:
            screen_y=62+y-self.scroll
            if screen_y+height<61 or screen_y>=self.bottom-16:continue
            record=self.model.blocks[block];color=p.TEXT if record['color'] is None else record['color']
            if record['type']=='text':content.text(x,screen_y,record['text'][start:end],color,font)
            else:content.expression(record['row'],x,screen_y+4,font,color)
        y=62+caret[3]-self.scroll;x=caret[5]+(self.index-caret[1])*content.metrics[caret[6]][0]
        if style['type']=='text':content.line(x,y,x,y+content.metrics[caret[6]][1],p.ACCENT)
        else:content.rect(16,y,w-32,caret[4],p.ACCENT)
        r.text(9,self.bottom-11,'Block %d/%d | %d characters'%(self.block+1,len(self.model.blocks),sum(len(b.get('text','')) for b in self.model.blocks)),p.MUTED,0)
