"""Settings - Persistent device settings."""

import json

# Retired upstream account fields: never load/use them, and drop them on the next save.
RETIRED_SERVICE_SETTINGS = ("jblanked_api_key", "server_username", "server_password")

class Settings:
    """Settings management for Picoware."""

    __slots__ = ["_storage", "_path", "_settings"]

    def __init__(self, storage):
        """Initialize settings, loading from storage if present.

        Args:
            storage (Storage): The storage instance for reading and writing settings.
        
        """
        from picoware.system.buttons import BUTTON_ESCAPE
        from picoware.system.boards import BOARD_HAS_KEYBOARD

        self._storage = storage
        self._path = "picoware/settings/picoware.json"
        self._settings = {
            "anthropic_api_key": "",
            "dark_mode": True,
            "deepseek_api_key": "",
            "debug": False,
            "exit_button": BUTTON_ESCAPE,
            "gemini_api_key": "",
            "gmt_offset": 0,
            "local_api_key": "",
            "local_url": "http://127.0.0.1:8080/v1/chat/completions",
            "lvgl_mode": False,
            "mcp_servers": [],
            "onscreen_keyboard": BOARD_HAS_KEYBOARD == 0,
            "openai_api_key": "",
            "screen_brightness": 100,
            "screensaver": "",
            "theme_color": 0x001F,
            "usb_stream": False,
            "wifi_ssid": "",
            "wifi_password": "",
            "xai_api_key": ""
        }
        if not self._storage.exists(self._path):
            self._settings = {
                "anthropic_api_key": "",
                "dark_mode":  bool(self.__fetch_setting("picoware/settings/dark_mode.json", "dark_mode", True)),
                "debug": bool(self.__fetch_setting("picoware/settings/debug.json", "debug", False)),
                "deepseek_api_key": "",
                "exit_button": int(self.__fetch_setting("picoware/settings/exit_button.json", "exit_button", BUTTON_ESCAPE)),
                "gemini_api_key": "",
                "gmt_offset": int(self.__fetch_setting("picoware/settings/gmt_offset.json", "gmt_offset", 0)),
                "local_api_key": "",
                "local_url": "http://127.0.0.1:8080/v1/chat/completions",
                "lvgl_mode": bool(self.__fetch_setting("picoware/settings/lvgl_mode.json", "lvgl_mode", False)),
                "mcp_servers": [],
                "onscreen_keyboard": bool(self.__fetch_setting("picoware/settings/onscreen_keyboard.json", "onscreen_keyboard", BOARD_HAS_KEYBOARD == 0)),
                "openai_api_key": "",
                "screen_brightness": 100,
                "screensaver": "",
                "theme_color": int(self.__fetch_setting("picoware/settings/theme_color.json", "theme_color", 0x001F)),
                "usb_stream": bool(self.__fetch_setting("picoware/settings/usb_stream.json", "usb_stream", False)),
                "wifi_ssid": self.__fetch_setting("picoware/wifi/ssid.json", "ssid", ""),
                "wifi_password": self.__fetch_setting("picoware/wifi/password.json", "password", ""),
                "xai_api_key": "",
            }
            if not self.__save_settings():
                print("Could not create device settings file")
        else:
            _data = self._storage.read(self._path)
            if _data is not None:
                try:
                    obj = json.loads(_data)
                    self._settings.update(obj)
                except Exception:
                    pass
        for key in RETIRED_SERVICE_SETTINGS:self._settings.pop(key,None)
        self._settings["dark_mode"]=True
        self._settings["exit_button"]=BUTTON_ESCAPE

    @property
    def screensaver(self):
        return self._settings.get('screensaver','')

    @property
    def anthropic_api_key(self) -> str:
        """Return the current Anthropic API key."""
        return self._settings.get("anthropic_api_key", "")
    
    @anthropic_api_key.setter
    def anthropic_api_key(self, value: str):
        """Set the Anthropic API key.

        Args:
            value (str): The API key to set.
        """
        if not self.update({'anthropic_api_key': value}):
            raise OSError("Could not save device settings")
    
    @property
    def dark_mode(self) -> bool:
        """Return True if dark mode is enabled, False otherwise."""
        return True
    
    @dark_mode.setter
    def dark_mode(self, value: bool):
        """Set dark mode.

        Args:
            value (bool): True to enable dark mode.
        """
        if not self.update({'dark_mode': value}):
            raise OSError("Could not save device settings")

    @property
    def debug(self) -> bool:
        """Return True if debug mode is enabled, False otherwise."""
        return bool(self._settings.get("debug", False))
    
    @debug.setter
    def debug(self, value: bool):
        """Set debug mode.

        Args:
            value (bool): True to enable debug mode.
        """
        if not self.update({'debug': value}):
            raise OSError("Could not save device settings")
    
    @property
    def deepseek_api_key(self) -> str:
        """Return the current DeepSeek API key."""
        return self._settings.get("deepseek_api_key", "")
    
    @deepseek_api_key.setter
    def deepseek_api_key(self, value: str):
        """Set the DeepSeek API key.

        Args:
            value (str): The API key to set.
        """
        if not self.update({'deepseek_api_key': value}):
            raise OSError("Could not save device settings")

    @property
    def exit_button(self) -> int:
        """Return the current exit button setting."""
        from picoware.system.buttons import BUTTON_ESCAPE
        return BUTTON_ESCAPE
    
    @exit_button.setter
    def exit_button(self, value: int):
        """Set the exit button setting.

        Args:
            value (int): The button code to use as the exit button.
        """
        if not self.update({'exit_button': value}):
            raise OSError("Could not save device settings")
    
    @property
    def gemini_api_key(self) -> str:
        """Return the current Gemini API key."""
        return self._settings.get("gemini_api_key", "")
    
    @gemini_api_key.setter
    def gemini_api_key(self, value: str):
        """Set the Gemini API key.

        Args:
            value (str): The API key to set.
        """
        if not self.update({'gemini_api_key': value}):
            raise OSError("Could not save device settings")
        
    @property
    def gmt_offset(self) -> int:
        """Return the current GMT offset."""
        return int(self._settings.get("gmt_offset", 0))
    
    @gmt_offset.setter
    def gmt_offset(self, value: int):
        """Set GMT offset.

        Args:
            value (int): The GMT offset in hours.
        """
        if not self.update({'gmt_offset': value}):
            raise OSError("Could not save device settings")

    @property
    def local_api_key(self) -> str:
        """Return the current local API key."""
        return self._settings.get("local_api_key", "")

    @local_api_key.setter
    def local_api_key(self, value: str):
        """Set the local API key.

        Args:
            value (str): The API key to set.
        """
        if not self.update({'local_api_key': value}):
            raise OSError("Could not save device settings")

    @property
    def local_url(self) -> str:
        """Return the current local URL."""
        return self._settings.get("local_url", "")

    @local_url.setter
    def local_url(self, value: str):
        """Set the local URL.

        Args:
            value (str): The local URL to set.
        """
        if not self.update({'local_url': value}):
            raise OSError("Could not save device settings")

    @property
    def lvgl_mode(self) -> bool:
        """Return True if LVGL mode is enabled, False otherwise."""
        return bool(self._settings.get("lvgl_mode", False))
    
    @lvgl_mode.setter
    def lvgl_mode(self, value: bool):
        """Set LVGL mode.

        Args:
            value (bool): True to enable LVGL mode.
        """
        if not self.update({'lvgl_mode': value}):
            raise OSError("Could not save device settings")

    @property
    def mcp_servers(self) -> list:
        """Return the list of MCP servers."""
        return self._settings.get("mcp_servers", [])

    @mcp_servers.setter
    def mcp_servers(self, value: list):
        """Set the list of MCP servers.

        Args:
            value (list): The list of MCP servers to set.
        """
        if not self.update({'mcp_servers': value}):
            raise OSError("Could not save device settings")



    @property
    def onscreen_keyboard(self) -> bool:
        """Return True if onscreen keyboard is enabled, False otherwise."""
        return bool(self._settings.get("onscreen_keyboard", False))
    
    @onscreen_keyboard.setter
    def onscreen_keyboard(self, value: bool):
        """Set onscreen keyboard.

        Args:
            value (bool): True to enable the onscreen keyboard.
        """
        if not self.update({'onscreen_keyboard': value}):
            raise OSError("Could not save device settings")
    
    @property
    def openai_api_key(self) -> str:
        """Return the current OpenAI API key."""
        return self._settings.get("openai_api_key", "")
    
    @openai_api_key.setter
    def openai_api_key(self, value: str):
        """Set the OpenAI API key.

        Args:
            value (str): The API key to set.
        """
        if not self.update({'openai_api_key': value}):
            raise OSError("Could not save device settings")

    @property
    def screen_brightness(self) -> int:
        """Return the current screen brightness."""
        return int(self._settings.get("screen_brightness", 100))

    @screen_brightness.setter
    def screen_brightness(self, value: int):
        """Set the screen brightness.

        Args:
            value (int): The brightness level (0-100).
        """
        if not self.update({'screen_brightness': value}):
            raise OSError("Could not save device settings")

    
    
    @property
    def settings(self) -> dict:
        """Return all settings as a dictionary."""
        return self._settings

    @property
    def theme_color(self) -> int:
        """Return the current theme color."""
        return int(self._settings.get("theme_color", 0x001F))
    
    @theme_color.setter
    def theme_color(self, value: int):
        """Set the theme color.

        Args:
            value (int): The theme color value.
        """
        if not self.update({'theme_color': value}):
            raise OSError("Could not save device settings")
    
    @property
    def usb_stream(self) -> bool:
        """Return True if USB streaming is enabled, False otherwise."""
        return bool(self._settings.get("usb_stream", False))
    
    @usb_stream.setter
    def usb_stream(self, value: bool):
        """Set USB streaming.

        Args:
            value (bool): True to enable USB streaming.
        """
        if not self.update({'usb_stream': value}):
            raise OSError("Could not save device settings")
    
    @property
    def wifi_settings(self) -> dict:
        """Return the current WiFi settings."""
        ssid = self._settings.get("wifi_ssid", "")
        password = self._settings.get("wifi_password", "")
        return {"ssid": ssid, "password": password}
    
    @wifi_settings.setter
    def wifi_settings(self, value: dict):
        """Set the WiFi settings.

        Args:
            value (dict): Dict with ssid and password keys.
        """
        self.save_wifi_settings(value)

    def save_wifi_settings(self, value: dict) -> bool:
        """Save WiFi credentials and return whether storage accepted the write."""
        ssid = value.get("ssid", "")
        password = value.get("password", "")
        return self.update({"wifi_ssid": ssid, "wifi_password": password})

    @property
    def xai_api_key(self) -> str:
        """Return the xAI API key."""
        return self._settings.get("xai_api_key", "")

    @xai_api_key.setter
    def xai_api_key(self, value: str):
        """Set the xAI API key.

        Args:
            value (str): The API key to set.
        """
        if not self.update({'xai_api_key': value}):
            raise OSError("Could not save device settings")
    
    def __fetch_setting(self, path: str, key: str, default=""):
        """Fetch a setting value from storage.

        Args:
            path (str): The storage path of the settings file.
            key (str): The setting key to look up.
            default (object): Value returned when the setting is missing. Defaults to "".

        Returns:
            object: The fetched setting value or the default.
        """
        if not self._storage.exists(path):
            return default

        data = self._storage.deserialize(path)
        if data:
            return data.get(key, default)

        return default
    
    def __save_settings(self) -> bool:
        """Save settings to storage.

        Returns:
            bool: True if the settings were saved successfully.
        """
        return self._storage.serialize(
            self._settings,
            self._path,
        )

    def update(self, values: dict) -> bool:
        """Persist a group of settings, retaining previous values on failure."""
        previous = self._settings.copy()
        current = previous.copy()
        # Another view may have saved credentials since this instance opened.
        # Merge only our changed fields into the latest settings on the card.
        if self._storage.exists(self._path):
            try:
                saved = json.loads(self._storage.read(self._path))
                if not isinstance(saved, dict):
                    return False
                current.update(saved)
            except Exception:
                print("Cannot update unreadable device settings")
                return False
        current.update(values)
        for key in RETIRED_SERVICE_SETTINGS:current.pop(key,None)
        current["dark_mode"]=True
        from picoware.system.buttons import BUTTON_ESCAPE
        current["exit_button"]=BUTTON_ESCAPE
        self._settings = current
        if self.__save_settings():
            try:
                saved = json.loads(self._storage.read(self._path))
                if saved == current:
                    return True
            except Exception:
                pass
        self._settings = previous
        return False

    @classmethod
    def get(cls, storage, key: str, default=None):
        """Get a setting value from storage.

        Args:
            key (str): The setting key to look up.
            default (object): Value returned when the setting is missing. Defaults to None.

        Returns:
            object: The fetched setting value or the default.
        """
        if key in RETIRED_SERVICE_SETTINGS:return default
        path = "picoware/settings/picoware.json"
        if storage is None or not storage.exists(path):
            return default
        data = storage.deserialize(path)
        if data:
            return data.get(key, default)
        return default
