"""TextBox - Multi-line text input widget."""

import textbox


class TextBox(textbox.TextBox):
    """Class for a text box with scrolling functionality."""

    def __init__(
        self,
        draw,
        y: int,
        height: int,
        foreground_color: int = 0xFFFF,
        background_color: int = 0x0000,
        show_scrollbar: bool = True,
        show_cursor: bool = False,
    ) -> None:
        """Initialize the text box with position, height, and styling.

        Args:
            draw (Draw): The drawing context to render the text box.
            y (int): The top Y position of the text box.
            height (int): The height of the text box.
            foreground_color (int): The text color. Defaults to 0xFFFF.
            background_color (int): The background color. Defaults to 0x0000.
            show_scrollbar (bool): Whether to show the scrollbar. Defaults to True.
            show_cursor (bool): Whether to show the cursor. Defaults to False.
        """
        self._draw = draw
        super().__init__(
            y,
            height,
            draw.size.x,
            int(draw.size.x // draw.font_size.x) - 1,  # chars per line
            draw.font_size.y + 2,  # spacing
            foreground_color,
            background_color,
            show_scrollbar,
            show_cursor,
        )

    def __del__(self):
        """Clean up resources."""

    def __setattr__(self, name, value):
        """Set an attribute, routing text and cursor changes to setters.

        Args:
            name (str): The attribute name.
            value: The attribute value.
        """
        if name == "text":
            self.set_text(value)
        elif name == "cursor":
            self._set_cursor(value)
        elif name == "current_line":
            self.set_current_line(value)
        else:
            super().__setattr__(name, value)

    @property
    def current_text(self) -> str:
        """Returns the current text content of the text box."""
        return self.text

    @current_text.setter
    def current_text(self, value: str) -> None:
        """Set the current text content.

        Args:
            value (str): The new text content.
        """

        self._set_text(value)

    @property
    def text_height(self) -> int:
        """Returns the total height of the text content in pixels."""
        tl = self.total_lines
        return 0 if tl == 0 else (tl - 1) * self._draw.font_size.y + 2

    def clear(self):
        """Clears the text box content and screen."""

        self._clear()

    def refresh(self):
        """Refreshes the text box display to reflect any changes in content or state."""

        self.render()

    def set_current_line(self, line: int):
        """Set the current line index for the visible portion of the text.

        Args:
            line (int): The line index to show.
        """

        self._set_current_line(line)

    def set_text(self, text: str):
        """Update the text content and refresh the display.

        Args:
            text (str): The new text content.
        """

        self._set_text(text)

    def scroll_down(self):
        """Scrolls the text box content down by one line"""

        self._scroll_down()

    def scroll_up(self):
        """Scrolls the text box content up by one line"""

        self._scroll_up()

    def jump_to_top(self):
        """Moves the cursor and viewport to the beginning of the text and redraws."""

        self._set_cursor(0)

    def jump_to_bottom(self):
        """Moves the cursor and viewport to the end of the text and redraws."""

        self.render()
