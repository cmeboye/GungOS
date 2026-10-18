"""Mode-specific high scores on internal flash, independent of the SD card."""
import json
import os

MODES = ('Modern', 'Classic')


def flash_path():
    from sys import platform
    if platform == 'rp2':
        return '/tetris_scores.json'
    import sim_runtime
    return sim_runtime.flash_path('tetris_scores.json')


def load(path):
    try:
        with open(path, 'r') as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            data = {}
    except (OSError, ValueError):
        data = {}
    # Reject booleans, fractional values and negative/corrupt records.
    return {mode: data[mode] if type(data.get(mode)) is int and data[mode] >= 0 else 0
            for mode in MODES}


class Scores:
    def __init__(self, path=None):
        try:
            self.path = path if path is not None else flash_path()
        except OSError:
            self.path = None
        self.values = load(self.path) if self.path else dict.fromkeys(MODES, 0)
        self.saved = self.values.copy()

    def record(self, mode, score):
        if mode in MODES:
            self.values[mode] = max(self.values[mode], score)

    def save(self):
        if self.values == self.saved:
            return True
        if self.path is None:
            return False
        temporary = self.path + '.tmp'
        try:
            # Keep records written by another game instance, too.
            disk = load(self.path)
            for mode in MODES:
                self.values[mode] = max(self.values[mode], disk[mode])
            with open(temporary, 'w') as handle:
                json.dump(self.values, handle)
            with open(temporary, 'r') as handle:
                if json.load(handle) != self.values:
                    raise ValueError('Invalid score write')
            # Never remove the previous file before the replacement is ready.
            os.rename(temporary, self.path)
        except (OSError, ValueError):
            try:
                os.remove(temporary)
            except OSError:
                pass
            return False
        self.saved = self.values.copy()
        return True
