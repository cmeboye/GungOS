"""WiFi Server - Host a web server over WiFi."""

from micropython import const
from utime import ticks_ms, ticks_diff

# menu states
STATE_MENU_MAIN = const(0)
STATE_MENU_EDIT = const(1)
STATE_RUNNING = const(2)
STATE_MENU_ADD_PAGE = const(3)
STATE_MENU_VIEW_PAGES = const(4)
STATE_MENU_SETTINGS = const(5)
STATE_MENU_EDIT_PAGE = const(6)  # editing a specific page
STATE_SETTINGS_MODE = const(7)
STATE_SETTINGS_SSID = const(8)
STATE_SETTINGS_PASSWORD = const(9)

# page states
STATE_PAGE_MENU = const(-1)  # showing page menu
STATE_PAGE_URL = const(0)
STATE_PAGE_HTML = const(1)
STATE_PAGE_METHOD = const(2)
STATE_PAGE_SCRIPT = const(3)
STATE_PAGE_DELETE = const(4)

# global objects
server = None
box = None
menu = None

# global variables
menu_state = STATE_MENU_MAIN
edit_page_state = STATE_PAGE_MENU
add_page_state = STATE_PAGE_MENU
view_page_state = STATE_PAGE_MENU
current_page_info = {}
current_page_index = -1  # index of the page being edited
just_started_editing = True
save_requested = False
settings_info = {}  # for storing settings being edited

# locations
SERVER_FOLDER = "picoware/wifi/server"
SERVER_INFO = "picoware/wifi/server/server_info.json"
# The access point password lives in internal flash, not in SERVER_INFO.
AP_PASSWORD_SECRET = "ap_password"

# json example
# {
#     "pages": [
#         {"url": "/custom", "method": "GET", "html": "page.html", "script": "page.py"},
#         {"url": "/submit", "method": "POST", "html": "submit.html", "script": "submit.py"},
#         {"url": "/data", "method": "GET", "html": "picoware/wifi/server/data.html", "script": "picoware/wifi/server/data.py"}
#     ]
# }


def _read_info(storage):
    if not storage.exists(SERVER_INFO):return {}
    from ujson import loads
    value=loads(storage.read(SERVER_INFO))
    if not isinstance(value,dict):raise ValueError('Server settings are unreadable.')
    return value


def _write_info(vm,value):
    storage=vm.storage;path=SERVER_INFO;temporary=path+'.tmp';backup=path+'.bak'
    try:
        if storage.exists(backup):raise OSError('Recover the existing server settings backup first.')
        if not storage.serialize(value,temporary) or storage.deserialize(temporary)!=value:raise OSError('SD write failed.')
        existed=storage.exists(path)
        if existed and not storage.rename(path,backup):raise OSError('Cannot back up settings.')
        if not storage.rename(temporary,path):
            if existed:storage.rename(backup,path)
            raise OSError('Cannot install settings.')
        if existed:storage.remove(backup)
        return True
    except Exception:
        vm.alert('Server settings could not be saved. Check the SD card.')
        return False


class Server:
    """Simple HTTP Server for MicroPython WiFi Devices"""

    def __init__(
        self,
        view_manager,
        append_question_mark=True,
    ):
        """Initialize the server.

        Args:
            view_manager (ViewManager): The view manager instance for display and storage access.
            append_question_mark (bool): Whether to append '?' to URLs. Defaults to True.
        """
        self.view_manager = view_manager
        self.server = None
        self.routes = {}  # Routing table as a dictionary
        self.http_type = "HTTP/1.1"
        self.append_question_mark = append_question_mark
        self.client = None
        self.last_response = None
        self._buffer=bytearray();self._response=None;self._sent=0;self._client_started=None;self._owns_ap=False

    def __del__(self):
        """Close the server and release resources."""
        self.close()
        self.last_response = None
        self.routes = None

    @property
    def is_running(self) -> bool:
        """Check if the server is running.

        Returns:
            bool: True if the server socket is open, False otherwise.
        """
        return self.server is not None

    def close(self, reason=None):
        """Close the server and client connections.

        Args:
            reason (str or None): Log message for the close reason. Defaults to None.
        """
        if reason:
            self.view_manager.log(reason)
        self._close_client()
        if self.server:
            self.server.close()
            del self.server
            self.server = None

        if self._owns_ap:
            self.view_manager.wifi.disconnect();self._owns_ap=False
        self.view_manager.log("Server closed.")

    def start(self, port=80) -> bool:
        """Start the server on the specified port.

        Args:
            port (int): The port to listen on. Defaults to 80.

        Returns:
            bool: True if the server started, False on failure.
        """
        try:
            import socket

            address = socket.getaddrinfo("0.0.0.0", port)[0][-1]
            self.server = socket.socket()
            self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server.bind(address)
            self.server.setblocking(False)
            self.server.listen(1)  # One active client; bounded memory and work per frame.

            # add routes from json file
            from picoware.system.storage import Storage

            storage: Storage = self.view_manager.storage
            server_info=_read_info(storage) if storage.exists(SERVER_INFO) else {}
            if not isinstance(server_info,dict):server_info={}
            if "pages" in server_info:
                for page in server_info["pages"]:
                    url = page.get("url", "/")
                    method = page.get("method", "GET").upper()
                    html_file = page.get("html", None)
                    script_file = page.get("script", None)

                    def make_handler(html_file, script_file):
                        """Create a request handler for a page.

                        Args:
                            html_file (str or None): HTML file path, if any.
                            script_file (str or None): Script file path, if any.

                        Returns:
                            callable: The request handler function.
                        """
                        def handler(data=None):
                            """Handle a request and build the response.

                            Args:
                                data (dict or None): POST data for the request. Defaults to None.

                            Returns:
                                str: The response content.
                            """
                            response = ""
                            # Execute script if available
                            if script_file:
                                try:
                                    if storage.size(script_file)>32768:raise ValueError('Script exceeds 32 KiB')
                                    script_code = storage.read(script_file)
                                    # Define a local scope for the script execution
                                    local_scope = {}
                                    exec(script_code, local_scope, local_scope)
                                    if "handle_request" in local_scope:
                                        response = local_scope["handle_request"](data)
                                except Exception as e:
                                    self.view_manager.log(
                                        f"Error executing script {script_file}: {e}", 2
                                    )
                                    raise

                            # Load HTML file if available
                            if html_file:
                                try:
                                    if storage.size(html_file)>32768:raise ValueError('Page exceeds 32 KiB')
                                    html_content = storage.read(html_file)
                                    response += html_content
                                except Exception as e:
                                    self.view_manager.log(
                                        f"Error loading HTML file {html_file}: {e}", 2
                                    )
                                    raise

                            return response

                        return handler

                    handler = make_handler(html_file, script_file)
                    self.add_route(url, handler, method)
            return True
        except Exception as e:
            self.view_manager.log(f"Failed to start server: {e}", 2)
            self.close()
            return False

    def add_route(self, path, handler, method="GET"):
        """Register a new route with its handler.

        Args:
            path (str): URL path (e.g. "/custom").
            handler (callable): Function to handle the route, returning the HTML response as a string.
            method (str): HTTP method (e.g. "GET", "POST"). Defaults to "GET".
        """
        normalized_path = path.rstrip("/") if path != "/" else path
        method = method.upper()

        if normalized_path not in self.routes:
            self.routes[normalized_path] = {}

        self.routes[normalized_path][method] = {
            "handler": handler,
        }

    def webpage(self):
        """Generate a basic HTML page.

        Returns:
            str: The generated HTML page.
        """
        html = """ 
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <title>Server</title>
            </head>
            <body>
                <h1>Server</h1>
                <p>Welcome to the Server.</p>
            </body>
            </html>
        """
        return html

    def _close_client(self):
        if self.client is not None:
            try:self.client.close()
            except OSError:pass
        self.client=None;self._buffer=bytearray();self._response=None;self._sent=0;self._client_started=None

    def _reply(self,status,content):
        reasons={200:'OK',204:'No Content',400:'Bad Request',404:'Not Found',405:'Method Not Allowed',408:'Request Timeout',413:'Content Too Large',431:'Request Header Fields Too Large',500:'Internal Server Error',501:'Not Implemented'}
        raw=content if isinstance(content,bytes) else str(content).encode()
        if len(raw)>32768:status=500;raw=b'Response exceeds server memory limit.'
        self._response=('HTTP/1.1 %d %s\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: %d\r\nConnection: close\r\n\r\n'%(status,reasons.get(status,'Response'),len(raw))).encode()+raw
        self._sent=0;self.last_response=self._response[:256]

    def _dispatch(self,method,path,headers,body):
        from json import loads
        path=path.split('?')[0];path=path.rstrip('/') if path!='/' else path
        methods=self.routes.get(path)
        if methods is None:
            self._reply(200,self.webpage()) if path=='/' and method=='GET' else self._reply(405 if path=='/' else 404,'Request not available.')
            return
        if method not in methods or method not in ('GET','POST'):self._reply(405,'Method not allowed.');return
        handler=methods[method]['handler']
        try:
            if method=='POST':
                try:
                    if 'application/json' in headers.get('content-type',''):value=loads(body.decode())
                    else:
                        value={}
                        for pair in body.split(b'&'):
                            if b'=' in pair:
                                key,part=pair.split(b'=',1);value[self._form_part(key)]=self._form_part(part)
                except (ValueError,UnicodeError):self._reply(400,'Malformed request body.');return
                response=handler(value)
            else:response=handler()
            status=200
            if isinstance(response,tuple):
                response,status=response;status=int(str(status).split()[0])
            self._reply(status,response)
        except Exception:
            self.view_manager.log('HTTP route handler failed.',2);self._reply(500,'Route handler failed.')

    def _form_part(self,raw):
        out=bytearray();i=0
        while i<len(raw):
            if raw[i]==37:
                if i+2>=len(raw):raise ValueError('Incomplete escape')
                out.append(int(raw[i+1:i+3],16));i+=3
            else:out.append(32 if raw[i]==43 else raw[i]);i+=1
        return bytes(out).decode()

    def _request_ready(self):
        end=self._buffer.find(b'\r\n\r\n')
        if end<0:
            if len(self._buffer)>4096:self._reply(431,'Headers exceed 4096 bytes.')
            return
        if end>4096:self._reply(431,'Headers exceed 4096 bytes.');return
        try:
            lines=bytes(self._buffer[:end]).decode().split('\r\n')
            method,path,protocol=lines[0].split()
            if protocol not in ('HTTP/1.0','HTTP/1.1') or not path.startswith('/'):raise ValueError('Invalid request line')
            headers={}
            for line in lines[1:]:
                key,value=line.split(':',1);key=key.strip().lower()
                if key=='content-length' and key in headers:raise ValueError('Duplicate length')
                headers[key]=value.strip()
            if 'transfer-encoding' in headers:self._reply(501,'Chunked request bodies are unsupported.');return
            length=headers.get('content-length','0')
            if not length.isdigit():raise ValueError('Invalid length')
            length=int(length)
            if length>4096:self._reply(413,'Request body exceeds 4096 bytes.');return
            if len(self._buffer)-end-4<length:return
            body=bytes(self._buffer[end+4:end+4+length])
            self._dispatch(method,path,headers,body)
        except (ValueError,UnicodeError):self._reply(400,'Malformed request.')

    def run(self):
        from picoware.system.buttons import BUTTON_ESCAPE
        global menu_state
        if self.view_manager.button==BUTTON_ESCAPE:
            self.close();menu_state=STATE_MENU_MAIN;globals()['__menu_start'](self.view_manager);return
        if self.server is None:return
        if self.client is None:
            try:
                self.client,_=self.server.accept();self.client.setblocking(False)
                self._client_started=ticks_ms();self._buffer=bytearray()
            except OSError:return
        if ticks_diff(ticks_ms(),self._client_started)>=5000:
            if self._response is None:self._reply(408,'Request timed out.');self._client_started=ticks_ms()
            else:self._close_client();return
        try:
            if self._response is not None:
                sent=self.client.send(self._response[self._sent:self._sent+1024])
                if not sent:self._close_client();return
                self._sent+=sent
                if self._sent>=len(self._response):self._close_client()
                return
            packet=self.client.recv(1024)
            if not packet:self._close_client();return
            self._buffer.extend(packet)
            self._request_ready()
        except OSError as exc:
            if not exc.args or exc.args[0] not in (11,35,10035):self._close_client()
        except Exception:
            self._close_client();self.view_manager.log('HTTP request failed.',2)


def __add_page(view_manager) -> bool:
    """Add a new page to the server.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.

    Returns:
        bool: True if editing continues or the page was saved, False otherwise.
    """
    keyboard = view_manager.keyboard

    if keyboard is None:
        print("No keyboard available")
        return False

    global just_started_editing, save_requested, menu_state

    if just_started_editing:
        just_started_editing = False
        keyboard.set_save_callback(__add_page_callback)
        keyboard.response = ""
        view_manager.input_manager.reset()
        keyboard.run(force=True)
        return True

    if save_requested:
        save_requested = False
        just_started_editing = True
        url = keyboard.response
        # save new page with default values
        storage = view_manager.storage
        try:
            server_info: dict = _read_info(storage)
            if "pages" not in server_info:
                server_info["pages"] = []
            new_page = {
                "url": url if url.startswith("/") else "/" + url,
                "method": "GET",
                "html": "",
                "script": "",
            }
            server_info["pages"].append(new_page)
            if not _write_info(view_manager,server_info):
                just_started_editing=False
                return True
        except Exception as e:
            view_manager.log("Error saving server info:" + str(e), 2)
            view_manager.alert("Server page could not be saved. Check the SD card.")
            just_started_editing=False
            return True
        #
        keyboard.reset()
        # Go back to edit menu
        menu_state = STATE_MENU_EDIT
        __menu_start(view_manager)
        return True

    if not keyboard.run():
        just_started_editing = True
        return False
    return True


def __add_page_callback(result: str) -> None:
    """Callback for when a page field is saved during add page.

    Args:
        result (str): The saved field value.
    """
    global save_requested, just_started_editing

    if just_started_editing:
        return

    save_requested = True


def __box_start(view_manager) -> None:
    """Start the textbox for server output.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.
    """
    from picoware.gui.textbox import TextBox

    global box

    if box is not None:
        del box
        box = None

    draw = view_manager.draw
    fg = view_manager.foreground_color
    bg = view_manager.background_color
    height = draw.size.y

    top = int(height * 0.0625)

    box = TextBox(
        draw,
        top + (top // 2),
        height - (top + (top // 2)),
        fg,
        bg,
    )

    if menu_state == STATE_RUNNING:
        box.set_text("Server is running...\n")
    elif menu_state == STATE_MENU_VIEW_PAGES:
        box.set_text("")


def __callback_edit_save(result: str) -> None:
    """Callback for when a page field is saved.

    Args:
        result (str): The saved field value.
    """
    global current_page_info, just_started_editing

    if just_started_editing:
        return

    global edit_page_state, add_page_state, save_requested

    if edit_page_state == STATE_PAGE_URL:
        current_page_info["url"] = result
    elif edit_page_state == STATE_PAGE_HTML:
        current_page_info["html"] = result
    elif edit_page_state == STATE_PAGE_METHOD:
        current_page_info["method"] = result
    elif edit_page_state == STATE_PAGE_SCRIPT:
        current_page_info["script"] = result
    elif add_page_state == STATE_PAGE_URL:
        current_page_info["url"] = result
    elif add_page_state == STATE_PAGE_HTML:
        current_page_info["html"] = result
    elif add_page_state == STATE_PAGE_METHOD:
        current_page_info["method"] = result
    elif add_page_state == STATE_PAGE_SCRIPT:
        current_page_info["script"] = result

    save_requested = True


def __edit_page(
    view_manager,
    index: int,
    key: str,
    return_status: bool = True,
    return_state: int = STATE_PAGE_MENU,
) -> bool:
    """Edit a page field given its index.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.
        index (int): The page index to edit.
        key (str): The field key to edit.
        return_status (bool): Whether to return to the edit page menu after saving. Defaults to True.
        return_state (int): The state to return to after saving. Defaults to STATE_PAGE_MENU.

    Returns:
        bool: True if editing continues, False otherwise.
    """
    if index < 0:
        return False

    global current_page_info, just_started_editing, save_requested, edit_page_state, add_page_state, menu_state

    if current_page_info == {} or "url" not in current_page_info:
        current_page_info = __get_page_info_index(view_manager, index)

    keyboard = view_manager.keyboard

    if keyboard is None:
        print("No keyboard available")
        return False

    if just_started_editing:
        just_started_editing = False
        keyboard.set_save_callback(__callback_edit_save)
        keyboard.response = current_page_info.get(key, "")
        view_manager.input_manager.reset()
        keyboard.run(force=True)
        return True

    if save_requested:
        save_requested = False
        just_started_editing = True
        # Get the updated value from keyboard
        current_page_info[key] = keyboard.response
        storage = view_manager.storage
        try:
            server_info: dict = _read_info(storage)
            if "pages" in server_info:
                if 0 <= index < len(server_info["pages"]):
                    server_info["pages"][index] = {
                        "url": current_page_info.get("url", "/"),
                        "method": current_page_info.get("method", "GET"),
                        "html": current_page_info.get("html", ""),
                        "script": current_page_info.get("script", ""),
                    }
                    if not _write_info(view_manager,server_info):
                        just_started_editing=False
                        return True
        except Exception as e:
            view_manager.log("Error saving server info:" + str(e), 2)
            view_manager.alert("Server page could not be saved. Check the SD card.")
            just_started_editing=False
            return True
        #
        keyboard.reset()
        if return_status:
            edit_page_state = return_state
            add_page_state = return_state
            # Stay in edit page menu to allow editing other fields
            menu_state = STATE_MENU_EDIT_PAGE
            __menu_start(view_manager)
            return True

    if not keyboard.run():
        just_started_editing = True
        return False
    return True


def __get_current_pages(view_manager) -> list[str]:
    """Get the list of current pages from the server info file.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.

    Returns:
        list[str]: The page URLs.
    """
    from picoware.system.storage import Storage

    storage: Storage = view_manager.storage
    pages = []

    try:
        _current_stats: dict = _read_info(storage)
        if "pages" in _current_stats:
            for page in _current_stats["pages"]:
                pages.append(page["url"])
    except Exception as e:
        view_manager.log("Error reading server info:" + str(e), 2)

    return pages


def __get_page_info_index(view_manager, index: int) -> dict:
    """Get the page info for a given index from the server info file.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.
        index (int): The page index.

    Returns:
        dict: The page info.
    """
    from picoware.system.storage import Storage

    storage: Storage = view_manager.storage
    page_info = {}

    try:
        _current_stats: dict = _read_info(storage)
        if "pages" in _current_stats:
            _page_amount = len(_current_stats["pages"])
            if 0 <= index < _page_amount:
                page_info = _current_stats["pages"][index]
                page_info["count"] = _page_amount
    except Exception as e:
        view_manager.log("Error reading server info:" + str(e), 2)

    return page_info


def __get_setting(view_manager, key: str, default: str = "") -> str:
    """Get a setting from the server info file.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.
        key (str): The setting key.
        default (str): The value returned if the key is missing. Defaults to "".

    Returns:
        str: The setting value.
    """
    from picoware.system.storage import Storage

    storage: Storage = view_manager.storage
    value = default

    try:
        server_info: dict = _read_info(storage)
        if "settings" in server_info:
            value = server_info["settings"].get(key, default)
    except Exception as e:
        view_manager.log("Error reading server setting:" + str(e), 2)

    if key == "password":
        from picoware.system import secrets
        stored = secrets.get(AP_PASSWORD_SECRET, None)
        if stored is not None:
            return stored
        # Older SD cards hold the access point password in plain text: move it to flash.
        if value and __save_setting(view_manager, key, value):
            return value
    return value


def __save_setting(view_manager, key: str, value: str) -> bool:
    """Save a setting to the server info file.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.
        key (str): The setting key.
        value (str): The setting value.
    """
    from picoware.system.storage import Storage

    storage: Storage = view_manager.storage

    try:
        server_info: dict = _read_info(storage)
        if "settings" not in server_info:
            server_info["settings"] = {}
        if key == "password":
            from picoware.system import secrets
            if not secrets.update({AP_PASSWORD_SECRET: value}):
                view_manager.alert("The access point password could not be saved.")
                return False
            if "password" not in server_info["settings"]:
                return True
            server_info["settings"].pop("password")
        else:
            server_info["settings"][key] = value
        return _write_info(view_manager,server_info)
    except Exception as e:
        view_manager.log("Error saving server setting:" + str(e), 2)
        view_manager.alert("Server settings are unreadable or could not be saved. Check the SD card.")
        return False


def __delete_page(view_manager, index: int) -> None:
    """Delete a page from the server info file.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.
        index (int): The page index to delete.
    """
    global menu_state, current_page_index, current_page_info

    from picoware.system.storage import Storage

    storage: Storage = view_manager.storage

    try:
        server_info: dict = _read_info(storage)
        if "pages" in server_info:
            if 0 <= index < len(server_info["pages"]):
                del server_info["pages"][index]
                if not _write_info(view_manager,server_info):return
    except Exception as e:
        view_manager.log("Error deleting page:" + str(e), 2)

    # Go back to view pages
    menu_state = STATE_MENU_VIEW_PAGES
    current_page_index = -1
    current_page_info = {}
    __menu_start(view_manager)


def __toggle_mode(view_manager, selection: int) -> None:
    """Toggle between AP and STA mode.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.
        selection (int): 0 for AP mode, otherwise STA mode.
    """
    global menu_state

    mode = "AP" if selection == 0 else "STA"
    if not __save_setting(view_manager, "mode", mode):return

    # Refresh the menu to show updated selection
    __menu_start(view_manager)


def __edit_setting(view_manager, setting_key: str) -> bool:
    """Edit a setting using the keyboard.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.
        setting_key (str): The setting key to edit.

    Returns:
        bool: True if editing continues or the setting was saved, False otherwise.
    """
    global just_started_editing, save_requested, menu_state, settings_info

    keyboard = view_manager.keyboard

    if keyboard is None:
        print("No keyboard available")
        return False

    if just_started_editing:
        just_started_editing = False
        current_value = __get_setting(view_manager, setting_key, "")
        settings_info = {"key": setting_key, "value": current_value}
        keyboard.secret = setting_key == "password"
        keyboard.set_save_callback(__setting_callback)
        keyboard.response = current_value
        view_manager.input_manager.reset()
        keyboard.run(force=True)
        return True

    if save_requested:
        save_requested = False
        just_started_editing = True
        new_value = keyboard.response
        if not __save_setting(view_manager,setting_key,new_value):
            just_started_editing=False
            return True
        keyboard.reset()
        settings_info = {}
        menu_state = STATE_MENU_SETTINGS
        menu.draw()
        return True

    if not keyboard.run():
        just_started_editing = True
        return False
    return True


def __setting_callback(result: str) -> None:
    """Callback for when a setting is saved.

    Args:
        result (str): The saved setting value.
    """
    global save_requested, just_started_editing

    if just_started_editing:
        return

    save_requested = True


def __menu_run(view_manager) -> None:
    """Run the server.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.
    """

    from picoware.system.buttons import (
        BUTTON_ESCAPE,
        BUTTON_UP,
        BUTTON_DOWN,
        BUTTON_LEFT,
        BUTTON_CENTER,
        BUTTON_RIGHT,
    )

    button = view_manager.button

    global menu_state, edit_page_state, current_page_index, current_page_info
    global just_started_editing, save_requested

    # Route every key to the active server before interpreting editor menus.
    if menu_state == STATE_RUNNING:
        if server is not None:server.run()
        return

    if menu is None:
        __menu_start(view_manager)

    if button == BUTTON_ESCAPE:
        view_manager.keyboard.reset()
        just_started_editing=True;save_requested=False
        if menu_state == STATE_MENU_MAIN:
            view_manager.back()
        elif menu_state in (STATE_RUNNING, STATE_MENU_EDIT):
            menu_state = STATE_MENU_MAIN
            __menu_start(view_manager)
        elif menu_state == STATE_MENU_ADD_PAGE:
            menu_state = STATE_MENU_EDIT
            __menu_start(view_manager)
        elif menu_state == STATE_MENU_VIEW_PAGES:
            menu_state = STATE_MENU_EDIT
            __menu_start(view_manager)
        elif menu_state == STATE_MENU_EDIT_PAGE:
            # Go back to view pages
            menu_state = STATE_MENU_VIEW_PAGES
            edit_page_state = STATE_PAGE_MENU
            current_page_index = -1
            current_page_info = {}
            __menu_start(view_manager)
        elif menu_state == STATE_MENU_SETTINGS:
            menu_state = STATE_MENU_EDIT
            __menu_start(view_manager)
        elif menu_state in (
            STATE_SETTINGS_MODE,
            STATE_SETTINGS_SSID,
            STATE_SETTINGS_PASSWORD,
        ):
            menu_state = STATE_MENU_SETTINGS
            __menu_start(view_manager)

    elif button in (BUTTON_UP, BUTTON_LEFT):
        menu.scroll_up()
    elif button in (BUTTON_DOWN, BUTTON_RIGHT):
        menu.scroll_down()
    elif button == BUTTON_CENTER:
        selection = menu.selected_index

        if menu_state == STATE_MENU_MAIN:
            if selection == 0:  # Start
                if __server_start(view_manager):
                    menu_state = STATE_RUNNING
                else:
                    menu_state = STATE_MENU_MAIN
                    __menu_start(view_manager)
            elif selection == 1:  # Edit
                menu_state = STATE_MENU_EDIT
                __menu_start(view_manager)
        elif menu_state == STATE_MENU_EDIT:
            if selection == 0:  # Add Page
                menu_state = STATE_MENU_ADD_PAGE
                __menu_start(view_manager)
            elif selection == 1:  # View Pages
                menu_state = STATE_MENU_VIEW_PAGES
                __menu_start(view_manager)
            elif selection == 2:  # Settings
                menu_state = STATE_MENU_SETTINGS
                __menu_start(view_manager)
        elif menu_state == STATE_MENU_VIEW_PAGES:
            # User selected a page to edit
            pages = __get_current_pages(view_manager)
            if pages and selection < len(pages):
                current_page_index = selection
                current_page_info = __get_page_info_index(view_manager, selection)
                menu_state = STATE_MENU_EDIT_PAGE
                edit_page_state = STATE_PAGE_MENU
                __menu_start(view_manager)
            # If no pages exist, do nothing (user clicked on "(No pages)")
        elif menu_state == STATE_MENU_EDIT_PAGE:
            # User selected which field to edit
            if selection == 0:  # URL
                edit_page_state = STATE_PAGE_URL
            elif selection == 1:  # HTML
                edit_page_state = STATE_PAGE_HTML
            elif selection == 2:  # Method
                edit_page_state = STATE_PAGE_METHOD
            elif selection == 3:  # Script
                edit_page_state = STATE_PAGE_SCRIPT
            elif selection == 4:  # Delete
                __delete_page(view_manager, current_page_index)
                return
        elif menu_state == STATE_MENU_SETTINGS:
            if selection == 0:  # Mode
                menu_state = STATE_SETTINGS_MODE
                __menu_start(view_manager)
            elif selection == 1:  # SSID
                menu_state = STATE_SETTINGS_SSID
            elif selection == 2:  # Password
                menu_state = STATE_SETTINGS_PASSWORD
        elif menu_state == STATE_SETTINGS_MODE:
            # Toggle between AP and STA
            __toggle_mode(view_manager, selection)

    # Handle keyboard states
    if menu_state == STATE_RUNNING:
        if server is not None:
            if server.is_running:
                server.run()
    elif menu_state == STATE_MENU_ADD_PAGE:
        if not __add_page(view_manager):
            view_manager.keyboard.reset()
            menu_state = STATE_MENU_EDIT
            __menu_start(view_manager)
    elif menu_state == STATE_MENU_EDIT_PAGE and edit_page_state != STATE_PAGE_MENU:
        state_map = {
            STATE_PAGE_URL: "url",
            STATE_PAGE_HTML: "html",
            STATE_PAGE_METHOD: "method",
            STATE_PAGE_SCRIPT: "script",
        }
        if not __edit_page(
            view_manager,
            current_page_index,
            state_map.get(edit_page_state, "url"),
            True,
            STATE_PAGE_MENU,
        ):
            view_manager.keyboard.reset()
            edit_page_state = STATE_PAGE_MENU
            __menu_start(view_manager)
    elif menu_state == STATE_SETTINGS_SSID:
        if not __edit_setting(view_manager, "ssid"):
            view_manager.keyboard.reset()
            menu_state = STATE_MENU_SETTINGS
            __menu_start(view_manager)
    elif menu_state == STATE_SETTINGS_PASSWORD:
        if not __edit_setting(view_manager, "password"):
            view_manager.keyboard.reset()
            menu_state = STATE_MENU_SETTINGS
            __menu_start(view_manager)


def __menu_start(view_manager) -> None:
    """Show a menu to select from options.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.
    """

    from picoware.gui.menu import Menu

    global menu

    if menu is not None:
        del menu
        menu = None

    draw = view_manager.draw
    draw.clear()
    title = ""
    options = []
    if menu_state == STATE_MENU_MAIN:
        title = "Server"
        options = ["Start", "Edit"]
    elif menu_state == STATE_MENU_EDIT:
        title = "Edit"
        options = ["Add Page", "View Pages", "Settings"]
    elif menu_state == STATE_MENU_VIEW_PAGES:
        title = "View Pages"
        options = __get_current_pages(view_manager)
        if not options:
            options = ["(No pages)"]
    elif menu_state == STATE_MENU_EDIT_PAGE:
        title = "Edit Page"
        options = [
            f"URL: {current_page_info.get('url', '/')}",
            f"HTML: {current_page_info.get('html', '')}",
            f"Method: {current_page_info.get('method', 'GET')}",
            f"Script: {current_page_info.get('script', '')}",
            "Delete Page",
        ]
    elif menu_state == STATE_MENU_SETTINGS:
        title = "Settings"
        options = ["Mode", "SSID", "Password"]
    elif menu_state == STATE_SETTINGS_MODE:
        title = "Mode"
        # Get current mode from settings
        current_mode = __get_setting(view_manager, "mode", "STA")
        options = [
            f"{'[X]' if current_mode == 'AP' else '[ ]'} AP (Access Point)",
            f"{'[X]' if current_mode == 'STA' else '[ ]'} STA (Station)",
        ]
    fg = view_manager.foreground_color
    bg = view_manager.background_color
    sel = view_manager.selected_color
    menu = Menu(
        draw,
        title,
        0,
        draw.size.y,
        fg,
        bg,
        sel,
        fg,
        2,
    )
    for option in options:
        menu.add_item(option)

    menu.draw()
    view_manager.input_manager.reset()


def __server_start(view_manager) -> bool:
    """Start the server app.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.

    Returns:
        bool: True if the server started, False otherwise.
    """

    global box

    if box is not None:
        del box
        box = None

    mode=__get_setting(view_manager,'mode','STA')
    if mode=='AP':
        name=__get_setting(view_manager,'ssid','GungOS') or 'GungOS'
        key=__get_setting(view_manager,'password','')
        if not view_manager.wifi.connect_async(name,key,sta_mode=False):
            view_manager.alert(view_manager.wifi.error);return False
        server._owns_ap=True
    elif not view_manager.wifi.is_connected():
        from picoware.applications.wifi.utils import connect_to_saved_wifi
        connect_to_saved_wifi(view_manager)
        view_manager.alert('Wi-Fi is not connected. Connect, then choose Start again.')
        return False
    if server.start():
        from picoware.system.vector import Vector

        bg = view_manager.background_color
        fg = view_manager.foreground_color

        draw = view_manager.draw
        draw.fill_screen(bg)
        size = draw.size
        msg = f"Server started at http://{view_manager.wifi.device_ip}"
        display_x = (size.x - len(msg) * draw.font_size.x) // 2
        draw.text(
            Vector(display_x, int(size.y * 0.0625)),
            msg,
            fg,
        )
        draw.swap()

        __box_start(view_manager)

        return True

    view_manager.alert("Server could not start. Check settings and port 80.")
    return False


def start(view_manager) -> bool:
    """Start the app and begin serving.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.

    Returns:
        bool: True if the app started, False on failure.
    """

    # if not a wifi device, return
    if not view_manager.has_wifi:
        view_manager.alert("WiFi not available...", False)
        return False

    # if no sd card, return
    if not view_manager.has_sd_card:
        view_manager.alert("Server app requires an SD card")
        return False

    # create server folder
    view_manager.storage.mkdir("picoware/wifi/server")

    wifi = view_manager.wifi

    global server

    if menu is None:
        __menu_start(view_manager)

    if server is None:
        server = Server(view_manager)

    return True


def run(view_manager) -> None:
    """Run the app.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.
    """

    __menu_run(view_manager)


def stop(view_manager) -> None:
    """Stop the app and clean up.

    Args:
        view_manager (ViewManager): The view manager instance for display and storage access.
    """
    from gc import collect

    global server, box, menu
    global menu_state, edit_page_state, add_page_state, view_page_state
    global current_page_info, just_started_editing, save_requested
    global current_page_index, settings_info

    if menu is not None:
        del menu
        menu = None

    if server is not None:
        server.close()
        del server
        server = None

    if box is not None:
        del box
        box = None

    menu_state = STATE_MENU_MAIN
    edit_page_state = STATE_PAGE_MENU
    add_page_state = STATE_PAGE_MENU
    view_page_state = STATE_PAGE_MENU

    current_page_info = {}
    current_page_index = -1
    just_started_editing = True
    save_requested = False
    settings_info = {}

    view_manager.keyboard.reset()

    collect()
