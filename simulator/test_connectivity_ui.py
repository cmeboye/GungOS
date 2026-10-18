"""Built-in BLE menus/chat/pairing and nonblocking HTTP server regressions."""
import os,sys
from time import ticks_ms
root=os.getcwd()
for name in ('src/MicroPython','simulator/hardware','builds/MicroPython/apps_unfrozen'):sys.path.insert(0,root+'/'+name)
import sim_runtime
sim_runtime.configure(root,'/private/tmp/gungos-radio-ui-'+str(ticks_ms()),root+'/builds/MicroPython/apps_unfrozen',1,'picocalc-pico2w',0,True,False,False,False,'',_network_mode='offline',_audio_mode='silent')
from picoware.system.view_manager import ViewManager
from picoware.system.view import View
from picoware.system.input import Input
from picoware.system import buttons as k
from picoware.applications.bluetooth import scan,advertise,pair,uart_chat,beacon,rssi_monitor
Input.button=property(lambda self:self._last_button)
vm=ViewManager();alerts=[]
ViewManager.alert=lambda self,message,*args,**kwargs:alerts.append(message)
vm.add(View('parent',lambda vm:None,lambda vm:True,lambda vm:None));vm.switch_to('parent')
def key(value=k.BUTTON_NONE):vm.input_manager._last_button=value;vm.run()
def open_app(name,module):vm.add(View(name,module.run,module.start,module.stop));vm.switch_to(name)
def text(value):
 for char in value:key(vm.input_manager._key_to_button(ord(char)))
assert not pair.start(vm) and pair._bluetooth._closed
assert 'pairing is unavailable' in alerts[-1]
pair.stop(vm)
# Explicit capability fixture exercises the generic UI on a stack offering SMP.
import ubluetooth
ubluetooth.sim_set_pairing_supported(True)
for module in (scan,advertise,beacon,rssi_monitor):
 name='test_'+module.__name__.rsplit('.',1)[-1];open_app(name,module)
 for _ in range(8):key()
 assert vm.current_view.name==name,(name,alerts)
 if module==scan:assert scan._scanned_devices[0][2]=='Picoware-Chat'
 old=module._bluetooth;key(k.BUTTON_ESCAPE)
 assert vm.current_view.name=='parent' and old._closed and not old._ble.active()
open_app('test_pair',pair)
for _ in range(3):key()
assert pair._scanned_devices
key(k.BUTTON_CENTER)
for _ in range(4):key()
assert pair._state==pair.STATE_CONNECTED
key(k.BUTTON_CENTER)
for _ in range(5):key()
assert pair._state==pair.STATE_PAIRED and pair._save_ok,alerts
writes=[];original=vm.storage.serialize
def tracked(*args):writes.append(args);return original(*args)
vm.storage.serialize=tracked
for _ in range(20):key()
assert writes==[],'Pair screen rewrote SD every frame'
vm.storage.serialize=original;key(k.BUTTON_ESCAPE)
open_app('test_chat',uart_chat);key(k.BUTTON_CENTER)
for _ in range(4):key()
assert uart_chat._state==uart_chat.STATE_DEVICE_LIST
key(k.BUTTON_CENTER)
for _ in range(16):key()
assert uart_chat._state==uart_chat.STATE_CHAT,alerts
key(k.BUTTON_CENTER)
assert uart_chat._state==uart_chat.STATE_TYPING
message='A longer message than one BLE packet'
text(message);assert vm.keyboard.response==message
key(k.BUTTON_CENTER)
for _ in range(20):key()
assert (True,message) in uart_chat._messages and (False,message) in uart_chat._messages,uart_chat._messages
key(k.BUTTON_ESCAPE);assert uart_chat._menu.item_count==2 and uart_chat._menu.title=='UART Chat'
key(k.BUTTON_DOWN);key(k.BUTTON_CENTER)
assert uart_chat._state==uart_chat.STATE_PERIPHERAL_WAIT
old=uart_chat._bluetooth
old._ble._emit(1,(2,0,b'\x01'*6));key()
assert uart_chat._state==uart_chat.STATE_CHAT
utf8='µ-test'.encode();uart_chat.on_data_received(utf8[:1]);uart_chat.on_data_received(utf8[1:]+b'\n')
assert uart_chat._messages[-1]==(False,'µ-test')
key(k.BUTTON_ESCAPE);assert old._closed
key(k.BUTTON_ESCAPE);assert vm.current_view.name=='parent'
print('PASS: all six BLE app lifecycles, full scan-response names, persisted pair-once, keyboard commit, UART readiness, long/UTF-8 lines and mode return')

from picoware.applications.wifi import server as app
class Client:
 def __init__(self,parts):self.parts=list(parts);self.output=bytearray();self.closed=False;self.blocking=[]
 def setblocking(self,value):self.blocking.append(value)
 def recv(self,count):
  if not self.parts:raise OSError(11)
  data=self.parts.pop(0)
  if data is None:raise OSError(11)
  if len(data)>count:self.parts.insert(0,data[count:]);data=data[:count]
  return data
 def send(self,data):
  size=min(7,len(data));self.output.extend(data[:size]);return size
 def close(self):self.closed=True
class Listener:
 def __init__(self):self.queue=[];self.closed=False
 def accept(self):
  if not self.queue:raise OSError(11)
  return self.queue.pop(0),('test-client',1)
 def close(self):self.closed=True
class ServerVM:
 button=k.BUTTON_NONE
 def log(self,*args):pass
sv=ServerVM();s=app.Server(sv);s.server=Listener()
s.add_route('/echo',lambda:'µ')
received=[]
s.add_route('/form',lambda value:received.append(value) or 'ok','POST')
def exchange(parts):
 client=Client(parts);s.server.queue.append(client)
 for _ in range(250):
  s.run()
  if client.closed:return bytes(client.output)
 raise AssertionError('HTTP exchange stalled')
response=exchange([None,b'GET /echo HTTP/1.1\r\nHost:test\r\n',b'\r\n'])
assert b'200 OK' in response and b'Content-Length: 2\r\n' in response and response.endswith('µ'.encode())
assert b'405' in exchange([b'POST /echo HTTP/1.1\r\n\r\n'])
assert b'400' in exchange([b'GET / HTTP/1.1\r\nContent-Length:-1\r\n\r\n'])
assert b'413' in exchange([b'POST /form HTTP/1.1\r\nContent-Length:5000\r\n\r\n'])
assert b'431' in exchange([b'x'*5000])
body=b'a=one%20two&symbol=%C2%B5'
assert b'200' in exchange([b'POST /form HTTP/1.1\r\nContent-Length:'+str(len(body)).encode()+b'\r\n\r\n',body])
assert received[-1]=={'a':'one two','symbol':'µ'}
assert b'400' in exchange([b'POST /form HTTP/1.1\r\nContent-Type:application/json\r\nContent-Length:1\r\n\r\n{'])
import utime
clock=[0];original_clock=app.ticks_ms;app.ticks_ms=lambda:clock[0]
client=Client([]);s.server.queue.append(client);s.run();assert s.client is client
clock[0]=5001;s.run()
for _ in range(100):s.run()
assert client.closed and b'408' in client.output
app.ticks_ms=original_clock
s.close();assert s.server is None
# A settings write failure is reported without replacing the existing document.
vm.storage.mkdir('picoware/wifi/server')
assert vm.storage.serialize({'settings':{'mode':'STA'}},app.SERVER_INFO)
class FailedStorage:
 def __init__(self,storage):self.storage=storage
 def __getattr__(self,name):return getattr(self.storage,name)
 def serialize(self,*args):return False
original_storage=vm._storage;vm._storage=FailedStorage(original_storage)
assert app.__save_setting(vm,'mode','AP') is False
vm._storage=original_storage
assert vm.storage.deserialize(app.SERVER_INFO)['settings']['mode']=='STA'
assert 'could not be saved' in alerts[-1]
print('PASS: partial HTTP reads/writes, Content-Length bytes, malformed/oversized requests, timeout, form decoding and failed SD settings writes')

# Server AP mode must be configurable without a pre-existing station connection.
class BindableListener(Listener):
 def setsockopt(self,*args):pass
 def bind(self,address):self.address=address
 def listen(self,backlog):self.backlog=backlog
 def setblocking(self,value):assert value is False
class SocketAPI:
 SOL_SOCKET=1
 SO_REUSEADDR=2
 def getaddrinfo(self,host,port):return [(2,1,0,'',(host,port))]
 def socket(self):return BindableListener()
original_socket=sys.modules.get('socket');sys.modules['socket']=SocketAPI()
vm.wifi.reset()
assert vm.storage.write('picoware/wifi/server/route.py','from math import sqrt\ndef handle_request(data=None):\n return str(sqrt(9))\n')
assert vm.storage.serialize({'settings':{'mode':'AP','ssid':'Test AP'},'pages':[{'url':'/script','method':'GET','script':'picoware/wifi/server/route.py'}]},app.SERVER_INFO)
assert app.start(vm)
try:
 assert app.__server_start(vm)
 assert app.server._owns_ap and vm.wifi.mode==1
 route=app.server.routes['/script']['GET']['handler']
 assert route()=='3.0','Script imports were missing from function globals'
 app.server._close_client();app.server.client=Client([]);app.server._client_started=0
 app.menu_state=app.STATE_RUNNING
 vm._button=k.BUTTON_ESCAPE;app.run(vm)
 assert app.server.server is None and not vm.wifi.is_connected()
finally:
 vm._button=k.BUTTON_NONE;app.stop(vm)
 if original_socket is not None:sys.modules['socket']=original_socket
 else:sys.modules.pop('socket',None)
print('PASS: disconnected server editor, real AP interface setup/cleanup, Esc on stalled peer and script import scope')

from picoware.applications.wifi import scan as wifi_scan,rssi_monitor as wifi_rssi
original_scan=vm.wifi.scan
vm.wifi.scan=lambda:[(b'',b'',1,-50,0,1),(b'\xff',b'',1,-40,0,0)]+[(('AP'+str(i)).encode(),b'',1,-30,0,0) for i in range(90)]
assert wifi_scan.start(vm)
assert len(wifi_scan._scan_ssids)==64 and wifi_scan._scan_ssids[0]==''
vm._button=k.BUTTON_CENTER;wifi_scan.run(vm)
assert 'hidden network' in alerts[-1]
wifi_scan.stop(vm);assert wifi_scan._scan_ssids==[]
clock=[500];old_clock=wifi_rssi.ticks_ms;wifi_rssi.ticks_ms=lambda:clock[0]
scans=[]
def counted_scan():scans.append(1);return []
vm.wifi.scan=counted_scan;vm._button=k.BUTTON_NONE
assert wifi_rssi.start(vm)
for value in (1000,1500,2000,2500):clock[0]=value;wifi_rssi.run(vm)
assert len(scans)==1,'RSSI monitor scanned at every redraw'
clock[0]=3000;wifi_rssi.run(vm);assert len(scans)==2
wifi_rssi.stop(vm);assert wifi_rssi.start(vm)
clock[0]=3500;wifi_rssi.run(vm);assert len(scans)==3,'Reopening RSSI inherited an old scan deadline'
wifi_rssi.stop(vm);wifi_rssi.ticks_ms=old_clock;vm.wifi.scan=original_scan
print('PASS: hidden/invalid SSIDs, bounded scan results, throttled RSSI scans and reopen cleanup')

# A first-use settings document is created; corrupt existing settings are preserved.
vm.storage.remove(app.SERVER_INFO)
assert app.__save_setting(vm,'mode','AP')
assert vm.storage.deserialize(app.SERVER_INFO)['settings']['mode']=='AP'
assert vm.storage.write(app.SERVER_INFO,'{invalid')
assert not app.__save_setting(vm,'mode','STA')
assert vm.storage.read(app.SERVER_INFO)=='{invalid'
print('PASS: first-use server settings creation and corrupt-document preservation')


# Failed Start must return to a usable menu and let Enter retry.
assert app.start(vm)
real_start=app.__server_start;attempts=[]
def delayed_start(manager):attempts.append(1);return False
app.__server_start=delayed_start
try:
 app.menu_state=app.STATE_MENU_MAIN;app.__menu_start(vm)
 vm._button=k.BUTTON_CENTER;app.run(vm)
 assert app.menu_state==app.STATE_MENU_MAIN,'Failed Start stranded the UI in running mode'
 assert app.menu.title=='Server' and app.menu.current_item=='Start'
 app.run(vm);assert len(attempts)==2,'Enter could not retry after a failed Start'
finally:
 app.__server_start=real_start;vm._button=k.BUTTON_NONE;app.stop(vm)
print('PASS: unsuccessful server Start keeps a usable menu and permits immediate retry')
