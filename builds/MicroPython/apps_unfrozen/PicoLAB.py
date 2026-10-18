"""PicoLAB engineering-tool launcher and shared plotting preview gallery."""

# (module, title, detail). A module with show(view_manager) opens its own view;
# unfinished tools stay out of the release launcher.
TOOLS = (('engtools.beamlab.app', 'Beam Lab', 'Supports, loads, sections and diagrams'),)

_selected = 0
_gallery_selected = 0
_page = 'tools'
_tool = None
_dirty = True
_resume = False
_error = ''
_bench = None
_bench_rows = []
_bench_info = ''


def start(view_manager):
    global _selected, _gallery_selected, _page, _tool, _dirty, _resume, _error
    if not _resume:
        _selected, _gallery_selected, _page, _tool, _error = 0, 0, 'tools', None, ''
    _resume = False
    _dirty = True
    view_manager.input_manager.reset()
    _draw(view_manager)
    return True


def _draw(view_manager):
    global _dirty
    from engtools.ui.theme import menu,system_palette
    palette=system_palette(view_manager)
    if _page == 'tools':
        rows = [('Graph','2D expressions, curves and shading'),('Graph3D','3D surfaces and implicit expressions'),('Plot previews','Test shared viewers and styling')]+[(title,detail) for _,title,detail in TOOLS]+[('Numerics checks','Accuracy and timings for the math core'),('Scientific Calculator','Keyboard input and textbook expressions')]
        menu(view_manager.draw,rows,_selected,hint2=_error or 'ESC returns',palette=palette)
    elif _page == 'gallery':
        from engtools.plots.gallery import CHOICES
        menu(view_manager.draw,CHOICES,_gallery_selected,'plot previews',hint2=_error or 'ESC returns to tools',palette=palette)
    elif _page == 'bench':
        from engtools.numerics.bench import CASES
        from engtools.ui import theme
        rows, colors = [], []
        for index, (name, _) in enumerate(CASES):
            if index < len(_bench_rows):
                record = _bench_rows[index]
                status = 'PASS ' if record['passed'] else 'FAIL '
                detail = record['error'] or '%d us | heap delta %d B' % (record['elapsed_us'], record['heap_delta_bytes'])
                color = palette.ACCENT if record['passed'] else palette.ERROR
            else:
                status, detail, color = 'WAIT ', 'Pending', palette.MUTED
            rows.append((status+name, detail))
            colors.append((color, palette.MUTED))
        menu(view_manager.draw,rows,-1,'numerics',hint1='ENTER rerun  ESC returns',
             hint2=_error or _bench_info,row_colors=colors,palette=palette)
    else:
        from engtools.ui.results import show_placeholder
        show_placeholder(view_manager.draw,_tool)
    _dirty = False


def run(view_manager):
    global _selected, _gallery_selected, _page, _tool, _dirty, _resume, _error, _bench
    from picoware.system.buttons import BUTTON_UP, BUTTON_DOWN, BUTTON_CENTER, BUTTON_ESCAPE
    button = view_manager.button
    if button == BUTTON_ESCAPE:
        if _page == 'tools':
            view_manager.back()
            return
        _page, _tool, _error = 'tools', None, ''
        _bench = None
        _dirty = True
    elif _page == 'tools':
        if button in (BUTTON_UP,BUTTON_DOWN):
            _selected = (_selected+(-1 if button == BUTTON_UP else 1)) % (len(TOOLS)+5)
            _dirty = True
        elif button == BUTTON_CENTER:
            if _selected in (0,1):
                from picoware.applications.library import launch
                _resume=True
                launch(view_manager,'Graph' if _selected==0 else 'Graph3D')
                return
            elif _selected == 2:
                _page = 'gallery'
            elif _selected == len(TOOLS)+3:
                _page = 'bench'
                _start_bench()
            elif _selected == len(TOOLS)+4:
                from engtools.calculator import app
                _resume = True
                app.show(view_manager)
                return
            else:
                path = TOOLS[_selected-3][0]
                module = __import__(path,None,None,('show',))
                if hasattr(module,'show'):
                    _resume = True
                    module.show(view_manager)
                    return
                _tool, _page = module.TOOL, 'tool'
            _dirty = True
    elif _page == 'gallery':
        from engtools.plots import gallery
        if button in (BUTTON_UP,BUTTON_DOWN):
            _gallery_selected = (_gallery_selected+(-1 if button == BUTTON_UP else 1)) % len(gallery.CHOICES)
            _dirty = True
        elif button == BUTTON_CENTER:
            _error = ''
            try:
                kind,spec = gallery.specification(_gallery_selected)
                _resume = True
                if kind == '2d':
                    from engtools.plots import plot2d
                    plot2d.show(view_manager,spec)
                else:
                    from engtools.plots import plot3d
                    plot3d.show(view_manager,spec)
                return
            except Exception as exc:
                _resume, _error, _dirty = False, str(exc), True
    elif _page == 'bench' and button == BUTTON_CENTER:
        _start_bench()
    if _page == 'bench' and _bench is not None:
        try:
            _bench_rows.append(next(_bench))
        except StopIteration:
            _bench = None
        except Exception as exc:
            _bench, _error = None, str(exc)
        _dirty = True
    if _dirty:
        _draw(view_manager)


def stop(view_manager):
    global _selected, _gallery_selected, _page, _tool, _dirty, _error, _bench, _bench_rows
    _bench, _bench_rows = None, []
    if not _resume:
        _selected, _gallery_selected, _page, _tool, _error = 0, 0, 'tools', None, ''
    _dirty = True
    from gc import collect
    collect()


def _start_bench():
    global _bench, _bench_rows, _bench_info, _error, _dirty
    _bench, _bench_rows, _error = None, [], ''
    try:
        from engtools.numerics.backend import information
        from engtools.numerics.bench import checks
        from sys import platform
        info = information()
        location = 'Desktop' if platform in ('darwin', 'linux', 'win32') else 'Device'
        _bench_info = 'float%d | %s check timings' % (info['float_bits'], location)
        _bench = checks()
    except Exception as exc:
        _bench_info, _error = '', str(exc)
    _dirty = True
