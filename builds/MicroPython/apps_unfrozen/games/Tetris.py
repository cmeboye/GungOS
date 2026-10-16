"""GungOS Tetris: seven-bag pieces, SRS kicks, hold/ghost and paced sound events.
Replaces Picoware Tetris originally based on lazerduck/PicoCalc_Dashboard.
The former implementation is retained under app_backups/gungos-v21.
"""
from random import randint
from time import ticks_ms,ticks_add,ticks_diff
from picoware.system import buttons as k
from engtools.ui import theme
from engtools.system.sfx import Effects

SHAPES=(((0,1),(1,1),(2,1),(3,1)),((1,0),(2,0),(1,1),(2,1)),
        ((1,0),(0,1),(1,1),(2,1)),((1,0),(2,0),(0,1),(1,1)),
        ((0,0),(1,0),(1,1),(2,1)),((0,0),(0,1),(1,1),(2,1)),
        ((2,0),(0,1),(1,1),(2,1)))
COLORS=(0x07FF,0xFFE0,0xF81F,0x07E0,0xF800,0x001F,0xFD20)
KICKS={
    (0,1):((0,0),(-1,0),(-1,1),(0,-2),(-1,-2)),
    (1,0):((0,0),(1,0),(1,-1),(0,2),(1,2)),
    (1,2):((0,0),(1,0),(1,-1),(0,2),(1,2)),
    (2,1):((0,0),(-1,0),(-1,1),(0,-2),(-1,-2)),
    (2,3):((0,0),(1,0),(1,1),(0,-2),(1,-2)),
    (3,2):((0,0),(-1,0),(-1,-1),(0,2),(-1,2)),
    (3,0):((0,0),(-1,0),(-1,-1),(0,2),(-1,2)),
    (0,3):((0,0),(1,0),(1,1),(0,-2),(1,-2))}
I_KICKS={
    (0,1):((0,0),(-2,0),(1,0),(-2,-1),(1,2)),
    (1,0):((0,0),(2,0),(-1,0),(2,1),(-1,-2)),
    (1,2):((0,0),(-1,0),(2,0),(-1,2),(2,-1)),
    (2,1):((0,0),(1,0),(-2,0),(1,-2),(-2,1)),
    (2,3):((0,0),(2,0),(-1,0),(2,1),(-1,-2)),
    (3,2):((0,0),(-2,0),(1,0),(-2,-1),(1,2)),
    (3,0):((0,0),(1,0),(-2,0),(1,-2),(-2,1)),
    (0,3):((0,0),(-1,0),(2,0),(-1,2),(2,-1))}

def shape(piece,rotation=0):
    result=SHAPES[piece]
    if piece==1:return result
    edge=3 if piece==0 else 2
    for _ in range(rotation%4):result=tuple((edge-y,x) for x,y in result)
    return result

class Game:
    def __init__(self,vm):
        self.vm=vm
        from picoware.system.settings import Settings
        prefs=Settings(vm.storage).settings
        self.sound=Effects(prefs.get('tetris_sound',True),prefs.get('tetris_volume',25),vm.storage)
        self.best=0
        self.error=''
        self.reset()
    def reset(self):
        self.sound.silence()
        self.grid=bytearray(200)
        self.bag,self.queue=[],[]
        self.score,self.lines,self.level=0,0,1
        self.held=None;self.hold_used=False
        self.over,self.paused=False,False
        self.dirty=True;self.last_draw=0
        while len(self.queue)<4:self.queue.append(self.piece())
        self.spawn()
        self.sound.restart()
    def piece(self):
        if not self.bag:
            self.bag=list(range(7))
            for i in range(6,0,-1):
                j=randint(0,i);self.bag[i],self.bag[j]=self.bag[j],self.bag[i]
        return self.bag.pop()
    def gravity(self):return max(70,900-(self.level-1)*70)
    def spawn(self,piece=None):
        if piece is None:
            piece=self.queue.pop(0);self.queue.append(self.piece())
        self.current,self.rotation,self.x,self.y=piece,0,3,-1
        self.hold_used=False
        self.lock_at=None;self.lock_resets=0
        self.drop_at=ticks_add(ticks_ms(),self.gravity())
        if self.collides(self.x,self.y,self.rotation):self.end()
        self.dirty=True
    def collides(self,x,y,rotation):
        for dx,dy in shape(self.current,rotation):
            xx,yy=x+dx,y+dy
            if xx<0 or xx>=10 or yy>=20 or (yy>=0 and self.grid[yy*10+xx]):return True
        return False
    def landed(self):return self.collides(self.x,self.y+1,self.rotation)
    def reset_lock(self):
        if self.lock_at is not None and self.lock_resets<15:
            self.lock_at=ticks_ms();self.lock_resets+=1
    def move(self,dx):
        if self.collides(self.x+dx,self.y,self.rotation):return False
        self.x+=dx;self.reset_lock();self.dirty=True;self.sound.play('move');return True
    def rotate(self,direction=1):
        target=(self.rotation+direction)%4
        tests=((0,0),) if self.current==1 else (I_KICKS if self.current==0 else KICKS)[(self.rotation,target)]
        for dx,dy in tests:
            if not self.collides(self.x+dx,self.y-dy,target):
                self.x+=dx;self.y-=dy;self.rotation=target
                self.reset_lock();self.dirty=True;self.sound.play('rotate');return True
        return False
    def soft_drop(self):
        if self.landed():return False
        self.y+=1;self.score+=1;self.dirty=True
        self.drop_at=ticks_add(ticks_ms(),self.gravity());return True
    def hard_drop(self):
        distance=0
        while not self.landed():self.y+=1;distance+=1
        self.score+=distance*2;self.lock()
    def hold(self):
        if self.hold_used:return False
        current=self.current
        if self.held is None:self.spawn()
        else:self.spawn(self.held)
        self.held=current;self.hold_used=True;self.sound.play('hold');self.dirty=True;return True
    def clear_lines(self):
        destination=19;cleared=0
        for row in range(19,-1,-1):
            if all(self.grid[row*10+col] for col in range(10)):cleared+=1;continue
            if row!=destination:
                for col in range(10):self.grid[destination*10+col]=self.grid[row*10+col]
            destination-=1
        for index in range((destination+1)*10):self.grid[index]=0
        return cleared
    def lock(self):
        positions=tuple((self.x+dx,self.y+dy) for dx,dy in shape(self.current,self.rotation))
        if any(y<0 for x,y in positions):self.end();return
        for x,y in positions:self.grid[y*10+x]=self.current+1
        cleared=self.clear_lines()
        if cleared:
            self.score+=(0,100,300,500,800)[cleared]*self.level
            self.lines+=cleared
            new_level=1+self.lines//10
            self.sound.play('tetris' if cleared==4 else 'clear')
            if new_level>self.level:self.sound.play('level')
            self.level=new_level
        else:self.sound.play('lock')
        self.best=max(self.best,self.score);self.spawn()
    def end(self):
        self.over=True;self.best=max(self.best,self.score);self.sound.play('game_over');self.dirty=True
    def pause(self):
        self.paused=not self.paused;self.sound.pause(self.paused);self.dirty=True
        self.drop_at=ticks_add(ticks_ms(),self.gravity())
        if self.lock_at is not None:self.lock_at=ticks_ms()
    def settings(self,key,value):
        from picoware.system.settings import Settings
        if not Settings(self.vm.storage).update({key:value}):
            self.error='Could not save sound setting';self.dirty=True;return False
        self.error=''
        enabled=value if key=='tetris_sound' else self.sound.enabled
        volume=value if key=='tetris_volume' else self.sound.volume
        self.sound.configure(enabled,volume);self.dirty=True;return True
    def run(self,button,now=None):
        now=ticks_ms() if now is None else now
        self.sound.tick(now)
        if button == k.BUTTON_ESCAPE:self.vm.back();return
        if button==k.BUTTON_F3:self.settings('tetris_sound',not self.sound.enabled)
        elif button==k.BUTTON_F4:self.settings('tetris_volume',(self.sound.volume+25)%125)
        elif button==k.BUTTON_F5 and (self.over or self.paused):self.reset()
        elif button==k.BUTTON_P and not self.over:self.pause()
        elif self.over and button==k.BUTTON_CENTER:self.reset()
        elif not self.paused and not self.over:
            if button==k.BUTTON_LEFT:self.move(-1)
            elif button==k.BUTTON_RIGHT:self.move(1)
            elif button==k.BUTTON_UP:self.rotate()
            elif button==k.BUTTON_Z:self.rotate(-1)
            elif button==k.BUTTON_DOWN:self.soft_drop()
            elif button in (k.BUTTON_CENTER,k.BUTTON_SPACE):self.hard_drop()
            elif button==k.BUTTON_C:self.hold()
        if not self.paused and not self.over:
            if self.landed():
                if self.lock_at is None:self.lock_at=now
                if ticks_diff(now,self.lock_at)>=500:self.lock()
            else:
                self.lock_at=None
                if ticks_diff(now,self.drop_at)>=0:
                    self.y+=1;self.drop_at=ticks_add(now,self.gravity());self.dirty=True
        if self.dirty and ticks_diff(now,self.last_draw)>=33:
            self.draw();self.last_draw=now
    def draw(self):
        palette=theme.system_palette(self.vm)
        d=self.vm.draw;w,h=int(d.size.x),int(d.size.y)
        cell=max(3,min((h-70)//20,(w-130)//10));left,top=14,30
        panel=left+cell*10+15
        d.fill_screen(palette.BG)
        d._fill_rectangle(0,0,w,23,palette.PANEL);d._text(8,6,'GungOS / TETRIS',palette.ACCENT,1)
        d._rectangle(left-2,top-2,cell*10+4,cell*20+4,palette.AXIS)
        for i in range(1,10):d._line(left+i*cell,top,left+i*cell,top+20*cell,palette.GRID)
        for i in range(1,20):d._line(left,top+i*cell,left+10*cell,top+i*cell,palette.GRID)
        def block(x,y,color,ghost=False):
            if y<0:return
            px,py=left+x*cell+1,top+y*cell+1
            if ghost:d._rectangle(px,py,cell-2,cell-2,palette.MUTED)
            else:d._fill_rectangle(px,py,cell-2,cell-2,color)
        for y in range(20):
            for x in range(10):
                if self.grid[y*10+x]:block(x,y,COLORS[self.grid[y*10+x]-1])
        if not self.over:
            ghost=self.y
            while not self.collides(self.x,ghost+1,self.rotation):ghost+=1
            for x,y in shape(self.current,self.rotation):block(self.x+x,ghost+y,COLORS[self.current],True)
            for x,y in shape(self.current,self.rotation):block(self.x+x,self.y+y,COLORS[self.current])
        for i,(name,value) in enumerate((('SCORE',self.score),('LINES',self.lines),('LEVEL',self.level),('BEST (session)',self.best))):
            y=32+i*29;d._text(panel,y,name,palette.MUTED,0);d._text(panel,y+11,str(value),palette.TEXT,1)
        d._text(panel,154,'NEXT',palette.ACCENT,0)
        def preview(piece,x,y):
            if piece is None:return
            for dx,dy in shape(piece):d._fill_rectangle(x+dx*9,y+dy*9,8,8,COLORS[piece])
        for i,piece in enumerate(self.queue[:3]):preview(piece,panel,169+i*34)
        d._text(panel+66,154,'HOLD',palette.ACCENT,0);preview(self.held,panel+66,169)
        d._text(panel+66,214,'SOUND',palette.MUTED,0)
        d._text(panel+66,226,'OFF' if not self.sound.enabled else str(self.sound.volume)+'%',palette.ACCENT,0)
        d._text(panel+66,242,'F3 mute',palette.MUTED,0);d._text(panel+66,253,'F4 volume',palette.MUTED,0)
        if self.paused or self.over:
            d._fill_rectangle(left+2,top+85,cell*10-4,80,palette.PANEL)
            d._text(left+6,top+93,'GAME OVER' if self.over else 'PAUSED',palette.ERROR if self.over else palette.ACCENT,0)
            d._text(left+6,top+115,'Enter restart' if self.over else 'P resumes',palette.TEXT,0)
            d._text(left+6,top+136,'F5 new game',palette.MUTED,0)
        d._fill_rectangle(0,h-36,w,36,palette.PANEL)
        d._text(6,h-30,'L/R move  UP/Z rotate  DOWN soft drop',palette.ACCENT,0)
        d._text(6,h-17,(self.error or self.sound.error or 'ENTER/SPACE drop  C hold  P pause  ESC exit')[:51],palette.ERROR if self.error or self.sound.error else palette.MUTED,0)
        d.swap();self.dirty=False
    def stop(self):self.sound.stop();self.grid=None

_game=None
def start(vm):
    global _game
    _game=Game(vm);_game.draw();return True
def run(vm):
    if _game is not None:_game.run(vm.button)
def stop(vm):
    global _game
    if _game is not None:_game.stop()
    _game=None
