#!/usr/bin/env python3
"""Run the source checks used locally and by GitHub Actions; no device required."""
import argparse
import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
LOGS = ROOT / '.build/source-checks'
NATIVE = ROOT / 'builds/MicroPython/desktop/micropython'
COMPILER = ROOT / '.build/mpy-cross/mpy-cross'
STAGING = ROOT / '.build/sd-app-staging'
# These scripts need generated fixture arguments; their host drivers run them.
FIXTURE_DRIVERS = {
    'test_calculator_functions.py': 'tools/tests/test_calculator_functions.py',
    'test_calculator_numerics.py': 'tools/tests/test_calculator_numerics.py',
    'test_calculator_scientific.py': 'tools/tests/test_calculator_scientific.py',
    'test_jpeg_images.py': 'tools/tests/test_jpeg.py',
    'test_jpeg_streaming.py': 'tools/tests/test_jpeg.py',
    'test_reader_buffer.py': 'tools/tests/test_reader_buffer.py',
    'test_reader_images.py': 'tools/tests/test_reader_images.py',
    'test_reader_inline.py': 'tools/tests/test_reader_math.py',
    'test_reader_math.py': 'tools/tests/test_reader_math.py',
    'test_reader_navigation.py': 'tools/tests/test_reader_navigation.py',
    'test_reader_ui.py': 'simulator/test_reader.py',
}


def selected_profile():
    module = ast.parse((ROOT / 'simulator/run.py').read_text())
    function = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == '_run_selected_profile_check')
    return set(ast.literal_eval(next(n.value for n in function.body if isinstance(n, ast.Assign)
                                    and any(isinstance(t, ast.Name) and t.id == 'tests' for t in n.targets))))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', action='store_true', help='build the compiler, simulator and helpers first')
    args = parser.parse_args()
    LOGS.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, MICROPYTHON_DIR=str(ROOT / 'vendor/micropython'),
               PICOWARE_DESKTOP_SOURCE_ALIAS=str(ROOT / '.build/desktop-source'),
               MPY_CROSS=str(COMPILER), SDL_AUDIODRIVER='dummy')
    rows = []

    def run(label, command):
        path = LOGS / (label.replace('/', '_') + '.log')
        start = time.monotonic()
        with path.open('wb') as output:
            result = subprocess.run([str(v) for v in command], cwd=ROOT, env=env,
                                    stdout=output, stderr=subprocess.STDOUT)
        rows.append(dict(check=label, exit_code=result.returncode, seconds=round(time.monotonic() - start, 2)))
        (LOGS / 'summary.json').write_text(json.dumps(rows, indent=2) + '\n')
        print(('PASS' if result.returncode == 0 else 'FAIL') + ': ' + label, flush=True)
        if result.returncode:
            print('\n'.join(path.read_text(errors='replace').splitlines()[-35:]))
            raise SystemExit(result.returncode)

    run('public-source', [sys.executable, 'tools/check-public-repo.py'])
    run('public-check-tests', [sys.executable, 'tools/tests/test_public_repo.py'])
    run('build-input-tests', [sys.executable, 'tools/tests/test_build_inputs.py'])
    if args.build:
        run('mpy-cross-build', ['make', '-C', 'vendor/micropython/mpy-cross', '-j4', 'BUILD=' + str(COMPILER.parent)])
        run('simulator-build', ['sh', 'tools/micropython-desktop.sh'])
        run('simulator-helpers', ['sh', 'simulator/build.sh'])
    if not NATIVE.is_file() or not COMPILER.is_file():
        parser.error('Matching simulator/compiler missing. Run this command with --build.')
    run('app-compilation', [sys.executable, 'tools/compile-engineering-apps.py', '--mpy-cross', COMPILER, '--snapshot', STAGING])
    run('packed-artwork', [sys.executable, 'tools/convert-dashboard-assets.py', '--check'])
    for component in ('gfx', 'picosolve', 'sd'):
        run('native-' + component, ['sh', 'src/MicroPython/' + component + '/tests/run-tests.sh'])
    run('device-syntax', ['sh', 'tools/check-device-syntax.sh'])
    run('simulator-self-check', [NATIVE, '-X', 'heapsize=16M', 'simulator/run.py', '--sim-check', '--board',
                                'picocalc-pico2w', '--network', 'offline', '--audio', 'silent'])
    host_drivers = {'simulator/test_reader.py', 'simulator/test_reader_memory.py'}
    for script in sorted((ROOT / 'tools/tests').glob('test_*.py')):
        if script.name in ('test_public_repo.py', 'test_build_inputs.py'):
            continue
        path = script.relative_to(ROOT).as_posix()
        host_drivers.add(path)
        command = [sys.executable, path]
        if script.name == 'test_reader_navigation.py':
            command.append(STAGING)
        run(path, command)
    for path in ('simulator/test_reader.py', 'simulator/test_reader_memory.py'):
        run(path, [sys.executable, path])
    assert set(FIXTURE_DRIVERS.values()) <= host_drivers, 'A required fixture driver was not run'
    covered = selected_profile() | set(FIXTURE_DRIVERS) | {'test_reader.py', 'test_reader_memory.py'}
    for script in sorted((ROOT / 'simulator').glob('test_*.py')):
        if script.name not in covered:
            run('simulator/' + script.name, [NATIVE, '-X', 'heapsize=16M', script.relative_to(ROOT)])
    print('PASS: complete source checks; logs in .build/source-checks/', flush=True)


if __name__ == '__main__':
    main()
