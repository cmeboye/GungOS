"""Single-channel Lenia using the configured ulab FFT, in cancellable batches.

Orbium seed/parameters: Bert Chan's Lenia, MIT (2018); see guides/Lenia-LICENSE.txt.
Source: https://github.com/Chakazul/Lenia/blob/master/Python/animals.json (O2u).
All solver/UI code here is the GungOS implementation.
"""
from math import exp, sqrt, isfinite, floor
from random import randint
from ulab import numpy as np

SIZES = (16, 32, 64)
RATES = (1, 2, 4, 8, 12, 16)
SHAPES = ('Polynomial', 'Gaussian', 'Step')
SEEDS = ('Orbium', 'Twin Orbium', 'Ring', 'Noise')
DEFAULTS = dict(size=32, radius=8.0, mu=0.15, sigma=0.015, dt=0.1,
                kernel='Polynomial', growth='Gaussian', center=0.5, width=0.5,
                rings=1, b1=1.0, b2=0.5, b3=0.25, seed='Orbium', density=0.35,
                amplitude=1.0, fps=8, gamma=0.75, grid=False, stats=True)
# Numeric values are intentionally limited as well as checked for finiteness.
LIMITS = dict(radius=(2.0, 31.0, 0.5), mu=(0.01, 0.6, 0.001),
              sigma=(0.001, 0.15, 0.001), dt=(0.01, 0.3, 0.01),
              center=(0.1, 0.9, 0.05), width=(0.05, 0.5, 0.025),
              b1=(0.0, 1.0, 0.1), b2=(0.0, 1.0, 0.1), b3=(0.0, 1.0, 0.1),
              density=(0.05, 1.0, 0.05), amplitude=(0.1, 1.0, 0.05),
              gamma=(0.25, 2.0, 0.05))
CHOICES = dict(size=SIZES, fps=RATES, kernel=SHAPES, growth=SHAPES,
               rings=(1, 2, 3), seed=SEEDS, grid=(False, True), stats=(False, True))


def clean(values):
    result = DEFAULTS.copy()
    if isinstance(values, dict):
        for name, allowed in CHOICES.items():
            value = values.get(name)
            if type(value) is type(allowed[0]) and value in allowed:
                result[name] = value
        for name, (low, high, step) in LIMITS.items():
            value = values.get(name)
            if type(value) in (int, float) and isfinite(value) and low <= value <= high:
                result[name] = float(value)
    result['radius'] = min(result['radius'], result['size'] / 2 - 1)
    return result


def validate(values):
    if clean(values) != values:
        raise ValueError('Parameter outside supported range')
    if sum(values['b'+str(i+1)] for i in range(values['rings'])) <= 0:
        raise ValueError('At least one ring weight must be > 0')


def estimate(size):
    # Four persistent float32 grids plus row FFT/growth temporaries and render work.
    return 16 * size * size + size * 192 + 4096


def fft2(real, imag, inverse=False):
    """ulab provides a 1-D FFT; compose it over strided rows and columns."""
    transform = np.fft.ifft if inverse else np.fft.fft
    size = real.shape[0]
    for row in range(size):
        r, i = transform(real[row, :], imag[row, :])
        real[row, :], imag[row, :] = r, i
        yield None
    for col in range(size):
        r, i = transform(real[:, col], imag[:, col])
        real[:, col], imag[:, col] = r, i
        yield None


class Field:
    def __init__(self, options):
        from gc import collect, mem_free
        validate(options)
        collect()
        self.options = options.copy()
        self.size = size = options['size']
        if mem_free() < estimate(size) + 32768:
            raise MemoryError('Low heap; choose a smaller grid')
        self.a = np.zeros((size, size))
        self.real = np.zeros((size, size))
        self.imag = np.zeros((size, size))
        self.kernel = np.zeros((size, size))
        self.generation = 0
        self.build_kernel()
        self.reseed()

    def build_kernel(self):
        o, n = self.options, self.size
        weights = (o['b1'], o['b2'], o['b3'])
        total = 0.0
        self.imag[:] = 0
        for y in range(n):
            yy = min(y, n-y)
            for x in range(n):
                xx = min(x, n-x)
                distance = sqrt(xx*xx+yy*yy) / o['radius'] * o['rings']
                ring = int(distance)
                value = 0.0
                if ring < o['rings']:
                    t = (distance-ring-o['center']) / o['width']
                    if abs(t) < 1:
                        value = ((1-t*t)**4 if o['kernel']=='Polynomial' else
                                 exp(-4.5*t*t) if o['kernel']=='Gaussian' else 1.0) * weights[ring]
                self.kernel[y, x] = value
                total += value
        if total <= 1e-10:
            raise ValueError('Kernel empty; increase radius/width')
        self.kernel[:] = self.kernel / total
        # Radial kernels are circularly even, hence their Fourier spectrum is real.
        for _ in fft2(self.kernel, self.imag):pass
        self.imag[:] = 0

    def reseed(self, randomize=False):
        n, o = self.size, self.options
        self.a[:] = 0
        self.generation = 0
        mode = o['seed']
        if mode in ('Orbium', 'Twin Orbium'):
            count = 2 if mode=='Twin Orbium' else 1
            for index in range(count):
                cx = n//2 if count==1 else (n//4 if index==0 else n*3//4)
                cy = n//2
                turn = 0
                if randomize:
                    cx, cy, turn = randint(0,n-1), randint(0,n-1), randint(0,3)
                scale = o['radius']/13
                width, height = max(2,round(ORB_W*scale)), max(2,round(ORB_H*scale))
                for y in range(height):
                    sy = (y+0.5)/scale-0.5
                    iy = int(floor(sy)); fy = sy-iy
                    for x in range(width):
                        sx = (x+0.5)/scale-0.5
                        ix = int(floor(sx)); fx = sx-ix
                        value = 0.0
                        for dy in (0,1):
                            for dx in (0,1):
                                xx, yy = ix+dx, iy+dy
                                if 0<=xx<ORB_W and 0<=yy<ORB_H:
                                    value += ORBIUM[yy*ORB_W+xx]/255 * (fx if dx else 1-fx) * (fy if dy else 1-fy)
                        xx, yy = x-width//2, y-height//2
                        for _ in range(turn):xx,yy=-yy,xx
                        dest = ((cy+yy)%n, (cx+xx)%n)
                        self.a[dest] = max(self.a[dest], value*o['amplitude'])
        elif mode=='Ring':
            cx, cy = (randint(0,n-1),randint(0,n-1)) if randomize else (n//2,n//2)
            for y in range(n):
                for x in range(n):
                    dx,dy=min(abs(x-cx),n-abs(x-cx)),min(abs(y-cy),n-abs(y-cy))
                    r=sqrt(dx*dx+dy*dy)/o['radius']
                    self.a[y,x]=o['amplitude']*exp(-((r-0.6)/0.2)**2)
        else:
            for y in range(n):
                for x in range(n):
                    self.a[y,x]=randint(0,1000)/1000*o['amplitude'] if randint(0,999)<o['density']*1000 else 0

    def step(self):
        """Publish a complete generation atomically; cancellation keeps a intact."""
        o, n = self.options, self.size
        self.real[:] = self.a
        self.imag[:] = 0
        for _ in fft2(self.real, self.imag):yield None
        self.real[:] = self.real * self.kernel
        self.imag[:] = self.imag * self.kernel
        yield None
        for _ in fft2(self.real, self.imag, True):yield None
        # imag is now free scratch for the next generation. Row operations bound
        # temporary allocation; the old visible generation remains unchanged.
        for row in range(n):
            t = (self.real[row,:]-o['mu'])/o['sigma']
            if o['growth']=='Gaussian':growth=2*np.exp(-t*t/2)-1
            elif o['growth']=='Polynomial':growth=2*np.maximum(1-t*t/9,0)**4-1
            else:growth=np.where(abs(t)<=1,1.0,-1.0)
            self.imag[row,:] = np.clip(self.a[row,:]+o['dt']*growth,0,1)
            yield None
        self.a, self.imag = self.imag, self.a
        self.generation += 1

ORB_W, ORB_H = 20, 20
ORBIUM = bytes.fromhex(
    '000000000000000d040000000000003c000000000000000000002335361512191a12014100000000000000000016445b6257'
    '302f2c2f2d1b590000000000000003115974776121140e101f37b400000000000009212f5767624822000000000c66540000'
    '010004232b221c3f454335000000000005dc00003c001a2c140000334f5e5f3d0000000000742800001f2f1c000000456d81'
    '89820000000000008400009637080000003087a2aeae6b00000000006d00008d3c00000000079ec1d6dace1b000000004819'
    '0000980000000000aadff5fdf88f0000000039240000d6000000000081f7ffffffe947000006382200008d130000000055ff'
    'fffafff88e280d1e3e1600000872000000002dd9ffe4dcdda65532373b0a0000006c1d0000001d9ee0d2c7bd9c684b442a00'
    '00000014551300001e6cacb8ada086674f391000000000002a42261e2c567f8e8b7f6d563e1e00000000000000253b3c4251'
    '636c695c4e3a20050000000000000000122b3a404647423b2a180500000000000000000000000f1a21221e140b0000000000'
)
