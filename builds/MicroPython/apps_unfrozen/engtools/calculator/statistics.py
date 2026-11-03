"""Calculator-owned statistics table, result views and explicit CSV actions."""
from picoware.system import buttons as keys
from picoware.system.font import FONT_XTRA_SMALL, FONT_SMALL
from engtools.ui import theme
from .editor import Editor, source
from .evaluate import Parser, calculate, format_value

SAVE_DIRECTORY = 'picoware/engineering/statistics'
OPTIONS = ('Frequency', 'Insert row', 'Delete row', 'Clear dataset', 'Save CSV',
           'Load CSV', 'Choose data type', 'Calculator prompt', 'Quartile rule')
SUMMARY = (('n','Count'),('mean','Mean'),('median','Median'),('std','Sample SD'),
           ('pstd','Population SD'),('var','Sample variance'),('pvar','Population variance'),
           ('min','Minimum'),('max','Maximum'),('range','Range'),('q1','Q1'),('q3','Q3'),
           ('iqr','Interquartile range'),('sum','Sum'),('sum2','Sum of squares'))


class Workspace:
    def __init__(self, calculator):
        self.calc = calculator
        self.datasets, self.dataset = {}, None
        self.page, self.selected, self.row, self.column = 'start', 0, 0, 0
        self.editing, self.predicting = False, False
        self.editor = Editor()
        self.message, self.files, self.return_page = '', [], 'data'

    def choose(self, paired):
        from engtools.numerics.statistics import Dataset
        if paired not in self.datasets: self.datasets[paired] = Dataset(paired)
        self.dataset = self.datasets[paired]
        self.page, self.row, self.column, self.selected = 'data', 0, 0, 0
        self.editing, self.predicting, self.message, self.calc.error = False, False, '', ''

    def begin_edit(self, replace=False):
        if self.dataset is None: raise ValueError('Choose a dataset first')
        value = self.dataset.get(self.row,self.dataset.columns()[self.column])
        self.editor.clear()
        if not replace and value is not None: self.editor.load(list('%.9g' % value))
        self.editing, self.predicting = True, False
        self.calc.error = ''

    def commit(self, across=False):
        if self.editor.focus_missing(): raise ValueError('Complete the highlighted slot')
        text = source(self.editor.root)
        assignment, _ = Parser(text).parse()
        if assignment is not None: raise ValueError('Use the calculator prompt to assign variables')
        value, _ = calculate(text,dict(self.calc.variables),self.calc.angle,False,self.dataset)
        if self.predicting:
            predicted = self.dataset.predict(value)
            self.use_result(predicted,'Prediction for X='+format_value(value),return_to_calc=False)
            self.editing, self.predicting = False, False
            self.message = 'Predicted Y='+format_value(predicted)
            self.page = 'fit'
            return
        column = self.dataset.columns()[self.column]
        self.dataset.set(self.row,column,value)
        self.use_result(value,column+' row '+str(self.row+1),return_to_calc=False)
        self.editor.clear()
        self.editing, self.calc.error = False, ''
        if across:
            self.column += 1
            if self.column < len(self.dataset.columns()): return
            self.column = 0
        if self.row == self.dataset.rows-1 and self.dataset.rows < 128:
            self.dataset.insert_row(self.dataset.rows)
        self.row = min(self.dataset.rows-1,self.row+1)

    def use_result(self, value, label, return_to_calc=True):
        self.calc.answer, self.calc.assignment = value,label
        self.calc.variables['Ans'] = value
        if return_to_calc:
            self.calc.page = 'calc'
            self.calc.error = ''

    def run(self, button):
        self.message = ''
        self.calc.error = ''
        if button == self.calc.vm.input_manager._key_esc:
            self.calc.error = ''
            if self.editing:
                self.editing = False
                self.editor.clear()
                if self.predicting: self.page = 'fit'
                self.predicting = False
            elif self.page == 'start': self.calc.page = 'calc'
            elif self.page in ('options','load','confirm'): self.page = self.return_page
            else: self.page,self.selected = 'start',0
            return
        if button in (keys.BUTTON_F1,keys.BUTTON_F2) and not self.editing:
            if self.dataset is not None and self.page == 'data':
                if button == keys.BUTTON_F1:self.dataset.insert_row(self.row+1);self.row+=1
                else:self.dataset.delete_row(self.row);self.row=min(self.row,self.dataset.rows-1)
            return
        if button == keys.BUTTON_F4:return
        if self.editing:
            if button == keys.BUTTON_TAB and self.editor.parents: self.editor.tab()
            elif button in (keys.BUTTON_CENTER,keys.BUTTON_TAB,keys.BUTTON_F6): self.commit(button == keys.BUTTON_TAB)
            elif button == keys.BUTTON_F7: self.calc.open_page('templates')
            elif button == keys.BUTTON_F8: self.calc.open_page('variables')
            elif button == keys.BUTTON_F10:
                self.editor.clear(); self.calc.error = ''
            elif button in (keys.BUTTON_F3,keys.BUTTON_F4,keys.BUTTON_F6):
                raise ValueError('Commit the cell or press ESC first')
            else: self.calc.edit_key(self.editor,button)
            return
        if button in (keys.BUTTON_F3,keys.BUTTON_F4,keys.BUTTON_F5,keys.BUTTON_F6,keys.BUTTON_F7,keys.BUTTON_F8):
            if self.dataset is None: raise ValueError('Choose 1-variable or 2-variable first')
            if button == keys.BUTTON_F3: self.page,self.selected = 'data',0
            elif button == keys.BUTTON_F4: self.page,self.selected = 'summary',0
            elif button == keys.BUTTON_F5: self.page,self.selected = 'summary',0
            elif button == keys.BUTTON_F6:
                self.dataset.summary()
                self.page,self.selected = 'summary',0
            elif button in (keys.BUTTON_F7,keys.BUTTON_F8):
                self.page = 'data'
                self.begin_edit(True)
                self.calc.open_page('templates' if button == keys.BUTTON_F7 else 'variables')
            self.calc.error = ''
            return
        if self.page == 'start':
            if button in (keys.BUTTON_UP,keys.BUTTON_DOWN):
                self.selected = (self.selected+(-1 if button == keys.BUTTON_UP else 1))%2
            elif button == keys.BUTTON_CENTER:
                self.choose(self.selected == 1)
            elif button in (keys.BUTTON_1,keys.BUTTON_2): self.choose(button == keys.BUTTON_2)
        elif self.page == 'data':
            if button == keys.BUTTON_UP: self.row = max(0,self.row-1)
            elif button == keys.BUTTON_DOWN: self.row = min(self.dataset.rows-1,self.row+1)
            elif button in (keys.BUTTON_LEFT,keys.BUTTON_RIGHT):
                self.column = (self.column+(-1 if button == keys.BUTTON_LEFT else 1))%len(self.dataset.columns())
            elif button == keys.BUTTON_TAB:
                self.column = (self.column+1)%len(self.dataset.columns())
                if self.column == 0: self.row = min(self.dataset.rows-1,self.row+1)
            elif button == keys.BUTTON_CENTER: self.begin_edit()
            elif button == keys.BUTTON_DELETE:
                self.dataset.delete_row(self.row)
                self.row = min(self.row,self.dataset.rows-1)
            elif button == self.calc.vm.input_manager._key_back or button == keys.BUTTON_BACKSPACE:
                self.dataset.clear_cell(self.row,self.dataset.columns()[self.column])
            else:
                char = self.calc.vm.input_manager.button_to_char(button)
                if char and char not in ('\n','\t'):
                    self.begin_edit(True)
                    self.calc.edit_key(self.editor,button)
        elif self.page in ('summary','fit'):
            rows = self.results()
            if button in (keys.BUTTON_UP,keys.BUTTON_DOWN):
                self.selected = (self.selected+(-1 if button == keys.BUTTON_UP else 1))%len(rows)
            elif button == keys.BUTTON_CENTER:
                label,value,note = rows[self.selected]
                if label == 'Predict Y':
                    self.editor.clear()
                    self.editing,self.predicting = True,True
                elif value is None: raise ValueError(note)
                else: self.use_result(value,label)
        elif self.page == 'options':
            if button in (keys.BUTTON_UP,keys.BUTTON_DOWN):
                self.selected = (self.selected+(-1 if button == keys.BUTTON_UP else 1))%len(OPTIONS)
            elif button == keys.BUTTON_CENTER: self.option()
        elif self.page == 'confirm' and button == keys.BUTTON_CENTER:
            self.dataset.clear()
            self.row,self.column,self.page = 0,0,'data'
        elif self.page == 'load' and self.files:
            if button in (keys.BUTTON_UP,keys.BUTTON_DOWN):
                self.selected = (self.selected+(-1 if button == keys.BUTTON_UP else 1))%len(self.files)
            elif button == keys.BUTTON_CENTER: self.load(self.files[self.selected])

    def results(self):
        try:
            if self.dataset is None: raise ValueError('Choose a dataset first')
            summary = self.dataset.summary()
            if self.page == 'summary':
                rows = []
                for column in self.dataset.columns():
                    if column == 'Freq': continue
                    for field,label in SUMMARY:
                        value = summary[column][field]
                        reason = 'Need at least two observations' if field in ('std','var') and summary['n'] < 2 else 'Out of range; scale the data'
                        rows.append((column+' '+label,value,reason if value is None else 'ENTER uses this value as Ans'))
                if self.dataset.paired:
                    pairs = self.dataset.pair_statistics()
                    for field,label in (('cov','Sample covariance'),('pcov','Population covariance'),('corr','Correlation r')):
                        value = pairs[field]
                        reason = 'Need at least two observations' if summary['n'] < 2 else 'Correlation needs variation in X and Y'
                        rows.append((label,value,reason if value is None else 'ENTER uses this value as Ans'))
                return rows
            fit = self.dataset.fit()
            rows = [(label,fit[field],('Need at least three observations' if field == 'residual_sd' else 'Y has no variation')
                     if fit[field] is None else 'ENTER uses this value as Ans')
                    for field,label in (('intercept','Intercept a'),('slope','Slope b'),('corr','Correlation r'),
                                        ('r2','R squared'),('sse','Residual sum of squares'),('residual_sd','Residual SD'))]
            rows.append(('Predict Y',None,'ENTER to enter an X value'))
            return rows
        except (ValueError,RuntimeError,ImportError) as exc:
            return [('No result',None,str(exc))]

    def option(self):
        option = OPTIONS[self.selected]
        if option == 'Frequency':
            self.dataset.set_frequency(not self.dataset.frequency)
            self.column = min(self.column,len(self.dataset.columns())-1)
            self.page = 'data'
        elif option == 'Insert row': self.dataset.insert_row(self.row); self.page = 'data'
        elif option == 'Delete row':
            self.dataset.delete_row(self.row); self.row = min(self.row,self.dataset.rows-1); self.page = 'data'
        elif option == 'Clear dataset': self.page = 'confirm'
        elif option == 'Save CSV': self.save(); self.page = 'data'
        elif option == 'Load CSV':
            if not self.calc.vm.storage.active: raise RuntimeError('SD card unavailable')
            self.files = sorted(name for name in self.calc.vm.storage.listdir(SAVE_DIRECTORY)
                                if name.lower().endswith('.csv') and '/' not in name and '\\' not in name)
            self.page,self.selected = 'load',0
        elif option == 'Choose data type': self.page,self.selected = 'start',0
        elif option == 'Calculator prompt': self.calc.page = 'calc'
        else: self.message = 'Type 7: interpolate at (n-1)*p'

    def save(self):
        storage = self.calc.vm.storage
        if not storage.active: raise RuntimeError('SD card unavailable')
        for path in ('picoware','picoware/engineering',SAVE_DIRECTORY):
            if not storage.exists(path) and not storage.mkdir(path): raise RuntimeError('Could not create statistics folder')
        data = self.dataset.to_csv()
        for index in range(1,1000):
            name = 'statistics-%dvar-%03d.csv' % (2 if self.dataset.paired else 1,index)
            path = SAVE_DIRECTORY+'/'+name
            if not storage.exists(path): break
        else: raise RuntimeError('Save folder full; remove old CSV files')
        try:
            if not storage.write(path,data) or storage.read(path) != data:
                raise RuntimeError('CSV write failed verification')
        except Exception:
            storage.remove(path)
            raise
        self.message = 'Saved '+name
        return path

    def load(self, name):
        from engtools.numerics.statistics import Dataset
        storage = self.calc.vm.storage
        path = SAVE_DIRECTORY+'/'+name
        if not storage.active: raise RuntimeError('SD card unavailable')
        if storage.size(path) > 32768: raise ValueError('CSV limit: 32 KiB')
        dataset = Dataset.from_csv(storage.read(path))
        self.datasets[dataset.paired],self.dataset = dataset,dataset
        self.row,self.column,self.page = 0,0,'data'
        self.calc.error,self.message = '','Loaded '+name

    def draw(self, draw, width, height):
        if self.page in ('start','distributions','options','load','confirm'):
            self.draw_menu(draw,width,height)
            return
        dataset = self.dataset
        status = 'STAT %d-VAR' % (2 if dataset.paired else 1)
        if self.page in ('summary','fit') and not self.predicting:
            rows = self.results()
            self.selected = min(self.selected,len(rows)-1)
            label,value,note = rows[self.selected]
            r = self.calc.draw_top(draw,width,height,label,value if value is not None else 'N/A',status)
            capacity = max(1,(height-self.calc.footer_height-128)//21)
            first = max(0,self.selected-capacity+1)
            for index in range(first,min(len(rows),first+capacity)):
                y = 129+(index-first)*21
                if index == self.selected: r.fill(8,y-3,width-16,20,self.calc.palette.SELECT)
                title,result,_ = rows[index]
                r.text(15,y,title[:27],self.calc.palette.TEXT,FONT_XTRA_SMALL)
                text = format_value(result,self.calc.engineering) if result is not None else '--'
                r.text(width-15-len(text)*6,y,text,self.calc.accent,FONT_XTRA_SMALL)
            self.footer(r,width,height,'F3 Options  F5 Results  F6 Calculate',self.calc.error or self.message or note)
            draw.swap()
            return
        r = self.calc.draw_top(draw,width,height,status=status)
        r.text(130,22,'n='+str(dataset.observation_count()),self.calc.palette.TEXT,FONT_XTRA_SMALL)
        r.text(width-70,22,'FREQ '+('ON' if dataset.frequency else 'OFF'),self.calc.palette.MUTED,FONT_XTRA_SMALL)
        bottom = height-self.calc.footer_height
        prompt_top = bottom-68
        r.rect(8,122,width-16,bottom-125,self.calc.palette.GRID)
        if self.predicting:
            fit = dataset.fit()
            r.text(16,133,'LINEAR PREDICTION',self.calc.accent,FONT_SMALL)
            r.text(16,155,'Y = a + b*X',self.calc.palette.TEXT,FONT_SMALL)
            r.text(16,176,'a='+format_value(fit['intercept'])+'  b='+format_value(fit['slope']),self.calc.palette.MUTED,FONT_XTRA_SMALL)
        else:
            columns = dataset.columns()
            if len(columns) == 3: positions = [(46,86),(138,86),(230,width-246)]
            elif len(columns) == 2:
                positions = [(46,124),(180,width-196)] if dataset.paired else [(46,175),(235,width-251)]
            else: positions = [(46,width-62)]
            r.text(15,129,'ROW',self.calc.palette.MUTED,FONT_XTRA_SMALL)
            for column,(x,_) in zip(columns,positions): r.text(x+4,127,column,self.calc.accent,FONT_SMALL)
            r.line(9,142,width-10,142,self.calc.palette.GRID)
            capacity = max(1,(prompt_top-146)//16)
            first = max(0,self.row-capacity+1)
            for index in range(first,min(dataset.rows,first+capacity)):
                y = 146+(index-first)*16
                r.text(15,y,str(index+1),self.calc.palette.MUTED,FONT_XTRA_SMALL)
                for column_index,(column,(x,w)) in enumerate(zip(columns,positions)):
                    chosen = index == self.row and column_index == self.column
                    if chosen:
                        r.fill(x,y-2,w,15,self.calc.palette.SELECT)
                        r.rect(x,y-2,w,15,self.calc.accent)
                    value = dataset.get(index,column)
                    text = format_value(value) if value is not None else '--'
                    font = FONT_SMALL if len(text)*8 <= w-8 else FONT_XTRA_SMALL
                    r.text(x+4,y,text,self.calc.palette.TEXT if value is not None else self.calc.palette.MUTED,font)
        r.line(9,prompt_top,width-10,prompt_top,self.calc.palette.GRID)
        r.text(16,prompt_top+7,'>>',self.calc.accent,FONT_SMALL)
        show_note = self.calc.show_hints or self.calc.error or self.message
        input_renderer = self.calc.renderer(draw,(40,prompt_top+5,width-17,bottom-(19 if show_note else 5)))
        if self.editing:
            input_renderer.expression(self.editor.root,43,prompt_top+9,editor=self.editor,follow=True)
            hint = self.editor.hint() if self.editor.parents else ('Enter X for prediction' if self.predicting else 'ENTER down | TAB across | ESC cancels')
        else:
            value = dataset.get(self.row,dataset.columns()[self.column])
            input_renderer.text(43,prompt_top+10,format_value(value) if value is not None else ('Type a value or press ENTER' if self.calc.show_hints else '--'),self.calc.palette.MUTED,FONT_SMALL)
            hint = 'ARROWS browse | DEL row | BS clears cell'
        if show_note:
            r.text(16,bottom-15,(self.calc.error or self.message or hint)[:48],self.calc.palette.ERROR if self.calc.error else self.calc.palette.MUTED,FONT_XTRA_SMALL)
        if self.editing:
            self.footer(r,width,height,'ENTER commit  TAB slots/across  ESC cancel',
                        'F3 Options  F10 Clear  F7 Math  F8 Variables')
        else:
            self.footer(r,width,height,'F3 Options  F5 Results  F6 Calculate','F3 Options  F7 Math  F8 Variables  ESC Return')
        draw.swap()

    def footer(self, r, width, height, first, second):
        self.calc.footer(r,width,height,first,second,self.message)

    def draw_menu(self, draw, width, height):
        if self.page == 'start':
            rows = [('1-variable','X values; optional frequencies'),('2-variable','X/Y pairs; linear regression')]
            hint = 'ENTER selects | F2 modes | ESC calculator'
        elif self.page == 'options':
            details = ('ON' if self.dataset.frequency else 'OFF','Before selected row','Selected row',
                       'Remove all values after confirmation','New numbered file; no automatic saving',
                       'Replace matching dataset from CSV','Both datasets stay in RAM','mean(X), std(X), predict(x)',
                       'Type 7: linear interpolation')
            rows = list(zip(OPTIONS,details)); hint = 'ENTER chooses | ESC returns'
        elif self.page == 'load':
            rows = [(name,'ENTER loads and replaces matching data') for name in self.files] or [('No CSV files','Save a dataset from Options first')]
            hint = 'Folder: picoware/engineering/statistics'
        elif self.page == 'confirm':
            rows = [('Clear this dataset?','ENTER clears | ESC keeps the data')]
            hint = 'This clears values held in RAM'
        else:
            rows = [('Distributions are planned','Normal, binomial and Poisson come later')]
            hint = 'ESC returns to Statistics'
        r = self.calc.renderer(draw,(0,18,width,height))
        r.fill(0,18,width,24,self.calc.palette.PANEL)
        r.text(9,24,'STATISTICS / '+self.page.upper(),self.calc.accent,FONT_SMALL)
        capacity = max(1,(height-self.calc.footer_height-51)//29)
        first = max(0,self.selected-capacity+1)
        for index in range(first,min(len(rows),first+capacity)):
            y = 53+(index-first)*29
            if index == self.selected: r.fill(8,y-3,width-16,27,self.calc.palette.SELECT)
            label,detail = rows[index]
            r.text(15,y,label[:36],self.calc.palette.TEXT,FONT_SMALL)
            r.text(15,y+14,detail[:48],self.calc.palette.MUTED,FONT_XTRA_SMALL)
        self.footer(r,width,height,hint,self.calc.error or self.message or 'UP/DOWN choose')
        draw.swap()
