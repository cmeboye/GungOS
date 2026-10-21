"""Shared GungOS menu colours and layout; independent of SD applications."""

BG = 0x0841
PANEL = 0x10A4
TEXT = 0xFFFF
MUTED = 0x7BEF
ACCENT = 0x07FF
SELECT = 0x0292
ERROR = 0xF800
GRID = 0x2125
AXIS = 0x632C
AMBER = 0xFD20
COLORS = (0x07FF, 0xFD20, 0xF81F, 0x07E0, 0xFFE0, 0xA51F)
HEAD_HEIGHT = 23
STATUS_HEIGHT = 16
# True while the screen shows the status strip; a header drawn at the top of
# the screen clears it, so the system never refreshes a strip that is gone.
_strip = False
FOOT_HEIGHT = 12
HELP_HINT = 'F9 Help'

# F9 help for a screen made of style.menu rows.
MENU_HELP = (
    'Menu:',
    'UP/DOWN\tchoose an item',
    'ENTER\topen the chosen item',
    'ESC\treturn to the previous screen',
)


class Palette:
    """Per-view colours; never mutate the shared engineering palette."""
    def __init__(self):
        self.BG,self.PANEL,self.TEXT,self.MUTED=BG,PANEL,TEXT,MUTED
        self.ACCENT,self.SELECT,self.ERROR=ACCENT,SELECT,ERROR
        self.GRID,self.AXIS=GRID,AXIS


DEFAULT_PALETTE=Palette()


def colors(background,foreground,accent):
    def mix(a,b,n,d):
        result=0
        for shift,mask in ((11,31),(5,63),(0,31)):
            result|=((((a>>shift)&mask)*(d-n)+((b>>shift)&mask)*n)//d)<<shift
        return result
    p=Palette()
    p.BG,p.TEXT,p.ACCENT=background,foreground,accent
    p.PANEL=mix(p.BG,p.TEXT,1,12)
    p.MUTED=mix(p.BG,p.TEXT,2,3)
    p.GRID=mix(p.BG,p.TEXT,1,5)
    p.AXIS=mix(p.BG,p.TEXT,1,2)
    p.SELECT=mix(p.BG,p.ACCENT,1,4)
    return p


def system_palette(vm):
    return colors(vm.background_color,vm.foreground_color,vm.selected_color)


def text(draw, x, y, value, color=TEXT):
    from picoware.system.font import FONT_SMALL
    draw._text(int(x), int(y), str(value), color, FONT_SMALL)


def columns(draw, pixel_width):
    from picoware.system.font import FONT_SMALL
    return max(1, int(pixel_width)//max(1, draw.len('M', FONT_SMALL)))


def status(vm):
    """Draw the status strip (clock, connections, battery) across the top.

    The system keeps it current while the view that drew it is on screen.
    Headers then start at STATUS_HEIGHT.
    """
    global _strip
    _strip = True
    vm.show_status()


def icon(draw, x, y, rows, palette):
    """Paint an 8x8 app icon: 'A' accent, 'T' text, anything else transparent."""
    for dy, row in enumerate(rows):
        start = None
        for dx in range(len(row) + 1):
            ink = row[dx] if dx < len(row) else '.'
            if start is not None and ink != row[start]:
                draw._fill_rectangle(x + start, y + dy, dx - start, 1,
                                     palette.ACCENT if row[start] == 'A' else palette.TEXT)
                start = None
            if start is None and ink in 'AT':
                start = dx


def header(draw, subtitle='', brand='GungOS', palette=None, height=HEAD_HEIGHT, font=None,
           top=0, rows=None):
    """Paint a logo/path header without swapping or covering the page body.

    top places it below the status strip; rows is the app's 8x8 icon,
    drawn between the brand logo and the path.
    """
    global _strip
    if top == 0:
        _strip = False
    from picoware.assets.logos import LOGOS, paint
    from picoware.system.font import FONT_SMALL, FONT_XTRA_SMALL
    p=palette or DEFAULT_PALETTE
    width=int(draw.size.x)
    names={'GungOS':'gungOS_small','PicoDESK':'picodesk','PicoLAB':'picolab'}
    # App-specific chart engines can identify themselves while retaining their
    # launcher's logo. Other tools default to the system brand.
    aliases={'Eggcel':'PicoDESK','PicoWord':'PicoDESK','PicoPaint':'PicoDESK'}
    original=brand
    brand=aliases.get(brand,brand)
    if brand not in names:
        brand='GungOS'
    label=str(subtitle).strip(' /')
    if original not in names:
        label=original+(' / '+label if label else '')
    label='/ '+label if label else ''
    origin,tall=top,height>=HEAD_HEIGHT
    draw._fill_rectangle(0,origin,width,height,p.PANEL)
    if tall:
        draw._fill_rectangle(0,origin,width,2,p.ACCENT)
    logo_width,logo_height=LOGOS[names[brand]][:2]
    top=origin+(2 if tall else 0)
    height=origin+height-top
    paint(draw,names[brand],7,top+(height-logo_height)//2,p.PANEL,p.ACCENT)
    x=logo_width+11
    if rows:
        icon(draw,x,top+(height-len(rows))//2,rows,p)
        x+=len(rows[0])+5
    available=max(0,width-x-6)
    if font is None:font=FONT_SMALL if tall else FONT_XTRA_SMALL
    if draw.len(label,font)>available:font=FONT_XTRA_SMALL
    if draw.len(label,font)>available:
        # Keep the current menu's name visible, even in a long nested path.
        tail=label[2:]
        while tail and draw.len('/ ...'+tail,font)>available:tail=tail[1:]
        label='/ ...'+tail
        if draw.len(label,font)>available:label=''
    text_height=int(draw.get_font(font).height)
    draw._text(x,top+(height-text_height)//2,label,p.TEXT,font)


def footer(draw, message='', error=False, palette=None, right=''):
    """One-line footer: the F9 help key, the latest message and optional
    right-aligned text. An error also shows in a box above the footer."""
    from picoware.system.font import FONT_XTRA_SMALL
    p=palette or DEFAULT_PALETTE
    width, height = int(draw.size.x), int(draw.size.y)
    bottom = height-FOOT_HEIGHT
    draw._fill_rectangle(0, bottom, width, FOOT_HEIGHT, p.PANEL)
    draw._text(6, bottom+2, HELP_HINT, p.ACCENT, FONT_XTRA_SMALL)
    end = width-6
    if right:
        end -= draw.len(right, FONT_XTRA_SMALL)
        draw._text(end, bottom+2, right, p.MUTED, FONT_XTRA_SMALL)
        end -= 6
    if message:
        left = 12+draw.len(HELP_HINT, FONT_XTRA_SMALL)
        chars = max(0, (end-left)//max(1, draw.len('M', FONT_XTRA_SMALL)))
        draw._text(left, bottom+2, str(message)[:chars], p.ERROR if error else p.MUTED, FONT_XTRA_SMALL)
    if error and message:
        from picoware.gui.overlay import wrap
        lines = wrap(message, max(1, (width-32)//6))[:2]
        h = 10*len(lines)+8
        y = bottom-h-3
        draw._fill_rectangle(8, y, width-16, h, p.BG)
        draw._rectangle(8, y, width-16, h, p.ERROR)
        for i, line in enumerate(lines):
            draw._text(16, y+4+10*i, line, p.ERROR, FONT_XTRA_SMALL)


def chrome(draw, subtitle, message='', brand='GungOS', palette=None, error=False):
    """Header with the screen's path and the one-line footer."""
    header(draw, subtitle, brand, palette)
    footer(draw, message, error, palette)


def menu(draw, rows, selected, subtitle='tools', brand='GungOS',
         message='', row_colors=None, palette=None, error=False):
    """Draw (label, detail) rows without allocating a native menu widget."""
    p=palette or DEFAULT_PALETTE
    draw.fill_screen(p.BG)
    capacity = max(1, (int(draw.size.y)-HEAD_HEIGHT-FOOT_HEIGHT-12)//29)
    first = max(0, selected-capacity+1)
    for index in range(first, min(len(rows), first+capacity)):
        y = 33+(index-first)*29
        if index == selected:
            draw._fill_rectangle(5, y-3, int(draw.size.x)-10, 27, p.SELECT)
            draw._rectangle(5, y-3, int(draw.size.x)-10, 27, p.ACCENT)
        label, detail = rows[index]
        limit = columns(draw, int(draw.size.x)-22)
        label_color, detail_color = row_colors[index] if row_colors else (p.TEXT, p.MUTED)
        text(draw, 11, y, label[:limit], label_color)
        text(draw, 11, y+12, detail[:limit], detail_color)
    chrome(draw, subtitle, message, brand, p, error)
    draw.swap()


def page(draw, subtitle, lines, first, brand='GungOS', palette=None, message='', error=False):
    """A scrolling page between header and footer, presented at once.

    Lines are laid out by picoware.gui.overlay.layout(lines, width) for a
    full-width page; returns how many fit, the step of a page scroll.
    """
    from picoware.gui import overlay
    p=palette or DEFAULT_PALETTE
    width, height = int(draw.size.x), int(draw.size.y)
    draw.fill_screen(p.BG)
    top, bottom = HEAD_HEIGHT+8, height-FOOT_HEIGHT-4
    count = max(1, (bottom-top)//overlay.PITCH)
    first = max(0, min(first, len(lines)-count))
    overlay.text(draw, p, 10, top, width-28, lines[first:first+count])
    if len(lines) > count:
        track = bottom-top
        thumb = max(8, track*count//len(lines))
        y = top+(track-thumb)*first//max(1, len(lines)-count)
        draw._line(width-6, top, width-6, top+track, p.GRID)
        draw._fill_rectangle(width-7, y, 3, thumb, p.ACCENT)
    header(draw, subtitle, brand, p)
    footer(draw, message, error, p,
           '%d-%d / %d' % (first+1, min(len(lines), first+count), len(lines)) if len(lines) > count else '')
    draw.swap()
    return count


# F9 help for text typed on the on-screen keyboard (picoware.gui.keyboard).
KEYBOARD_HELP = (
    'Typing:',
    'Keys\ttype straight into the field',
    'Arrows\tmove on the on-screen keyboard',
    'ENTER\tpress the highlighted key',
    'UP (top row)\tedit the text; LEFT/RIGHT move',
    'ENTER (text)\tsave the text',
    'BACK\terase before the cursor',
    'ESC\tcancel without saving',
)

# F9 help for a style.page screen.
PAGE_HELP = (
    'Page:',
    'UP/DOWN\tscroll one line',
    'LEFT/RIGHT\tscroll one page',
    'ESC\treturn to the previous screen',
)


class Page:
    """Scrolling text for a whole screen: style.page plus its scroll keys."""
    def __init__(self, vm, subtitle, lines, brand='GungOS'):
        self.vm, self.subtitle, self.brand = vm, subtitle, brand
        self.first, self.count, self.message, self.error = 0, 1, '', False
        self.set_lines(lines)
    def set_lines(self, lines):
        from picoware.gui.overlay import layout
        self.source = lines
        self.lines = layout(lines, int(self.vm.draw.size.x)-8)
    def invalidate(self):
        """Something else drew over the screen: the next update redraws."""
        self.source = None
    def update(self, lines, message='', error=False):
        """Show these lines and footer message; redraws only on a change."""
        if lines != self.source or message != self.message or error != self.error:
            self.message, self.error = message, error
            self.set_lines(lines)
            self.draw()
    def key(self, button):
        """Scroll for UP/DOWN/LEFT/RIGHT and redraw; False for other keys."""
        from picoware.system import buttons as k
        step = {k.BUTTON_UP: -1, k.BUTTON_DOWN: 1,
                k.BUTTON_LEFT: -self.count, k.BUTTON_RIGHT: self.count}.get(button)
        if step is None:
            return False
        self.first = max(0, min(len(self.lines)-self.count, self.first+step))
        self.draw()
        return True
    def draw(self):
        self.count = page(self.vm.draw, self.subtitle, self.lines, self.first, self.brand,
                          system_palette(self.vm), self.message, self.error)
        self.first = max(0, min(self.first, len(self.lines)-self.count))
