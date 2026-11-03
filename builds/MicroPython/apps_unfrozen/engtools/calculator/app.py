"""Scientific-calculator UI prototype, owned by one PicoLAB session."""
from picoware.system import buttons as keys
from picoware.system.font import FONT_XTRA_SMALL, FONT_SMALL, FONT_MEDIUM, FONT_LARGE
from engtools.ui import theme
from .editor import Editor, Node, clone, source, count
from .evaluate import calculate, format_value
from .render import Renderer

MODES = ('Calculate', 'Statistics', 'Solver', 'Complex', 'Base-N', 'Matrix')
DETAILS = ('Scientific expressions', 'Data, summaries, linear fit', 'Equations and roots',
           'Real + imaginary', 'BIN / OCT / DEC / HEX', 'Arrays and operations')
SUPPORTED = (0, 1, 2, 3, 4, 5)
TEMPLATES = ('pow', 'sub', 'sqrt', 'frac', 'int', 'logb', 'sin', 'cos', 'tan', 'ln', 'pi', 'sum', 'prod')
TEMPLATE_LABELS = ('Power', 'Subscript', 'Square root', 'Fraction', 'Integral (in x)',
                   'Log with base', 'Sine', 'Cosine', 'Tangent', 'Natural log', 'Pi',
                   'Sum (Sigma)', 'Product (Pi)')
HISTORY_LIMIT = 24
HISTORY_ITEM_LIMIT = 1536


class Calculator:
    def __init__(self,compact=False):
        self.compact=compact
        self.vm = None
        self.editor = Editor()
        self.variables = {'Ans': 0}
        self.mode, self.angle, self.engineering = 0, 'DEG', False
        self.page, self.selected = 'calc', 0
        self.history, self.history_index, self.draft = [], None, None
        self.answer, self.assignment, self.error = 0, None, ''
        self.dirty = True
        self.statistics, self.menu_return = None, 'calc'
        self.workspaces={}
        self.show_hints = False
        self.help_open, self.help_first = False, 0

    @property
    def accent(self):
        return self.vm.selected_color

    @property
    def footer_height(self):
        return 36 if self.show_hints else 12

    def renderer(self, draw, clip):
        return Renderer(draw, clip, self.accent, self.palette)

    def footer(self, r, width, height, first, second='', message=''):
        from engtools.ui import breadcrumbs
        breadcrumbs.paint(r.draw,theme.system_palette(self.vm),fallback=('tools','Scientific calculator'))
        bottom = height-self.footer_height
        r.fill(0, bottom, width, self.footer_height, self.palette.PANEL)
        limit = max(1, (width-12)//6)
        if self.show_hints:
            r.text(6, bottom+4, first[:limit], self.accent, FONT_XTRA_SMALL)
            r.text(6, bottom+20, (self.error or message or second)[:limit],
                   self.palette.ERROR if self.error else self.palette.MUTED, FONT_XTRA_SMALL)
        else:
            r.text(6, bottom+2, 'F9 Help', self.accent, FONT_XTRA_SMALL)
            if self.error or message:
                r.text(55, bottom+2, (self.error or message)[:max(1,(width-61)//6)],
                       self.palette.ERROR if self.error else self.palette.MUTED, FONT_XTRA_SMALL)

    def start(self, vm):
        self.vm = vm
        self.palette = theme.system_palette(vm)
        vm.input_manager.reset()
        self.draw()
        return True

    def stop(self, vm):
        # Session history and variables are deliberately RAM-only in this preview.
        self.history, self.variables, self.draft = [], {}, None
        self.editor.clear()
        self.statistics = None
        for workspace in self.workspaces.values():
            if getattr(workspace,'job',None): workspace.job.close()
        self.workspaces={}
        self.vm = None

    def open_page(self, page):
        if self.page in ('calc','stats','solver','base','matrix'): self.menu_return = self.page
        self.page, self.selected = page, self.mode if page == 'modes' else 0

    def statistics_view(self):
        if self.statistics is None:
            from .statistics import Workspace
            self.statistics = Workspace(self)
        return self.statistics

    def choose_mode(self, mode):
        self.mode, self.error, self.menu_return = mode,'','calc'
        if mode == 1:
            self.statistics_view()
            self.page = 'stats'
        elif mode in (2,4,5):
            self.workspace(mode)
            self.page={2:'solver',4:'base',5:'matrix'}[mode]
        else: self.page = 'calc'

    def workspace(self,mode=None):
        mode=self.mode if mode is None else mode
        if mode not in self.workspaces:
            from .workspaces import SolverWorkspace,BaseWorkspace,MatrixWorkspace
            self.workspaces[mode]={2:SolverWorkspace,4:BaseWorkspace,5:MatrixWorkspace}[mode](self)
        return self.workspaces[mode]

    def input_editor(self):
        if self.mode in (2,4,5) and self.menu_return!='calc':
            return self.workspace().editor
        if self.statistics is not None and self.statistics.editing and (
                self.page == 'stats' or (self.page != 'calc' and self.menu_return == 'stats')):
            return self.statistics.editor
        return self.editor

    def edit_key(self, editor, button):
        if button == keys.BUTTON_LEFT: editor.move(-1)
        elif button == keys.BUTTON_RIGHT: editor.move(1)
        elif button in (keys.BUTTON_UP,keys.BUTTON_DOWN): editor.vertical(-1 if button == keys.BUTTON_UP else 1)
        elif button in (keys.BUTTON_TAB,keys.BUTTON_CTRL_DOWN): editor.tab()
        elif button == keys.BUTTON_CTRL_UP: editor.tab(True)
        elif button in (keys.BUTTON_BACKSPACE,self.vm.input_manager._key_back): editor.delete()
        elif button == keys.BUTTON_DELETE: editor.delete()
        else:
            char = self.vm.input_manager.button_to_char(button)
            if char and char not in ('\n','\t'):
                if char == ' ':
                    if not editor.expand(): editor.insert(' ')
                else: editor.insert(char)
                self.error = ''

    def recall(self, direction):
        if not self.history: return
        if self.history_index is None:
            if direction > 0: return
            self.draft = clone(self.editor.root)
            self.history_index = len(self.history)-1
        else:
            target = self.history_index+direction
            if target >= len(self.history):
                self.editor.load(self.draft or [])
                self.history_index, self.draft = None, None
                return
            self.history_index = max(0, target)
        self.editor.load(self.history[self.history_index]['row'])
        self.error = ''

    def submit(self):
        self.error = ''
        if not self.editor.root: return
        if self.mode not in SUPPORTED:
            self.error = MODES[self.mode]+' engine is planned; UI preview only'
            return
        if self.editor.focus_missing():
            self.error = 'Complete the highlighted slot'
            return
        try:
            text = source(self.editor.root)
            dataset = self.statistics.dataset if self.statistics else None
            value, assignment = calculate(text, self.variables, self.angle, self.mode == 3, dataset)
            if not self.compact:
                record = {'row': clone(self.editor.root), 'value': value, 'assignment': assignment,
                          'mode': self.mode, 'angle': self.angle, 'text': text}
                self.history.append(record)
            while len(self.history) > HISTORY_LIMIT or sum(count(entry['row']) for entry in self.history) > HISTORY_ITEM_LIMIT:
                del self.history[0]
            self.answer, self.assignment = value, assignment
            self.history_index, self.draft = None, None
            self.editor.clear()
        except (ValueError, TypeError, ZeroDivisionError, OverflowError, ImportError, RuntimeError) as exc:
            self.error = str(exc) or 'Invalid mathematical operation'

    def run(self, vm):
        button = vm.button
        if not self.help_open and self.page=='solver' and self.workspace().job is not None:
            self.workspace().tick()
            self.draw()
        if button == keys.BUTTON_NONE: return
        try:
            if button == keys.BUTTON_F9:
                self.help_open = not self.help_open
                self.help_first = 0
                self.draw()
                return
            if self.help_open:
                from engtools.ui import lab
                capacity = lab.help_capacity(int(vm.draw.size.y)-lab.FOOT)
                if button == vm.input_manager._key_esc:self.help_open = False
                else:
                    step = {keys.BUTTON_UP:-1, keys.BUTTON_DOWN:1, keys.BUTTON_LEFT:-capacity, keys.BUTTON_RIGHT:capacity}.get(button,0)
                    self.help_first = min(max(0,self.help_first+step),max(0,len(self.help_lines())-capacity))
                self.draw()
                return
            if button == keys.BUTTON_F3:
                self.open_page('options')
                self.draw()
                return
            if self.page == 'options':
                if button == vm.input_manager._key_esc:self.page = self.menu_return
                elif button in (keys.BUTTON_UP,keys.BUTTON_DOWN):self.selected = (self.selected+(-1 if button==keys.BUTTON_UP else 1))%len(self.option_rows())
                elif button == keys.BUTTON_CENTER:self.option_action()
                self.draw()
                return
            # Input remaps Escape/Backspace according to the global exit-key
            # preference. Follow the physical key roles in either configuration.
            if self.page in ('solver','base','matrix'):
                self.workspace().run(button)
                if self.vm is None: return
            elif self.page == 'stats':
                self.statistics_view().run(button)
            elif button == vm.input_manager._key_esc:
                if self.page != 'calc':
                    self.page = self.menu_return
                else:
                    vm.back()
                    return
            elif button in (keys.BUTTON_F1,keys.BUTTON_F2,keys.BUTTON_F4): pass
            elif button == keys.BUTTON_F8: self.open_page('variables')
            elif button == keys.BUTTON_F10:
                self.input_editor().clear()
                self.history_index, self.draft, self.error = None, None, ''
                self.page = self.menu_return if self.page != 'calc' else 'calc'
            elif button == keys.BUTTON_F6:
                if self.page == 'calc':self.submit()
            elif button == keys.BUTTON_F5:
                if self.compact:return
                self.open_page('history')
                self.selected = max(0, len(self.history)-1)
            elif button == keys.BUTTON_F7: self.open_page('templates')
            elif self.page == 'modes':
                row, col = self.selected//3, self.selected%3
                if button == keys.BUTTON_LEFT: col = (col-1)%3
                elif button == keys.BUTTON_RIGHT: col = (col+1)%3
                elif button in (keys.BUTTON_UP, keys.BUTTON_DOWN): row = 1-row
                elif button == keys.BUTTON_CENTER:
                    self.choose_mode(self.selected)
                elif keys.BUTTON_1 <= button <= keys.BUTTON_6:
                    self.choose_mode(button-keys.BUTTON_1)
                if self.page == 'modes': self.selected = row*3+col
            elif self.page == 'variables':
                names = self.variable_names()
                if button in (keys.BUTTON_UP, keys.BUTTON_DOWN):
                    self.selected = (self.selected+(-1 if button == keys.BUTTON_UP else 1))%len(names)
                elif button == keys.BUTTON_CENTER:
                    for char in names[self.selected]: self.input_editor().insert(char)
                    self.page = self.menu_return
                elif button in (keys.BUTTON_DELETE,keys.BUTTON_BACKSPACE) and names[self.selected] != 'Ans':
                    del self.variables[names[self.selected]]
                    self.selected = max(0, self.selected-1)
            elif self.page == 'history':
                if self.history:
                    if button in (keys.BUTTON_UP, keys.BUTTON_DOWN):
                        self.selected = (self.selected+(-1 if button == keys.BUTTON_UP else 1))%len(self.history)
                    elif button == keys.BUTTON_CENTER:
                        self.draft, self.history_index = clone(self.editor.root), self.selected
                        self.editor.load(self.history[self.selected]['row'])
                        self.page, self.error = 'calc', ''
            elif self.page == 'templates':
                if button in (keys.BUTTON_UP, keys.BUTTON_DOWN):
                    self.selected = (self.selected+(-1 if button == keys.BUTTON_UP else 1))%len(TEMPLATES)
                elif button == keys.BUTTON_CENTER:
                    kind = TEMPLATES[self.selected]
                    editor = self.input_editor()
                    if kind in ('pow', 'sub') and editor.index == 0:
                        raise ValueError('Enter a base first')
                    editor.template(kind)
                    self.page, self.error = self.menu_return, ''
            else:
                if button == keys.BUTTON_CENTER: self.submit()
                elif button == keys.BUTTON_LEFT: self.editor.move(-1)
                elif button == keys.BUTTON_RIGHT: self.editor.move(1)
                elif button in (keys.BUTTON_UP, keys.BUTTON_DOWN):
                    direction = -1 if button == keys.BUTTON_UP else 1
                    if not self.editor.vertical(direction) and not self.editor.parents: self.recall(direction)
                elif button == keys.BUTTON_TAB: self.editor.tab()
                elif button == keys.BUTTON_CTRL_UP: self.editor.tab(True)
                elif button == keys.BUTTON_CTRL_DOWN: self.editor.tab()
                elif button in (keys.BUTTON_BACKSPACE, vm.input_manager._key_back): self.editor.delete()
                elif button == keys.BUTTON_DELETE: self.editor.delete()
                else:
                    char = vm.input_manager.button_to_char(button)
                    if char and char not in ('\n', '\t'):
                        if char == ' ':
                            if not self.editor.expand(): self.editor.insert(' ')
                        else: self.editor.insert(char)
                        self.error = ''
        except (ValueError, MemoryError, TypeError, ZeroDivisionError, OverflowError, ImportError, RuntimeError, OSError) as exc:
            self.error = str(exc)
        self.dirty = True
        self.draw()

    def variable_names(self):
        return ['Ans']+sorted(name for name in self.variables if name != 'Ans')

    def help_lines(self):
        common = ('Scientific calculator / '+MODES[self.mode]+':',
                'F3 Options: modes, settings and tools',
                'F6 Evaluate / Calculate; ENTER also accepts',
                'F5 Results (history in Calculate/Complex)',
                'F7 Templates; F8 Variables; F10 Clear input',
                'F1/F2 add/remove rows in Statistics data',
                'Other modes have no collection action',
                'F4 is reserved for graphical plots',
                'Editing:', 'Arrows move through expressions or cells',
                'TAB moves mathematical slots or table cells',
                'CTRL-UP previous slot; CTRL-DOWN next slot',
                'SPACE expands mathematical shorthand',
                'Back and Delete erase before the caret',
                'ESC cancels an edit or returns',
                'F9 help preserves the draft and selection',
                'UP/DOWN history in Calculate/Complex',
                'Options:', 'Statistics tools: Data, Fit, frequency and CSV',
                'Solver setup changes polynomial degree / system size',
                'Matrix setup selects names and dimensions',
                'Base-N setup changes base / width / signedness')
        details = (
            ('Expression entry:', 'Type 2^ SPACE to create an exponent slot',
             'sqrt(), frac(), int(), logb(): SPACE expands',
             'sum(), prod(): SPACE creates Sigma / Pi',
             'TAB: lower, upper, expression; k is the index',
             'sum(k,1,10,k^2); prod(k,1,5,k)',
             'Sum/product: inclusive integers, 1024 terms',
             'TAB steps fraction / integral / log slots',
             'Assignments: a=12; Ans keeps the last answer',
             'DEG/RAD and engineering format: Options'),
            ('Statistics data:', 'ENTER edits; TAB accepts and moves across',
             'F1 inserts a row; F2 removes the selected row',
             'F5 Summary; Options / Fit for regression',
             'Options / Statistics tools: CSV, frequency',
             'ENTER on a result uses its value as Ans'),
            ('Solver:', 'ENTER edits equation, bounds or coefficients',
             'F6 solves; ESC cancels an active job',
             'Options / Mode setup: degree or system size',
             'Equation uses x; bounded root finding',
             'F5 returns to retained solver results'),
            ('Complex expressions:', 'Use i or j for the imaginary unit',
             'Example: (1+2i)*(3-4i)',
             'Templates and structured slots: F7 / TAB',
             'F6 or ENTER evaluates; F5 opens history'),
            ('Base-N:', 'Options / Mode setup: base, bits and sign',
             'F7 lists AND OR XOR NOT and shifts',
             '0b / 0o / 0x override the input base',
             'F6 or ENTER evaluates; arithmetic wraps'),
            ('Matrix:', 'Options / Mode setup: MatA..MatD and sizes',
             'Arrows select cells; ENTER edits; F6 accepts',
             'inv(MatA), det(MatA), trn(MatA), MatA*MatB',
             'F6 evaluates expressions; F5 retains results'))
        return common + details[self.mode]

    def option_rows(self):
        rows = [('Angle unit',self.angle), ('Number format','Engineering' if self.engineering else 'Normal'),
                ('Mode',MODES[self.mode]), ('Variables','Insert a stored value'),
                ('History','Recall a calculation'), ('Clear input','Erase the active draft')]
        if self.mode == 1:rows += [('Data','Open the statistics table'),('Fit','Regression results'),('Statistics tools','Frequency and CSV')]
        elif self.mode in (2,4,5):rows += [('Mode setup','Degree / size' if self.mode==2 else 'Base / width / sign' if self.mode==4 else 'Matrix names / dimensions')]
        return rows

    def option_action(self):
        index = self.selected
        if index == 0:self.angle = 'RAD' if self.angle == 'DEG' else 'DEG'
        elif index == 1:self.engineering = not self.engineering
        elif index == 2:
            if self.compact:raise ValueError('Widget uses Calculate; open PicoLAB for other modes')
            self.open_page('modes')
        elif index == 3:self.open_page('variables')
        elif index == 4:self.open_page('history');self.selected=max(0,len(self.history)-1)
        elif index == 5:self.input_editor().clear();self.error='';self.page=self.menu_return
        elif self.mode == 1:
            workspace = self.statistics_view()
            if workspace.editing:raise ValueError('Commit the cell or press ESC first')
            if workspace.dataset is None and index != 6:raise ValueError('Choose a dataset first')
            workspace.return_page = workspace.page
            workspace.page = ('data' if workspace.dataset is not None else 'start') if index == 6 else ('fit' if index == 7 else 'options')
            workspace.selected = 0
            self.page = 'stats'
        else:
            workspace = self.workspace()
            if workspace.editing and self.mode != 4 and not (self.mode == 5 and workspace.page == 'entry'):
                raise ValueError('Commit the cell or press ESC first')
            self.page = self.menu_return
            workspace.run(keys.BUTTON_F3)

    def draw(self):
        if self.help_open:
            from engtools.ui import lab
            draw = self.vm.draw
            draw.fill_screen(self.palette.BG)
            lab.chrome(draw,self.palette,'Help',title='SCIENTIFIC CALCULATOR',fallback=('tools','Scientific calculator'))
            lab.help_box(draw,self.palette,self.help_lines(),self.help_first,int(draw.size.y)-lab.FOOT)
            draw.swap()
            return
        draw = self.vm.draw
        width, height = int(draw.size.x), int(draw.size.y)
        if self.compact and self.page=='calc':
            self.draw_widget(draw,width,height)
            self.dirty=False
            return
        draw.fill_screen(self.palette.BG)
        if self.page in ('solver','base','matrix'):
            self.workspace().draw(draw,width,height)
            self.dirty=False
            return
        if self.page == 'stats':
            self.statistics_view().draw(draw,width,height)
            self.dirty = False
            return
        if self.page != 'calc':
            self.draw_page(draw, width, height)
            self.dirty = False
            return
        r = self.draw_top(draw,width,height)
        # Prompt uses the lower portion of the shared prompt/history panel.
        bottom = height-self.footer_height
        prompt_top = bottom-74
        r.rect(8, 122, width-16, bottom-122-3, self.palette.GRID)
        r.text(16, 129, 'SESSION HISTORY', self.palette.MUTED, FONT_XTRA_SMALL)
        if not self.history and self.show_hints:
            instructions = ('Type 2^ then SPACE for a power', '2/ or log_ + SPACE for slots',
                            'Assign a=3; use it in 2a+1') if self.mode in SUPPORTED else (
                            MODES[self.mode]+' mode preview', DETAILS[self.mode], 'Numerical workflow comes next')
            if self.mode == 1:
                instructions = ('mean(X), std(X), sum(X), predict(x)',
                                'F3 Options / Data opens the table', 'std = sample; pstd = population')
            for i, text in enumerate(instructions): r.text(16, 146+i*16, text, self.palette.MUTED, FONT_XTRA_SMALL)
        elif self.history:
            anchor = self.history_index if self.history_index is not None else len(self.history)-1
            hr = self.renderer(draw, (16, 144, width-16, prompt_top-3))
            shown, used = [], 0
            for index in range(anchor, max(-1, anchor-2), -1):
                record = self.history[index]
                needed = hr.layout(record['row'], FONT_XTRA_SMALL).h+13
                if shown and used+needed > prompt_top-147: break
                needed = min(needed, prompt_top-147)
                shown.insert(0, (record, needed))
                used += needed
            y = prompt_top-3-used
            for record, available in shown:
                prefix = '* ' if self.history_index is not None and record is self.history[anchor] else '  '
                hr.text(16, y, prefix, self.accent, FONT_XTRA_SMALL)
                # A separate clipped row for each history entry prevents nested
                # fractions/roots from spilling into the neighbouring entry.
                line = self.renderer(draw, (30, y, width-16, y+available-10))
                line.expression(record['row'], 30, y, FONT_XTRA_SMALL, self.palette.MUTED)
                hr.text(30, y+available-10, '= '+format_value(record['value']), self.accent, FONT_XTRA_SMALL)
                y += available
        r.line(9, prompt_top, width-10, prompt_top, self.palette.GRID)
        r.text(16, prompt_top+7, '>>', self.accent, FONT_SMALL)
        editor_bottom = bottom-20 if self.show_hints or self.error else bottom-5
        editor_renderer = self.renderer(draw, (40, prompt_top+5, width-17, editor_bottom))
        editor_renderer.expression(self.editor.root, 43, prompt_top+9, editor=self.editor, follow=True)
        hint = self.error or (self.editor.hint() if self.mode in SUPPORTED else 'UI preview | mode engine follows')
        hint_font = FONT_XTRA_SMALL
        if len(hint) > (width-30)//6: hint = hint[:(width-30)//6-3]+'...'
        if self.show_hints or self.error:
            r.text(16, bottom-15, hint, self.palette.ERROR if self.error else self.palette.MUTED, hint_font)
        self.footer(r,width,height,'F3 Options  F6 Calculate  F8 Vars',
                    'F10 Clear F5 History F7 Math F9 Help ESC Lab')
        draw.swap()
        self.dirty = False

    def draw_widget(self,draw,width,height):
        fg,bg,accent=self.vm.foreground_color,self.vm.background_color,self.accent
        draw.fill_screen(bg)
        r=self.renderer(draw,(0,0,width,height))
        r.text(7,5,'CALCULATE  '+self.angle,accent,FONT_XTRA_SMALL)
        r.line(6,18,width-7,18,self.palette.GRID)
        r.text(9,25,'ANSWER'+(' '+self.assignment if self.assignment else ''),self.palette.MUTED,FONT_XTRA_SMALL)
        result=format_value(self.answer,self.engineering)
        font=FONT_MEDIUM if draw.len(result,FONT_MEDIUM)<=width-18 else FONT_SMALL
        if draw.len(result,font)>width-18: font=FONT_XTRA_SMALL
        r.text(max(9,width-9-draw.len(result,font)),42,result,accent,font)
        footer_height = 24 if self.show_hints else 12
        bottom = height-footer_height
        prompt_bottom = bottom-(14 if self.show_hints or self.error else 4)
        r.rect(6,75,width-12,prompt_bottom-75,self.palette.GRID)
        r.text(12,82,'>>',accent,FONT_SMALL)
        prompt=self.renderer(draw,(34,80,width-12,prompt_bottom-4))
        prompt.expression(self.editor.root,36,83,FONT_SMALL,fg,editor=self.editor,follow=True)
        hint=self.error or self.editor.hint()
        if self.show_hints or self.error:
            r.text(7,bottom-11,hint[:max(1,(width-14)//6)],self.palette.ERROR if self.error else self.palette.MUTED,FONT_XTRA_SMALL)
        if self.show_hints:
            r.text(7,bottom+3,'F3 Opt F8 Vars F7 Math',accent,FONT_XTRA_SMALL)
            r.text(7,bottom+14,'ENTER= F10 Clear F9 Help ESC',self.palette.MUTED,FONT_XTRA_SMALL)
        else:
            r.text(7,bottom+2,'F9 Help',accent,FONT_XTRA_SMALL)
        draw.swap()

    def draw_top(self, draw, width, height, label=None, value=None, status=None):
        r = self.renderer(draw,(0,18,width,height))
        r.fill(0,18,width,20,self.palette.PANEL)
        r.text(8,22,status or MODES[self.mode],self.accent)
        if status is None:
            r.text(width-144,22,self.angle,self.palette.TEXT)
            r.text(width-104,22,'ENG' if self.engineering else 'NORM',self.palette.MUTED)
            r.text(width-54,22,'M' if len(self.variables)>1 else '',self.accent)
            r.text(width-28,22,'i' if self.mode == 3 else '',self.accent)
        r.fill(8,43,width-16,73,self.palette.PANEL)
        r.rect(8,43,width-16,73,self.palette.GRID)
        caption = label if label is not None else 'ANSWER'+('  '+self.assignment if self.assignment else '')
        r.text(17,50,caption[:46],self.palette.MUTED,FONT_XTRA_SMALL)
        number = self.answer if value is None else value
        text = number if isinstance(number,str) else format_value(number,self.engineering)
        font = FONT_LARGE if draw.len(text,FONT_LARGE) <= width-36 else FONT_MEDIUM
        row = list(text)
        if 'e' in text and not isinstance(number,(complex,str)):
            mantissa, exponent = text.split('e')
            row = list(mantissa+'*10')+[Node('pow',[list(str(int(exponent)))])]
        ar = self.renderer(draw,(16,65,width-16,106))
        box = ar.layout(row,font)
        if box.w > width-32: font = FONT_SMALL; box = ar.layout(row,font)
        ar.expression(row,max(16,width-18-box.w),69,font,self.accent)
        return r

    def draw_page(self, draw, width, height):
        if self.page == 'modes':
            r = self.renderer(draw, (0, 18, width, height))
            r.fill(0, 18, width, 24, self.palette.PANEL)
            r.text(9, 24, 'CALCULATOR / MODE', self.accent)
            gap, margin = 6, 8
            tilew = (width-2*margin-2*gap)//3
            for i, label in enumerate(MODES):
                x, y = margin+(i%3)*(tilew+gap), 68+(i//3)*83
                chosen = i == self.selected
                r.fill(x, y, tilew, 75, self.palette.SELECT if chosen else self.palette.PANEL)
                r.rect(x, y, tilew, 75, self.accent if chosen else self.palette.GRID)
                r.text(x+7, y+7, str(i+1), self.accent, FONT_XTRA_SMALL)
                # Small mode-specific sketches are drawn, not loaded images.
                icon = self.renderer(draw, (x+4, y+16, x+tilew-4, y+48))
                sketches = ('x + y', 'x  s', 'x = ?', 'a + bi', '01 AF', '[a b]')
                icon.text(x+(tilew-len(sketches[i])*8)//2, y+26, sketches[i], self.palette.TEXT, FONT_SMALL)
                r.text(x+(tilew-draw.len(label, FONT_SMALL))//2, y+55, label,
                       self.palette.TEXT if chosen else self.palette.MUTED, FONT_SMALL)
            r.text(9, 245, DETAILS[self.selected], self.accent, FONT_SMALL)
            r.text(9, 264, 'Ready' if self.selected in SUPPORTED else 'UI preview; engine planned', self.palette.MUTED, FONT_XTRA_SMALL)
            self.footer(r,width,height,'ARROWS choose  ENTER open',
                        '1-6 select  F9 Help  ESC returns')
            draw.swap()
            return
        if self.page == 'options':
            rows = self.option_rows()
            hint = 'ENTER changes | RAM history; no SD writes'
        elif self.page == 'variables':
            names = self.variable_names()
            rows = [(name, format_value(self.variables[name])) for name in names]
            hint = 'ENTER inserts | DELETE removes | a=3 assigns'
        elif self.page == 'templates':
            rows = [(label, {'frac':'numerator/ + SPACE', 'logb':'log_ + SPACE: base, argument'}.get(kind, kind+'() + SPACE') if kind not in ('pow', 'sub', 'pi') else
                     {'pow':'^ + SPACE', 'sub':'_ + SPACE', 'pi':'pi + SPACE'}[kind])
                    for kind, label in zip(TEMPLATES, TEMPLATE_LABELS)]
            hint = 'ENTER inserts | TAB slots | CTRL-UP previous'
        else:
            rows = [(record['text'], '= '+format_value(record['value'])) for record in self.history]
            if not rows: rows = [('No calculations yet', 'History is kept only while the calculator is open')]
            hint = 'ENTER recalls | last 24 | saving OFF'
        r = self.renderer(draw, (0, 18, width, height))
        r.fill(0, 18, width, 24, self.palette.PANEL)
        r.text(9, 24, 'CALCULATOR / '+self.page.upper(), self.accent)
        capacity = max(1, (height-self.footer_height-51)//29)
        first = max(0, self.selected-capacity+1)
        for index in range(first, min(len(rows), first+capacity)):
            y = 52+(index-first)*29
            if index == self.selected: r.fill(8, y-3, width-16, 27, self.palette.SELECT)
            label, detail = rows[index]
            r.text(15, y, label[:(width-30)//8], self.palette.TEXT, FONT_SMALL)
            r.text(15, y+14, detail[:(width-30)//6], self.palette.MUTED, FONT_XTRA_SMALL)
        self.footer(r,width,height,hint,'UP/DOWN choose  F9 Help  ESC returns')
        draw.swap()


_active = None


class CalculatorView:
    def __init__(self,compact=False): self.compact=compact; self.app=None
    def start(self, vm):
        global _active
        self.app = Calculator(self.compact)
        _active = self.app
        return self.app.start(vm)

    def run(self, vm):
        if self.app is not None: self.app.run(vm)

    def stop(self, vm):
        global _active
        if self.app is not None: self.app.stop(vm)
        self.app, _active = None, None


def show(vm):
    from engtools.plots.view import open_view
    return open_view(vm, 'eng_calculator', CalculatorView())
