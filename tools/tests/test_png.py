"""Exact native PNG pixels, all filters/colour modes, checksums and bounds."""
from pathlib import Path
import os, random, struct, subprocess, tempfile, zlib
ROOT=Path(__file__).resolve().parents[2]
def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data))
def make_png(w,h,depth,kind,rows,extra=b'',filters=False):
    channels={0:1,2:3,3:1,4:2,6:4}[kind];bpp=max(1,(channels*depth+7)//8)
    prev=bytes(len(rows[0]));raw=b''
    for y,row in enumerate(rows):
        f=y%5 if filters else 0;encoded=bytearray(row)
        for i,v in enumerate(row):
            a=row[i-bpp] if i>=bpp else 0;b=prev[i];c=prev[i-bpp] if i>=bpp else 0
            p=a+b-c;pa,pb,pc=abs(p-a),abs(p-b),abs(p-c)
            pred=(0,a,b,(a+b)//2,a if pa<=pb and pa<=pc else b if pb<=pc else c)[f]
            encoded[i]=(v-pred)&255
        raw+=bytes([f])+encoded;prev=row
    encoded=zlib.compress(raw)
    # Split deflate at awkward boundaries, interspersed zero-length IDATs.
    step=7 if len(encoded)<10000 else 1024
    data=b''.join(chunk(b'IDAT',encoded[i:i+step])+chunk(b'IDAT',b'') for i in range(0,len(encoded),step))
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,depth,kind,0,0,0))+extra+data+chunk(b'IEND',b'')
def pack(values,depth):
    b=bytearray((len(values)*depth+7)//8)
    for i,v in enumerate(values):b[i*depth//8]|=v<<(8-depth-(i*depth)%8)
    return bytes(b)
def rgb332(r,g,b,a=255,bg=(245,90,31)):
    rgb=[(c*a+d*(255-a)+127)//255 for c,d in zip((r,g,b),bg)]
    return (rgb[0]&224)|((rgb[1]>>3)&28)|(rgb[2]>>6)
with tempfile.TemporaryDirectory(prefix='gungos-png-') as tmp:
    folder=Path(tmp);binary=folder/'decode'
    env=dict(os.environ,PNG_TEST_BINARY=str(binary),PNG_TEST_CFLAGS='-fsanitize=address,undefined -fno-sanitize-recover=all -g')
    subprocess.run(['sh','simulator/png/build.sh'],cwd=ROOT,env=env,check=True)
    count=0
    def check(data,expected=None,w=320,h=280):
        global count
        src=folder/'image.png';dst=folder/'image.rgb';src.write_bytes(data)
        r=subprocess.run([str(binary),str(src),str(dst),str(w),str(h),'f55a1f'],capture_output=True)
        if expected is None:
            assert r.returncode==1,(r.returncode,r.stderr.decode())
            assert not dst.exists()
        else:
            assert r.returncode==0,r.stderr.decode()
            pixels=dst.read_bytes();ow,oh,sw,sh=struct.unpack('<4H',pixels[:8])
            ew,eh=sw,sh
            if ew>w:ew,eh=w,sh*w//sw
            if eh>h:ew,eh=sw*h//sh,h
            ew,eh=max(1,ew),max(1,eh)
            assert (ow,oh)==(ew,eh)
            want=bytes(expected[y*sh//oh][x*sw//ow] for y in range(oh) for x in range(ow))
            assert pixels[8:]==want,(sw,sh,pixels[8:30],want[:22])
        count+=1
    random.seed(17)
    good=[]
    for kind in (0,2,3,4,6):
        for depth in ((1,2,4,8) if kind in (0,3) else (8,)):
            for w,h in ((1,1),(7,9),(17,11),(321,29),(701,401)):
                palette=[(i*31%256,i*59%256,i*137%256) for i in range(1<<depth)]
                alpha=[i*53%256 for i in range(1<<depth)]
                extra=b'';rows=[];want=[]
                if kind==3:extra=chunk(b'PLTE',bytes(c for rgb in palette for c in rgb))+chunk(b'tRNS',bytes(alpha))
                elif kind==0:extra=chunk(b'tRNS',struct.pack('>H',0))
                elif kind==2:extra=chunk(b'tRNS',struct.pack('>3H',0,0,0))
                for y in range(h):
                    line=[];pixels=[]
                    for x in range(w):
                        v=(x+y)%(1<<depth)
                        if kind==0:
                            c=v*255//((1<<depth)-1);line.append(v);pixels.append(rgb332(c,c,c,0 if v==0 else 255))
                        elif kind==3:line.append(v);pixels.append(rgb332(*palette[v],alpha[v]))
                        else:
                            rgb=(x*7%256,y*19%256,(x+y)*13%256);a=(x*11+y*17)%256
                            if kind==2:line.extend(rgb);pixels.append(rgb332(*rgb,0 if rgb==(0,0,0) else 255))
                            elif kind==4:line.extend((rgb[0],a));pixels.append(rgb332(rgb[0],rgb[0],rgb[0],a))
                            else:line.extend((*rgb,a));pixels.append(rgb332(*rgb,a))
                    rows.append(pack(line,depth) if kind in (0,3) else bytes(line));want.append(pixels)
                data=make_png(w,h,depth,kind,rows,extra,True);check(data,want);good.append(data)
    # Largest supported source rows and extreme aspect ratios.
    for w,h,kind in ((1024,3,2),(768,3,6),(2048,1,0),(1,4096,0)):
        channels={0:1,2:3,6:4}[kind];rows=[bytes([255])*(w*channels)]*h
        check(make_png(w,h,8,kind,rows),[[rgb332(255,255,255)]*w]*h)
    base=good[-1]
    for i in (0,1,8,16,len(base)//2,len(base)-1):
        corrupt=bytearray(base);corrupt[i]^=1;check(bytes(corrupt))
    for n in (0,4,15,32,len(base)-1):check(base[:n])
    check(base+b'junk')
    # Valid CRC but unsupported/oversized IHDR and malformed filters/streams.
    for w,h,d,t,inter in ((769,2,8,6,0),(2049,1,8,0,0),(1,4097,8,0,0),(1,1,16,0,0),(1,1,8,6,1),(1,1,4,2,0)):
        ihdr=struct.pack('>IIBBBBB',w,h,d,t,0,0,inter)
        check(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',ihdr)+chunk(b'IDAT',zlib.compress(b'\0\0'))+chunk(b'IEND',b''))
    for raw in (b'\5\0',b'\0',b'\0\0\0',b'\0\0\0\0'):
        check(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,0,0,0,0))+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b''))
    # Missing palette, invalid palette index, unknown critical chunk.
    check(make_png(1,1,8,3,[b'\0']))
    check(make_png(1,1,8,3,[b'\1'],chunk(b'PLTE',b'\0\0\0')))
    check(make_png(1,1,8,0,[b'\0'],chunk(b'WHAT',b'hello')))
    # Exercise short reads in the actual native binding and reader integration separately.
    print('PASS:',count,'native PNG pixel/integrity/bounds cases under ASan/UBSan')
