/* Fixed-buffer PCM sink for the GungOS Tetris desktop preview. */
#include <SDL.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <sys/stat.h>
#define CAP 4096
typedef struct {int16_t ring[CAP];unsigned read,write;SDL_mutex *lock;} state_t;
static void callback(void *data,Uint8 *stream,int bytes) {
    state_t *s=data;int16_t *out=(int16_t*)stream;
    memset(stream,0,bytes);
    SDL_LockMutex(s->lock);
    unsigned count=s->write-s->read;
    if(count>(unsigned)bytes/2)count=bytes/2;
    for(unsigned i=0;i<count;i++)out[i]=s->ring[(s->read+i)&(CAP-1)];
    s->read+=count;
    SDL_UnlockMutex(s->lock);
}
static void status(const char *path,const char *state) {
    FILE *f=fopen(path,"w");if(f){fprintf(f,"state=%s\nplaying=%d\n",state,strcmp(state,"playing")==0);fclose(f);}
}
int main(int argc,char **argv) {
    if(argc!=4)return 2;
    char command[1024],status_path[1024];
    snprintf(command,sizeof(command),"%s.cmd",argv[2]);
    snprintf(status_path,sizeof(status_path),"%s.status",argv[2]);
    int rate=atoi(argv[3]);
    if(rate<8000||rate>48000)return 2;
    if(SDL_Init(SDL_INIT_AUDIO)<0){fprintf(stderr,"%s\n",SDL_GetError());status(status_path,"error");return 1;}
    state_t state={0};state.lock=SDL_CreateMutex();
    SDL_AudioSpec wanted={0},actual={0};wanted.freq=rate;wanted.format=AUDIO_S16SYS;
    wanted.channels=1;wanted.samples=512;wanted.callback=callback;wanted.userdata=&state;
    SDL_AudioDeviceID device=SDL_OpenAudioDevice(NULL,0,&wanted,&actual,0);
    if(!device){fprintf(stderr,"%s\n",SDL_GetError());status(status_path,"error");SDL_Quit();return 1;}
    int fd=open(argv[1],O_RDONLY|O_NONBLOCK);
    if(fd<0){status(status_path,"error");SDL_CloseAudioDevice(device);SDL_Quit();return 1;}
    status(status_path,"playing");SDL_PauseAudioDevice(device,0);
    unsigned char buffer[4096],header[4];unsigned have=0,needed=0,header_have=0;
    int quit=0;unsigned counter=0;
    while(!quit) {
        if((counter++%8)==0) {
            FILE *f=fopen(command,"r");char text[32];
            if(f){if(fgets(text,sizeof(text),f)&&strstr(text,"stop"))quit=1;fclose(f);}
        }
        if(!needed) {
            int got=read(fd,header+header_have,4-header_have);
            if(got>0)header_have+=got;
            if(header_have==4) {
                needed=(uint32_t)header[0]|((uint32_t)header[1]<<8)|((uint32_t)header[2]<<16)|((uint32_t)header[3]<<24);
                header_have=0;have=0;
                if(needed==UINT32_MAX){quit=1;continue;}
                if(!needed){SDL_LockMutex(state.lock);state.read=state.write;SDL_UnlockMutex(state.lock);}
                else if(needed>sizeof(buffer)||(needed&1)){quit=1;continue;}
            }
        }
        if(needed) {
            if(have<needed){int got=read(fd,buffer+have,needed-have);if(got>0)have+=got;}
            if(have==needed) {
                SDL_LockMutex(state.lock);
                unsigned free=CAP-(state.write-state.read);
                if(free>=needed/2) {
                    for(unsigned i=0;i<needed/2;i++)state.ring[(state.write+i)&(CAP-1)]=(int16_t)((uint16_t)buffer[i*2]|((uint16_t)buffer[i*2+1]<<8));
                    state.write+=needed/2;needed=have=0;
                }
                SDL_UnlockMutex(state.lock);
            }
        }
        SDL_Delay(2);
    }
    SDL_CloseAudioDevice(device);close(fd);SDL_DestroyMutex(state.lock);
    status(status_path,"stopped");SDL_Quit();return 0;
}
