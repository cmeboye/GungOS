"""Bounded spreadsheet ranges to sampled XY specifications for the shared viewer."""
from .formulas import ROWS,COLS,CellError,address,reference,finite


def column_range(top,col,bottom):
    return address(top,col)+(':'+address(bottom,col) if bottom!=top else '')


def parse_range(text):
    """Accept a single cell or vertical A1:A200 range; $ anchors are allowed."""
    parts=text.strip().split(':')
    if not 1<=len(parts)<=2 or any(not part.strip() for part in parts):
        raise ValueError('Use a range such as A2:A20')
    try:
        first=reference(parts[0].strip())
        last=reference(parts[-1].strip())
    except CellError:
        raise ValueError('Range must be inside A1:Z200')
    if first[1]!=last[1] or first[0]>last[0]:
        raise ValueError('Use one column, top to bottom')
    return first[0],first[1],last[0]


def defaults(sheet,bounds):
    top,left,bottom,right=bounds
    x='' if left==right else column_range(top,left,bottom)
    columns=[left] if left==right else list(range(left+1,min(right,left+3)+1))
    ys=[column_range(top,col,bottom) for col in columns]
    ys+=['']*(3-len(ys))
    header=any(isinstance(sheet.cache.get((top,col)) if sheet.cells.get((top,col),'').startswith('=') else sheet.peek((top,col)),str) for col in ([left]+columns))
    return {'style':'line','x':x,'ys':ys,'header':header}


def numeric(value):
    return type(value) in (int,float) and finite(value)


def series_colors(vm):
    # Independent hues for light/dark backgrounds; the first series follows the
    # system theme. Marker shapes also distinguish all three series.
    colors=[vm.selected_color]
    bg=vm.background_color
    light=((bg>>11)&31)*299/31+((bg>>5)&63)*587/63+(bg&31)*114/31>540
    candidates=(0xB300,0x880F,0x0300,0x001F) if light else (0xFD20,0xF81F,0x07E0,0xFFFF)
    for color in candidates:
        if all(sum(abs(((color>>s)&m)-((other>>s)&m)) for s,m in ((11,31),(5,63),(0,31)))>20 for other in colors):
            colors.append(color)
        if len(colors)==3: return colors
    return colors


def build_spec(sheet,options,vm):
    style=options.get('style')
    if style in ('column','pie'):return build_categories(sheet,options,vm)
    if style not in ('line','scatter'): raise ValueError('Choose XY lines or XY scatter')
    fields=options.get('ys',[])
    if len(fields)!=3: raise ValueError('Use up to three Y ranges')
    ys=[(index,parse_range(value)) for index,value in enumerate(fields) if value.strip()]
    if not ys: raise ValueError('Enter at least one Y range')
    x=parse_range(options['x']) if options.get('x','').strip() else None
    length=(x[2]-x[0]+1) if x else ys[0][1][2]-ys[0][1][0]+1
    if any(end-start+1!=length for _,(start,col,end) in ys):
        raise ValueError('X and Y ranges must have equal lengths')
    header=bool(options.get('header'))
    if length-int(header)<1: raise ValueError('No data rows below the header')
    colors=series_colors(vm)
    series=[];box=None;gaps=0
    for ordinal,(field,(start,col,end)) in enumerate(ys):
        name=sheet.value((start,col)) if header else None
        name=name if isinstance(name,str) and name.strip() else 'Column '+chr(65+col)
        points=[];valid=0
        for offset in range(int(header),length):
            xv=sheet.value((x[0]+offset,x[1])) if x else start+offset+1
            yv=sheet.value((start+offset,col))
            if not numeric(xv) or not numeric(yv):
                points.append((None,None));gaps+=1;continue
            if abs(xv)>1e12 or abs(yv)>1e12: raise ValueError('Coordinates exceed graph limits')
            points.append((xv,yv));valid+=1
            if box is None: box=[xv,xv,yv,yv]
            else: box=[min(box[0],xv),max(box[1],xv),min(box[2],yv),max(box[3],yv)]
        if not valid: raise ValueError('Y%d has no numeric pairs'%(field+1))
        series.append({'type':'samples','name':name[:40],'points':points,'style':style,
                       'color':colors[ordinal],'marker':('square','cross','diamond')[ordinal]})
    for i in (0,2):
        pad=max((box[i+1]-box[i])*0.1,abs(box[i])*0.05 if box[i]==box[i+1] else 0,1e-6)
        box[i]-=pad;box[i+1]+=pad
    from engtools.plots.plot2d import valid_bounds
    if not valid_bounds(box): raise ValueError('Data exceeds graph range; scale values')
    xlabel=sheet.value((x[0],x[1])) if x and header else None
    xlabel=xlabel if isinstance(xlabel,str) and xlabel.strip() else ('Column '+chr(65+x[1]) if x else 'Worksheet row')
    return {'title':'XY lines' if style=='line' else 'XY scatter','system_theme':True,'data_only':True,
            'series':series,'bounds':box,'legend':True,'axes':{'x':{'label':xlabel[:32]},'y':{'label':'Value'}},
            'note':str(gaps)+' gaps: blank / text / error' if gaps else ''}


def build_categories(sheet,options,vm):
    """Categorical columns and positive-only pie data; invalid bars stay gaps."""
    kind=options['style'];fields=options.get('ys',[])
    if len(fields)!=3:raise ValueError('Use up to three value ranges')
    enabled=[(i,parse_range(v)) for i,v in enumerate(fields) if v.strip() and (kind!='pie' or i==0)]
    if not enabled:raise ValueError('Enter Y1 values for the chart')
    labels_range=parse_range(options['x']) if options.get('x','').strip() else None
    length=enabled[0][1][2]-enabled[0][1][0]+1;header=int(bool(options.get('header')))
    if any(b-a+1!=length for _,(a,c,b) in enabled) or (labels_range and labels_range[2]-labels_range[0]+1!=length):
        raise ValueError('Labels and values need equal lengths')
    if length<=header:raise ValueError('No data below the header')
    if length-header>200:raise ValueError('Column chart limit: 200 categories')
    labels=[]
    for offset in range(header,length):
        value=sheet.value((labels_range[0]+offset,labels_range[1])) if labels_range else None
        if isinstance(value,CellError):raise ValueError('Chart label contains '+value.code)
        labels.append(str(value) if value is not None and str(value).strip() else str(enabled[0][1][0]+offset+1))
    series=[];gaps=0;low=high=0.;colors=series_colors(vm)
    for ordinal,(index,(start,col,end)) in enumerate(enabled):
        title=sheet.value((start,col)) if header else None
        title=title if isinstance(title,str) and title.strip() else 'Column '+chr(65+col)
        values=[];valid=0
        for offset in range(header,length):
            value=sheet.value((start+offset,col))
            if not numeric(value):
                if kind=='pie':raise ValueError('Pie requires numeric values: '+address(start+offset,col))
                values.append(None);gaps+=1;continue
            if abs(value)>1e12:raise ValueError('Chart values exceed 1e12; scale data')
            if kind=='pie' and value<0:raise ValueError('Pie values cannot be negative')
            values.append(value);valid+=1;low=min(low,value);high=max(high,value)
        if not valid:raise ValueError('No numeric values in '+title)
        series.append({'name':title[:40],'values':values,'color':colors[ordinal]})
    if kind=='pie':
        values=series[0]['values'];items=[(label,value) for label,value in zip(labels,values) if value>0]
        if not items:raise ValueError('Pie total must be greater than zero')
        if len(items)>24:raise ValueError('Pie limit: 24 positive slices; choose a smaller range')
        return {'kind':'pie','title':series[0]['name'],'items':items,'total':sum(value for label,value in items),
                'note':str(len(values)-len(items))+' zero values omitted' if len(items)!=len(values) else ''}
    if low==high:high=1.
    return {'kind':'column','title':'2D column','labels':labels,'series':series,'bounds':(low,high),
            'note':str(gaps)+' gaps: blank / text / error' if gaps else ''}
