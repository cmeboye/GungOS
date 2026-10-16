"""Wi-Fi station/AP interface with bounded, cooperative connection handling."""
from utime import ticks_ms, ticks_diff, sleep
from ujson import loads
from micropython import const

WIFI_STATE_INACTIVE = const(-1)
WIFI_STATE_IDLE = const(0)
WIFI_STATE_CONNECTING = const(1)
WIFI_STATE_CONNECTED = const(2)
WIFI_STATE_ISSUE = const(3)
WIFI_STATE_TIMEOUT = const(4)


class WiFi:
    """Start connections without occupying the RP2's worker thread.

    ViewManager polls this object every frame. Standalone callers must call
    poll() while a connection is pending, or use the synchronous connect().
    """
    def __init__(self, view_manager, timeout=10):
        from picoware.system.boards import BOARD_FLIPPER_ZERO, BOARD_ID
        self._is_flipper=BOARD_ID==BOARD_FLIPPER_ZERO
        self._wifi_uart=None;self.wlan=None;self.mode=0
        self.ssid=self.password=self.error=''
        self._state=WIFI_STATE_IDLE;self._callback_connect=None
        self.connection_start_time=None;self.connection_timeout=timeout
        self._thread=None;self._current_task=None;self._thread_running=False
        self._thread_manager=getattr(view_manager,'thread_manager',None)
        if self._is_flipper:
            try:self._wifi_uart=WiFiUART(view_manager.uart,timeout*1000)
            except Exception:self.error='Wi-Fi UART unavailable.'
        else:
            from network import STA_IF,WLAN
            self.mode=STA_IF
            try:self.wlan=WLAN(STA_IF)
            except Exception:self.error='Wi-Fi interface unavailable.';self._state=WIFI_STATE_INACTIVE

    def __del__(self):
        try:
            self._callback_connect=None
            self.reset()
        except Exception:pass

    @property
    def callback_connect(self):return self._callback_connect
    @callback_connect.setter
    def callback_connect(self,value):self._callback_connect=value
    @property
    def timeout(self):return self.connection_timeout
    @timeout.setter
    def timeout(self,value):
        if value<=0:raise ValueError('Timeout must be positive')
        self.connection_timeout=value
    @property
    def state(self):
        if self._is_flipper:return self._wifi_uart.state if self._wifi_uart else WIFI_STATE_INACTIVE
        return self.poll()
    @property
    def last_error(self):return self._wifi_uart.last_error if self._is_flipper and self._wifi_uart else self.error
    @property
    def device_ip(self):
        if self._is_flipper:return self._wifi_uart.device_ip if self._wifi_uart else ''
        try:return self.wlan.ifconfig()[0] if self.wlan and self.is_connected() else ''
        except OSError:return ''
    @property
    def mac_address(self):
        if self._is_flipper:return self._wifi_uart.mac_address if self._wifi_uart else ''
        try:return ':'.join('%02x'%b for b in self.wlan.config('mac')) if self.wlan else ''
        except OSError:return ''

    def _finish(self,state,error=''):
        self._state,self.error=state,error
        self.connection_start_time=None;self._thread_running=False
        if self._callback_connect:
            try:self._callback_connect(state,error)
            except Exception:
                # An application callback must not change the radio result.
                print('Wi-Fi callback failed.')
        return state

    def poll(self):
        if self._is_flipper:return self.state
        if self.wlan is None:return WIFI_STATE_INACTIVE
        from network import AP_IF,STAT_WRONG_PASSWORD,STAT_NO_AP_FOUND,STAT_CONNECT_FAIL
        if self.mode==AP_IF:
            if self._state==WIFI_STATE_CONNECTED and not self.wlan.active():return self._finish(WIFI_STATE_IDLE,'Access point stopped.')
            return self._state
        try:
            if self._state==WIFI_STATE_CONNECTING:
                if self.wlan.isconnected():return self._finish(WIFI_STATE_CONNECTED)
                status=self.wlan.status()
                messages={STAT_WRONG_PASSWORD:'Wrong password.',STAT_NO_AP_FOUND:'No access point found.',STAT_CONNECT_FAIL:'Failed to connect.'}
                if status in messages:
                    self.wlan.disconnect()
                    return self._finish(WIFI_STATE_ISSUE,messages[status])
                if self.connection_start_time is not None and ticks_diff(ticks_ms(),self.connection_start_time)>=self.connection_timeout*1000:
                    self.wlan.disconnect()
                    return self._finish(WIFI_STATE_TIMEOUT,'Connection timed out.')
            elif self._state==WIFI_STATE_CONNECTED and not self.wlan.isconnected():
                return self._finish(WIFI_STATE_IDLE,'Connection lost.')
        except OSError:
            return self._finish(WIFI_STATE_ISSUE,'Wi-Fi status failed.')
        return self._state

    def connect_async(self,ssid,password='',sta_mode=True):
        if not isinstance(ssid,str) or not ssid or len(ssid.encode())>32:
            self.error='SSID must be 1–32 bytes.';return False
        if not isinstance(password,str):self.error='Invalid password type.';return False
        if self._is_flipper:
            return bool(self._wifi_uart and self._wifi_uart.connect_async(ssid,password,sta_mode))
        if self.wlan is None:self.error='Wi-Fi interface unavailable.';return False
        from network import STA_IF,AP_IF,WLAN
        mode=STA_IF if sta_mode else AP_IF
        if self._state==WIFI_STATE_CONNECTING:
            self.error='A connection is already in progress.';return False
        if mode==AP_IF and password and not 8<=len(password.encode())<=63:
            self.error='AP password must be 8–63 bytes, or empty for an open AP.';return False
        if mode==self.mode and ssid==self.ssid and password==self.password and self.is_connected():return True
        try:
            self.disconnect()
            if mode!=self.mode:
                self.wlan.active(False)
                self.wlan=WLAN(mode);self.mode=mode
            self.ssid,self.password=ssid,password
            self.error=''
            if mode==AP_IF:
                self.wlan.active(False)
                security=WLAN.SEC_WPA_WPA2 if password else WLAN.SEC_OPEN
                self.wlan.config(ssid=ssid,key=password,security=security)
                self.wlan.active(True)
                self._finish(WIFI_STATE_CONNECTED)
            else:
                self._state=WIFI_STATE_CONNECTING;self._thread_running=True
                self.connection_start_time=ticks_ms()
                self.wlan.active(True);self.wlan.connect(ssid,password)
                self.poll()
            return self._state in (WIFI_STATE_CONNECTING,WIFI_STATE_CONNECTED)
        except Exception:
            try:self.wlan.active(False)
            except Exception:pass
            self._finish(WIFI_STATE_ISSUE,'Failed to start Wi-Fi connection.')
            return False

    def connect(self,ssid,password='',sta_mode=True):
        if not self.connect_async(ssid,password,sta_mode):return False
        if self._is_flipper:return self._wifi_uart.is_connected()
        while self.poll()==WIFI_STATE_CONNECTING:sleep(.05)
        return self._state==WIFI_STATE_CONNECTED

    def disconnect(self):
        if self._is_flipper:
            if self._wifi_uart:self._wifi_uart.disconnect()
            return
        self._thread_running=False;self.connection_start_time=None
        if self.wlan:
            from network import AP_IF
            if self.mode==AP_IF:self.wlan.active(False)
            else:self.wlan.disconnect()
        self._state=WIFI_STATE_IDLE;self.error=''

    def is_connected(self):
        if self._is_flipper:return bool(self._wifi_uart and self._wifi_uart.is_connected())
        self.poll()
        return self._state==WIFI_STATE_CONNECTED

    def scan(self):
        if self._is_flipper:
            return [(ssid.encode(),0,0,0,0,0) for ssid in (self._wifi_uart.scan() if self._wifi_uart else [])]
        if self.wlan is None:return []
        from network import AP_IF
        if self.mode==AP_IF:raise ValueError('Stop the access point before scanning.')
        self.wlan.active(True)
        return self.wlan.scan()

    def status(self):return self.state

    def reset(self):
        if self._is_flipper:
            if self._wifi_uart:self._wifi_uart.reset()
            return
        self.disconnect()
        if self.wlan:self.wlan.active(False)
        self.ssid=self.password=''

class WiFiUART:
    """Class to manage WiFi functionality on a MicroPython device.
        
    Attributes:
        uart: The UART object for communication with the WiFi module.
        error (str): The last error message encountered during WiFi operations.
        timeout_ms (int): The timeout for UART receiving
    """
    def __init__(self, uart = None, timeout_ms: int = 5000):
        """Initialize the WiFiUART instance.

        Args:
            uart: The UART object for communication with the WiFi module.
            timeout_ms (int): The timeout for UART receiving in milliseconds. Defaults to 5000.
        """
        self.uart = None
        if uart is None:
            from picoware.system.uart import UART
            self.uart = UART(timeout=timeout_ms)
        else:
            self.uart = uart
        if self.uart and not self.ping():
            print("FlipperHTTP board not connected...")
            self.uart = None
        self.error = ""
        self.timeout_ms = timeout_ms

    @property
    def device_ip(self):
        """Get the current device IP address."""
        if not self.uart:
            return ""
        return self.__send_and_wait("[IP/ADDRESS]")

    @property
    def last_error(self):
        """Get the last error message encountered during WiFi operations."""
        return self.error

    @property
    def mac_address(self):
        """Get the current device MAC address."""
        return ""

    @property
    def state(self):
        """Get the current WiFi state."""
        _status = self.__send_and_wait("[WIFI/STATUS]")
        if "true" in _status:
            return WIFI_STATE_CONNECTED
        return WIFI_STATE_IDLE

    def __send_and_wait(self, command: str) -> str:
        """Send a command to the UART and wait for a response.

        Args:
            command (str): The command to send.

        Returns:
            str: The response from the UART.
        """
        if not self.uart:
            return ""
        self.uart.println(command)
        while self.uart.is_sending:
            pass
        data = self.uart.read_line()
        if not data:
            return "[ERROR] No data returned"
        if "[ERROR]" in data:
            self.error = data
        return data

    def connect(self, ssid: str, password: str = "", sta_mode: bool = True) -> bool:
        """Connect to a Wi-Fi network.

        Args:
            ssid (str): SSID of the Wi-Fi network.
            password (str): Password for the Wi-Fi network. Defaults to "".
            sta_mode (bool): True for station mode (STA_IF), False for access point mode (AP_IF). Defaults to True.

        Returns:
            bool: True if the connection succeeded, False otherwise.
        """
        if not self.uart:
            return False
        if sta_mode:
            response = self.__send_and_wait("[WIFI/SAVE]{\"ssid\":\"%s\",\"password\":\"%s\"}" % (ssid, password))
            return "[ERROR]" not in response
        response = self.__send_and_wait("[WIFI/AP]{\"ssid\":\"%s\"}" % ssid)
        return "[AP/CONNECTED]" in response
    
    def connect_async(self, ssid: str, password: str = "", sta_mode: bool = True) -> bool:
        """Initiate an asynchronous connection to a Wi-Fi network.

        Args:
            ssid (str): SSID of the Wi-Fi network.
            password (str): Password for the Wi-Fi network. Defaults to "".
            sta_mode (bool): True for station mode (STA_IF), False for access point mode (AP_IF). Defaults to True.

        Returns:
            bool: True if the command to initiate the connection was sent successfully, False otherwise.
        """
        if not self.uart:
            return False
        # for now, this is mainly for Flipper, so leave as synch
        return self.connect(ssid, password, sta_mode)

    def disconnect(self) -> None:
        """Disconnect from the current Wi-Fi network.

        Returns:
            None
        """
        if not self.uart:
            return
        self.uart.println("[WIFI/DISCONNECT]")

    def is_connected(self) -> bool:
        """Check if the device is currently connected to a Wi-Fi network.

        Returns:
            bool: True if connected, False otherwise.
        """
        return self.state == WIFI_STATE_CONNECTED
    
    def ping(self) -> bool:
        """Check for pong response"""
        return "PONG" in self.__send_and_wait("[PING]")

    def scan(self) -> list:
        """Scan for available Wi-Fi networks."""
        if not "[GET/SUCCESS]" in self.__send_and_wait("[WIFI/SCAN]"):
            return []
        response = self.uart.read_line()
        if response:
            end = response.find("]}") + 2
            _res = response[:end]
            try:
                d = loads(_res)
                return d["networks"]
            except Exception as e:
                print(f"Failed to load response: {e}")
        return []

    def status(self) -> int:
        """Get the current Wi-Fi status.

        Returns:
            int: The current Wi-Fi status as one of the WIFI_STATE_* constants.
        """
        return self.state

    def reset(self) -> None:
        """Reset the Wi-Fi module.

        Returns:
            None
        """
        self.error = ""
    