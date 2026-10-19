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
        self.box,self.rect=box,rect
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

    def project(self,p):
        q=tuple((p[i]-self.center[i])/self.scale for i in range(3))
        ratio=self.ratio(q)
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


def segments(feature,steps=16):
    shape=feature['shape'];a,b,c=feature['a'],feature['b'],feature['c']
    if shape=='Box':
        vertices=[(x*a/2,y*b/2,z*c/2) for z in (-1,1) for y in (-1,1) for x in (-1,1)]
        for i in range(8):
            for bit in (1,2,4):
                if not i&bit:yield vertices[i],vertices[i|bit]
        return
    if shape=='Sphere':
        for axis in range(3):
            for i in range(steps):
                p=[0.0]*3;q=[0.0]*3
                p[(axis+1)%3],p[(axis+2)%3]=a*cos(2*pi*i/steps),a*sin(2*pi*i/steps)
                q[(axis+1)%3],q[(axis+2)%3]=a*cos(2*pi*(i+1)/steps),a*sin(2*pi*(i+1)/steps)
                yield p,q
        return
    for i in range(steps):
        x,y=a*cos(2*pi*i/steps),a*sin(2*pi*i/steps)
        xx,yy=a*cos(2*pi*(i+1)/steps),a*sin(2*pi*(i+1)/steps)
        yield (x,y,-c/2),(xx,yy,-c/2)
        if shape=='Cylinder':yield (x,y,c/2),(xx,yy,c/2)
        if i%(steps//4)==0:yield (x,y,-c/2),((x,y,c/2) if shape=='Cylinder' else (0,0,c/2))


def primitive(draw,camera,feature,color,dashed=False):
    m=dm.matrix(feature);position=tuple(feature[k] for k in ('x','y','z'))
    for a,b in segments(feature):
        if feature['shape']=='Sphere':
            world_a=tuple(a[i]+position[i] for i in range(3));world_b=tuple(b[i]+position[i] for i in range(3))
        else:
            world_a=tuple(sum(m[i][j]*a[j] for j in range(3))+position[i] for i in range(3))
            world_b=tuple(sum(m[i][j]*b[j] for j in range(3))+position[i] for i in range(3))
        p,q=camera.project(world_a),camera.project(world_b)
        if p is None or q is None:continue
        if dashed:
            for i in range(0,12,2):
                draw._line(p[0]+(q[0]-p[0])*i/12,p[1]+(q[1]-p[1])*i/12,
                           p[0]+(q[0]-p[0])*(i+1)/12,p[1]+(q[1]-p[1])*(i+1)/12,color)
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
