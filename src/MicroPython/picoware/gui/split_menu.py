"""Compact category sidebar with a selectable submenu on the right."""


class SplitMenu:
    def __init__(self, view_manager, categories, sections):
        self.vm = view_manager
        self.categories = categories
        self.sections = sections
        self.category = 0
        self.indices = [0] * len(categories)
        self.focus_right = False
        self.nested_items = None
        self.nested_title = ""
        self.nested_index = 0

    @property
    def items(self):
        return self.nested_items if self.nested_items is not None else self.sections[self.category]

    @property
    def index(self):
        return self.nested_index if self.nested_items is not None else self.indices[self.category]

    @property
    def current_item(self):
        return self.items[self.index]

    def move(self, delta):
        if self.focus_right:
            selected = (self.index + delta) % len(self.items)
            if self.nested_items is not None:
                self.nested_index = selected
            else:
                self.indices[self.category] = selected
        else:
            self.category = (self.category + delta) % len(self.categories)
            self.nested_items = None
        self.draw()

    def open_submenu(self, title, items):
        self.nested_title = title
        self.nested_items = items
        self.nested_index = 0
        self.focus_right = True
        self.draw()

    def back(self):
        if self.nested_items is not None:
            self.nested_items = None
        elif self.focus_right:
            self.focus_right = False
        else:
            return False
        self.draw()
        return True

    def draw(self):
        vm = self.vm
        draw = vm.draw
        width, height = draw.size.x, draw.size.y
        fg, bg, accent = vm.foreground_color, vm.background_color, vm.selected_color
        # Match the file browser's thin header/footer and bordered panels.
        pad = max(3, width // 64)
        header = max(18, height // 12)
        footer = max(18, height // 12)
        split = width * 33 // 100
        top = header + pad
        bottom = height - footer - pad
        font_size = 2 if width >= 240 and height >= 240 else 0
        font = draw.get_font(font_size)
        line_height = font.height + max(7, height // 40)
        available = max(1, (bottom - top - font.height - pad * 3) // line_height)
        row_y = top + font.height + pad * 2
        draw.erase()
        from picoware.gui import style
        path="Menu / "+self.categories[self.category]
        if self.nested_items is not None:path+=" / "+self.nested_title
        style.header(draw,path,palette=style.system_palette(vm),height=header)
        draw._rectangle(pad, top, split - pad * 2, bottom - top, accent)
        draw._rectangle(split, top, width - split - pad, bottom - top, accent)
        title = self.categories[self.category]
        if self.nested_items is not None:
            title += " / " + self.nested_title
        draw._text(pad * 2, top + pad, "Browse", fg)
        draw._text(split + pad, top + pad, title, fg)

        def row(x, y, row_width, text, selected, active):
            if selected:
                if active:
                    draw._fill_rectangle(x, y - 2, row_width, line_height - 2, accent)
                else:
                    draw._rectangle(x, y - 2, row_width, line_height - 2, accent)
            max_chars = max(1, (row_width - pad * 2) // (font.width + font.spacing))
            text = text if len(text) <= max_chars else text[:max(1, max_chars - 1)] + "~"
            draw._text(x + pad, y, text, fg, font_size)

        for i, category in enumerate(self.categories):
            row(pad + 2, row_y + i * line_height, split - pad * 2 - 4,
                category, self.category == i, not self.focus_right)
        offset = max(0, self.index - available + 1)
        for i in range(offset, min(len(self.items), offset + available)):
            row(split + 2, row_y + (i - offset) * line_height,
                width - split - pad - 4, self.items[i], self.index == i, self.focus_right)
        if offset:
            draw._text(width - pad * 3, top + pad, "^", fg)
        if offset + available < len(self.items):
            draw._text(width - pad * 3, bottom - draw.font_size.y - pad, "v", fg)
        draw._fill_rectangle(0, height - footer, width, footer, accent)
        hint = "UP/DOWN: Move  ENTER: Open" if self.focus_right else "UP/DOWN: Browse  RIGHT: Open"
        draw._text(pad, height - footer + 3, hint, fg)
        draw._text(pad, height - draw.font_size.y - 2, "LEFT: Categories  ESC: Return", fg)
        draw.swap()
