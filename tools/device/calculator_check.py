"""Optional REPL runner; the same check is under PicoLAB > Checks."""
import sys
from picoware.system.storage import Storage
storage=Storage()
if not storage.active:raise OSError('SD card unavailable')
if not storage.vfs_mounted and not storage.mount_vfs():raise OSError('Cannot mount SD')
apps=storage.vfs_prefix+'/picoware/apps'
if apps not in sys.path:sys.path.insert(0,apps)
from engtools.bench.calculator import run_report
run_report(storage.vfs_prefix+'/picoware/calculator-check.txt')
