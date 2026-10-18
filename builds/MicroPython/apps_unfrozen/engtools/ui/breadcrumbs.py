"""PicoLAB breadcrumb paths scoped to managed views; no extra framebuffer."""
_vm=None
_paths={}


def bind(vm,path,name=None):
    global _vm,_paths
    if _vm is not vm:_vm,_paths=vm,{}
    view=vm.current_view
    name=name or (view.name if view is not None else None)
    if name is not None:_paths[name]=tuple(path)


def current(vm=None,name=None):
    manager=vm or _vm
    if manager is None or manager is not _vm:return None
    view=manager.current_view
    name=name or (view.name if view is not None else None)
    return _paths.get(name)


def unbind(vm,name=None):
    global _vm
    if vm is not _vm:return
    view=vm.current_view
    name=name or (view.name if view is not None else None)
    _paths.pop(name,None)
    if not _paths:_vm=None


def paint(draw,palette,height=18,fallback=None,suffix=None):
    path=current()
    if path is None:path=fallback
    if path is None:return
    if suffix and (not path or str(suffix).lower()!=str(path[-1]).lower()):
        path=tuple(path)+(str(suffix),)
    from .theme import header
    from picoware.system.font import FONT_XTRA_SMALL
    header(draw,' / '.join(path),'PicoLAB',palette,height,font=FONT_XTRA_SMALL)
