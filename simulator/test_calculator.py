"""Calculator editing, parsing, keyboard routes, rendering and session lifetime."""
import os, sys
from time import ticks_ms
root = os.getcwd()
sys.path.insert(0, root+'/src/MicroPython')
sys.path.insert(0, root+'/simulator/hardware')
sys.path.insert(0, root+'/builds/MicroPython/apps_unfrozen')
from engtools.calculator.editor import Editor, Node, source, clone
from engtools.calculator.evaluate import calculate, format_value

def type_text(editor, text):
    for char in text:
        if char == ' ' and editor.expand(): continue
        editor.insert(char)

e = Editor()
type_text(e, '2^ ')
assert isinstance(e.root[-1], Node) and e.root[-1].kind == 'pow'
assert e.focus_missing()
type_text(e, '3')
assert source(e.root) == '2^(3)'
assert e.move(1) and not e.parents
type_text(e, '+sqrt() ')
type_text(e, 'frac() ')
type_text(e, '9')
e.vertical(1); type_text(e, '4')
assert source(e.root) == '2^(3)+sqrt(((9)/(4)))'
assert abs(calculate(source(e.root), {})[0]-9.5) < 1e-5
snapshot = clone(e.root)
e.load(snapshot); e.move(-1)
assert e.parents and e.row is e.root[-1].rows[0]
e.clear(); type_text(e, 'int() ')
type_text(e, '0'); e.tab(); type_text(e, '1'); e.tab(); type_text(e, 'x^ ')
type_text(e, '2')
assert source(e.root) == 'int(0,1,x^(2))'
assert abs(calculate(source(e.root), {})[0]-1/3) < 1e-4
assert abs(calculate('int(0,1000,1)', {})[0]-1000) < 0.1
assert abs(calculate('int(1,0,x^2)', {})[0]+1/3) < 1e-4
assert calculate('int(1,1,x)', {})[0] == 0
e.clear(); type_text(e, 'V_ '); type_text(e, '1'); e.move(1); type_text(e, '=12')
variables = {}
assert calculate(source(e.root), variables) == (12, 'V_1')
assert calculate('2V_1+1', variables)[0] == 25
for text, expected in (('2^3^2',512), ('-2^2',-4), ('2^-2',0.25),
                       ('2(3+4)',14), ('sin(30)',0.5), ('logb(2,8)',3),
                       ('3!',6), ('1e-3+2e-3',0.003)):
    assert abs(calculate(text, {})[0]-expected) < 1e-5, text
assert abs(calculate('sin(pi/2)', {}, 'RAD')[0]-1) < 1e-5
# Slash expansion captures the preceding multiplicative term and enters the
# denominator. Existing grouping, powers and division must retain their meaning.
for numerator, denominator, expected in (
    ('2/', '3', 2/3), ('1+2/', '4', 1.5), ('(1+2)/', '3', 1),
    ('1/2/', '3', 1/6), ('2^-3/', '2', 1/16), ('1e-3/', '2', 0.0005),
    ('sin(30)/', '2', 0.25), ('a=1+2/', '4', 1.5)):
    e.clear(); type_text(e, numerator+' ')
    parent, index, slot = e.parents[-1]
    assert parent[index].kind == 'frac' and slot == 1 and not e.row
    type_text(e, denominator)
    assert abs(calculate(source(e.root), {})[0]-expected) < 1e-5, numerator
e.clear(); type_text(e, '2^ '); type_text(e, '3'); e.move(1)
type_text(e, '/ '); type_text(e, '4')
assert calculate(source(e.root), {})[0] == 2
for shorthand in ('log_', 'log_()', 'logb()'):
    e.clear(); type_text(e, shorthand+' ')
    assert e.root[0].kind == 'logb' and e.parents[-1][2] == 0
    type_text(e, '2'); e.tab(); type_text(e, '5')
    assert abs(calculate(source(e.root), {})[0]-2.321928) < 1e-5
for shorthand in ('log_2()', 'log_2(5)'):
    e.clear(); type_text(e, shorthand+' ')
    assert e.root[0].kind == 'logb' and e.parents[-1][2] == 1
    assert e.root[0].rows[0] == ['2']
    if not e.row: type_text(e, '5')
    assert abs(calculate(source(e.root), {})[0]-2.321928) < 1e-5
e.clear(); type_text(e, 'log_b(5) ')
assert abs(calculate(source(e.root), {'b':2})[0]-2.321928) < 1e-5
e.clear(); type_text(e, '2log_ '); type_text(e, '2'); e.tab(); type_text(e, '8')
assert calculate(source(e.root), {})[0] == 6
for text in ('/', '2+/', '2*/'):
    e.clear(); type_text(e, text)
    before = source(e.root, False)
    try: e.expand()
    except ValueError: pass
    else: raise AssertionError('Missing numerator accepted')
    assert source(e.root, False) == before
assert abs(calculate('sqrt(-1)', {}, complex_mode=True)[0]-1j) < 1e-5
assert abs(calculate('(1+i)^2', {}, complex_mode=True)[0]-2j) < 1e-5
for text in ('__import__(x)', 'a.b', 'int(0,1,int(0,1,x))', 'pi=3', '2^', 'sqrt()',
             'i', '35!', '0/0', 'x', '1e99', 'logb(1,3)', 'a=1/0'):
    before = dict(variables)
    try: calculate(text, variables)
    except (ValueError, TypeError, ZeroDivisionError, OverflowError): pass
    else: raise AssertionError('Invalid expression accepted: '+text)
    assert variables == before, text
# Empty-node deletion and the depth limit leave the tree intact.
e.clear(); type_text(e, 'sqrt() '); e.delete(); assert not e.root
e.clear()
for _ in range(10): e.template('sqrt')
before = source(e.root, False)
try: e.template('sqrt')
except ValueError: pass
else: raise AssertionError('Nesting limit ignored')
assert source(e.root, False) == before
type_text(e, '2')
for _ in range(10): e.move(1)
type_text(e, '/')
before = source(e.root, False)
try: e.expand()
except ValueError: pass
else: raise AssertionError('Wrapping an existing deep tree exceeded the nesting limit')
assert source(e.root, False) == before and not e.parents
print('PASS: structured templates, nesting, assignment, safe arithmetic and integrals')

import sim_runtime
sd = '/private/tmp/picoware-calculator-test-'+str(ticks_ms())
sim_runtime.configure(root, sd, root+'/builds/MicroPython/apps_unfrozen', 1, 'picocalc-pico2w',
                      0, True, False, False, False, '', _network_mode='offline', _audio_mode='silent')
from picoware.system.view_manager import ViewManager
from picoware.system.view import View
from picoware.system.input import Input
from picoware.system import buttons as k
Input.button = property(lambda self:self._last_button)
import PicoLAB as lab
from engtools.calculator import app
from engtools.calculator.render import Renderer
vm = ViewManager()
vm.add(View('parent', lambda vm:None, lambda vm:True, lambda vm:None)); vm.switch_to('parent')
vm.add(View('lab', lab.run, lab.start, lab.stop)); vm.switch_to('lab')
lab._selected = len(lab.TOOLS)+4

def key(button):
    vm.input_manager._last_button = button
    vm.run()

def text(text):
    for char in text:
        button = vm.input_manager._key_to_button(ord(char))
        key(button)

key(k.BUTTON_CENTER)
assert vm.current_view.name == 'eng_calculator'
calc = app._active
assert not calc.show_hints
# Help toggles preserve the input/session on every mode, with no new SD setting.
text('2^ ')
saved = source(calc.editor.root, False)
key(k.BUTTON_F9)
assert calc.show_hints and source(calc.editor.root, False) == saved
key(k.BUTTON_F9)
assert not calc.show_hints and source(calc.editor.root, False) == saved
key(k.BUTTON_F5)
vm.draw.screenshot('/private/tmp/picoware-calculator-empty.bmp')
key(k.BUTTON_F2)
assert calc.page == 'modes'
vm.draw.screenshot('/private/tmp/picoware-calculator-modes.bmp')
for mode in range(6):
    calc.selected = mode
    key(k.BUTTON_CENTER)
    assert calc.mode == mode and calc.page == {0:'calc',1:'stats',2:'solver',3:'calc',4:'base',5:'matrix'}[mode]
    page = calc.page
    key(k.BUTTON_F9); assert calc.show_hints and calc.page == page
    key(k.BUTTON_F9); assert not calc.show_hints and calc.page == page
    if mode not in app.SUPPORTED:
        text('2+2'); key(k.BUTTON_CENTER)
        assert 'planned' in calc.error and calc.answer == 0
        key(k.BUTTON_F5)
    key(k.BUTTON_F2)
calc.selected = 0; key(k.BUTTON_CENTER)
# Record actual drawing: theme follows the VM without changing the shared Lab
# palette, hidden help frees panel space, and errors survive both layouts.
from engtools.ui import theme
class RecordingDraw:
    def __init__(self, draw): self.draw=draw; self.size=draw.size; self.calls=[]
    def get_font(self, size): return self.draw.get_font(size)
    def len(self, text, font): return self.draw.len(text,font)
    def _text(self, x,y,char,color,font): self.calls.append(('text',x,y,char,color))
    def _line(self, x1,y1,x2,y2,color): self.calls.append(('line',x1,y1,x2,y2,color))
    def _fill_rectangle(self,x,y,w,h,color): self.calls.append(('fill',x,y,w,h,color))
    def fill_screen(self,color): self.calls=[]
    def swap(self): pass
    def text(self): return ''.join(call[3] for call in self.calls if call[0]=='text')

original_draw, original_color = vm._draw, vm.selected_color
recording = RecordingDraw(original_draw)
vm._draw = recording
try:
    for color in (0xFD20,0xF81F):
        vm.selected_color=color
        calc.draw()
        assert any(c[0]=='text' and c[1:4]==(8,22,'C') and c[4]==color for c in recording.calls)
        assert calc.renderer(recording,(0,0,320,320)).accent == color
    assert theme.ACCENT==0x07FF
    assert 'F9 Help' in recording.text() and 'F3 Options' not in recording.text()
    assert any(c[:5]==('line',8,122,311,122) for c in recording.calls)
    assert any(c[:5]==('line',8,304,311,304) for c in recording.calls)
    key(k.BUTTON_F9)
    assert 'F3 Options' in recording.text() and 'Type 2^' in recording.text()
    assert any(c[:5]==('line',8,280,311,280) for c in recording.calls)
    calc.error='Complete the highlighted slot'
    key(k.BUTTON_F9)
    assert not calc.show_hints and calc.error in recording.text()
    calc.error=''
finally:
    vm._draw, vm.selected_color = original_draw, original_color
calc.draw()
text('a=3'); key(k.BUTTON_CENTER)
assert calc.variables['a'] == 3 and calc.answer == 3
text('2a+1'); key(k.BUTTON_CENTER)
assert calc.answer == 7
text('2/ ')
assert calc.editor.parents[-1][2] == 1 and not calc.editor.row
vm.draw.screenshot('/private/tmp/picoware-calculator-division-slot.bmp')
text('3'); key(k.BUTTON_CENTER)
assert abs(calc.answer-2/3) < 1e-5
text('log_ ')
assert calc.editor.root[0].kind == 'logb' and len(calc.editor.root[0].rows) == 2
vm.draw.screenshot('/private/tmp/picoware-calculator-log-slots.bmp')
text('2'); key(k.BUTTON_TAB); text('5')
vm.draw.screenshot('/private/tmp/picoware-calculator-log-filled.bmp')
key(k.BUTTON_CENTER)
assert abs(calc.answer-2.321928) < 1e-5
text('2^ ')
assert calc.editor.parents and calc.editor.row == []
vm.draw.screenshot('/private/tmp/picoware-calculator-power-slot.bmp')
key(k.BUTTON_CENTER)
assert calc.error == 'Complete the highlighted slot'
text('3'); key(k.BUTTON_RIGHT); text('+sqrt() '); text('frac() ')
text('9'); key(k.BUTTON_DOWN); text('4')
vm.draw.screenshot('/private/tmp/picoware-calculator-nested.bmp')
key(k.BUTTON_CENTER)
assert abs(calc.answer-9.5) < 1e-5 and not calc.editor.root
key(k.BUTTON_UP)
assert source(calc.editor.root) == '2^(3)+sqrt(((9)/(4)))'
key(k.BUTTON_DOWN); assert not calc.editor.root
text('draft'); key(k.BUTTON_UP); key(k.BUTTON_DOWN)
assert source(calc.editor.root) == 'draft'
key(k.BUTTON_F5)
text('int() '); text('0'); key(k.BUTTON_TAB); text('1'); key(k.BUTTON_TAB); text('x^ '); text('2')
vm.draw.screenshot('/private/tmp/picoware-calculator-integral.bmp')
key(k.BUTTON_CENTER); assert abs(calc.answer-1/3) < 1e-4
key(k.BUTTON_F4); assert calc.page == 'variables'
vm.draw.screenshot('/private/tmp/picoware-calculator-variables.bmp')
key(k.BUTTON_ESCAPE); assert calc.page == 'calc'
key(k.BUTTON_F3); key(k.BUTTON_CENTER); assert calc.angle == 'RAD'
key(k.BUTTON_DOWN); key(k.BUTTON_CENTER); assert calc.engineering
key(k.BUTTON_ESCAPE); text('sin(pi/2)'); key(k.BUTTON_CENTER)
assert abs(calc.answer-1) < 1e-5
key(k.BUTTON_F6); assert calc.page == 'history'
key(k.BUTTON_CENTER); assert calc.page == 'calc' and calc.editor.root
key(k.BUTTON_F5)
text('12'); key(k.BUTTON_BACKSPACE); assert source(calc.editor.root) == '1'
key(k.BUTTON_F5)
for deletion in (k.BUTTON_BACK,k.BUTTON_DELETE,k.BUTTON_BACKSPACE):
    text('12'); key(deletion); assert source(calc.editor.root) == '1'
    key(k.BUTTON_F3); key(k.BUTTON_ESCAPE); assert calc.page == 'calc'
    key(k.BUTTON_F5)
for _ in range(30):
    text('1+1'); key(k.BUTTON_CENTER)
assert len(calc.history) == 24
for _ in range(10):
    text('1+'*100+'1'); key(k.BUTTON_CENTER)
assert sum(len(record['text']) for record in calc.history) <= app.HISTORY_ITEM_LIMIT
assert len(calc.history) < 24 and calc.answer == 101
# Long/nested layouts stay clipped to the editor region and follow the cursor.
text('1234567890'*10)
r = Renderer(vm.draw, (40, 215, 303, 264))
r.expression(calc.editor.root, 43, 219, editor=calc.editor, follow=True)
assert 40 <= r.cursor[0] <= 299
# Check every primitive against a recording surface, including partially visible
# roots, fractions and integrals. This prevents overdraw into answer/status bars.
class Surface:
    def get_font(self, size): return vm.draw.get_font(size)
    def _text(self, x, y, char, color, font):
        f = self.get_font(font)
        assert 40 <= x and x+f.width+f.spacing <= 303 and 215 <= y and y+f.height <= 264
    def _line(self, x1, y1, x2, y2, color):
        assert 40 <= x1 < 303 and 40 <= x2 < 303 and 215 <= y1 < 264 and 215 <= y2 < 264
    def _fill_rectangle(self, x, y, w, h, color):
        assert 40 <= x and x+w <= 303 and 215 <= y and y+h <= 264
e.clear(); type_text(e, 'int() '); e.template('frac'); e.template('sqrt')
r = Renderer(Surface(), (40, 215, 303, 264))
r.expression(e.root, 20, 200, editor=e, follow=True)
count = vm._view_count
key(k.BUTTON_ESCAPE)
assert vm.current_view.name == 'lab' and vm._view_count == count-1 and app._active is None
assert not calc.history and not calc.variables and not calc.editor.root
key(k.BUTTON_CENTER)
assert vm.current_view.name == 'eng_calculator' and app._active.answer == 0
assert not app._active.show_hints
key(k.BUTTON_ESCAPE)
assert vm.current_view.name == 'lab'
print('PASS: mode grid, physical key routing, result/history, clipping and cleanup')
