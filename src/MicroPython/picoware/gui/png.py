"""Native, sequential PNG drawing. No compressed/full-image Python buffer."""
def draw_png(path,x=0,y=0,width=320,height=320,background=0xffffff):
    try:import pngdec
    except ImportError:raise ValueError('PNG images need the updated firmware')
    from gc import collect
    collect()
    with open(path,'rb') as stream:
        stream.seek(0,2);size=stream.tell();stream.seek(0)
        return pngdec.draw(stream,size,x,y,width,height,background)
