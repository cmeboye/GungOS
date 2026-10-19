"""Logo/path consistency across native menus, selectors and shipped SD menus."""
import os,sys
from time import ticks_ms
root=os.getcwd()
for part in ('src/MicroPython','simulator/hardware','builds/MicroPython/apps_unfrozen'):
    sys.path.insert(0,root+'/'+part)
import sim_runtime
sim_runtime.configure(root,'/private/tmp/gungos-header-test-'+str(ticks_ms()),root+'/builds/MicroPython/apps_unfrozen',1,'picocalc-pico2w',0,True,False,False,False,'',_network_mode='offline',_audio_mode='silent',_sd_profile='clean')
from picoware.system.view_manager import ViewManager
from picoware.system.vector import Vector
from picoware.system import buttons as k
from picoware.gui import style
from picoware.assets import logos
vm=ViewManager();vm._wifi=None
vm.alert=lambda message,*args: (_ for _ in ()).throw(AssertionError(message))
vm._button=k.BUTTON_NONE
preview='/private/tmp/gungos-menu-header-previews'
sim_runtime.mkdir_p(preview)
events=[]
original_logo=logos.paint
original_text=vm.draw._text

def logo(draw,name,*args):
    events.append(('logo',name,args));return original_logo(draw,name,*args)
def text(x,y,value,colour,font=-1):
    if y<18:events.append(('text',value,x,font))
    return original_text(x,y,value,colour,font)
logos.paint=logo
vm.draw._text=text

def check(name,brand,label,render):
    events.clear();render()
    images=[item[1] for item in events if item[0]=='logo']
    assert images and images[-1]==brand,(name,images)
    labels=[item for item in events if item[0]=='text' and str(item[1]).startswith('/ ')]
    assert labels and label in labels[-1][1],(name,labels)
    assert labels[-1][2]+vm.draw.len(labels[-1][1],labels[-1][3])<=int(vm.draw.size.x)-6
    sim_runtime.lcd_screenshot(preview+'/'+name+'.bmp')

try:
    from picoware.gui.menu import Menu
    m=Menu(vm.draw,'WiFi',0,320,selected_color=vm.selected_color)
    m.add_item('Scan');m.add_item('Settings')
    check('wifi','gungOS_small','/ WiFi',m.draw)
    from picoware.gui.choice import Choice
    choice=Choice(vm.draw,Vector(0,0),vm.draw.size,'Screen Brightness',['10','50','100'])
    check('brightness','gungOS_small','Screen Brightness',choice.draw)
    from picoware.gui.theme_picker import ThemePicker
    picker=ThemePicker(vm,vm.selected_color)
    check('theme','gungOS_small','Appearance / Theme colour',picker.draw)
    picker._begin_edit()
    check('theme-custom','gungOS_small','Custom',picker.draw)
    from picoware.gui.date_picker import DatePicker
    date=DatePicker(vm,Vector(0,0),vm.draw.size)
    check('date','gungOS_small','Time / Date & Time',date.run)
    from picoware.applications.system import screensaver_setting
    check('screensaver','gungOS_small','Settings / Screensaver',lambda:screensaver_setting.start(vm))
    screensaver_setting.stop(vm)
    from picoware.gui.file_browser import FileBrowser,FILE_BROWSER_SELECTOR
    browser=FileBrowser(vm,FILE_BROWSER_SELECTOR)
    check('files','gungOS_small','File Browser',browser.run)
    browser._show_options=True;browser._needs_redraw=True
    check('file-options','gungOS_small','File Browser / Options',browser.run)
    spawn=getattr(browser,'__menu_spawn')
    context=spawn('document.csv',('Open','Copy','Rename'))
    check('file-context','gungOS_small','document.csv',context.draw)
    csv=FileBrowser(vm,FILE_BROWSER_SELECTOR,allowed_extensions=['csv'],brand='PicoDESK',breadcrumb='Eggcel / Import CSV')
    check('csv-browser','picodesk','Eggcel / Import CSV',csv.run)
    context=getattr(csv,'__menu_spawn')('Confirm',('No','Yes'))
    check('csv-confirm','picodesk','Eggcel / Import CSV / Confirm',context.draw)
    from desktopapps.launcher import Launcher
    desk=Launcher()
    check('desk','picodesk','Productivity',lambda:desk.start(vm))
    from desktopapps.word import Word
    word=Word();word.start(vm);word.menu('file')
    check('word-file','picodesk','PicoWord / FILE',word.draw)
    from desktopapps.paint import Paint
    paint=Paint();paint.start(vm);paint.menu('color')
    check('paint-colours','picodesk','PicoPaint / COLOR',paint.draw)
    from desktopapps.eggcel.app import Spreadsheet
    egg=Spreadsheet();egg.start(vm);egg.page='actions'
    check('eggcel-actions','picodesk','Eggcel / ACTIONS',egg.draw)
    from engtools.ui import breadcrumbs
    check('lab','picolab','modules / structural / Beam view',lambda:breadcrumbs.paint(vm.draw,style.system_palette(vm),fallback=('modules','structural','Beam view')))
    check('eggcel-plot','picodesk','Eggcel / Settings',lambda:style.chrome(vm.draw,'Settings','','','Eggcel',style.system_palette(vm)))
    check('long-path','gungOS_small','Current selection',lambda:style.header(vm.draw,'A very long parent name / another long parent / Current selection',palette=style.system_palette(vm)))
    # An SD update before the next UF2 must keep the apps usable.
    native_header=style.header
    del style.header
    try:
        check('old-uf2-word','picodesk','PicoWord / FILE',word.draw)
        check('old-uf2-lab','picolab','Scientific calculator',lambda:breadcrumbs.paint(vm.draw,style.system_palette(vm),fallback=('tools','Scientific calculator')))
    finally:
        style.header=native_header
    # A custom app must never leave its logo as a global default for native menus.
    check('back-to-system','gungOS_small','WiFi',m.draw)
    print('PASS: system menus/selectors, file dialogs, theme/date/widget selection, PicoDESK app menus and PicoLAB paths')
    print('PASS: logo ownership, slash separation, bounded long labels, old-UF2 fallback and return to system branding')
    print('Menu screenshots:',preview)
finally:
    logos.paint=original_logo
    del vm.draw._text
