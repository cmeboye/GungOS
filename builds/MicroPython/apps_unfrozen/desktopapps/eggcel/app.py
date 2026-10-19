"""Keyboard-first spreadsheet UI, drawn at the PicoCalc's native resolution."""
from picoware.system import buttons as k
from picoware.system.font import FONT_XTRA_SMALL as TINY, FONT_SMALL as SMALL
from engtools.calculator.render import Renderer
from .formulas import ROWS, COLS, MAX_TEXT, CellError, address, reference
from .model import Sheet, DIRECTORY, MAX_CELLS, format_value, safe_name, write_verified, read_sheet, demo

_active = None
FILE_ITEMS = ('New sheet','Open workbook','Save','Save as','Open CSV','Export CSV','Load example')
ACTIONS = ('Fill selection','Fill down','Fill right','Convert to values','Undo last edit',
           'Copy selection','Paste','Clear selection','Format: General','Format: 2 decimals',
           'Format: Scientific','Recalculate','Plot selection')
CHART_TYPES=('line','scatter','column','pie')
CHART_LABELS=('XY lines','XY scatter','2D column','2D pie')


def blend(first,second,numerator,denominator):
    result=0
    for shift,mask in ((11,31),(5,63),(0,31)):
        a,b=(first>>shift)&mask,(second>>shift)&mask
        result|=((a*(denominator-numerator)+b*numerator)//denominator)<<shift
    return result


class Spreadsheet:
    def __init__(self):
        self.vm=None
        self.sheet=Sheet()
        self.row=self.col=self.top=self.left=0
        self.anchor=None
        self.page,self.selected='grid',0
        self.editing,self.help=False,False
        self.buffer,self.cursor,self.offset='',0,0
        self.filename,self.message,self.error='','',''
        self.clipboard=None
        self.files=[]
        self.browser=None
        self.csv_directory='/picoware'
        self.pending,self.after_save,self.overwrite=None,None,None
        self.purpose='';self.replace_on_type=False
        self.plot_options=None
        self._plot_selection=None
        self.suspended,self._keep_on_stop=False,False
        self.job=None;self.job_kind='';self.calc_paused=False;self.progress=0
        self.text_clipboard=None;self._safe_mode=False;self.last_diagnostic=''

    def start(self,vm):
        global _active
        self.vm,_active=vm,self
        self.suspended,self._keep_on_stop=False,False
        vm.input_manager.reset()
        self.safe_draw()
        return True

    def stop(self,vm):
        global _active
        self.cancel_job()
        self.browser=None
        if self._keep_on_stop:
            self._keep_on_stop,self.suspended=False,True
            return
        self.suspended=False
        self.sheet,self.clipboard,self.vm=None,None,None
        _active=None

    def cancel_job(self):
        job,self.job=self.job,None
        if job is not None:
            try:job.close()
            except Exception:pass
        self.job_kind=''

    def start_job(self,job,kind):
        self.cancel_job();self.job,self.job_kind=job,kind;self.progress=0
        self.error='';self._safe_mode=False

    def tick_job(self):
        if self.job is None:return False
        try:
            for _ in range(2):self.progress=next(self.job)
        except StopIteration:
            kind=self.job_kind;self.cancel_job()
            if kind=='Chart':self.open_plot_ready();return True
            if kind=='Calculating' and self.sheet.last_errors:
                self.error=str(self.sheet.last_errors)+' formula error(s)'+(' / first: '+address(*self.sheet.problem) if self.sheet.problem else '')+'; cells marked red'
                self.calc_paused=True
            else:self.message='Converted to values; Actions > Undo' if kind=='Converting' else 'Calculation complete'
        return True

    def report_error(self,exc):
        self.cancel_job();self.calc_paused=True
        self.last_diagnostic=type(exc).__name__+': '+str(exc)
        print('Eggcel:',self.last_diagnostic)
        self.error=('Memory limit; workbook retained' if isinstance(exc,MemoryError) else
                    'Calculation stack limit; workbook retained' if isinstance(exc,RuntimeError) and 'recursion' in str(exc) else str(exc)) or 'Operation failed; workbook retained'

    def safe_draw(self):
        if self.vm is None or self.suspended or self.browser is not None:return
        try:
            if self._safe_mode:self.draw_fallback()
            else:self.draw()
        except Exception as exc:
            self.report_error(exc);self._safe_mode=True;self.draw_fallback()

    def draw_fallback(self):
        d=self.vm.draw;fg,bg=self.vm.foreground_color,self.vm.background_color
        d.fill_screen(bg)
        from engtools.ui import theme
        theme.header(d,'Eggcel / Recovery','PicoDESK',theme.system_palette(self.vm),height=18)
        d._text(8,25,'Eggcel / workbook retained',fg,1)
        d._text(8,57,address(*self.position)+'  '+self.sheet.cells.get(self.position,'')[:35],fg,0)
        d._text(8,85,'F1 File   F2 Recovery   ESC dismiss',fg,0)
        if self.message:d._text(8,98,self.message[:49],fg,0)
        if self.page!='grid':
            rows=self.menu_items();first=max(0,self.selected-5)
            for i in range(first,min(len(rows),first+6)):
                d._text(8,110+(i-first)*21,('> ' if i==self.selected else '  ')+rows[i][:46],fg,0)
            if self.page=='dialog':d._text(8,125,self.buffer[:45],fg,0)
        self.draw_error_native();d.swap()

    def draw_error_native(self):
        d=self.vm.draw;w,h=int(d.size.x),int(d.size.y);y=self.bottom-52
        d._fill_rectangle(3,y,w-6,50,0x3000);d._rectangle(3,y,w-6,50,0xF800)
        cut=self.error.rfind(' ',0,39) if len(self.error)>39 else len(self.error)
        if cut<12:cut=39
        d._text(9,y+6,'ERROR / '+self.error[:cut],0xF800,0)
        d._text(9,y+20,self.error[cut:].strip()[:49],self.vm.foreground_color,0)
        d._text(9,y+35,'F2 Recovery   F1 File   ESC dismiss',self.vm.foreground_color,0)

    def resume(self):
        self.cancel_job();self.error='';self._safe_mode=False;self.calc_paused=True;self.page='grid'

    def recover(self,index):
        if index==0:self.resume()
        elif index==1:
            problem=self.sheet.problem
            self.resume()
            if problem is not None:self.row,self.col=problem;self.anchor=None;self.reveal()
            self.begin()
        elif index==2:
            self.resume();self.sheet.restore();self.reveal()
        elif index==3:
            self.resume();self.calc_paused=False;self.start_job(self.sheet.recalculate_job(),'Calculating')
        elif index==4:self.resume();self.page,self.selected='convert_confirm',1
        else:
            name=next(('Recovery-%03d.egg'%i for i in range(1,1000) if not self.vm.storage.exists(DIRECTORY+'/Recovery-%03d.egg'%i)),None)
            if name is None:raise ValueError('Recovery filenames are full')
            write_verified(self.vm.storage,DIRECTORY+'/'+name,self.sheet.document())
            self.resume();self.message='Recovery copy saved: '+name

    def copy_text(self):self.text_clipboard=self.buffer;self.message='Entry copied'
    def paste_text(self):
        value=self.text_clipboard
        if value is None and self.clipboard is not None:
            bounds,cells=self.clipboard
            if bounds[0]==bounds[2] and bounds[1]==bounds[3]:value=cells[(0,0)]
        if value is None:raise ValueError('Copy an entry or one cell first')
        base='' if self.replace_on_type else self.buffer
        cursor=0 if self.replace_on_type else self.cursor
        if len(base)+len(value)>(MAX_TEXT if self.page=='grid' else 48):raise ValueError('Paste exceeds input limit')
        self.buffer=base[:cursor]+value+base[cursor:];self.cursor=cursor+len(value);self.replace_on_type=False

    @property
    def position(self): return self.row,self.col
    @property
    def bounds(self):
        r,c=self.anchor if self.anchor is not None else self.position
        return min(r,self.row),min(c,self.col),max(r,self.row),max(c,self.col)
    @property
    def bottom(self): return int(self.vm.draw.size.y)-(36 if self.help else 13)
    @property
    def visible_rows(self): return max(1,(self.bottom-127-(52 if self.error else 0))//22)

    def renderer(self,clip=None):
        d=self.vm.draw
        return Renderer(d,clip or (0,18,int(d.size.x),int(d.size.y)),self.vm.selected_color)

    def visible_columns(self):
        width=int(self.vm.draw.size.x)
        columns=[]; x=28
        for col in range(self.left,COLS):
            size=self.sheet.widths.get(col,72)
            if x+size>width-1: break
            columns.append((col,x,size)); x+=size
        return columns

    def reveal(self):
        count=self.visible_rows
        self.top=min(self.top,self.row)
        if self.row>=self.top+count: self.top=self.row-count+1
        self.left=min(self.left,self.col)
        while self.col not in [col for col,_,_ in self.visible_columns()] and self.left<self.col:
            self.left+=1

    def begin(self,text=None):
        self.buffer=self.sheet.cells.get(self.position,'') if text is None else text
        self.cursor,self.offset=len(self.buffer),0
        self.editing=True;self.replace_on_type=False
        self.error=self.message=''

    def commit(self,advance=False):
        self.cancel_job();self.calc_paused=False;self.error=''
        self.sheet.apply({self.position:self.buffer})
        self.editing=False
        self.anchor=None
        if advance: self.col=min(COLS-1,self.col+1)
        self.reveal()

    def edit_input(self,button):
        if button in (k.BUTTON_LEFT,k.BUTTON_RIGHT,k.BUTTON_BACKSPACE,k.BUTTON_DELETE):self.replace_on_type=False
        if button==k.BUTTON_LEFT: self.cursor=max(0,self.cursor-1)
        elif button==k.BUTTON_RIGHT: self.cursor=min(len(self.buffer),self.cursor+1)
        elif button in (k.BUTTON_BACKSPACE,self.vm.input_manager._key_back):
            if self.cursor:
                self.buffer=self.buffer[:self.cursor-1]+self.buffer[self.cursor:];self.cursor-=1
        elif button==k.BUTTON_DELETE: self.buffer=self.buffer[:self.cursor]+self.buffer[self.cursor+1:]
        elif button==k.BUTTON_F4:self.copy_text()
        elif button==k.BUTTON_F5:self.paste_text()
        else:
            char=self.vm.input_manager.button_to_char(button)
            limit=MAX_TEXT if self.page=='grid' else 48
            if char and char not in ('\n','\r','\t'):
                if self.replace_on_type:self.buffer,self.cursor='',0;self.replace_on_type=False
                if len(self.buffer)>=limit: raise ValueError('Input limit reached')
                self.buffer=self.buffer[:self.cursor]+char+self.buffer[self.cursor:];self.cursor+=1

    def guard(self,action):
        if self.sheet.dirty:
            self.pending,self.page,self.selected=action,'confirm',0
        else: self.perform(action)

    def perform(self,action):
        self.pending=None
        if action=='quit': self.vm.back();return
        if action in ('new','demo'):
            self.sheet=demo() if action=='demo' else Sheet()
            self.row=self.col=self.top=self.left=0
            self.filename,self.anchor,self.page='',None,'grid'
            self.plot_options=None;self.calc_paused=False;self._safe_mode=False;self.error=''
            self.message='Example loaded' if action=='demo' else 'New sheet'
        elif action=='import':
            from picoware.gui.file_browser import FileBrowser, FILE_BROWSER_SELECTOR
            self.browser=FileBrowser(self.vm,FILE_BROWSER_SELECTOR,self.csv_directory,['csv'])
            self.browser._brand='PicoDESK'
            self.browser._breadcrumb='Eggcel / Import CSV'
            self.page='csv_browser'
            # Render on the next tick: vm.button still contains the Enter
            # that opened the selector, even after input.reset().
            self.vm.input_manager.reset()
        elif action=='open':
            extension='.egg'
            self.files=sorted(name for name in self.vm.storage.listdir(DIRECTORY)
                              if name.lower().endswith(extension))
            self.purpose,self.page,self.selected=action,'files',0

    def load_file(self,path,imported=False):
        # Validate the entire file before replacing the current workbook.
        result=read_sheet(self.vm.storage,path,imported)
        self.sheet=result
        self.filename='' if imported else path
        self.row=self.col=self.top=self.left=0
        self.anchor,self.page=None,'grid'
        self.message=('Imported ' if imported else 'Opened ')+path.rsplit('/',1)[-1]
        self.plot_options=None;self._plot_selection=None
        self.calc_paused=False;self._safe_mode=False;self.error=''

    def run_csv_browser(self):
        browser=self.browser
        if browser.run():return
        path,selected=browser.path,browser.mode==browser.MODE_SELECT
        self.csv_directory=browser.directory
        self.browser=None;self.page='grid'
        if selected:
            if not path.lower().endswith('.csv'):raise ValueError('Select a CSV file')
            self.load_file(path,True)

    def prompt(self,purpose,text=''):
        self.purpose,self.page=purpose,'dialog';self.replace_on_type=True
        self.buffer,self.cursor,self.offset=text,len(text),0

    def save(self,as_new=False):
        if self.filename and not as_new:
            self.write(self.filename)
        else:
            self.prompt('save',self.filename.rsplit('/',1)[-1][:-4] if self.filename else 'Workbook')

    def write(self,path,export=False):
        text=self.sheet.csv() if export else self.sheet.document()
        write_verified(self.vm.storage,path,text)
        self.page,self.message='grid',('Exported ' if export else 'Saved ')+path.rsplit('/',1)[-1]
        if not export:
            self.filename=path;self.sheet.mark_saved()
            if self.after_save:
                action,self.after_save=self.after_save,None
                self.perform(action)

    def dialog_commit(self):
        if self.purpose.startswith('plot_'):
            from .charts import parse_range
            value=self.buffer.strip().upper()
            if value: parse_range(value)
            if self.purpose=='plot_x': self.plot_options['x']=value
            else: self.plot_options['ys'][int(self.purpose[-1])]=value
            self.page='plot_setup'
            return
        if self.purpose=='goto':
            self.row,self.col=reference(self.buffer.strip())
            self.page='grid';self.reveal();return
        export=self.purpose=='export'
        path=DIRECTORY+'/'+safe_name(self.buffer,'.csv' if export else '.egg')
        if self.vm.storage.exists(path):
            self.overwrite,self.page,self.selected=(path,export),'overwrite',1
        else: self.write(path,export)

    def copy(self):
        self.clipboard=self.sheet.copied(self.bounds);self.text_clipboard=None
        bounds=self.bounds
        self.message='Copied '+address(bounds[0],bounds[1])+':'+address(bounds[2],bounds[3])
        self.anchor=None

    def paste(self):
        if self.clipboard is None: raise ValueError('Copy a cell or range first')
        self.sheet.paste(self.clipboard,self.position)
        self.anchor=None;self.message='Pasted; relative references adjusted';self.calc_paused=False

    def clear_selection(self):
        top,left,bottom,right=self.bounds
        self.sheet.apply({position:'' for position in self.sheet.cells
                          if top<=position[0]<=bottom and left<=position[1]<=right})
        self.anchor=None

    def cycle_plot_type(self,step):
        old=self.plot_options['style']
        self.plot_options['style']=CHART_TYPES[(CHART_TYPES.index(old)+step)%4]
        if old in ('line','scatter') and self.plot_options['style'] in ('column','pie'):
            from .charts import parse_range
            first=[parse_range(v) for v in self.plot_options['ys'] if v.strip()]
            self.plot_options['header']=any(isinstance(self.sheet.peek((a,c)),str) and not (self.sheet.cells.get((a,c),'').startswith('=') and (a,c) not in self.sheet.cache) for a,c,b in first)

    def open_plot_setup(self):
        from .charts import defaults
        selection=self.bounds if self.anchor is not None else None
        if self.plot_options is None or (selection is not None and selection!=self._plot_selection):
            self.plot_options=defaults(self.sheet,self.bounds)
            self._plot_selection=selection
        self.page,self.selected='plot_setup',6
        self.error=self.message=''

    def open_plot(self):
        self.start_job(self.sheet.recalculate_job(False),'Chart')

    def open_plot_ready(self):
        from .charts import build_spec
        from engtools.plots import plot2d
        spec=build_spec(self.sheet,self.plot_options,self.vm)
        categorical=self.plot_options['style'] in ('column','pie')
        if not categorical:plot2d.validate_spec(spec)
        self._keep_on_stop=True
        self.page='grid'
        try:
            if categorical:
                from .chart_view import show
                show(self.vm,spec)
            else:plot2d.show(self.vm,spec)
        except Exception:
            self._keep_on_stop,self.suspended=False,False
            self.page='plot_setup'
            raise

    def menu_choose(self):
        index=self.selected
        if self.page=='file':
            if index==0: self.guard('new')
            elif index==1: self.guard('open')
            elif index==2: self.save()
            elif index==3: self.save(True)
            elif index==4: self.guard('import')
            elif index==5: self.prompt('export','Workbook')
            else: self.guard('demo')
        elif self.page=='actions':
            self.page='grid'
            if index in (0,1,2):
                if index==0 and self.bounds[0]!=self.bounds[2] and self.bounds[1]!=self.bounds[3]:
                    self.page,self.selected='fill_direction',0;return
                direction=None if index==0 else ('down' if index==1 else 'right')
                count=self.sheet.fill(self.bounds,direction)
                self.calc_paused=False;self.message='Filled '+str(count)+' cells; Actions > Undo'
            elif index==3:self.page,self.selected='convert_confirm',1
            elif index==4:
                self.sheet.restore();self.calc_paused=False;self.error='';self.message='Last cell edit undone';self.reveal()
            elif index==5:self.copy()
            elif index==6:self.paste()
            elif index==7:self.clear_selection()
            elif index in (8,9,10):
                style=('general','fixed2','scientific')[index-8]
                if style!=self.sheet.style:
                    self.sheet.undo=(self.sheet.cells,self.sheet.style,self.sheet.dirty)
                    self.sheet.style,self.sheet.dirty=style,True
            elif index==11:
                self.calc_paused=False;self.start_job(self.sheet.recalculate_job(),'Calculating')
            else:self.open_plot_setup()
        elif self.page=='fill_direction':
            count=self.sheet.fill(self.bounds,'down' if index==0 else 'right')
            self.page='grid';self.calc_paused=False;self.message='Filled '+str(count)+' cells; Actions > Undo'
        elif self.page=='convert_confirm':
            self.page='grid'
            if index==0:self.start_job(self.sheet.convert_job(self.bounds),'Converting')
        elif self.page=='recovery':self.recover(index)
        elif self.page=='plot_setup':
            if index==0:
                self.cycle_plot_type(1)
            elif index==1: self.prompt('plot_x',self.plot_options['x'])
            elif index in (3,4) and self.plot_options['style']=='pie':raise ValueError('Pie uses Y1 only')
            elif index in (2,3,4): self.prompt('plot_y'+str(index-2),self.plot_options['ys'][index-2])
            elif index==5: self.plot_options['header']=not self.plot_options['header']
            else: self.open_plot()
        elif self.page=='files' and self.files:
            name=self.files[index]
            self.load_file(DIRECTORY+'/'+name)
        elif self.page=='confirm':
            action=self.pending
            if index==0:
                self.after_save=action;self.save()
            elif index==1:self.after_save=None;self.perform(action)
            else:self.pending,self.after_save,self.page=None,None,'grid'
        elif self.page=='overwrite':
            if index==0: self.write(*self.overwrite)
            else: self.page='dialog'

    def run(self,vm):
        button=vm.button
        try:
            if self.browser is not None:
                self.run_csv_browser()
                self.safe_draw();return
            if self.job is not None:
                if button==vm.input_manager._key_esc:
                    self.cancel_job();self.calc_paused=True;self.message='Cancelled; original cells retained'
                    self.safe_draw();return
                if button==k.BUTTON_NONE:
                    self.tick_job();self.safe_draw();return
                if self.job_kind=='Converting':return
                self.cancel_job()
            if button==k.BUTTON_NONE:return
            if button==k.BUTTON_F9:self.help=not self.help;self.reveal()
            elif button==k.BUTTON_F1:
                if self.editing:self.commit()
                self.page,self.selected='file',0
            elif button==k.BUTTON_F2 and self.error:self.page,self.selected='recovery',0
            elif self._safe_mode and self.page=='grid':
                if button==vm.input_manager._key_esc:self.resume()
            elif self.page=='dialog':
                if button==vm.input_manager._key_esc:self.page,self.after_save=('plot_setup' if self.purpose.startswith('plot_') else 'grid'),None;self.error=''
                elif button==k.BUTTON_CENTER:self.dialog_commit();self.error=''
                else:self.edit_input(button)
            elif self.page!='grid':
                if button==vm.input_manager._key_esc:self.page,self.pending,self.after_save='grid',None,None;self.error=''
                elif button in (k.BUTTON_UP,k.BUTTON_DOWN):self.selected=(self.selected+(-1 if button==k.BUTTON_UP else 1))%max(1,len(self.menu_items()))
                elif button==k.BUTTON_CENTER:self.menu_choose()
                elif self.page=='plot_setup' and button in (k.BUTTON_LEFT,k.BUTTON_RIGHT) and self.selected in (0,5):
                    if self.selected==0:self.cycle_plot_type(-1 if button==k.BUTTON_LEFT else 1)
                    else:self.menu_choose()
            elif self.editing:
                if button==vm.input_manager._key_esc:self.editing=False;self.error=''
                elif button in (k.BUTTON_CENTER,k.BUTTON_TAB):self.commit(button==k.BUTTON_TAB)
                else:self.edit_input(button)
            elif button==vm.input_manager._key_esc:
                if self.error:self.resume()
                else:self.guard('quit')
            elif button==k.BUTTON_F2:self.page,self.selected='actions',0
            elif button==k.BUTTON_F3:self.anchor=None if self.anchor is not None else self.position
            elif button==k.BUTTON_F4:self.copy()
            elif button==k.BUTTON_F5:self.paste()
            elif button==k.BUTTON_F6:self.open_plot_setup()
            elif button==k.BUTTON_F7:self.prompt('goto','')
            elif button==k.BUTTON_F8:
                current=self.sheet.widths.get(self.col,72);options=(48,72,96,120)
                self.sheet.widths[self.col]=options[(options.index(current)+1)%4] if current in options else 72
                self.sheet.dirty=True;self.reveal()
            elif button in (k.BUTTON_DELETE,k.BUTTON_BACKSPACE):self.clear_selection();self.calc_paused=False
            elif button==k.BUTTON_CENTER:self.begin()
            elif button in (k.BUTTON_UP,k.BUTTON_DOWN,k.BUTTON_LEFT,k.BUTTON_RIGHT,k.BUTTON_TAB,k.BUTTON_CTRL_UP,k.BUTTON_CTRL_DOWN):
                self.message=''
                if button==k.BUTTON_UP:self.row=max(0,self.row-1)
                elif button==k.BUTTON_DOWN:self.row=min(ROWS-1,self.row+1)
                elif button in (k.BUTTON_LEFT,k.BUTTON_CTRL_UP):self.col=max(0,self.col-1)
                else:self.col=min(COLS-1,self.col+1)
                self.reveal()
            else:
                char=vm.input_manager.button_to_char(button)
                if char and char not in ('\n','\r','\t'):self.begin(char)
        except Exception as exc:
            if self.page=='csv_browser':self.browser=None;self.page='grid'
            self.report_error(exc)
        if self.vm is not None and not self.suspended:self.safe_draw()

    def menu_items(self):
        if self.page=='plot_setup':
            p=self.plot_options
            return ('Type: '+CHART_LABELS[CHART_TYPES.index(p['style'])],
                    ('Labels: ' if p['style'] in ('column','pie') else 'X: ')+(p['x'] or 'Worksheet row'),
                    'Y1: '+(p['ys'][0] or '(none)'), 'Y2: '+('unused for pie' if p['style']=='pie' else p['ys'][1] or '(none)'),
                    'Y3: '+('unused for pie' if p['style']=='pie' else p['ys'][2] or '(none)'),
                    'First row headers: '+('Yes' if p['header'] else 'No'),'Draw plot')
        if self.page=='file': return FILE_ITEMS
        if self.page=='actions': return ACTIONS
        if self.page=='fill_direction':return ('Fill down: use top row','Fill right: use left column')
        if self.page=='convert_confirm':return ('Replace formulas with values','Cancel')
        if self.page=='recovery':return ('Resume without recalculating','Edit selected cell','Undo last cell edit','Recalculate','Convert selection to values','Save recovery copy')
        if self.page=='files': return self.files
        if self.page=='confirm': return ('Save then continue','Discard changes','Keep editing')
        if self.page=='overwrite': return ('Replace existing file','Cancel')
        return ()

    def entry_text(self,r,x,y,width):
        # Follow the caret horizontally without changing the underlying input.
        capacity=max(1,width//8)
        self.offset=max(0,min(self.offset,self.cursor))
        if self.cursor>=self.offset+capacity: self.offset=self.cursor-capacity+1
        r.text(x,y,self.buffer[self.offset:self.offset+capacity],self.vm.foreground_color,SMALL)
        caret=x+(self.cursor-self.offset)*8
        r.line(caret,y,caret,y+12,self.vm.selected_color)

    def draw(self):
        vm=self.vm;d=vm.draw
        width,height=int(d.size.x),int(d.size.y)
        fg,bg,accent=vm.foreground_color,vm.background_color,vm.selected_color
        panel=blend(bg,fg,1,12);grid=blend(bg,fg,1,4);muted=blend(bg,fg,2,3)
        selected=blend(bg,accent,1,4)
        # Choose readable text when a theme-colour header is filled.
        from picoware.gui.status_bar import foreground
        contrast=foreground(accent)
        d.fill_screen(bg)
        from engtools.ui import theme
        path='Eggcel'+(' / '+self.page.replace('_',' ').upper() if self.page!='grid' else '')
        theme.header(d,path,'PicoDESK',theme.system_palette(vm),height=18)
        r=self.renderer()
        r.fill(0,18,width,23,panel)
        r.fill(6,23,13,13,accent)
        for n in (1,2):
            r.line(6+n*4,23,6+n*4,35,contrast)
            r.line(6,23+n*4,18,23+n*4,contrast)
        r.text(25,24,'Eggcel',fg,SMALL)
        title=(self.filename.rsplit('/',1)[-1][:-4] if self.filename else 'Untitled')+(' *' if self.sheet.dirty else '')
        r.text(max(91,width-8-min(len(title),26)*6),26,title[-26:],muted,TINY)
        if self.page!='grid':
            self.draw_page(r,width,height,fg,bg,accent,panel,muted,selected)
            d.swap();return
        self.reveal()
        r.fill(4,46,width-8,43,panel)
        r.rect(4,46,width-8,43,accent if self.editing else grid)
        r.text(11,54,address(*self.position),accent,SMALL)
        r.line(51,48,51,85,grid)
        r.text(59,54,'fx',muted,SMALL)
        if self.editing:
            entry=self.renderer((80,49,width-10,70))
            self.entry_text(entry,81,54,width-94)
            detail='EDIT CELL'
        else:
            raw=self.sheet.cells.get(self.position,'')
            r.text(81,54,raw[:max(1,(width-91)//8)],fg,SMALL)
            value=self.sheet.peek(self.position)
            detail=('FORMULA  '+format_value(value,self.sheet.style)) if raw.startswith('=') else (
                'TEXT' if isinstance(value,str) else ('NUMBER' if value is not None else 'EMPTY CELL'))
        r.text(59,75,detail[:max(1,(width-69)//6)],muted,TINY)
        columns=self.visible_columns();count=self.visible_rows
        top,left,bottom,right=self.bounds
        r.fill(4,96,24,18,panel)
        for col,x,size in columns:
            active=left<=col<=right
            r.fill(x,96,size,18,accent if active else panel)
            r.text(x+(size-8)//2,99,chr(65+col),contrast if active else muted,SMALL)
        for row in range(self.top,min(ROWS,self.top+count)):
            y=114+(row-self.top)*22
            if y+22>self.bottom-15-(52 if self.error else 0): break
            active=top<=row<=bottom
            r.fill(4,y,24,22,accent if active else panel)
            label=str(row+1)
            r.text(25-len(label)*6,y+7,label,contrast if active else muted,TINY)
            for col,x,size in columns:
                marked=top<=row<=bottom and left<=col<=right
                if marked: r.fill(x,y,size,22,selected)
                r.rect(x,y,size+1,23,grid)
                value=self.sheet.peek((row,col));text=format_value(value,self.sheet.style)
                font=TINY if isinstance(value,str) or isinstance(value,CellError) else SMALL
                if font==SMALL and len(text)*8>size-10: font=TINY
                cw=6 if font==TINY else 8
                capacity=max(1,(size-10)//cw)
                if len(text)>capacity:
                    if isinstance(value,(int,float)) and not isinstance(value,bool): text='#'*capacity
                    else: text=text[:max(1,capacity-1)]+'~'
                tx=x+5 if isinstance(value,(str,CellError)) else x+size-5-len(text)*cw
                cell=self.renderer((x+2,y+2,x+size-2,y+21))
                cell.text(tx,y+(7 if font==TINY else 5),text,0xF800 if isinstance(value,CellError) else fg,font)
                if (row,col)==self.position:
                    r.rect(x+1,y+1,size-1,21,accent)
                    r.fill(x+size-4,y+18,4,4,accent)
        status_y=self.bottom-12-(52 if self.error else 0)
        r.fill(0,status_y,width,12,panel)
        selection=address(top,left)+(':'+address(bottom,right) if self.anchor is not None else '')
        status=(self.job_kind+' '+str(self.progress)+' / ESC cancel') if self.job is not None else self.message or ('Sheet1  |  '+selection+'  |  '+self.sheet.style+'  |  '+str(len(self.sheet.cells))+'/'+str(MAX_CELLS))
        r.text(6,status_y+2,status[:max(1,(width-12)//6)],fg if self.error else muted,TINY)
        self.draw_footer(r,width,height,accent,muted,panel)
        if self.error:self.draw_error_native()
        d.swap()
        if self.job is None and not self.calc_paused and not self.error and any(raw.startswith('=') and pos not in self.sheet.cache for pos,raw in self.sheet.cells.items()):
            self.start_job(self.sheet.recalculate_job(False),'Calculating')

    def draw_footer(self,r,width,height,accent,muted,panel):
        bottom=self.bottom
        r.fill(0,bottom,width,height-bottom,panel)
        if self.help:
            first='ENTER edit/set  ARROWS move  ESC cancel/back' if self.page=='grid' else 'UP/DOWN choose  ENTER open  ESC returns'
            r.text(6,bottom+3,first[:(width-12)//6],accent,TINY)
            r.text(6,bottom+15,'F1 File F2 Actions F3 Range F4 Copy F5 Paste'[:(width-12)//6],muted,TINY)
            r.text(6,bottom+26,'F6 Plot F7 Go F8 Width F9 Hide TAB next'[:(width-12)//6],muted,TINY)
        else: r.text(6,bottom+3,'F1 File   F2 Actions   F9 Help',accent,TINY)

    def draw_page(self,r,width,height,fg,bg,accent,panel,muted,selected):
        title={'file':'FILE','actions':'ACTIONS','files':'IMPORT CSV' if self.purpose=='import' else 'OPEN WORKBOOK',
               'confirm':'UNSAVED CHANGES','overwrite':'REPLACE FILE?', 'plot_setup':'PLOT / CHART', 'fill_direction':'FILL DIRECTION', 'convert_confirm':'CONVERT TO VALUES', 'recovery':'RECOVERY',
               'dialog':('PLOT RANGE' if self.purpose.startswith('plot_') else self.purpose.upper())}.get(self.page,'')
        r.text(9,53,title,accent,SMALL)
        if self.page=='dialog':
            r.fill(8,86,width-16,34,panel);r.rect(8,86,width-16,34,accent)
            entry=self.renderer((13,89,width-13,117))
            self.entry_text(entry,16,98,width-37)
            note=('Column range: A2:A20; blank = rows/off' if self.purpose.startswith('plot_') else
                  'Address: A1 through Z200' if self.purpose=='goto' else 'SD: '+DIRECTORY)
            r.text(9,134,note[:(width-18)//6],muted,TINY)
            r.text(9,152,'Type replaces | arrows edit | ENTER set',muted,TINY)
        else:
            items=self.menu_items()
            capacity=max(1,(self.bottom-90-(52 if self.error else 0))//25)
            first=max(0,self.selected-capacity+1)
            for index in range(first,min(len(items),first+capacity)):
                y=83+(index-first)*25
                if index==self.selected: r.fill(6,y-4,width-12,24,selected);r.rect(6,y-4,width-12,24,accent)
                r.text(13,y,items[index][:max(1,(width-26)//8)],fg,SMALL)
            if not items: r.text(10,91,'No files in '+DIRECTORY,muted,TINY)
            if self.page=='confirm': r.text(10,177,'Keep edits by saving before continuing.',muted,TINY)
            if self.page=='overwrite' and self.overwrite:
                r.text(10,150,self.overwrite[0].rsplit('/',1)[-1][:48],muted,TINY)
            if self.page=='plot_setup' and not self.error:
                r.text(10,267,'ENTER edits | L/R type/labels | ESC sheet',muted,TINY)
        if self.page=='convert_confirm':
            r.text(9,162,'Formula links will stop updating.',muted,TINY)
            r.text(9,178,'Undo is available until the next edit.',muted,TINY)
        if self.error:self.draw_error_native()
        self.draw_footer(r,width,height,accent,muted,panel)


def show(vm):
    from engtools.plots.view import open_view
    return open_view(vm,'eggcel',Spreadsheet())
