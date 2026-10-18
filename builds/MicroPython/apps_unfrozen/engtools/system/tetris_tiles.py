"""Original 8x8 indexed block artwork and level palettes; bounded RGB565 cache."""

# Each level selects a three-colour family. The cycle repeats after ten levels.
PALETTES=((0x039F,0x07FF,0xFFFF),(0x04E0,0xAFE5,0xFFFF),
          (0xB01F,0xFC1F,0xFFFF),(0xF800,0xFD20,0xFFE0),
          (0x025F,0x7DFF,0xFFFF),(0xD800,0xFB4D,0xFFFF),
          (0x026D,0x07D7,0xFFFF),(0x980F,0xFD17,0xFFFF),
          (0xA280,0xFEA0,0xFFFF),(0x421F,0xABFF,0xFFFF))
FAMILIES=(0,2,1,0,1,2,0)
STYLES=('Pixel','Bevel','Solid')
# 0 background, 1 base, 2 highlight, 3 shadow, 4 white detail.
PIXEL=(
 ('22222223','21111133','21444133','21411133','21411133','21444133','23333333','33333333'),
 ('22222223','21111133','21444133','21414133','21444133','21111133','23333333','33333333'),
 ('22222223','21111133','21444133','21141133','21141133','21111133','23333333','33333333'),
 ('22222223','21111133','21144133','21441133','21111133','21111133','23333333','33333333'),
 ('22222223','21111133','21441133','21144133','21111133','21111133','23333333','33333333'),
 ('22222223','21111133','21144133','21114133','21444133','21111133','23333333','33333333'),
 ('22222223','21111133','21441133','21411133','21444133','21111133','23333333','33333333'))
BEVEL=('22222223','21111113','21111113','21111113','21111113','21111113','21111133','33333333')
SOLID=('11111111',)*8


def mix(a,b,n,d):
    result=0
    for shift,mask in ((11,31),(5,63),(0,31)):
        result|=((((a>>shift)&mask)*(d-n)+((b>>shift)&mask)*n)//d)<<shift
    return result


class Blocks:
    def __init__(self):self.key=None;self.cache={};self.colors=()
    def prepare(self,level,style,background):
        key=((max(1,level)-1)%len(PALETTES),style,background)
        if key==self.key:return
        self.key=key;self.cache={}
        family=PALETTES[key[0]]
        self.colors=tuple(family[index] for index in FAMILIES)
    def sprite(self,piece,size):
        key=(piece,size)
        if key not in self.cache:
            base=self.colors[piece]
            colors=(self.key[2],base,mix(base,0xFFFF,1,2),mix(base,0,1,2),0xFFFF)
            rows=PIXEL[piece] if self.key[1]=='Pixel' else BEVEL if self.key[1]=='Bevel' else SOLID
            out=bytearray(size*size*2)
            for y in range(size):
                for x in range(size):
                    color=colors[ord(rows[y*8//size][x*8//size])-48]
                    index=(y*size+x)*2
                    out[index]=color&255;out[index+1]=color>>8
            self.cache[key]=out
        return self.cache[key]
    def draw(self,draw,piece,x,y,size):
        draw._bytearray(x,y,size,size,self.sprite(piece,size))
