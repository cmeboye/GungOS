#include <stdio.h>
#include <stdlib.h>
#include "../../src/MicroPython/png/png_core.h"
typedef struct { FILE *file;gungos_png_info *info; } output;
static int read_png(void *p,uint8_t *b,int n) { return fread(b,1,n,p); }
static int write_row(void *p,int y,int width,const uint8_t *b) {
    (void)y;output *o=p;return fwrite(b,1,width,o->file)==(unsigned)width;
}
int main(int argc,char **argv) {
    if (argc!=6) return 2;
    FILE *in=fopen(argv[1],"rb"),*out=fopen(argv[2],"wb");if (!in || !out) return 2;
    fseek(in,0,SEEK_END);long size=ftell(in);rewind(in);fseek(out,8,SEEK_SET);
    void *work=malloc(gungos_png_workspace_size());gungos_png_info info={0};output o={out,&info};
    const char *error=gungos_png_decode(work,read_png,in,size,atoi(argv[3]),atoi(argv[4]),strtoul(argv[5],NULL,16),write_row,&o,&info);
    if (error) fprintf(stderr,"%s\n",error);
    else { rewind(out);uint8_t b[8]={info.width&255,info.width>>8,info.height&255,info.height>>8,
        info.source_width&255,info.source_width>>8,info.source_height&255,info.source_height>>8};fwrite(b,1,8,out); }
    free(work);fclose(in);fclose(out);
    if (error) { remove(argv[2]);return 1; }
    printf("workspace=%zu bytes\n",gungos_png_workspace_size());return 0;
}
