"""Core benchmark: every part of the firmware core, timed the same way on
each build so that two reports can be compared line by line.

Each stage runs in one pass of the app loop. A value within a round is the
fastest of several runs (the least disturbed one). The timing stages repeat
for several rounds; the report gives each line's mean with its minimum,
maximum and spread (standard deviation as a percentage of the mean). Results
are saved to picoware/core-benchmark.txt after every stage, so a hang leaves
the last completed stage on the SD. tools/compare-benchmark.py lines up two
reports.

Only the stages' own scratch data is written: a PSRAM block the benchmark
allocates and, when SD writes are switched on, an SD folder that is removed
at the end.
"""
from time import ticks_us, ticks_ms, ticks_diff
from picoware.system import buttons as k

RESULT_PATH = 'picoware/core-benchmark.txt'
SCRATCH = 'picoware/core-benchmark-tmp'
FONT = 1  # FONT_SMALL, 12 px rows
WHITE, BLACK, BLUE, GREY = 0xFFFF, 0x0000, 0x001F, 0x7BEF

ROUNDS = (10, 3, 1)

_stage = -1
_plan = ()      # (round, index into STAGES) in running order
_rounds = ROUNDS[0]
_sd_writes = False
_round = 1
_labels = []    # report order
_values = {}    # label -> [values], numbers or text
_units = {}     # label -> unit as first recorded
_saved = ''
_start_mode = None
_heap_at_start = None


def _measure(function, repeat):
    """(fastest, median) of repeat runs, in microseconds."""
    samples = []
    for _ in range(repeat):
        start = ticks_us()
        function()
        samples.append(ticks_diff(ticks_us(), start))
    samples.sort()
    return samples[0], samples[len(samples) // 2]


def _time(label, function, repeat=5, per=1, unit='us'):
    """Record the fastest run divided over per operations, in unit."""
    scale = {'ns': 0.001, 'us': 1, 'ms': 1000}[unit]
    best, _ = _measure(function, repeat)
    _record(label, best / per / scale, unit)
    return best


def _rate(label, function, size, repeat=3):
    """Record throughput in KB/s from the fastest run moving size bytes."""
    best, _ = _measure(function, repeat)
    _record(label, size * 1000000 / 1024 / max(1, best), 'KB/s (%d KB)' % (size // 1024))


def _record(label, value, unit):
    """Add one round's value; text values are kept once each."""
    if label not in _values:
        _labels.append(label)
        _values[label], _units[label] = [], unit
    values = _values[label]
    if isinstance(value, (int, float)) or value not in values:
        values.append(value)


def _line(label):
    """label: mean unit (min, max, spread, rounds; note), or label: value."""
    values, unit = _values[label], _units[label]
    base, _, note = unit.partition(' (') if not unit.startswith('(') else ('', '', unit[1:])
    note = note.rstrip(')')
    numbers = [v for v in values if isinstance(v, (int, float))]
    texts = [v for v in values if not isinstance(v, (int, float))]
    if not numbers:
        return '%s: %s %s' % (label, ' / '.join(str(v) for v in texts), unit)
    if len(numbers) == 1:
        details = [note] if note else []
        text = _format(numbers[0])
    else:
        mean = sum(numbers) / len(numbers)
        deviation = (sum((v - mean) ** 2 for v in numbers) / (len(numbers) - 1)) ** 0.5
        details = ['min %s' % _format(min(numbers)), 'max %s' % _format(max(numbers)),
                   'spread %.1f%%' % (deviation * 100 / mean if mean else 0), '%d rounds' % len(numbers)]
        if note:
            details.append(note)
        text = _format(float(mean))
    if texts:
        details.append(' / '.join(str(v) for v in texts))
    parts = [text] + ([base] if base else []) + (['(%s)' % ', '.join(details)] if details else [])
    return '%s: %s' % (label, ' '.join(parts))


def _format(value):
    return ('%.2f' % value) if isinstance(value, float) else str(value)


def _status(draw, title, lines=()):
    draw._clear(BLACK)
    draw._text(8, 8, 'Core benchmark', WHITE, 2)
    draw._text(8, 34, title, GREY, FONT)
    for i, line in enumerate(lines):
        draw._text(8, 60 + i * 14, line, WHITE, FONT)
    draw.swap()


class _QuietVM:
    """The view manager without the keyboard: a key pressed while a screen
    is timed must not reach that screen (the home screen would open an app)."""
    button = k.BUTTON_NONE

    def __init__(self, vm):
        self._vm = vm

    def __getattr__(self, name):
        return getattr(self._vm, name)


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
    if _start_mode in ('SRAM', 'PSRAM'):
        _use_mode(vm, _start_mode == 'SRAM')


# System ---------------------------------------------------------------------

def _measured_clock():
    """Processor MHz from the Cortex-M33 cycle counter over 100 ms of the
    crystal-driven microsecond timer, or None where there is no counter.

    The wait is a busy loop: the cycle counter stops while the core sleeps."""
    try:
        from machine import mem32
    except ImportError:
        return None
    try:
        mem32[0xE000EDFC] |= 1 << 24  # DEMCR.TRCENA: power the trace unit
        mem32[0xE0001000] |= 1        # DWT_CTRL.CYCCNTENA: count cycles
        start = ticks_us()
        first = mem32[0xE0001004]
        while ticks_diff(ticks_us(), start) < 100000:
            pass
        cycles = (mem32[0xE0001004] - first) & 0xFFFFFFFF
        took = ticks_diff(ticks_us(), start)
    except Exception:
        return None
    return cycles / took if cycles else None


def _largest_block():
    """Largest single allocation the GC heap can satisfy, to 256 bytes."""
    import gc
    gc.collect()
    low, high = 0, gc.mem_free()
    while high - low > 256:
        middle = (low + high) // 2
        try:
            block = bytearray(middle)
            block = None
            low = middle
        except MemoryError:
            high = middle
        gc.collect()
    return low


def _stage_system(vm):
    global _start_mode, _heap_at_start
    import gc
    import sys
    try:
        import os
        _record('Firmware build', os.uname().version, '')
    except (ImportError, AttributeError):
        _record('Firmware build', 'unknown', '')
    _record('Uptime at start', ticks_ms() // 1000, 's')
    _start_mode = _mode_name(vm.draw)
    _record('Screen mode at start', _start_mode, '')
    try:
        import machine
        _record('Processor clock, reported', machine.freq() // 1000000, 'MHz')
    except (ImportError, AttributeError):
        pass
    gc.collect()
    free, used = gc.mem_free(), gc.mem_alloc()
    _heap_at_start = free
    _record('Heap total', (free + used) // 1024, 'KB')
    _record('Heap free at start', free // 1024, 'KB')
    _record('Largest free block at start', _largest_block() // 1024, 'KB')
    _record('Modules loaded', len(sys.modules), '(%d search paths)' % len(sys.path))
    try:
        from picoware.system.psram import PSRAM
        _record('PSRAM free', PSRAM().mem_free() // 1024, 'KB')
    except Exception as e:
        _record('PSRAM free', 'not available (%s)' % e, '')


def _stage_clock(vm):
    # Its own step, after the system values are saved: it is the only stage
    # that writes processor registers (to turn the cycle counter on).
    measured = _measured_clock()
    _record('Processor clock, measured', measured if measured else 'not available',
            'MHz (cycle counter against the crystal timer)' if measured else '')


# Interpreter ----------------------------------------------------------------

_N = 4000
_GLOBAL = 5


class _Thing:
    def __init__(self):
        self.value = 1

    def method(self, value):
        return value


def _call(value):
    return value


def _count(n):
    for i in range(n):
        yield i


def _empty(n):
    for i in range(n):
        pass


def _int_math(n):
    x = 0
    for i in range(n):
        x = (x + i * 3) & 0xFFFF


def _float_math(n):
    x = 1.0
    for i in range(n):
        x = x * 1.0001 + 0.5


def _global_read(n):
    for i in range(n):
        x = _GLOBAL


def _attribute_read(n):
    thing = _Thing()
    for i in range(n):
        x = thing.value


def _function_call(n):
    for i in range(n):
        _call(i)


def _method_call(n):
    thing = _Thing()
    for i in range(n):
        thing.method(i)


def _dict_read(n):
    table = {'alpha': 1, 'beta': 2, 'gamma': 3}
    for i in range(n):
        x = table['beta']


def _list_append(n):
    items = []
    for i in range(n):
        items.append(i)


def _tuple_build(n):
    for i in range(n):
        x = (i, i)


def _bytearray_write(n):
    buffer = bytearray(256)
    for i in range(n):
        buffer[i & 255] = i & 255


def _string_format(n):
    for i in range(n):
        x = '%d' % i


def _string_concat(n):
    for i in range(n):
        x = 'value ' + str(i)


def _generator(n):
    for i in _count(n):
        pass


def _exception(n):
    for i in range(n):
        try:
            raise ValueError
        except ValueError:
            pass


def _stage_interpreter(vm):
    import gc
    for label, function in (('empty loop', _empty), ('integer arithmetic', _int_math),
                            ('float arithmetic', _float_math), ('global read', _global_read),
                            ('attribute read', _attribute_read), ('function call', _function_call),
                            ('method call', _method_call), ('dict read', _dict_read),
                            ('list append', _list_append), ('two-item tuple', _tuple_build),
                            ('bytearray write', _bytearray_write), ('%d format', _string_format),
                            ('string concatenation', _string_concat), ('generator step', _generator)):
        _time('Python ' + label, lambda: function(_N), 3, _N, 'ns')
    _time('Python raise and catch', lambda: _exception(500), 3, 500, 'us')
    gc.collect()
    _time('Garbage collection, full', gc.collect, 5, 1, 'ms')

    def churn():
        for _ in range(1000):
            bytearray(32)
    _time('Allocate 32 bytes (1000 times, collections included)', churn, 3, 1000, 'us')


# Imports --------------------------------------------------------------------

def _import_once(name):
    """Microseconds to import name afresh; sys.modules and the parent package
    are put back as they were, so the running modules are left in use."""
    import sys
    old = sys.modules.pop(name, None)
    parent, _, child = name.rpartition('.')
    package = sys.modules.get(parent)
    start = ticks_us()
    try:
        __import__(name)
        return ticks_diff(ticks_us(), start)
    finally:
        if old is not None:
            sys.modules[name] = old
            if package is not None:
                setattr(package, child, old)
        else:
            sys.modules.pop(name, None)
            if package is not None and hasattr(package, child):
                delattr(package, child)


def _stage_imports(vm):
    import sys
    for name in ('picoware.gui.alert', 'picoware.gui.list', 'picoware.gui.textbox',
                 'picoware.system.settings', 'picoware.gui.file_browser'):
        _record('Import %s (frozen)' % name, min(_import_once(name) for _ in range(3)) / 1000, 'ms')
    _record('Import engtools.bench.models (SD .mpy)',
            min(_import_once('engtools.bench.models') for _ in range(3)) / 1000, 'ms')
    import picoware.gui.alert
    _time('Import of a module already loaded', lambda: __import__('picoware.gui.alert'), 5, 1, 'us')

    def missing():
        try:
            __import__('gungos_benchmark_missing')
        except ImportError:
            pass
    _time('Import of a missing module (%d search paths)' % len(sys.path), missing, 3, 1, 'ms')


# Display --------------------------------------------------------------------

def _primitives(draw, label):
    from picoware.system.vector import Vector
    _time('Clear whole screen, ' + label, lambda: draw._clear(BLACK), 5, 1, 'us')

    def pixels():
        for i in range(500):
            draw._pixel(i % 320, i // 2, WHITE)
    _time('Pixel, ' + label, pixels, 3, 500, 'us')

    def hlines():
        for y in range(0, 300, 3):
            draw._line(0, y, 319, y, WHITE)
    _time('Line, horizontal full width, ' + label, hlines, 3, 100, 'us')

    def diagonals():
        for i in range(100):
            draw._line(0, i * 3, 319, 319 - i * 3, WHITE)
    _time('Line, diagonal full screen, ' + label, diagonals, 3, 100, 'us')

    def outlines():
        for i in range(100):
            draw._rectangle(i, i, 100, 60, WHITE)
    _time('Rectangle outline 100x60, ' + label, outlines, 3, 100, 'us')

    def small_fills():
        for i in range(100):
            draw._fill_rectangle(i * 2, i, 32, 32, BLUE)
    _time('Fill rectangle 32x32, ' + label, small_fills, 3, 100, 'us')
    _time('Fill rectangle 320x320, ' + label, lambda: draw._fill_rectangle(0, 0, 320, 320, BLUE), 5, 1, 'us')

    def rounded():
        for i in range(50):
            draw._fill_round_rectangle(10, i * 5, 300, 24, 6, BLUE)
    _time('Fill round rectangle 300x24, ' + label, rounded, 3, 50, 'us')

    def circles():
        for i in range(50):
            draw._circle(160, 160, 20 + i, WHITE)
    _time('Circle outline r20-70, ' + label, circles, 3, 50, 'us')

    def disks():
        for i in range(20):
            draw._fill_circle(160, 160, 40, BLUE)
    _time('Fill circle r40, ' + label, disks, 3, 20, 'us')

    def triangles():
        for i in range(50):
            draw._fill_triangle(i * 4, 300, i * 4 + 60, 180, i * 4 + 120, 310, BLUE)
    _time('Fill triangle, ' + label, triangles, 3, 50, 'us')
    icon = bytes(24 * 24)

    def icons():
        for i in range(50):
            draw._bytearray(i * 6, 100, 24, 24, icon)
    _time('8-bit image 24x24, ' + label, icons, 3, 50, 'us')
    line = 'Settings > Display > Brightness 42 percent'
    for font in (0, 1, 2):
        def texts():
            for row in range(20):
                draw._text(2, row * 14, line, WHITE, font)
        _time('Text, 42 characters, font %d, %s' % (font, label), texts, 3, 20, 'us')
    _time('Text width of 42 characters, ' + label, lambda: draw.len(line, 1), 5, 1, 'us')
    # The Python wrappers apps call, against the C calls above.
    position, size = Vector(10, 10), Vector(32, 32)

    def wrapped_fills():
        for i in range(100):
            draw.fill_rectangle(position, size, BLUE)
    _time('Fill rectangle 32x32 through Draw, ' + label, wrapped_fills, 3, 100, 'us')

    def wrapped_texts():
        for row in range(20):
            draw.text(position, line, WHITE, 1)
    _time('Text, 42 characters through Draw, ' + label, wrapped_texts, 3, 20, 'us')


def _swaps(draw, label):
    """Present costs: every row changed, one text line, a quarter, nothing."""
    def timed_swaps(prepare, repeat):
        samples = []
        for i in range(repeat):
            prepare(i)
            start = ticks_us()
            rows = draw.swap()
            samples.append((ticks_diff(ticks_us(), start), rows))
        samples.sort()
        return samples[0], samples[len(samples) // 2][0]
    draw._clear(BLACK)
    draw.swap()
    (best, rows), median = timed_swaps(lambda i: draw._clear(BLUE if i % 2 == 0 else BLACK), 6)
    _record('Swap, whole screen changed, ' + label, best, 'us (%d rows)' % rows)
    (best, rows), median = timed_swaps(lambda i: draw._fill_rectangle(0, 80, 320, 80, BLUE if i % 2 == 0 else BLACK), 6)
    _record('Swap, quarter screen changed, ' + label, best, 'us (%d rows)' % rows)

    def one_line(i):
        draw._fill_rectangle(0, 120, 320, 12, BLACK)
        draw._text(2, 120, 'Changed line %d' % i, WHITE, FONT)
    (best, rows), median = timed_swaps(one_line, 8)
    _record('Swap, one text line changed, ' + label, best, 'us (%d rows)' % rows)
    (best, rows), median = timed_swaps(lambda i: None, 8)
    _record('Swap, nothing changed, ' + label, best, 'us (%d rows)' % rows)


def _stage_display(vm, sram):
    import gc
    label = 'SRAM' if sram else 'PSRAM'
    if not _use_mode(vm, sram):
        _record(label + ' screen mode', 'not available (not enough free memory?)', '')
        return
    try:
        gc.collect()
        _record('Free heap, %s screen' % label, gc.mem_free() // 1024, 'KB')
        _primitives(vm.draw, label)
        _swaps(vm.draw, label)
    finally:
        _restore_mode(vm)


# GUI ------------------------------------------------------------------------

def _stage_gui(vm):
    """The core screens apps are built from, drawn without the keyboard."""
    import gc
    draw = vm.draw
    fg, bg, accent = vm.foreground_color, vm.background_color, vm.selected_color
    quiet = _QuietVM(vm)
    from picoware.gui.menu import Menu
    menu = Menu(draw, 'Benchmark', 0, 320, fg, bg, accent)
    for i in range(30):
        menu.add_item('Menu entry %d' % i)
    _time('Menu of 30 entries, draw', menu.draw, 5, 1, 'ms')

    def scroll_frame():
        menu.scroll_down()
        draw.swap()
    _time('Menu, move down one entry and present', scroll_frame, 5, 1, 'ms')
    from picoware.gui.list import List
    items = List(draw, 0, 320, fg, bg, accent)
    for i in range(30):
        items.add_item('List entry %d' % i)
    _time('List of 30 entries, draw', lambda: items.draw(False), 5, 1, 'ms')
    _time('List, move down one entry', lambda: items.scroll_down(False), 5, 1, 'ms')
    from picoware.gui.textbox import TextBox
    text = '\n'.join('Line %d of a long help page, wrapped to the screen width when needed.' % i
                     for i in range(120))
    box = TextBox(draw, 0, 320, fg, bg)
    _time('Text box, set 120 lines (%d KB)' % (len(text) // 1024), lambda: box.set_text(text), 3, 1, 'ms')
    _time('Text box, redraw', box.refresh, 5, 1, 'ms')
    _time('Text box, scroll one line', box.scroll_down, 5, 1, 'ms')
    _time('Text box, jump to the end', box.jump_to_bottom, 3, 1, 'ms')
    box = None
    from picoware.gui.alert import Alert
    alert = Alert(draw, 'Benchmark alert with a message that wraps over two lines.', fg, bg)
    _time('Alert, draw', lambda: alert.draw('Alert'), 5, 1, 'ms')
    from picoware.gui.status_bar import StatusBar
    bar = StatusBar(quiet)
    _time('Status bar, read clock and battery', lambda: bar.sample(True), 5, 1, 'ms')
    state = bar.sample(True)
    _time('Status bar, draw', lambda: bar.draw(state), 5, 1, 'ms')
    previous = vm._keyboard
    try:
        keyboard = vm.keyboard
        keyboard.reset()
        keyboard.response = 'Benchmark text'
        _time('On-screen keyboard frame, draw', lambda: keyboard.run(False, True), 5, 1, 'ms')
        keyboard.reset()
    finally:
        vm._keyboard = previous
    gc.collect()
    from picoware.gui.dashboard import Dashboard
    start = ticks_us()
    home = Dashboard(quiet)
    _record('Home screen, open (screensaver widget included)', ticks_diff(ticks_us(), start) / 1000, 'ms')
    try:
        home.update()  # first frame: snapshot, status bar and full draw
        _time('Home screen, full draw', home.draw, 5, 1, 'ms')
        home.dirty = False
        _time('Home screen, idle frame (no key)', home.update, 10, 1, 'ms')
    finally:
        home.stop()
        home = None
        gc.collect()


# System services ------------------------------------------------------------

def _stage_services(vm):
    from picoware.system.vector import Vector
    from picoware.system.resource_info import snapshot, lines
    from picoware.system.settings import Settings
    inputs = vm.input_manager

    def buttons():
        for _ in range(200):
            inputs.button
    _time('Input.button read', buttons, 3, 200, 'us')
    try:
        from picoware_keyboard import key_available

        def polls():
            for _ in range(50):
                key_available()
        _time('Keyboard key_available()', polls, 3, 50, 'us')
    except ImportError:
        pass
    _time('Battery percentage (southbridge)', lambda: vm.battery.percentage, 5, 1, 'ms')
    try:
        from machine import RTC
        clock = RTC()
        _time('Real-time clock read', clock.datetime, 5, 1, 'us')
    except (ImportError, AttributeError):
        pass
    _time('Resource snapshot (home screen, every 5 s)', lambda: snapshot(vm), 3, 1, 'ms')
    info = snapshot(vm)
    _time('Resource snapshot, text lines', lambda: lines(info), 5, 1, 'us')
    _time('Settings load from SD', lambda: Settings(vm.storage), 3, 1, 'ms')
    manager = vm.thread_manager

    def idle_threads():
        for _ in range(100):
            manager.run()
    _time('Thread manager, idle step', idle_threads, 3, 100, 'us')
    if vm.has_wifi and vm.wifi is not None:
        wifi = vm.wifi

        def polls():
            for _ in range(100):
                wifi.poll()
        _time('Wi-Fi poll', polls, 3, 100, 'us')

    def vectors():
        for i in range(200):
            Vector(i, i)
    _time('Vector creation', vectors, 3, 200, 'us')


# PSRAM ----------------------------------------------------------------------

def _stage_psram(vm):
    import gc
    try:
        from picoware.system.psram import PSRAM
        psram = PSRAM()
    except Exception as e:
        _record('PSRAM', 'not available (%s)' % e, '')
        return
    size = 64 * 1024
    start = ticks_us()
    block = psram.malloc(bytearray(size))  # the benchmark's own block
    _record('PSRAM allocate and write 64 KB', ticks_diff(ticks_us(), start) / 1000, 'ms')
    try:
        base = block.addr()
        chunk = bytearray(4096)

        def writes():
            for offset in range(0, size, 4096):
                psram.write(base + offset, chunk)
        _rate('PSRAM write, 4 KB pieces', writes, size)
        _rate('PSRAM read into a 4 KB buffer', lambda: psram.read_into(base, chunk), 4096)
        _rate('PSRAM read 4 KB as bytes', lambda: psram.read(base, 4096), 4096)
        _rate('PSRAM fill 64 KB', lambda: psram.fill(base, 0, size), size)
        _rate('PSRAM copy 32 KB inside PSRAM', lambda: psram.copy(base, base + size // 2, size // 2), size // 2)

        def bytes8():
            for i in range(200):
                psram.write8(base + i, i & 255)
                psram.read8(base + i)
        _time('PSRAM 8-bit write and read', bytes8, 3, 200, 'us')
        draw = vm.draw
        if hasattr(draw, '_psram'):
            _time('Draw 64x64 pixels from PSRAM', lambda: draw._psram(0, 0, 64, 64, base), 5, 1, 'us')
    finally:
        block = None
        gc.collect()


# SD card --------------------------------------------------------------------

def _clear_scratch(storage):
    if not storage.exists(SCRATCH):
        return
    for name in storage.listdir(SCRATCH):
        storage.remove(SCRATCH + '/' + name)
    storage.rmdir(SCRATCH)


def _stage_sd(vm):
    """SD card through the firmware's driver, reading and writing in a
    scratch folder that is removed afterwards."""
    storage = vm.storage
    if not storage.active:
        _record('SD card', 'not available', '')
        return
    import sd_mp
    _time('SD free space query', lambda: storage.free_space, 1, 1, 'ms')
    _clear_scratch(storage)
    storage.mkdir(SCRATCH)
    try:
        path = SCRATCH + '/data.bin'
        size = 64 * 1024
        data = bytes(range(256)) * (size // 256)
        _rate('SD write 64 KB file in one call', lambda: sd_mp.write(path, data, True), size)
        piece = data[:512]

        def appends():
            sd_mp.write(path, piece, True)
            for _ in range(31):
                sd_mp.write(path, piece, False)
        _time('SD append 512 bytes (32 appends)', appends, 2, 32, 'ms')
        sd_mp.write(path, data, True)
        buffer = bytearray(4096)

        def read_pieces():
            handle = storage.file_open(path)
            try:
                while storage.file_readinto(handle, buffer):
                    pass
            finally:
                storage.file_close(handle)
        _rate('SD read 64 KB in 4 KB pieces', read_pieces, size)

        def read_small():
            handle = storage.file_open(path)
            try:
                for offset in range(0, size, 512):
                    storage.file_read(handle, offset, 512, decode=False)
            finally:
                storage.file_close(handle)
        _rate('SD read 64 KB in 512-byte pieces', read_small, size)
        _rate('SD read 64 KB file whole', lambda: storage.read(path, 'rb'), size)
        if storage.vfs_mounted:
            full = storage.vfs_prefix + '/' + path

            def vfs_write():
                with open(full, 'wb') as handle:
                    for _ in range(128):
                        handle.write(piece)
            _rate('SD write 64 KB through open() in 512-byte writes', vfs_write, size, 2)

            def vfs_read():
                with open(full, 'rb') as handle:
                    while handle.readinto(buffer):
                        pass
            _rate('SD read 64 KB through open() in 4 KB reads', vfs_read, size)
        names = [SCRATCH + '/file-with-a-long-name-%02d.txt' % i for i in range(16)]

        def creates():
            for name in names:
                storage.write(name, 'small file contents\n')
        _time('SD create small file (16, long names)', creates, 1, 16, 'ms')
        _time('SD list folder of 17 files', lambda: storage.listdir(SCRATCH), 3, 1, 'ms')
        _time('SD look up existing file', lambda: [storage.exists(n) for n in names], 3, 16, 'ms')
        missing = [SCRATCH + '/missing-%02d.mpy' % i for i in range(16)]
        _time('SD look up missing file', lambda: [storage.exists(n) for n in missing], 3, 16, 'ms')
        renamed = SCRATCH + '/renamed-file-with-a-long-name.txt'

        def renames():
            storage.rename(names[0], renamed)
            storage.rename(renamed, names[0])
        _time('SD rename (there and back)', renames, 3, 2, 'ms')
        settings = {'theme_color': 31, 'screen_brightness': 80, 'gmt_offset': 2,
                    'onscreen_keyboard': True, 'screensaver': 'Lorenz', 'debug': False}
        _time('SD save settings as JSON', lambda: storage.serialize(settings, SCRATCH + '/settings.json'), 3, 1, 'ms')
        _time('SD load settings JSON', lambda: storage.deserialize(SCRATCH + '/settings.json'), 3, 1, 'ms')
        _time('SD delete small file (16)', lambda: [storage.remove(n) for n in names], 1, 16, 'ms')
    finally:
        _clear_scratch(storage)


# Memory after ---------------------------------------------------------------

def _stage_memory_after(vm):
    import gc
    import sys
    gc.collect()
    free = gc.mem_free()
    _record('Heap free at end', free // 1024, 'KB')
    if _heap_at_start is not None:
        _record('Heap free, end minus start', (free - _heap_at_start) // 1024,
                'KB (negative: memory still held after the stages)')
    _record('Largest free block at end', _largest_block() // 1024, 'KB')
    _record('Modules loaded at end', len(sys.modules), '')


STAGES = (
    ('System and memory', _stage_system),
    ('Processor clock check', _stage_clock),
    ('Python interpreter', _stage_interpreter),
    ('Imports', _stage_imports),
    ('Drawing, SRAM screen', lambda vm: _stage_display(vm, True)),
    ('Drawing, PSRAM screen', lambda vm: _stage_display(vm, False)),
    ('Screens (menu, text, home)', _stage_gui),
    ('System services', _stage_services),
    ('PSRAM', _stage_psram),
    ('SD card', _stage_sd),
    ('Memory afterwards', _stage_memory_after),
)


FIRST, SD_STAGE, LAST = (0, 1), 9, 10  # once only; every other stage repeats


def _make_plan():
    """System steps, the timing steps for each round (the SD card after the
    first round's, when switched on), and the memory check at the end."""
    repeated = [i for i in range(len(STAGES)) if i not in FIRST + (SD_STAGE, LAST)]
    plan = [(1, i) for i in FIRST]
    for number in range(1, _rounds + 1):
        plan.extend((number, i) for i in repeated)
        if number == 1 and _sd_writes:
            plan.append((1, SD_STAGE))
    plan.append((_rounds, LAST))
    return tuple(plan)


def _checkpoint(vm, status):
    """Keep completed measurements on SD before attempting the next stage."""
    global _saved
    lines = ['Status: ' + status]
    try:
        import sys
        lines.insert(0, 'GungOS core benchmark, %s' % sys.implementation._machine)
    except AttributeError:
        pass
    lines.extend(_line(label) for label in _labels)
    _saved = RESULT_PATH if vm.storage.write(RESULT_PATH, '\n'.join(lines) + '\n') else ''
    return lines


def _report(vm):
    _restore_mode(vm)
    lines = _checkpoint(vm, 'complete, %d rounds' % _rounds)
    draw = vm.draw
    draw._clear(BLACK)
    for i, line in enumerate(lines[:22]):
        draw._text(2, 2 + i * 13, line[:52], WHITE, 0)
    footer = ('All %d results in %s' % (len(_labels), _saved)) if _saved else 'Could not save results'
    draw._text(2, 300, footer[:40] + '  Esc: back', GREY, 0)
    draw.swap()


def _intro(vm):
    _status(vm.draw, 'Every part of the firmware core.', (
        'F2 Rounds: %d (about %d min)' % (_rounds, 1 + _rounds * 3 // 2),
        'F3 SD card writes: ' + ('ON, first round' if _sd_writes else 'OFF'),
        '',
        'Each timing repeats every round;',
        'the report gives mean, min, max.',
        'Restart first, so every run starts',
        'from the same memory state.',
        'SD writes use a scratch folder',
        'that is removed afterwards.',
        'Saved after each step to',
        RESULT_PATH + '.',
        '',
        'Enter: start    Esc: back'))


def start(vm):
    global _stage, _plan, _rounds, _sd_writes, _round, _labels, _values, _units
    global _saved, _start_mode, _heap_at_start
    _stage, _plan, _rounds, _sd_writes, _round = -1, (), ROUNDS[0], False, 1
    _labels, _values, _units = [], {}, {}
    _saved, _start_mode, _heap_at_start = '', None, None
    _intro(vm)
    return True


def run(vm):
    global _stage, _plan, _rounds, _sd_writes, _round
    button = vm.button
    if button == k.BUTTON_ESCAPE:
        if 0 <= _stage < len(_plan):
            _restore_mode(vm)
            _checkpoint(vm, 'cancelled in round %d of %d' % (_round, _rounds))
        vm.back()
        return
    if _stage == -1:
        if button == k.BUTTON_F2:
            _rounds = ROUNDS[(ROUNDS.index(_rounds) + 1) % len(ROUNDS)]
            _intro(vm)
        elif button == k.BUTTON_F3:
            _sd_writes = not _sd_writes
            _intro(vm)
        elif button in (k.BUTTON_CENTER, k.BUTTON_ENTER):
            _plan, _stage = _make_plan(), 0
            _record('Rounds', _rounds, '')
            if not _sd_writes:
                _record(STAGES[SD_STAGE][0], 'skipped (writes off; F3 on the first screen)', '')
        return
    if _stage < len(_plan):
        _round, index = _plan[_stage]
        title, function = STAGES[index]
        where = 'round %d of %d, step %d of %d: %s' % (_round, _rounds, _stage + 1, len(_plan), title)
        _status(vm.draw, 'Round %d of %d' % (_round, _rounds), ('Step %d of %d' % (_stage + 1, len(_plan)), title))
        _checkpoint(vm, 'running ' + where)
        try:
            function(vm)
        except MemoryError:
            # A result like any other: later stages still run, and what this
            # stage measured before failing is kept.
            import gc
            gc.collect()
            _record(title, 'ran out of memory in round %d (%d KB free afterwards)' % (_round, gc.mem_free() // 1024), '')
        except Exception as e:
            _record(title, 'failed in round %d: %s: %s' % (_round, type(e).__name__, e), '')
        _checkpoint(vm, 'finished ' + where)
        _stage += 1
        if _stage == len(_plan):
            _report(vm)
            _stage += 1


def stop(vm):
    _restore_mode(vm)
