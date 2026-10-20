#!/usr/bin/env python3
"""Compare two benchmark reports line by line.

    python3 tools/compare-benchmark.py baseline.txt candidate.txt [--all]

Works on any report made of "label: value unit" lines (core-benchmark.txt,
benchmark.txt). Each numeric line shows both values and the change; a change
of at least 5% is marked better or worse. Times, sizes in use and counts are
better lower; throughput (KB/s) and free memory are better higher. Without
--all, only lines that changed by at least 5%, or that differ in text, are shown.
"""
import re
import sys

NUMBER = re.compile(r'^(-?\d+(?:\.\d+)?)(?:\s+(.*))?$')
THRESHOLD = 5.0


def parse(path):
    """{label: (number or None, text)} in file order."""
    results = {}
    with open(path, encoding='utf-8') as handle:
        for line in handle:
            label, sep, rest = line.rstrip('\n').partition(': ')
            if not sep or label == 'Status':
                continue
            match = NUMBER.match(rest.strip())
            results[label] = (float(match.group(1)), match.group(2) or '') if match else (None, rest.strip())
    return results


def higher_is_better(label, unit):
    return unit.startswith('KB/s') or 'free' in label.lower() or label.startswith('Heap total')


def main(argv):
    show_all = '--all' in argv
    paths = [arg for arg in argv if arg != '--all']
    if len(paths) != 2:
        print(__doc__.strip())
        return 2
    a, b = parse(paths[0]), parse(paths[1])
    rows = []
    better = worse = 0
    for label in list(a) + [label for label in b if label not in a]:
        if label not in a or label not in b:
            rows.append((label, a.get(label, (None, '-'))[1] if label in a else '-',
                         b[label][1] if label in b else '-', 'only in one report'))
            continue
        (va, ua), (vb, ub) = a[label], b[label]
        if va is None or vb is None:
            if show_all or ua != ub:
                rows.append((label, ua, ub, '' if ua == ub else 'differs'))
            continue
        unit = ua.split(' (')[0]
        change = (vb - va) / abs(va) * 100 if va else (0.0 if vb == va else float('inf'))
        verdict = ''
        if abs(change) >= THRESHOLD:
            good = (change > 0) == higher_is_better(label, unit)
            verdict = 'better' if good else 'worse'
            better += good
            worse += not good
        if show_all or verdict:
            rows.append((label, '%g %s' % (va, unit), '%g %s' % (vb, unit),
                         '%+.1f%% %s' % (change, verdict) if va else verdict))
    width = max([len(row[0]) for row in rows] + [5])
    print('%-*s  %16s  %16s  %s' % (width, 'Label', 'A', 'B', 'Change'))
    for label, va, vb, note in rows:
        print('%-*s  %16s  %16s  %s' % (width, label, va[:16], vb[:16], note))
    print('\n%d better, %d worse (threshold %g%%)' % (better, worse, THRESHOLD))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
