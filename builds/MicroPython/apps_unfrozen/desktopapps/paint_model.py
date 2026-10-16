"""RGB332 canvas, one-level undo and cooperative scanline flood fill."""
from array import array
import struct

WIDTH,HEIGHT=256,192
TOOLS=('Pencil','Eraser','Line','Rectangle','Fill','Picker')
PATTERNS=('Solid','Dashes 25%','Diagonal 50%','Dots 25%')


def packed(color):return ((color>>13)&7)<<5|((color>>8)&7)<<2|((color>>3)&3)
def rgb(color):return ((color>>5)&7)*255//7,((color>>2)&7)*255//7,(color&3)*255//3
def rgb565(color):
    r,g,b=rgb(color);return (r>>3)<<11|(g>>2)<<5|(b>>3)
def on(pattern,x,y):
    if pattern==0:return True
    if pattern==1:return y%4<2 and x%8<4
    if pattern==2:return (x+y)%4<2
    return x%2==0 and y%2==0


class Canvas:
    def __init__(self):
        self.width,self.height=WIDTH,HEIGHT
        self.paper=255;self.pixels=bytearray(b'\xff'*(WIDTH*HEIGHT))
        self.dirty=False;self.undo=None;self.undo_dirty=False
    def checkpoint(self):self.undo=bytearray(self.pixels);self.undo_dirty=self.dirty
    def mark_saved(self):self.undo_dirty=True
    def restore(self):
        if self.undo is None:return False
        self.pixels,self.undo=self.undo,None;self.dirty=self.undo_dirty;return True
    def brush(self,x,y,color,size=1,pattern=0):
        radius=size//2
        for row in range(max(0,y-radius),min(HEIGHT,y+radius+1)):
            for col in range(max(0,x-radius),min(WIDTH,x+radius+1)):
                index=row*WIDTH+col
                value=color if on(pattern,col,row) else self.paper
                if self.pixels[index]!=value:self.pixels[index]=value;self.dirty=True
    def line(self,x0,y0,x1,y1,color,size=1,pattern=0):
        dx,dy=abs(x1-x0),-abs(y1-y0)
        sx,sy=1 if x0<x1 else -1,1 if y0<y1 else -1
        error=dx+dy
        while True:
            self.brush(x0,y0,color,size,pattern)
            if x0==x1 and y0==y1:break
            double=2*error
            if double>=dy:error+=dy;x0+=sx
            if double<=dx:error+=dx;y0+=sy
    def rectangle(self,x0,y0,x1,y1,color,size=1,pattern=0):
        self.line(x0,y0,x1,y0,color,size,pattern);self.line(x1,y0,x1,y1,color,size,pattern)
        self.line(x1,y1,x0,y1,color,size,pattern);self.line(x0,y1,x0,y0,color,size,pattern)
    def fill(self,x,y,color,pattern=0):
        target=self.pixels[y*WIDTH+x]
        if target==color and pattern==0:return
        mask=bytearray((WIDTH*HEIGHT+7)//8);pending=array('H',bytearray(16384));count=1;steps=0
        pending[0]=y*WIDTH+x
        def eligible(index):return self.pixels[index]==target and not mask[index>>3]&(1<<(index&7))
        while count:
            count-=1;index=pending[count]
            if not eligible(index):continue
            row,col=divmod(index,WIDTH);left=right=col
            while left and eligible(row*WIDTH+left-1):left-=1
            while right<WIDTH-1 and eligible(row*WIDTH+right+1):right+=1
            for col in range(left,right+1):
                index=row*WIDTH+col;mask[index>>3]|=1<<(index&7)
                value=color if on(pattern,col,row) else self.paper
                if self.pixels[index]!=value:self.pixels[index]=value;self.dirty=True
            for neighbor in (row-1,row+1):
                if not 0<=neighbor<HEIGHT:continue
                col=left
                while col<=right:
                    if eligible(neighbor*WIDTH+col):
                        if count>=8192:raise ValueError('Fill complexity limit; undo restored')
                        pending[count]=neighbor*WIDTH+col;count+=1
                        while col<=right and eligible(neighbor*WIDTH+col):col+=1
                    else:col+=1
            steps+=right-left+1
            yield steps
    def native_chunks(self):
        yield b'PPA1'+struct.pack('<HHBB',WIDTH,HEIGHT,self.paper,0)
        data=memoryview(self.pixels)
        for i in range(0,len(data),1024):yield data[i:i+1024]
    def bmp_chunks(self):
        # Standard uncompressed indexed BMP; pixel colours are independent of UI.
        size=54+1024+WIDTH*HEIGHT
        yield struct.pack('<2sIHHI',b'BM',size,0,0,1078)
        yield struct.pack('<IIIHHIIIIII',40,WIDTH,HEIGHT,1,8,0,WIDTH*HEIGHT,2835,2835,256,256)
        palette=bytearray()
        for color in range(256):
            r,g,b=rgb(color);palette.extend(bytes((b,g,r,0)))
        yield palette
        view=memoryview(self.pixels)
        for row in range(HEIGHT-1,-1,-1):yield view[row*WIDTH:(row+1)*WIDTH]
    @classmethod
    def load(cls,storage,path):
        header=storage.read(path,'rb',0,10)
        if not isinstance(header,bytes) or len(header)!=10 or header[:4]!=b'PPA1':raise ValueError('Not a PicoPaint image')
        width,height,paper,reserved=struct.unpack('<HHBB',header[4:])
        if (width,height)!=(WIDTH,HEIGHT) or reserved or storage.size(path)!=10+WIDTH*HEIGHT:
            raise ValueError('Unsupported image dimensions/data')
        result=cls();result.paper=paper
        for offset in range(0,WIDTH*HEIGHT,1024):
            part=storage.read(path,'rb',10+offset,min(1024,WIDTH*HEIGHT-offset))
            if not isinstance(part,bytes) or len(part)!=min(1024,WIDTH*HEIGHT-offset):raise OSError('Incomplete image; original kept')
            result.pixels[offset:offset+len(part)]=part
        return result


def example():
    c=Canvas();blue=packed(0x001F);orange=packed(0xFD20);green=packed(0x07E0)
    c.rectangle(18,18,237,173,blue,3)
    c.rectangle(38,47,106,141,blue,1)
    for _ in c.fill(50,60,orange,1):pass
    c.rectangle(133,47,215,141,blue,1)
    for _ in c.fill(150,60,green,2):pass
    c.line(32,156,221,31,packed(0xF81F),3)
    c.dirty=True
    return c
