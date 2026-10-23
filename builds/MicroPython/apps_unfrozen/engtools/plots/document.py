"""Small renderer-independent plot document and explicit v1 capabilities.

Metadata is copied; sampled buffers are borrowed, never duplicated. Values
are in the units declared on the axes; v1 does not perform unit conversion.
"""

import math

VERSION = 1
MAX_POINTS = 4096


def _keys(value, allowed, where):
    if not isinstance(value, dict):
        raise ValueError(where + ' must be a dictionary')
    for key in value:
        if key not in allowed:
            raise ValueError('Unsupported ' + where + ' option: ' + str(key))


def _number(value, low, high, where):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or math.isnan(value) or math.isinf(value) or not low <= value <= high:
        raise ValueError('Invalid ' + where)
    return value


def _pair(value, where):
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        raise ValueError(where + ' needs [minimum, maximum]')
    lo, hi = [_number(v, -1e9, 1e9, where) for v in value]
    if not 1e-8 <= hi - lo <= 1e9:
        raise ValueError('Invalid ' + where + ' span')
    return [lo, hi]


def _text(value, where, limit=80):
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError('Invalid ' + where)
    return value


def normalize(document):
    """Validate structure without importing UI, native modules or renderers."""
    _keys(document, ('kind', 'version', 'title', 'sources', 'layers', 'axes', 'view'), 'plot')
    if document.get('kind') != 'plot' or type(document.get('version')) is not int or document['version'] != VERSION:
        raise ValueError('Expected kind=plot, version=1')
    view = document.get('view', {})
    mode = view.get('mode') if isinstance(view, dict) else None
    if mode not in ('2d', '3d'):
        raise ValueError('View mode must be 2d or 3d')
    options = ('mode', 'grid', 'legend', 't_range', 'padding') if mode == '2d' else (
        'mode', 'resolution', 'style', 'aspect', 'contours', 'camera')
    _keys(view, options, 'view')
    view = dict(view)
    for key in ('grid', 'legend', 'contours'):
        if key in view and type(view[key]) is not bool:
            raise ValueError(key + ' must be a boolean')
    if mode == '2d':
        view['t_range'] = _pair(view.get('t_range', [0, 2 * math.pi]), 'parameter range')
        if view['t_range'][1] - view['t_range'][0] > 1e6:
            raise ValueError('Parameter range is too large')
        view['padding'] = _number(view.get('padding', 10), 0, 50, 'fit padding')
    else:
        n = view.get('resolution', 12)
        if type(n) is not int or not 4 <= n <= 64:
            raise ValueError('Resolution must be an integer: 4..64')
        view['resolution'] = n
        if view.get('style', 'solid') not in ('solid', 'wire', 'heatmap'):
            raise ValueError('Surface style: solid, wire or heatmap')
        if view.get('aspect', 'equal') not in ('equal', 'box'):
            raise ValueError('Aspect: equal or box')
        if 'camera' in view:
            camera = view['camera']
            _keys(camera, ('yaw', 'pitch', 'zoom', 'pan_x', 'pan_y', 'navigation'), 'camera')
            camera = dict(camera)
            for key in ('yaw', 'pitch', 'pan_x', 'pan_y'):
                if key in camera:
                    _number(camera[key], -1e6, 1e6, 'camera ' + key)
            if 'zoom' in camera:
                _number(camera['zoom'], .2, 8, 'camera zoom')
            if camera.get('navigation', 'pan') not in ('pan', 'orbit'):
                raise ValueError('Camera navigation: pan or orbit')
            view['camera'] = camera
    axes = document.get('axes', {})
    _keys(axes, ('x', 'y') if mode == '2d' else ('x', 'y', 'z'), 'axes')
    copied_axes = {}
    for name, axis in axes.items():
        _keys(axis, ('bounds', 'scale', 'label', 'unit') if mode == '2d' else ('bounds', 'scale'), 'axis ' + name)
        if axis.get('scale', 'linear') != 'linear':
            raise ValueError('Only linear axes are supported in v1')
        entry = dict(axis)
        if 'bounds' in entry:
            entry['bounds'] = _pair(entry['bounds'], name + ' bounds')
        for key in ('label', 'unit'):
            if key in entry:
                _text(entry[key], name + ' ' + key, 40)
        copied_axes[name] = entry
    sources = document.get('sources')
    if not isinstance(sources, dict) or not 1 <= len(sources) <= 6:
        raise ValueError('Use 1 to 6 named sources')
    copied_sources, count = {}, 0
    for name, source in sources.items():
        if not _text(name, 'source name', 40):
            raise ValueError('Source names must not be empty')
        _keys(source, ('kind', 'expression', 'points'), 'source')
        kind = source.get('kind')
        if kind == 'expression':
            _keys(source, ('kind', 'expression'), 'expression source')
            _text(source.get('expression'), 'expression', 240 if mode == '3d' else 180)
        elif kind == 'samples' and mode == '2d':
            _keys(source, ('kind', 'points'), 'sample source')
            points = source.get('points')
            if not isinstance(points, (list, tuple)) or not points:
                raise ValueError('Samples need a nonempty point sequence')
            count += len(points)
            if count > MAX_POINTS:
                raise ValueError('Use at most 4096 sampled points total')
            for point in points:
                if not isinstance(point, (list, tuple)) or len(point) != 2:
                    raise ValueError('Sample points must be (x, y) pairs')
                if point[0] is None and point[1] is None:
                    continue
                for value in point:
                    _number(value, -1e12, 1e12, 'sample coordinate; use (None, None) for a gap')
        else:
            raise ValueError('Unsupported source kind for ' + mode)
        copied_sources[name] = dict(source)
    layers = document.get('layers')
    maximum = 6 if mode == '2d' else 2
    if not isinstance(layers, (tuple, list)) or not 1 <= len(layers) <= maximum:
        raise ValueError('Use 1 to %d layers' % maximum)
    copied_layers = []
    for layer in layers:
        allowed = ('source', 'name', 'visible', 'color', 'style', 'marker') if mode == '2d' else ('source',)
        _keys(layer, allowed, 'layer')
        name = layer.get('source')
        if not isinstance(name, str) or name not in copied_sources:
            raise ValueError('Layer references an unknown source')
        if 'name' in layer:
            _text(layer['name'], 'layer name', 40)
        if 'visible' in layer and type(layer['visible']) is not bool:
            raise ValueError('Layer visible must be a boolean')
        if 'color' in layer and (type(layer['color']) is not int or not 0 <= layer['color'] <= 65535):
            raise ValueError('Layer color must be RGB565')
        if 'style' in layer or 'marker' in layer:
            if copied_sources[name]['kind'] != 'samples':
                raise ValueError('Style and marker apply to sampled layers')
            if layer.get('style', 'line') not in ('line', 'scatter'):
                raise ValueError('Sample style: line or scatter')
            if layer.get('marker', 'none') not in ('none', 'square', 'cross', 'diamond'):
                raise ValueError('Invalid sample marker')
        copied_layers.append(dict(layer))
    return {'kind': 'plot', 'version': VERSION,
            'title': _text(document.get('title', 'Grapher'), 'title'),
            'sources': copied_sources, 'layers': copied_layers, 'axes': copied_axes, 'view': view}


def backend_spec(document):
    """Translate the public document at the compatibility boundary only."""
    view, axes = document['view'], document['axes']
    mode = view['mode']
    bounds = []
    default = [-10, 10] if mode == '2d' else [-4, 4]
    for name in ('x', 'y'):
        bounds.extend(axes.get(name, {}).get('bounds', default))
    spec = {'title': document['title'], 'bounds': bounds}
    items = []
    for layer in document['layers']:
        source = document['sources'][layer['source']]
        item = dict(layer)
        del item['source']
        item['type'] = source['kind']
        key = 'expression' if source['kind'] == 'expression' else 'points'
        item[key] = source[key]
        items.append(item)
    if mode == '2d':
        spec.update({'series': items, 'axes': axes, 'grid': view.get('grid', True),
                     'legend': view.get('legend', True), 't_range': view['t_range'], 'padding': view['padding']})
    else:
        spec.update({'surfaces': items, 'resolution': view['resolution'],
                     'style': view.get('style', 'solid'), 'aspect': view.get('aspect', 'equal'),
                     'contours': view.get('contours', True), 'camera': view.get('camera', {}),
                     'zrange': axes.get('z', {}).get('bounds')})
    return spec


def example(mode='2d'):
    """New independent workspace for a mode; never changes a legacy session."""
    return {'kind': 'plot', 'version': VERSION, 'title': 'Grapher',
            'sources': {'f': {'kind': 'expression', 'expression': 'sin(x)' if mode == '2d' else '0.6*sin(x)*cos(y)'}},
            'layers': [{'source': 'f'}], 'axes': {}, 'view': {'mode': mode}}
