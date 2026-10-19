"""Clipped direct boundaries and editable primitive construction guides."""
from math import cos,sin,pi
from . import model as dm
from engtools.ui.viewport import Viewport


ISO_YAW=pi/4
ISO_PITCH=.61547970867
PROJECTIONS=('Perspective','Isometric')


class Camera:
    def __init__(self):
        self.yaw,self.pitch=.7,.55
        self.zoom=1.0;self.pan_x=self.pan_y=0.0;self.focal=250.0;self.cam=4.0
        self.mode='Orbit';self.projection='Perspective'

    def setup(self,box,rect):
        self.rect=rect
        self.center=tuple((box[2*i]+box[2*i+1])/2 for i in range(3))
        self.scale=max((box[2*i+1]-box[2*i])/2 for i in range(3))
        self.cy,self.sy,self.cp,self.sp=cos(self.yaw),sin(self.yaw),cos(self.pitch),sin(self.pitch)
        x,y,w,h=rect;self.cx,self.cy_screen=x+w/2+self.pan_x,y+h/2+self.pan_y

    def ratio(self,p):
        x,y,z=p
        xx=x*self.cy-y*self.sy;depth=x*self.sy+y*self.cy
        yy=z*self.cp-depth*self.sp;zz=z*self.sp+depth*self.cp
        if self.projection=='Isometric':return xx/self.cam,-yy/self.cam
        distance=self.cam-zz
        if distance<.4:return None
        return xx/distance,-yy/distance

    def view(self,p):
        """Camera-space (screen x, screen y, depth); linear, so curve axes rotate once."""
        x,y,z=p;depth=x*self.sy+y*self.cy
        return x*self.cy-y*self.sy,z*self.cp-depth*self.sp,z*self.sp+depth*self.cp

    def flat(self,xx,yy,zz):
        if self.projection=='Isometric':return xx/self.cam,-yy/self.cam
        distance=self.cam-zz
        if distance<.4:return None
        return xx/distance,-yy/distance

    def project(self,p):
        c=self.center;s=self.scale
        ratio=self.ratio(((p[0]-c[0])/s,(p[1]-c[1])/s,(p[2]-c[2])/s))
        if ratio is None:return None
        return self.cx+ratio[0]*self.focal*self.zoom,self.cy_screen+ratio[1]*self.focal*self.zoom

    def fit(self,box,rect,geometry=None):
        self.zoom=1.0;self.pan_x=self.pan_y=0.0;self.setup(box,rect)
        if geometry is not None and len(geometry):
            low_x=low_y=1e30;high_x=high_y=-1e30
            points=geometry.fit_points()
            for vertex in points:
                p=self.ratio(vertex)
                if p is not None:
                    low_x=min(low_x,p[0]);high_x=max(high_x,p[0]);low_y=min(low_y,p[1]);high_y=max(high_y,p[1])
            self.focal=min((rect[2]-24)/max(1e-8,high_x-low_x),(rect[3]-24)/max(1e-8,high_y-low_y))
            self.pan_x=-(low_x+high_x)*self.focal/2;self.pan_y=-(low_y+high_y)*self.focal/2
            self.setup(box,rect)
            return
        half=tuple((box[2*i+1]-box[2*i])/2/self.scale for i in range(3))
        projected=[self.ratio((x,y,z)) for x in (-half[0],half[0]) for y in (-half[1],half[1]) for z in (-half[2],half[2])]
        self.focal=min((rect[2]-24)/2/max(.01,max(abs(p[0]) for p in projected if p)),
                       (rect[3]-24)/2/max(.01,max(abs(p[1]) for p in projected if p)))


def outline(feature,steps=16):
    """Local guide vertices and the index pairs joining them."""
    shape=feature['shape'];a,b,c=feature['a'],feature['b'],feature['c']
    if shape=='Box':
        points=[(x*a/2,y*b/2,z*c/2) for z in (-1,1) for y in (-1,1) for x in (-1,1)]
        return points,[(i,i|bit) for i in range(8) for bit in (1,2,4) if not i&bit]
    ring=[(a*cos(2*pi*i/steps),a*sin(2*pi*i/steps)) for i in range(steps)]
    loop=[(i,(i+1)%steps) for i in range(steps)]
    if shape=='Sphere':
        points=[]
        for axis in range(3):
            for x,y in ring:
                p=[0.0]*3;p[(axis+1)%3],p[(axis+2)%3]=x,y;points.append(p)
        return points,[(i+n*steps,j+n*steps) for n in range(3) for i,j in loop]
    points=[(x,y,-c/2) for x,y in ring];edges=loop
    if shape=='Cylinder':
        points.extend((x,y,c/2) for x,y in ring)
        edges+=[(i+steps,j+steps) for i,j in loop]+[(i,i+steps) for i in range(0,steps,steps//4)]
    else:
        points.append((0.0,0.0,c/2));edges+=[(i,steps) for i in range(0,steps,steps//4)]
    return points,edges


def primitive(draw,camera,feature,color,dashed=False):
    points,edges=outline(feature)
    px,py,pz=feature['x'],feature['y'],feature['z']
    # Spheres are rotation invariant; each shared vertex is projected once.
    if feature['shape']=='Sphere':screen=[camera.project((x+px,y+py,z+pz)) for x,y,z in points]
    else:
        (a,b,c),(d,e,f),(g,h,i)=dm.matrix(feature)
        screen=[camera.project((a*x+b*y+c*z+px,d*x+e*y+f*z+py,g*x+h*y+i*z+pz)) for x,y,z in points]
    for i,j in edges:
        p,q=screen[i],screen[j]
        if p is None or q is None:continue
        if dashed:
            # About one dash per 8px, at most six: short edges skip sub-pixel dashes.
            dx,dy=q[0]-p[0],q[1]-p[1];count=min(6,max(1,int(abs(dx)+abs(dy))//8))
            for n in range(count):
                s,t=n/count,(n+.5)/count
                draw._line(p[0]+dx*s,p[1]+dy*s,p[0]+dx*t,p[1]+dy*t,color)
        else:draw._line(p[0],p[1],q[0],q[1],color)


def built(draw,camera,geometry,palette):
    x,y,w,h=camera.rect;bounded=Viewport(draw,(x,y,x+w,y+h))
    for a,b in geometry.projected(camera):
        bounded._line(camera.cx+a[0]*camera.focal*camera.zoom,camera.cy_screen+a[1]*camera.focal*camera.zoom,
                      camera.cx+b[0]*camera.focal*camera.zoom,camera.cy_screen+b[1]*camera.focal*camera.zoom,palette.ACCENT)


def preview(draw,camera,model,selected,palette):
    x,y,w,h=camera.rect;bounded=Viewport(draw,(x,y,x+w,y+h))
    for index,feature in enumerate(model['features']):
        color=palette.ACCENT if index==selected else palette.TEXT if feature['op']=='Add' else palette.MUTED
        primitive(bounded,camera,feature,color,feature['op']!='Add')


def axes(draw,camera,palette):
    """Fixed-size, theme-coloured world XYZ guide; rotates with the camera."""
    from engtools.ui import lab
    x,y,w,h=camera.rect;cx,cy=x+28,y+26
    bounded=Viewport(draw,(x+2,y+2,x+54,y+52))
    bounded._fill_rectangle(x+2,y+2,52,50,palette.BG)
    directions=((camera.cy,camera.sy*camera.sp),(-camera.sy,camera.cy*camera.sp),(0,-camera.cp))
    for label,(dx,dy) in zip(('X','Y','Z'),directions):
        bounded._line(cx,cy,cx+14*dx,cy+14*dy,palette.ACCENT)
        if abs(dx)+abs(dy)<.1:lab.text(bounded,cx-10,cy+5,label,palette.TEXT)
        else:lab.text(bounded,cx+18*dx-3,cy+18*dy-3,label,palette.TEXT)
    bounded._fill_rectangle(cx-1,cy-1,3,3,palette.ACCENT)
