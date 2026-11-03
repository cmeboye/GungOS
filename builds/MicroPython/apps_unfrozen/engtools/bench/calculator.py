"""Small on-device calculator check. UI and REPL share one report generator."""
import gc,sys,os,math
from time import ticks_us,ticks_diff

PATH='picoware/calculator-check.txt'
HEADER='GUNGOS CALCULATOR CHECK v2'
FIXED_CHECKS=28
HELP=('Calculator check:', 'ENTER / F6: run the fixed checks', 'ESC: cancel or return',
      'UP / DOWN: scroll the report', 'Saved text: picoware/calculator-check.txt',
      'Send the complete text, including its END line.',
      'Times exclude screen drawing and report saving.', 'Sampled heap use can miss short peaks.',
      'No settings, sessions or documents are changed.')
_active=None


def _distance(a,b):
    from engtools.calculator.scientific import hypot
    a,b=complex(a),complex(b)
    return hypot(a.real-b.real,a.imag-b.imag)


def _format(value):
    from engtools.calculator.evaluate import format_value
    if isinstance(value,list):return '['+', '.join(format_value(v) for v in value)+']'
    return format_value(value)


def report_job(screen='none'):
    """Yield report lines; timings include normal GC, not screen redraw/save."""
    from engtools.calculator import evaluate as ev
    from engtools.numerics.equations import polynomial_job
    from engtools.calculator.scientific import hypot
    yield HEADER
    from picoware.system.features import FIRMWARE_VERSION
    yield 'firmware='+FIRMWARE_VERSION
    yield 'runtime='+sys.version.replace('\n',' ')[:150]
    try:yield 'machine='+os.uname().machine
    except AttributeError:yield 'machine=unknown'
    try:
        import machine
        yield 'clock_hz='+str(machine.freq())
    except (ImportError,AttributeError):yield 'clock_hz=unknown'
    yield 'screen_mode='+screen
    yield 'native_formula='+str(ev.native_function(ev.Parser('x*x').parse()[1],{}) is not None)
    gc.collect();initial=gc.mem_free();yield 'heap_free_start='+str(initial)
    yield 'Times are compute us; heap_min_sampled is not a true allocation peak.'
    cases=(('arithmetic','(sin(30)^2+cos(30)^2)*ncr(20,3)',1140,'DEG',False),
           ('sum1024','sum(k,1,1024,k)',524800,'RAD',False),
           ('nested_sum','sum(k,1,24,sum(m,1,k,m))',2600,'RAD',False),
           ('complex_asin','asin(2)',complex(math.pi/2,math.acosh(2)),'RAD',True),
           ('tiny_complex_sqrt','sqrt(1e-30*i)',complex(math.sqrt(.5e-30),math.sqrt(.5e-30)),'RAD',True),
           ('integral_smooth','int(0,1,x^2)',1/3,'RAD',False),
           ('integral_peak','int(0,1,exp(-((x-0.12345)/0.0001)^2))',math.sqrt(math.pi)*.0001,'RAD',False),
           ('integral_split','int(0,1,exp(-((x-0.12345)/0.000001)^2),1e-9,2e-5,0.12345)',math.sqrt(math.pi)*.000001,'RAD',False),
           ('integral_zero','int(0,1,0)',0,'RAD',False),
           ('polar_roundtrip','rect(radius(3+4i),phase(3+4i))',complex(3,4),'DEG',True),
           ('gcd_lcm','lcm(12,18)+gcd(-48,18)',42,'RAD',False),
           ('inverse_hyperbolic','acosh(-2)',complex(math.acosh(2),math.pi),'DEG',True),
           ('stable_increment','log1p(1e-8)/expm1(1e-8)',1,'RAD',False),
           ('scaled_hypot','hypot(3e30,4e30)',5e30,'RAD',False),
           ('decimal_round','round(1.25,1)+sigfig(1.23456,4)',2.435,'RAD',False),
           ('special_functions','gamma(5)+lgamma(1)+erf(0)+erfc(0)',25,'RAD',False))
    passed=failed=0;sampled=initial
    for label,text,want,angle,cmode in cases:
        gc.collect();before=gc.mem_free();info=[];times=[];got=None;status='OK';detail=''
        try:
            for repeat in range(3):
                start=ticks_us();got=ev.calculate(text,{},angle,cmode,diagnostics=info)[0]
                times.append(ticks_diff(ticks_us(),start));sampled=min(sampled,gc.mem_free())
                yield None
            tolerance=0.002 if label=='integral_split' else 0.0005 if label=='integral_peak' else 0.00002
            if _distance(got,want)>tolerance*max(hypot(complex(want).real,complex(want).imag),1e-37):status='FAIL'
            if info:detail=' err~%.3g samples=%d'%(info[-1]['error'],info[-1]['evaluations'])
        except Exception as exc:status='FAIL';detail=' '+str(exc)
        gc.collect();after=gc.mem_free()
        if status=='OK':passed+=1
        else:failed+=1
        yield '%s %s value=%s median_us=%d retained_bytes=%d%s'%(status,label,_format(got) if got is not None else '-',sorted(times)[len(times)//2] if times else 0,before-after,detail)
    for label,c,want in (('poly_repeat4',[1,-4,6,-4,1],[1]*4),('poly_complex_repeat',[1,0,2,0,1],[-1j,-1j,1j,1j]),
                         ('poly_quartic',[1,0,-5,0,4],[-2,-1,1,2]),('poly_scaled',[1e-30,-6e-30,11e-30,-6e-30],[1,2,3]),
                         ('poly_wide',[1,1e20,1],[-1e20,-1e-20])):
        gc.collect();before=gc.mem_free();elapsed=0;record=None;status='OK';detail=''
        try:
            job=polynomial_job(c)
            while True:
                start=ticks_us()
                try:record=next(job)
                except StopIteration:elapsed+=ticks_diff(ticks_us(),start);break
                elapsed+=ticks_diff(ticks_us(),start)
                sampled=min(sampled,gc.mem_free())
                if 'progress' in record:yield None
            got=record['roots'];remaining=list(want)
            for z in got:
                i=min(range(len(remaining)),key=lambda i:_distance(z,remaining[i]));target=remaining.pop(i)
                if _distance(z,target)>1e-5*max(abs(target),1e-37):status='FAIL'
            detail=' warnings='+str(len(record.get('warnings',[])))
        except Exception as exc:status='FAIL';got=[];detail=' '+str(exc)
        gc.collect();after=gc.mem_free()
        if status=='OK':passed+=1
        else:failed+=1
        yield '%s %s roots=%s time_us=%d retained_bytes=%d%s'%(status,label,_format(got),elapsed,before-after,detail)
    try:
        from engtools.calculator.app import Calculator
        from engtools.calculator.workspaces import MatrixWorkspace
        from engtools.numerics.matrices import matrix
        calc=Calculator();calc.angle='RAD';workspace=MatrixWorkspace(calc)
        workspace.matrices['MatA']=matrix([[2,0],[0,3]])
        start=ticks_us();got=workspace.evaluate('sum(k,1,3,k*trace(MatA))');elapsed=ticks_diff(ticks_us(),start)
        status='OK' if abs(got-30)<0.0001 else 'FAIL'
        if status=='OK':passed+=1
        else:failed+=1
        yield '%s matrix_scoped_sum value=%s time_us=%d'%(status,_format(got),elapsed)
        start=ticks_us();got=workspace.evaluate('int(0,1,x*trace(MatA))');elapsed=ticks_diff(ticks_us(),start)
        status='OK' if abs(got-2.5)<0.0001 else 'FAIL'
        if status=='OK':passed+=1
        else:failed+=1
        yield '%s matrix_integral value=%s time_us=%d'%(status,_format(got),elapsed)
        workspace=None;calc=None;gc.collect()
    except Exception as exc:
        failed+=1;yield 'FAIL matrix_workflow '+str(exc)
    # Expected errors must leave assignment and Ans untouched.
    for text in ('a=tan(90)','a=int(0,1,exp(-((x-0.173234)/0.0000001)^2))','a=ncr(5,6)'):
        variables={'a':7,'Ans':11}
        try:ev.calculate(text,variables,'DEG');status='FAIL';message='accepted'
        except (ValueError,ZeroDivisionError) as exc:status='OK' if variables=={'a':7,'Ans':11} else 'FAIL';message=str(exc)
        if status=='OK':passed+=1
        else:failed+=1
        yield status+' expected_error '+text+' -> '+message
        yield None
    display=ev.format_value(math.ldexp(1.0,-149))
    if display=='1.401298e-45':passed+=1;status='OK'
    else:failed+=1;status='FAIL'
    yield status+' subnormal_display text='+display
    gc.collect();before=gc.mem_free();preloaded='engtools.calculator.catalogue' in sys.modules
    from engtools.calculator.catalogue import groups
    discovered=set(token.split('_',1)[0] for _,_,entries in groups() for token,_,_ in entries)
    status='OK' if set(ev.FUNCTIONS)<=discovered else 'FAIL'
    if status=='OK':passed+=1
    else:failed+=1
    discovered=None;gc.collect();sampled=min(sampled,gc.mem_free())
    yield '%s catalogue families=%d retained_bytes=%d preloaded=%s'%(status,len(groups()),before-gc.mem_free(),preloaded)
    # Repeated load/calculate/root cleanup, sampled after warm-up and collection.
    retained=[]
    for cycle in range(12):
        ev.calculate('sum(k,1,128,k^2)',{},'RAD')
        for record in polynomial_job([1,-4,6,-4,1]):pass
        record=None;gc.collect();retained.append(gc.mem_free());yield None
    drift=max(retained[3:])-min(retained[3:]);gc.collect()
    yield 'cleanup_drift_bytes='+str(drift)+' (last 9 of 12 cycles, after GC)'
    yield 'heap_min_sampled='+str(sampled)+' heap_free_end='+str(gc.mem_free())
    yield 'RESULT passed=%d failed=%d'%(passed,failed)
    yield 'END '+HEADER


def run_report(path=None):
    """REPL: from engtools.bench.calculator import run_report; run_report()."""
    lines=[]
    for line in report_job():
        if line is not None:print(line);lines.append(line)
    text='\n'.join(lines)+'\n'
    if path:
        with open(path,'w') as handle:handle.write(text)
    return text


class Check:
    HELP=HELP
    def __init__(self,vm):self.vm=vm;self.lines=[];self.job=None;self.selected=0;self.message='ENTER starts a short calculator check'
    def start(self,vm):
        self.vm=vm;vm.input_manager.reset();self.draw();return True
    def stop(self,vm):
        if self.job:self.job.close()
        self.job=None
    def draw(self):
        from engtools.ui import theme
        rows=[(line[:49],line[49:98]) for line in self.lines] or [('Calculator check','Timings, numeric results and heap samples')]
        theme.menu(self.vm.draw,rows,self.selected,'Calculator check','PicoLAB',self.message,vm=self.vm)
    def advance(self):
        if self.job is None:return
        try:
            line=next(self.job)
            if line is not None:self.lines.append(line);self.selected=max(0,len(self.lines)-1);self.draw()
        except StopIteration:
            self.job=None
            try:
                text='\n'.join(self.lines)+'\n'
                if not self.vm.storage.write(PATH,text):raise OSError('SD write failed')
                self.message='Saved: '+PATH
            except (OSError,MemoryError) as exc:self.message='Save failed: '+str(exc)
            self.draw()
        except Exception as exc:
            self.job=None;self.message='Check stopped: '+str(exc);self.draw()
    def run(self,vm=None):
        from picoware.system import buttons as k
        button=self.vm.button
        if self.job is not None:
            if button==self.vm.input_manager._key_esc:self.job.close();self.job=None;self.message='Cancelled';self.draw()
            else:self.advance()
        elif button==self.vm.input_manager._key_esc:self.vm.back()
        elif button in (k.BUTTON_CENTER,k.BUTTON_F6):self.lines=[];self.selected=0;self.job=report_job('SRAM' if self.vm.draw.mode else 'PSRAM');self.message='Running / ESC cancels';self.draw()
        elif button in (k.BUTTON_UP,k.BUTTON_DOWN):
            self.selected=max(0,min(len(self.lines)-1,self.selected+(-1 if button==k.BUTTON_UP else 1)));self.draw()


def start(vm):
    global _active
    _active=Check(vm);vm.input_manager.reset();_active.draw();return True

def run(vm):
    if _active:_active.run()

def stop(vm):
    global _active
    if _active and _active.job:_active.job.close()
    _active=None


def show(vm):
    from engtools.plots.view import open_view
    return open_view(vm,'calculator_check',Check(vm))
