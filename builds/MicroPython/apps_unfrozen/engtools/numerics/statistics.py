"""Bounded frequency statistics and centred linear regression on native ulab."""
import math
from .backend import require

MAX_ROWS = 128
MAX_FREQUENCY = 9999


def real(value):
    if isinstance(value, complex) or isinstance(value, bool):
        raise ValueError('Use a finite real number')
    value = float(value)
    if math.isnan(value) or math.isinf(value): raise ValueError('Use a finite real number')
    return value


def optional(value):
    return None if math.isnan(value) or math.isinf(value) else value


class Dataset:
    def __init__(self, paired=False):
        self.np, _ = require()
        if not hasattr(self.np, 'sort'):
            raise RuntimeError('Statistics needs the ulab sorting build')
        self.paired, self.frequency = bool(paired), False
        self.x = self.np.zeros(MAX_ROWS)
        self.y = self.np.zeros(MAX_ROWS) if self.paired else None
        self.freq = self.np.ones(MAX_ROWS, dtype=self.np.uint16)
        self.mask = bytearray(MAX_ROWS)
        self.rows, self.revision, self._cache = 1, 0, None

    def changed(self):
        self.revision += 1
        self._cache = None

    def columns(self):
        return ['X']+(['Y'] if self.paired else [])+(['Freq'] if self.frequency else [])

    def set_frequency(self, enabled):
        if self.frequency != bool(enabled):
            self.frequency = bool(enabled)
            self.changed()

    def get(self, row, column):
        if not 0 <= row < self.rows: raise ValueError('Row out of range')
        if column == 'Freq': return int(self.freq[row])
        flag = 1 if column == 'X' else 2
        if column not in ('X', 'Y') or (column == 'Y' and not self.paired):
            raise ValueError('Column unavailable')
        if not self.mask[row] & flag: return None
        return float((self.x if column == 'X' else self.y)[row])

    def set(self, row, column, value):
        if not 0 <= row < self.rows: raise ValueError('Row out of range')
        value = real(value)
        if column == 'Freq':
            if value != int(value) or not 0 <= value <= MAX_FREQUENCY:
                raise ValueError('Frequency: integer 0..9999')
            self.freq[row] = int(value)
        else:
            if column not in ('X', 'Y') or (column == 'Y' and not self.paired):
                raise ValueError('Column unavailable')
            value = real(self.np.array([value])[0])
            (self.x if column == 'X' else self.y)[row] = value
            self.mask[row] |= 1 if column == 'X' else 2
        self.changed()

    def clear_cell(self, row, column):
        self.get(row, column)
        if column == 'Freq': self.freq[row] = 1
        else: self.mask[row] &= ~(1 if column == 'X' else 2)
        self.changed()

    def insert_row(self, index):
        if self.rows >= MAX_ROWS: raise ValueError('Dataset limit: 128 rows')
        if not 0 <= index <= self.rows: raise ValueError('Row out of range')
        for row in range(self.rows, index, -1):
            self.x[row], self.freq[row], self.mask[row] = self.x[row-1], self.freq[row-1], self.mask[row-1]
            if self.paired: self.y[row] = self.y[row-1]
        self.x[index], self.freq[index], self.mask[index] = 0, 1, 0
        if self.paired: self.y[index] = 0
        self.rows += 1
        self.changed()

    def delete_row(self, index):
        if not 0 <= index < self.rows: raise ValueError('Row out of range')
        original_rows = self.rows
        for row in range(index, original_rows-1):
            self.x[row], self.freq[row], self.mask[row] = self.x[row+1], self.freq[row+1], self.mask[row+1]
            if self.paired: self.y[row] = self.y[row+1]
        self.rows = max(1, original_rows-1)
        last = original_rows-1
        self.x[last], self.freq[last], self.mask[last] = 0, 1, 0
        if self.paired: self.y[last] = 0
        self.changed()

    def clear(self):
        self.mask[:] = bytes(MAX_ROWS)
        self.freq[:] = 1
        self.rows = 1
        self.changed()

    def observation_count(self):
        required = 3 if self.paired else 1
        return sum((int(self.freq[i]) if self.frequency else 1) for i in range(self.rows)
                   if self.mask[i] == required)

    def _collect(self):
        xs, ys, weights = [], [], []
        for row in range(self.rows):
            weight = int(self.freq[row]) if self.frequency else 1
            if not self.mask[row] or weight == 0: continue
            if self.mask[row] != (3 if self.paired else 1):
                raise ValueError('Complete row %d: X and Y required' % (row+1))
            xs.append(float(self.x[row])); weights.append(weight)
            if self.paired: ys.append(float(self.y[row]))
        if not xs: raise ValueError('Enter at least one observation')
        return self.np.array(xs), self.np.array(ys) if ys else None, self.np.array(weights), sum(weights), weights

    def _column(self, values, w, n, weights):
        np = self.np
        anchor = float(values[0])
        relative = values-anchor
        mean_relative = float(np.dot(w, relative))/n
        centred = relative-mean_relative
        if not bool(np.all(np.isfinite(centred))): raise ValueError('Data range is too large; scale the values')
        scale = max(abs(float(np.min(centred))),abs(float(np.max(centred))))
        normalized = centred/scale if scale else centred
        m2 = float(np.dot(w, normalized*normalized))
        population_sd = scale*math.sqrt(m2/n)
        sample_sd = scale*math.sqrt(m2/(n-1)) if n > 1 else None
        # Weighted Type-7 quantiles without expanding repeated observations.
        frequencies = {}
        for index, value in enumerate(values):
            frequencies[value] = frequencies.get(value, 0)+weights[index]
        ordered, cumulative, running = [], [], 0
        for value in np.sort(values):
            weight = frequencies.pop(value, 0)
            if weight:
                ordered.append(value); running += weight; cumulative.append(running)
        def rank(index):
            for i, limit in enumerate(cumulative):
                if index < limit: return ordered[i]
            return ordered[-1]
        def quantile(p):
            position = (n-1)*p
            low = int(position)
            fraction = position-low
            return rank(low)*(1-fraction)+rank(min(n-1, low+1))*fraction
        q1, median, q3 = quantile(.25), quantile(.5), quantile(.75)
        result = {'n':n, 'sum':optional(float(np.dot(w, values))),
                  'sum2':optional(float(np.dot(w, values*values))),
                  'mean':optional(anchor+mean_relative), 'median':median,
                  'min':ordered[0], 'max':ordered[-1], 'range':optional(ordered[-1]-ordered[0]),
                  'q1':q1, 'q3':q3, 'iqr':optional(q3-q1),
                  'pstd':optional(population_sd), 'pvar':optional(population_sd*population_sd),
                  'std':optional(sample_sd) if sample_sd is not None else None,
                  'var':optional(sample_sd*sample_sd) if sample_sd is not None else None}
        return result, centred, anchor, mean_relative, scale

    def summary(self):
        if self._cache is None:
            x, y, w, n, weights = self._collect()
            xc = self._column(x, w, n, weights)
            yc = self._column(y, w, n, weights) if y is not None else None
            self._cache = {'summary':{'n':n, 'X':xc[0], 'Y':yc[0] if yc else None},
                           'x':xc, 'y':yc, 'w':w, 'fit':None}
        return self._cache['summary']

    def fit(self):
        if not self.paired: raise ValueError('Linear fit needs a 2-variable dataset')
        summary = self.summary()
        if self._cache['fit'] is not None: return self._cache['fit']
        n, xc, yc, w, np = summary['n'], self._cache['x'], self._cache['y'], self._cache['w'], self.np
        if n < 2 or xc[4] == 0: raise ValueError('Fit needs at least two distinct X values')
        dx = xc[1]/xc[4]
        dy = yc[1]/yc[4] if yc[4] else yc[1]
        sxx, sxy, syy = float(np.dot(w,dx*dx)), float(np.dot(w,dx*dy)), float(np.dot(w,dy*dy))
        beta = sxy/sxx
        slope = beta*(yc[4]/xc[4])
        intercept = summary['Y']['mean']-slope*summary['X']['mean']
        if optional(slope) is None or optional(intercept) is None:
            raise ValueError('Fit coefficients out of range; scale the data')
        residual = dy-beta*dx
        rss = max(0, float(np.dot(w,residual*residual)))
        r = max(-1,min(1,sxy/math.sqrt(sxx*syy))) if syy else None
        r2 = max(0,min(1,1-rss/syy)) if syy else None
        residual_sd = yc[4]*math.sqrt(rss/(n-2)) if n > 2 else None
        fit = {'slope':slope, 'intercept':intercept, 'corr':r, 'r2':r2,
               'cov':optional(((sxy/(n-1))*xc[4])*yc[4]),
               'pcov':optional(((sxy/n)*xc[4])*yc[4]),
               'sse':optional((rss*yc[4])*yc[4]),
               'residual_sd':optional(residual_sd) if residual_sd is not None else None}
        self._cache['fit'] = fit
        return fit

    def pair_statistics(self):
        if not self.paired: raise ValueError('Paired statistics need X and Y')
        n = self.summary()['n']
        xc, yc, w, np = self._cache['x'], self._cache['y'], self._cache['w'], self.np
        if 'pairs' not in self._cache:
            dx = xc[1]/xc[4] if xc[4] else xc[1]
            dy = yc[1]/yc[4] if yc[4] else yc[1]
            sxy = float(np.dot(w,dx*dy))
            sxx, syy = float(np.dot(w,dx*dx)), float(np.dot(w,dy*dy))
            self._cache['pairs'] = {
                'cov':optional(((sxy/(n-1))*xc[4])*yc[4]) if n > 1 else None,
                'pcov':optional(((sxy/n)*xc[4])*yc[4]),
                'corr':max(-1,min(1,sxy/math.sqrt(sxx*syy))) if sxx and syy else None}
        return self._cache['pairs']

    def predict(self, value):
        value = real(value)
        fit = self.fit()
        xc, yc = self._cache['x'], self._cache['y']
        predicted = yc[2]+(yc[3]+fit['slope']*((value-xc[2])-xc[3]))
        return real(predicted)

    def statistic(self, name, column):
        if column not in ('X','Y') or (column == 'Y' and not self.paired):
            raise ValueError('Column unavailable: '+column)
        values = self.summary()[column]
        value = values[name]
        if value is None:
            if name in ('std','var') and values['n'] < 2:
                raise ValueError('Sample statistics need at least two observations')
            raise ValueError('Statistic out of range; scale the data')
        return value

    def observations(self, column):
        """Validated observations, with frequency as repetition, streamed."""
        if column not in ('X','Y') or (column == 'Y' and not self.paired):
            raise ValueError('Column unavailable: '+column)
        xs, ys, _, _, weights = self._collect()
        values = xs if column == 'X' else ys
        for row, value in enumerate(values):
            for _ in range(weights[row]):
                yield value

    def to_csv(self):
        lines = ['# Picoware statistics v1; frequency=%d' % self.frequency,
                 'X,Y,Freq' if self.paired else 'X,Freq']
        last = self.rows-1
        while last > 0 and not self.mask[last]: last -= 1
        for row in range(last+1):
            values = [self.get(row,'X')]+([self.get(row,'Y')] if self.paired else [])
            lines.append(','.join('' if value is None else '%.9g' % value for value in values)+','+str(int(self.freq[row])))
        return '\n'.join(lines)+'\n'

    @classmethod
    def from_csv(cls, text):
        if not isinstance(text,str) or len(text) > 32768: raise ValueError('CSV limit: 32 KiB')
        lines = text.splitlines()
        frequency = None
        if lines and lines[0].startswith('# Picoware statistics v1; frequency='):
            flag = lines.pop(0).split('=')[-1]
            if flag not in ('0','1'): raise ValueError('Invalid frequency setting')
            frequency = flag == '1'
        if not lines: raise ValueError('CSV is empty')
        headers = [value.strip().upper() for value in lines.pop(0).split(',')]
        if headers not in (['X'],['X','FREQ'],['X','Y'],['X','Y','FREQ']):
            raise ValueError('CSV headers: X, optional Y, optional Freq')
        rows = [line for line in lines if line.strip()]
        if len(rows) > MAX_ROWS: raise ValueError('CSV limit: 128 rows')
        dataset = cls('Y' in headers)
        dataset.rows = max(1,len(rows))
        dataset.set_frequency('FREQ' in headers if frequency is None else frequency)
        for row, line in enumerate(rows):
            fields = line.split(',')
            if len(fields) != len(headers): raise ValueError('CSV column count at row '+str(row+1))
            for column, field in zip(headers,fields):
                field = field.strip()
                if field: dataset.set(row, 'Freq' if column == 'FREQ' else column, float(field))
        return dataset
