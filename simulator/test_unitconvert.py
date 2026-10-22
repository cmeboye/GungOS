"""Known-answer conversions and the first-pass converter driven by keys.

Run from the root with builds/MicroPython/desktop/micropython -X heapsize=16M.
"""
import os, sys
from time import ticks_ms
root = os.getcwd()
for part in ('src/MicroPython', 'simulator/hardware', 'builds/MicroPython/apps_unfrozen'):
    sys.path.insert(0, root + '/' + part)
from engtools.unitconvert import model as m, catalog as c


def near(got, want, tol=3e-6):
    assert abs(got-want) <= tol*max(abs(want), 1e-20), (got, want)


def convert(key, source, target, value):
    return m.result({'category': key, 'from': source, 'to': target, 'value': value})


for key, source, target, value, answer in (
    ('length', 'in', 'mm', 1, 25.4), ('length', 'mi', 'km', 1, 1.609344),
    ('mass', 'lb', 'kg', 1, .45359237), ('mass', 'ozt', 'g', 1, 31.1034768),
    ('area', 'acre', 'm2', 1, 4046.8564224), ('volume', 'gal-US', 'L', 1, 3.785411784),
    ('volume', 'gal-UK', 'L', 1, 4.54609), ('volume', 'cup-US', 'mL', 1, 236.5882365),
    ('temperature', 'degC', 'degF', 100, 212), ('temperature', 'degF', 'degC', -40, -40),
    ('temperature', 'degC', 'K', -273.15, 0), ('interval', 'degC', 'degF', 10, 18),
    ('pressure', 'psi', 'Pa', 1, 6894.757293), ('force', 'kgf', 'N', 1, 9.80665),
    ('energy', 'kWh', 'J', 1, 3600000), ('energy', 'eV', 'J', 1, 1.602176634e-19),
    ('power', 'hp', 'kW', 1, .74569987158), ('torque', 'lbf*ft', 'N*m', 1, 1.35581794833),
    ('angular', 'rpm', 'rad/s', 60, 6.28318530718),
    ('area-inertia', 'in4', 'mm4', 1, 416231.4256),
    ('flow', 'gpm-US', 'L/min', 1, 3.785411784),
    ('dynamic-viscosity', 'cP', 'Pa*s', 1, .001),
    ('fuel', 'mpg-US', 'L/100km', 30, 7.84048611111),
    ('fuel', 'L/100km', 'km/L', 5, 20),
    ('expansion', '1/degF', '1/K', 1, 1.8),
    ('charge', 'Ah', 'C', 1, 3600), ('capacitance', 'pF', 'F', 1, 1e-12),
    ('data', 'MiB', 'kB', 1, 1048.576), ('data-rate', 'MB/s', 'Mbit/s', 1, 8)):
    # Absolute zero is sensitive to the rounding of offset subtraction.
    if answer == 0:
        assert abs(convert(key, source, target, value)) < .0001
    else:
        near(convert(key, source, target, value), answer)

for key, source, target, value in (('temperature', 'K', 'degC', -1),
                                  ('fuel', 'mpg-US', 'L/100km', 0),
                                  ('fuel', 'L/100km', 'mpg-US', -2),
                                  ('length', 'm', 'ft', float('inf'))):
    try:
        convert(key, source, target, value)
    except ValueError:
        pass
    else:
        raise AssertionError('Invalid input accepted')

total = 0
for category in c.CATEGORIES:
    key = category[0]
    choices = c.units(key)
    assert len({u[0] for u in choices}) == len(choices), key
    for u in choices:
        # Round-trip each supported unit through SI, cases and swap.
        value = 300.0 if key == 'temperature' else 1.25
        state = {'category': key, 'from': u[0], 'to': choices[0][0], 'value': value}
        near(m.from_case(m.to_case(state))['value'], value)
        m.swap(state)
        m.swap(state)
        near(state['value'], value)
        total += 1
assert m.shown(1e-19) != '0' and m.shown(1e12) != '0'
print('PASS: %d categories, %d units; known answers, errors, SI cases and swaps' % (len(c.CATEGORIES), total))

import sim_runtime
sim_runtime.configure(root, '/private/tmp/gungos-unitconvert-' + str(ticks_ms()),
                      root + '/builds/MicroPython/apps_unfrozen', 1, 'picocalc-pico2w', 0,
                      True, False, False, False, '', _network_mode='offline',
                      _audio_mode='silent', _sd_profile='clean')
from picoware.system.view_manager import ViewManager
from picoware.system.view import View
from picoware.system.input import Input
from picoware.system import buttons as k
Input.button = property(lambda self: self._last_button)
vm = ViewManager(); vm._wifi = None
vm.add(View('parent', lambda vm: None, lambda vm: True, lambda vm: None)); vm.switch_to('parent')
from engtools.unitconvert import app
app.show(vm)
a = app._active


def key(button):
    vm.input_manager._last_button = button
    vm.run()


def text(value):
    for char in value:
        key(vm.input_manager._key_to_button(ord(char)))


def search(value):
    text(value)
    assert a.search_rows(), value
    key(k.BUTTON_CENTER)


def option(index):
    key(k.BUTTON_F3)
    for _ in range(index):
        key(k.BUTTON_DOWN)
    key(k.BUTTON_CENTER)


assert a.page == 'browse'
search('length')
assert a.page == 'convert'
# Use only keys to choose inch -> mm and enter a fractional inch.
key(k.BUTTON_DOWN); key(k.BUTTON_CENTER); search('inch')
assert a.state['from'] == 'in'
key(k.BUTTON_DOWN); key(k.BUTTON_CENTER); search('millimetre')
assert a.state['to'] == 'mm'
text('3/8'); key(k.BUTTON_CENTER)
near(m.result(a.state), 9.525)
text('s'); near(a.state['value'], 9.525)
text('z'); assert a.state['from'] == 'in'; near(a.state['value'], .375)
key(k.BUTTON_F5); assert a.page == 'results'; a.draw()
key(k.BUTTON_DOWN); key(k.BUTTON_CENTER); assert a.state['to'] == 'mm'
option(1); assert len(a.favorites) == 1 and not a.error
option(2); assert a.page == 'favorites'; key(k.BUTTON_CENTER)
assert a.state['from'] == 'in'
option(4); assert a.dialog is not None
for _ in range(30):
    key(k.BUTTON_BACKSPACE)
text('inch-check'); key(k.BUTTON_CENTER)
assert a.dialog is None and not a.error, a.message
option(6); assert not a.error and 'CSV:' in a.message, a.message
files = vm.storage.listdir('picoware/engineering/exports')
data = vm.storage.read('picoware/engineering/exports/' + files[0])
assert data.startswith('value [m]\n'), data
near(float(data.split('\n')[1]), .009525)
option(5); assert a.page == 'files' and a.files == ['inch-check']
key(k.BUTTON_CENTER); assert a.state['from'] == 'in'
# Search a unit name globally, zero search matches, cancellation, temperature error.
key(k.BUTTON_F1); text('nonsense-no-unit'); assert not a.search_rows(); a.draw()
key(k.BUTTON_ESCAPE); search('fahrenheit')
assert a.state['category'] == 'temperature'
text('-1'); key(k.BUTTON_CENTER)
assert a.error and a.edit is not None and a.state['value'] == 1
key(k.BUTTON_ESCAPE); assert a.edit is None
key(k.BUTTON_F9); assert vm.current_view.help
key(k.BUTTON_ESCAPE)
sim_runtime.lcd_screenshot('/private/tmp/gungos-unitconvert-screen.bmp')
# Stop / restart reads favorites from SD and keeps conversion state in-session.
key(k.BUTTON_ESCAPE); assert a.page == 'browse'
key(k.BUTTON_ESCAPE); assert vm.current_view.name == 'parent'
app.show(vm); a = app._active
assert len(a.favorites) == 1 and a.recent
# Every category and result list renders; return from a child is safe.
for record in c.CATEGORIES:
    a.choose_category(record[0]); a.draw()
    a.page = 'results'; a.index = 0; a.draw()
    a.index = len(c.units(record[0]))-1; a.draw()
    a.page = 'convert'
a.choose_category('length'); a.draw()
sim_runtime.lcd_screenshot('/private/tmp/gungos-unitconvert-convert.bmp')
a.browse(); a.draw()
sim_runtime.lcd_screenshot('/private/tmp/gungos-unitconvert-browse.bmp')
key(k.BUTTON_ESCAPE)
print('PASS: keyboard search, arithmetic, swapping, undo, equivalents, favorites, files, CSV and all category screens')
