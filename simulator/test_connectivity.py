"""Wi-Fi lifecycle and BLE protocol conformance; no physical radio is simulated."""
import os,sys,gc
from time import ticks_ms,ticks_add
root=os.getcwd()
for name in ('src/MicroPython','simulator/hardware','builds/MicroPython/apps_unfrozen'):sys.path.insert(0,root+'/'+name)
import sim_runtime
sim_runtime.configure(root,'/private/tmp/gungos-radio-tests-'+str(ticks_ms()),root+'/builds/MicroPython/apps_unfrozen',1,'picocalc-pico2w',0,True,False,False,False,'',_network_mode='offline',_audio_mode='silent')
from picoware.system.view_manager import ViewManager
from picoware.system import wifi as wi
from picoware.system.bluetooth import Bluetooth
import network
vm=ViewManager()
original_wlan=network.WLAN
class DelayedWLAN(original_wlan):
    def connect(self,ssid,key=''):
        self._ssid,self._passphrase=ssid,key;self._status=network.STAT_CONNECTING;self._connected=False
network.WLAN=DelayedWLAN
w=wi.WiFi(vm);events=[];w.callback_connect=lambda state,error:events.append((state,error))
clock=[0];original_clock=wi.ticks_ms;wi.ticks_ms=lambda:clock[0]
assert w.connect_async('first','sample') and w.state==wi.WIFI_STATE_CONNECTING
assert w.connection_start_time==0
assert not w.connect_async('duplicate') and w.ssid=='first'
w.wlan._connected=True;assert w.poll()==wi.WIFI_STATE_CONNECTED
assert len(events)==1 and w.error==''
assert w.connect_async('second','sample') and not w.is_connected() and w.wlan._ssid=='second'
w.timeout=.1;clock[0]=101
assert w.poll()==wi.WIFI_STATE_TIMEOUT and 'timed out' in w.error
for _ in range(5):w.poll()
assert len(events)==2
assert w.connect_async('bad','sample');w.wlan._status=network.STAT_WRONG_PASSWORD
assert w.poll()==wi.WIFI_STATE_ISSUE and w.last_error=='Wrong password.'
assert w.connect_async('cancel','sample');w.disconnect();clock[0]+=200
assert w.state==wi.WIFI_STATE_IDLE and not w._thread_running
assert w.connect_async('AP','eightchars',False)
assert w.mode==network.AP_IF and w.wlan.mode==network.AP_IF and w.wlan.active()
assert w.wlan._passphrase=='eightchars' and w.wlan._authmode==network.WLAN.SEC_WPA_WPA2
assert not w.connect_async('AP','short',False) and w.is_connected()
assert w.connect_async('station','sample',True) and w.mode==network.STA_IF
w.reset();assert w.timeout==.1
assert not [task for task in vm.thread_manager._tasks if task.name=='WiFi']
wi.ticks_ms=original_clock;network.WLAN=original_wlan
print('PASS: correct network switch/AP interface, prompt failures, zero-tick timeout, cancellation and no Wi-Fi worker thread')

import ubluetooth
bt=Bluetooth(vm.storage)
assert not bt.supports_pairing and not bt.pair() and 'unavailable' in bt.error
ubluetooth.sim_set_pairing_supported(True)
assert bt.start_peripheral('Picoware-Chat'),bt.error
assert len(bt._adv_payload)<=31 and len(bt._resp_payload)<=31
assert bt.decode_name(bt._resp_payload)=='Picoware-Chat'
assert not bt.start_peripheral('x'*30)
bt.stop_peripheral();assert bt.connect(0,b'\x02\x50\x43\x57\x10\x01')
assert not bt.is_uart_ready(),'GAP connect incorrectly advertised UART readiness'
for _ in range(20):bt.poll()
assert bt.is_uart_ready() and bt._cccd==5,bt.error
assert bt._cccd!=bt._peripheral_tx_handle+1
received=[];bt.on_notify(lambda value:received.append(value))
mutable=bytearray(b'owned')
bt._ble._emit(18,(bt._conn_handle,bt._peripheral_tx_handle,memoryview(mutable)));mutable[:]=b'other'
assert received==[]
bt.poll();assert received==[b'owned']
received.clear();assert bt.write('abc'*29,response=True)
for _ in range(30):bt.poll()
assert b''.join(received)==b'abc'*29 and bt._out_bytes==0
assert not bt.write('x'*1025)
assert bt.subscribe(notify=False)
for _ in range(3):bt.poll()
assert not bt.is_uart_ready()
assert bt.subscribe()
for _ in range(3):bt.poll()
assert bt.is_uart_ready()
# Pairing key callbacks are synchronous; persistence happens outside the IRQ.
assert bt.pair()
for _ in range(4):bt.poll()
assert bt.bonds_saved,bt.error
assert bt.save_paired_device('02:50:43:57:10:01','Test peripheral')
assert bt.is_device_paired('02:50:43:57:10:01')
stored=bt._ble._emit(29,(1,0,b'simulator-bond-key'))
assert stored==b'simulator-bond-value'
new=Bluetooth(vm.storage);bt.close();assert new._ble.active()
assert new._ble._emit(29,(1,0,b'simulator-bond-key'))==stored
assert new.remove_paired_device('02:50:43:57:10:01') and not new.is_device_paired('02:50:43:57:10:01')
assert new._ble._emit(29,(1,0,b'simulator-bond-key')) is None
calls=[];new._ble.gap_passkey=lambda *args:calls.append(args)
new._ble._emit(31,(1,2,0));new.poll();assert new.passkey_reply(passkey=0) and calls[-1]==(1,2,0)
new._ble._emit(31,(1,4,123456));new.poll();assert new.passkey_reply(True) and calls[-1]==(1,4,1)
new._ble._emit(31,(1,4,123456));new.poll();assert new.passkey_reply(False) and calls[-1]==(1,4,0)
assert new.decode_name(b'\x20\x09bad')=='' and new.decode_services(b'\x20\x07bad')==[]
new.close()
class FailingStorage:
    def __init__(self,storage):self.storage=storage;self.writes=0
    def __getattr__(self,name):return getattr(self.storage,name)
    def serialize(self,*args):self.writes+=1;return False
bad_storage=FailingStorage(vm.storage);bad=Bluetooth(bad_storage)
assert bad._ble._emit(30,(1,b'key',b'value')) is True
for _ in range(12):bad.poll()
assert not bad.bonds_saved and bad_storage.writes==1
assert not bad.save_paired_device('FA:KE','Unstored')
bad.close()
print('PASS: advertising limits, real UUID equality/discovery, CCCD discovery/ACK, owned IRQ data and MTU-bounded writes')
print('PASS: pairing unsupported by default; opt-in protocol fixture verifies bonding storage/forget, failed writes and passkeys')

# Pending operations must expire/cancel even when the driver delivers no completion.
from picoware.system import bluetooth as bluetooth_module
original_clock=bluetooth_module.ticks_ms;clock=[0];bluetooth_module.ticks_ms=lambda:clock[0]
slow=Bluetooth(vm.storage);calls=[]
slow._ble.gap_connect=lambda *args:calls.append(args)
assert slow.connect(0,b'\x01'*6,timeout_ms=100)
clock[0]=101;slow.poll()
assert not slow.is_connecting and calls[-1]==(None,) and 'timed out' in slow.error
slow.close()
clock[0]=0;slow=Bluetooth(vm.storage)
slow._ble.gattc_discover_services=lambda *args:None
assert slow.connect(0,b'\x02\x50\x43\x57\x10\x01',timeout_ms=100)
slow.poll();assert slow.is_connected and not slow.is_uart_ready()
clock[0]=101;slow.poll();slow.poll()
assert not slow.is_connected and 'timed out' in slow.error
slow.close()
clock[0]=0;slow=Bluetooth(vm.storage)
assert slow.connect(0,b'\x02\x50\x43\x57\x10\x01')
for _ in range(20):slow.poll()
slow._ble.gattc_write=lambda *args:None
assert slow.write('requires ACK',response=True);slow.poll()
clock[0]=5001;slow.poll();slow.poll()
assert not slow.is_connected and 'write timed out' in slow.error
slow.close();bluetooth_module.ticks_ms=original_clock
print('PASS: BLE connect/discovery/write deadlines cancel incomplete driver operations')

# Worker failures must not leave NTP permanently "requested" after a DNS failure.
from picoware.system.time import Time
class Tasks:
 def __init__(self):self.tasks=[]
 def add_task(self,task):self.tasks.append(task)
class BrokenDNS:
 def getaddrinfo(self,*args):raise OSError('DNS unavailable')
manager=Tasks();ntp=Time(manager);ntp._is_set=False
old_socket=sys.modules.get('usocket');sys.modules['usocket']=BrokenDNS()
try:
 assert ntp.fetch() and ntp.is_fetching
 try:manager.tasks[-1].function()
 except OSError:pass
 else:raise AssertionError('DNS failure was not exercised')
 assert not ntp.is_running and not ntp.is_fetching and not ntp.is_set
 assert ntp.fetch() and len(manager.tasks)==2
finally:
 if old_socket is None:sys.modules.pop('usocket',None)
 else:sys.modules['usocket']=old_socket
 ntp._current_task=None
print('PASS: NTP worker failure permits a new time-sync request')
