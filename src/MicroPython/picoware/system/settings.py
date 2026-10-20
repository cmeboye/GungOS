"""Settings - Persistent device settings."""

import json

# Fields of features removed from GungOS (AI providers, LVGL, USB video, fixed
# theme/exit keys). Old SD cards may still contain them; they are dropped on load/save.
RETIRED_SETTINGS = (
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
# Kept in internal flash (picoware.system.secrets), never in the SD settings file.
WIFI_PASSWORD_KEY = "wifi_password"


class Settings:
    """Settings management for GungOS."""

    __slots__ = ["_storage", "_path", "_settings", "_legacy_password"]

    def __init__(self, storage):
        """Initialize settings, loading from storage if present.

        Args:
            storage (Storage): The storage instance for reading and writing settings.
        """
        self._storage = storage
        self._path = SETTINGS_PATH
        self._settings = {
            "debug": False,
            "fast_drawing": False,
            "gmt_offset": 0,
            "onscreen_keyboard": False,
            "screen_brightness": 100,
            "screensaver": "",
            "theme_color": 0x001F,
            "background_color": 0,
            "text_on_dark": 0xFFFF,
            "text_on_light": 0,
            "wifi_ssid": "",
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
        # Older SD cards hold the Wi-Fi password in plain text: move it to flash
        # and remove it from the card. An empty field is dropped on the next save.
        self._legacy_password = None
        legacy = self._settings.pop(WIFI_PASSWORD_KEY, None)
        if legacy:
            if self.__store_password(legacy, False):
                self.__save_settings()
            else:
                self._legacy_password = legacy

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
    def fast_drawing(self) -> bool:
        """Return True if the screen image should live in fast on-chip SRAM."""
        return bool(self._settings.get("fast_drawing", False))

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
        if self._legacy_password is not None:
            password = self._legacy_password
        else:
            from picoware.system import secrets

            password = secrets.get(WIFI_PASSWORD_KEY, "")
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
        return self.update({"wifi_ssid": ssid, WIFI_PASSWORD_KEY: password})

    def __store_password(self, value: str, explicit: bool) -> bool:
        """Write the Wi-Fi password to internal flash.

        Args:
            value (str): The password.
            explicit (bool): False when migrating an SD copy; an empty legacy
                value then has nothing worth moving.

        Returns:
            bool: True if flash holds the value afterwards.
        """
        from picoware.system import secrets

        if secrets.get(WIFI_PASSWORD_KEY, None) == value or (value == "" and not explicit):
            return True
        return secrets.update({WIFI_PASSWORD_KEY: value})

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
        """Persist a group of settings, retaining previous values on failure.

        The Wi-Fi password goes to internal flash once the SD part is saved; if
        that write fails the SD file is restored, so a failed save changes nothing.
        """
        values = dict(values)
        password = values.pop(WIFI_PASSWORD_KEY, None)
        previous = self._settings.copy()
        current = previous.copy()
        on_card = None
        # Another view may have saved credentials since this instance opened.
        # Merge only our changed fields into the latest settings on the card.
        if self._storage.exists(self._path):
            try:
                on_card = json.loads(self._storage.read(self._path))
                if not isinstance(on_card, dict):
                    return False
                current.update(on_card)
            except Exception:
                print("Cannot update unreadable device settings")
                return False
        current.update(values)
        for key in RETIRED_SETTINGS:
            current.pop(key, None)
        legacy = current.pop(WIFI_PASSWORD_KEY, None)
        # Move a plain-text SD password to flash before the card copy is dropped.
        if password is None and legacy and not self.__store_password(legacy, False):
            return False
        self._settings = current
        saved = False
        if self.__save_settings():
            try:
                saved = json.loads(self._storage.read(self._path)) == current
            except Exception:
                saved = False
        if saved and (password is None or self.__store_password(password, True)):
            self._legacy_password = None
            return True
        self._settings = previous
        if saved and on_card is not None:
            self._storage.serialize(on_card, self._path)
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
