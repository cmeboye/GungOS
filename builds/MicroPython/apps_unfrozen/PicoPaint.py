"""PicoPaint standalone application entry."""
_owner=None


def start(vm):
    global _owner
    from desktopapps.paint import Paint
    _owner=Paint()
    return _owner.start(vm)


def run(vm):
    if _owner is not None:_owner.run(vm)


def stop(vm):
    global _owner
    if _owner is not None:_owner.stop(vm)
    _owner=None
