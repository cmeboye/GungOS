"""Device benchmark: display pipeline, screen-image modes and Python versus C.

Each stage runs in one pass of the app loop so the screen stays responsive.
Results are shown at the end and saved to picoware/benchmark.txt.
"""
from time import ticks_us, ticks_diff
from picoware.system import buttons as k

RESULT_PATH = 'picoware/benchmark.txt'
FONT = 1  # FONT_SMALL, 12 px rows
WHITE, BLACK, BLUE, GREY = 0xFFFF, 0x0000, 0x001F, 0x7BEF

_stage = 0
_results = []   # (label, value, unit)
_waiting = False
_saved = ''


def _best(function, repeat):
    """Fastest of repeat runs in microseconds: the least disturbed one."""
    best = None
    for _ in range(repeat):
        start = ticks_us()
        function()
        took = ticks_diff(ticks_us(), start)
        best = took if best is None or took < best else best
    return best


def _record(label, value, unit):
    _results.append((label, value, unit))


def _status(draw, title, lines=()):
    draw._clear(BLACK)
    draw._text(8, 8, 'Benchmark', WHITE, 2)
    draw._text(8, 34, title, GREY, FONT)
    for i, line in enumerate(lines):
        draw._text(8, 60 + i * 14, line, WHITE, FONT)
    draw.swap()


def _text_screen(draw):
    for row in range(26):
        draw._text(2, row * 12, 'Row %02d Settings > Display > Brightness %d' % (row, row * 3), WHITE, FONT)


def _shapes(draw):
    for i in range(20):
        draw._fill_round_rectangle(10 + i * 3, 10 + i * 14, 300 - i * 6, 12, 5, BLUE + i * 0x0800)
    for i in range(100):
        draw._line(0, i * 3, 319, 319 - i * 3, WHITE)
    for i in range(30):
        draw._fill_triangle(i * 10, 300, i * 10 + 40, 200, i * 10 + 80, 310, 0x07E0)


def _swap_full(draw):
    """Every row changes: the worst case for change-only presenting."""
    times, rows = [], 0
    for i in range(6):
        draw._clear(BLUE if i % 2 else BLACK)
        start = ticks_us()
        rows = draw.swap()
        times.append(ticks_diff(ticks_us(), start))
    return min(times), rows


def _stage_memory(vm):
    import gc
    gc.collect()
    _record('Free heap, SRAM screen', gc.mem_free() // 1024, 'KB')
    _record('Screen mode at start', 'SRAM' if getattr(vm.draw, 'mode', 1) == 1 else 'PSRAM', '')


def _stage_swaps(vm):
    draw = vm.draw
    took, rows = _swap_full(draw)
    _record('Swap, whole screen changed', took / 1000, 'ms (%d rows)' % rows)
    # One text line changes: what a menu cursor or typing costs.
    draw._clear(BLACK)
    _text_screen(draw)
    draw.swap()
    times, rows = [], 0
    for i in range(8):
        draw._fill_rectangle(0, 120, 320, 12, BLACK)
        draw._text(2, 120, 'Changed line %d' % i, WHITE, FONT)
        start = ticks_us()
        rows = draw.swap()
        times.append(ticks_diff(ticks_us(), start))
    _record('Swap, one text line changed', min(times) / 1000, 'ms (%d rows)' % rows)
    # Everything redrawn but identical: rows are hashed, nothing is sent.
    times = []
    for _ in range(4):
        draw._clear(BLACK)
        _text_screen(draw)
        start = ticks_us()
        rows = draw.swap()
        times.append(ticks_diff(ticks_us(), start))
    _record('Swap, identical redraw', min(times) / 1000, 'ms (%d rows)' % rows)


def _stage_drawing(vm, label):
    draw = vm.draw
    draw._clear(BLACK)
    _record('Draw 26 text rows, ' + label, _best(lambda: _text_screen(draw), 3) / 1000, 'ms')
    draw._clear(BLACK)
    _record('Draw 150 shapes, ' + label, _best(lambda: _shapes(draw), 2) / 1000, 'ms')
    draw.swap()


def _stage_psram(vm):
    import gc
    draw = vm.draw
    if not hasattr(draw, 'MODE_PSRAM'):
        _record('PSRAM screen mode', 'not available', '')
        return
    draw.set_mode(draw.MODE_PSRAM)
    try:
        gc.collect()
        _record('Free heap, PSRAM screen', gc.mem_free() // 1024, 'KB')
        _stage_drawing(vm, 'PSRAM')
        took, rows = _swap_full(draw)
        _record('Swap whole screen, PSRAM', took / 1000, 'ms (%d rows)' % rows)
    finally:
        draw.set_mode(draw.MODE_SRAM)


def _test_pattern(draw):
    draw._clear(BLACK)
    colours = (0xF800, 0x07E0, 0x001F, 0xFFE0, 0xF81F, 0x07FF, WHITE, GREY)
    names = ('red', 'green', 'blue', 'yellow', 'magenta', 'cyan', 'white', 'grey')
    for i, colour in enumerate(colours):
        draw._fill_rectangle(8 + i * 38, 60, 34, 120, colour)
        draw._text(8 + i * 38, 186, names[i][:5], WHITE, 0)
    draw._text(8, 8, '12-bit colour test', WHITE, 2)
    draw._text(8, 220, 'Bars left to right: red, green, blue,', WHITE, FONT)
    draw._text(8, 234, 'yellow, magenta, cyan, white, grey.', WHITE, FONT)
    draw._text(8, 260, 'Correct?  Y = yes   N = no', WHITE, FONT)
    draw._text(8, 280, '(the screen returns to normal next)', GREY, FONT)


def _stage_panel_start(vm):
    """Experimental 12-bit panel format: time it, then ask if it looks right."""
    global _waiting
    draw = vm.draw
    if not hasattr(draw, 'set_panel_bits') or not draw.set_panel_bits(12):
        _record('12-bit panel format', 'not available', '')
        return
    took, rows = _swap_full(draw)
    _record('Swap whole screen, 12-bit', took / 1000, 'ms (%d rows)' % rows)
    _test_pattern(draw)
    draw.swap()
    _waiting = True


def _stage_panel_answer(vm, answer):
    vm.draw.set_panel_bits(16)
    _record('12-bit colours looked right', 'yes' if answer else 'no', '')


def _stage_compute(vm):
    from array import array
    n = 2000
    a = array('f', [i * 0.001 for i in range(n)])
    b = array('f', [1.0 - i * 0.0005 for i in range(n)])

    def python_dot():
        total = 0.0
        for i in range(n):
            total += a[i] * b[i]
        return total

    python = _best(python_dot, 3)
    _record('Python loop, 2000 multiply-adds', python / 1000, 'ms')
    try:
        from ulab import numpy as np
        x, y = np.array(a), np.array(b)
        native = _best(lambda: np.dot(x, y), 5)
        _record('ulab (C), 2000 multiply-adds', native / 1000, 'ms')
        if native:
            _record('Python / C speed ratio', python // native, 'x')
    except ImportError:
        _record('ulab', 'not available', '')


def _format(value):
    return ('%.2f' % value) if isinstance(value, float) else str(value)


def _report(vm):
    global _saved
    lines = ['%s: %s %s' % (label, _format(value), unit) for label, value, unit in _results]
    try:
        import sys
        lines.insert(0, 'GungOS benchmark, %s' % sys.implementation._machine)
    except AttributeError:
        pass
    _saved = RESULT_PATH if vm.storage.write(RESULT_PATH, '\n'.join(lines) + '\n') else ''
    draw = vm.draw
    draw._clear(BLACK)
    for i, line in enumerate(lines[:22]):
        draw._text(2, 2 + i * 13, line[:52], WHITE, 0)
    footer = ('Saved to ' + _saved) if _saved else 'Could not save results'
    draw._text(2, 300, footer + '   Esc: back', GREY, 0)
    draw.swap()


STAGES = (
    ('Memory', _stage_memory),
    ('Sending changes', _stage_swaps),
    ('Drawing in SRAM', lambda vm: _stage_drawing(vm, 'SRAM')),
    ('PSRAM screen mode', _stage_psram),
    ('12-bit colour (experimental)', _stage_panel_start),
    ('Python versus C', _stage_compute),
)


def start(vm):
    global _stage, _results, _waiting, _saved
    _stage, _results, _waiting, _saved = -1, [], False, ''
    _status(vm.draw, 'Display, memory and processor.', (
        'Takes about half a minute. The screen',
        'flashes and changes colour meanwhile.',
        '',
        'One step shows a colour test: answer',
        'Y if it looks right, N if not.',
        '',
        'Results are saved to the SD card.',
        '',
        'Enter: start    Esc: back'))
    return True


def run(vm):
    global _stage, _waiting
    button = vm.button
    if button == k.BUTTON_ESCAPE:
        if _waiting:
            _stage_panel_answer(vm, False)
            _waiting = False
        vm.back()
        return
    if _waiting:
        if button in (k.BUTTON_Y, k.BUTTON_N):
            _stage_panel_answer(vm, button == k.BUTTON_Y)
            _waiting = False
            _stage += 1
        return
    if _stage == -1:
        if button == k.BUTTON_CENTER:
            _stage = 0
        return
    if _stage < len(STAGES):
        title, function = STAGES[_stage]
        _status(vm.draw, 'Step %d of %d: %s' % (_stage + 1, len(STAGES), title))
        function(vm)
        if not _waiting:
            _stage += 1
        if _stage == len(STAGES):
            _report(vm)
            _stage += 1


def stop(vm):
    global _waiting
    if _waiting:
        vm.draw.set_panel_bits(16)
        _waiting = False
