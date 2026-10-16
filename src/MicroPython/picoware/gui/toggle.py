"""Toggle - On/off toggle switch widget."""

from picoware.system.vector import Vector


class Toggle:
    """A simple toggle switch for the GUI."""

    def __init__(
        self,
        draw,
        position: Vector,
        size: Vector,
        text: str,
        initial_state: bool = False,
        foreground_color: int = 0xFFFF,
        background_color: int = 0x0000,
        on_color: int = 0x001F,
        border_color: int = 0xFFFF,
        border_width: int = 1,
        should_clear: bool = True,
    ):
        """Initialize the Toggle switch with drawing context and styling.

        Args:
            draw (Draw): The drawing context to render the toggle.
            position (Vector): Vector position of the toggle.
            size (Vector): Vector size of the toggle.
            text (str): The label text for the toggle.
            initial_state (bool): Initial state of the toggle. Defaults to False.
            foreground_color (int): The color of the text. Defaults to 0xFFFF.
            background_color (int): The background color. Defaults to 0x0000.
            on_color (int): The color when the toggle is on. Defaults to 0x001F.
            border_color (int): The color of the border. Defaults to 0xFFFF.
            border_width (int): The width of the border. Defaults to 1.
            should_clear (bool): Whether to clear on init. Defaults to True.
        """

        self.display = draw
        self.position = position
        self.size = size
        self._text = text
        self._state = initial_state
        self.foreground_color = foreground_color
        self.background_color = background_color
        self.on_color = on_color
        self.border_color = border_color
        self.border_width = border_width

        if should_clear:
            self.clear()

    def __del__(self):
        """Clean up resources."""
        if self.position:
            del self.position
            self.position = None
        if self.size:
            del self.size
            self.size = None
        self._text = ""

    @property
    def state(self) -> bool:
        """Get the current state of the toggle."""
        return self._state

    @state.setter
    def state(self, new_state: bool) -> None:
        """Set the toggle state and redraw.

        Args:
            new_state (bool): The new toggle state.
        """
        self._state = new_state

        self.draw()

    @property
    def text(self) -> str:
        """Get the current text of the toggle."""
        return self._text

    @text.setter
    def text(self, new_text: str) -> None:
        """Set the toggle text and redraw.

        Args:
            new_text (str): The new toggle text.
        """
        self._text = new_text

        self.draw()

    def clear(self) -> None:
        """Clear the toggle area with the background color."""

        self.display.clear(self.position, self.size, self.background_color)
        self.display.swap()

    def draw(
        self, swap: bool = True, clear: bool = True, selected: bool = False
    ) -> None:
        """Render the toggle switch on the display.

        Args:
            swap (bool): Whether to swap the display buffer. Defaults to True.
            clear (bool): Whether to clear the area first. Defaults to True.
            selected (bool): Whether the toggle is selected. Defaults to False.
        """

        if clear:
            self.display.clear(self.position, self.size, self.background_color)

        display_size: Vector = self.display.size

        self.display._line(
            self.position.x, self.position.y + self.size.y - self.border_width,
            self.position.x + self.size.x,
            self.position.y + self.size.y - self.border_width,
            self.border_color,
        )
        self.display._text(
            self.position.x + self.display.scale_x(5), 
            self.position.y + self.size.y // 2 - self.display.scale_y(8),
            self._text,
            self.on_color if selected else self.foreground_color,
        )

        toggle_width = int(display_size.x * 0.09375)
        toggle_height = int(display_size.x * 0.05)
        toggle_x = self.position.x + self.size.x - toggle_width - self.display.scale_x(5)
        toggle_y = self.position.y + (self.size.y - toggle_height) // 2
        knob_radius = self.display.scale_x(6)

        if self._state:
            # Toggle is ON
            self.display._fill_rectangle(
                toggle_x, toggle_y,
                toggle_width, toggle_height,
                self.on_color,
            )
            self.display._fill_circle(
                toggle_x + toggle_width - knob_radius - self.display.scale_x(2),
                toggle_y + toggle_height // 2,
                knob_radius,
                self.background_color,
            )
        else:
            # Toggle is OFF
            self.display._fill_rectangle(
                toggle_x, toggle_y,
                toggle_width, toggle_height,
                self.border_color,
            )
            self.display._fill_circle(
                toggle_x + knob_radius + self.display.scale_x(2), toggle_y + toggle_height // 2,
                knob_radius,
                self.background_color,
            )

        if swap:
            self.display.swap()

    def toggle(self) -> None:
        """Toggle the current state."""

        self._state = not self._state
        self.draw()

    def update(self, text: str, state: bool) -> None:
        """Update both text and state of the toggle.

        Args:
            text (str): The new toggle text.
            state (bool): The new toggle state.
        """

        self._text = text
        self._state = state
