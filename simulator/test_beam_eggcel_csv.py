"""Beam Lab CSV -> Eggcel via the real SD file selector, including cancellation."""
import os,sys
from time import ticks_ms
root=os.getcwd()
for part in ('src/MicroPython','simulator/hardware','builds/MicroPython/apps_unfrozen'):
    sys.path.insert(0,root+'/'+part)
import sim_runtime
sim_runtime.configure(root,'/private/tmp/gungos-beam-eggcel-'+str(ticks_ms()),
    root+'/builds/MicroPython/apps_unfrozen',1,'picocalc-pico2w',0,True,False,False,False,'',
    _network_mode='offline',_audio_mode='silent',_sd_profile='clean')
from picoware.system.view_manager import ViewManager
from picoware.system.view import View
from picoware.system.input import Input
from picoware.system import buttons as k
from engtools.beamlab import app as beam,model as bm
from engtools import cases
from desktopapps.eggcel import app as egg
from desktopapps.eggcel.model import Sheet,read_sheet,MAX_CELLS
Input.button=property(lambda self:self._last_button)
vm=ViewManager();vm._wifi=None
beam._kept=None
lab=beam.BeamLab(vm)
# Every template's compact export fits an ordinary Eggcel workbook, even
# frames with multiple runs. Each run retains both endpoint rows and units.
for index in range(len(bm.TEMPLATES)):
    lab.replace_model(bm.template(index))
    assert lab.evaluate()
    lab.model['name']='template-%d'%index
    lab.export()
    path=cases.EXPORT_DIRECTORY+'/template-%d-eggcel-001.csv'%index
    sheet=read_sheet(vm.storage,path,True)
    assert len(sheet.cells)<=MAX_CELLS and sheet.dirty
    assert sheet.value((0,0))=='line' and sheet.value((0,6))=='w_mm'
    nrows=max(r for r,c in sheet.cells)
    assert nrows<=72
    for line in range(len(lab.solution.lines)):
        rows=[r for r in range(1,nrows+1) if sheet.value((r,0))==line+1]
        assert len(rows)>=2
        assert abs(sheet.value((rows[0],1)))<1e-6
        length=lab.line_length(line)
        assert abs(sheet.value((rows[-1],1))-length)<1e-5*max(1,length)
        source=lab.solution.at_line(line,0,lab.view,1)
        for col,expected in ((2,source[0]/1e3),(3,source[1]/1e3),(6,source[3]*1e3)):
            assert abs(sheet.value((rows[0],col))-expected)<1e-4*max(1,abs(expected))
lab.replace_model(bm.template(0));lab.model['name']='browser-test'
assert lab.evaluate()
lab.export();lab.export()
compact=cases.EXPORT_DIRECTORY+'/browser-test-eggcel-001.csv'
assert vm.storage.exists(cases.EXPORT_DIRECTORY+'/browser-test-eggcel-002.csv')
lab.export(compact=False)
full=cases.EXPORT_DIRECTORY+'/browser-test-full-001.csv'
assert len(vm.storage.read(full).splitlines())>200
print('PASS: all Beam Lab templates export importable sampled CSVs, endpoints, units and unique names; full export retained')

ui=egg.Spreadsheet()
vm.add(View('eggcel-csv-test',ui.run,ui.start,ui.stop));vm.switch_to('eggcel-csv-test')
def key(button):
    vm.input_manager._last_button=button;vm.run()
    vm.input_manager._last_button=k.BUTTON_NONE;vm.run()

def choose(name):
    browser=ui.browser;assert browser is not None
    state=browser._app_state
    assert state['active_pane']==browser.PANE_LEFT
    files=state['left_files'];target=files.index(name)
    current=state['left_index']
    for _ in range(abs(target-current)):
        key(k.BUTTON_DOWN if target>current else k.BUTTON_UP)
    key(k.BUTTON_CENTER)

def open_csv():
    key(k.BUTTON_F1)
    assert ui.page=='file' and 'Open CSV' in ui.menu_items()
    for _ in range(ui.menu_items().index('Open CSV')):key(k.BUTTON_DOWN)
    key(k.BUTTON_CENTER)

# A dirty sheet prompts first. Cancel and discard-to-browser/ESC both keep
# the same workbook until a replacement has been read and validated.
ui.sheet.apply({(0,0):'123'})
original=ui.sheet
open_csv();assert ui.page=='confirm' and ui.browser is None
key(k.BUTTON_ESCAPE);assert ui.sheet is original and ui.sheet.dirty
open_csv();key(k.BUTTON_DOWN);key(k.BUTTON_CENTER)
assert ui.browser is not None and ui.page=='csv_browser'
vm.draw.screenshot('/private/tmp/gungos-eggcel-csv-browser.bmp')
key(k.BUTTON_ESCAPE)
assert ui.browser is None and ui.page=='grid' and ui.sheet is original
assert ui.sheet.dirty and not ui.error
# Navigate the actual file selector to the engineering exports.
open_csv();key(k.BUTTON_DOWN);key(k.BUTTON_CENTER)
choose('engineering');choose('exports')
assert 'browser-test-full-001.csv' in ui.browser._app_state['left_files']
choose('browser-test-eggcel-001.csv')
assert ui.browser is None and ui.sheet is not original and not ui.error
assert ui.sheet.cells==read_sheet(vm.storage,compact,True).cells
assert ui.filename=='' and ui.sheet.dirty and ui.page=='grid'
assert vm.storage.read(compact).startswith('line,s_m,')
vm.draw.screenshot('/private/tmp/gungos-eggcel-beam-import.bmp')
# An oversized full export reports the existing recovery error without
# replacing the workbook, closing the app, or modifying the source.
original=ui.sheet
open_csv();key(k.BUTTON_DOWN);key(k.BUTTON_CENTER)
assert ui.browser.directory=='/picoware/engineering/exports', (ui.browser.directory,ui.csv_directory,ui.browser._app_state)
choose('browser-test-full-001.csv')
assert ui.sheet is original and ui.browser is None and ui.page=='grid'
assert ui.error and ('limit' in ui.error.lower() or 'exceeds' in ui.error.lower())
key(k.BUTTON_ESCAPE)
assert not ui.error and ui.sheet is original
# CSV files outside picoware are reachable; filters hide non-CSV documents.
vm.storage.mkdir('outside')
vm.storage.write('outside/Mixed.CSV','Name,Value\r\nLiteral,=1+1\r\n')
vm.storage.write('outside/ignored.txt','Do not import')
open_csv();key(k.BUTTON_DOWN);key(k.BUTTON_CENTER)
choose('..');choose('..');choose('..');choose('outside')
assert 'Mixed.CSV' in ui.browser._app_state['left_files']
assert 'ignored.txt' not in ui.browser._app_state['left_files']
choose('Mixed.CSV')
assert ui.sheet.value((1,1))=='=1+1' and not ui.error and ui.filename==''
# A malformed file, too, leaves the prior data available for editing/saving.
original=ui.sheet
vm.storage.write('outside/broken.csv','"unterminated')
open_csv();key(k.BUTTON_DOWN);key(k.BUTTON_CENTER);choose('broken.csv')
assert ui.sheet is original and 'quote' in ui.error.lower()
key(k.BUTTON_ESCAPE);assert not ui.error
assert ui.vm is vm and vm.current_view.name=='eggcel-csv-test'
print('PASS: Open CSV, SD navigation, filters, remembered folder, unsaved guards, cancel, data-only import and transactional error recovery')
