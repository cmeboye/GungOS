"""Cooperative Beam/PicoCAD render stress ladder with SD checkpoints.

Uses actual app draw code and the normal panel format. No user model/session,
settings or native capacity is changed. Native solver/draw calls are atomic;
deadlines and Escape are checked between those calls, never inside them.
"""
import gc, json, sys
from time import ticks_us, ticks_ms, ticks_diff
from picoware.system import buttons as k
from picoware.system.features import FIRMWARE_VERSION
from engtools.ui import theme
from . import models

RESULT_PATH = 'picoware/engtool-render-benchmark.txt'
RESERVE = 32 * 1024
WORK_LIMIT_US = 30 * 1000000
MODES = ('Both', 'PSRAM', 'SRAM')
HELP = ('ENGTOOL RENDER BENCHMARK',
        'ENTER: start the selected test ladder',
        'F2: Quick / Full stress', 'F3: Both / PSRAM / SRAM screen',
        'F4: original display / CPU benchmark',
        'F5: skip the current case', 'ESC: cancel, keep completed results',
        'F9: show / hide this help', '',
        'Full: real editor limits, then synthetic',
        'Beam models above the editor limits.',
        'CAD: 8 steps, quality 24, camera zoom',
        '1x/4x/16x, perspective and isometric.',
        'Five-cycle build/release checks too.', '',
        'Memory: GC heap only; sampled live use',
        'can miss a temporary allocation peak.',
        'Native info is reported separately.',
        'Build/solve, compose and swap are timed',
        'separately with normal garbage collection.', '',
        'A 32 KB free-heap reserve stops a case.',
        '30 seconds of measured work stops it',
        'between calls. Native calls cannot be',
        'interrupted; a hang leaves its last',
        'START/phase checkpoint on the SD.', '',
        'A failure stops remaining cases in that',
        'family/screen mode; other families run.',
        'Expected CAD refusals are NOT failures.',
        'No settings or documents are changed.')


class ResourceStop(Exception):
    pass


class MeterDraw:
    def __init__(self, draw): self.draw, self.swap_us, self.rows = draw, 0, 0
    def __getattr__(self, name): return getattr(self.draw, name)
    def swap(self):
        start = ticks_us(); result = self.draw.swap()
        self.swap_us += ticks_diff(ticks_us(), start)
        if isinstance(result, int): self.rows += result
        return result


class QuietVM:
    def __init__(self, vm, draw): self.master, self.draw = vm, draw
    @property
    def button(self): return k.BUTTON_NONE
    def __getattr__(self, name): return getattr(self.master, name)


def _mode(draw):
    return 'SRAM' if draw.mode == draw.MODE_SRAM else 'PSRAM'


def _median(values):
    values = sorted(values)
    return values[len(values)//2]


def _frames(draw, render, update):
    """Normal app frames: compose + present, including cache misses on frame 1."""
    frames, compose, swaps, rows = [], [], [], []
    for index in range(3):
        update(index)
        draw.swap_us, draw.rows = 0, 0
        start = ticks_us(); render(); elapsed = ticks_diff(ticks_us(), start)
        frames.append(elapsed); swaps.append(draw.swap_us)
        compose.append(max(0, elapsed-draw.swap_us)); rows.append(draw.rows)
        yield None
    yield dict(frame_first_us=frames[0], frame_median_us=_median(frames), frame_max_us=max(frames),
               compose_median_us=_median(compose), swap_median_us=_median(swaps), dirty_rows=rows)


def _imports(kind):
    if kind in ('beam','frame'):
        from engtools.beamlab import model
        from engtools.beamlab.app import BeamLab
        return model, BeamLab
    from engtools.picocad import model
    from engtools.picocad.geometry import Build
    from engtools.picocad.draw import Camera, built, axes
    return model, Build, Camera, built, axes


def _case_job(vm, case, measure):
    kind, count, quality, cycles = case
    api = _imports(kind)
    gc.collect(); baseline = gc.mem_alloc(); free = gc.mem_free(); peak = baseline
    row = dict(kind=kind, count=count, quality_or_cases=quality, cycles=cycles,
               screen=_mode(vm.draw), heap_free_before=free, status='ok', pages=[])
    builder = tool = geometry = model = camera = build_job = None
    cycle_free, times = [], []
    expected = {'limit':'limit','invalid':'invalid','unsupported':'unsupported'}.get(kind)
    try:
        if free < RESERVE: raise ResourceStop('32 KB heap reserve before model')
        for cycle in range(cycles):
            yield 'model factory / cycle '+str(cycle+1)
            start = ticks_us()
            model = models.beam(count, kind=='frame', quality) if kind in ('beam','frame') else models.cad(kind,count,quality)
            row['model_us'] = ticks_diff(ticks_us(),start)
            if gc.mem_free() < RESERVE: raise ResourceStop('32 KB heap reserve before build')
            if kind in ('beam','frame'):
                bm, cls = api
                # Constructor restoration is deliberately disabled only during
                # creation, then put back immediately. close()/keep() is not used.
                from engtools import session
                kept = session.kept.pop('beam', None)
                try: tool = cls(vm)
                finally:
                    if kept is not None: session.kept['beam'] = kept
                tool.model = model
                yield 'solve + diagram preparation'
                start=ticks_us(); tool.resolve()
                times.append(ticks_diff(ticks_us(),start))
                if tool.problem is not None:
                    if 'memory' in str(tool.problem).lower(): raise MemoryError(str(tool.problem))
                    raise ValueError(str(tool.problem))
                tool.select_point(0,0.0);tool.page='model'
                row.update(members=len(model['members']), loads=len(model['loads']),
                           native_info=tool.solution.info, nodes=len(tool.solution.nodes),
                           elements=len(tool.solution.elements),
                           synthetic=len(model['members'])>bm.MAX_MEMBERS or bm.item_count(model)>bm.MAX_ITEMS)
                for page in ('model','diagrams','overview'):
                    yield 'draw '+page
                    tool.page = 'diagrams' if page=='overview' else page
                    tool.whole = page=='overview'; tool.cache=None
                    def update(i):
                        tool.zoom = i%3
                        tool.s = bm.member_length(model,0)*i/3
                        tool.ds = tool.s
                        tool.quantity = i%3
                    for sample in _frames(measure, tool.draw, update):
                        if sample is not None and cycle==cycles-1:
                            sample['page']=page;row['pages'].append(sample)
                        gc.collect();peak=max(peak,gc.mem_alloc())
                        if gc.mem_free()<RESERVE:raise ResourceStop('32 KB heap reserve during drawing')
                        yield None
            else:
                dm, cls, camera_cls, built, axes = api
                yield 'analytic boundary build'
                start=ticks_us();builder=cls(model)
                active=ticks_diff(ticks_us(),start);build_start=start
                build_job=builder.job()
                while True:
                    start=ticks_us()
                    try:next(build_job)
                    except StopIteration:
                        active+=ticks_diff(ticks_us(),start);break
                    active+=ticks_diff(ticks_us(),start)
                    gc.collect();peak=max(peak,gc.mem_alloc())
                    if gc.mem_free()<RESERVE:raise ResourceStop('32 KB heap reserve during build')
                    yield None
                build_job=None
                row['build_active_us']=active
                row['build_wall_us']=ticks_diff(ticks_us(),build_start)
                geometry=builder.geometry
                row.update(features=len(model['features']), bodies=builder.body_count,
                           geometry_status=builder.status,
                           packed_bytes=4*sum(len(a) for a in (geometry.lines,geometry.circles,geometry.surfaces,geometry.arcs,geometry.spans)))
                camera=camera_cls()
                rect=(12,64,296,135);box=dm.bounds(model)
                yield 'camera fit'
                start=ticks_us();camera.fit(box,rect,geometry)
                row['fit_us']=ticks_diff(ticks_us(),start)
                row['segments']=sum(1 for _ in geometry.projected(camera))
                for projection in ('Perspective','Isometric'):
                    yield 'draw '+projection
                    camera.projection=projection
                    def update(i):
                        camera.zoom=(1.0,4.0,16.0)[i]
                        camera.yaw=.7+i*.2;camera.setup(box,rect)
                    def draw():
                        palette=theme.system_palette(vm)
                        vm.draw.fill_screen(palette.BG)
                        built(vm.draw,camera,geometry,palette);axes(vm.draw,camera,palette)
                        theme.header(vm.draw,'EngTool benchmark / PicoCAD',palette=palette,height=18)
                        vm.draw.swap()
                    for sample in _frames(measure, draw, update):
                        if sample is not None and cycle==cycles-1:
                            sample['page']=projection;row['pages'].append(sample)
                        gc.collect();peak=max(peak,gc.mem_alloc())
                        if gc.mem_free()<RESERVE:raise ResourceStop('32 KB heap reserve during drawing')
                        yield None
                if expected: raise AssertionError('Expected '+expected+' rejection was accepted')
            gc.collect();peak=max(peak,gc.mem_alloc())
            if tool is not None and tool.solution is not None: tool.solution.free();tool.solution=None
            if builder is not None:builder.release()
            if build_job is not None:build_job.close();build_job=None
            builder=tool=geometry=model=camera=None
            gc.collect();cycle_free.append(gc.mem_free())
            if gc.mem_free()<RESERVE:raise ResourceStop('32 KB heap reserve after cycle')
    except Exception as exc:
        actual=getattr(exc,'kind',None)
        row['status']='expected refusal' if expected and actual==expected else ('memory' if isinstance(exc,MemoryError) else 'reserve' if isinstance(exc,ResourceStop) else 'error')
        row['error']=str(exc)[:160]
        if actual is not None: row['diagnostic']=actual
    finally:
        if build_job is not None:build_job.close();build_job=None
        if tool is not None and tool.solution is not None:tool.solution.free();tool.solution=None
        if builder is not None:builder.release()
        builder=tool=geometry=model=camera=None
        gc.collect()
    if times:row['solve_prepare_us']=times
    row['cycle_free_bytes']=cycle_free
    row['sampled_live_gc_bytes']=max(0,peak-baseline)
    row['heap_free_after']=gc.mem_free()
    row['slow_frame']=any(p['frame_max_us']>200000 for p in row['pages'])
    yield row


class Benchmark:
    def __init__(self,vm):
        self.vm=vm;self.full=True;self.mode=0;self.phase='intro';self.help=False;self.help_first=0
        self.queue=[];self.index=0;self.job=None;self.work=0;self.total_work=0;self.blocked=set()
        self.last=[];self.error='';self.saved=False;self.start_mode=vm.draw.mode
        self.measure=MeterDraw(vm.draw);self.quiet=QuietVM(vm,self.measure)
        self.title='';self.current_phase='';self.counts={};self.legacy=None;self.family=None

    def log(self,row,truncate=False):
        if not self.vm.storage.write(RESULT_PATH,json.dumps(row)+'\n','w' if truncate else 'a'):
            self.error='Cannot save SD checkpoint; stopped.'
            raise OSError(self.error)
        self.saved=True

    def restore(self):
        if self.vm.draw.mode!=self.start_mode:
            gc.collect();self.vm.draw.set_mode(self.start_mode)

    def close_job(self):
        job,self.job=self.job,None
        if job is not None:job.close()
        gc.collect()

    def begin(self):
        modes=('PSRAM','SRAM') if self.mode==0 else (MODES[self.mode],)
        self.queue=[(mode,case) for mode in modes for case in models.cases(self.full)]
        self.index=0;self.blocked=set();self.last=[];self.counts={};self.total_work=0
        import machine
        self.log(dict(clock_hz=machine.freq(),benchmark='EngTool render benchmark',version=FIRMWARE_VERSION,
                      status='started',machine=sys.implementation._machine,
                      profile='Full' if self.full else 'Quick',modes=modes,
                      reserve_bytes=RESERVE,work_limit_us=WORK_LIMIT_US,
                      memory='GC heap; sampled after yields, not a true transient/native peak',
                      timings='microseconds; compose excludes swap; first frame can be cold; normal GC enabled',
                      cad_build='build_wall_us includes cooperative loop and GC; active build steps also reported',
                      limits='Beam synthetic rows exceed editor caps; CAD retains its 8-step limit'),True)
        self.phase='run'

    def finish_case(self,row):
        row.update(case=self.index+1,label=self.title,work_us=self.work)
        self.total_work+=self.work
        mode,case=self.queue[self.index]
        family='beam' if case[0] in ('beam','frame') else 'cad'
        row.setdefault('kind',case[0]);row.setdefault('count',case[1]);row.setdefault('screen',mode)
        if row['status'] in ('memory','reserve','timeout','error'):
            self.blocked.add((mode,family))
        self.log(row)
        status=row['status'];self.counts[status]=self.counts.get(status,0)+1
        timing=max([0]+[p['frame_median_us'] for p in row.get('pages',())])
        self.last.append(self.title+': '+status+(' %.1fms'%(timing/1000) if timing else ''))
        self.last=self.last[-7:]
        self.close_job();self.index+=1

    def step(self):
        if self.index>=len(self.queue):
            self.restore();self.log(dict(status='complete',cases=self.index,counts=self.counts,active_work_us=self.total_work))
            self.current_phase='%d OK / %d expected refusals'%(self.counts.get('ok',0),self.counts.get('expected refusal',0))
            self.phase='done';self.draw();return
        mode,case=self.queue[self.index]
        family='beam' if case[0] in ('beam','frame') else 'cad'
        if self.job is None:
            self.work=0;self.title='%s %s %d %s%d'%(mode,case[0],case[1],'cases' if family=='beam' else 'q',case[2])
            self.log(dict(status='START',case=self.index+1,label=self.title))
            if (mode,family) in self.blocked and case[0] not in ('limit','invalid','unsupported'):
                self.finish_case(dict(status='skipped after failure'));self.draw();return
            gc.collect()
            target=self.vm.draw.MODE_SRAM if mode=='SRAM' else self.vm.draw.MODE_PSRAM
            if self.vm.draw.mode!=target:self.vm.draw.set_mode(target)
            if self.vm.draw.mode!=target:
                self.finish_case(dict(status='reserve',error='Requested screen mode unavailable'));self.draw();return
            if self.family!=family:
                # Only one engine's SD code is kept, matching a normal launch.
                # The benchmark package and any kept model dictionaries remain.
                for prefix in ('engtools.beamlab','engtools.picocad'):
                    for name in list(sys.modules):
                        if name==prefix or name.startswith(prefix+'.'):
                            module=sys.modules.pop(name)
                            parent,child=name.rsplit('.',1)
                            package=sys.modules.get(parent)
                            if package is not None and getattr(package,child,None) is module:
                                delattr(package,child)
                self.family=family;gc.collect()
            self.job=_case_job(self.quiet,case,self.measure)
            self.current_phase='starting';self.draw();return
        if self.work>WORK_LIMIT_US:
            self.close_job();self.finish_case(dict(status='timeout',error='30 seconds of measured work exceeded'));self.draw();return
        start=ticks_us()
        try:event=next(self.job)
        except StopIteration:raise RuntimeError('Case ended without a result')
        finally:self.work+=ticks_diff(ticks_us(),start)
        if isinstance(event,dict):
            self.finish_case(event);self.draw()
        elif isinstance(event,str):
            self.current_phase=event
            self.log(dict(status='phase',case=self.index+1,phase=event))
            self.draw()

    def run(self,button):
        if self.legacy is not None:self.legacy.run(self.vm);return
        if button==k.BUTTON_F9:
            self.help=not self.help;self.draw();return
        if self.help:
            if button==k.BUTTON_ESCAPE:self.help=False
            elif button==k.BUTTON_UP:self.help_first=max(0,self.help_first-1)
            elif button==k.BUTTON_DOWN:self.help_first=min(len(HELP)-10,self.help_first+1)
            self.draw();return
        if button==k.BUTTON_ESCAPE:
            self.close_job()
            try:
                if self.phase=='run':self.log(dict(status='cancelled',finished=self.index))
            except OSError:pass
            self.restore();self.phase='cancelled';self.vm.back();return
        try:
            if self.phase=='intro':
                if button==k.BUTTON_F2:self.full=not self.full
                elif button==k.BUTTON_F3:self.mode=(self.mode+1)%len(MODES)
                elif button==k.BUTTON_F4:
                    from . import display
                    self.legacy=display;display.start(self.vm);return
                elif button in (k.BUTTON_CENTER,k.BUTTON_ENTER):self.begin()
                if button!=k.BUTTON_NONE:self.draw()
            elif self.phase=='run':
                if button==k.BUTTON_F5:
                    self.close_job();self.finish_case(dict(status='user skipped'));self.draw()
                else:self.step()
        except OSError as exc:
            self.close_job();self.restore();self.error=str(exc);self.phase='stopped';self.draw()
        except Exception as exc:
            self.close_job()
            if self.phase=='run' and self.index<len(self.queue):
                self.finish_case(dict(status='memory' if isinstance(exc,MemoryError) else 'error',error=str(exc)[:160]));self.draw()
            else:raise

    def draw(self):
        d=self.vm.draw;p=theme.system_palette(self.vm)
        d.fill_screen(p.BG)
        theme.header(d,'Misc / EngTool render benchmark',palette=p,height=18)
        def text(y,s,color=None):d._text(9,y,s[:50],p.TEXT if color is None else color,0)
        if self.help:
            for i,s in enumerate(HELP[self.help_first:self.help_first+24]):text(30+i*11,s)
            text(307,'UP/DOWN scroll   F9 / ESC close',p.ACCENT)
        elif self.phase=='intro':
            for y,s in ((34,'BEAM + PICOCAD'),(56,'Build / solve, draw and panel transfer'),
                        (75,'F2 Profile: '+('Full stress' if self.full else 'Quick')),
                        (94,'F3 Screen: '+MODES[self.mode]),(122,'Uses disposable synthetic models.'),
                        (140,'Full stress can take several minutes.'),
                        (158,'Checkpoints saved before every case.'),
                        (176,'Expected refusals are reported separately.'),
                        (205,'F4 Display / CPU baseline benchmark'),
                        (245,'ENTER Start   F9 Help   ESC Return')):text(y,s)
        else:
            text(31,self.phase.upper(),p.ACCENT)
            text(51,'Case %d / %d'%(min(self.index+1,len(self.queue)),len(self.queue)))
            text(71,self.title)
            text(91,self.current_phase,p.MUTED)
            for i,s in enumerate(self.last):text(122+i*18,s)
            if self.error:text(263,self.error,p.ERROR)
            text(282,'Report: picoware/engtool-render-benchmark.txt',p.MUTED)
            text(307,'F5 Skip   F9 Help   ESC Return',p.ACCENT)
        d.swap()


_app=None
def start(vm):
    global _app
    _app=Benchmark(vm);_app.draw();return True
def run(vm):
    if _app is not None:_app.run(vm.button)
def stop(vm):
    global _app
    if _app is not None:
        if _app.legacy is not None:_app.legacy.stop(vm)
        _app.close_job();_app.restore()
    _app=None
