#!/usr/bin/env python3
"""Check maintained Python runtime sources for retired upstream service clients.

Comments/docstrings and upstream attribution remain allowed. This is a source
regression check, not a network firewall or an audit of user-supplied SD scripts.
"""
import ast
from pathlib import Path
import re
import runpy
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOTS = ('src/MicroPython/picoware', 'builds/MicroPython/apps_unfrozen',
                 'simulator/hardware')
REMOVED_MODULES = ('picoware.applications.applications.FlipSocial',
                   'picoware.applications.notifications',
                   'picoware.applications.applications.app_store',
                   'picoware.applications.system.update')
URL = re.compile(r'(?:https?|wss?)://[^\s\'"<>]+', re.I)


def check(root=ROOT):
    issues = []
    profile = runpy.run_path(str(root / 'src/MicroPython/picoware/system/features.py'))
    disabled = profile['DISABLED_MODULES']
    for name in REMOVED_MODULES:
        if name not in disabled:
            issues.append((name, 0, 'retired client is not excluded from firmware/simulator'))
        path = root / 'src/MicroPython' / (name.replace('.', '/') + '.py')
        if path.exists():
            issues.append((str(path.relative_to(root)), 0, 'retired service client still exists'))
    count = 0
    for folder in RUNTIME_ROOTS:
        for path in sorted((root / folder).rglob('*.py')):
            count += 1
            tree = ast.parse(path.read_text(), filename=str(path))
            docstrings = set()
            for node in ast.walk(tree):
                if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.body and isinstance(node.body[0], ast.Expr):
                        value = node.body[0].value
                        if isinstance(value, ast.Constant) and isinstance(value.value, str):
                            docstrings.add(id(value))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Constant) or not isinstance(node.value, str) or id(node) in docstrings:
                    continue
                literal = node.value.lower()
                # Catch a bare/assembled hostname as well as a complete URL.
                forbidden = 'jblanked.com' in literal
                for match in URL.finditer(literal):
                    url = urlsplit(match.group())
                    if url.hostname in ('github.com', 'www.github.com', 'raw.githubusercontent.com', 'api.github.com'):
                        parts = [part for part in url.path.split('/') if part]
                        forbidden |= bool(parts and parts[0] == 'jblanked') or (len(parts) > 1 and parts[:2] == ['repos', 'jblanked'])
                if forbidden:
                    issues.append((str(path.relative_to(root)), node.lineno, 'retired upstream service/download endpoint in executable source'))
    return count, issues


def main():
    count, issues = check()
    for path, line, reason in issues:
        print(str(path) + (':' + str(line) if line else '') + ': ' + reason)
    print(('FAIL' if issues else 'PASS') + ': service-independence check, ' + str(count) + ' Python runtime files')
    return bool(issues)


if __name__ == '__main__':
    sys.exit(main())
