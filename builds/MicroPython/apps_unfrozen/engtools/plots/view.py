"""Connect shared plot viewers to the existing Picoware navigation stack."""


def open_view(view_manager, name, controller):
    from picoware.system.view import View
    if view_manager.get_view(name) is not None:
        raise ValueError('This plot viewer is already open')
    view = View(name, controller.run, controller.start, controller.stop)
    if not view_manager.add(view):
        raise ValueError('No free view slots')
    view_manager.switch_to(name)
    return name
