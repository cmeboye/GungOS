"""Versioned plotting API. Importing this package loads no renderer."""


def validate(document):
    """Validate a v1 document, including expressions, without opening a view."""
    from .runtime import prepare
    viewer = prepare(document)
    try:
        return viewer.document
    finally:
        viewer.close()


def show(view_manager, document):
    """Open an isolated plot; Escape returns to its caller."""
    from .runtime import prepare
    from .view import open_view
    viewer = prepare(document)
    try:
        name = open_view(view_manager, 'eng_plot', viewer)
        if view_manager.current_view is None or view_manager.current_view.name != name:
            raise ValueError('Plot viewer could not start')
        return name
    except Exception:
        viewer.close()
        raise
