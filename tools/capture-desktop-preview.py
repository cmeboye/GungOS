#!/usr/bin/env python3
"""Capture the current desktop/Lorenz framebuffer using an isolated simulator SD."""
import argparse
from pathlib import Path
import subprocess
import tempfile
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
CAPTURE = '''import os,sys
root=os.getcwd()
for path in ('src/MicroPython','simulator/hardware','builds/MicroPython/apps_unfrozen'):
    sys.path.insert(0,root+'/'+path)
import sim_runtime
folder=sys.argv[1]
sim_runtime.configure(root,folder+'/sd',root+'/builds/MicroPython/apps_unfrozen',1,
                      'picocalc-pico2w',0,True,False,False,False,'',
                      _network_mode='offline',_audio_mode='silent',_sd_profile='clean')
from picoware.system.view_manager import ViewManager
from picoware.system.settings import Settings
from picoware.applications import desktop
from picoware.system.buttons import BUTTON_NONE
import picoware_southbridge as power
class Clock:
    def datetime(self):return (2026,11,6,4,12,0,0,0)
    def deinit(self):pass
vm=ViewManager();vm._wifi=None
vm.time._rtc=Clock();vm.time._is_set=True
power.set_battery_percentage(85);power.set_battery_charging(False)
# These are normal Lorenz options; omit host timing statistics in a still image.
assert Settings(vm.storage).update({'screensaver':'Lorenz',
    'lorenz':{'detail':3,'points':1536,'fps':8,'stats':False}})
assert desktop.start(vm)
home=desktop._dashboard
home.widget.load('Lorenz');assert home.widget.module,home.widget.error
for _ in range(int(sys.argv[2])):
    home.widget.next_frame=0;home.widget.module._next=0
    vm._button=BUTTON_NONE;home.update()
assert home.widget.module._count==1536
home.status_bar.sample(force=True);home.draw()
assert sim_runtime.lcd_screenshot(folder+'/desktop.bmp')
desktop.stop(vm)
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--micropython', type=Path, default=ROOT / 'builds/MicroPython/desktop/micropython')
    parser.add_argument('--output', type=Path, default=ROOT / 'assets/screenshots/desktop.png')
    parser.add_argument('--frames', type=int, default=160)
    args = parser.parse_args()
    if args.frames < 96:
        parser.error('Use at least 96 frames to fill the configured Lorenz trail')
    with tempfile.TemporaryDirectory(prefix='gungos-desktop-preview-') as folder:
        subprocess.run([str(args.micropython.resolve()), '-X', 'heapsize=16M', '-c', CAPTURE,
                        folder, str(args.frames)], cwd=ROOT, check=True)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(Path(folder) / 'desktop.bmp') as capture:
            assert capture.size == (320, 320), 'Unexpected native display size'
            capture.save(args.output)
    print('Saved current desktop with Lorenz: ' + str(args.output))


if __name__ == '__main__':
    main()
