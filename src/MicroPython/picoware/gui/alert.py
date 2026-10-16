"""Alert - Simple alert dialog."""

class Alert:
    """A simple alert dialog class for displaying messages to the user."""

    def __init__(
        self, draw, text: str, text_color: int = 0xFFFF, background_color: int = 0x0000
    ):
        """Initialize the Alert with drawing context and styling.

        Args:
            draw (Draw): The drawing context to render the alert.
            text (str): The message to display in the alert.
            text_color (int): The color of the text. Defaults to 0xFFFF.
            background_color (int): The background color of the alert. Defaults to 0x0000.
        """

        self.display = draw
        self._text = text
        self.text_color = text_color
        self.background_color = background_color

    def __del__(self):
        """Clean up resources."""
        self._text = ""
        self.text_color = 0
        self.background_color = 0

    @property
    def text(self) -> str:
        """Get the current alert text."""
        return self._text

    @text.setter
    def text(self, value: str) -> None:
        """Set the alert text.

        Args:
            value (str): The new alert text.
        """
        self._text = value

    def clear(self) -> None:
        """Clear the display with the background color."""

        from picoware.system.vector import Vector

        self.display.clear(Vector(0, 0), self.display.size, self.background_color)
        self.display.swap()

    def draw(self, title: str) -> None:
        """Render the alert message on the display.

        Args:
            title (str): The title text to display at the top.
        """

        self.clear()

        size = self.display.size
        font = self.display.get_font()

        # Draw Title
        title_width = len(title) * (font.width + font.spacing)
        title_x = (size.x - title_width) // 2
        self.display._text(title_x, 0, title, self.text_color)

        # Draw Border
        border_left = int(size.x * 0.0625)
        border_top = font.height + 1
        border_width = int(size.x - (2 * border_left))
        border_height = (size.y - self.display.scale_y(5)) - border_top
        self.display._rectangle(
            border_left, border_top,
            border_width, border_height,
            self.text_color,
        )

        # Calculate text area constraints
        text_start_x = int(size.x * 0.09375)
        text_start_y = border_top + 2
        text_max_width = size.x - (2 * text_start_x)  # Leave padding from border
        chars_per_line = (text_max_width // (font.width + font.spacing)) - 1

        # Wrap text manually based on character count
        line: int = 0
        # max/last/most-recent 400 characters only
        if len(self._text) > 400:
            self._text = self._text[-400:]
        words = self._text.split()
        current_line = ""

        distance = font.height + 1
        for word in words:
            # Check if adding this word would exceed the line width
            test_line = current_line + (" " if current_line else "") + word
            current_y = text_start_y + line * distance

            if current_y + distance > border_height:
                break

            if len(test_line) <= chars_per_line:
                current_line = test_line
            else:
                # Draw the current line and start a new one
                if current_line:
                    self.display._text(
                        text_start_x,
                        current_y,
                        current_line,
                        self.text_color,
                    )
                    line += 1

                # If the word itself is longer than a line, split it
                if len(word) > chars_per_line:
                    for i in range(0, len(word), chars_per_line):
                        chunk = word[i : i + chars_per_line]
                        self.display._text(
                            text_start_x,
                            current_y,
                            chunk,
                            self.text_color,
                        )
                        line += 1
                    current_line = ""
                else:
                    current_line = word

        # Draw any remaining text
        if current_line:
            self.display._text(
                text_start_x,
                text_start_y + line * distance,
                current_line,
                self.text_color,
            )

        self.display.swap()
