"""PicoLAB: organised checks, tools and engineering modules."""

HELP = ('PicoLAB:', 'UP/DOWN\tchoose an entry', 'ENTER\topen it', 'ESC\tback one level',
        'Numerics check:', 'ENTER\trun the checks again')

# Keys are stable route IDs; labels are the visible names.
MENUS = {
    'root': (('checks','Checks','Numerics validation and plot previews'),
             ('tools','Tools','Graphing and scientific calculation'),
             ('modules','Modules','Engineering disciplines')),
    'checks': (('bench','Numerics check','Accuracy and timings for the math core'),
               ('gallery','Plot previews','Shared 2D and 3D viewer examples')),
    'tools': (('Graph','Graph','2D expressions, curves and shading'),
              ('Graph3D','Graph3D','3D surfaces and implicit expressions'),
              ('calculator','Scientific calculator','Expressions, statistics, solver and matrices'),
              ('picocad','PicoCAD','Analytic primitives and Boolean part previews')),
    'modules': (('structural','Structural','Beams, frames, sections and stress'),
                ('dynamics','Dynamics','No tools yet'),('thermal','Thermal','No tools yet'),
                ('electrical','Electrical','No tools yet'),('fluids','Fluids','No tools yet')),
    'structural': (('beam','Beam view','Supports, loads, sections and diagrams'),
                   ('discs','Shrink fit','Rotating discs, thick cylinders, press fits'),
                   ('mohr','Mohr circle','2D/3D stress, element rotation, principal')),
    'dynamics': (), 'thermal': (), 'electrical': (), 'fluids': (),
}
PARENTS = {'checks':'root','tools':'root','modules':'root','structural':'modules',
           'dynamics':'modules','thermal':'modules','electrical':'modules','fluids':'modules',
           'gallery':'checks','bench':'checks'}
PATHS = {'root':(), 'checks':('checks',), 'tools':('tools',), 'modules':('modules',),
         'structural':('modules','structural'), 'gallery':('checks','Plot previews'),
         'bench':('checks','Numerics check')}
for _name in ('dynamics','thermal','electrical','fluids'):
    PATHS[_name]=('modules',_name)

_selected = 0
_gallery_selected = 0
_page = 'root'
_selections = {}
_dirty = True
_resume = False
_suspended = False
_error = ''
_bench = None
_bench_rows = []
_bench_info = ''


# Kept loaded while PicoLAB runs: its menu's own modules and tools' saved state.
_KEEP = ('engtools.ui', 'engtools.session')


def _release_tools(view_manager):
    """Unload closed tools' code on returning to the PicoLAB menu: Beam view,
    Graph, Graph3D and the calculator are each tens to 100+ KB of heap."""
    import sys
    names=[n for n in sys.modules if n in ('Graph','Graph3D') or
           (n.startswith('engtools.') and not n.startswith(_KEEP))]
    for name in names:
        # A parent package's attribute would keep the module alive.
        parent,_,child=name.rpartition('.')
        if parent and parent in sys.modules and parent not in names:
            try:delattr(sys.modules[parent],child)
            except AttributeError:pass
        del sys.modules[name]
    loader=getattr(view_manager,'app_loader',None)
    if loader is not None:
        for key in ('Graph','Graph3D'):loader.loaded_apps.pop(key,None)
    from gc import collect
    collect()


def start(view_manager):
    global _selected, _gallery_selected, _page, _selections, _dirty, _resume, _suspended, _error
    if _resume:
        _release_tools(view_manager)
    if not _resume:
        _selected, _gallery_selected, _page, _selections, _error = 0,0,'root',{},''
    _resume, _suspended = False,False
    _dirty = True
    view_manager.input_manager.reset()
    _draw(view_manager)
    return True


def _enter(page):
    global _page, _selected, _dirty, _error
    _selections[_page]=_selected
    _page, _selected, _dirty, _error = page,_selections.get(page,0),True,''


def _draw(view_manager):
    global _dirty
    from engtools.ui import theme,breadcrumbs
    palette=theme.system_palette(view_manager)
    breadcrumbs.bind(view_manager,PATHS[_page])
    if _page in MENUS:
        entries=MENUS[_page]
        rows=[(label,detail) for _,label,detail in entries] if entries else [('No tools yet','This module is planned; ESC returns')]
        theme.menu(view_manager.draw,rows,_selected if entries else -1,'',message=_error,palette=palette,error=bool(_error))
    elif _page == 'gallery':
        from engtools.plots.gallery import CHOICES
        theme.menu(view_manager.draw,CHOICES,_gallery_selected,'',message=_error,palette=palette,error=bool(_error))
    elif _page == 'bench':
        from engtools.numerics.bench import CASES
        rows,colors=[],[]
        for index,(name,_) in enumerate(CASES):
            if index<len(_bench_rows):
                record=_bench_rows[index]
                status='PASS ' if record['passed'] else 'FAIL '
                detail=record['error'] or '%d us | heap delta %d B'%(record['elapsed_us'],record['heap_delta_bytes'])
                color=palette.ACCENT if record['passed'] else palette.ERROR
            else:status,detail,color='WAIT ','Pending',palette.MUTED
            rows.append((status+name,detail));colors.append((color,palette.MUTED))
        theme.menu(view_manager.draw,rows,-1,'',message=_error or _bench_info,row_colors=colors,
                   palette=palette,error=bool(_error))
    _dirty=False


def _launch(view_manager,target):
    global _resume,_error,_dirty
    from engtools.ui import breadcrumbs
    before=view_manager.current_view
    name={'Graph':'app_Graph','Graph3D':'app_Graph3D','calculator':'eng_calculator','beam':'beam_lab',
          'mohr':'mohr_view','discs':'discs_view','picocad':'picocad_view'}[target]
    path={'beam':('modules','structural','Beam view'),'mohr':('modules','structural','Mohr circle'),
          'discs':('modules','structural','Shrink fit'),
          'calculator':('tools','Scientific calculator'),'picocad':('tools','PicoCAD')}.get(target,('tools',target))
    breadcrumbs.bind(view_manager,path,name)
    _resume=True
    try:
        if target in ('Graph','Graph3D'):
            from picoware.applications.library import launch
            launch(view_manager,target)
        elif target=='calculator':
            from engtools.calculator import app
            app.show(view_manager)
        elif target=='picocad':
            from engtools.picocad import app
            app.show(view_manager)
        elif target=='mohr':
            from engtools.mohr import app
            app.show(view_manager)
        elif target=='discs':
            from engtools.discs import app
            app.show(view_manager)
        else:
            from engtools.beamlab import app
            app.show(view_manager)
    except Exception as exc:
        _error=str(exc)
    if view_manager.current_view is before:
        _resume,_dirty=False,True
        breadcrumbs.unbind(view_manager,name)
        breadcrumbs.bind(view_manager,PATHS[_page])


def run(view_manager):
    global _selected,_gallery_selected,_dirty,_resume,_error,_bench
    from picoware.system.buttons import BUTTON_UP,BUTTON_DOWN,BUTTON_CENTER,BUTTON_ESCAPE
    button=view_manager.button
    if button==BUTTON_ESCAPE:
        if _page=='root':view_manager.back();return
        _bench=None
        _enter(PARENTS[_page])
    elif _page in MENUS:
        entries=MENUS[_page]
        if button in (BUTTON_UP,BUTTON_DOWN) and entries:
            _selected=(_selected+(-1 if button==BUTTON_UP else 1))%len(entries);_dirty=True
        elif button==BUTTON_CENTER and entries:
            target=entries[_selected][0]
            if target in MENUS:_enter(target)
            elif target in ('bench','gallery'):
                _enter(target)
                if target=='bench':_start_bench()
            else:
                _launch(view_manager,target)
                if _resume:return
    elif _page=='gallery':
        from engtools.plots import gallery
        if button in (BUTTON_UP,BUTTON_DOWN):
            _gallery_selected=(_gallery_selected+(-1 if button==BUTTON_UP else 1))%len(gallery.CHOICES);_dirty=True
        elif button==BUTTON_CENTER:
            _error=''
            try:
                kind,spec=gallery.specification(_gallery_selected)
                _resume=True
                if kind=='2d':
                    from engtools.plots import plot2d
                    plot2d.show(view_manager,spec)
                else:
                    from engtools.plots import plot3d
                    plot3d.show(view_manager,spec)
                return
            except Exception as exc:_resume,_error,_dirty=False,str(exc),True
    elif _page=='bench' and button==BUTTON_CENTER:_start_bench()
    if _page=='bench' and _bench is not None:
        try:_bench_rows.append(next(_bench))
        except StopIteration:_bench=None
        except Exception as exc:_bench,_error=None,str(exc)
        _dirty=True
    if _dirty:_draw(view_manager)


def stop(view_manager):
    global _selected,_gallery_selected,_page,_selections,_dirty,_error,_bench,_bench_rows,_resume,_suspended
    from engtools.ui import breadcrumbs
    breadcrumbs.unbind(view_manager)
    _bench,_bench_rows=None,[]
    leaving=not _resume or _suspended
    _suspended=not leaving
    if leaving:
        _selected,_gallery_selected,_page,_selections,_error=0,0,'root',{},''
        _resume=False
    _dirty=True
    from gc import collect
    collect()


def _start_bench():
    global _bench,_bench_rows,_bench_info,_error,_dirty
    _bench,_bench_rows,_error=None,[],''
    try:
        from engtools.numerics.backend import information
        from engtools.numerics.bench import checks
        from sys import platform
        info=information()
        location='Desktop' if platform in ('darwin','linux','win32') else 'Device'
        _bench_info='float%d | %s check timings'%(info['float_bits'],location)
        _bench=checks()
    except Exception as exc:_bench_info,_error='',str(exc)
    _dirty=True
