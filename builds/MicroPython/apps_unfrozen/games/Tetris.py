"""GungOS Tetris: Modern/Classic modes, piece statistics and streamed audio.
Replaces Picoware Tetris originally based on lazerduck/PicoCalc_Dashboard.
"""
from random import randint
from time import ticks_ms,ticks_add,ticks_diff
from picoware.system import buttons as k
from engtools.ui import theme
from engtools.system.sfx import Effects
from engtools.system.tetris_tiles import Blocks,STYLES
from engtools.system.tetris_scores import Scores

MODES=('Modern','Classic')
PIECE_NAMES=('I','O','T','S','Z','J','L')

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
        legacy=bool(prefs.get('tetris_sound',True))
        self.music_enabled=bool(prefs.get('tetris_music',legacy))
        self.fx_enabled=bool(prefs.get('tetris_sfx',legacy))
        self.mode=prefs.get('tetris_mode','Modern')
        if self.mode not in MODES:self.mode='Modern'
        self.block_style=prefs.get('tetris_blocks','Pixel')
        if self.block_style not in STYLES:self.block_style='Pixel'
        self.blocks=Blocks()
        self.sound=Effects(self.music_enabled or self.fx_enabled,prefs.get('tetris_volume',25),vm.storage,
                           self.music_enabled,self.fx_enabled)
        self.scores=Scores()
        self.error=''
        self.reset()
    @property
    def best(self):
        current=self.score if getattr(self,'run_mode',None)==self.mode else 0
        return max(self.scores.values[self.mode],current)
    def save_best(self):
        if hasattr(self,'run_mode'):self.scores.record(self.run_mode,self.score)
        saved=self.scores.save()
        if not saved:self.error='Could not save best to internal flash.';self.dirty=True
        elif self.error=='Could not save best to internal flash.':self.error=''
        return saved
    def reset(self):
        self.save_best()
        self.run_mode=self.mode
        self.sound.silence()
        self.grid=bytearray(200)
        self.counts=[0]*7
        self.page='game';self.menu_started=None
        self.settings_row=0;self.help_first=0;self.help_return='game'
        self.pending_mode=None;self.confirm_row=1;self.confirm_return='game'
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
        fresh=piece is None
        if fresh:
            piece=self.queue.pop(0);self.queue.append(self.piece())
        self.current,self.rotation,self.x,self.y=piece,0,3,-1
        self.hold_used=False
        self.lock_at=None;self.lock_resets=0
        self.drop_at=ticks_add(ticks_ms(),self.gravity())
        if self.collides(self.x,self.y,self.rotation):self.end()
        elif fresh:self.counts[piece]+=1
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
        if self.mode=='Classic' or self.hold_used:return False
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
        self.scores.record(self.run_mode,self.score);self.spawn()
    def end(self):
        self.over=True;self.save_best();self.sound.play('game_over');self.dirty=True
    def pause(self):
        self.save_best()
        self.paused=not self.paused;self.sound.pause(self.paused);self.dirty=True
        self.drop_at=ticks_add(ticks_ms(),self.gravity())
        if self.lock_at is not None:self.lock_at=ticks_ms()
    @property
    def next_count(self):return 1 if self.mode=='Classic' else 3
    def settings(self,key,value):
        """Save first; a failed SD write must not change the live game/audio."""
        from picoware.system.settings import Settings
        music,fx=self.music_enabled,self.fx_enabled
        values={key:value}
        if key=='tetris_sound':music=fx=bool(value)
        elif key=='tetris_music':music=bool(value)
        elif key=='tetris_sfx':fx=bool(value)
        elif key=='tetris_mode' and value not in MODES:return False
        elif key=='tetris_blocks' and value not in STYLES:return False
        if key in ('tetris_sound','tetris_music','tetris_sfx'):
            values.update(tetris_music=music,tetris_sfx=fx,tetris_sound=music or fx)
        if not Settings(self.vm.storage).update(values):
            self.error='Could not save settings. Check SD.';self.dirty=True;return False
        self.error=''
        if key=='tetris_mode':
            self.save_best();self.mode=value
        elif key=='tetris_blocks':self.block_style=value
        else:
            self.music_enabled,self.fx_enabled=music,fx
            volume=value if key=='tetris_volume' else self.sound.volume
            self.sound.configure(music or fx,volume,music,fx)
        self.dirty=True;return True
    def open_page(self,page,now):
        if self.page=='game':
            self.save_best()
            self.menu_started=now;self.sound.pause(True)
        self.page=page;self.dirty=True
    def close_page(self,now):
        if self.menu_started is not None:
            elapsed=max(0,ticks_diff(now,self.menu_started))
            self.drop_at=ticks_add(self.drop_at,elapsed)
            if self.lock_at is not None:self.lock_at=ticks_add(self.lock_at,elapsed)
        self.menu_started=None;self.page='game'
        self.sound.pause(self.paused);self.dirty=True
    def request_restart(self,mode=None,return_page='game'):
        self.pending_mode=mode;self.confirm_return=return_page;self.confirm_row=1
        self.page='restart';self.dirty=True
    def menu_input(self,button,now):
        if button==k.BUTTON_NONE:return
        self.dirty=True
        if self.page=='help':
            capacity=self.help_capacity()
            limit=max(0,len(self.help_layout())-capacity)
            if button in (k.BUTTON_F9,k.BUTTON_ESCAPE):
                if self.help_return=='game':self.close_page(now)
                else:self.page=self.help_return
            elif button in (k.BUTTON_UP,k.BUTTON_DOWN):
                self.help_first=max(0,min(limit,self.help_first+(-1 if button==k.BUTTON_UP else 1)))
            elif button in (k.BUTTON_LEFT,k.BUTTON_RIGHT):
                self.help_first=max(0,min(limit,self.help_first+(-capacity if button==k.BUTTON_LEFT else capacity)))
            elif button in (k.BUTTON_HOME,k.BUTTON_CTRL_UP):self.help_first=0
            elif button in (k.BUTTON_END,k.BUTTON_CTRL_DOWN):self.help_first=limit
            return
        if button==k.BUTTON_F9:
            self.help_return=self.page;self.help_first=0;self.page='help';return
        if self.page=='restart':
            if button==k.BUTTON_ESCAPE:
                if self.confirm_return=='game':self.close_page(now)
                else:self.page=self.confirm_return
                return
            if button in (k.BUTTON_UP,k.BUTTON_DOWN,k.BUTTON_LEFT,k.BUTTON_RIGHT):self.confirm_row=1-self.confirm_row
            elif button==k.BUTTON_CENTER:
                if self.confirm_row==1:self.page=self.confirm_return
                elif self.pending_mode is None or self.settings('tetris_mode',self.pending_mode):
                    self.reset();return
            if self.page=='game':self.close_page(now)
            return
        if button in (k.BUTTON_ESCAPE,k.BUTTON_F2):self.close_page(now);return
        if button in (k.BUTTON_UP,k.BUTTON_DOWN):
            self.settings_row=(self.settings_row+(-1 if button==k.BUTTON_UP else 1))%7
        elif button in (k.BUTTON_CENTER,k.BUTTON_LEFT,k.BUTTON_RIGHT):
            step=-1 if button==k.BUTTON_LEFT else 1
            row=self.settings_row
            if row==0:self.request_restart(MODES[1-MODES.index(self.mode)],'settings')
            elif row==1:self.settings('tetris_music',not self.music_enabled)
            elif row==2:self.settings('tetris_sfx',not self.fx_enabled)
            elif row==3:self.settings('tetris_volume',(self.sound.volume+step*25)%125)
            elif row==4:self.settings('tetris_blocks',STYLES[(STYLES.index(self.block_style)+step)%len(STYLES)])
            elif row==5:self.request_restart(return_page='settings')
            else:self.close_page(now)
    def run(self,button,now=None):
        now=ticks_ms() if now is None else now
        self.sound.tick(now)
        if self.page!='game':
            self.menu_input(button,now)
            if self.dirty:self.draw()
            return
        if button==k.BUTTON_ESCAPE:self.vm.back();return
        if button==k.BUTTON_F9:
            self.help_return='game';self.help_first=0;self.open_page('help',now)
        elif button==k.BUTTON_F2:self.open_page('settings',now)
        elif button==k.BUTTON_F3:self.settings('tetris_music',not self.music_enabled)
        elif button==k.BUTTON_F4:self.settings('tetris_sfx',not self.fx_enabled)
        elif button==k.BUTTON_F5:
            if self.over or self.paused:self.reset()
            else:self.open_page('restart',now);self.request_restart()
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
        if self.page!='game':self.draw();return
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
    def help_lines(self):
        return (
            'Play:',
            'LEFT/RIGHT\tmove the falling piece',
            'UP\trotate clockwise',
            'Z\trotate counter-clockwise',
            'DOWN\tsoft drop (+1 point per cell)',
            'ENTER / SPACE\thard drop (+2 per cell)',
            'C\thold / swap (Modern mode only)',
            'P\tpause or resume',
            'ESC\tleave Tetris from the game screen',
            'Function keys:',
            'F2\topen / close Settings',
            'F3\ttoggle music',
            'F4\ttoggle sound effects',
            'F5\tnew game (confirms during play)',
            'F9\tshow / close this help',
            'Settings:',
            'UP/DOWN\tchoose a setting',
            'LEFT/RIGHT\tchange it; ENTER too',
            'Mode change starts a new game; confirm first.',
            'Music, FX, volume and block style save to SD.',
            'A failed save keeps your current settings.',
            'Menus freeze gravity, lock delay and audio.',
            'ESC returns without unpausing a paused game.',
            'Modes and statistics:',
            'Classic: one next piece; hold disabled.',
            'Modern: three next pieces and one hold slot.',
            'Both use seven-bag, SRS and current scoring.',
            'Both retain the landing-outline preview.',
            'Counts track new pieces entering play.',
            'Swapping a held piece does not add a count.',
            'Counts reset when a new game starts.',
            'Ten cleared lines advance the level.',
            'Level colours repeat after ten palettes.',
            'Block styles: Pixel / Bevel / Solid.')
    def help_layout(self):
        from picoware.gui import overlay
        return overlay.layout(self.help_lines(),overlay.RECT[2])
    def help_capacity(self):
        from picoware.gui import overlay
        return overlay.capacity(overlay.RECT[3])
    def draw_help(self,p):
        from picoware.gui import overlay
        lines=self.help_layout();capacity=self.help_capacity()
        self.help_first=max(0,min(self.help_first,max(0,len(lines)-capacity)))
        overlay.paint(self.vm.draw,p,overlay.RECT,'KEYBINDINGS',lines,self.help_first)
    def draw_settings(self,p):
        rows=(('Mode',self.mode+' / '+str(self.next_count)+' next / '+('no hold' if self.mode=='Classic' else 'hold')),
              ('Music','On' if self.music_enabled else 'Off'),
              ('Sound FX','On' if self.fx_enabled else 'Off'),
              ('Volume',str(self.sound.volume)+'%'),('Block style',self.block_style),
              ('New game','Reset board and piece counts'),('Return','Keep playing'))
        error=self.error or self.sound.error
        theme.menu(self.vm.draw,rows,self.settings_row,'Games / Tetris / Settings','GungOS',
                   error,palette=p,error=bool(error))
        self.dirty=False
    def draw_restart(self,p):
        label='Start '+self.pending_mode if self.pending_mode else 'New game'
        theme.menu(self.vm.draw,((label,'Reset board and piece counts'),('Cancel','Keep the current game')),
                   self.confirm_row,'Games / Tetris / Confirm','GungOS',
                   self.error,palette=p,error=bool(self.error))
        self.dirty=False
    def preview(self,piece,x,y,size):
        if piece is None:return
        cells=SHAPES[piece];min_x=min(a for a,b in cells);min_y=min(b for a,b in cells)
        for dx,dy in cells:self.blocks.draw(self.vm.draw,piece,x+(dx-min_x)*size,y+(dy-min_y)*size,size-1)
    def draw(self):
        p=theme.system_palette(self.vm)
        if self.page=='settings':self.draw_settings(p);return
        if self.page=='restart':self.draw_restart(p);return
        self.draw_board(p)
        # Help is a box over the paused board.
        if self.page=='help':self.draw_help(p)
        self.vm.draw.swap();self.dirty=False
    def draw_board(self,p):
        d=self.vm.draw;w,h=int(d.size.x),int(d.size.y)
        cell=max(3,min(13,(h-52)//20,(w-170)//10))
        left,top=max(76,(w-150)//2),30
        right=left+cell*10+10
        self.blocks.prepare(self.level,self.block_style,p.BG)
        d.fill_screen(p.BG)
        theme.header(d,'Games / Tetris / '+self.mode,palette=p)
        d._rectangle(4,28,left-13,cell*20+4,p.GRID)
        d._text(10,36,'PIECES',p.ACCENT,0)
        for piece in range(7):
            y=57+piece*30
            if piece==self.current and not self.over:
                d._fill_rectangle(6,y-4,left-17,26,p.SELECT)
            d._text(9,y+4,PIECE_NAMES[piece],p.MUTED,0)
            self.preview(piece,20,y+2,5)
            count=str(self.counts[piece]) if self.counts[piece]<10000 else '9999+'
            d._text(left-16-d.len(count,0),y+5,count,p.TEXT,0)
        d._text(10,top+cell*20-12,'N '+str(sum(self.counts)),p.MUTED,0)
        d._rectangle(left-2,top-2,cell*10+4,cell*20+4,p.AXIS)
        for i in range(1,10):d._line(left+i*cell,top,left+i*cell,top+20*cell,p.GRID)
        for i in range(1,20):d._line(left,top+i*cell,left+10*cell,top+i*cell,p.GRID)
        def block(x,y,piece,ghost=False):
            if y<0:return
            px,py=left+x*cell+1,top+y*cell+1
            if ghost:d._rectangle(px,py,cell-2,cell-2,p.MUTED)
            else:self.blocks.draw(d,piece,px,py,cell-1)
        for y in range(20):
            for x in range(10):
                if self.grid[y*10+x]:block(x,y,self.grid[y*10+x]-1)
        if not self.over:
            ghost=self.y
            while not self.collides(self.x,ghost+1,self.rotation):ghost+=1
            for x,y in shape(self.current,self.rotation):block(self.x+x,ghost+y,self.current,True)
            for x,y in shape(self.current,self.rotation):block(self.x+x,self.y+y,self.current)
        d._rectangle(right-2,28,w-right-3,cell*20+4,p.GRID)
        for i,(name,value) in enumerate((('SCORE',self.score),('LINES',self.lines),('LEVEL',self.level),('BEST',self.best))):
            y=36+i*30;d._text(right+4,y,name,p.MUTED,0)
            text=str(value);font=1 if d.len(text,1)<w-right-8 else 0
            d._text(right+4,y+11,text,p.TEXT,font)
        d._text(right+4,165,'NEXT',p.ACCENT,0)
        for i,piece in enumerate(self.queue[:self.next_count]):self.preview(piece,right+4,182+i*33,7)
        hold_x=right+47
        if self.mode=='Modern':
            d._text(hold_x,165,'HOLD',p.ACCENT,0);self.preview(self.held,hold_x,182,7)
        else:d._text(hold_x,165,'--',p.MUTED,0)
        for y,name,enabled in ((218,'MUSIC',self.music_enabled),(252,'FX',self.fx_enabled)):
            d._text(hold_x,y,name,p.MUTED,0)
            d._text(hold_x,y+11,'ON' if enabled else 'OFF',p.TEXT,0)
        if self.paused or self.over:
            x,y=left+3,top+88
            d._fill_rectangle(x,y,cell*10-6,73,p.PANEL)
            d._rectangle(x,y,cell*10-6,73,p.ACCENT)
            d._text(x+6,y+8,'GAME OVER' if self.over else 'PAUSED',p.ERROR if self.over else p.ACCENT,0)
            d._text(x+6,y+29,'Enter restart' if self.over else 'P resumes',p.TEXT,0)
            d._text(x+6,y+49,'F5 new game',p.MUTED,0)
        error=self.error or self.sound.error
        theme.footer(d,error,bool(error),p)
    def stop(self):
        self.save_best();self.sound.stop();self.grid=None;self.blocks.cache={}

_game=None
def start(vm):
    global _game
    # Borrow the faster SRAM screen while playing; returned when the view stops.
    fast=getattr(vm,'request_fast_drawing',None)
    if fast:fast()
    _game=Game(vm);_game.draw();return True
def run(vm):
    if _game is not None:_game.run(vm.button)
def stop(vm):
    global _game
    if _game is not None:_game.stop()
    _game=None
