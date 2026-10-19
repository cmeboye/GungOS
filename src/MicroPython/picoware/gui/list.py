"""List - Scrollable list widget."""

class List:
    """A simple list class for a GUI."""

    def __init__(
        self,
        draw,
        y: int,
        height: int,
        text_color: int = 0xFFFF,
        background_color: int = 0x0000,
        selected_color: int = 0x001F,
        border_color: int = 0xFFFF,
        border_width: int = 2,
    ):
        """Initialize the list with drawing context and styling.

        Args:
            draw (Draw): The drawing context to render the list.
            y (int): The top Y position of the list.
            height (int): The height of the list.
            text_color (int): The text color. Defaults to 0xFFFF.
            background_color (int): The background color. Defaults to 0x0000.
            selected_color (int): The selected item color. Defaults to 0x001F.
            border_color (int): The border color. Defaults to 0xFFFF.
            border_width (int): The border width. Defaults to 2.
        """
        from picoware.system.vector import Vector

        self.display = draw
        self.y = y
        self.height = height
        self.text_color = text_color
        self.background_color = background_color
        self.selected_color = selected_color
        self.border_color = border_color
        self.border_width = border_width

        self.position = Vector(0, y)
        self.size = Vector(draw.size.x, height)
        draw.clear(self.position, self.size, background_color)

        # 320 / 64 = 5
        self._five = Vector(self.display.size.x // 64, self.display.size.y // 64)
        self._sixteen = self.display.size.y // 20  # 320 / 20 = 16
        self._three = self.display.size.y // 106  # 320 / 106 = 3

        self.item_height = draw.scale_y(20)
        self._selected_index = 0
        self.visible_item_count = (
            self.size.y - 2 * border_width
        ) / self.item_height
        self.items = []
        draw.swap()

        self.size_x = self.display.size.x
        self._dec_v = Vector(0, 0)
        self._dec_v_b = Vector(0, 0)

        self.rec_vec_pos = Vector(self._five.x, 0)
        self.rec_vec_size = Vector(self.size_x - self._five.x * 2, 0)
        self.text_vec_pos = Vector(self._five.x * 2, 0)

        self.menu_y = int(self.position.y + self.size.y // 4)
        self.box_width = int(self.size_x - int(self.size_x // draw.font_size.x))
        self.box_height = int(self.size.y // draw.font_size.y)
        self.box_x = int((self.size_x - self.box_width) // 2)
        self.dot_size = Vector(self._five.x * 2, self._five.y * 2)

    def __del__(self):
        """Destructor to clean up resources"""

        self.items = []
        self.size = None
        self.position = None
        self._dec_v = None
        self._dec_v_b = None
        self.rec_vec_pos = None
        self.rec_vec_size = None
        self.text_vec_pos = None
        self.menu_y = None
        self.box_width = None
        self.box_height = None
        self.box_x = None
        self.dot_size = None

    @property
    def current_item(self) -> str:
        """Get the currently selected item."""

        # Get the currently selected item
        if 0 <= self._selected_index < len(self.items):
            return self.items[self._selected_index]
        return ""

    @property
    def item_count(self) -> int:
        """Get the number of items in the list."""
        return len(self.items)

    @property
    def list_height(self) -> int:
        """Get the height of the list."""
        return len(self.items) * self.item_height

    @property
    def selected_index(self) -> int:
        """Get the selected index."""
        return self._selected_index

    def add_item(self, item: str) -> None:
        """Add an item to the list.

        Args:
            item (str): The item to add.
        """
        self.items.append(item)

    def clear(self, swap: bool = True) -> None:
        """Clear the list.

        Args:
            swap (bool): Whether to swap the display buffer. Defaults to True.
        """

        # Clear the list of items
        self.items = []
        self._selected_index = 0

        # Clear the display area
        self.display._fill_rectangle(
            self.position.x,
            self.position.y,
            self.size.x,
            self.size.y,
            self.background_color,
        )
        if swap:
            self.display.swap()

    def draw(self, swap: bool = True) -> None:
        """Draw the list.

        Args:
            swap (bool): Whether to swap the display buffer. Defaults to True.
        """

        # Clear the display area
        self.display._fill_rectangle(
            self.position.x,
            self.position.y,
            self.size.x,
            self.size.y,
            self.background_color,
        )

        _len = len(self.items)

        # Draw decorative pattern below underline
        self._dec_v.y = self.position.y + self._five.y + (self.display.size.y // 16)
        for i in range(0, self.size_x, 10):
            self.display._pixel(i, self._dec_v.y, self.border_color)

        # Get current selected item
        if 0 <= self._selected_index < _len:
            current_item = self.items[self._selected_index]
            indicator_y = self.menu_y + self._five.y * 4
            bottom_decorator_y = indicator_y + self._five.y * 5
            decorator_center_y = (self._dec_v.y + bottom_decorator_y) // 2

            # text dimensions for centering
            font_size = 2
            font = self.display.get_font(font_size)
            item_width = min(len(current_item) * (font.width + font.spacing), self.size_x - (self.size_x // 5))
            item_x = (self.size_x - item_width) // 2
            text_y = decorator_center_y - font.height // 2

            # Draw selection box
            padding_x = self._five.x * 2
            padding_y = self._three
            box_width = item_width + self.display.scale_x(2) * padding_x
            box_x = (self.size_x - box_width) // 2
            text_font_height = font.height
            box_height = text_font_height + self.display.scale_y(2) * padding_y
            box_y = decorator_center_y - box_height // 2
            self.display._fill_rectangle(
                box_x,
                box_y,
                box_width,
                box_height,
                self.selected_color,
            )

            from picoware.gui.status_bar import foreground
            # Draw text centered
            self.display._text(
                item_x,
                text_y,
                current_item[:item_width // (font.width + font.spacing)],
                foreground(self.selected_color),
                font_size,
            )

            # Draw navigation arrows
            self.text_vec_pos.y = decorator_center_y - self.display.font_size.y // 2
            if self._selected_index > 0:
                self.display._text(
                    self._five.x, self.text_vec_pos.y, "<", self.border_color
                )
            if self._selected_index < _len - 1:
                self.display._text(
                    self.size_x - self._five.x * 3,
                    self.text_vec_pos.y,
                    ">",
                    self.border_color,
                )

            # Draw indicator dots
            if _len <= self._five.x * 3:
                dots_spacing = self._five.x * 3
                dots_start_x = (self.size_x - (_len * dots_spacing)) // 2
                for i in range(_len):
                    if i == self._selected_index:
                        self.display._fill_rectangle(
                            dots_start_x + (i * dots_spacing),
                            indicator_y,
                            self.dot_size.x,
                            self.dot_size.y,
                            self.border_color,
                        )
                    else:
                        self.display._rectangle(
                            dots_start_x + (i * dots_spacing),
                            indicator_y,
                            self.dot_size.x,
                            self.dot_size.y,
                            self.border_color,
                        )
            else:
                # show the current selected item index and total count
                index_text = "{}/{}".format(self._selected_index + 1, _len)
                index_text_width = len(index_text) * self.display.font_size.x
                index_text_x = (self.size_x - index_text_width) // 2
                self.display._text(
                    index_text_x,
                    indicator_y,
                    index_text,
                    self.border_color,
                )

            # Draw decorative bottom pattern
            for i in range(0, self.size_x, 10):
                self.display._pixel(
                    i, indicator_y + self._five.y * 5, self.border_color
                )

            # Draw scrollable list below decorative pattern
            list_start_y = indicator_y + self._five.y * 8
            available_height = (self.position.y + self.size.y) - list_start_y
            item_height = (
                self.display.font_size.y + self._three * 2
            )  # Font height + padding
            max_visible_items = max(1, int(available_height / item_height))

            # Calculate which items to show based on selected index
            if _len <= max_visible_items:
                # Show all items if they fit
                first_visible = 0
                last_visible = _len
            else:
                # Center the selected item when possible
                half_visible = max_visible_items // 2
                first_visible = max(0, self._selected_index - half_visible)
                last_visible = min(_len, first_visible + max_visible_items)

                # Adjust if we're near the end
                if last_visible == _len:
                    first_visible = max(0, _len - max_visible_items)

            # Draw each visible item
            for i in range(first_visible, last_visible):
                visible_idx = i - first_visible
                item_y = list_start_y + (visible_idx * item_height)

                # Draw background for selected item
                if i == self._selected_index:
                    self.display._fill_rectangle(
                        self.rec_vec_pos.x,
                        item_y,
                        self.rec_vec_size.x,
                        item_height,
                        self.selected_color,
                    )

                # Draw item text
                text_y = item_y + self._three
                item_text = self.items[i]

                # Truncate text if too long
                max_chars = (self.size_x - self._five.x * 4) // self.display.font_size.x
                if len(item_text) > max_chars:
                    item_text = item_text[: max_chars - 2] + ".."

                # Center text if circular display, otherwise left-align with padding
                text_x = self._five.x * 2
                from picoware.gui.status_bar import foreground
                self.display._text(text_x, text_y, item_text, foreground(self.selected_color) if i == self._selected_index else self.text_color)

        # Swap buffers
        if swap:
            self.display.swap()

    def get_item(self, index: int) -> str:
        """Get an item from the list.

        Args:
            index (int): The index of the item.

        Returns:
            str: The item string, or "" if not found.
        """

        # Get the item from the list
        if 0 <= index < len(self.items):
            return self.items[index]
        return ""

    def item_exists(self, item: str) -> bool:
        """Check if an item exists in the list.

        Args:
            item (str): The item to look for.

        Returns:
            bool: True if the item exists.
        """
        return item in self.items

    def remove_item(self, index: int) -> None:
        """Remove an item from the list and update the display.

        Args:
            index (int): The index of the item to remove.
        """
        _len = len(self.items)

        # Remove the item from the list
        if 0 <= index < _len:
            self.items.pop(index)

        if self._selected_index >= _len:
            self._selected_index = _len - 1 if _len > 0 else 0

    def scroll_down(self, swap: bool = True) -> None:
        """Scroll the list down by one item.

        Args:
            swap (bool): Whether to swap the display buffer. Defaults to True.
        """

        self._selected_index += 1
        if self._selected_index >= len(self.items):
            self._selected_index = 0
        self.draw(swap)

    def scroll_up(self, swap: bool = True) -> None:
        """Scroll the list up by one item.

        Args:
            swap (bool): Whether to swap the display buffer. Defaults to True.
        """

        self._selected_index -= 1
        if self._selected_index < 0:
            self._selected_index = len(self.items) - 1
        self.draw(swap)

    def set_selected(self, index: int, swap: bool = True) -> None:
        """Set the selected item in the list.

        Args:
            index (int): The index of the item to select.
            swap (bool): Whether to swap the display buffer. Defaults to True.
        """

        if 0 <= index < len(self.items):
            self._selected_index = index
            self.draw(swap)
