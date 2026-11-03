#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../../JPEGDEC/src/JPEGDEC.h"
#include "../jpeg_output.h"

static uint16_t screen[320*320];
static int calls, submitted;
static void blit(int x,int y,int w,int h,const uint16_t *pixels) {
    calls++; submitted += w*h;
    for (int yy=0;yy<h;yy++) for(int xx=0;xx<w;xx++) {
        if(x+xx>=0 && x+xx<320 && y+yy>=0 && y+yy<320)
            screen[(y+yy)*320+x+xx]=pixels[yy*w+xx];
    }
}
static int draw(JPEGDRAW *tile) { return jpeg_output(tile, blit); }
static void check(bool ok,const char *msg) { if(!ok){fprintf(stderr,"FAIL: %s\n",msg);exit(1);} }
int main(int argc,char **argv) {
    uint16_t pixels[32];for(int i=0;i<32;i++)pixels[i]=(uint16_t)(i+1);
    JPEGDRAW tile;memset(&tile,0,sizeof(tile));
    tile.x=3;tile.y=4;tile.iWidth=16;tile.iWidthUsed=7;tile.iHeight=2;tile.pPixels=pixels;
    memset(screen,0,sizeof(screen));calls=submitted=0;
    check(draw(&tile)==1,"tile result");
    check(calls==2 && submitted==14,"padding is not submitted");
    check(screen[4*320+3]==1 && screen[5*320+3]==17,"source row stride");
    check(screen[4*320+10]==0 && screen[5*320+10]==0,"no right-edge bleed");
    tile.iWidthUsed=16;calls=submitted=0;draw(&tile);
    check(calls==1 && submitted==32,"full tile uses one blit");
    for(int arg=1;arg<argc;arg++) {
        FILE *file=fopen(argv[arg],"rb");check(file!=NULL,"fixture open");
        fseek(file,0,SEEK_END);long size=ftell(file);rewind(file);
        uint8_t *data=(uint8_t*)malloc((size_t)size);check(data!=NULL,"fixture allocation");
        check(fread(data,1,(size_t)size,file)==(size_t)size,"fixture read");fclose(file);
        for(int divisor=1;divisor<=8;divisor*=2) {
            JPEGDEC decoder;check(decoder.openRAM(data,(int)size,draw)!=0,"JPEG header");
            int w=(decoder.getWidth()+divisor-1)/divisor,h=(decoder.getHeight()+divisor-1)/divisor;
            if(w>310 || h>310){decoder.close();continue;}
            for(int i=0;i<320*320;i++)screen[i]=0x1234;
            calls=submitted=0;decoder.setPixelType(RGB565_LITTLE_ENDIAN);
            check(decoder.decode(5,7,divisor==1?0:divisor)!=0,"JPEG decode");decoder.close();
            check(submitted==w*h,"exact image pixel count (all scales)");
            for(int y=0;y<320;y++)for(int x=0;x<320;x++)
                if(x<5 || x>=5+w || y<7 || y>=7+h)check(screen[y*320+x]==0x1234,"pixels outside image unchanged");
        }
        free(data);
    }
    puts("PASS: JPEG tile stride/padding, one-blit full tiles and native decoded image bounds at all scales");
}
