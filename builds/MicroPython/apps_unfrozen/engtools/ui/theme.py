"""Shared firmware theme with PicoLAB breadcrumbs supplied by SD views."""
from picoware.gui.style import *
from picoware.gui import style as _style


def header(draw,subtitle='',brand='GungOS',palette=None,height=HEAD_HEIGHT,font=None):
    """Use firmware chrome, with a compact fallback for existing UF2 releases."""
    native=getattr(_style,'header',None)
    if native is not None:
        return native(draw,subtitle,brand,palette,height,font)
    # SD apps must still open before the matching firmware update is flashed.
    from picoware.assets.logos import LOGOS,paint
    p=palette or DEFAULT_PALETTE
    names={'GungOS':'gungOS_small','PicoDESK':'picodesk','PicoLAB':'picolab'}
    label=str(subtitle).strip(' /')
    if brand not in names:
        label=brand+(' / '+label if label else '')
        brand='PicoDESK' if brand in ('Eggcel','PicoWord','PicoPaint') else 'GungOS'
    draw._fill_rectangle(0,0,int(draw.size.x),height,p.PANEL)
    width,logo_height=LOGOS[names[brand]][:2]
    paint(draw,names[brand],7,(height-logo_height)//2,p.PANEL,p.ACCENT)
    label='/ '+label if label else ''
    while label and draw.len(label,0)>int(draw.size.x)-width-17:label=label[:-1]
    draw._text(width+11,(height-8)//2,label,p.TEXT,0)


def chrome(draw,subtitle,hint1,hint2,brand='PicoLAB',palette=None):
    p=palette or DEFAULT_PALETTE
    if brand not in ('PicoLAB','GRAPH','GRAPH 3D'):
        return _style.chrome(draw,subtitle,hint1,hint2,brand,p)
    from . import breadcrumbs
    fallback={'PicoLAB':(), 'GRAPH':('tools','Graph'), 'GRAPH 3D':('tools','Graph3D')}[brand]
    breadcrumbs.paint(draw,p,HEAD_HEIGHT,fallback,subtitle)
    width,height=int(draw.size.x),int(draw.size.y)
    bottom=height-FOOT_HEIGHT
    draw._fill_rectangle(0,bottom,width,FOOT_HEIGHT,p.PANEL)
    text(draw,6,bottom+5,hint1[:columns(draw,width-12)],p.ACCENT)
    text(draw,6,bottom+20,hint2[:columns(draw,width-12)],p.MUTED)


def menu(draw,rows,selected,subtitle='tools',brand='PicoLAB',
         hint1='UP/DOWN choose  ENTER open',hint2='ESC returns',row_colors=None,palette=None):
    p=palette or DEFAULT_PALETTE
    draw.fill_screen(p.BG)
    capacity=max(1,(int(draw.size.y)-HEAD_HEIGHT-FOOT_HEIGHT-12)//29)
    first=max(0,selected-capacity+1)
    for index in range(first,min(len(rows),first+capacity)):
        y=33+(index-first)*29
        if index==selected:
            draw._fill_rectangle(5,y-3,int(draw.size.x)-10,27,p.SELECT)
            draw._rectangle(5,y-3,int(draw.size.x)-10,27,p.ACCENT)
        label,detail=rows[index];limit=columns(draw,int(draw.size.x)-22)
        fg,muted=row_colors[index] if row_colors else (p.TEXT,p.MUTED)
        text(draw,11,y,label[:limit],fg)
        text(draw,11,y+12,detail[:limit],muted)
    chrome(draw,subtitle,hint1,hint2,brand,p)
    draw.swap()
