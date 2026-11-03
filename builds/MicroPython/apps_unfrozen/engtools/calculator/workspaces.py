"""Solver, integer-base and small-matrix calculator workspaces."""
from picoware.system import buttons as k
from picoware.system.font import FONT_XTRA_SMALL as TINY,FONT_SMALL as SMALL
from engtools.ui import theme
from .editor import Editor,source,clone
from .evaluate import calculate,format_value,finite,Parser,Evaluator,FUNCTIONS


class Workspace:
    def __init__(self,calculator):
        self.calc=calculator
        self.editor=Editor()
        self.editing=False
        self.selected=0
        self.page='start'

    def scalar(self,text):
        value,name=calculate(text,dict(self.calc.variables),self.calc.angle)
        if name or isinstance(value,complex) or not finite(value): raise ValueError('Enter a finite real expression')
        return value

    def common(self,button):
        if button in (k.BUTTON_F1,k.BUTTON_F2,k.BUTTON_F4):return True
        if button==k.BUTTON_F8 and self.editing:
            self.calc.open_page('variables'); return True
        if button==k.BUTTON_F7 and self.editing:
            self.calc.open_page('templates'); return True
        return False

    def begin(self,text):
        self.editor.load(list(str(text)))
        self.editing=True
        self.calc.error=''

    def entry(self,button,commit):
        if button==self.calc.vm.input_manager._key_esc:
            self.editing=False; self.calc.error=''; return
        if button in (k.BUTTON_CENTER,k.BUTTON_F6):
            if self.editor.focus_missing(): raise ValueError('Complete the highlighted slot')
            commit(source(self.editor.root))
            self.editing=False; self.calc.error=''
        elif button==k.BUTTON_F10: self.editor.clear()
        else: self.calc.edit_key(self.editor,button)

    def chrome(self,draw,title,hint):
        width,height=int(draw.size.x),int(draw.size.y)
        draw.fill_screen(self.calc.palette.BG)
        r=self.calc.renderer(draw,(0,18,width,height))
        r.fill(0,18,width,24,self.calc.palette.PANEL)
        r.text(9,25,title,self.calc.accent,SMALL)
        self.calc.footer(r,width,height,hint,'F3 Options F8 Vars F9 Help ESC returns')
        return r,width,height

    def input(self,draw,width,height):
        bottom=height-self.calc.footer_height
        top=height-110
        r=self.calc.renderer(draw,(8,top,width-8,bottom-4))
        r.rect(8,top,width-16,bottom-top-6,self.calc.accent)
        r.text(14,top+5,'>>',self.calc.accent,TINY)
        prompt=self.calc.renderer(draw,(34,top+4,width-15,bottom-10))
        prompt.expression(self.editor.root,36,top+11,SMALL,editor=self.editor,follow=True)

    def rows(self,r,rows,selected,width,height):
        capacity=max(1,((height-114 if self.editing else height-self.calc.footer_height-8)-50)//24)
        first=max(0,selected-capacity+1)
        for i in range(first,min(len(rows),first+capacity)):
            y=51+(i-first)*24
            if i==selected: r.fill(7,y-3,width-14,23,self.calc.palette.SELECT)
            label,value=rows[i]
            r.text(13,y,label[:(width-24)//8],self.calc.palette.TEXT,SMALL)
            r.text(13,y+12,str(value)[:(width-24)//6],self.calc.palette.MUTED,TINY)

    def sheet(self,r,values,labels,width):
        columns=len(labels); cw=(width-30)//columns
        for col,label in enumerate(labels): r.text(28+col*cw,49,label,self.calc.accent,TINY)
        for row,values_row in enumerate(values):
            y=70+row*30
            r.text(8,y+5,str(row+1),self.calc.palette.MUTED,TINY)
            for col,value in enumerate(values_row):
                x=24+col*cw
                if self.selected==row*columns+col: r.fill(x,y-2,cw-2,28,self.calc.palette.SELECT)
                text=format_value(value)
                if len(text)>(cw-6)//6: text='%.2g'%value
                r.text(x+3,y+7,text[:(cw-6)//6],self.calc.palette.TEXT,TINY)


class BaseWorkspace(Workspace):
    def __init__(self,calculator):
        super().__init__(calculator)
        self.base,self.bits,self.signed=10,32,True
        self.value,self.page,self.editing=0,'entry',True
    def run(self,button):
        from .base_n import IntegerParser,RADICES
        if button==k.BUTTON_F7:
            self.page,self.selected='operators',0; return
        if self.common(button): return
        if button==self.calc.vm.input_manager._key_esc:
            if self.page!='entry': self.page='entry'
            else: self.calc.vm.back()
            return
        if button==k.BUTTON_F3: self.page='settings'; self.selected=0; return
        if self.page=='operators':
            operators=(' AND ',' OR ',' XOR ',' NOT ',' << ',' >> ')
            if button in (k.BUTTON_UP,k.BUTTON_DOWN): self.selected=(self.selected+(-1 if button==k.BUTTON_UP else 1))%6
            elif button==k.BUTTON_CENTER:
                for char in operators[self.selected]: self.editor.insert(char)
                self.page='entry'
            return
        if self.page=='settings':
            if button in (k.BUTTON_UP,k.BUTTON_DOWN): self.selected=(self.selected+(-1 if button==k.BUTTON_UP else 1))%3
            elif button in (k.BUTTON_CENTER,k.BUTTON_LEFT,k.BUTTON_RIGHT):
                direction=-1 if button==k.BUTTON_LEFT else 1
                if self.selected==0: self.base=RADICES[(RADICES.index(self.base)+direction)%4]
                elif self.selected==1: self.bits=(8,16,32)[((8,16,32).index(self.bits)+direction)%3]
                else: self.signed=not self.signed
            return
        if button in (k.BUTTON_CENTER,k.BUTTON_F6):
            text=source(self.editor.root)
            if not text.strip(): return
            self.value,name=IntegerParser(text,self.calc.variables,self.base,self.bits,self.signed).calculate()
            self.calc.answer,self.calc.assignment=self.value,name
            self.editor.clear(); self.calc.error=''
        elif button==k.BUTTON_F10: self.editor.clear(); self.calc.error=''
        else: self.calc.edit_key(self.editor,button)
    def draw(self,draw,width,height):
        from .base_n import display,LABELS,RADICES
        r,_,_=self.chrome(draw,'BASE-N / %d-bit %s'%(self.bits,'signed' if self.signed else 'unsigned'),'F3 Options  F10 Clear  F7 Ops  ENTER =')
        if self.page=='operators':
            rows=tuple(zip(('AND','OR','XOR','NOT','<<','>>'),('Bitwise and','Bitwise or','Bitwise xor','Bitwise complement','Shift left','Shift right')))
            editing=self.editing; self.editing=False
            self.rows(r,rows,self.selected,width,height); self.editing=editing
        elif self.page=='settings':
            rows=(('Input base',LABELS[RADICES.index(self.base)]),('Word width',str(self.bits)+' bits'),('Interpretation','Signed' if self.signed else 'Unsigned'))
            editing=self.editing; self.editing=False
            self.rows(r,rows,self.selected,width,height); self.editing=editing
            if self.calc.show_hints:
                r.text(12,149,'ENTER/L/R changes; ESC returns',self.calc.palette.MUTED,TINY)
                r.text(12,168,'Wraps modulo 2^width; division truncates',self.calc.palette.MUTED,TINY)
                r.text(12,187,'Operators: AND OR XOR NOT, << >>',self.calc.palette.MUTED,TINY)
        else:
            for i,base in enumerate(RADICES):
                y=51+i*29
                if base==self.base: r.fill(7,y-3,width-14,27,self.calc.palette.SELECT)
                r.text(12,y,LABELS[i],self.calc.accent,TINY)
                r.text(45,y+3,display(self.value,base,self.bits,self.signed),self.calc.palette.TEXT,TINY)
            if self.calc.show_hints:
                r.text(12,170,'0x / 0o / 0b prefixes override input base',self.calc.palette.MUTED,TINY)
            self.input(draw,width,height)
        draw.swap()


class SolverWorkspace(Workspace):
    def __init__(self,calculator):
        super().__init__(calculator)
        self.degree,self.size=2,2
        self.expression='x^2=2'
        self.bounds=[-10.0,10.0,1.0]
        self.coefficients=[1.0,0.0,-2.0]
        self.system=[[1.0,0.0,1.0],[0.0,1.0,2.0]]
        self.results=[]
        self.job=None
        self.progress=0
        self.return_page='start'
    def tick(self):
        if self.job is None: return
        try:
            record=next(self.job)
            if 'root' in record:
                value=record['root']
                self.results=[('x',format_value(value)),('Residual',format_value(record['residual'])),('Iterations',str(record['iterations']))]
            elif 'roots' in record:
                roots=[v.real if v.imag==0 else v for v in record['roots']]
                value=roots[0]
                self.results=[('x'+str(i+1),format_value(v)) for i,v in enumerate(roots)]
                self.results.append(('Numerical roots','Approximate for stored coefficients'))
                for warning in record.get('warnings',[]):self.results.append(('Conditioning',warning))
                if any(n>1 for n in record.get('multiplicities',[])):
                    self.results.append(('Multiplicity',' '.join(str(n) for n in record['multiplicities'])))
            else:
                self.progress=record.get('progress',0); return
            self.calc.answer=value; self.calc.variables['Ans']=value
            self.job.close(); self.job=None
            self.return_page,self.page=self.page,'results'; self.selected=0
        except StopIteration: self.job=None
        except Exception as exc:
            self.job=None; self.calc.error=str(exc)
        self.calc.dirty=True
    def solve(self):
        from engtools.numerics.equations import root_job,polynomial_job
        self.calc.error=''
        if self.page=='equation':
            self.job=root_job(self.expression,*self.bounds,variables=self.calc.variables,angle=self.calc.angle)
        elif self.page=='polynomial': self.job=polynomial_job(self.coefficients)
        else:
            from engtools.numerics.matrices import matrix,solve
            a=matrix([row[:-1] for row in self.system]); b=matrix([[row[-1]] for row in self.system])
            solution=solve(a,b)
            self.results=[('xyzw'[i],format_value(solution[i,0])) for i in range(self.size)]
            self.calc.answer=solution[0,0]; self.calc.variables['Ans']=self.calc.answer
            self.return_page,self.page='system','results'; self.selected=0
        self.progress=0
    def commit(self,text):
        if self.page=='equation':
            if self.selected==0:
                from engtools.numerics.equations import equation
                equation(text,self.calc.variables,self.calc.angle)
                self.expression=text
            else: self.bounds[self.selected-1]=self.scalar(text)
        elif self.page=='polynomial': self.coefficients[self.selected]=self.scalar(text)
        else:
            row,col=divmod(self.selected,self.size+1)
            self.system[row][col]=self.scalar(text)
    def run(self,button):
        if self.job:
            if button==self.calc.vm.input_manager._key_esc:
                self.job.close(); self.job=None; self.calc.error='Cancelled'
            return
        if self.common(button): return
        if button==k.BUTTON_F5 and not self.editing:
            if self.results and self.page!='results':self.return_page=self.page;self.page='results';self.selected=0
            return
        if self.editing: self.entry(button,self.commit); return
        if button==k.BUTTON_F6 and self.page not in ('start',):
            if self.page=='results':self.page=self.return_page
            self.solve();return
        if button==self.calc.vm.input_manager._key_esc:
            if self.page=='results': self.page=self.return_page; self.selected=0
            elif self.page!='start': self.page='start'; self.selected=0
            else: self.calc.vm.back()
            return
        if self.page=='start':
            if button in (k.BUTTON_UP,k.BUTTON_DOWN): self.selected=(self.selected+(-1 if button==k.BUTTON_UP else 1))%3
            elif button==k.BUTTON_CENTER: self.page=('equation','polynomial','system')[self.selected]; self.selected=0
        elif self.page=='results':
            if button in (k.BUTTON_UP,k.BUTTON_DOWN): self.selected=(self.selected+(-1 if button==k.BUTTON_UP else 1))%len(self.results)
        elif button==k.BUTTON_F6: self.solve()
        elif button==k.BUTTON_F3 and self.page in ('polynomial','system'):
            if self.page=='polynomial':
                self.degree=2+(self.degree-1)%3
                self.coefficients=[1.0]+[0.0]*(self.degree-1)+[-2.0]
            else:
                old=self.system; old_size=self.size
                self.size=2+(self.size-1)%3
                self.system=[[old[i][j] if i<old_size and j<old_size else (1.0 if i==j else 0.0) for j in range(self.size)]+[old[i][-1] if i<old_size else 0.0] for i in range(self.size)]
            self.selected=0
        elif self.page=='system':
            row,col=divmod(self.selected,self.size+1)
            if button==k.BUTTON_LEFT: col=(col-1)%(self.size+1)
            elif button==k.BUTTON_RIGHT: col=(col+1)%(self.size+1)
            elif button==k.BUTTON_UP: row=(row-1)%self.size
            elif button==k.BUTTON_DOWN: row=(row+1)%self.size
            elif button==k.BUTTON_CENTER: self.begin(format_value(self.system[row][col]))
            self.selected=row*(self.size+1)+col
        else:
            values=[self.expression]+self.bounds if self.page=='equation' else self.coefficients
            if button in (k.BUTTON_UP,k.BUTTON_DOWN): self.selected=(self.selected+(-1 if button==k.BUTTON_UP else 1))%len(values)
            elif button==k.BUTTON_CENTER: self.begin(values[self.selected])
    def draw(self,draw,width,height):
        title='SOLVER / '+self.page.upper()
        r,_,_=self.chrome(draw,title,'ENTER edit  F6 Solve  Options: degree/size')
        if self.page=='start': rows=(('Equation in x','General form, bounded numerical root'),('Polynomial','Degree 2..4; real or complex roots'),('Linear system','2..4 unknowns; native QR solve'))
        elif self.page=='results': rows=self.results
        elif self.page=='equation': rows=[('Equation',self.expression)]+list(zip(('Lower bound','Upper bound','Initial guess'),(format_value(v) for v in self.bounds)))
        elif self.page=='polynomial': rows=[('a%d (x^%d)'%(self.degree-i,self.degree-i),format_value(v)) for i,v in enumerate(self.coefficients)]
        else:
            rows=None
            self.sheet(r,self.system,list('xyzw'[:self.size])+['RHS'],width)
            row,col=divmod(self.selected,self.size+1)
            r.text(12,191,'Equation %d, %s = %s'%(row+1,'xyzw'[col] if col<self.size else 'RHS',format_value(self.system[row][col])),self.calc.palette.MUTED,TINY)
        if rows is not None: self.rows(r,rows,self.selected,width,height)
        if self.editing: self.input(draw,width,height)
        if self.job: r.text(12,height-62,'Solving... %d iterations; ESC cancels'%self.progress,self.calc.accent,TINY)
        draw.swap()


class MatrixWorkspace(Workspace):
    NAMES=('MatA','MatB','MatC','MatD')
    def __init__(self,calculator):
        super().__init__(calculator)
        self.matrices={}
        self.result=None
        self.name='MatA'
        self.rows_count,self.columns=2,2
        self.page='entry'; self.editing=True
        self.field='expression'
        self.result_scroll=0
        self.expression_draft=None
    def return_entry(self):
        self.page,self.editing,self.field='entry',True,'expression'
        self.editor.load(self.expression_draft or [])
        self.expression_draft=None
    def is_matrix(self,value):
        from engtools.numerics.backend import require
        return isinstance(value,require()[0].ndarray)
    def evaluate(self,text):
        from engtools.numerics.backend import require
        from engtools.numerics import matrices as m
        np,_=require()
        parser=Parser(text,FUNCTIONS+('det','inv','trn','transpose','trace','identity'))
        name,node=parser.parse()
        if name and name not in self.NAMES: raise ValueError('Assign only MatA, MatB, MatC or MatD')
        workspace=self
        dataset=self.calc.statistics.dataset if self.calc.statistics else None
        functions=('det','inv','trn','transpose','trace','identity')
        def contains_matrix(node):
            if node[0]=='name':return node[1] in workspace.NAMES+('MatAns',)
            if node[0]=='binary':return contains_matrix(node[2]) or contains_matrix(node[3])
            if node[0]=='call':return node[1] in functions or any(contains_matrix(arg) for arg in node[2])
            if node[0]=='unary':return contains_matrix(node[2])
            if node[0]=='factorial':return contains_matrix(node[1])
            return False
        class MatrixEvaluator(Evaluator):
            def matrix_charge(self,expensive=True):
                self.charge()
                if expensive:self.matrix_steps+=1
                if self.matrix_steps>512:raise ValueError('Matrix operation limit: 512')
            def series(self,function,args,local):
                if len(args)==4 and args[0][0]=='name' and args[0][1] in workspace.NAMES+('MatAns',)+functions:
                    raise ValueError('Sum/product index is reserved in Matrix mode')
                return super().series(function,args,local)
            def reduction(self,function,values):
                def terms():
                    for value in values:
                        if workspace.is_matrix(value):raise ValueError('Sum/product terms must be scalars')
                        yield value
                return super().reduction(function,terms())
            def run(self,node,local=None):
                # Dispatch through one evaluator, including every binder's body.
                # Scalar subtrees keep their original local k/x and shared budget.
                if not contains_matrix(node):return super().run(node,local)
                kind=node[0]
                if kind=='name':
                    self.charge();key=node[1]
                    if key in workspace.NAMES:
                        if key not in workspace.matrices:raise ValueError('Define '+key+' first (F3)')
                        return workspace.matrices[key]
                    if workspace.result is None:raise ValueError('No matrix answer yet')
                    return workspace.result
                if kind=='unary':
                    value=self.run(node[2],local)
                    if workspace.is_matrix(value):
                        self.matrix_charge();return m.validate(-value if node[1]=='-' else value)
                    return super().run(('unary',node[1],('value',value)),local)
                if kind=='binary':
                    a,b=self.run(node[2],local),self.run(node[3],local);op=node[1]
                    am,bm=workspace.is_matrix(a),workspace.is_matrix(b)
                    if not am and not bm:return super().run(('binary',op,('value',a),('value',b)),local)
                    self.matrix_charge()
                    if op in ('+','-'):
                        if not am or not bm or a.shape!=b.shape:raise ValueError('Add/subtract equally sized matrices')
                        value=a+b if op=='+' else a-b
                    elif op=='*':
                        if am and bm:
                            if a.shape[1]!=b.shape[0]:raise ValueError('Matrix product dimensions do not match')
                            value=np.dot(a,b)
                        else:value=a*b
                    elif op=='/':
                        if bm:raise ValueError('Use inv(MatB) for matrix division')
                        if b==0:raise ZeroDivisionError('Division by zero')
                        value=a/b
                    elif op=='^':
                        if not am or bm:raise ValueError('Use MatA^integer')
                        value=m.power(a,b)
                    else:raise ValueError('Unsupported matrix operator')
                    return m.validate(value)
                if kind=='call':
                    function,args=node[1],node[2]
                    if function in ('sum','prod','int'):return super().run(node,local)
                    if function in functions:
                        if len(args)!=1:raise ValueError(function+' takes one argument')
                        value=self.run(args[0],local);self.matrix_charge(function!='trace')
                        if function=='identity':
                            if workspace.is_matrix(value):raise ValueError('Identity size must be a scalar')
                            return m.identity(value)
                        m.validate(value)
                        if function=='det':return m.determinant(value)
                        if function=='inv':return m.inverse(value)
                        if function=='trace':return sum(value[i,i] for i in range(m.square(value)))
                        return np.array(value.transpose())
                    values=[self.run(arg,local) for arg in args]
                    if any(workspace.is_matrix(value) for value in values):raise ValueError('Use matrix-specific functions for matrix arguments')
                    return super().run(('call',function,[('value',value) for value in values]),local)
                if kind=='factorial':
                    value=self.run(node[1],local)
                    if workspace.is_matrix(value):raise ValueError('Factorial requires a scalar')
                    return super().run(('factorial',('value',value)),local)
                return super().run(node,local)
        self.calc.calculation_info=[];self.calc.notice=''
        evaluator=MatrixEvaluator(self.calc.variables,self.calc.angle,statistics=dataset,
                                  diagnostics=self.calc.calculation_info,progress=self.calc.calculation_progress)
        evaluator.matrix_steps=0
        value=evaluator.run(node)
        self.calc.calculation_done()
        if self.is_matrix(value): value=np.array(m.validate(value))
        elif not finite(value) or isinstance(value,complex): raise ValueError('Expected a real matrix or scalar result')
        if name:
            if not self.is_matrix(value): raise ValueError('Matrix variables require a matrix result')
            self.matrices[name]=np.array(value)
        return value
    def resize(self):
        from engtools.numerics.backend import require
        np,_=require()
        result=np.zeros((self.rows_count,self.columns))
        old=self.matrices.get(self.name)
        if old is not None:
            for i in range(min(self.rows_count,old.shape[0])):
                for j in range(min(self.columns,old.shape[1])): result[i,j]=old[i,j]
        self.matrices[self.name]=result
        self.page,self.selected,self.field,self.editing='cells',0,'cell',False
    def commit(self,text):
        self.matrices[self.name][self.selected//self.columns,self.selected%self.columns]=self.scalar(text)
    def run(self,button):
        if self.common(button): return
        if button==k.BUTTON_F5:
            if self.editing and self.page=='cells':return
            if self.result is not None:self.page='result';self.editing=False
            return
        if button==self.calc.vm.input_manager._key_esc:
            if self.page=='entry': self.calc.vm.back()
            elif self.page=='cells' and self.editing: self.editing=False; self.calc.error=''
            else: self.return_entry()
            return
        if button==k.BUTTON_F3:
            if self.page=='entry':
                self.expression_draft=clone(self.editor.root)
                self.editor.clear()
            self.page,self.selected,self.editing='names',0,False; return
        if self.page=='entry':
            if button in (k.BUTTON_CENTER,k.BUTTON_F6):
                if self.editor.focus_missing(): raise ValueError('Complete the highlighted slot')
                value=self.evaluate(source(self.editor.root))
                if self.is_matrix(value):
                    self.result=value; self.page='result'; self.editing=False; self.result_scroll=0
                else:
                    self.calc.answer=value; self.calc.variables['Ans']=value
                    self.result=None
                self.editor.clear(); self.calc.error=''
            elif button==k.BUTTON_F10: self.editor.clear()
            else: self.calc.edit_key(self.editor,button)
        elif self.page=='names':
            if button in (k.BUTTON_UP,k.BUTTON_DOWN): self.selected=(self.selected+(-1 if button==k.BUTTON_UP else 1))%4
            elif button==k.BUTTON_CENTER:
                self.name=self.NAMES[self.selected]
                old=self.matrices.get(self.name)
                self.rows_count,self.columns=old.shape if old is not None else (2,2)
                self.page,self.selected='dimensions',0
        elif self.page=='dimensions':
            if button in (k.BUTTON_UP,k.BUTTON_DOWN): self.selected=1-self.selected
            elif button in (k.BUTTON_LEFT,k.BUTTON_RIGHT):
                delta=-1 if button==k.BUTTON_LEFT else 1
                if self.selected==0: self.rows_count=1+(self.rows_count-1+delta)%4
                else: self.columns=1+(self.columns-1+delta)%4
            elif button==k.BUTTON_CENTER: self.resize()
        elif self.page=='cells':
            if self.editing: self.entry(button,self.commit); return
            row,col=divmod(self.selected,self.columns)
            if button==k.BUTTON_LEFT: col=(col-1)%self.columns
            elif button==k.BUTTON_RIGHT: col=(col+1)%self.columns
            elif button==k.BUTTON_UP: row=(row-1)%self.rows_count
            elif button==k.BUTTON_DOWN: row=(row+1)%self.rows_count
            elif button==k.BUTTON_CENTER: self.begin(format_value(self.matrices[self.name][row,col]))
            self.selected=row*self.columns+col
        elif self.page=='result':
            if button==k.BUTTON_CENTER:
                self.return_entry()
            elif button in (k.BUTTON_UP,k.BUTTON_DOWN):
                self.result_scroll=(self.result_scroll+(-1 if button==k.BUTTON_UP else 1))%(self.result.shape[0]*self.result.shape[1])
    def draw(self,draw,width,height):
        r,_,_=self.chrome(draw,'MATRIX / '+(self.name if self.page=='cells' else self.page.upper()),'F3 Define matrices  ENTER edit/evaluate')
        if self.page=='names':
            rows=[(name,'%d x %d'%self.matrices[name].shape if name in self.matrices else 'Not defined') for name in self.NAMES]
            self.rows(r,rows,self.selected,width,height)
        elif self.page=='dimensions':
            self.rows(r,(('Rows',self.rows_count),('Columns',self.columns)),self.selected,width,height)
            if self.calc.show_hints:
                r.text(12,123,'L/R changes (1..4); ENTER applies',self.calc.palette.MUTED,TINY)
                r.text(12,147,'Overlap is kept when resizing '+self.name,self.calc.palette.MUTED,TINY)
        elif self.page in ('cells','result'):
            value=self.matrices[self.name] if self.page=='cells' else self.result
            selected=self.selected
            if self.page=='result': self.selected=self.result_scroll
            self.sheet(r,[[value[i,j] for j in range(value.shape[1])] for i in range(value.shape[0])],['c'+str(j+1) for j in range(value.shape[1])],width)
            row,col=divmod(self.selected,value.shape[1]); self.selected=selected
            r.text(12,191,'[%d,%d] = %s'%(row+1,col+1,format_value(value[row,col])),self.calc.accent,TINY)
            if self.editing: self.input(draw,width,height)
            elif self.page=='result' and self.calc.show_hints:
                r.text(12,217,'Saved as MatAns; ENTER returns',self.calc.palette.MUTED,TINY)
        else:
            r.text(12,53,'Scalar answer: '+format_value(self.calc.answer),self.calc.accent,TINY)
            hints=('Options defines MatA..MatD, sizes 1..4','MatA+MatB  MatA*MatB  2*MatA','inv(MatA) det(MatA) trn(MatA)','MatA^2  trace(MatA) identity(3)','MatB=inv(MatA)  MatAns*MatA')
            if self.calc.show_hints:
                for i,text in enumerate(hints): r.text(12,78+i*19,text,self.calc.palette.MUTED,TINY)
            self.input(draw,width,height)
        draw.swap()
