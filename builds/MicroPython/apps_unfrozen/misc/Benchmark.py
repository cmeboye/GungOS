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
    try:
        import machine
        _record('Processor clock', machine.freq() // 1000000, 'MHz')
    except (ImportError, AttributeError):
        pass
    import gc
    import sys
    gc.collect()
    free, used = gc.mem_free(), gc.mem_alloc()
    _record('Heap total', (free + used) // 1024, 'KB')
    _record('Heap in use when the benchmark started', used // 1024,
            'KB (%d modules loaded; lowest right after a restart)' % len(sys.modules))

    def import_array():
        from array import array
        return array
    took = _best(import_array, 3)
    _record('Import of a built-in (array) inside a function', took / 1000,
            'ms (%d search paths; %s)' % (len(sys.path), 'cached at startup' if 'array' in sys.modules
                                           else 'searches the SD card each time'))


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


def _stage_3d(vm):
    """One Graph3D frame of its default surface, Python renderer versus C."""
    try:
        from engtools.plots import plot3d as g
    except ImportError:
        _record('3-D frame', 'Graph3D not installed', '')
        return
    draw = vm.draw
    if not hasattr(draw, '_mesh3d'):
        _record('3-D frame, C renderer', 'not in this firmware', '')
    fast = _use_mode(vm, True)  # Graph3D draws with the SRAM screen
    try:
        if not g.start(vm):
            _record('3-D frame', 'Graph3D did not start', '')
            return
        vm._button = k.BUTTON_NONE
        for _ in range(5000):
            if g._state != g.ST_SAMPLING:
                break
            g.run(vm)
        if g._state != g.ST_PLOT:
            _record('3-D frame', 'surface not ready', '')
            return
        triangles = len(g._mesh_colors)
        python = _best(lambda: g._draw_mesh(draw, False, native=False), 1)
        _record('3-D frame, Python, %d triangles' % triangles, python / 1000, 'ms')
        if hasattr(draw, '_mesh3d'):
            native = _best(lambda: g._draw_mesh(draw, False, native=True), 3)
            _record('3-D frame, C, %d triangles' % triangles, native / 1000, 'ms')
            if native:
                _record('3-D frame speed-up', python // native, 'x')
        _record('3-D frame screen', 'SRAM' if fast else 'PSRAM', '')
        # Building an implicit surface: formula sampling plus meshing.
        g._expr, g._expr2, g._grid_n = 'x^2+y^2+z^2=4', '', 12

        def build(native, formula):
            g.NATIVE_FORMULA = formula
            for _ in g._sample_job(native):
                pass
        compiled = hasattr(g, '_formula') and g._formula('x') is not None
        try:
            _record('Implicit sphere mesh, Python', _best(lambda: build(False, False), 1) / 1000, 'ms')
            if hasattr(g, '_geometry') and g._geometry():
                _record('Implicit sphere mesh, C mesh', _best(lambda: build(True, False), 1) / 1000,
                        'ms (%d triangles)' % len(g._mesh_colors))
                if compiled:
                    _record('Implicit sphere mesh, C mesh + formula', _best(lambda: build(True, True), 1) / 1000, 'ms')
        finally:
            g.NATIVE_FORMULA = True
    finally:
        try:
            g.stop(vm)
        finally:
            _restore_mode(vm)


def _stage_beam(vm):
    """The built-in beam solver: building from Python, solving, diagrams."""
    try:
        import picosolve as ps
    except ImportError:
        _record('Beam solver', 'not in this firmware', '')
        return
    import gc
    from array import array
    spans = 600
    gc.collect()
    start = ticks_us()
    b = ps.Beam(spans + 1, spans, loads=spans)
    b.section(0, 2.1e11, 8.36e-5)
    for i in range(spans + 1):
        b.node(i, float(i))
    for e in range(spans):
        b.element(e, e, e + 1)
        b.line(0, e, 0.0, 1.0, -5e3)
    for i in range(0, spans + 1, 4):
        b.support(i, ps.UY)
    _record('Beam model built from Python, %d elements' % spans, ticks_diff(ticks_us(), start) / 1000, 'ms')
    try:
        for name, precision in (('double', ps.DOUBLE), ('single', ps.SINGLE)):
            took = _best(lambda: b.solve(precision), 3)
            info = b.info()
            _record('Beam solve, %s' % name, took / 1000,
                    'ms (%d equations, %d refinements)' % (info['equations'], info['refinements']))
        moments = array('f', [0.0] * 64)

        def diagrams():
            for e in range(spans):
                b.diagram(e, 64, None, moments, None, None)
        _record('Moment diagrams, %d elements x 64 points' % spans, _best(diagrams, 1) / 1000, 'ms')
        _record('Beam model memory', b.info()['bytes'] // 1024, 'KB')
    finally:
        b.free()


def _stage_formula(vm):
    """A plot formula at 4096 points: Python's eval versus picosolve.Formula."""
    try:
        from picosolve import Formula
    except ImportError:
        _record('Formula compiler', 'not in this firmware', '')
        return
    import math
    from array import array
    n = 4096
    xs = array('f', [-4 + 8 * i / (n - 1) for i in range(n)])
    out = array('f', bytes(4 * n))
    env = {'sin': math.sin, 'cos': math.cos, 'sqrt': math.sqrt, '__builtins__': {}}
    for text in ('0.6*sin(x)*cos(y)', 'x*x+y*y-9', 'sqrt(x*x+y*y)-2'):
        code = compile(text, '<f>', 'eval')
        f = Formula(text, ('x', 'y'))

        def python():
            env['y'] = 0.75
            for x in xs:
                env['x'] = x
                try:
                    eval(code, env)
                except Exception:
                    pass
        slow = _best(python, 1)
        fast = _best(lambda: f.map(out, xs, 0.75), 3)
        _record('Formula %s, 4096 points, eval' % text, slow / 1000, 'ms')
        _record('Formula %s, 4096 points, C' % text, fast / 1000,
                'ms (%dx)' % (slow // fast) if fast else 'ms')


class _QuietVM:
    """The view manager as an app sees it, without the keyboard: a key pressed
    while a plot is timed must not reach the plot."""
    button = k.BUTTON_NONE

    def __init__(self, vm):
        self._vm = vm

    def __getattr__(self, name):
        return getattr(self._vm, name)


class _Timed:
    """Forwards to an object, adding up the time spent in the named methods."""

    def __init__(self, target, names, totals):
        self._target, self._names, self._totals = target, names, totals

    def __getattr__(self, name):
        value = getattr(self._target, name)
        if name not in self._names:
            return value
        totals = self._totals

        def timed(*args):
            start = ticks_us()
            result = value(*args)
            totals[name] = totals.get(name, 0) + ticks_diff(ticks_us(), start)
            return result
        return timed

    def __call__(self, *args):
        start = ticks_us()
        result = self._target(*args)
        self._totals['call'] = self._totals.get('call', 0) + ticks_diff(ticks_us(), start)
        return result


def _stage_graph(vm):
    """Graph: the same plots drawn with its Python loops and with the C ones,
    then where the C version spends its time."""
    try:
        from engtools.plots import plot2d as G
    except ImportError:
        _record('Graph', 'not installed', '')
        return
    if not hasattr(G, 'NATIVE_DRAW'):
        _record('Graph', 'older version without C drawing', '')
        return
    import gc
    draw = vm.draw
    _record('Graph C functions in firmware', ' '.join(
        name for name in ('_plot_curve', '_plot_segments', '_stipple') if hasattr(draw, name)) or 'none', '')
    quiet = _QuietVM(vm)
    app = G.GraphApp(quiet, persistent=False)

    def render(texts, native, totals=None):
        """Draw to completion: (microseconds, run() calls, finished)."""
        G.NATIVE_FORMULA = G.NATIVE_GEOMETRY = G.NATIVE_DRAW = native
        app.items = [G.Expression(t, G.COLORS[i % len(G.COLORS)]) for i, t in enumerate(texts)]
        if totals is not None:
            app.draw = _Timed(draw, ('swap', '_plot_curve', '_plot_segments', '_stipple', '_line', '_pixel'), totals)
            for e in app.items:
                for name in ('formula', 'formula2'):
                    if getattr(e, name, None) is not None:
                        setattr(e, name, _Timed(getattr(e, name), ('map',), totals))
        app.dirty, app.refine = True, None
        calls = 0
        start = ticks_us()
        try:
            while ticks_diff(ticks_us(), start) < 30000000:
                app.run()
                calls += 1
                if app.job is None and not app.dirty and app.refine is None:
                    return ticks_diff(ticks_us(), start), calls, True
            return ticks_diff(ticks_us(), start), calls, False
        finally:
            app.draw = draw

    def note(took, calls, finished):
        return 'ms (%d runs%s)' % (calls, '' if finished else ', DID NOT FINISH')
    try:
        for label, texts in (('3 curves', ('sin(x)', 'cos(x)', 'y=x^2/4')),
                             ('shaded band', ('y>=sin(x)', 'y<=sin(x)+2')),
                             ('disk and circle', ('x^2+y^2<=9', 'x^2+y^2=25')),
                             ('heart', ('16*sin(t)^3;13*cos(t)-5*cos(2*t)-2*cos(3*t)-cos(4*t)',))):
            slow = render(texts, False)
            fast = render(texts, True)
            _record('Graph %s, Python' % label, slow[0] / 1000, note(*slow))
            _record('Graph %s, C' % label, fast[0] / 1000, note(*fast))
            # Where the C version's time goes.
            totals = {}
            took = render(texts, True, totals)[0]
            parts = ', '.join('%s %d' % (name.strip('_'), totals[name] // 1000) for name in sorted(totals))
            rest = took - sum(totals.values())
            _record('Graph %s, C time split' % label, parts + ', Python %d' % (rest // 1000), 'ms')
            gc.collect()
            gc.disable()
            try:
                no_gc = render(texts, True)
                _record('Graph %s, C, garbage collector paused' % label, no_gc[0] / 1000, note(*no_gc))
            except MemoryError:
                _record('Graph %s, C, garbage collector paused' % label, 'ran out of memory', '')
            finally:
                gc.enable()
        _record('Graph screen', _mode_name(vm.draw), '')
    finally:
        G.NATIVE_FORMULA = G.NATIVE_GEOMETRY = G.NATIVE_DRAW = True


def _stage_calculator(vm):
    """Calculator integrals and equation roots: its evaluator versus compiled."""
    try:
        import engtools.calculator.evaluate as ev
        from engtools.numerics.equations import root_job
    except ImportError:
        _record('Calculator', 'not installed', '')
        return
    if not hasattr(ev, 'NATIVE_FORMULA'):
        _record('Calculator', 'older version without compiled formulas', '')
        return

    def timed(run, native):
        ev.NATIVE_FORMULA = native
        start = ticks_us()
        try:
            run()
        except Exception as exc:
            return None, str(exc)
        return ticks_diff(ticks_us(), start), ''

    def solve():
        for _ in root_job('x^3-2x-5', -10, 10, 0, {}, 'RAD'):
            pass
    try:
        for label, run in (('integral of exp(-x^2)', lambda: ev.calculate('int(-3,3,exp(-x^2))', {}, 'RAD')),
                           ('integral of sin(x)', lambda: ev.calculate('int(0,pi,sin(x))', {}, 'RAD')),
                           ('root of x^3-2x-5', solve)):
            slow, problem = timed(run, False)
            fast, _ = timed(run, True)
            if slow is None or fast is None:
                _record('Calculator ' + label, 'failed: ' + problem, '')
                continue
            _record('Calculator %s, Python' % label, slow / 1000, 'ms')
            _record('Calculator %s, C' % label, fast / 1000, 'ms (%dx)' % (slow // fast) if fast else 'ms')
    finally:
        ev.NATIVE_FORMULA = True


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
        'Takes about a minute.',
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
    ('3-D plot frame', _stage_3d),
    ('Beam solver', _stage_beam),
    ('Formula compiler', _stage_formula),
    ('Graph drawing', _stage_graph),
    ('Calculator', _stage_calculator),
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
        if 0 <= _stage < len(STAGES):
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
