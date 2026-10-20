"""ViewManager - Manage views and navigation."""

from picoware.system.buttons import BUTTON_ALT_S, BUTTON_HOME

class ViewManager:
    """Manage multiple views and provide navigation capabilities."""

    MAX_VIEWS = 10
    MAX_STACK_SIZE = 10
    FREQ_DEFAULT = 200000000  # reduced clock used by the REPL and serial terminal
    FREQ_RP2350 = 240000000  # normal clock on the Pico 2 W

    __slots__ = (
        "_active",
        "_battery",
        "_current_view",
        "_view_count",
        "_selected_color",
        "_stack_depth",
        "_current_board_id",
        "_thread_manager",
        "_wifi",
        "_storage",
        "_background_color",
        "_foreground_color",
        "_text_on_dark",
        "_text_on_light",
        "_draw",
        "_gmt_offset",
        "_input_manager",
        "_button",
        "_keyboard",
        "_time",
        "views",
        "view_stack",
        "_log",
        "_app_loader",
        "_uart",
        "_fast_drawing",
        "_fast_owner",
    )

    def __init__(self):
        """Initialize the ViewManager with default settings."""
        from picoware.gui.draw import Draw
        from picoware.system.input import Input
        from picoware.system.battery import Battery
        from picoware.system.storage import Storage
        from picoware.system.system import System
        from picoware.system.settings import Settings
        from picoware.system.time import Time
        from picoware.system.thread import ThreadManager
        from picoware.system.log import Log, LOG_MODE_ALL, LOG_MODE_REPL
        from picoware.system.colors import TFT_BLUE, TFT_BLACK, TFT_WHITE
        from picoware.system.app_loader import AppLoader

        self._active = True
        self._current_view = None
        self._view_count = 0
        self._selected_color = TFT_BLUE
        self._stack_depth = 0

        self._current_board_id = System().board_id

        self.freq()

        # Initialize ThreadManager
        self._thread_manager = ThreadManager()

        # Initialize storage
        self._storage = Storage()
        self._storage.mkdir("picoware")
        self._storage.mkdir("picoware/settings")
        self._storage.mkdir("picoware/keyboard")

        settings = Settings(self._storage)
        self._gmt_offset = settings.gmt_offset

        # Set up colors
        from picoware.gui import appearance
        colors = appearance.values(settings.settings)
        self._text_on_dark, self._text_on_light = colors['text_on_dark'], colors['text_on_light']
        appearance.configure(self._text_on_dark, self._text_on_light)
        self._background_color = colors['background_color']
        self._foreground_color = appearance.text_on(self._background_color)

        # Initialize drawing system
        self._draw = Draw(self._foreground_color, self._background_color)

        # Screen image: PSRAM by default, SRAM ("fast drawing") when chosen in
        # Settings or borrowed by an animated app (request_fast_drawing).
        self._fast_drawing = settings.fast_drawing
        self._fast_owner = None
        self.__apply_screen_mode(self._fast_drawing)

        # theme color
        self._selected_color = colors['theme_color']
        self._draw.theme_color = self._selected_color

        # debug mode
        __debug = settings.debug

        # Escape is always the return/cancel key.
        self._input_manager = Input()
        self._button = -1

        # Initialize battery
        self._battery = Battery()

        # Initialize keyboard
        self._keyboard = None

        # Initialize time
        self._time = Time(self._thread_manager)

        # Initialize arrays
        self.views = [None] * self.MAX_VIEWS
        self.view_stack = [None] * self.MAX_STACK_SIZE

        self._log = Log(
            LOG_MODE_ALL if __debug else LOG_MODE_REPL, "picoware/log.txt", True
        )

        # Initialize app loader
        self._app_loader = AppLoader(self)

        # UART (created on first use)
        self._uart = None

        # Initialize WiFi
        from picoware.system.wifi import WiFi
        self._wifi = WiFi(self)

        # Clear screen
        self.clear()

        # Screen brightness
        self._draw.set_brightness(settings.screen_brightness)

    def __del__(self):
        """Destructor to clean up resources."""
        from gc import collect

        # Clean up views
        for i in range(self.MAX_VIEWS):
            if self.views[i] is not None:
                del self.views[i]
                self.views[i] = None

        if self._current_view is not None:
            del self._current_view
            self._current_view = None

        # Clean up other resources
        if self._keyboard:
            del self._keyboard
            self._keyboard = None
        if self._draw:
            del self._draw
            self._draw = None
        if self._input_manager:
            del self._input_manager
            self._input_manager = None
        if self._app_loader is not None:
            del self._app_loader
            self._app_loader = None
        if self._storage is not None:
            del self._storage
            self._storage = None
        if self._wifi is not None:
            del self._wifi
            self._wifi = None
        if self._time:
            del self._time
            self._time = None
        if self._thread_manager:
            del self._thread_manager
            self._thread_manager = None
        if self._battery is not None:
            del self._battery
            self._battery = None
        if self._uart is not None:
            del self._uart
            self._uart = None

        collect()

    @property
    def active(self):
        """Return whether the ViewManager is active."""
        return self._active

    @active.setter
    def active(self, value: bool):
        """Set the active state of the ViewManager.

        Args:
            value (bool): True to keep the manager running.
        """
        self._active = value

    @property
    def app_loader(self):
        """Return the shared AppLoader instance."""
        return self._app_loader

    @property
    def text_on_dark(self):
        return self._text_on_dark

    @property
    def text_on_light(self):
        return self._text_on_light

    def apply_appearance(self, values):
        """Apply already-persisted appearance roles to drawing and lazy widgets."""
        from picoware.gui import appearance
        colors = appearance.values(values)
        self._text_on_dark, self._text_on_light = colors['text_on_dark'], colors['text_on_light']
        appearance.configure(self._text_on_dark, self._text_on_light)
        self.background_color = colors['background_color']
        self.foreground_color = appearance.text_on(self.background_color)
        self.selected_color = colors['theme_color']

    @property
    def background_color(self):
        """Return the current background color."""
        return self._background_color

    @background_color.setter
    def background_color(self, color):
        """Set the background color.

        Args:
            color (int): The background color value.
        """
        self._background_color = color
        self._draw.background = color
        if self._keyboard is not None:
            self._keyboard.background_color = color

    @property
    def battery(self):
        """Return the Battery instance."""
        return self._battery

    @property
    def board_id(self):
        """Return the current board ID."""
        return self._current_board_id

    @property
    def board_name(self):
        """Return the current device name."""
        from picoware.system.boards import BOARD_NAME

        return BOARD_NAME

    @property
    def button(self):
        """Return the current button state."""
        return self._button

    @property
    def current_view(self):
        """Return the current view."""
        return self._current_view

    @property
    def draw(self):
        """Return the Draw instance."""
        return self._draw

    @property
    def foreground_color(self):
        """Return the current foreground color."""
        return self._foreground_color

    @foreground_color.setter
    def foreground_color(self, color):
        """Set the foreground color.

        Args:
            color (int): The foreground color value.
        """
        self._foreground_color = color
        self._draw.foreground = color
        if self._keyboard is not None:
            self._keyboard.text_color = color

    @property
    def gmt_offset(self):
        """Return the GMT offset in hours."""
        return self._gmt_offset

    @gmt_offset.setter
    def gmt_offset(self, value):
        self._gmt_offset = value

    @property
    def has_bluetooth(self):
        """Return whether Bluetooth is available (always on the Pico 2 W)."""
        return True

    @property
    def has_sd_card(self):
        """Return whether the current board has an SD card."""
        return self._storage is not None

    @property
    def has_wifi(self):
        """Return whether the current board has WiFi capability."""
        return self._wifi is not None

    @property
    def input_manager(self):
        """Return the Input manager instance."""
        return self._input_manager

    @property
    def keyboard(self):
        """Return the Keyboard instance."""
        if self._keyboard is None:
            from picoware.gui.keyboard import Keyboard
            from picoware.system.settings import Settings
            self._keyboard = Keyboard(
                self._draw,
                self._input_manager,
                self._foreground_color,
                self._background_color,
                self._selected_color,
            )
            self._keyboard.show_keyboard = Settings.get(self._storage, "onscreen_keyboard", False)
        return self._keyboard

    @property
    def logs(self) -> list:
        """Return the stored logs as a list of strings."""
        return self._log.logs

    @property
    def selected_color(self):
        """Return the selected color."""
        return self._selected_color

    @selected_color.setter
    def selected_color(self, color):
        """Set the selected color.

        Args:
            color (int): The selected color value.
        """
        self._selected_color = color
        self._draw.theme_color = color
        if self._keyboard is not None:
            self._keyboard.selected_color = color

    @property
    def screen_size(self):
        """Return the screen size as a Vector."""
        return self._draw.size

    @property
    def storage(self):
        """Return the Storage instance."""
        return self._storage

    @property
    def time(self):
        """Return the Time instance."""
        return self._time

    @property
    def thread_manager(self):
        """Return the ThreadManager instance."""
        return self._thread_manager

    @property
    def uart(self):
        """Return the UART instance."""
        if self._uart is None:
            from picoware.system.uart import UART
            self._uart = UART()
        return self._uart

    @property
    def view_count(self):
        """Return the number of views managed."""
        return self._view_count

    @property
    def wifi(self):
        """Return the WiFi instance."""
        return self._wifi

    def add(self, view):
        """Add a view to the manager.

        Args:
            view (View): The View object to add.

        Returns:
            bool: True if successfully added, False if max views reached.
        """
        if self._view_count >= self.MAX_VIEWS:
            return False

        self.views[self._view_count] = view
        self._view_count += 1
        return True

    def alert(self, message: str, back: bool = False, title: str = "Alert") -> bool:
        """Show an alert and wait for the user to acknowledge it.

        Args:
            message (str): The message to display in the alert.
            back (bool): Whether to navigate back after the alert is acknowledged. Defaults to False.
            title (str): The heading drawn above the message. Defaults to "Alert".

        Returns:
            bool: True if the user confirmed the alert, False otherwise.
        """

        from picoware.gui.alert import Alert
        from picoware.system.buttons import BUTTON_BACK, BUTTON_ESCAPE

        self._draw.clear()
        _alert = Alert(
            self._draw,
            message,
            self._foreground_color,
            self._background_color,
        )
        _alert.draw(title)
        self.log(f"Alert: {message}", 2)

        _denied: bool = False

        # Wait for user to acknowledge
        inp = self._input_manager
        inp.reset()
        from time import sleep_ms

        while True:
            button = inp.button
            if button == -1:
                sleep_ms(10)  # wait without spinning the CPU
                continue
            _denied = button == BUTTON_ESCAPE
            inp.reset()
            break

        if back:
            self.back()

        # back/escape button returns false, any other button returns true
        return not _denied

    def back(
        self,
        remove_current_view: bool = True,
        should_clear: bool = True,
        should_start: bool = True,
    ):
        """Navigate back to the previous view in the stack.

        Args:
            remove_current_view (bool): Whether to remove the current view from the manager. Defaults to True.
            should_clear (bool): Whether to clear the screen. Defaults to True.
            should_start (bool): Whether to start the previous view. Defaults to True.
        """
        if self._stack_depth > 0:
            view_to_remove = None

            # Mark current view for removal if requested
            if self._current_view is not None and remove_current_view:
                view_to_remove = self._current_view

            # Stop current view
            if self._current_view is not None:
                self._current_view.stop(self)
                if should_clear:
                    self.clear()

            # Pop from stack and set as current view
            self._stack_depth -= 1
            self._current_view = self.view_stack[self._stack_depth]
            self.view_stack[self._stack_depth] = None

            # Start the previous view
            if self._current_view is not None:
                if should_start:
                    if not self._current_view.start(self):
                        # If the previous view fails to start, try going back again
                        self.back(False, should_clear, should_start)
                        return

            # Remove the view if requested
            if view_to_remove is not None:
                # Find and remove the view from the views array
                for i in range(self._view_count):
                    if self.views[i] == view_to_remove:
                        # Remove any remaining instances from the stack
                        j = 0
                        while j < self._stack_depth:
                            if self.view_stack[j] == view_to_remove:
                                # Shift remaining stack elements down
                                for k in range(j, self._stack_depth - 1):
                                    self.view_stack[k] = self.view_stack[k + 1]
                                self._stack_depth -= 1
                                self.view_stack[self._stack_depth] = None
                                j -= 1  # Check this index again after shifting
                            j += 1

                        # Remove from views array
                        for j in range(i, self._view_count - 1):
                            self.views[j] = self.views[j + 1]
                        self.views[self._view_count - 1] = None
                        self._view_count -= 1
                        break

    def clear(self):
        """Clear the screen with the background color."""
        self._draw.fill_screen(self._background_color)
        self._draw.swap()

    def clear_stack(self):
        """Clear the navigation stack."""
        for i in range(self._stack_depth):
            self.view_stack[i] = None
        self._stack_depth = 0

    @property
    def fast_drawing(self) -> bool:
        """The user's preference: keep the screen image in SRAM."""
        return self._fast_drawing

    def set_fast_drawing(self, enabled: bool) -> bool:
        """Apply the Fast Drawing preference.

        Returns:
            bool: False if SRAM mode was wanted but there was not enough free
                memory; the preference is kept and applies on the next start.
        """
        self._fast_drawing = bool(enabled)
        if self._fast_owner is not None:
            return True  # an app holds SRAM; the preference applies when it stops
        return self.__apply_screen_mode(self._fast_drawing)

    def request_fast_drawing(self) -> bool:
        """Let the current view draw in SRAM until it stops (animations, games).

        The screen image moves from PSRAM to on-chip SRAM, which draws about
        2.5x faster but takes 100 KB of RAM. It moves back automatically when
        the view stops, even after a crash.

        Returns:
            bool: True if the screen image is in SRAM.
        """
        if self._current_view is None:
            return False
        self._fast_owner = self._current_view.name
        return self.__apply_screen_mode(True)

    def view_stopped(self, view) -> None:
        """Called by View.stop: return a borrowed SRAM screen."""
        if self._fast_owner is not None and view.name == self._fast_owner:
            self._fast_owner = None
            self.__apply_screen_mode(self._fast_drawing)

    def __apply_screen_mode(self, sram: bool) -> bool:
        """Move the screen image to SRAM or PSRAM; True if it ended there."""
        draw = self._draw
        if draw is None or not hasattr(draw, "MODE_SRAM"):
            return not sram
        target = draw.MODE_SRAM if sram else draw.MODE_PSRAM
        if draw.mode != target:
            if sram:
                from gc import collect

                collect()  # SRAM mode needs one free 100 KB block
            draw.set_mode(target)
        return draw.mode == target

    def freq(self, use_default: bool = False, frequency: int = None) -> int:
        """Set the CPU frequency.

        Args:
            use_default (bool): Whether to use the reduced default frequency. Defaults to False.
            frequency (int): Explicit frequency in Hz. Defaults to None.

        Returns:
            int: The new CPU frequency.
        """
        from machine import freq

        if frequency is not None:
            return freq(frequency)
        if use_default:
            return freq(self.FREQ_DEFAULT)
        return freq(self.FREQ_RP2350)

    def get_view(self, view_name: str):
        """Get a view by name.

        Args:
            view_name (str): The name of the view to find.

        Returns:
            View: The view object if found, None otherwise.
        """
        for i in range(self._view_count):
            if self.views[i] is not None:
                if self.views[i].name == view_name:
                    return self.views[i]
            else:
                self.log(
                    f"ViewManager: View '{view_name}' found in views array but is None.",
                    2,
                )
        return None

    def log(self, message: str, log_type: int = -1) -> bool:
        """Log a message with an optional log type.

        Args:
            message (str): The message to log.
            log_type (int): The type of log. Defaults to -1.

        Returns:
            bool: True if the message was logged.
        """
        return self._log.log(message, log_type)

    def remove(self, view_name: str):
        """Remove a view by name.

        Args:
            view_name (str): The name of the view to remove.
        """
        for i in range(self._view_count):
            if self.views[i] and self.views[i].name == view_name:
                removed_view = self.views[i]

                # Check if this view is in the stack and remove all instances
                j = 0
                while j < self._stack_depth:
                    if self.view_stack[j] == removed_view:
                        # Shift remaining stack elements down
                        for k in range(j, self._stack_depth - 1):
                            self.view_stack[k] = self.view_stack[k + 1]
                        self._stack_depth -= 1
                        self.view_stack[self._stack_depth] = None
                        j -= 1  # Check this index again after shifting
                    j += 1

                # If this is the current view, clear it
                if self._current_view == removed_view:
                    self._current_view.stop(self)
                    self._current_view = None
                    self.clear()

                # Shift the later views down; the array keeps MAX_VIEWS slots
                for j in range(i, self._view_count - 1):
                    self.views[j] = self.views[j + 1]
                self.views[self._view_count - 1] = None
                self._view_count -= 1

                break

    def run(self) -> bool:
        """Run the current view."""
        button = self._input_manager.normalize_button(self._input_manager.button)
        self._button = button
        if button == BUTTON_HOME:
            while self._stack_depth > 0:
                if self._stack_depth == 1:
                    self.back(should_clear=True, should_start=True)
                else:
                    self.back(should_clear=False, should_start=False)
        elif button == BUTTON_ALT_S:
            # System shortcut: capture the screen and keep the key from the view.
            self._draw.screenshot("screenshot.bmp")
            self._input_manager.reset()
            button = self._button = -1

        if self._wifi is not None:
            self._wifi.poll()

        if self._thread_manager.run():
            self.log(self._thread_manager._outgoing)

        if self._current_view is not None:
            self._current_view.run(self)

        if button != -1:
            self._input_manager.reset()
            self._button = -1

        return self._active

    def set(self, view_name: str):
        """Set the current view by name, clearing the stack.

        Args:
            view_name (str): The name of the view to set as current.
        """
        if self._current_view is not None:
            self._current_view.stop(self)
            self.clear()

        self._current_view = self.get_view(view_name)
        if self._current_view is not None:
            if not self._current_view.start(self):
                self.back()

        # Clear the stack when explicitly setting a view
        self.clear_stack()

    def switch_to(self, view_name: str, clear_stack=False, push_view=True):
        """Switch to a view by name with options for stack management.

        Args:
            view_name (str): The name of the view to switch to.
            clear_stack (bool): Whether to clear the navigation stack. Defaults to False.
            push_view (bool): Whether to push the current view to the stack. Defaults to True.
        """
        view = self.get_view(view_name)
        if view is None:
            self.log(f"ViewManager: View '{view_name}' not found or is None.", 2)
            return

        # Push current view to stack before switching
        if self._current_view is not None:
            if clear_stack:
                self.clear_stack()
            if push_view:
                self._push_view(self._current_view)
            self._current_view.stop(self)
            self.clear()

        self._current_view = view
        if not self._current_view.start(self):
            self.back()

    def _push_view(self, view):
        """Push a view onto the navigation stack.

        Args:
            view (View): The view to push.
        """
        if self._stack_depth < self.MAX_STACK_SIZE and view is not None:
            self.view_stack[self._stack_depth] = view
            self._stack_depth += 1

    def push_view(self, view_name: str):
        """Push a view to the stack by name.

        Args:
            view_name (str): The name of the view to push.
        """
        view = self.get_view(view_name)
        if view is not None:
            self._push_view(view)
