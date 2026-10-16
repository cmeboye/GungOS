"""Settings - Persistent device settings."""

import json

# Retired upstream account fields: never load/use them, and drop them on the next save.
RETIRED_SERVICE_SETTINGS = ("jblanked_api_key", "server_username", "server_password")
# Fields of features removed from GungOS (AI providers, LVGL, USB video, fixed
# theme/exit keys). Old SD cards may still contain them; they are dropped too.
RETIRED_SETTINGS = RETIRED_SERVICE_SETTINGS + (
    "anthropic_api_key",
    "dark_mode",
    "deepseek_api_key",
    "exit_button",
    "gemini_api_key",
    "local_api_key",
    "local_url",
    "lvgl_mode",
    "mcp_servers",
    "openai_api_key",
    "usb_stream",
    "xai_api_key",
)

SETTINGS_PATH = "picoware/settings/picoware.json"


class Settings:
    """Settings management for GungOS."""

    __slots__ = ["_storage", "_path", "_settings"]

    def __init__(self, storage):
        """Initialize settings, loading from storage if present.

        Args:
            storage (Storage): The storage instance for reading and writing settings.
        """
        self._storage = storage
        self._path = SETTINGS_PATH
        self._settings = {
            "debug": False,
            "gmt_offset": 0,
            "onscreen_keyboard": False,
            "screen_brightness": 100,
            "screensaver": "",
            "theme_color": 0x001F,
            "wifi_ssid": "",
            "wifi_password": "",
        }
        if not self._storage.exists(self._path):
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
        for key in RETIRED_SETTINGS:
            self._settings.pop(key, None)

    @property
    def screensaver(self):
        return self._settings.get('screensaver','')

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
    def onscreen_keyboard(self) -> bool:
        """Return True if the on-screen keyboard is shown during text entry."""
        return bool(self._settings.get("onscreen_keyboard", False))

    @onscreen_keyboard.setter
    def onscreen_keyboard(self, value: bool):
        """Show or hide the on-screen keyboard.

        Args:
            value (bool): True to show the on-screen keyboard.
        """
        if not self.update({'onscreen_keyboard': value}):
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
        for key in RETIRED_SETTINGS:
            current.pop(key, None)
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
        if key in RETIRED_SETTINGS:
            return default
        if storage is None or not storage.exists(SETTINGS_PATH):
            return default
        data = storage.deserialize(SETTINGS_PATH)
        if data:
            return data.get(key, default)
        return default
