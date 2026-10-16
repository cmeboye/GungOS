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

        ansi_button_map = {
            # printable/symbol keys
            32: buttons.BUTTON_SPACE,
            33: buttons.BUTTON_EXCLAMATION,
            34: buttons.BUTTON_DOUBLE_QUOTE,
            35: buttons.BUTTON_HASH,
            36: buttons.BUTTON_DOLLAR,
            37: buttons.BUTTON_PERCENT,
            38: buttons.BUTTON_AMPERSAND,
            39: buttons.BUTTON_SINGLE_QUOTE,
            40: buttons.BUTTON_LEFT_PARENTHESIS,
            41: buttons.BUTTON_RIGHT_PARENTHESIS,
            42: buttons.BUTTON_ASTERISK,
            43: buttons.BUTTON_PLUS,
            44: buttons.BUTTON_COMMA,
            45: buttons.BUTTON_MINUS,
            46: buttons.BUTTON_PERIOD,
            47: buttons.BUTTON_SLASH,
            # numbers
            48: buttons.BUTTON_0,
            49: buttons.BUTTON_1,
            50: buttons.BUTTON_2,
            51: buttons.BUTTON_3,
            52: buttons.BUTTON_4,
            53: buttons.BUTTON_5,
            54: buttons.BUTTON_6,
            55: buttons.BUTTON_7,
            56: buttons.BUTTON_8,
            57: buttons.BUTTON_9,
            # punctuation
            58: buttons.BUTTON_COLON,
            59: buttons.BUTTON_SEMICOLON,
            60: buttons.BUTTON_LESS_THAN,
            61: buttons.BUTTON_EQUAL,
            62: buttons.BUTTON_GREATER_THAN,
            63: buttons.BUTTON_QUESTION,
            64: buttons.BUTTON_AT,
            # uppercase letters
            65: buttons.BUTTON_A,
            66: buttons.BUTTON_B,
            67: buttons.BUTTON_C,
            68: buttons.BUTTON_D,
            69: buttons.BUTTON_E,
            70: buttons.BUTTON_F,
            71: buttons.BUTTON_G,
            72: buttons.BUTTON_H,
            73: buttons.BUTTON_I,
            74: buttons.BUTTON_J,
            75: buttons.BUTTON_K,
            76: buttons.BUTTON_L,
            77: buttons.BUTTON_M,
            78: buttons.BUTTON_N,
            79: buttons.BUTTON_O,
            80: buttons.BUTTON_P,
            81: buttons.BUTTON_Q,
            82: buttons.BUTTON_R,
            83: buttons.BUTTON_S,
            84: buttons.BUTTON_T,
            85: buttons.BUTTON_U,
            86: buttons.BUTTON_V,
            87: buttons.BUTTON_W,
            88: buttons.BUTTON_X,
            89: buttons.BUTTON_Y,
            90: buttons.BUTTON_Z,
            # additional punctuation
            91: buttons.BUTTON_LEFT_BRACKET,
            92: buttons.BUTTON_BACKSLASH,
            93: buttons.BUTTON_RIGHT_BRACKET,
            94: buttons.BUTTON_CARET,
            95: buttons.BUTTON_UNDERSCORE,
            96: buttons.BUTTON_BACK_TICK,
            # lowercase letters
            97: buttons.BUTTON_A,
            98: buttons.BUTTON_B,
            99: buttons.BUTTON_C,
            100: buttons.BUTTON_D,
            101: buttons.BUTTON_E,
            102: buttons.BUTTON_F,
            103: buttons.BUTTON_G,
            104: buttons.BUTTON_H,
            105: buttons.BUTTON_I,
            106: buttons.BUTTON_J,
            107: buttons.BUTTON_K,
            108: buttons.BUTTON_L,
            109: buttons.BUTTON_M,
            110: buttons.BUTTON_N,
            111: buttons.BUTTON_O,
            112: buttons.BUTTON_P,
            113: buttons.BUTTON_Q,
            114: buttons.BUTTON_R,
            115: buttons.BUTTON_S,
            116: buttons.BUTTON_T,
            117: buttons.BUTTON_U,
            118: buttons.BUTTON_V,
            119: buttons.BUTTON_W,
            120: buttons.BUTTON_X,
            121: buttons.BUTTON_Y,
            122: buttons.BUTTON_Z,
            123: buttons.BUTTON_LEFT_BRACE,
            124: buttons.BUTTON_PIPE,
            125: buttons.BUTTON_RIGHT_BRACE,
            126: buttons.BUTTON_TILDE,
        }

        self._button_map = {
            buttons.KEY_UP: buttons.BUTTON_UP,
            buttons.KEY_DOWN: buttons.BUTTON_DOWN,
            buttons.KEY_LEFT: buttons.BUTTON_LEFT,
            buttons.KEY_RIGHT: buttons.BUTTON_RIGHT,
            buttons.KEY_ESC: self._key_esc,
            buttons.KEY_HOME: buttons.BUTTON_HOME,
            buttons.KEY_DEL: buttons.BUTTON_BACKSPACE,
            buttons.KEY_END: buttons.BUTTON_END,
            8: self._key_back,
            9: buttons.BUTTON_TAB,
            13: buttons.BUTTON_CENTER,
        }
        self._button_map.update(ansi_button_map)
        self._button_map.update(
            {
                buttons.KEY_F1: buttons.BUTTON_F1,
                buttons.KEY_F2: buttons.BUTTON_F2,
                buttons.KEY_F3: buttons.BUTTON_F3,
                buttons.KEY_F4: buttons.BUTTON_F4,
                buttons.KEY_F5: buttons.BUTTON_F5,
                buttons.KEY_F6: buttons.BUTTON_F6,
                buttons.KEY_F7: buttons.BUTTON_F7,
                buttons.KEY_F8: buttons.BUTTON_F8,
                buttons.KEY_F9: buttons.BUTTON_F9,
                buttons.KEY_F10: buttons.BUTTON_F10,
                buttons.KEY_CTRL_UP: buttons.BUTTON_CTRL_UP,
                buttons.KEY_CTRL_DOWN: buttons.BUTTON_CTRL_DOWN,
            }
        )
        for offset in range(26):
            self._button_map[buttons.KEY_ALT_A + offset] = buttons.BUTTON_ALT_A + offset

        self._character_map = {
            buttons.BUTTON_A: "a",
            buttons.BUTTON_B: "b",
            buttons.BUTTON_C: "c",
            buttons.BUTTON_D: "d",
            buttons.BUTTON_E: "e",
            buttons.BUTTON_F: "f",
            buttons.BUTTON_G: "g",
            buttons.BUTTON_H: "h",
            buttons.BUTTON_I: "i",
            buttons.BUTTON_J: "j",
            buttons.BUTTON_K: "k",
            buttons.BUTTON_L: "l",
            buttons.BUTTON_M: "m",
            buttons.BUTTON_N: "n",
            buttons.BUTTON_O: "o",
            buttons.BUTTON_P: "p",
            buttons.BUTTON_Q: "q",
            buttons.BUTTON_R: "r",
            buttons.BUTTON_S: "s",
            buttons.BUTTON_T: "t",
            buttons.BUTTON_U: "u",
            buttons.BUTTON_V: "v",
            buttons.BUTTON_W: "w",
            buttons.BUTTON_X: "x",
            buttons.BUTTON_Y: "y",
            buttons.BUTTON_Z: "z",
            #
            buttons.BUTTON_0: "0",
            buttons.BUTTON_1: "1",
            buttons.BUTTON_2: "2",
            buttons.BUTTON_3: "3",
            buttons.BUTTON_4: "4",
            buttons.BUTTON_5: "5",
            buttons.BUTTON_6: "6",
            buttons.BUTTON_7: "7",
            buttons.BUTTON_8: "8",
            buttons.BUTTON_9: "9",
            #
            buttons.BUTTON_CENTER: "\n",
            buttons.BUTTON_SPACE: " ",
            buttons.BUTTON_PERIOD: ".",
            buttons.BUTTON_QUESTION: "?",
            buttons.BUTTON_COMMA: ",",
            buttons.BUTTON_SEMICOLON: ";",
            buttons.BUTTON_MINUS: "-",
            buttons.BUTTON_EQUAL: "=",
            buttons.BUTTON_LEFT_BRACKET: "[",
            buttons.BUTTON_LEFT_BRACE: "{",
            buttons.BUTTON_RIGHT_BRACKET: "]",
            buttons.BUTTON_RIGHT_BRACE: "}",
            buttons.BUTTON_SLASH: "/",
            buttons.BUTTON_BACKSLASH: "\\",
            buttons.BUTTON_UNDERSCORE: "_",
            buttons.BUTTON_COLON: ":",
            buttons.BUTTON_SINGLE_QUOTE: "'",
            buttons.BUTTON_DOUBLE_QUOTE: '"',
            buttons.BUTTON_PLUS: "+",
            #
            buttons.BUTTON_EXCLAMATION: "!",
            buttons.BUTTON_AT: "@",
            buttons.BUTTON_HASH: "#",
            buttons.BUTTON_DOLLAR: "$",
            buttons.BUTTON_PERCENT: "%",
            buttons.BUTTON_CARET: "^",
            buttons.BUTTON_AMPERSAND: "&",
            buttons.BUTTON_ASTERISK: "*",
            buttons.BUTTON_LEFT_PARENTHESIS: "(",
            buttons.BUTTON_RIGHT_PARENTHESIS: ")",
            buttons.BUTTON_LESS_THAN: "<",
            buttons.BUTTON_GREATER_THAN: ">",
            buttons.BUTTON_BACK_TICK: "`",
            buttons.BUTTON_TILDE: "~",
            buttons.BUTTON_PIPE: "|",
        }

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

        return self._button_map.get(key, buttons.BUTTON_NONE)

    def button_to_char(self, button: int) -> str:
        """Convert a button code to its corresponding character.

        Args:
            button (int): Button code.

        Returns:
            str: The corresponding character or empty string if unmapped.
        """
        if button in self._character_map:
            char_to_add = self._character_map[button]
            if self._was_capitalized and char_to_add.isalpha():
                char_to_add = char_to_add.upper()
            return char_to_add
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
