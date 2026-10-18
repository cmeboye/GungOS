"""Device benchmark: display pipeline, screen-image modes and Python versus C.

Each stage runs in one pass of the app loop so the screen stays responsive.
Results are shown at the end and saved to picoware/benchmark.txt.
"""
from time import ticks_us, ticks_ms, ticks_diff
from picoware.system import buttons as k

RESULT_PATH = 'picoware/benchmark.txt'
FONT = 1  # FONT_SMALL, 12 px rows
WHITE, BLACK, BLUE, GREY = 0xFFFF, 0x0000, 0x001F, 0x7BEF

_stage = 0
_results = []   # (label, value, unit)
_waiting = False
_saved = ''
_panel_test = False
_prompt_started = 0
_start_mode = None


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
    """Time only full-screen changes, keeping each time with its row count."""
    # The status screen is mostly black. Clearing it to black can change only
    # a few text rows, so establish an untimed baseline before alternating.
    draw._clear(BLACK)
    draw.swap()
    samples = []
    expected = int(draw.size.y)
    for i in range(6):
        draw._clear(BLUE if i % 2 == 0 else BLACK)
        start = ticks_us()
        rows = draw.swap()
        took = ticks_diff(ticks_us(), start)
        if rows != expected:
            raise RuntimeError('Full-screen sample sent %d rows; expected %d' % (rows, expected))
        samples.append((took, rows))
    return min(samples)


def _mode_name(draw):
    if not hasattr(draw, 'MODE_SRAM'):
        return 'unknown'
    return 'SRAM' if draw.mode == draw.MODE_SRAM else 'PSRAM'


def _use_mode(vm, sram):
    """Move the screen image; True if it ended up where asked."""
    import gc
    draw = vm.draw
    if not hasattr(draw, 'MODE_SRAM'):
        return False
    target = draw.MODE_SRAM if sram else draw.MODE_PSRAM
    if draw.mode != target:
        gc.collect()
        draw.set_mode(target)
    return draw.mode == target


def _restore_mode(vm):
    if _start_mode is not None:
        _use_mode(vm, _start_mode == 'SRAM')


def _stage_memory(vm):
    global _start_mode
    _start_mode = _mode_name(vm.draw)
    _record('Screen mode at start', _start_mode, '')


def _stage_swaps(vm, label):
    draw = vm.draw
    took, rows = _swap_full(draw)
    _record('Swap, whole screen changed, ' + label, took / 1000, 'ms (%d rows)' % rows)
    # One text line changes: what a menu cursor or typing costs.
    draw._clear(BLACK)
    _text_screen(draw)
    draw.swap()
    samples = []
    for i in range(8):
        draw._fill_rectangle(0, 120, 320, 12, BLACK)
        draw._text(2, 120, 'Changed line %d' % i, WHITE, FONT)
        start = ticks_us()
        rows = draw.swap()
        samples.append((ticks_diff(ticks_us(), start), rows))
    took, rows = min(samples)
    _record('Swap, one text line changed, ' + label, took / 1000, 'ms (%d rows)' % rows)
    # Establish the exact baseline before timing identical redraws.
    draw._clear(BLACK)
    _text_screen(draw)
    draw.swap()
    samples = []
    for _ in range(4):
        draw._clear(BLACK)
        _text_screen(draw)
        start = ticks_us()
        rows = draw.swap()
        samples.append((ticks_diff(ticks_us(), start), rows))
    took, rows = min(samples)
    _record('Swap, identical redraw, ' + label, took / 1000, 'ms (%d rows)' % rows)


def _stage_drawing(vm, label):
    draw = vm.draw
    draw._clear(BLACK)
    _record('Draw 26 text rows, ' + label, _best(lambda: _text_screen(draw), 3) / 1000, 'ms')
    draw._clear(BLACK)
    _record('Draw 150 shapes, ' + label, _best(lambda: _shapes(draw), 2) / 1000, 'ms')
    draw.swap()


def _stage_mode(vm, sram):
    """Everything measured with the screen image in one place."""
    import gc
    label = 'SRAM' if sram else 'PSRAM'
    if not _use_mode(vm, sram):
        _record(label + ' screen mode', 'not available (not enough free memory?)', '')
        return
    gc.collect()
    _record('Free heap, %s screen' % label, gc.mem_free() // 1024, 'KB')
    _stage_swaps(vm, label)
    _stage_drawing(vm, label)


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
    global _waiting, _prompt_started
    draw = vm.draw
    if not _panel_test:
        _record('12-bit panel format', 'skipped (disabled by default)', '')
        return
    if not hasattr(draw, 'set_panel_bits') or not draw.set_panel_bits(12):
        _record('12-bit panel format', 'not available', '')
        return
    took, rows = _swap_full(draw)
    _record('Swap whole screen, 12-bit', took / 1000, 'ms (%d rows)' % rows)
    _test_pattern(draw)
    draw.swap()
    _prompt_started = ticks_ms()
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


def _checkpoint(vm, status):
    """Keep completed measurements on SD before attempting the next stage."""
    global _saved
    lines = ['Status: ' + status]
    try:
        import sys
        lines.insert(0, 'GungOS benchmark, %s' % sys.implementation._machine)
    except AttributeError:
        pass
    lines.extend('%s: %s %s' % (label, _format(value), unit)
                 for label, value, unit in _results)
    _saved = RESULT_PATH if vm.storage.write(RESULT_PATH, '\n'.join(lines) + '\n') else ''
    return lines


def _report(vm):
    _restore_mode(vm)
    lines = _checkpoint(vm, 'complete')
    draw = vm.draw
    draw._clear(BLACK)
    for i, line in enumerate(lines[:22]):
        draw._text(2, 2 + i * 13, line[:52], WHITE, 0)
    footer = ('Saved to ' + _saved) if _saved else 'Could not save results'
    draw._text(2, 300, footer + '   Esc: back', GREY, 0)
    draw.swap()


def _intro(vm):
    _status(vm.draw, 'Display, memory and processor.', (
        'Takes about half a minute.',
        'Screen flashes during the tests.',
        '',
        'F2: 12-bit experiment ' + ('ON' if _panel_test else 'OFF'),
        'Normal tests use 16-bit colour.',
        'If the experiment stops updating',
        'the picture, press N to restore it.',
        'Y/N answer times out after 20 sec.',
        'Progress is saved between steps.',
        'Enter: start    Esc: back'))


STAGES = (
    ('Memory', _stage_memory),
    ('SRAM screen (fast drawing)', lambda vm: _stage_mode(vm, True)),
    ('PSRAM screen (default)', lambda vm: _stage_mode(vm, False)),
    ('12-bit colour (experimental)', _stage_panel_start),
    ('Python versus C', _stage_compute),
)


def start(vm):
    global _stage, _results, _waiting, _saved, _panel_test, _prompt_started, _start_mode
    _stage, _results, _waiting, _saved, _start_mode = -1, [], False, '', None
    _panel_test, _prompt_started = False, 0
    _intro(vm)
    return True


def run(vm):
    global _stage, _waiting
    button = vm.button
    if button == k.BUTTON_ESCAPE:
        if _waiting:
            _stage_panel_answer(vm, False)
            _waiting = False
        if _stage >= 0:
            _restore_mode(vm)
            _checkpoint(vm, 'cancelled')
        vm.back()
        return
    if _waiting:
        timed_out = ticks_diff(ticks_ms(), _prompt_started) >= 20000
        if button in (k.BUTTON_Y, k.BUTTON_N) or timed_out:
            _stage_panel_answer(vm, button == k.BUTTON_Y and not timed_out)
            if timed_out:
                _record('12-bit answer', 'timed out; restored 16-bit', '')
            _waiting = False
            _stage += 1
            _checkpoint(vm, '12-bit colour test ended')
        return
    if _stage == -1:
        if button == k.BUTTON_F2:
            global _panel_test
            _panel_test = not _panel_test
            _intro(vm)
        elif button == k.BUTTON_CENTER:
            _stage = 0
        return
    if _stage < len(STAGES):
        title, function = STAGES[_stage]
        _status(vm.draw, 'Step %d of %d: %s' % (_stage + 1, len(STAGES), title))
        _checkpoint(vm, 'running step %d: %s' % (_stage + 1, title))
        function(vm)
        _checkpoint(vm, 'waiting for Y/N' if _waiting else 'finished step %d: %s' % (_stage + 1, title))
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
    _restore_mode(vm)
