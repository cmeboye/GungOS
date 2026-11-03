"""Read-only bounded MathML boxes using calculator drawing/clipping primitives."""
from engtools.calculator.render import Renderer,Box
from .mathglyphs import PATTERNS,ALIASES

ALLOWED={'math':('display','alttext','xmlns'), 'mo':('stretchy',),
         'mfrac':('bevelled',),'mfenced':('open','close','separators'),
         'mover':('accent',),'munder':('accentunder',),
         'mstyle':('displaystyle','mathsize','scriptlevel'),
         'mtable':('equalcolumns','equalrows','columnalign'),
         'mtr':('columnalign',),'mtd':('columnalign',)}
REQUIRED={'mfrac':2,'msup':2,'msub':2,'msubsup':3,'mroot':2,'mover':2,'munder':2,'munderover':3}

class MathRenderer(Renderer):
    def row(self,boxes,font):
        ch=self.metrics[font][1]
        above=max([ch]+[b.base for b in boxes]);below=max([0]+[b.h-b.base for b in boxes])
        height=above+below;x=0;children=[]
        for b in boxes:
            fence=b if b.kind=='fence' else (b.children[0][0] if b.kind=='mathrow' and len(b.children)==1 and b.children[0][0].kind=='fence' else None)
            if fence and fence.value[1]:
                fence.h=height;fence.base=above;b.h=height;b.base=above
            children.append((b,x,above-b.base));x+=b.w
        return Box('mathrow',x,height,above,font,children=children)

    def token(self,text,font,stretch=True):
        text=''.join(ALIASES.get(c,c) for c in text)
        cw,ch=self.metrics[font];boxes=[]
        for c in text:
            if c in ('¼','½','¾'):
                a,b={'¼':('1','4'),'½':('1','2'),'¾':('3','4')}[c]
                small=max(0,font-1);top=self.token(a,small);bottom=self.token(b,small);w=max(top.w,bottom.w)+8
                b=Box('mathfrac',w,top.h+bottom.h+7,top.h+3+ch//2,font,children=[(top,(w-top.w)//2,0),(bottom,(w-bottom.w)//2,top.h+7)])
            elif c in '()[]{}|':
                b=Box('fence',cw,ch,ch,font,(c,stretch))
            elif c in ('∑','∏','∫','∭'):
                b=Box('operator',20 if c in ('∑','∏') else (30 if c=='∭' else 13),max(24,ch+8),max(24,ch+8)-3,font,c)
            elif 32<=ord(c)<=126:b=Box('mathtext',cw,ch,ch,font,c)
            elif c in PATTERNS:b=Box('symbol',cw,ch,ch,font,c)
            else:raise ValueError('Unsupported math symbol U+%04X'%ord(c))
            boxes.append(b)
        return boxes[0] if len(boxes)==1 else self.row(boxes,font)

    def validate(self,node):
        tag=node.tag;attrs=node.attrs
        # Reject semantic attributes this prototype cannot honour.
        for key in attrs:
            if key in ('id','class','xmlns') or key.startswith('xmlns:'):continue
            if key not in ALLOWED.get(tag,()):raise ValueError('Unsupported MathML attribute: '+tag+'/'+key)

    def layout_math(self,node,font=2):
        tag=node.tag;attrs=node.attrs;nodes=node.children
        self.validate(node)
        if tag in ('mi','mn','mo','mtext','ms'):
            if any(not isinstance(c,str) for c in nodes):raise ValueError('Nested MathML token')
            text=''.join(nodes)
            if tag!='mtext':text=text.strip()
            if '&' in text and ';' in text:raise ValueError('Unresolved MathML entity')
            if tag=='ms':text='"'+text+'"'
            return self.token(text,font,attrs.get('stretchy','true')!='false')
        if any(isinstance(c,str) for c in nodes):raise ValueError('Invalid MathML structure')
        if tag in ('math','mrow','mstyle'):
            if tag=='mstyle':
                if attrs.get('scriptlevel') not in (None,'+1'):raise ValueError('Unsupported MathML script level')
                if attrs.get('mathsize') not in (None,'140%'):raise ValueError('Unsupported MathML size')
                if attrs.get('scriptlevel')=='+1':font=max(0,font-1)
                if attrs.get('mathsize')=='140%':font=min(4,font+1)
            return self.row([self.layout_math(c,font) for c in nodes],font)
        if tag in ('maligngroup','malignmark'):raise ValueError('MathML alignment marks not supported yet')
        if tag in REQUIRED and len(nodes)!=REQUIRED[tag]:raise ValueError('Wrong MathML child count: '+tag)
        small=max(0,font-1);cw,ch=self.metrics[font]
        if tag=='mfrac':
            a,b=[self.layout_math(c,small) for c in nodes];w=max(a.w,b.w)+8
            return Box('mathfrac',w,a.h+b.h+7,a.h+3+ch//2,font,
                       children=[(a,(w-a.w)//2,0),(b,(w-b.w)//2,a.h+7)])
        if tag in ('msub','msup','msubsup'):
            base=self.layout_math(nodes[0],font)
            sub=self.layout_math(nodes[1],small) if tag!='msup' else None
            sup=self.layout_math(nodes[-1],small) if tag!='msub' else None
            # Both scripts start at the same x; never turn x_i^2 into x_i^(2).
            sy=base.base-ch//2-(sup.h if sup else 0);offset=max(0,-sy) if sup else 0
            children=[(base,0,offset)];h=base.h+offset;w=base.w
            if sup:children.append((sup,base.w+1,sy+offset));h=max(h,sy+offset+sup.h);w=max(w,base.w+1+sup.w)
            if sub:
                y=base.base+offset-2;children.append((sub,base.w+1,y));h=max(h,y+sub.h);w=max(w,base.w+1+sub.w)
            return Box('scripts',w,h,base.base+offset,font,children=children)
        if tag in ('msqrt','mroot'):
            if not nodes:raise ValueError('Empty MathML root')
            body=self.row([self.layout_math(c,font) for c in nodes],font) if tag=='msqrt' else self.layout_math(nodes[0],font)
            idx=self.layout_math(nodes[1],small) if tag=='mroot' else None
            shift=max(0,idx.w-6) if idx else 0
            children=[(body,shift+13,5)]
            if idx:children.append((idx,0,0))
            return Box('mathroot',body.w+shift+14,max(body.h+5,idx.h if idx else 0),body.base+5,font,shift,children)
        if tag in ('munder','mover','munderover'):
            if attrs.get('accentunder')=='true':raise ValueError('Under accents not supported yet')
            base=self.layout_math(nodes[0],font)
            # A macron is an accent spanning the base, not a floating text bar.
            if tag=='mover' and attrs.get('accent')=='true':
                accent=nodes[1]
                if accent.tag not in ('mo','mtext') or ''.join(accent.children).strip() not in ('¯','‾','_'):
                    raise ValueError('Unsupported MathML accent')
                return Box('overbar',base.w,base.h+4,base.base+4,font,children=[(base,0,4)])
            low=self.layout_math(nodes[1],small) if tag!='mover' else None
            high=self.layout_math(nodes[-1],small) if tag!='munder' else None
            w=max([base.w]+([low.w] if low else [])+([high.w] if high else []));y=(high.h+2) if high else 0
            children=[(base,(w-base.w)//2,y)]
            if high:children.append((high,(w-high.w)//2,0))
            if low:children.append((low,(w-low.w)//2,y+base.h+2))
            return Box('limits',w,y+base.h+(low.h+2 if low else 0),y+base.base,font,children=children)
        if tag=='mfenced':
            opening=attrs.get('open','(');closing=attrs.get('close',')');seps=''.join(attrs.get('separators',',').split());boxes=[]
            if opening:boxes.append(self.token(opening,font))
            for i,c in enumerate(nodes):
                if i and seps:boxes.append(self.token(seps[min(i-1,len(seps)-1)],font))
                boxes.append(self.layout_math(c,font))
            if closing:boxes.append(self.token(closing,font))
            result=self.row(boxes,font)
            # token() wraps delimiters in rows: stretch them explicitly.
            for b,_,_ in result.children:
                if b.children and len(b.children)==1 and b.children[0][0].kind=='fence':
                    f=b.children[0][0];f.h=result.h;f.base=result.base;b.h=result.h;b.base=result.base
            result.children=[(b,x,result.base-b.base) for b,x,_ in result.children]
            return result
        if tag=='mtable':
            if not nodes or any(r.tag!='mtr' for r in nodes):raise ValueError('Unsupported MathML table row')
            rows=[];aligns=[];widths=[];heights=[];bases=[]
            for r in nodes:
                self.validate(r)
                cells=[];alignment=[]
                if not r.children or any(c.tag!='mtd' for c in r.children):raise ValueError('Invalid MathML table cell')
                for i,c in enumerate(r.children):
                    self.validate(c)
                    box=self.row([self.layout_math(n,font) for n in c.children],font);cells.append(box)
                    if i==len(widths):widths.append(0)
                    widths[i]=max(widths[i],box.w)
                    values=c.attrs.get('columnalign',r.attrs.get('columnalign',attrs.get('columnalign','center'))).split()
                    alignment.append(values[min(i,len(values)-1)] if values else 'center')
                base=max(c.base for c in cells);height=base+max(c.h-c.base for c in cells)
                rows.append(cells);aligns.append(alignment);heights.append(height);bases.append(base)
            if attrs.get('equalcolumns')=='true':widths=[max(widths)]*len(widths)
            if attrs.get('equalrows')=='true':heights=[max(heights)]*len(heights)
            children=[];y=0
            for ri,cells in enumerate(rows):
                x=0
                for i,c in enumerate(cells):
                    align=aligns[ri][i]
                    if align not in ('left','center','right'):raise ValueError('Unsupported MathML column alignment')
                    dx=0 if align=='left' else widths[i]-c.w if align=='right' else (widths[i]-c.w)//2
                    children.append((c,x+dx,y+bases[ri]-c.base));x+=widths[i]+8
                y+=heights[ri]+5
            return Box('mathtable',sum(widths)+8*(len(widths)-1),y-5,(y-5+ch)//2,font,children=children)
        raise ValueError('Unsupported MathML element: '+tag)

    def paint(self,box,x,y,color=None,editor=None):
        if color is None:color=self.palette.TEXT
        kind=box.kind;cw,ch=self.metrics[box.font]
        if kind=='mathtext':self.text(x,y,box.value,color,box.font)
        elif kind=='symbol':
            scale=2 if ch>=16 and cw>=10 else 1
            yy=y+ch-7*scale;xx=x+max(0,(cw-5*scale)//2)
            for row,bits in enumerate(PATTERNS[box.value]):
                for col in range(5):
                    if bits&(16>>col):self.fill(xx+col*scale,yy+row*scale,scale,scale,color)
        elif kind=='operator':
            if box.value in ('∑','∏'):self.glyph('sum' if box.value=='∑' else 'prod',x,y+2,box.w-2,box.h-3,color)
            else:
                for i in range(3 if box.value=='∭' else 1):self.glyph('int',x+2+i*8,y+2,12,box.h-3,color)
        elif kind=='mathfrac':self.line(x,y+box.children[0][0].h+3,x+box.w-1,y+box.children[0][0].h+3,color)
        elif kind=='mathroot':
            xx=x+box.value;mid=y+box.h//2
            self.line(xx+1,mid,xx+4,mid+3,color);self.line(xx+4,mid+3,xx+7,y+box.h-2,color)
            self.line(xx+7,y+box.h-2,xx+11,y+2,color);self.line(xx+11,y+2,x+box.w-1,y+2,color)
        elif kind=='overbar':self.line(x,y,x+box.w-1,y,color)
        elif kind=='fence':
            c=box.value[0];h=box.h-2;left=x+1;right=x+cw-2;mid=x+cw//2;top=y+1;bottom=y+h
            if c=='|':self.line(mid,top,mid,bottom,color)
            elif c in '[]':
                side=left if c=='[' else right
                self.line(left,top,right,top,color);self.line(side,top,side,bottom,color);self.line(left,bottom,right,bottom,color)
            elif c in '()':
                outer=left if c=='(' else right;inner=right if c=='(' else left
                self.line(inner,top,outer,top+min(4,h//3),color);self.line(outer,top+min(4,h//3),outer,bottom-min(4,h//3),color);self.line(outer,bottom-min(4,h//3),inner,bottom,color)
            else:
                outer=left if c=='{' else right;inner=right if c=='{' else left
                points=[(inner,top),(mid,top+2),(mid,top+h//2-2),(outer,top+h//2),(mid,top+h//2+2),(mid,bottom-2),(inner,bottom)]
                for a,b in zip(points,points[1:]):self.line(a[0],a[1],b[0],b[1],color)
        for child,dx,dy in box.children:self.paint(child,x+dx,y+dy,color)
