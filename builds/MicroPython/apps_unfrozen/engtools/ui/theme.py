"""Shared firmware theme with PicoLAB breadcrumbs supplied by SD views."""
from picoware.gui.style import *
from picoware.gui import style as _style


# Status strip height; firmware without the strip leaves the top row blank.
STRIP=getattr(_style,'STATUS_HEIGHT',16)


def status(vm,palette=None):
    """The firmware's status strip, or a blank strip on firmware without it."""
    native=getattr(_style,'status',None)
    if native is not None:return native(vm)
    p=palette or DEFAULT_PALETTE
    vm.draw._fill_rectangle(0,0,int(vm.draw.size.x),STRIP,p.BG)


def header(draw,subtitle='',brand='GungOS',palette=None,height=HEAD_HEIGHT,font=None,top=0,rows=None):
    """Use firmware chrome, with a compact fallback for existing UF2 releases.
    top places the header below the status strip; rows is the app's 8x8 icon."""
    native=getattr(_style,'header',None)
    if native is not None and hasattr(_style,'status'):
        return native(draw,subtitle,brand,palette,height,font,top,rows)
    if top==0 and native is not None:
        return native(draw,subtitle,brand,palette,height,font)
    # SD apps must still open before the matching firmware update is flashed.
    from picoware.assets.logos import LOGOS,paint
    p=palette or DEFAULT_PALETTE
    names={'GungOS':'gungOS_small','PicoDESK':'picodesk','PicoLAB':'picolab'}
    label=str(subtitle).strip(' /')
    if brand not in names:
        label=brand+(' / '+label if label else '')
        brand='PicoDESK' if brand in ('Eggcel','PicoWord','PicoPaint') else 'GungOS'
    draw._fill_rectangle(0,top,int(draw.size.x),height,p.PANEL)
    width,logo_height=LOGOS[names[brand]][:2]
    paint(draw,names[brand],7,top+(height-logo_height)//2,p.PANEL,p.ACCENT)
    label='/ '+label if label else ''
    while label and draw.len(label,0)>int(draw.size.x)-width-17:label=label[:-1]
    draw._text(width+11,top+(height-8)//2,label,p.TEXT,0)


def footer(draw,message='',error=False,palette=None):
    """The firmware's one-line F9 Help footer, with a fallback for older UF2s."""
    native=getattr(_style,'footer',None)
    if native is not None:
        return native(draw,message,error,palette)
    p=palette or DEFAULT_PALETTE
    width,height=int(draw.size.x),int(draw.size.y)
    draw._fill_rectangle(0,height-12,width,12,p.PANEL)
    draw._text(6,height-10,'F9 Help',p.ACCENT,0)
    if message:draw._text(54,height-10,str(message)[:(width-60)//6],p.ERROR if error else p.MUTED,0)


def chrome(draw,subtitle,message='',brand='PicoLAB',palette=None,error=False):
    p=palette or DEFAULT_PALETTE
    if brand in ('PicoLAB','GRAPH','GRAPH 3D'):
        from . import breadcrumbs
        fallback={'PicoLAB':(), 'GRAPH':('tools','Graph'), 'GRAPH 3D':('tools','Graph3D')}[brand]
        breadcrumbs.paint(draw,p,HEAD_HEIGHT,fallback,subtitle)
    else:
        header(draw,subtitle,brand,p)
    footer(draw,message,error,p)


def menu(draw,rows,selected,subtitle='tools',brand='PicoLAB',
         message='',row_colors=None,palette=None,error=False,vm=None):
    """(label, detail) rows. With vm, the status strip and the compact
    18-pixel header of the PicoDESK screens sit above them."""
    p=palette or DEFAULT_PALETTE
    draw.fill_screen(p.BG)
    head=STRIP+18 if vm is not None else HEAD_HEIGHT
    capacity=max(1,(int(draw.size.y)-head-FOOT_HEIGHT-12)//29)
    first=max(0,selected-capacity+1)
    for index in range(first,min(len(rows),first+capacity)):
        y=head+10+(index-first)*29
        if index==selected:
            draw._fill_rectangle(5,y-3,int(draw.size.x)-10,27,p.SELECT)
            draw._rectangle(5,y-3,int(draw.size.x)-10,27,p.ACCENT)
        label,detail=rows[index];limit=columns(draw,int(draw.size.x)-22)
        fg,muted=row_colors[index] if row_colors else (p.TEXT,p.MUTED)
        text(draw,11,y,label[:limit],fg)
        text(draw,11,y+12,detail[:limit],muted)
    if vm is None:
        chrome(draw,subtitle,message,brand,p,error)
    else:
        status(vm,p)
        header(draw,subtitle,brand,p,18,top=STRIP)
        footer(draw,message,error,p)
    draw.swap()
