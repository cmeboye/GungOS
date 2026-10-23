"""Standalone entry point for the shared Grapher workspace."""

_app = None


def start(vm):
    global _app
    from engtools.plots.grapher import Grapher
    _app = Grapher()
    return _app.start(vm)


def run(vm):
    if _app is not None:
        _app.run(vm)


def stop(vm):
    global _app
    if _app is not None:
        _app.stop(vm)
    _app = None
    from engtools.ui import breadcrumbs
    breadcrumbs.unbind(vm)
