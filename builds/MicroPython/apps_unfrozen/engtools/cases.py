"""Versioned JSON case storage and streamed CSV export.

A case is a dict of reproducible inputs in SI units. Saving adds `version`
and `tool`; every write is read back before it is reported as done.
"""

CASE_VERSION = 1
CASE_DIRECTORY = "picoware/engineering/cases"
EXPORT_DIRECTORY = "picoware/engineering/exports"
CASE_LIMIT = 32768
NAME_LIMIT = 24


def clean_name(name):
    """A file-safe case name: letters, digits, - and _ only."""
    name = ''.join(c for c in name.strip().replace(' ', '-') if c.isalpha() or c.isdigit() or c in '-_')
    if not name:
        raise ValueError('Name needs letters or digits')
    return name[:NAME_LIMIT]


def _folder(storage, directory):
    if not storage.active:
        raise RuntimeError('SD card unavailable')
    path = ''
    for part in directory.split('/'):
        path = path + '/' + part if path else part
        if not storage.exists(path) and not storage.mkdir(path):
            raise RuntimeError('Could not create ' + path)


def case_path(case_id):
    return CASE_DIRECTORY + '/' + clean_name(case_id) + '.json'


def exists(storage, case_id):
    return storage.active and storage.exists(case_path(case_id))


def save_case(storage, case_id, case):
    """Save reproducible inputs, units and settings; verify the write."""
    from json import dumps
    _folder(storage, CASE_DIRECTORY)
    record = dict(case)
    record['version'] = CASE_VERSION
    data = dumps(record)
    if len(data) > CASE_LIMIT:
        raise ValueError('Case too large to save')
    path = case_path(case_id)
    if not storage.write(path, data) or storage.read(path) != data:
        storage.remove(path)
        raise RuntimeError('Save failed verification')
    return path


def load_case(storage, case_id, tool):
    """Load and validate a versioned saved case."""
    from json import loads
    path = case_path(case_id)
    if not storage.active:
        raise RuntimeError('SD card unavailable')
    if not storage.exists(path):
        raise ValueError('No saved case ' + case_id)
    if storage.size(path) > CASE_LIMIT:
        raise ValueError('Case file too large')
    try:
        case = loads(storage.read(path))
    except ValueError:
        raise ValueError('Case file is damaged')
    if not isinstance(case, dict) or case.get('tool') != tool:
        raise ValueError('Not a ' + tool + ' case')
    if case.get('version') != CASE_VERSION:
        raise ValueError('Unsupported case version')
    return case


def list_cases(storage, tool=None):
    """Saved case names, sorted. `tool` is checked when the case is loaded."""
    if not storage.active or not storage.exists(CASE_DIRECTORY):
        return []
    return sorted(name[:-5] for name in storage.listdir(CASE_DIRECTORY)
                  if name.endswith('.json') and '/' not in name)


def free_path(storage, directory, stem, extension):
    """The first unused numbered path such as exports/beam-001.csv."""
    _folder(storage, directory)
    for index in range(1, 1000):
        path = '%s/%s-%03d.%s' % (directory, stem, index, extension)
        if not storage.exists(path):
            return path
    raise RuntimeError('Folder full; remove old files')


def export_csv(storage, path, columns, rows):
    """Stream tabular results to a CSV file, a few rows per write."""
    directory = path.rsplit('/', 1)[0]
    _folder(storage, directory)
    written = len(','.join(columns)) + 1
    if not storage.write(path, ','.join(columns) + '\n'):
        raise RuntimeError('CSV write failed')
    chunk = []
    for row in rows:
        chunk.append(','.join('%.7g' % value for value in row))
        if len(chunk) == 32:
            text = '\n'.join(chunk) + '\n'
            written += len(text)
            if not storage.write(path, text, 'a'):
                storage.remove(path)
                raise RuntimeError('CSV write failed')
            chunk = []
    if chunk:
        text = '\n'.join(chunk) + '\n'
        written += len(text)
        if not storage.write(path, text, 'a'):
            storage.remove(path)
            raise RuntimeError('CSV write failed')
    if storage.size(path) != written:
        storage.remove(path)
        raise RuntimeError('CSV write failed verification')
    return path
