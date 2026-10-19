"""Adjustable Lorenz demo: bounded trails, timing and native-size widget UI."""
from array import array
from time import ticks_ms, ticks_us, ticks_diff, ticks_add
from picoware.system import buttons as k

WIDGET_NATIVE = True
POINTS = 768
DETAILS = (('Coarse', 12), ('Medium', 6), ('Balanced', 4),
           ('Smooth', 3), ('Fine', 2), ('Ultra', 1))
TRAILS = (192, 384, 768, 1536, 3072, 6144)
RATES = (4, 8, 12, 16, 24, 30)
DEFAULTS = {'detail': 3, 'points': POINTS, 'fps': 8, 'stats': True}
STEPS_PER_SECOND = 384
_options = None
_draft = None
_trail = None
_count = _head = _step_credit = _sample_steps = _period_credit = 0
_x, _y, _z = 0.1, 0.0, 0.0
_next = 0
_paused = False
_selected = 0
_error = ''
_widget = False
_actual_fps = 0.0
_work_us = _frame_us = 0
_last_frame = None
_notice = ''


def _effective_fps(options=None):
    fps = (options or _options)['fps']
    return min(8, fps) if _widget else fps


def _load_options(vm):
    result = DEFAULTS.copy()
    try:
        from picoware.system.settings import Settings
        saved = Settings(vm.storage).settings.get('lorenz', {})
        if isinstance(saved, dict):
            for name, allowed in (('detail', tuple(item[1] for item in DETAILS)),
                                  ('points', TRAILS), ('fps', RATES)):
                if type(saved.get(name)) is int and saved[name] in allowed:
                    result[name] = saved[name]
            if isinstance(saved.get('stats'), bool):
                result['stats'] = saved['stats']
    except (OSError, ValueError, TypeError):
        pass
    return result


def _allocate(points):
    from gc import collect, mem_free
    collect()
    # Preserve room for the desktop/widget, settings UI and input handling.
    if mem_free() < points * 4 + 24 * 1024:
        raise MemoryError('Not enough free heap')
    return array('h', (0 for _ in range(points * 2)))


def _reset():
    global _count, _head, _x, _y, _z, _next, _step_credit, _sample_steps, _period_credit
    global _actual_fps, _work_us, _frame_us, _last_frame
    _count, _head, _x, _y, _z = 0, 0, 0.1, 0.0, 0.0
    _next = _step_credit = _sample_steps = _period_credit = 0
    _actual_fps, _work_us, _frame_us, _last_frame = 0.0, 0, 0, None


def start(vm):
    global _trail, _options, _draft, _paused, _widget, _error, _notice
    _widget = getattr(vm, 'host', None) is not None
    _options = _load_options(vm)
    _draft, _paused, _error, _notice = None, False, '', ''
    try:
        _trail = _allocate(_options['points'])
    except MemoryError:
        _options = dict(detail=12, points=192, fps=4, stats=True)
        try:
            _trail = _allocate(192)
        except MemoryError:
            return False
        _notice = 'Low heap: smaller trail.'
    _reset()
    # The full-screen trail uses the shared native gfx core. Borrow its faster
    # SRAM screen just while this view is open; View.stop restores the user's
    # preference. A widget already owns a small RAM surface and needs no loan.
    if not _widget:
        fast = getattr(vm, 'request_fast_drawing', None)
        if fast is not None:
            fast()  # safely remains in PSRAM if a 100 KiB block is unavailable
    return True


def _open_settings(vm):
    global _draft, _selected, _error
    _draft, _selected, _error = _options.copy(), 0, ''
    _draw_settings(vm)


def _close_settings():
    global _draft, _next, _last_frame, _actual_fps, _period_credit
    _draft, _next, _last_frame, _actual_fps, _period_credit = None, 0, None, 0.0, 0


def _apply(vm):
    global _options, _trail, _error, _notice
    replacement = None
    if _draft['points'] != _options['points']:
        try:
            replacement = _allocate(_draft['points'])
        except MemoryError:
            _error = 'Low heap. Reduce trail.'
            return False
    try:
        from picoware.system.settings import Settings
        if not Settings(vm.storage).update({'lorenz': _draft.copy()}):
            _error = 'SD save failed. F2 retries.'
            return False
    except (OSError, ValueError, TypeError, MemoryError):
        _error = 'SD save failed. F2 retries.'
        return False
    reset = replacement is not None or _draft['detail'] != _options['detail']
    _options = _draft.copy()
    _notice = ''
    if replacement is not None:
        _trail = replacement
    if reset:
        _reset()
    else:
        # The fractional integration budget belongs to the previous FPS divisor.
        global _step_credit
        _step_credit = 0
    _close_settings()
    return True


def _settings_input(vm, button):
    global _selected, _draft, _error
    if button == k.BUTTON_ESCAPE:
        _close_settings()
        return
    if button == k.BUTTON_F2:
        if not _apply(vm):
            _draw_settings(vm)
        return
    if button in (k.BUTTON_UP, k.BUTTON_DOWN):
        _selected = (_selected + (-1 if button == k.BUTTON_UP else 1)) % 6
    elif button in (k.BUTTON_LEFT, k.BUTTON_RIGHT, k.BUTTON_CENTER, k.BUTTON_ENTER):
        direction = -1 if button == k.BUTTON_LEFT else 1
        if _selected < 4:
            name, values = (('detail', tuple(item[1] for item in DETAILS)),
                            ('points', TRAILS), ('fps', RATES),
                            ('stats', (False, True)))[_selected]
            _draft[name] = values[(values.index(_draft[name]) + direction) % len(values)]
            _error = ''
        elif _selected == 4 and button in (k.BUTTON_CENTER, k.BUTTON_ENTER):
            if _apply(vm):
                return
        elif _selected == 5 and button in (k.BUTTON_CENTER, k.BUTTON_ENTER):
            _draft, _error = DEFAULTS.copy(), ''
    _draw_settings(vm)


def _foreground(background):
    from picoware.gui.status_bar import foreground
    return foreground(background)


def _draw_settings(vm):
    draw = vm.draw
    width, height = int(draw.size.x), int(draw.size.y)
    accent, text, bg = vm.selected_color, vm.foreground_color, vm.background_color
    from engtools.ui import theme
    ink, muted = _foreground(accent), theme.system_palette(vm).MUTED
    draw.fill_screen(bg)
    theme.header(draw,'Lorenz / Settings',palette=theme.system_palette(vm),height=18)
    detail = next(label for label, stride in DETAILS if stride == _draft['detail'])
    fps = str(_draft['fps']) + (' (cap 8)' if _widget and _draft['fps'] > 8 else '')
    rows = (('Detail', detail + ' /' + str(_draft['detail'])),
            ('Trail', str(_draft['points']) + ' pts'), ('FPS', fps),
            ('Stats', 'On' if _draft['stats'] else 'Off'),
            ('Apply & save', ''), ('Defaults', ''))
    row_height = max(16, min(28, (height - 78) // 6))
    for index, (label, value) in enumerate(rows):
        y = 28 + index * row_height
        colour = text
        if index == _selected:
            draw._fill_rectangle(4, y - 3, width - 8, row_height - 1, accent)
            colour = ink
        draw._text(8, y, label, colour, 0)
        draw._text(width - 8 - draw.len(value, 0), y, value, colour, 0)
    info_y = height - 55
    used = _draft['points'] * 4
    draw._text(6, info_y, '%.1f KiB trail / %.1fs' % (used / 1024, _draft['points'] * _draft['detail'] / STEPS_PER_SECOND), muted, 0)
    warning = ('Heavy trail: test on Pico.' if _draft['points'] > 1536 else
               'Widget host: maximum 8 FPS.' if _widget else
               'High FPS: test on Pico.' if _draft['fps'] > 16 else
               'More points = more drawing.')
    if _error:
        draw._fill_rectangle(2, height - 44, width - 4, 13, 0x5800)
        draw._text(5, height - 41, _error, 0xFFFF, 0)
    else:
        draw._text(6, height - 41, warning, 0xFD20 if _draft['points'] > 1536 or (_draft['fps'] > 16 and not _widget) else muted, 0)
    draw._fill_rectangle(0, height - 28, width, 28, accent)
    draw._text(5, height - 23, 'Arrows choose / adjust', ink, 0)
    draw._text(5, height - 11, 'F2 save  ESC cancel', ink, 0)
    draw.swap()


def _advance(width, height, fps):
    global _x, _y, _z, _step_credit, _sample_steps, _head, _count
    # Preserve the original 384 integration steps per second at the target FPS.
    # Work is bounded (at most 96 steps/frame); overloaded devices slow down
    # rather than accumulating a catch-up queue that blocks keyboard input.
    _step_credit += STEPS_PER_SECOND
    steps, _step_credit = _step_credit // fps, _step_credit % fps
    left, right, top, bottom = 19, width - 9, 35, height - 23
    points, stride = _options['points'], _options['detail']
    dt = 0.006
    for _ in range(steps):
        dx, dy, dz = 10 * (_y - _x), _x * (28 - _z) - _y, _x * _y - (8 / 3) * _z
        x, y, z = _x + dx * dt / 2, _y + dy * dt / 2, _z + dz * dt / 2
        _x += 10 * (y - x) * dt
        _y += (x * (28 - z) - y) * dt
        _z += (x * y - (8 / 3) * z) * dt
        _sample_steps += 1
        if _sample_steps >= stride:
            _sample_steps = 0
            px = max(left, min(right, int(left + (_x + 25) * (right - left) / 50)))
            py = max(top, min(bottom, int(bottom - _z * (bottom - top) / 55)))
            _trail[_head * 2], _trail[_head * 2 + 1] = px, py
            _head = (_head + 1) % points
            _count = min(points, _count + 1)


def _draw(vm, fps):
    from picoware.gui.style import system_palette
    draw = vm.draw
    width, height = int(draw.size.x), int(draw.size.y)
    fg, bg = vm.foreground_color, vm.background_color
    palette = system_palette(vm)
    colors = (palette.PANEL, palette.SELECT, palette.AXIS, palette.ACCENT, palette.TEXT)
    draw.fill_screen(bg)
    draw._fill_rectangle(0, 0, width, 2, vm.selected_color)
    draw._text(6, 8, 'LORENZ' if _widget or width < 240 else 'GungOS / LORENZ', fg, 0)
    if _paused:
        draw._text(width - 6 - draw.len('PAUSED', 0), 8, 'PAUSED', fg, 0)
    if _options['stats']:
        rate = '%.1f' % _actual_fps if _actual_fps else '--'
        stats = '%s/%dfps  work %.1fms' % (rate, fps, _work_us / 1000)
        draw._text(6, 22, stats, palette.MUTED, 0)
        if _frame_us > 1000000 // fps or (_actual_fps > 0 and _actual_fps < fps * 0.85):
            draw._text(width - 25, 22, 'SLOW', 0xF800, 0)
    else:
        draw._text(6, 22, 'sigma=10 rho=28 beta=8/3', palette.MUTED, 0)
    left, right, top, bottom = 19, width - 9, 35, height - 23
    draw._line(left, top, left, bottom, palette.AXIS)
    draw._line(left, bottom, right, bottom, palette.AXIS)
    draw._text(7, top, 'z', fg, 0)
    draw._text(right - 6, bottom + 3, 'x', fg, 0)
    points = _options['points']
    a = (_head - _count) % points
    for i in range(1, _count):
        b = a + 1 if a + 1 < points else 0
        colour = colors[min(4, i * 5 // _count)]
        draw._line(_trail[a * 2], _trail[a * 2 + 1], _trail[b * 2], _trail[b * 2 + 1], colour)
        a = b
    if _notice:
        draw._text(5, height - 22, _notice, 0xFD20, 0)
    hint = 'F2 opts  SPACE pause  F5 reset' if _widget or width < 240 else 'F4 stats F2 opts SPACE pause F5 reset ESC exit'
    draw._text(5, height - 9, hint, fg, 0)


def run(vm):
    global _next, _paused, _last_frame, _actual_fps, _work_us, _frame_us, _period_credit
    button = vm.button
    if _draft is not None:
        if button != k.BUTTON_NONE:
            _settings_input(vm, button)
        return
    if button == k.BUTTON_ESCAPE:
        vm.back()
        return
    if button == k.BUTTON_F2:
        _open_settings(vm)
        return
    if button == k.BUTTON_SPACE:
        _paused, _next = not _paused, 0
    if button == k.BUTTON_F4:
        _options['stats'], _next = not _options['stats'], 0
    if button == k.BUTTON_F5:
        _reset()
    now = ticks_ms()
    if _next and ticks_diff(now, _next) < 0:
        return
    fps = _effective_fps()
    _period_credit += 1000
    interval, _period_credit = _period_credit // fps, _period_credit % fps
    _next = ticks_add(now, interval)
    started = ticks_us()
    if _last_frame is not None:
        elapsed = ticks_diff(started, _last_frame)
        if elapsed > 0:
            sample = 1000000 / elapsed
            _actual_fps = sample if not _actual_fps else _actual_fps * 0.8 + sample * 0.2
    _last_frame = started
    if not _paused:
        _advance(int(vm.draw.size.x), int(vm.draw.size.y), fps)
    _draw(vm, fps)
    _work_us = ticks_diff(ticks_us(), started)
    vm.draw.swap()
    _frame_us = ticks_diff(ticks_us(), started)


def stop(vm):
    global _trail, _draft
    _trail, _draft = None, None
