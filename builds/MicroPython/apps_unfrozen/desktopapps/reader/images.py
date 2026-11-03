"""Full-screen EPUB illustration preview, backed by managed external PSRAM."""
import os
from gc import collect

CACHE='picoware/cache/picoreader'
HEIGHT=280

def rgb888(colour):
    r=(colour>>11)&31;g=(colour>>5)&63;b=colour&31
    return ((r*255//31)<<16)|((g*255//63)<<8)|(b*255//31)


class ImageViewer:
    def __init__(self,vm):
        self.vm=vm;self.preview=None;self.psram=None;self.previous_mode=vm.draw.mode
        vm.draw.set_mode(vm.draw.MODE_PSRAM)

    def clear(self):
        if self.preview is not None:
            self.preview.__del__();self.preview=None
        collect()

    def open(self,book,resource,background):
        self.clear();vm=self.vm;draw=vm.draw
        ext=resource.rsplit('.',1)[-1].lower()
        if ext not in ('png','jpg','jpeg'):raise ValueError('Image format unsupported: '+ext)
        vm.storage.mkdir('picoware/cache');vm.storage.mkdir(CACHE)
        path=vm.storage.vfs_prefix+'/'+CACHE+'/image.'+ext
        try:
            book.archive.extract(resource,path)
            draw.fill_screen(background)
            if ext=='png':
                from picoware.gui.png import draw_png
                draw_png(path,0,0,320,HEIGHT,rgb888(background))
            else:
                from picoware.gui.jpeg import JPEG
                decoder=JPEG(screen_width=320,screen_height=HEIGHT)
                try:
                    if not decoder.draw(0,0,path,vm.storage):raise ValueError(decoder.last_error or 'JPEG decode failed')
                finally:decoder.close()
            # alloc_buffer reserves PSRAM directly; never construct bytearray(89600).
            from picoware_psram import PSRAM,alloc_buffer
            self.psram=PSRAM();self.preview=alloc_buffer(320*HEIGHT)
            for y in range(HEIGHT):
                self.psram.write(self.preview.addr()+y*320,draw._read_row(y))
        except Exception:
            self.clear();raise
        finally:
            try:os.remove(path)
            except OSError:pass

    def draw(self):
        if self.preview is None:return
        draw=self.vm.draw;buf=bytearray(320)
        for y in range(HEIGHT):
            # Managed allocations may move during PSRAM compaction.
            self.psram.read_into(self.preview.addr()+y*320,buf)
            draw._bytearray(0,y,320,1,buf,False)

    def close(self):
        self.clear();self.psram=None
        self.vm.draw.set_mode(self.previous_mode)
