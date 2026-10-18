"""Offline characterization of inherited tools, not a physical certification."""
import os,sys,struct
from time import ticks_ms
root=os.getcwd()
for path in ('src/MicroPython','simulator/hardware'):
    sys.path.insert(0,root+'/'+path)
import sim_runtime
sim_runtime.configure(root,'/private/tmp/gungos-comms-audit-'+str(ticks_ms()),root+'/builds/MicroPython/apps_unfrozen',1,'picocalc-pico2w',0,True,False,False,False,'',_network_mode='offline',_audio_mode='silent',_sd_profile='clean')
from picoware.system.view_manager import ViewManager
from picoware.system import buttons as k
vm=ViewManager()
from picoware.applications.utilities import serial
serial._uart=vm.uart
serial._uart.uart.inject_rx(b'first')
serial.__uart_callback(serial._uart.uart)
serial._uart.uart.inject_rx(b'second')
serial.__uart_callback(serial._uart.uart)
print('Serial: burst overwrite:', 'first' not in serial.message, '; bytes rendered literally:', "b'second'" in serial.message)
serial.__callback('hello')
print('Serial: sent line reached UART:', serial._uart.uart.tx_buffer().endswith(b'hello\n'), '; local echo discarded:', serial.message=='')
serial.stop(vm)

from picoware.system.usb import USBKeyboard
from picoware.applications.usb import keyboard
key=USBKeyboard();key.init()
keyboard._usb=key;keyboard._initialized=True
before=len(key._usbdev.transfers)
for button in (k.BUTTON_UP,k.BUTTON_BACKSPACE,k.BUTTON_TAB,k.BUTTON_F1):
    vm._button=button;keyboard.run(vm)
print('USB: reports for Up/Backspace/Tab/F1:',len(key._usbdev.transfers)-before)
vm._button=k.BUTTON_CENTER;keyboard.run(vm)
print('USB: Enter does produce a HID report:',len(key._usbdev.transfers)>before)
key._wait=lambda *args:False
submitted=[]
key._usbdev.submit_xfer=lambda *args:submitted.append(args) or False
key.send_key(0,4)
print('USB: still submits after timeout:',bool(submitted),'; rejected transfer leaves pending:',not key._xfer_done)
keyboard.stop(vm)
print('USB: runtime HID remains active after app stop:',key._usbdev.active(),'; callbacks retained:',key._usbdev.xfer_cb is not None)

from picoware.applications.utilities import ssh
client=ssh.SSHClient()
client._server_version='SSH-2.0-audit'
client._client_kexinit=b'client';client._server_kexinit=b'server'
client._send_packet=lambda packet:None
client._read_ssh_packet=lambda:bytes([ssh.SSH_MSG_KEXDH_REPLY])+ssh._ssh_string(b'not-a-host-key')+ssh._ssh_string(b'Q'*32)+ssh._ssh_string(b'not-a-signature')
x25519=ssh._x25519
ssh._x25519=lambda *args:b'\x01'*32
try:
    client._do_curve25519_kex()
    print('SSH: invalid host key/signature accepted by key exchange: True (ECDH stubbed; verification is the operation under test)')
finally:
    ssh._x25519=x25519
value,offset=ssh._parse_string(struct.pack('>I',99)+b'x',0)
print('SSH: truncated string accepted beyond packet:',offset>5)
class IdentityCipher:
    def __init__(self,*args):pass
    def process(self,data):return data
cipher=ssh._AES_CTR;ssh._AES_CTR=IdentityCipher
try:
    client._cipher_c2s=client._cipher_s2c='aes128-ctr'
    client._mac_c2s='hmac-sha1';client._mac_s2c='hmac-sha2-256'
    client._derive_keys(42,b'H'*32,ssh.hashlib.sha256)
    print('SSH: asymmetric MAC mismatch, inbound key length:',len(client._mac_key_s2c),'expected 32')
finally:
    ssh._AES_CTR=cipher
class Socket:
    def __init__(self,data):self.data=data
    def recv(self,n):out,self.data=self.data[:n],self.data[n:];return out
client._sock=Socket(struct.pack('>I',1)+b'\x00')
print('SSH: invalid zero-padding packet accepted:',client._read_packet()==b'')
client._sock=None
print('Audit complete: no external network, passwords, physical UART, or host USB device used.')
