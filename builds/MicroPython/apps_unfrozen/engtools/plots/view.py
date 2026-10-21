"""Connect shared plot viewers to the existing Picoware navigation stack."""


def open_view(view_manager, name, controller):
    from picoware.system.view import View
    if view_manager.get_view(name) is not None:
        raise ValueError('This plot viewer is already open')
    from engtools.ui import breadcrumbs
    path=breadcrumbs.current(view_manager,name)
    if path is None:path=breadcrumbs.current(view_manager)
    def start(vm):
        if path is not None:breadcrumbs.bind(vm,path,name)
        return controller.start(vm)
    def stop(vm):
        try:controller.stop(vm)
        finally:breadcrumbs.unbind(vm,name)
    view = View(name, controller.run, start, stop)
    help = getattr(controller, 'HELP', None)
    if help is not None:
        try:view.help = help  # F9 help drawn by the firmware
        except AttributeError:pass  # firmware without shared help
    if not view_manager.add(view):
        raise ValueError('No free view slots')
    view_manager.switch_to(name)
    return name
