"""Bound native drawing to a panel without allocating another framebuffer."""


class Viewport:
    """A draw adapter with exclusive right/bottom bounds and native fast paths."""
    def __init__(self, draw, box):
        self.draw, self.box, self.size = draw, box, draw.size
        self.len, self.get_font = draw.len, draw.get_font

    def _line(self, x1, y1, x2, y2, color):
        left, top, right, bottom = self.box
        right -= 1; bottom -= 1
        if min(x1,x2)>=left and max(x1,x2)<=right and min(y1,y2)>=top and max(y1,y2)<=bottom:
            self.draw._line(int(x1),int(y1),int(x2),int(y2),color)
            return
        dx,dy,first,last=x2-x1,y2-y1,0.0,1.0
        for p,q in ((-dx,x1-left),(dx,right-x1),(-dy,y1-top),(dy,bottom-y1)):
            if p==0:
                if q<0:return
            else:
                t=q/p
                if p<0:first=max(first,t)
                else:last=min(last,t)
                if first>last:return
        self.draw._line(max(left,min(right,int(x1+first*dx))),max(top,min(bottom,int(y1+first*dy))),
                        max(left,min(right,int(x1+last*dx))),max(top,min(bottom,int(y1+last*dy))),color)

    def _fill_rectangle(self,x,y,w,h,color):
        left,top,right,bottom=self.box
        x1,y1=max(left,int(x)),max(top,int(y))
        x2,y2=min(right,int(x+w)),min(bottom,int(y+h))
        if x2>x1 and y2>y1:self.draw._fill_rectangle(x1,y1,x2-x1,y2-y1,color)

    def _rectangle(self,x,y,w,h,color):
        if w<=0 or h<=0:return
        self._line(x,y,x+w-1,y,color);self._line(x,y+h-1,x+w-1,y+h-1,color)
        self._line(x,y,x,y+h-1,color);self._line(x+w-1,y,x+w-1,y+h-1,color)

    def _text(self,x,y,value,color,font=0):
        left,top,right,bottom=self.box
        value=str(value);metrics=self.get_font(font)
        cw,ch=metrics.width+metrics.spacing,metrics.height
        x,y=int(x),int(y)
        if y<top or y+ch>bottom:return
        first=max(0,(left-x+cw-1)//cw)
        last=min(len(value),(right-x)//cw)
        if last>first:self.draw._text(x+first*cw,y,value[first:last],color,font)

    def _fill_triangle(self,x1,y1,x2,y2,x3,y3,color):
        left,top,right,bottom=self.box
        right-=1;bottom-=1
        if max(x1,x2,x3)<left or min(x1,x2,x3)>right or max(y1,y2,y3)<top or min(y1,y2,y3)>bottom:return
        if min(x1,x2,x3)>=left and max(x1,x2,x3)<=right and min(y1,y2,y3)>=top and max(y1,y2,y3)<=bottom:
            self.draw._fill_triangle(int(x1),int(y1),int(x2),int(y2),int(x3),int(y3),color)
            return
        points=[(x1,y1),(x2,y2),(x3,y3)]
        for axis,edge,sign in ((0,left,1),(0,right,-1),(1,top,1),(1,bottom,-1)):
            if not points:return
            out=[];prev=points[-1];pin=(prev[axis]-edge)*sign>=0
            for point in points:
                inside=(point[axis]-edge)*sign>=0
                if inside!=pin:
                    t=(edge-prev[axis])/(point[axis]-prev[axis])
                    out.append((prev[0]+t*(point[0]-prev[0]),prev[1]+t*(point[1]-prev[1])))
                if inside:out.append(point)
                prev,pin=point,inside
            points=out
        if len(points)<3:return
        points=[(max(left,min(right,int(x))),max(top,min(bottom,int(y)))) for x,y in points]
        a=points[0]
        for i in range(1,len(points)-1):
            b,c=points[i],points[i+1]
            self.draw._fill_triangle(a[0],a[1],b[0],b[1],c[0],c[1],color)

    def _circle(self,x,y,radius,color):
        self._round(x,y,radius,color,False)

    def _fill_circle(self,x,y,radius,color):
        self._round(x,y,radius,color,True)

    def _round(self,cx,cy,radius,color,fill):
        cx,cy,radius=int(cx),int(cy),int(radius)
        if radius<=0:return
        left,top,right,bottom=self.box
        if cx+radius<left or cx-radius>=right or cy+radius<top or cy-radius>=bottom:return
        if cx-radius>=left and cx+radius<right and cy-radius>=top and cy+radius<bottom:
            if fill:self.draw._fill_circle(cx,cy,radius,color)
            else:self.draw._circle(cx,cy,radius,color)
            return
        # Same midpoint algorithm as gfx, using clipped spans at panel edges.
        x,y,d=0,radius,3-2*radius
        while x<=y:
            if fill:
                for yy,a,b in ((cy+y,cx-x,cx+x),(cy-y,cx-x,cx+x),
                               (cy+x,cx-y,cx+y),(cy-x,cx-y,cx+y)):
                    self._fill_rectangle(a,yy,b-a+1,1,color)
            else:
                for xx,yy in ((cx+x,cy+y),(cx-x,cy+y),(cx+x,cy-y),(cx-x,cy-y),
                              (cx+y,cy+x),(cx-y,cy+x),(cx+y,cy-x),(cx-y,cy-x)):
                    self._fill_rectangle(xx,yy,1,1,color)
            if d<0:d+=4*x+6
            else:d+=4*(x-y)+10;y-=1
            x+=1
