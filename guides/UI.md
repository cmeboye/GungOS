# Screen and control conventions

Every GungOS screen is built from the same few parts, so a key or a box means
the same thing everywhere. New screens use these parts instead of drawing
their own.

## Keys on every screen

| Key | Action |
|---|---|
| F9 | Show or close help: every key of the screen with its meaning |
| Escape | Close a box, cancel an edit or return to the previous screen |
| Home | Return to the desktop |
| Alt+S | Save a screenshot to the SD card |

F9 works while typing, because it is not a character key. Help never replaces
the screen: it opens in a box over it, the app waits behind it unchanged, and
closing the box puts the screen back exactly as it was.

## Parts

| Part | Use | Code |
|---|---|---|
| Header | Logo and the screen's path, such as `System / Info` | `style.header` |
| Footer | One line: `F9 Help`, then the latest message; errors also show in a red box above it | `style.footer` |
| Menu | Rows with an optional detail line; the chosen row is filled and outlined in the accent | `style.menu`, `Menu` |
| Page | Scrolling text between header and footer | `style.page`, `style.Page` |
| Box | A titled, scrollable box over the screen: help, alerts, information | `vm.show`, `vm.alert` |
| Popup | A box with options to choose from, such as No / Yes | `vm.choose` |

Pages and boxes take the same lines:

- `'Heading:'` — a line ending in a colon is a section heading.
- `'F5\tsave and run'` — a key, a tab and its meaning; the meaning wraps in its
  own column.
- Anything else is plain text and wraps to the box.

## Help for a screen

Give the module a `HELP` tuple of such lines. Views opened by the desktop,
the menus and `open_view` pick it up, and the system adds Home, Alt+S and F9 at
the end. `style.MENU_HELP`, `style.PAGE_HELP` and `style.KEYBOARD_HELP` cover
the common screens; add the keys the screen adds to them.

A screen whose keys change by mode either lists every mode under its own
heading, or sets `vm.help` when the mode changes. A view that must handle F9
itself (games and plots that pause their own work) leaves `HELP` out and draws
its help with `overlay.paint`, so the box looks the same.

Key hints do not go in the footer or on the screen; the footer keeps one place
for messages, and F9 lists the keys.
