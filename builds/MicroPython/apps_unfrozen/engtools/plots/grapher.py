"""Unified Grapher workspace. Only the selected mode's engine is resident."""

from .document import example, normalize
from .runtime import prepare
from engtools.ui import theme, lab
from picoware.system import buttons as k

SESSION = 'picoware/settings/grapher/session.json'
LIMIT = 32768
HELP = ('Grapher:', 'F2 switches 2D / 3D at the plot', 'F3 or ESC opens the Grapher menu',
        'Each mode keeps its own working plot', 'ARROWS pan   + / - zoom   F fit',
        'ENTER edits expressions   W settings', '3D: SPACE changes pan / orbit',
        'Plot options opens mode-specific tools', 'F9 shows these workspace controls',
        'Save session keeps both working plots', 'ESC in this menu saves and closes')
ROWS = (('Continue', 'return to the plot'), ('2D plot', 'curves, expressions and sampled data'),
        ('3D plot', 'surfaces, contours and heat maps'), ('Plot options', 'expressions, ranges and presets'),
        ('Examples', 'isolated mathematical and data fixtures'), ('Save session', 'both working plots'),
        ('Help', 'Grapher controls'), ('Quit', 'save and return'))
EXAMPLES = ('Expression and samples', 'Implicit region', 'Parametric curve',
            'Height surface', 'Implicit sphere', 'Heat map')


def fixture(index):
    document = example('2d' if index < 3 else '3d')
    document['title'] = EXAMPLES[index]
    source = document['sources']['f']
    if index == 0:
        from math import sin
        document['sources']['data'] = {'kind': 'samples', 'points': [(i / 4, sin(i / 4)) for i in range(-24, 25)]}
        document['layers'] += [{'source': 'data', 'style': 'scatter', 'marker': 'cross', 'name': 'Samples'}]
        document['axes'] = {'x': {'bounds': [-6, 6]}, 'y': {'bounds': [-1.5, 1.5]}}
    elif index == 1:
        source['expression'] = 'x^2+y^2<=9'
    elif index == 2:
        source['expression'] = '3*cos(t);2*sin(t)'
    elif index == 3:
        source['expression'] = '0.12*(x^2-y^2)'
    elif index == 4:
        source['expression'] = 'x^2+y^2+z^2=4'
    elif index == 5:
        document['view']['style'] = 'heatmap'
    return document


class Grapher:
    def __init__(self):
        self.documents = {'2d': example('2d'), '3d': example('3d')}
        self.mode = '2d'
        self.viewer = self.vm = None
        self.page, self.row, self.message = 'plot', 0, ''
        self.error = False
        self.opened = False
        self.saved_on_exit = False

    def start(self, vm):
        self.vm = vm
        from engtools.ui import breadcrumbs
        if breadcrumbs.current(vm) is None:
            breadcrumbs.bind(vm, ('tools', 'Grapher'))
        try:
            storage = vm.storage
            path = SESSION if storage.exists(SESSION) else SESSION + '.bak'
            if storage.exists(path):
                if storage.size(path) > LIMIT:
                    raise ValueError('Saved Grapher session is too large')
                from json import loads
                saved = loads(storage.read(path))
                if saved.get('kind') != 'grapher-session' or saved.get('version') != 1 or saved.get('mode') not in ('2d', '3d'):
                    raise ValueError('Unsupported Grapher session')
                documents = {mode: normalize(saved['documents'][mode]) for mode in ('2d', '3d')}
                if any(documents[mode]['view']['mode'] != mode for mode in documents):
                    raise ValueError('Saved plot mode does not match its workspace')
                self.documents, self.mode = documents, saved['mode']
                if path != SESSION and not storage.rename(path, SESSION):
                    raise ValueError('Could not restore Grapher session backup')
                if storage.exists(SESSION + '.bak') and not storage.remove(SESSION + '.bak'):
                    raise ValueError('Could not clear old Grapher session backup')
            self.open_mode(self.mode)
        except Exception as exc:
            self.page, self.message, self.error = 'menu', str(exc), True
            self.draw_menu()
        return True

    def capture(self):
        if self.viewer is not None:
            self.documents[self.mode] = self.viewer.snapshot()

    def release(self):
        if self.viewer is not None:
            self.viewer.close()
            self.viewer = None

    def open_mode(self, mode, document=None):
        self.capture()
        self.release()
        if document is not None:
            self.documents[mode] = document
        viewer = prepare(self.documents[mode])
        try:
            viewer.start(self.vm)
        except Exception:
            viewer.close()
            raise
        self.viewer, self.mode, self.page = viewer, mode, 'plot'
        self.opened = True
        self.vm.input_manager.reset()

    def save(self):
        if not self.opened:
            return
        self.capture()
        from json import dumps
        data = dumps({'kind': 'grapher-session', 'version': 1, 'mode': self.mode, 'documents': self.documents})
        if len(data.encode('utf-8')) > LIMIT:
            raise ValueError('Session exceeds 32 KB')
        storage = self.vm.storage
        for path in ('picoware/settings', 'picoware/settings/grapher'):
            if not storage.exists(path) and not storage.mkdir(path):
                raise ValueError('Could not create Grapher settings folder')
        temporary, backup = SESSION + '.tmp', SESSION + '.bak'
        if not storage.write(temporary, data) or storage.read(temporary) != data:
            storage.remove(temporary)
            raise ValueError('Could not verify Grapher session')
        existed = storage.exists(SESSION)
        if storage.exists(backup):
            raise ValueError('Session backup exists; reopen Grapher to recover')
        if existed and not storage.rename(SESSION, backup):
            raise ValueError('Could not back up Grapher session')
        if not storage.rename(temporary, SESSION):
            if existed:
                storage.rename(backup, SESSION)
            raise ValueError('Could not replace session; previous file or .bak kept')
        if existed and not storage.remove(backup):
            raise ValueError('Session saved; old .bak could not be removed')
        self.message, self.error = 'Session saved', False

    def draw_menu(self):
        rows = [(name, '') for name in EXAMPLES] if self.page == 'examples' else self.viewer.option_rows() if self.page == 'options' else ROWS
        theme.menu(self.vm.draw, rows,
                   self.row, 'Grapher / ' + self.mode.upper(), message=self.message,
                   error=self.error, palette=theme.system_palette(self.vm))

    def run(self, vm):
        button = vm.button
        try:
            if self.page == 'plot':
                if self.viewer.root() and button in (k.BUTTON_F2, k.BUTTON_F3, k.BUTTON_ESCAPE, k.BUTTON_F9):
                    vm.input_manager.reset()
                    if button == k.BUTTON_F2:
                        self.open_mode('3d' if self.mode == '2d' else '2d')
                    elif button == k.BUTTON_F9:
                        self.help()
                    else:
                        self.page, self.row = 'menu', 0
                        self.draw_menu()
                else:
                    self.viewer.run(vm)
                    if self.viewer is not None and self.viewer.in_menu():
                        self.page, self.row = 'options', 0
                        self.draw_menu()
                return
            if button == k.BUTTON_NONE:
                return
            vm.input_manager.reset()
            if self.page == 'help':
                if button in (k.BUTTON_ESCAPE, k.BUTTON_F9, k.BUTTON_CENTER):
                    self.page = self.help_return
                    if self.page == 'plot':
                        self.viewer.redraw()
                    else:
                        self.draw_menu()
                return
            if button in (k.BUTTON_UP, k.BUTTON_DOWN):
                count = len(EXAMPLES) if self.page == 'examples' else len(self.viewer.option_rows()) if self.page == 'options' else len(ROWS)
                self.row = (self.row + (1 if button == k.BUTTON_DOWN else -1)) % count
            elif button == k.BUTTON_F9:
                self.help()
                return
            elif button == k.BUTTON_ESCAPE:
                if self.page in ('examples', 'options'):
                    self.page, self.row = 'menu', 4 if self.page == 'examples' else 3
                else:
                    self.save()
                    self.saved_on_exit = True
                    vm.back()
                    return
            elif button == k.BUTTON_CENTER:
                self.message, self.error = '', False
                if self.page == 'options':
                    self.viewer.options(self.row)
                    self.page = 'plot'
                    return
                if self.page == 'examples':
                    doc = fixture(self.row)
                    self.open_mode(doc['view']['mode'], doc)
                    return
                if self.row == 0:
                    if self.viewer is None:
                        self.open_mode(self.mode)
                    else:
                        self.page = 'plot'
                        self.viewer.redraw()
                    return
                if self.row in (1, 2):
                    self.open_mode('2d' if self.row == 1 else '3d')
                    return
                if self.row == 3:
                    if self.viewer is None:
                        self.open_mode(self.mode)
                    self.page, self.row = 'options', 0
                    self.draw_menu()
                    return
                if self.row == 4:
                    self.page, self.row = 'examples', 0
                elif self.row == 5:
                    self.save()
                elif self.row == 6:
                    self.help()
                    return
                elif self.row == 7:
                    self.save()
                    self.saved_on_exit = True
                    vm.back()
                    return
            self.draw_menu()
        except Exception as exc:
            self.page, self.row, self.message, self.error = 'menu', 0, str(exc), True
            self.draw_menu()

    def help(self):
        self.help_return = self.page
        self.page = 'help'
        palette = theme.system_palette(self.vm)
        lab.help_box(self.vm.draw, palette, HELP, 0, int(self.vm.draw.size.y) - lab.FOOT)
        lab.chrome(self.vm.draw, palette, 'Grapher help')
        self.vm.draw.swap()

    def stop(self, vm):
        self.capture()
        self.release()
        try:
            if not self.saved_on_exit:
                self.save()
        except Exception as exc:
            print('[Grapher] Save:', exc)
        self.documents = {}
        self.vm = None


def show(vm):
    from .view import open_view
    return open_view(vm, 'eng_grapher', Grapher())
