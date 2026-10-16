"""BLE UART chat: wait for subscription, frame UTF-8 lines, and bound buffers."""
from utime import ticks_ms,ticks_diff
_bluetooth=None
_menu=None
_loading=None
_messages=[]
_scanned_devices=[]
_addresses=[]
_selected_device=None
_state=0
_mode=None
_pending_message=None
_incoming=bytearray()
_incoming_at=0
_last_update=0
STATE_MODE_SELECT=0
STATE_SCANNING=1
STATE_DEVICE_LIST=2
STATE_CONNECTING=3
STATE_CHAT=4
STATE_TYPING=5
STATE_PERIPHERAL_WAIT=6


def _append(sent,text):
    if text:_messages.append((sent,text));del _messages[:-20]

def _finish_line():
    if not _incoming:return
    try:text=bytes(_incoming).decode().rstrip('\r')
    except UnicodeError:text='[Invalid UTF-8 message]'
    _incoming[:]=b'';_append(False,text)

def on_data_received(data):
    global _incoming_at
    for value in data:
        if value==10:_finish_line()
        elif len(_incoming)<512:_incoming.append(value)
        else:_incoming[:]=b'';_append(False,'[Incoming message too long]');break
    _incoming_at=ticks_ms()

def bluetooth_callback(event,data):
    global _state
    if event==5:
        from picoware.applications.bluetooth.common import add_result
        add_result(_bluetooth,_menu,_scanned_devices,_addresses,data,True)
    elif event==6 and _state==STATE_SCANNING:_state=STATE_DEVICE_LIST
    elif event==8:_state=STATE_MODE_SELECT
    elif event==1:_state=STATE_CHAT
    elif event==2:_finish_line();_state=STATE_PERIPHERAL_WAIT

def _saved(text):
    global _pending_message
    _pending_message=text

def _modes(vm):
    global _bluetooth,_menu,_loading,_state,_mode,_scanned_devices,_addresses,_incoming,_selected_device
    from picoware.gui.menu import Menu
    if _bluetooth is not None:_bluetooth.close()
    _bluetooth=None
    if _loading is not None:_loading.stop()
    _loading=None;_state=STATE_MODE_SELECT;_mode=None
    _scanned_devices=[];_addresses=[];_incoming=bytearray();_selected_device=None
    vm.keyboard.reset()
    _menu=Menu(vm.draw,'UART Chat',0,vm.draw.size.y,vm.foreground_color,vm.background_color,vm.selected_color,vm.foreground_color,2)
    _menu.add_item('Central (Connect)');_menu.add_item('Peripheral (Wait)');_menu.draw()

def start(vm):
    global _messages,_pending_message,_last_update
    _messages=[];_pending_message=None;_last_update=0;_modes(vm);return True

def run(vm):
    global _state,_mode,_bluetooth,_menu,_loading,_selected_device,_pending_message,_last_update
    from picoware.system import buttons as k
    from picoware.gui.menu import Menu
    if _bluetooth is not None:_bluetooth.poll()
    button=vm.button
    if button==k.BUTTON_ESCAPE:
        if _state==STATE_TYPING:vm.keyboard.reset();_pending_message=None;_state=STATE_CHAT;return
        if _state==STATE_MODE_SELECT:vm.back();return
        _modes(vm);return
    if _state==STATE_MODE_SELECT:
        if _menu.title!='UART Chat':_modes(vm)
        if button in (k.BUTTON_UP,k.BUTTON_LEFT):_menu.scroll_up()
        elif button in (k.BUTTON_DOWN,k.BUTTON_RIGHT):_menu.scroll_down()
        elif button==k.BUTTON_CENTER:
            from picoware.system.bluetooth import Bluetooth
            _bluetooth=Bluetooth(vm.storage);_bluetooth.callback=bluetooth_callback
            if _menu.selected_index==0:
                _mode='central';_bluetooth.on_notify(on_data_received)
                _menu=Menu(vm.draw,'Select Device',0,vm.draw.size.y,vm.foreground_color,vm.background_color,vm.selected_color,vm.foreground_color,2)
                _state=STATE_SCANNING
                if not _bluetooth.scan():vm.alert(_bluetooth.error);_modes(vm)
            else:
                _mode='peripheral';_bluetooth.on_write(on_data_received);_state=STATE_PERIPHERAL_WAIT
                if not _bluetooth.start_peripheral('Picoware-Chat'):vm.alert(_bluetooth.error);_modes(vm)
        return
    if _state==STATE_DEVICE_LIST:
        _menu.draw()
        if button in (k.BUTTON_UP,k.BUTTON_LEFT):_menu.scroll_up()
        elif button in (k.BUTTON_DOWN,k.BUTTON_RIGHT):_menu.scroll_down()
        elif button==k.BUTTON_CENTER and _scanned_devices:
            _selected_device=_scanned_devices[_menu.selected_index];_state=STATE_CONNECTING
            if not _bluetooth.connect(*_selected_device[:2]):vm.alert(_bluetooth.error or 'Connection failed.');_modes(vm)
        return
    if _state==STATE_CONNECTING:
        if _bluetooth.is_uart_ready():_state=STATE_CHAT;_last_update=0
        elif not _bluetooth.is_connecting and (_bluetooth.error or _bluetooth.discovery_complete):
            vm.alert(_bluetooth.error or 'The device has no compatible UART service.');_modes(vm);return
    if _state==STATE_TYPING:
        if _pending_message is None:vm.keyboard.run(max_characters=128);return
        text,_pending_message=_pending_message,None
        if text:
            if len(text.encode())>511:vm.alert('Message exceeds 511 encoded bytes.');return
            accepted=_bluetooth.write(text+'\n',response=True) if _mode=='central' else _bluetooth.send(text+'\n')
            if not accepted:vm.alert(_bluetooth.error or 'No connected device.');return
            _append(True,text)
        vm.keyboard.reset();_state=STATE_CHAT;_last_update=0
    if _incoming and ticks_diff(ticks_ms(),_incoming_at)>250:_finish_line()
    now=ticks_ms()
    if button==k.BUTTON_NONE and ticks_diff(now,_last_update)<100:return
    _last_update=now
    d=vm.draw;fg=vm.foreground_color;d.clear()
    d._text(5,24,'UART Chat / '+str(_mode),vm.selected_color)
    if _state==STATE_SCANNING:d._text(5,60,'Scanning... ESC cancels',fg)
    elif _state==STATE_CONNECTING:d._text(5,60,'Connecting / discovering UART...',fg)
    elif _state==STATE_PERIPHERAL_WAIT:d._text(5,60,'Waiting for a connection...',fg);d._text(5,85,'Name: Picoware-Chat',fg)
    elif _state==STATE_CHAT:
        for index,(sent,text) in enumerate(_messages[-10:]):d._text(5,52+index*18,('> ' if sent else '< ')+text[:43],fg)
        if _bluetooth.error:d._text(5,int(d.size.y)-53,_bluetooth.error[:45],0xF800)
        d._text(5,int(d.size.y)-30,'ENTER Type   ESC Disconnect',fg)
        if button==k.BUTTON_CENTER:
            _pending_message=None;_state=STATE_TYPING;vm.keyboard.reset();vm.keyboard.title='Send UART message'
            vm.keyboard.set_save_callback(_saved);vm.input_manager.reset();vm.keyboard.run(force=True,max_characters=128)
            return
    d.swap()

def stop(vm):
    global _bluetooth,_menu,_loading,_messages,_incoming,_state,_pending_message
    if _bluetooth is not None:_bluetooth.close()
    _bluetooth=None;_menu=None;_loading=None;_messages=[];_incoming=bytearray();_state=STATE_MODE_SELECT;_pending_message=None
    vm.keyboard.reset()
