import sim_runtime

_IRQ_CENTRAL_CONNECT = 1
_IRQ_CENTRAL_DISCONNECT = 2
_IRQ_GATTS_WRITE = 3
_IRQ_SCAN_RESULT = 5
_IRQ_SCAN_DONE = 6
_IRQ_PERIPHERAL_CONNECT = 7
_IRQ_PERIPHERAL_DISCONNECT = 8
_IRQ_GATTC_SERVICE_RESULT = 9
_IRQ_GATTC_SERVICE_DONE = 10
_IRQ_GATTC_CHARACTERISTIC_RESULT = 11
_IRQ_GATTC_CHARACTERISTIC_DONE = 12
_IRQ_GATTC_DESCRIPTOR_RESULT = 13
_IRQ_GATTC_DESCRIPTOR_DONE = 14
_IRQ_GATTC_READ_RESULT = 15
_IRQ_GATTC_READ_DONE = 16
_IRQ_GATTC_WRITE_DONE = 17
_IRQ_GATTC_NOTIFY = 18
_IRQ_ENCRYPTION_UPDATE = 28
_IRQ_PASSKEY_ACTION = 31

_UART_SERVICE_UUID = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
_UART_RX_CHAR_UUID = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"
_UART_TX_CHAR_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"


def _hex_to_bytes(text):
    text = text.replace("-", "")
    out = bytearray()
    for i in range(0, len(text), 2):
        out.append(int(text[i : i + 2], 16))
    return bytes(out)


class UUID:
    def __init__(self, value):
        if isinstance(value, UUID):
            self._bytes = value._bytes
            self._text = value._text
        elif isinstance(value, int):
            self._bytes = bytes((value & 0xFF, (value >> 8) & 0xFF))
            self._text = "%04X" % value
        elif isinstance(value, bytes) or isinstance(value, bytearray):
            self._bytes = bytes(value)
            if len(self._bytes) == 16:
                text = "".join("%02X" % b for b in reversed(self._bytes))
                self._text = text[0:8] + "-" + text[8:12] + "-" + text[12:16] + "-" + text[16:20] + "-" + text[20:32]
            elif len(self._bytes) == 2:
                self._text = "%02X%02X" % (self._bytes[1], self._bytes[0])
            else:
                self._text = "".join("%02X" % b for b in reversed(self._bytes))
        else:
            self._text = str(value).upper()
            self._bytes = bytes(reversed(_hex_to_bytes(self._text)))

    def __bytes__(self):
        return self._bytes

    def __iter__(self):
        return iter(self._bytes)

    def __len__(self):
        return len(self._bytes)

    def __getitem__(self, index):
        return self._bytes[index]

    def __str__(self):
        return "UUID(\'"+self._text.lower()+"\')"

    def __eq__(self, other):
        return self._bytes == UUID(other)._bytes


def _adv_payload(name, services=()):
    payload = bytearray()

    def append(kind, value):
        payload.extend(bytes((len(value) + 1, kind)))
        payload.extend(value)

    append(0x01, b"\x06")
    for service in services:
        b=bytes(UUID(service));append({2:3,4:5,16:7}[len(b)],b)
    if name:
        raw=name.encode() if isinstance(name,str) else bytes(name)
        available=31-len(payload)-2
        if available>0:append(9 if len(raw)<=available else 8,raw[:available])
    return bytes(payload)


def _default_devices():
    return [
        {
            "addr_type": 0,
            "addr": b"\x02\x50\x43\x57\x10\x01",
            "adv_type": 0,
            "rssi": -41,
            "adv_data": _adv_payload("Picoware-Chat", (_UART_SERVICE_UUID,)),
            "connectable": True,
            "name": "Picoware-Chat",
        },
        {
            "addr_type": 1,
            "addr": b"\x02\x50\x43\x57\x10\x02",
            "adv_type": 0,
            "rssi": -58,
            "adv_data": _adv_payload("Picoware-Beacon", ()),
            "connectable": True,
            "name": "Picoware-Beacon",
        },
        {
            "addr_type": 1,
            "addr": b"\x02\x50\x43\x57\x10\x03",
            "adv_type": 3,
            "rssi": -72,
            "adv_data": _adv_payload("SensorTag", (0x180F,)),
            "connectable": True,
            "name": "SensorTag",
        },
    ]


_scan_devices = _default_devices()
_advertisements = []


def sim_reset():
    global _scan_devices, _advertisements
    _scan_devices = _default_devices()
    _advertisements = []


def sim_clear_scan_devices():
    _scan_devices[:] = []


def sim_add_scan_device(
    name="Picoware-Sim",
    addr=b"\x02\x50\x43\x57\x30\x01",
    addr_type=0,
    adv_type=0,
    rssi=-50,
    services=(),
    connectable=True,
    adv_data=None,
):
    if adv_data is None:
        adv_data = _adv_payload(name, services)
    device = {
        "addr_type": addr_type,
        "addr": bytes(addr),
        "adv_type": adv_type,
        "rssi": rssi,
        "adv_data": bytes(adv_data),
        "connectable": bool(connectable),
        "name": name,
    }
    _scan_devices.append(device)
    return device


def sim_advertisements():
    return tuple(_advertisements)


def _find_scan_device(addr):
    addr = bytes(addr)
    for device in _scan_devices:
        if device["addr"] == addr:
            return device
    return None


# The selected Pico 2 W build uses BTstack with MicroPython pairing disabled.
# Protocol tests may opt in explicitly; this does not enable native firmware support.
_pairing_supported=False

def sim_set_pairing_supported(enabled):
    global _pairing_supported
    _pairing_supported=bool(enabled)

class BLE:
    def __init__(self):
        self._active = False
        self._irq = None
        self._mac = (1, b"\x02\x50\x43\x57\x42\x01")
        self._conn_handle = None
        self._next_handle = 16
        self._values = {}
        self._registered = ()
        self._advertising = False
        self._adv_data = b""
        self._notify_queue = []
        self._buffers={}
        self._subscribed=False

    def active(self, value=None):
        if value is None:
            return self._active
        self._active = bool(value)
        return None

    def irq(self, handler=None):
        self._irq = handler
        return None

    def config(self, *args, **kwargs):
        if not _pairing_supported and any(key in kwargs for key in ("bond","io","mitm","le_secure")):raise ValueError("unknown config param")
        if args and args[0] == "mac":
            return self._mac
        if "mac" in kwargs:
            self._mac = kwargs["mac"]
        return None

    def _emit(self, event, data):
        if self._irq:
            return self._irq(event, data)

    def gap_scan(self, duration_ms=None, interval_us=30000, window_us=30000, active=True):
        if duration_ms is None:
            self._emit(_IRQ_SCAN_DONE, None)
            return None
        if sim_runtime.bluetooth_mode == "off":
            self._emit(_IRQ_SCAN_DONE, None)
            return None
        for device in _scan_devices:
            self._emit(
                _IRQ_SCAN_RESULT,
                (
                    device["addr_type"],
                    device["addr"],
                    device["adv_type"],
                    device["rssi"],
                    device["adv_data"],
                ),
            )
            if active and device.get('name'):
                raw=device['name'].encode()[:29]
                self._emit(_IRQ_SCAN_RESULT,(device['addr_type'],device['addr'],4,device['rssi'],bytes((len(raw)+1,9))+raw))
        self._emit(_IRQ_SCAN_DONE, None)
        return None

    def gap_connect(self, addr_type, addr=None, timeout_ms=10000):
        if addr_type is None:
            self._emit(_IRQ_PERIPHERAL_DISCONNECT,(self._conn_handle or 0,0,b"\0"*6));return
        addr = bytes(addr)
        device = _find_scan_device(addr)
        if (
            sim_runtime.bluetooth_mode == "off"
            or device is None
            or not device.get("connectable", True)
        ):
            self._emit(_IRQ_PERIPHERAL_DISCONNECT, (0, addr_type, addr))
            return None
        self._peer=device
        self._conn_handle = 1
        self._emit(_IRQ_PERIPHERAL_CONNECT, (self._conn_handle, addr_type, addr))
        return None

    def gap_disconnect(self, conn_handle):
        addr = b"\x02\x50\x43\x57\x10\x01"
        if conn_handle == self._conn_handle:
            self._emit(_IRQ_PERIPHERAL_DISCONNECT, (conn_handle, 0, addr))
            self._conn_handle = None
        else:
            self._emit(_IRQ_CENTRAL_DISCONNECT, (conn_handle, 0, addr))
        return None

    def gap_advertise(self, interval_us, adv_data=None, resp_data=None, connectable=True):
        if len(adv_data or b" ")>31 or len(resp_data or b" ")>31:raise ValueError("Advertising payload exceeds 31 bytes")
        self._advertising = interval_us is not None
        self._adv_data = adv_data or b""
        _advertisements.append(
            {
                "interval_us": interval_us,
                "adv_data": bytes(self._adv_data),
                "resp_data": bytes(resp_data or b""),
                "connectable": bool(connectable),
            }
        )
        return None

    def gatts_register_services(self, services):
        registered = []
        for service in services:
            chars = []
            for _char in service[1]:
                handle = self._next_handle
                self._next_handle += 2
                self._values[handle] = b""
                chars.append(handle)
            registered.append(tuple(chars))
        self._registered = tuple(registered)
        return self._registered

    def gatts_set_buffer(self,value_handle,length,append=False):self._buffers[value_handle]=(length,append)

    def gatts_read(self, value_handle):
        result=self._values.get(value_handle,b"")
        if self._buffers.get(value_handle,(0,False))[1]:self._values[value_handle]=b""
        return result

    def gatts_write(self, value_handle, data, send_update=False):
        self._values[value_handle] = bytes(data)
        return None

    def gatts_notify(self, conn_handle, value_handle, data=None):
        if data is not None and len(data)>20:raise ValueError("Notification exceeds negotiated MTU")
        if data is None:
            data = self._values.get(value_handle, b"")
        self._notify_queue.append((conn_handle, value_handle, bytes(data)))
        return None

    def gattc_discover_services(self, conn_handle):
        if bytes(UUID(_UART_SERVICE_UUID)) in self._peer["adv_data"]:
            self._emit(_IRQ_GATTC_SERVICE_RESULT, (conn_handle, 1, 9, UUID(_UART_SERVICE_UUID)))
        self._emit(_IRQ_GATTC_SERVICE_DONE, (conn_handle, 0))
        return None

    def gattc_discover_characteristics(self, conn_handle, start_handle, end_handle):
        self._emit(_IRQ_GATTC_CHARACTERISTIC_RESULT, (conn_handle, 2, 3, 0x0010, UUID(_UART_TX_CHAR_UUID)))
        self._emit(_IRQ_GATTC_CHARACTERISTIC_RESULT, (conn_handle, 7, 8, 0x000C, UUID(_UART_RX_CHAR_UUID)))
        self._emit(_IRQ_GATTC_CHARACTERISTIC_DONE, (conn_handle, 0))
        return None

    def gattc_read(self, conn_handle, value_handle):
        data = self._values.get(value_handle, b"Picoware-Sim")
        self._emit(_IRQ_GATTC_READ_RESULT, (conn_handle, value_handle, data))
        self._emit(_IRQ_GATTC_READ_DONE, (conn_handle, value_handle, 0))
        return None

    def gattc_discover_descriptors(self,conn_handle,start_handle,end_handle):
        # A user-description descriptor occupies TX+1. CCCD is TX+2.
        for handle,uuid in ((4,0x2901),(5,0x2902)):
            if start_handle<=handle<=end_handle:self._emit(13,(conn_handle,handle,UUID(uuid)))
        self._emit(14,(conn_handle,0))

    def gattc_write(self,conn_handle,value_handle,data,mode=0):
        data=bytes(data)
        if len(data)>20:raise ValueError('Write exceeds negotiated MTU')
        self._values[value_handle]=data
        if value_handle==5:self._subscribed=data==b"\x01\x00"
        if mode:self._emit(_IRQ_GATTC_WRITE_DONE,(conn_handle,value_handle,0))
        if value_handle==8 and self._subscribed:self._emit(_IRQ_GATTC_NOTIFY,(conn_handle,3,data))

    def gap_pair(self, conn_handle):
        if not _pairing_supported:raise OSError(95)
        self._persist_pair(conn_handle)
        self._emit(_IRQ_ENCRYPTION_UPDATE, (conn_handle, True, True, True, 16))
        return None

    def gap_passkey(self, conn_handle, action, passkey):
        if not _pairing_supported:raise OSError(95)
        self._persist_pair(conn_handle)
        self._emit(_IRQ_ENCRYPTION_UPDATE, (conn_handle, True, True, True, 16))
        return None

    def _persist_pair(self,conn_handle):
        if self._irq:self._irq(30,(1,b'simulator-bond-key',b'simulator-bond-value'))

    def sim_notifications(self):
        out = tuple(self._notify_queue)
        self._notify_queue = []
        return out
