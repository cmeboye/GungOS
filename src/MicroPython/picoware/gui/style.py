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
FOOT_HEIGHT = 36


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


def header(draw, subtitle='', brand='GungOS', palette=None, height=HEAD_HEIGHT, font=None):
    """Paint a logo/path header without swapping or covering the page body."""
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
    draw._fill_rectangle(0,0,width,height,p.PANEL)
    if height>=HEAD_HEIGHT:
        draw._fill_rectangle(0,0,width,2,p.ACCENT)
    logo_width,logo_height=LOGOS[names[brand]][:2]
    top=2 if height>=HEAD_HEIGHT else 0
    paint(draw,names[brand],7,top+(height-top-logo_height)//2,p.PANEL,p.ACCENT)
    x=logo_width+11
    available=max(0,width-x-6)
    if font is None:font=FONT_SMALL if height>=HEAD_HEIGHT else FONT_XTRA_SMALL
    if draw.len(label,font)>available:font=FONT_XTRA_SMALL
    if draw.len(label,font)>available:
        # Keep the current menu's name visible, even in a long nested path.
        tail=label[2:]
        while tail and draw.len('/ ...'+tail,font)>available:tail=tail[1:]
        label='/ ...'+tail
        if draw.len(label,font)>available:label=''
    text_height=int(draw.get_font(font).height)
    draw._text(x,top+(height-top-text_height)//2,label,p.TEXT,font)


def chrome(draw, subtitle, hint1, hint2, brand='GungOS', palette=None):
    p=palette or DEFAULT_PALETTE
    width, height = int(draw.size.x), int(draw.size.y)
    header(draw,subtitle,brand,p)
    bottom = height-FOOT_HEIGHT
    draw._fill_rectangle(0, bottom, width, FOOT_HEIGHT, p.PANEL)
    text(draw, 6, bottom+5, hint1[:columns(draw, width-12)], p.ACCENT)
    text(draw, 6, bottom+20, hint2[:columns(draw, width-12)], p.MUTED)


def menu(draw, rows, selected, subtitle='tools', brand='GungOS',
         hint1='UP/DOWN choose  ENTER open', hint2='ESC returns', row_colors=None, palette=None):
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
    chrome(draw, subtitle, hint1, hint2, brand,p)
    draw.swap()
