"""Shared PicoLAB screen parts: the title bar, panels, menus, property forms
with inline editing, choice lists, prompts and the F9 help box.

Beam view, Graph and Graph3D draw through these, so every tool looks and
answers the keys the same way. Nothing here allocates a framebuffer;
Viewport keeps drawing inside its panel.
"""
from picoware.system.font import FONT_XTRA_SMALL as XS, FONT_SMALL as SM
from .viewport import Viewport

HEAD = 38   # breadcrumb (18) and title bar (20)
FOOT = 12   # one line: F9 Help and the latest message
ROW = 15    # property form row


def mix(a, b, n, d):
    out = 0
    for shift, mask in ((11, 31), (5, 63), (0, 31)):
        out |= ((((a >> shift) & mask) * (d - n) + ((b >> shift) & mask) * n) // d) << shift
    return out


def text(draw, x, y, value, color, font=XS):
    draw._text(int(x), int(y), str(value), color, font)


def right_text(draw, x, y, value, color, font=XS):
    value = str(value)
    draw._text(int(x - draw.len(value, font)), int(y), value, color, font)


def centre_text(draw, x, y, value, color, font=XS, low=16, high=304):
    value = str(value)
    w = draw.len(value, font)
    left = min(max(int(x - w // 2), low), high - w)
    draw._text(left, int(y), value, color, font)


def wrap(value, width):
    words, lines, line = str(value).split(), [], ''
    for word in words:
        if line and len(line) + 1 + len(word) > width:
            lines.append(line)
            line = word
        else:
            line = line + ' ' + word if line else word
    if line:
        lines.append(line)
    return lines


def panel(draw, p, rect, title, status='', fill=None):
    x,y,w,h=rect
    draw._fill_rectangle(x,y,w,h,p.BG if fill is None else fill)
    draw._rectangle(x,y,w,h,p.GRID)
    bounded=Viewport(draw,(x+5,y+4,x+w-5,y+h-4))
    text(bounded,x+8,y+7,title,p.ACCENT)
    if status:right_text(bounded,x+w-8,y+7,status,p.MUTED)


def tabs(draw,p,rect,labels,selected,counts,font=SM,height=22):
    """Theme-coloured tabs contained in the property panel's header."""
    from picoware.gui.status_bar import foreground
    x,y,w,h=rect
    panel(draw,p,rect,'')
    width=w-2
    text_y=y+(height-draw.get_font(font).height)//2
    for i,label in enumerate(labels):
        left=x+1+i*width//len(labels)
        right=x+1+(i+1)*width//len(labels)
        active=i==selected
        color=p.ACCENT if active else p.PANEL
        draw._fill_rectangle(left,y+1,right-left,height-2,color)
        title=label+' '+str(counts[i])
        text(draw,left+(right-left-draw.len(title,font))//2,text_y,title,
             foreground(color) if active else p.MUTED,font)
    draw._line(x+1,y+height-1,x+w-2,y+height-1,p.GRID)


def chrome(draw,p,page,message='',error=False,title='BEAM VIEW',fallback=('modules','structural','Beam view'),
           hint='F9 Help',brand='PicoLAB'):
    """Breadcrumb, app title bar with the page name, and a one-line footer.
    A PicoLAB tool shows its breadcrumb; another brand (a PicoDESK app
    embedding a plot) shows that brand with the fallback path."""
    if brand=='PicoLAB':
        from engtools.ui import breadcrumbs
        breadcrumbs.paint(draw,p,fallback=fallback)
    else:
        from engtools.ui import theme
        theme.header(draw,' / '.join(fallback),brand,p,18,font=XS)
    width,height=int(draw.size.x),int(draw.size.y)
    draw._fill_rectangle(0,18,width,20,p.PANEL)
    text(draw,8,22,title,p.ACCENT,SM)
    right_text(draw,width-8,24,page.upper(),p.TEXT)
    bottom=height-12
    draw._fill_rectangle(0,bottom,width,12,p.PANEL)
    text(draw,6,bottom+2,hint,p.ACCENT)
    if message:
        left=12+draw.len(hint,XS)
        text(draw,left,bottom+2,message[:max(1,(width-left-4)//6)],p.ERROR if error else p.MUTED)
    if error and message:
        lines=wrap(message,max(1,(width-32)//6))[:2]
        h=10*len(lines)+8
        y=bottom-h-3
        draw._fill_rectangle(8,y,width-16,h,p.BG)
        draw._rectangle(8,y,width-16,h,p.ERROR)
        for i,line in enumerate(lines):text(draw,16,y+4+10*i,line,p.ERROR)


def menu(draw,p,rows,selected,title,bottom,colors=None):
    """(label, detail) rows in a panel; colors: optional (label, detail) per row."""
    panel(draw,p,(8,43,int(draw.size.x)-16,bottom-46),title)
    top=67;capacity=max(1,(bottom-6-top)//29)
    first=min(max(0,selected-capacity//2),max(0,len(rows)-capacity))
    bounded=Viewport(draw,(12,64,int(draw.size.x)-12,bottom-6))
    for i in range(first,min(len(rows),first+capacity)):
        y=top+(i-first)*29
        if i==selected:
            bounded._fill_rectangle(14,y-2,int(draw.size.x)-28,27,p.SELECT)
            bounded._rectangle(14,y-2,int(draw.size.x)-29,26,p.ACCENT)
        label,detail=rows[i]
        fg,muted=colors[i] if colors else (p.TEXT,p.MUTED)
        text(bounded,20,y,label,fg,SM)
        text(bounded,20,y+14,detail,muted)
    right_text(draw,int(draw.size.x)-16,50,'%d/%d'%(selected+1,len(rows)),p.MUTED)


def form(draw, p, rows, selected, edit, top, bottom, font=SM, row_height=ROW):
    """Scroll properties inside their panel, retaining inline edit and units."""
    label_offset=(draw.get_font(font).height-draw.get_font(XS).height)//2
    left,right=12,int(draw.size.x)-12
    draw=Viewport(draw,(left,top-3,right,bottom))
    capacity=max(1,(bottom-top)//row_height)
    first=min(max(0,selected-capacity//2),max(0,len(rows)-capacity))
    for index in range(first,min(len(rows),first+capacity)):
        kind,label,value,editable=rows[index]
        y=top+(index-first)*row_height;chosen=index==selected
        if chosen:
            draw._fill_rectangle(left+2,y-2,right-left-4,row_height,p.SELECT)
            draw._rectangle(left+2,y-2,right-left-4,row_height,p.ACCENT)
        if kind=='head':
            draw._fill_rectangle(left+2,y-2,3,row_height,p.ACCENT)
            text(draw,left+10,y,label,p.TEXT,font)
            continue
        label_end=right-155
        label_draw=Viewport(draw,(left,top-3,label_end,bottom))
        text(label_draw,left+12,y+label_offset,label,p.MUTED)
        if chosen and edit is not None:
            unit=value.split(' ')[-1] if ' ' in value else ''
            uw=draw.len(unit,XS)+4 if unit else 0
            box=150;x=right-box-5
            draw._fill_rectangle(x,y-1,box,row_height-2,p.BG)
            edit.draw(draw,x+3,y,box-8-uw,p.TEXT,p.ACCENT,font)
            if unit:right_text(draw,right-6,y+label_offset,unit,p.MUTED)
        else:
            value_draw=Viewport(draw,(label_end+2,top-3,right-5,bottom))
            right_text(value_draw,right-6,y,value,p.TEXT if editable else p.MUTED,font)
    if first:
        draw._fill_triangle(right-4,top-2,right-7,top+1,right-1,top+1,p.MUTED)
    if first+capacity<len(rows):
        y=top+capacity*row_height-3
        draw._fill_triangle(right-4,y+2,right-7,y-1,right-1,y-1,p.MUTED)


def popup(draw,p,title,options,selected,box=None):
    if box is None:
        width,height=int(draw.size.x),int(draw.size.y)
        h=min(24+min(len(options),8)*17,height-70)
        box=(20,max(43,(height-h)//2),width-40,h)
    x,y,w,h=box
    panel(draw,p,box,title,'%d/%d'%(selected+1,len(options)),p.PANEL)
    bounded=Viewport(draw,(x+4,y+22,x+w-4,y+h-4))
    # A short box (Beam view's model list) packs rows to show three.
    pitch=17 if h>=26+3*17 else 15
    capacity=max(1,(h-26)//pitch)
    first=min(max(0,selected-capacity//2),max(0,len(options)-capacity))
    for index in range(first,min(len(options),first+capacity)):
        yy=y+25+(index-first)*pitch
        if index==selected:
            bounded._fill_rectangle(x+5,yy-2,w-10,pitch-1,p.SELECT)
            bounded._rectangle(x+5,yy-2,w-10,pitch-1,p.ACCENT)
        text(bounded,x+12,yy,options[index],p.TEXT,SM)


def prompt(draw,p,title,detail,edit,message,error,box=None):
    if box is None:box=(8,43,int(draw.size.x)-16,int(draw.size.y)-60)
    x,y,w,h=box
    panel(draw,p,box,title)
    bounded=Viewport(draw,(x+5,y+22,x+w-5,y+h-4))
    lines=wrap(detail,max(1,(w-24)//6))[:2 if h>=110 else 1]
    for i,line in enumerate(lines):text(bounded,x+10,y+25+10*i,line,p.MUTED)
    ey=y+29+10*len(lines)
    bounded._rectangle(x+8,ey,w-17,20,p.ACCENT)
    edit.draw(bounded,x+14,ey+4,w-33,p.TEXT,p.ACCENT,SM)
    text(bounded,x+10,ey+26,message,p.ERROR if error else p.MUTED)


def results(draw, p, rows, selected, top, bottom):
    """A scrolling results list. Rows are (label, value, detail, color or
    None); a row with no value and no detail is a section heading."""
    width = int(draw.size.x)
    capacity = max(1, (bottom - top) // 26)
    first = min(max(0, selected - capacity // 2), max(0, len(rows) - capacity))
    for index in range(first, min(len(rows), first + capacity)):
        label, value, detail, color = rows[index]
        y = top + (index - first) * 26
        if value is None and not detail:
            text(draw, 14, y + 10, label, p.ACCENT)
            draw._line(14 + draw.len(label, XS) + 4, y + 14, width - 14, y + 14, p.GRID)
            continue
        if index == selected:
            draw._fill_rectangle(12, y - 2, width - 24, 25, p.SELECT)
            draw._rectangle(12, y - 2, width - 24, 25, p.ACCENT)
        text(draw, 16, y, label[:22], p.TEXT, SM)
        if value is not None:
            right_text(draw, width - 16, y, value, color or p.ACCENT, SM)
        text(draw, 16, y + 13, detail[:46], p.MUTED)


def help_capacity(bottom):
    return max(1,(bottom-98)//11)


def help_box(draw,p,lines,first,bottom):
    try:from picoware.gui import overlay
    except ImportError:overlay=None  # firmware without the shared box
    if overlay is not None:
        overlay.paint(draw,p,(8,43,int(draw.size.x)-16,bottom-46),'KEYBINDINGS',lines,first)
        return
    capacity=help_capacity(bottom)
    right=int(draw.size.x)-8
    panel(draw,p,(8,43,right-8,bottom-46),'KEYBINDINGS',
          '%d-%d / %d'%(first+1,min(first+capacity,len(lines)),len(lines)))
    bounded=Viewport(draw,(14,65,right-12,bottom-25))
    for i,line in enumerate(lines[first:first+capacity]):
        text(bounded,18 if line.endswith(':') else 22,67+11*i,line,p.ACCENT if line.endswith(':') else p.TEXT)
    # Scroll thumb and compact instructions stay inside the help box.
    track=bottom-95
    thumb=max(8,track*min(capacity,len(lines))//len(lines))
    top=66+(track-thumb)*first//max(1,len(lines)-capacity)
    draw._line(right-6,66,right-6,66+track,p.GRID)
    draw._fill_rectangle(right-7,top,3,thumb,p.ACCENT)
    text(draw,18,bottom-17,'UP/DOWN scroll   F9 / ESC close',p.MUTED)
