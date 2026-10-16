"""BLE pairing with passkey input/confirmation and verified key persistence."""
from utime import ticks_ms
_bluetooth=None
_menu=None
_scanned_devices=[]
_addresses=[]
_selected_device=None
_state=0
_save_done=False
_save_ok=False
_passkey_editing=False
_passkey_result=None
STATE_IDLE=0
STATE_SCANNING=1
STATE_CONNECTING=2
STATE_CONNECTED=5
STATE_PAIRING=4
STATE_PAIRED=6


def bluetooth_callback(event,data):
    global _state
    if event==5:
        from picoware.applications.bluetooth.common import add_result
        add_result(_bluetooth,_menu,_scanned_devices,_addresses,data,True)
    elif event==6 and _state==STATE_SCANNING:_state=STATE_IDLE
    elif event==7:_state=STATE_CONNECTED
    elif event==8:_state=STATE_IDLE
    elif event==28:
        if data[1] and data[3]:_state=STATE_PAIRED
        else:_state=STATE_CONNECTED;_bluetooth.error='Pairing did not establish a saved bond.'

def _saved(value):
    global _passkey_result
    _passkey_result=value

def start(vm):
    global _bluetooth,_menu,_scanned_devices,_addresses,_selected_device,_state,_save_done,_save_ok,_passkey_editing,_passkey_result
    from picoware.system.bluetooth import Bluetooth
    from picoware.gui.menu import Menu
    if _bluetooth is not None:_bluetooth.close()
    _scanned_devices=[];_addresses=[];_selected_device=None;_save_done=_save_ok=False
    _passkey_editing=False;_passkey_result=None;_state=STATE_SCANNING
    _menu=Menu(vm.draw,'Pair Device',0,vm.draw.size.y,vm.foreground_color,vm.background_color,vm.selected_color,vm.foreground_color,2)
    _bluetooth=Bluetooth(vm.storage);_bluetooth.callback=bluetooth_callback
    if not _bluetooth.supports_pairing:
        vm.alert('Bluetooth pairing is unavailable in this firmware. Scan and UART chat do not require pairing.');_bluetooth.close();return False
    if not _bluetooth.scan():vm.alert(_bluetooth.error);_bluetooth.close();return False
    return True

def run(vm):
    global _state,_selected_device,_save_done,_save_ok,_passkey_editing,_passkey_result
    from picoware.system import buttons as k
    _bluetooth.poll();button=vm.button
    if button==k.BUTTON_ESCAPE:
        if _bluetooth.passkey_action==4:_bluetooth.passkey_reply(False)
        vm.keyboard.reset();vm.back();return
    if _state==STATE_IDLE:
        _menu.draw()
        if button in (k.BUTTON_UP,k.BUTTON_LEFT):_menu.scroll_up()
        elif button in (k.BUTTON_DOWN,k.BUTTON_RIGHT):_menu.scroll_down()
        elif button==k.BUTTON_CENTER and _scanned_devices:
            _selected_device=_scanned_devices[_menu.selected_index];_state=STATE_CONNECTING
            # Pairing does not depend on a UART service being present.
            if not _bluetooth.connect(*_selected_device[:2],auto_discover=False):vm.alert(_bluetooth.error);_state=STATE_IDLE
        return
    if _state==STATE_PAIRING and _bluetooth.passkey_action==2:
        if not _passkey_editing:
            vm.keyboard.reset();vm.keyboard.title='Bluetooth passkey (6 digits)'
            vm.keyboard.set_save_callback(_saved);vm.input_manager.reset();vm.keyboard.run(force=True,max_characters=6);_passkey_editing=True
        elif _passkey_result is None:vm.keyboard.run(max_characters=6)
        else:
            value,_passkey_result=_passkey_result,None
            if len(value)!=6 or not value.isdigit():vm.alert('Enter exactly six digits.');_passkey_editing=False
            else:_bluetooth.passkey_reply(passkey=int(value));_passkey_editing=False
            vm.keyboard.reset()
        return
    if _state==STATE_PAIRING and not _bluetooth.is_pairing:
        _state=STATE_CONNECTED if _bluetooth.is_connected else STATE_IDLE
    if _state==STATE_CONNECTING and not _bluetooth.is_connecting and not _bluetooth.is_connected:_state=STATE_IDLE
    d=vm.draw;fg=vm.foreground_color;d.clear();d._text(5,24,'Bluetooth Pairing',vm.selected_color)
    if _state==STATE_SCANNING:d._text(5,60,'Scanning...',fg)
    elif _state==STATE_CONNECTING:d._text(5,60,'Connecting...',fg)
    elif _state==STATE_CONNECTED:
        d._text(5,60,'Connected: '+(_selected_device[2] or 'Unknown'),fg)
        d._text(5,100,'ENTER Pair   ESC Disconnect',fg)
        if button==k.BUTTON_CENTER:
            _save_done=False;_passkey_editing=False
            if _bluetooth.pair():_state=STATE_PAIRING
    elif _state==STATE_PAIRING:
        action=_bluetooth.passkey_action
        d._text(5,60,'Pairing...',fg)
        if action in (3,4):
            d._text(5,100,'Passkey: %06d'%(_bluetooth.passkey or 0),fg)
            d._text(5,130,'ENTER Confirm   ESC Reject' if action==4 else 'Enter this code on the other device',fg)
            if action==4 and button==k.BUTTON_CENTER:_bluetooth.passkey_reply(True)
    elif _state==STATE_PAIRED:
        if not _save_done:
            _save_done=True
            address=':'.join('%02X'%b for b in _selected_device[1])
            _save_ok=_bluetooth.bonds_saved and _bluetooth.save_paired_device(address,_selected_device[2])
        d._text(5,60,'Pairing succeeded',fg)
        d._text(5,100,'Bond saved to SD' if _save_ok else 'Session only: bond save failed',fg if _save_ok else 0xF800)
    if _bluetooth.error:d._text(5,int(d.size.y)-45,_bluetooth.error[:45],0xF800)
    d._text(5,int(d.size.y)-22,'ESC Return',fg);d.swap()

def stop(vm):
    global _bluetooth,_menu,_state,_passkey_editing
    if _bluetooth is not None:_bluetooth.close()
    _bluetooth=None;_menu=None;_state=STATE_IDLE;_passkey_editing=False
    vm.keyboard.reset()
