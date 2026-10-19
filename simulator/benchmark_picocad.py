"""Measure direct PicoCAD construction time, heap and display segment count.

Run with the desktop MicroPython binary, not CPython. Times exclude drawing,
fit, file I/O and imports. Peak is a lower-bound observation at builder yields
(after GC), not a native allocator watermark. Desktop heap bytes are not Pico
heap bytes. No SD model, settings or firmware are changed.
"""
import os,sys,gc,json
from time import ticks_us,ticks_diff
root=os.getcwd()
for path in ('src/MicroPython','simulator/hardware','builds/MicroPython/apps_unfrozen'):
    sys.path.insert(0,root+'/'+path)
import sim_runtime
sim_runtime.configure(root,'/private/tmp/gungos-picocad-benchmark',root+'/builds/MicroPython/apps_unfrozen',1,'picocalc-pico2w',0,True,False,False,False,'',_network_mode='offline',_audio_mode='silent',_sd_profile='clean')
from engtools.picocad import model as dm
from engtools.picocad.geometry import Build
from engtools.picocad.draw import Camera


def run(factory,model):
    b=factory(model)
    for _ in b.job():pass
    return b


def timing(factory,model,repeats):
    values=[]
    for _ in range(repeats):
        gc.collect();start=ticks_us();b=run(factory,model)
        elapsed=ticks_diff(ticks_us(),start)
        b.release();b=None;values.append(elapsed)
    values.sort()
    return dict(median_us=values[len(values)//2],min_us=values[0],max_us=values[-1],runs=repeats)


def memory(factory,model):
    gc.collect();baseline=gc.mem_alloc();peak=baseline
    b=factory(model);job=b.job()
    gc.collect();peak=max(peak,gc.mem_alloc())
    for _ in job:
        gc.collect();peak=max(peak,gc.mem_alloc())
    job=None;gc.collect();peak=max(peak,gc.mem_alloc())
    lines=len(b.geometry.lines)//6;circles=len(b.geometry.circles)//10
    surfaces=len(b.geometry.surfaces)//23
    payload=(len(b.geometry.lines)+len(b.geometry.circles)+len(b.geometry.surfaces)+len(b.geometry.arcs)+len(b.geometry.spans))*4
    build_live=gc.mem_alloc()-baseline
    # Match app installation: keep boundaries and a cloned model, then release
    # the completed builder and collect. There are no triangle/flag buffers.
    geometry,model_copy=b.geometry,dm.clone(model)
    b.release();b=None;gc.collect();wire=gc.mem_alloc()-baseline
    camera=Camera();camera.fit(dm.bounds(model),(12,64,296,135),geometry)
    segments=sum(1 for _ in geometry.projected(camera))
    return dict(observed_live_peak_bytes=peak-baseline,built_live_bytes=build_live,retained_wire_bytes=wire,
                geometry_payload_bytes=payload,lines=lines,circles=circles,surfaces=surfaces,draw_segments=segments)


# Warm the import path before timing; no legacy backend is loaded or bundled.
model=dm.example();b=run(Build,model);b.release();b=None;gc.collect()
results=[]
for n in dm.QUALITIES:
    model=dm.example();model['resolution']=n
    row=dict(resolution=n,curve_target_px=4.0/n)
    row.update(timing(Build,model,9));row.update(memory(Build,model));results.append(row)
report=dict(platform=sys.platform,implementation=str(sys.implementation),
            model='40x30x10 mm box; centered r5 mm through-bore, 16 mm cutter',
            method='Direct only; warm modules; normal GC timing; separate GC-at-yield live-heap samples; no drawing or fit in timed region',
            caveats='Host timings/heap sizes are not Pico measurements; observed live peak misses allocations wholly within a step; retained wire includes cloned model',
            results=results)
print(json.dumps(report))
