"""Input - PicoCalc keyboard input handling."""

from picoware.system import buttons


class Input:
    """Handles input from the PicoCalc keyboard."""

    __slots__ = (
        "_key_esc",
        "_key_back",
        "_elapsed_time",
        "_last_button",
        "_was_pressed",
        "_was_capitalized",
        "_button_map",
        "_character_map",
    )

    def __init__(self, back_button=buttons.BUTTON_ESCAPE):
        """Initialize the PicoCalc keyboard driver.

        Args:
            back_button (int): Retained for older callers; Escape always returns.
        """
        from picoware_keyboard import (
            init,
            set_background_poll,
            set_key_available_callback,
        )

        self._key_esc = buttons.BUTTON_ESCAPE
        self._key_back = buttons.BUTTON_BACKSPACE

        init()
        set_key_available_callback(self.on_key_callback)
        set_background_poll(True)

        self._elapsed_time = 0
        self._last_button = -1
        self._was_pressed = False
        self._was_capitalized = False

        # Key code -> button, one byte per code (255: no button). Letters and
        # digits are runs of consecutive buttons; letters ignore case.
        keys = bytearray(b"\xff" * 256)
        for offset in range(26):
            keys[65 + offset] = keys[97 + offset] = buttons.BUTTON_A + offset
            keys[buttons.KEY_ALT_A + offset] = buttons.BUTTON_ALT_A + offset
        for offset in range(10):
            keys[48 + offset] = buttons.BUTTON_0 + offset
        for key, button in (
            # punctuation and space, by ASCII code
            (32, buttons.BUTTON_SPACE),
            (33, buttons.BUTTON_EXCLAMATION),
            (34, buttons.BUTTON_DOUBLE_QUOTE),
            (35, buttons.BUTTON_HASH),
            (36, buttons.BUTTON_DOLLAR),
            (37, buttons.BUTTON_PERCENT),
            (38, buttons.BUTTON_AMPERSAND),
            (39, buttons.BUTTON_SINGLE_QUOTE),
            (40, buttons.BUTTON_LEFT_PARENTHESIS),
            (41, buttons.BUTTON_RIGHT_PARENTHESIS),
            (42, buttons.BUTTON_ASTERISK),
            (43, buttons.BUTTON_PLUS),
            (44, buttons.BUTTON_COMMA),
            (45, buttons.BUTTON_MINUS),
            (46, buttons.BUTTON_PERIOD),
            (47, buttons.BUTTON_SLASH),
            (58, buttons.BUTTON_COLON),
            (59, buttons.BUTTON_SEMICOLON),
            (60, buttons.BUTTON_LESS_THAN),
            (61, buttons.BUTTON_EQUAL),
            (62, buttons.BUTTON_GREATER_THAN),
            (63, buttons.BUTTON_QUESTION),
            (64, buttons.BUTTON_AT),
            (91, buttons.BUTTON_LEFT_BRACKET),
            (92, buttons.BUTTON_BACKSLASH),
            (93, buttons.BUTTON_RIGHT_BRACKET),
            (94, buttons.BUTTON_CARET),
            (95, buttons.BUTTON_UNDERSCORE),
            (96, buttons.BUTTON_BACK_TICK),
            (123, buttons.BUTTON_LEFT_BRACE),
            (124, buttons.BUTTON_PIPE),
            (125, buttons.BUTTON_RIGHT_BRACE),
            (126, buttons.BUTTON_TILDE),
            # navigation, editing and function keys
            (buttons.KEY_UP, buttons.BUTTON_UP),
            (buttons.KEY_DOWN, buttons.BUTTON_DOWN),
            (buttons.KEY_LEFT, buttons.BUTTON_LEFT),
            (buttons.KEY_RIGHT, buttons.BUTTON_RIGHT),
            (buttons.KEY_ESC, self._key_esc),
            (buttons.KEY_HOME, buttons.BUTTON_HOME),
            (buttons.KEY_DEL, buttons.BUTTON_BACKSPACE),
            (buttons.KEY_END, buttons.BUTTON_END),
            (8, self._key_back),
            (9, buttons.BUTTON_TAB),
            (13, buttons.BUTTON_CENTER),
            (buttons.KEY_F1, buttons.BUTTON_F1),
            (buttons.KEY_F2, buttons.BUTTON_F2),
            (buttons.KEY_F3, buttons.BUTTON_F3),
            (buttons.KEY_F4, buttons.BUTTON_F4),
            (buttons.KEY_F5, buttons.BUTTON_F5),
            (buttons.KEY_F6, buttons.BUTTON_F6),
            (buttons.KEY_F7, buttons.BUTTON_F7),
            (buttons.KEY_F8, buttons.BUTTON_F8),
            (buttons.KEY_F9, buttons.BUTTON_F9),
            (buttons.KEY_F10, buttons.BUTTON_F10),
            (buttons.KEY_CTRL_UP, buttons.BUTTON_CTRL_UP),
            (buttons.KEY_CTRL_DOWN, buttons.BUTTON_CTRL_DOWN),
        ):
            keys[key] = button
        self._button_map = keys

        # Button -> the ASCII code it types (0: none), the reverse of the
        # printable keys above; letters type lowercase unless capitalized.
        chars = bytearray(buttons.BUTTON_ALT_A)
        for code in range(32, 127):
            if not 65 <= code <= 90:
                chars[keys[code]] = code
        chars[buttons.BUTTON_CENTER] = 10
        self._character_map = chars

    def __del__(self):
        """Destructor to clean up resources."""
        from picoware_southbridge import deinit

        self.reset()
        deinit()
        del self._button_map
        self._button_map = None

    @property
    def button(self) -> int:
        """Returns the last button pressed."""
        return self.normalize_button(self._last_button)

    @property
    def was_capitalized(self) -> bool:
        """Returns True if the last key pressed was a capital letter."""
        return self._was_capitalized

    @staticmethod
    def normalize_button(button):
        if button in (buttons.BUTTON_BACK,buttons.BUTTON_DELETE):
            return buttons.BUTTON_BACKSPACE
        return button

    def _key_to_button(self, key) -> int:
        """Map a key to a button.

        Args:
            key (int): Key code from the keyboard driver.

        Returns:
            int: The mapped button code, or BUTTON_NONE if unmapped.
        """
        if 65 <= key <= 90:
            self._was_capitalized = True

        if 0 <= key < 256:
            button = self._button_map[key]
            if button != 255:
                return button
        return buttons.BUTTON_NONE

    def button_to_char(self, button: int) -> str:
        """Convert a button code to its corresponding character.

        Args:
            button (int): Button code.

        Returns:
            str: The corresponding character or empty string if unmapped.
        """
        if 0 <= button < len(self._character_map):
            code = self._character_map[button]
            if code:
                if self._was_capitalized and 97 <= code <= 122:
                    code -= 32
                return chr(code)
        return ""

    def is_pressed(self) -> bool:
        """Returns True if any key is currently pressed."""
        from picoware_keyboard import key_available

        return key_available()

    def is_held(self, duration: int = 3) -> bool:
        """Return True if the last button was held for the specified duration.

        Args:
            duration (int): Number of polls the button must be held. Defaults to 3.

        Returns:
            bool: True if the button is held for the duration.
        """
        return self._was_pressed and self._elapsed_time >= duration

    def on_key_callback(self, _=None) -> None:
        """Callback invoked when a key becomes available.

        Args:
            _ (None): Unused argument required by mp_sched_schedule.
        """
        __button = self.read_non_blocking()

        if __button == -1:
            self.reset()
            return

        self._was_capitalized = False
        self._last_button = self._key_to_button(__button)
        self._elapsed_time += 1
        self._was_pressed = True

    def read(self) -> int:
        """Returns the key code as an integer (blocking call).

        Returns:
            int: Key code (0-255)

        Warning:
            This is a blocking call and should not be used in callback contexts.
        """
        from picoware_keyboard import get_key

        return get_key()

    def read_non_blocking(self) -> int:
        """Returns the key code as integer, or -1 if no key is pressed."""
        from picoware_keyboard import get_key_nonblocking

        key = get_key_nonblocking()
        return key if key else -1

    def reset(self) -> None:
        """Resets the input state."""
        self._elapsed_time = 0
        self._was_pressed = False
        self._last_button = -1
        self._was_capitalized = False
