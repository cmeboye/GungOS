/* Bounded PNG reader for PicoCalc. See upstream/SOURCE.md for the inflater. */
#include "png_core.h"
#include <string.h>
#include "upstream/zutil.h"
#include "upstream/inftrees.h"
#include "upstream/inflate.h"
#define MAX_PITCH 3072
#define MAX_WIDTH 2048
#define MAX_HEIGHT 4096
#define CHUNK(a,b,c,d) (((uint32_t)(a)<<24)|((uint32_t)(b)<<16)|((uint32_t)(c)<<8)|(d))
typedef struct {
    struct inflate_state state;
    z_stream z;
    uint8_t window[32768];
    uint8_t rows[2][MAX_PITCH + 1];
    uint8_t input[1024], palette[768], alpha[256], output[320];
    int width, height, pitch, channels, depth, type, colors;
    int y, out_y, out_w, out_h, current, transparent;
    uint16_t key[3];
    uint32_t background;
    gungos_png_read read;
    gungos_png_row draw;
    void *in, *out;
    unsigned remaining;
} png_workspace;
_Static_assert(sizeof(png_workspace) <= GUNGOS_PNG_WORKSPACE_LIMIT, "PNG workspace exceeds 48 KiB");
size_t gungos_png_workspace_size(void) { return sizeof(png_workspace); }
static uint32_t be32(const uint8_t *p) {
    return ((uint32_t)p[0]<<24)|((uint32_t)p[1]<<16)|((uint32_t)p[2]<<8)|p[3];
}
static int exact(png_workspace *p, uint8_t *dst, unsigned count) {
    if (count > p->remaining) return 0;
    while (count) {
        int n = p->read(p->in, dst, count);
        if (n <= 0 || (unsigned)n > count) return 0;
        count -= n; p->remaining -= n; dst += n;
    }
    return 1;
}
static int abs_i(int n) { return n < 0 ? -n : n; }
static int unfilter(png_workspace *p) {
    uint8_t *cur = p->rows[p->current], *prev = p->rows[1-p->current]+1;
    int filter = *cur++, bpp = (p->channels*p->depth+7)/8;
    if (filter > 4) return 0;
    for (int i=0; i<p->pitch; ++i) {
        int a = i>=bpp ? cur[i-bpp] : 0, b = prev[i], c = i>=bpp ? prev[i-bpp] : 0;
        int v = 0;
        if (filter==1) v=a;
        else if (filter==2) v=b;
        else if (filter==3) v=(a+b)/2;
        else if (filter==4) {
            int base=a+b-c, pa=abs_i(base-a), pb=abs_i(base-b), pc=abs_i(base-c);
            v=(pa<=pb && pa<=pc) ? a : pb<=pc ? b : c;
        }
        cur[i]=(uint8_t)(cur[i]+v);
    }
    return 1;
}
static int emit(png_workspace *p) {
    uint8_t *s=p->rows[p->current]+1;
    /* Validate palette indices even on source rows omitted by downsampling. */
    if (p->type==3) for (int x=0; x<p->width; ++x) {
        int bit=x*p->depth, v=(s[bit/8]>>(8-p->depth-bit%8))&((1<<p->depth)-1);
        if (v>=p->colors) return 0;
    }
    if (p->out_y >= p->out_h || p->y != p->out_y*p->height/p->out_h) return 1;
    for (int x=0; x<p->out_w; ++x) {
        int sx=x*p->width/p->out_w, r,g,b,a=255;
        if (p->type==0 || p->type==3) {
            int bit=sx*p->depth, v=(s[bit/8]>>(8-p->depth-bit%8))&((1<<p->depth)-1);
            if (p->type==3) { r=p->palette[v*3];g=p->palette[v*3+1];b=p->palette[v*3+2];a=p->alpha[v]; }
            else { r=g=b=v*255/((1<<p->depth)-1);if (p->transparent && v==p->key[0]) a=0; }
        } else {
            uint8_t *v=s+sx*p->channels;
            if (p->type==4) { r=g=b=v[0];a=v[1]; }
            else { r=v[0];g=v[1];b=v[2];if (p->type==6) a=v[3];
                else if (p->transparent && r==p->key[0] && g==p->key[1] && b==p->key[2]) a=0; }
        }
        if (a!=255) {
            r=(r*a+((p->background>>16)&255)*(255-a)+127)/255;
            g=(g*a+((p->background>>8)&255)*(255-a)+127)/255;
            b=(b*a+(p->background&255)*(255-a)+127)/255;
        }
        p->output[x]=(r&224)|((g>>3)&28)|(b>>6);
    }
    return p->draw(p->out, p->out_y++, p->out_w, p->output);
}
static const char *feed(png_workspace *p, unsigned n, int *ended) {
    p->z.next_in=p->input;p->z.avail_in=n;
    while (p->z.avail_in) {
        if (*ended) return "Extra PNG compressed data";
        unsigned before=p->z.avail_in;
        int status=inflate(&p->z, Z_NO_FLUSH, 1);
        int produced=p->z.avail_out==0;
        if (produced) {
            if (p->y>=p->height) return "Extra PNG scanlines";
            if (!unfilter(p) || !emit(p)) return "Invalid PNG scanline";
            ++p->y;p->current=1-p->current;
            p->z.next_out=p->rows[p->current];p->z.avail_out=p->pitch+1;
        }
        if (status==Z_STREAM_END) {
            *ended=1;
            if (p->z.avail_in || p->y!=p->height || p->z.avail_out!=(unsigned)p->pitch+1)
                return "Invalid PNG image size";
        } else if (status!=Z_OK && status!=Z_BUF_ERROR) return "Damaged PNG compressed data";
        else if (before==p->z.avail_in && !produced) return "Stalled PNG inflater";
    }
    return NULL;
}
const char *gungos_png_decode(void *workspace, gungos_png_read read, void *input,
    unsigned size, int width, int height, uint32_t bg,
    gungos_png_row row, void *output, gungos_png_info *info) {
    if (!workspace || !read || !row || !info || size<45 || size>GUNGOS_PNG_INPUT_LIMIT ||
        width<1 || width>320 || height<1 || height>320) return "Invalid PNG input or viewport";
    png_workspace *p=workspace;memset(p,0,sizeof(*p));memset(p->alpha,255,256);
    p->read=read;p->in=input;p->draw=row;p->out=output;p->remaining=size;p->background=bg;
    uint8_t header[13];
    if (!exact(p,header,8) || memcmp(header,"\211PNG\r\n\032\n",8)) return "Invalid PNG signature";
    int ihdr=0,plte=0,trns=0,idat=0,after_idat=0,ended=0;
    for (int chunks=0; chunks<4096; ++chunks) {
        if (!exact(p,header,8)) return "Truncated PNG chunk";
        uint32_t n=be32(header),type=be32(header+4);
        if (p->remaining<4 || n>p->remaining-4) return "Invalid PNG chunk size";
        for (int i=4;i<8;++i) if (!((header[i]>='A' && header[i]<='Z') || (header[i]>='a' && header[i]<='z')))
            return "Invalid PNG chunk type";
        if (header[6]&32) return "Invalid PNG reserved bit";
        if (!ihdr && type!=CHUNK('I','H','D','R')) return "PNG header must be first";
        if (idat && type!=CHUNK('I','D','A','T')) after_idat=1;
        uint32_t crc=crc32(0,header+4,4);
        int metadata=0;
        if (type==CHUNK('I','H','D','R')) {
            if (ihdr || n!=13) return "Invalid PNG header";
            metadata=1;
        } else if (type==CHUNK('P','L','T','E')) {
            if (plte || idat || trns || n<3 || n>768 || n%3 || p->type==0 || p->type==4 ||
                (p->type==3 && n/3>(1u<<p->depth))) return "Invalid PNG palette";
            metadata=1;plte=1;
        } else if (type==CHUNK('t','R','N','S')) {
            if (trns || idat || (p->type==3 ? (!plte || n<1 || n>(unsigned)p->colors) :
                p->type==0 ? n!=2 : p->type==2 ? n!=6 : 1)) return "Invalid PNG transparency";
            metadata=1;trns=1;
        } else if (type==CHUNK('I','D','A','T')) {
            if (after_idat || (p->type==3 && !plte)) return "Invalid PNG data order";
            if (!idat) {
                p->z.state=(struct internal_state *)&p->state;p->state.window=p->window;
                if (inflateInit(&p->z)!=Z_OK) return "Cannot initialize PNG inflater";
                p->z.next_out=p->rows[0];p->z.avail_out=p->pitch+1;idat=1;
            }
        } else if (type==CHUNK('I','E','N','D')) {
            if (n || !ended || p->out_y!=p->out_h) return "Incomplete PNG image";
        } else if (!(type&0x20000000)) return "Unsupported PNG critical chunk";
        unsigned left=n;
        while (left) {
            unsigned take=left>sizeof(p->input) ? sizeof(p->input) : left;
            if (!exact(p,p->input,take)) return "Truncated PNG data";
            crc=crc32(crc,p->input,take);left-=take;
            if (type==CHUNK('I','D','A','T')) { const char *error=feed(p,take,&ended);if (error) return error; }
        }
        if (!exact(p,header,4) || be32(header)!=crc) return "PNG checksum mismatch";
        if (metadata && type==CHUNK('I','H','D','R')) {
            uint8_t *h=p->input;uint32_t w=be32(h),hgt=be32(h+4);
            p->depth=h[8];p->type=h[9];
            if (h[12]) return "Interlaced PNG unsupported";
            if (p->depth==16) return "16-bit PNG unsupported";
            if (h[10] || h[11]) return "Unsupported PNG compression or filter";
            if (!w || !hgt || w>MAX_WIDTH || hgt>MAX_HEIGHT || w*hgt>4*1024*1024) return "PNG dimensions too large";
            if (p->type==0 || p->type==3) { p->channels=1;
                if (p->depth!=1 && p->depth!=2 && p->depth!=4 && p->depth!=8) return "Invalid PNG bit depth";
            } else {
                p->channels=p->type==2 ? 3 : p->type==4 ? 2 : p->type==6 ? 4 : 0;
                if (!p->channels || p->depth!=8) return "Unsupported PNG colour type";
            }
            p->width=w;p->height=hgt;p->pitch=(w*p->channels*p->depth+7)/8;
            if (p->pitch>MAX_PITCH) return "PNG source row exceeds 3 KiB";
            p->out_w=w;p->out_h=hgt;
            if (p->out_w>width) { p->out_w=width;p->out_h=(int)((uint32_t)hgt*width/w); }
            if (p->out_h>height) { p->out_h=height;p->out_w=(int)((uint32_t)w*height/hgt); }
            if (p->out_w<1) p->out_w=1;if (p->out_h<1) p->out_h=1;
            *info=(gungos_png_info){w,hgt,p->out_w,p->out_h};ihdr=1;
        } else if (metadata && type==CHUNK('P','L','T','E')) {
            memcpy(p->palette,p->input,n);p->colors=n/3;
        } else if (metadata && type==CHUNK('t','R','N','S')) {
            if (p->type==3) memcpy(p->alpha,p->input,n);
            else { p->transparent=1;for (unsigned i=0;i<n/2;++i) {
                p->key[i]=(p->input[i*2]<<8)|p->input[i*2+1];
                if (p->key[i]>=(1u<<p->depth)) return "Invalid PNG transparent colour";
            } }
        }
        if (type==CHUNK('I','E','N','D')) return p->remaining ? "Trailing PNG data" : NULL;
    }
    return "Too many PNG chunks";
}
const char *gungos_zip_inflate(void *workspace,gungos_png_read read,void *input,
    unsigned compressed,unsigned plain,uint32_t expected,gungos_png_write write,void *output) {
    if (!workspace || !read || !write || compressed>GUNGOS_PNG_INPUT_LIMIT || plain>GUNGOS_PNG_INPUT_LIMIT)
        return "EPUB image exceeds 4 MiB";
    png_workspace *p=workspace;memset(p,0,sizeof(*p));p->read=read;p->in=input;p->remaining=compressed;
    p->z.state=(struct internal_state *)&p->state;p->state.window=p->window;
    if (inflateInit2(&p->z,-15)!=Z_OK) return "Cannot initialize EPUB inflater";
    uint32_t crc=0,total=0;
    while (1) {
        if (!p->z.avail_in && p->remaining) {
            unsigned n=p->remaining>sizeof(p->input) ? sizeof(p->input) : p->remaining;
            if (!exact(p,p->input,n)) return "Truncated EPUB image";
            p->z.next_in=p->input;p->z.avail_in=n;
        }
        p->z.next_out=p->rows[0];p->z.avail_out=1024;
        unsigned before=p->z.avail_in;int status=inflate(&p->z,Z_NO_FLUSH,1);
        unsigned n=1024-p->z.avail_out;
        if (n>plain-total) return "Invalid EPUB image size";
        if (n) {
            crc=crc32(crc,p->rows[0],n);total+=n;
            if (!write(output,p->rows[0],n)) return "Cannot write EPUB image";
        }
        if (status==Z_STREAM_END) {
            if (p->remaining || p->z.avail_in || total!=plain || crc!=expected) return "Damaged EPUB image";
            return NULL;
        }
        if ((status!=Z_OK && status!=Z_BUF_ERROR) || (!n && before==p->z.avail_in)) return "Invalid EPUB deflate stream";
    }
}
