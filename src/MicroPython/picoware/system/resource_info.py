"""Measured resource counters; unknown whole-chip usage is never inferred."""

_heap_total=None


def snapshot(vm):
    global _heap_total
    from gc import mem_free,mem_alloc
    from picoware.system.system import System
    from sys import platform
    system=System()
    # mem_free() and mem_alloc() each walk the whole heap (~4 ms on the device);
    # the total never changes, so one walk per snapshot gives both.
    free=mem_free()
    if _heap_total is None: _heap_total=free+mem_alloc()
    used=_heap_total-free
    rows=[('Heap',free,used,_heap_total)]
    try:
        from os import statvfs
        stat=statvfs('/')
        unit=stat[1] or stat[0]
        total=unit*stat[2]
        available=unit*stat[4]
        rows.append(('Flash',available,total-available,total))
    except Exception: rows.append(('Flash',None,None,None))
    try:
        storage=vm.storage
        if not storage.active: raise OSError('SD unavailable')
        total,available=int(storage.total_space),int(storage.free_space)
        if total<=0 or not 0<=available<=total: raise ValueError('Invalid SD counters')
        rows.append(('SD',available,total-available,total))
    except Exception: rows.append(('SD',None,None,None))
    try:
        total=system.total_psram
        available=system.free_psram
        rows.append(('PSRAM',available,total-available,total))
    except Exception: rows.append(('PSRAM',None,None,None))
    # Physical RP2350 SRAM includes the two scratch banks (SDK SRAM_END-SRAM_BASE).
    rows.append(('SRAM',None,None,520*1024))
    return {'board':system.board_name,'frequency':system.freq,'rows':rows,
            'simulator':platform in ('darwin','linux','win32')}


def compact(value):
    if value is None: return '-'
    if value<1024: return str(value)+'B'
    if value<1000*1024: return str(value//1024)+'K'
    if value<10*1024*1024: return '%.1fM' % (value/(1024*1024))
    if value<1000*1024*1024: return str(value//(1024*1024))+'M'
    if value<1000*1024*1024*1024: return str(value//(1024*1024*1024))+'G'
    return '%.1fT' % (value/(1024*1024*1024*1024))


def lines(info):
    result=['Board: '+info['board'],'Frequency: %d MHz' % info['frequency']]
    result.append('       Free Used  Tot  %F')
    for name,free,used,total in info['rows']:
        percent=str(int(100*free/total)) if free is not None and total else '-'
        result.append('%-5s %4s %4s %4s %3s' % (name,compact(free),compact(used),compact(total),percent))
    result.extend(('K/M/G are binary units','Flash = filesystem space',
                   'SRAM usage unavailable','Heap is part of SRAM'))
    if info['simulator']: result.append('Simulator: host counters')
    for name,free,used,total in info['rows']:
        result.append(name+' bytes:')
        for label,value in (('Free',free),('Used',used),('Total',total)):
            result.append(' '+label+': '+(str(value) if value is not None else 'unavailable'))
    return result
