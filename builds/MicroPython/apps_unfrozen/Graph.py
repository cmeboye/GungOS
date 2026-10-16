"""Standalone Graph entry point using the shared engineering plot viewer."""

_engine = None


def start(view_manager):
    global _engine
    from engtools.plots import plot2d
    _engine = plot2d
    return _engine.start(view_manager)


def run(view_manager):
    if _engine is not None:
        _engine.run(view_manager)


def stop(view_manager):
    global _engine
    if _engine is not None:
        _engine.stop(view_manager)
    _engine = None
