"""One active renderer, with explicit ownership and disposable render caches.

The existing 3D engine is a singleton. This boundary prevents overlapping
viewers and restores its settings; callers never depend on its globals.
"""

import sys
from gc import collect
from .document import normalize, backend_spec

_active = None


def _unload(name, module):
    if sys.modules.get(name) is not module:
        return
    del sys.modules[name]
    parent, _, child = name.rpartition('.')
    package = sys.modules.get(parent)
    if package is not None and getattr(package, child, None) is module:
        delattr(package, child)


def prepare(document):
    """Validate before navigation or allocating render buffers."""
    if _active is not None:
        raise ValueError('A shared plot viewer is already open')
    return Viewer(normalize(document))


class Viewer:
    def __init__(self, document):
        self.document = document
        self.mode = document['view']['mode']
        self.name = 'engtools.plots.plot' + self.mode
        self.owned = self.name not in sys.modules
        self.engine = self.controller = self.vm = None
        self.pending_camera = None
        try:
            self.engine = __import__(self.name, None, None, ['start'])
            if self.mode == '2d' and self.engine._app is not None:
                raise ValueError('Graph is already open')
            if self.mode == '3d' and self.engine._viewer_active:
                raise ValueError('Graph3D is already open')
            self.spec = backend_spec(document)
            self.engine.validate_spec(self.spec)
            if self.mode == '3d' and self.spec['style'] == 'heatmap':
                if self.engine._surface_expression(self.spec['surfaces'][0]['expression'])[0]:
                    raise ValueError('Heatmap needs z=f(x,y)')
        except Exception:
            self.close()
            raise

    def start(self, vm):
        global _active
        if _active is not None:
            raise ValueError('A shared plot viewer is already open')
        _active = self
        self.vm = vm
        try:
            self.controller = self.engine._PlotView(self.spec)
            result = self.controller.start(vm)
            if self.mode == '2d':
                self.controller.app.padding = self.spec['padding']
                self.controller.app.minimum_items = 1
            else:
                self.pending_camera = self.spec['camera'] or None
            return result
        except Exception:
            self.close()
            raise

    def run(self, vm):
        if self.controller is not None:
            self.controller.run(vm)
            engine = self.engine
            if engine is not None and self.mode == '3d' and self.pending_camera and engine._state == engine.ST_PLOT:
                for key, value in self.pending_camera.items():
                    setattr(engine, '_' + key, value)
                self.pending_camera = None
                engine._dirty = True

    def root(self):
        if self.mode == '2d':
            return self.controller.app.state == 'plot'
        return self.engine._state in (self.engine.ST_PLOT, self.engine.ST_SAMPLING,
                                      self.engine.ST_ERROR, self.engine.ST_RES_WARNING)

    def redraw(self):
        if self.mode == '2d':
            if self.in_menu():
                self.controller.app.set_state('plot')
            else:
                self.controller.app.dirty = True
        else:
            if self.in_menu():
                self.engine._goto_plot(self.vm)
            else:
                self.engine._dirty = True

    def in_menu(self):
        if self.mode == '2d':
            return self.controller.app.state == 'menu'
        return self.engine._state == self.engine.ST_MENU

    def option_rows(self):
        names = ('Layers', 'Window', 'Fit', 'Presets', 'Mode help') if self.mode == '2d' else (
            'Main surface', 'Second surface', 'Settings', 'Presets', 'Mode help')
        return [(name, '') for name in names]

    def options(self, index):
        if self.mode == '2d':
            self.controller.app.set_state(('expressions', 'window', 'fit', 'presets', 'help')[index])
        else:
            engine = self.engine
            engine._auto = False
            if index in (0, 1):
                engine._state = engine.ST_INPUT if index == 0 else engine.ST_INPUT2
                engine._begin_input(self.vm, index == 1)
            elif index == 2:
                engine._state, engine._set_row, engine._dirty = engine.ST_SETTINGS, 0, True
            elif index == 3:
                engine._state = engine.ST_PRESETS
                engine._make_presets(self.vm)
            else:
                engine._help_return, engine._state = engine.ST_PLOT, engine.ST_HELP
                engine._make_help(self.vm)

    def snapshot(self):
        """Capture editable settings and borrowed sources, never cached geometry."""
        if self.controller is None:
            return self.document
        sources, layers = {}, []
        if self.mode == '2d':
            app = self.controller.app
            for i, item in enumerate(app.items):
                name = 's' + str(i)
                layer = {'source': name, 'visible': item.visible, 'color': item.color}
                if item.kind == 'samples':
                    sources[name] = {'kind': 'samples', 'points': item.points}
                    layer.update({'name': item.text, 'style': item.style, 'marker': item.marker})
                else:
                    sources[name] = {'kind': 'expression', 'expression': item.text}
                    if hasattr(item, 'name'):
                        layer['name'] = item.name
                layers.append(layer)
            axes = {name: dict(app.axes_spec.get(name, {})) for name in ('x', 'y')}
            axes['x']['bounds'], axes['y']['bounds'] = app.bounds[:2], app.bounds[2:]
            view = {'mode': '2d', 'grid': app.grid, 'legend': app.legend,
                    'padding': app.padding, 't_range': app.trange[:]}
        else:
            engine = self.engine
            for i, text in enumerate((engine._expr, engine._expr2)):
                if text:
                    name = 's' + str(i)
                    sources[name] = {'kind': 'expression', 'expression': text}
                    layers.append({'source': name})
            bounds = list(engine._xy_bounds())
            axes = {'x': {'bounds': bounds[:2]}, 'y': {'bounds': bounds[2:]}}
            if engine._zrange is not None:
                axes['z'] = {'bounds': list(engine._zrange)}
            camera = {key: getattr(engine, '_' + key) for key in ('yaw', 'pitch', 'zoom', 'pan_x', 'pan_y', 'navigation')}
            view = {'mode': '3d', 'style': ('wire', 'solid', 'heatmap')[engine._style],
                    'resolution': engine._grid_n, 'aspect': engine._aspect,
                    'contours': engine._contours, 'camera': self.pending_camera or camera}
        return {'kind': 'plot', 'version': 1, 'title': self.document['title'],
                'sources': sources, 'layers': layers, 'axes': axes, 'view': view}

    def stop(self, vm):
        self.close()

    def close(self):
        global _active
        try:
            if self.controller is not None:
                self.controller.stop(self.vm)
        finally:
            self.controller = self.vm = self.pending_camera = None
            self.spec = None
            self.document = None
            if _active is self:
                _active = None
            if self.engine is not None and self.owned:
                _unload(self.name, self.engine)
            self.engine = None
            collect()
