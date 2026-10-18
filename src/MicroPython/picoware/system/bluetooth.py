"""Bounded BLE central/peripheral transport. Call poll() from the app loop.

Adapted from MicroPython's ble_simple_central, ble_simple_peripheral and
ble_advertising examples; upstream attribution retained from Picoware.
"""
# https://github.com/micropython/micropython/blob/master/examples/bluetooth/ble_simple_central.py
# https://github.com/micropython/micropython/blob/master/examples/bluetooth/ble_simple_peripheral.py
# https://github.com/micropython/micropython/blob/master/examples/bluetooth/ble_advertising.py
import struct
from utime import ticks_ms,ticks_diff
from micropython import const

_IRQ_CENTRAL_CONNECT=const(1)
_IRQ_CENTRAL_DISCONNECT=const(2)
_IRQ_GATTS_WRITE=const(3)
_IRQ_SCAN_RESULT=const(5)
_IRQ_SCAN_DONE=const(6)
_IRQ_PERIPHERAL_CONNECT=const(7)
_IRQ_PERIPHERAL_DISCONNECT=const(8)
_IRQ_GATTC_SERVICE_RESULT=const(9)
_IRQ_GATTC_SERVICE_DONE=const(10)
_IRQ_GATTC_CHARACTERISTIC_RESULT=const(11)
_IRQ_GATTC_CHARACTERISTIC_DONE=const(12)
_IRQ_GATTC_DESCRIPTOR_RESULT=const(13)
_IRQ_GATTC_DESCRIPTOR_DONE=const(14)
_IRQ_GATTC_READ_RESULT=const(15)
_IRQ_GATTC_READ_DONE=const(16)
_IRQ_GATTC_WRITE_DONE=const(17)
_IRQ_GATTC_NOTIFY=const(18)
_IRQ_ENCRYPTION_UPDATE=const(28)
_IRQ_GET_SECRET=const(29)
_IRQ_SET_SECRET=const(30)
_IRQ_PASSKEY_ACTION=const(31)
_PASSKEY_ACTION_INPUT=const(2)
_PASSKEY_ACTION_DISPLAY=const(3)
_PASSKEY_ACTION_NUMERIC_COMPARISON=const(4)
_ADV_MAX_PAYLOAD=const(31)
_UART_SERVICE_UUID='6E400001-B5A3-F393-E0A9-E50E24DCCA9E'
_UART_RX_CHAR_UUID='6E400002-B5A3-F393-E0A9-E50E24DCCA9E'
_UART_TX_CHAR_UUID='6E400003-B5A3-F393-E0A9-E50E24DCCA9E'
_BONDING_FILE='picoware/bluetooth/paired_devices.json'
_SECRETS_FILE='picoware/bluetooth/bonds.json'
_owner_token=0
_connection_active=False


def connection_active():
    """Read the current wrapper's link state without activating the radio."""
    return _connection_active



class Bluetooth:
    def __init__(self,storage=None):
        global _owner_token, _connection_active
        from ubluetooth import BLE,UUID
        _owner_token+=1;self._token=_owner_token
        _connection_active=False
        self._ble=BLE();self._closed=False
        self._callback=self._scan_callback=self._write_callback=self._notify_callback=None
        self._storage=storage;self.error='';self._events=[];self._out=[];self._out_bytes=0
        self._scanning=False;self._connecting=False;self._connected=False
        self._conn_handle=None;self._connected_addr=None;self._central_connections=set()
        self._tx_handle=self._rx_handle=None;self._peripheral_registered=False
        self._peripheral_rx_handle=self._peripheral_tx_handle=None
        self._start_handle=self._end_handle=None;self._cccd=None
        self._services=[];self._characteristics=[];self._definitions=[]
        self._discovery_complete=False;self._subscribed=False;self._subscribe_pending=None
        self._mtus={};self._write_pending=None;self._write_started=None
        self._auto_discover=True;self._started=None;self._timeout_ms=10000
        self._advertising=False;self._adv_payload=b'';self._resp_payload=b'';self._interval=500000
        self._pairing=False;self._passkey=None;self._passkey_action=None;self._passkey_conn=None
        self._secrets={};self._dirty=False;self._bond_saved=False;self._new_secret_ids=set();self._flush_failed=False
        self._uart_uuid=UUID(_UART_SERVICE_UUID);self._rx_uuid=UUID(_UART_RX_CHAR_UUID);self._tx_uuid=UUID(_UART_TX_CHAR_UUID)
        self._load_secrets()
        # Native BLE is a singleton. Retire the previous handler before resetting it;
        # an old wrapper's late finalizer must not deactivate a new controller owner.
        self._ble.irq(None);self._ble.active(False);self._ble.active(True)
        self._ble.irq(self.__irq)

    def __del__(self):
        try:self.close()
        except Exception:pass

    def close(self):
        global _connection_active
        if self._closed:return
        self._closed=True
        if self._token==_owner_token:
            _connection_active=False
            self.flush_bonds()
            self._ble.irq(None)
            try:self._ble.gap_scan(None);self._ble.gap_advertise(None)
            except OSError:pass
            try:self._ble.active(False)
            except OSError:pass
        self._events=[];self._out=[];self._out_bytes=0
        self._connected=self._scanning=self._connecting=self._advertising=False
        self._central_connections.clear()
        self._callback=self._scan_callback=self._write_callback=self._notify_callback=None

    @property
    def callback(self):return self._callback
    @callback.setter
    def callback(self,value):self._callback=value
    @property
    def characteristics(self):return self._characteristics
    @property
    def services(self):return self._services
    @property
    def connected_address(self):return self._connected_addr
    @property
    def is_connected(self):return self._connected
    @property
    def is_connecting(self):return self._connecting
    @property
    def is_scanning(self):return self._scanning
    @property
    def is_peripheral_connected(self):return bool(self._central_connections)
    @property
    def central_connections(self):return self._central_connections
    @property
    def is_pairing(self):return self._pairing
    @property
    def supports_pairing(self):
        if not hasattr(self._ble,'gap_pair'):return False
        try:
            self._ble.config(bond=self._storage is not None,io=4)
            return True
        except (OSError,ValueError,AttributeError):return False
    @property
    def passkey(self):return self._passkey
    @property
    def passkey_action(self):return self._passkey_action
    @property
    def discovery_complete(self):return self._discovery_complete
    @property
    def bonds_saved(self):return self._bond_saved and not self._dirty
    @property
    def mac_address(self):
        addr=self._ble.config('mac');addr=addr[1] if isinstance(addr,tuple) else addr
        return ':'.join('%02X'%b for b in addr)

    def _queue(self,event,data):
        if len(self._events)>=64:
            # Drop scan traffic first, keeping disconnect/security events responsive.
            index=next((i for i,item in enumerate(self._events) if item[0]==5),None)
            if index is not None:self._events.pop(index)
            elif event==5:return
            else:self.error='Bluetooth event queue full.';return
        self._events.append((event,data))

    def __irq(self,event,data):
        if self._closed or self._token!=_owner_token:return
        if event==_IRQ_GET_SECRET:
            kind,index,key=data
            if key is None:
                keys=[value for (typ,_),value in self._secrets.items() if typ==kind]
                return keys[index] if 0<=index<len(keys) else None
            return self._secrets.get((kind,bytes(key)))
        if event==_IRQ_SET_SECRET:
            kind,key,value=data;key=(kind,bytes(key))
            if value is None:self._secrets.pop(key,None)
            else:
                if len(key[1])>64 or len(value)>256 or (key not in self._secrets and len(self._secrets)>=16):return False
                self._secrets[key]=bytes(value)
            self._new_secret_ids.add(key)
            self._dirty=True;self._bond_saved=False;self._flush_failed=False
            return True
        # Snapshot native ring-buffer views while they are valid. No UI callbacks
        # or filesystem writes run from the Bluetooth IRQ.
        if event in (1,2,7,8):data=(data[0],data[1],bytes(data[2]))
        elif event==5:data=(data[0],bytes(data[1]),data[2],data[3],bytes(data[4]))
        elif event in (9,11,13):
            from ubluetooth import UUID
            data=tuple(data[:-1])+(UUID(data[-1]),)
        elif event in (15,18,19):data=(data[0],data[1],bytes(data[2]))
        elif event==3:data=(data[0],data[1],bytes(self._ble.gatts_read(data[1])))
        self._queue(event,data)

    def poll(self):
        global _connection_active
        if self._closed or self._token!=_owner_token:return
        # Process one bounded snapshot; callbacks cannot recursively drain new IRQs.
        count=min(8,len(self._events))
        for _ in range(count):
            if self._closed or not self._events:break
            event,data=self._events.pop(0)
            try:
                self._event(event,data)
                _connection_active=self._connected or bool(self._central_connections)
                if self._callback:self._callback(event,data)
            except Exception as exc:self.error='Bluetooth event failed: '+str(exc)
        if self._started is not None and ticks_diff(ticks_ms(),self._started)>=self._timeout_ms:
            if self._connecting or self._pairing or (self._connected and not self._discovery_complete):
                self.error='Bluetooth operation timed out.';self.disconnect()
            self._started=None
        if self._write_pending is not None and self._write_started is not None and ticks_diff(ticks_ms(),self._write_started)>=5000:
            self.error='Bluetooth write timed out.';self.disconnect()
        if self._dirty and not self._flush_failed:self.flush_bonds()
        self._send_next()

    def _event(self,event,data):
        if event==1:self._central_connections.add(data[0]);self._mtus[data[0]]=23
        elif event==2:
            self._central_connections.discard(data[0]);self._drop_out(data[0]);self._mtus.pop(data[0],None)
            if self._advertising:self._start_advertising()
        elif event==3:
            if data[1]==self._rx_handle and self._write_callback:self._write_callback(data[2])
        elif event==5:
            if self._scan_callback and data[2] in (0,1,4):self._scan_callback(data[0],data[1],self.decode_name(data[4]),data[3],data[4])
        elif event==6:self._scanning=False
        elif event==7:
            self._conn_handle=data[0];self._connected=True;self._connecting=False;self._mtus[data[0]]=23
            self._connected_addr=':'.join('%02X'%b for b in data[2])
            if self._auto_discover:self.discover_services()
            else:self._discovery_complete=True;self._started=None
        elif event==8:
            self._drop_out(data[0]);self._connected=self._connecting=self._pairing=False
            self._conn_handle=self._connected_addr=None;self._clear_discovery();self._started=None
        elif event==9 and data[0]==self._conn_handle:
            if len(self._services)<64:self._services.append(data[1:])
            if data[3]==self._uart_uuid:self._start_handle,self._end_handle=data[1:3]
        elif event==10 and data[0]==self._conn_handle:
            if data[1]:self.error='Service discovery failed.';self._discovery_complete=True
            elif self._start_handle is not None:self._ble.gattc_discover_characteristics(self._conn_handle,self._start_handle,self._end_handle)
            else:self._discovery_complete=True;self._started=None
        elif event==11 and data[0]==self._conn_handle:
            if len(self._characteristics)<64:
                self._characteristics.append((data[2],data[3],data[4]));self._definitions.append(data[1:])
            if data[4]==self._rx_uuid:self._peripheral_rx_handle=data[2]
            if data[4]==self._tx_uuid:self._peripheral_tx_handle=data[2]
        elif event==12 and data[0]==self._conn_handle:
            if data[1] or self._peripheral_tx_handle is None or self._peripheral_rx_handle is None:
                self.error='UART characteristics unavailable.';self._discovery_complete=True;return
            start=self._peripheral_tx_handle+1
            end=min([d[0]-1 for d in self._definitions if d[0]>self._peripheral_tx_handle]+[self._end_handle])
            if start>end:self.error='UART notification descriptor missing.';self._discovery_complete=True;return
            self._ble.gattc_discover_descriptors(self._conn_handle,start,end)
        elif event==13 and data[0]==self._conn_handle:
            from ubluetooth import UUID
            if data[2]==UUID(0x2902):self._cccd=data[1]
        elif event==14 and data[0]==self._conn_handle:
            if data[1] or self._cccd is None:
                self.error='UART notification descriptor unavailable.';self._discovery_complete=True
            else:self.subscribe()
        elif event==17 and data[0]==self._conn_handle:
            if self._subscribe_pending==data[1]:
                self._subscribe_pending=None;self._discovery_complete=True;self._started=None
                self._subscribed=self._subscription_enabled and data[2]==0
                if data[2]:self.error='Notification subscription failed.'
            elif self._write_pending==data[1]:
                self._write_pending=None;self._write_started=None
                if data[2]:self.error='Remote write failed.';self._drop_out(data[0])
        elif event==18:
            if data[0]==self._conn_handle and data[1]==self._peripheral_tx_handle and self._notify_callback:self._notify_callback(data[2])
        elif event==21:self._mtus[data[0]]=max(23,int(data[1]))
        elif event==28:
            self._pairing=False;self._passkey_action=None;self._started=None
            if not data[1]:self.error='Pairing/encryption failed.'
        elif event==31:
            self._passkey_conn,self._passkey_action,self._passkey=data

    def _clear_discovery(self):
        self._services=[];self._characteristics=[];self._definitions=[]
        self._start_handle=self._end_handle=self._cccd=None
        self._peripheral_tx_handle=self._peripheral_rx_handle=None
        self._subscribed=self._discovery_complete=False;self._subscribe_pending=None
        self._write_pending=self._write_started=None

    def _advertising_payload(self,name=None,services=None,appearance=0):
        from ubluetooth import UUID
        payload=bytearray(b'\x02\x01\x06')
        for service in services or ():
            raw=bytes(UUID(service));kind={2:3,4:5,16:7}.get(len(raw))
            if kind is None:raise ValueError('Invalid service UUID')
            payload.extend(bytes((len(raw)+1,kind))+raw)
        if appearance:payload.extend(b'\x03\x19'+struct.pack('<H',appearance))
        if name:
            raw=name.encode() if isinstance(name,str) else bytes(name)
            available=31-len(payload)-2
            if available>0:payload.extend(bytes((min(len(raw),available)+1,9 if len(raw)<=available else 8))+raw[:available])
        if len(payload)>31:raise ValueError('BLE advertising payload exceeds 31 bytes')
        return payload

    def _start_advertising(self,interval_us=None):
        self._ble.gap_advertise(self._interval if interval_us is None else interval_us,adv_data=self._adv_payload,resp_data=self._resp_payload)

    def advertise(self,interval_us=None,name='Picoware'):
        try:
            if interval_us is None:
                self._advertising=False;self._ble.gap_advertise(None);return True
            if not self.register():return False
            raw=name.encode() if isinstance(name,str) else bytes(name)
            # Flags + UART UUID fit in advertising; the full name uses scan response.
            if len(raw)>29:raise ValueError('BLE name exceeds 29 encoded bytes')
            self._adv_payload=self._advertising_payload(name=name,services=[self._uart_uuid])
            self._resp_payload=bytes((len(raw)+1,9))+raw if raw else b''
            self._interval=interval_us;self._advertising=True;self._start_advertising();return True
        except Exception as exc:self.error=str(exc);self._advertising=False;return False

    def register(self):
        if self._peripheral_registered:return True
        try:
            self._ble.gap_advertise(None)
            ((self._tx_handle,self._rx_handle),)=self._ble.gatts_register_services(((self._uart_uuid,((self._tx_uuid,0x12),(self._rx_uuid,0x0c))),))
            self._ble.gatts_set_buffer(self._rx_handle,512,True)
            self._peripheral_registered=True;return True
        except Exception as exc:self.error='UART registration failed: '+str(exc);return False
    def start_peripheral(self,name='Picoware',interval_us=500000):return self.advertise(interval_us,name)
    def stop_peripheral(self):return self.advertise(None)

    def scan(self,duration_ms=5000,interval_us=30000,window_us=30000,active=True,callback=None):
        if callback is not None:self._scan_callback=callback
        self.error='';self._scanning=True
        try:self._ble.gap_scan(duration_ms,interval_us,window_us,active);return True
        except Exception as exc:self.error='Scan failed: '+str(exc);self._scanning=False;return False
    def scan_stop(self):self._ble.gap_scan(None);self._scanning=False

    def connect(self,addr_type,addr,timeout_ms=10000,auto_discover=True):
        if self._connected or self._connecting:return False
        self.error='';self._clear_discovery();self._auto_discover=auto_discover
        self._started=ticks_ms();self._timeout_ms=timeout_ms;self._connecting=True
        try:self._ble.gap_scan(None);self._ble.gap_connect(addr_type,bytes(addr),timeout_ms);return True
        except Exception as exc:self.error='Connect failed: '+str(exc);self._connecting=False;self._started=None;return False

    def disconnect(self,conn_handle=None):
        if self._connecting:
            try:self._ble.gap_connect(None)
            except OSError:pass
            self._connecting=False
        handles=[conn_handle] if conn_handle is not None else list(self._central_connections)+([self._conn_handle] if self._conn_handle is not None else [])
        for handle in handles:
            try:self._ble.gap_disconnect(handle)
            except OSError:pass
            self._drop_out(handle)
        self._pairing=False;self._started=None

    def discover_services(self):
        if not self._connected:return False
        self._clear_discovery();self._started=ticks_ms()
        try:self._ble.gattc_discover_services(self._conn_handle);return True
        except OSError:self.error='Service discovery failed.';return False
    def discover_characteristics(self,start_handle,end_handle):
        if not self._connected:return False
        self._characteristics=[];self._definitions=[]
        try:self._ble.gattc_discover_characteristics(self._conn_handle,start_handle,end_handle);return True
        except OSError:self.error='Characteristic discovery failed.';return False
    def subscribe(self,handle=None,notify=True):
        if not self._connected or self._cccd is None or (handle is not None and handle!=self._peripheral_tx_handle):return False
        try:
            self._subscription_enabled=bool(notify)
            self._subscribe_pending=self._cccd
            self._ble.gattc_write(self._conn_handle,self._cccd,b'\x01\x00' if notify else b'\x00\x00',1)
            return True
        except OSError:self._subscribe_pending=None;self.error='Notification subscription failed.';return False
    def read(self,handle):
        if not self._connected:return False
        try:self._ble.gattc_read(self._conn_handle,handle);return True
        except OSError:self.error='Read failed.';return False
    def is_uart_ready(self):return self._connected and self._subscribed and self._peripheral_rx_handle is not None
    def on_write(self,callback):self._write_callback=callback
    def on_notify(self,callback):self._notify_callback=callback
    def on_scan(self,callback):self._scan_callback=callback

    def _enqueue(self,kind,connections,handle,data,response=False):
        raw=data.encode() if isinstance(data,str) else bytes(data)
        if not raw:return True
        if len(raw)*len(connections)+self._out_bytes>1024:self.error='Bluetooth send queue full.';return False
        self.error=''
        for conn in connections:self._out.append([kind,conn,handle,raw,0,response]);self._out_bytes+=len(raw)
        return bool(connections)
    def send(self,data):return self._enqueue('notify',list(self._central_connections),self._tx_handle,data) if self._tx_handle is not None else False
    def write(self,data,handle=None,response=False):
        handle=self._peripheral_rx_handle if handle is None else handle
        if not self._connected or handle is None:return False
        return self._enqueue('write',[self._conn_handle],handle,data,response)
    def _drop_out(self,conn):
        self._out=[item for item in self._out if item[1]!=conn]
        self._out_bytes=sum(len(item[3]) for item in self._out);self._write_pending=None
    def _send_next(self):
        if not self._out or self._write_pending is not None:return
        item=self._out[0];kind,conn,handle,raw,offset,response=item
        if conn!=self._conn_handle and conn not in self._central_connections:self._drop_out(conn);return
        packet=raw[offset:offset+max(1,min(244,self._mtus.get(conn,23)-3))]
        try:
            if kind=='notify':self._ble.gatts_notify(conn,handle,packet)
            else:
                if response:self._write_pending=handle;self._write_started=ticks_ms()
                self._ble.gattc_write(conn,handle,packet,1 if response else 0)
        except OSError as exc:
            self._write_pending=None
            if exc.args and exc.args[0] in (11,12,16):return
            self.error='Bluetooth send failed.';self._drop_out(conn);return
        item[4]+=len(packet)
        if item[4]>=len(raw):self._out.pop(0);self._out_bytes-=len(raw)

    def pair(self):
        if not self.supports_pairing:
            self.error='Pairing is unavailable in this firmware.';return False
        if not self._connected:return False
        try:
            self.error=''
            self._new_secret_ids=set()
            self._pairing=True;self._started=ticks_ms();self._timeout_ms=30000
            self._ble.gap_pair(self._conn_handle);return True
        except (OSError,ValueError,AttributeError):self._pairing=False;self.error='Pairing is unavailable in this firmware.';return False
    def passkey_reply(self,accept=True,passkey=None):
        if self._passkey_conn is None:return False
        action=self._passkey_action
        if action==2:
            if passkey is None or not 0<=int(passkey)<=999999:self.error='Enter a six-digit passkey.';return False
            value=int(passkey)
        elif action==4:value=int(bool(accept))
        else:return False
        try:self._ble.gap_passkey(self._passkey_conn,action,value)
        except (OSError,ValueError,AttributeError):self.error='Passkey exchange is unavailable in this firmware.';return False
        self._passkey_action=None;return True

    def _load_json(self,path):
        if self._storage is None:return {}
        try:
            if not self._storage.exists(path):return {}
            value=self._storage.deserialize(path)
            return value if isinstance(value,dict) else {}
        except Exception:return {}
    def _save_json(self,path,value):
        if self._storage is None:return False
        storage=self._storage;temporary=path+'.tmp';backup=path+'.bak'
        try:
            from ujson import loads
            storage.mkdir('picoware/bluetooth')
            if storage.exists(path) and not isinstance(loads(storage.read(path)),dict):return False
            if storage.exists(backup):self.error='Bluetooth backup needs recovery.';return False
            if not storage.serialize(value,temporary) or storage.deserialize(temporary)!=value:return False
            existed=storage.exists(path)
            if existed and not storage.rename(path,backup):return False
            if not storage.rename(temporary,path):
                if existed:storage.rename(backup,path)
                return False
            if existed:storage.remove(backup)
            return True
        except Exception:return False
    def _load_secrets(self):
        from ubinascii import unhexlify
        try:
            rows=self._load_json(_SECRETS_FILE).get('keys',[])
            for row in rows[:16]:
                typ,key,value=row;key,value=unhexlify(key),unhexlify(value)
                if len(key)<=64 and len(value)<=256:self._secrets[(int(typ),bytes(key))]=bytes(value)
            self._bond_saved=bool(self._secrets)
        except Exception:self._secrets={};self.error='Stored Bluetooth keys are invalid.'
    def flush_bonds(self):
        if not self._dirty:return self._bond_saved
        from ubinascii import hexlify
        value={'version':1,'keys':[[kind,hexlify(key).decode(),hexlify(val).decode()] for (kind,key),val in self._secrets.items()]}
        if self._save_json(_SECRETS_FILE,value):self._dirty=False;self._bond_saved=True;self._flush_failed=False;return True
        self.error='Bluetooth keys could not be saved.';self._bond_saved=False;self._flush_failed=True;return False
    def load_paired_devices(self):return self._load_json(_BONDING_FILE)
    def is_device_paired(self,addr):
        from ubinascii import unhexlify
        try:
            identifiers=self.load_paired_devices().get(addr,{}).get('bond_keys',[])
            return bool(identifiers) and all((kind,bytes(unhexlify(key))) in self._secrets for kind,key in identifiers)
        except (ValueError,TypeError):return False
    def save_paired_device(self,addr,name=''):
        from ubinascii import hexlify
        values=self.load_paired_devices();values[addr]={'name':name,'paired':True,'bond_keys':[[kind,hexlify(key).decode()] for kind,key in self._new_secret_ids]}
        if len(values)>32:self.error='Paired-device list is full.';return False
        return self._save_json(_BONDING_FILE,values)
    def remove_paired_device(self,addr):
        values=self.load_paired_devices()
        if addr not in values:return False
        from ubinascii import unhexlify
        if 'bond_keys' not in values[addr]:self.error='Legacy pairing has no saved key identifiers.';return False
        for kind,key in values[addr]['bond_keys']:self._secrets.pop((kind,bytes(unhexlify(key))),None)
        self._dirty=True
        if not self.flush_bonds():return False
        del values[addr];return self._save_json(_BONDING_FILE,values)

    def decode_name(self,adv_data):
        for kind,data in self._fields(adv_data):
            if kind in (8,9):
                try:return bytes(data).decode()
                except UnicodeError:pass
        return ''
    def _fields(self,raw):
        position=0
        while position+1<len(raw):
            length=raw[position]
            if length<1 or position+length+1>len(raw):break
            yield raw[position+1],raw[position+2:position+1+length]
            position+=length+1
    def decode_services(self,adv_data):
        from ubluetooth import UUID
        values=[]
        for kind,data in self._fields(adv_data):
            length=2 if kind in (2,3) else 4 if kind in (4,5) else 16 if kind in (6,7) else 0
            if length:
                for pos in range(0,len(data)-length+1,length):values.append(UUID(bytes(data[pos:pos+length])))
        return values
    def scan_for_uart_devices(self,callback,duration_ms=5000):
        seen=set()
        def result(addr_type,addr,name,rssi,adv_data):
            key=(addr_type,bytes(addr))
            if self._uart_uuid in self.decode_services(adv_data) and key not in seen and len(seen)<64:
                seen.add(key);callback(addr_type,bytes(addr),name)
        return self.scan(duration_ms=duration_ms,callback=result)
