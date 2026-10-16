"""Small analytical checks with timings for the actual native numerics build.

Each yielded record times one complete numerical check, including its setup
and validation. Heap delta is an allocation snapshot, not peak workspace.
Desktop timings cannot predict device timings.
"""


def _near(value, expected, tolerance=2e-5):
    from math import isfinite
    if not isfinite(value) or abs(value - expected) > tolerance:
        raise ValueError("Numerical result outside tolerance")


def _arrays(np, sp):
    values = np.linspace(0, 1, 256)
    output = np.zeros(256)
    for _ in range(16):
        np.exp(values, out=output)
    _near(output[0], 1)
    from math import e
    _near(output[-1], e)
    _near(np.mean(values), .5)
    _near(np.interp(np.array([.25]), values, values)[0], .25)


def _complex(np, sp):
    values = np.array([1 + 2j, 3 - 4j], dtype=np.complex)
    result = values * np.conjugate(values)
    _near(result[0].real, 5)
    _near(result[1].real, 25)
    _near(result[1].imag, 0)


def _qr(np, sp):
    from .backend import guarded_qr
    matrix = np.array([[1, 0], [1, 1], [1, 2], [1, 3]])
    values = np.array([2, 5, 8, 11])
    q, r = guarded_qr(matrix)
    solution = sp.linalg.solve_triangular(r, np.dot(q.transpose(), values), lower=False)
    _near(solution[0], 2)
    _near(solution[1], 3)
    _near(np.linalg.norm(np.dot(matrix, solution) - values), 0)
    fitted = np.polyval(np.array([solution[1], solution[0]]), np.array([2]))
    _near(fitted[0], 8)


def _cholesky(np, sp):
    matrix = np.array([[4, 1], [1, 3]])
    values = np.array([1, 2])
    solution = sp.linalg.cho_solve(np.linalg.cholesky(matrix), values)
    _near(solution[0], 1 / 11)
    _near(solution[1], 7 / 11)


def _roots(np, sp):
    function = lambda x: x * x - 2
    from math import sqrt
    root = sp.optimize.bisect(function, 0, 2, xtol=1e-5, maxiter=32)
    _near(root, sqrt(2))
    root = sp.optimize.newton(function, 1, tol=1e-5, maxiter=32)
    _near(root, sqrt(2))
    _near(function(root), 0)


def _integrals(np, sp):
    value, error = sp.integrate.quad(lambda x: x * x, 0, 1, eps=1e-5, order=3)
    _near(value, 1 / 3)
    if not 0 <= error < 1e-5:
        raise ValueError("Unexpected quadrature error estimate")
    x = np.linspace(0, 1, 65)
    _near(np.trapz(x * x, x), 1 / 3, 6e-5)


def _fft(np, sp):
    x = np.arange(256)
    signal = np.sin(x * (2 * np.pi * 8 / 256))
    real, imag = np.fft.fft(signal)
    _near(real[8], 0, 3e-4)
    _near(abs(imag[8]), 128, 3e-4)
    reconstructed, imaginary = np.fft.ifft(real, imag)
    _near(np.max(abs(reconstructed - signal)), 0)
    _near(np.max(abs(imaginary)), 0)


def _filter(np, sp):
    coefficients = [[.5, .5, 0, 1, 0, 0]]
    result = sp.signal.sosfilt(coefficients, np.array([1, 0, 0, 0]))
    for value, expected in zip(result, (.5, .5, 0, 0)):
        _near(value, expected)
    first, state = sp.signal.sosfilt(coefficients, np.array([1]), zi=np.zeros((1, 2)))
    second, state = sp.signal.sosfilt(coefficients, np.array([0, 0, 0]), zi=state)
    _near(first[0], .5)
    _near(second[0], .5)
    _near(second[-1], 0)


CASES = (
    ('Arrays / statistics', _arrays), ('Complex arithmetic', _complex),
    ('QR / fitting', _qr), ('Cholesky solve', _cholesky),
    ('Root finding', _roots), ('Integration', _integrals),
    ('FFT 256 / inverse', _fft), ('SOS filtering', _filter),
)


def checks():
    """Yield one bounded numerical check at a time; caller can cancel between."""
    from .backend import require
    from gc import collect, mem_free
    from time import ticks_us, ticks_diff
    np, sp = require()
    for name, function in CASES:
        collect()
        before = mem_free()
        start = ticks_us()
        error = ''
        try:
            function(np, sp)
        except Exception as exc:
            error = str(exc)
        elapsed = ticks_diff(ticks_us(), start)
        delta = before - mem_free()
        yield {'name': name, 'passed': not error, 'elapsed_us': elapsed,
               'heap_delta_bytes': delta, 'error': error}
