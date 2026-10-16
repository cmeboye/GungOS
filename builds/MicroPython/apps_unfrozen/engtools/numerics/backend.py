"""Lazy access to the selected native ulab build and its workspace guards."""

_modules = None
MAX_QR_ROWS = 64
MAX_QR_COLUMNS = 16
MAX_QR_WORKSPACE = 64 * 1024
HEAP_RESERVE = 80 * 1024


def require():
    """Return native numpy/scipy modules, checking the selected capabilities."""
    global _modules
    if _modules is None:
        try:
            from ulab import numpy as np, scipy as sp
        except ImportError:
            raise RuntimeError("This firmware needs the configured ulab build.")
        if np.zeros(1).itemsize != 4 or np.zeros(1, dtype=np.complex).itemsize != 8:
            raise RuntimeError("The selected numerical profile requires float32.")
        for module, names in (
            (np, ('sin', 'cos', 'exp', 'expm1', 'log', 'sqrt', 'dot', 'polyval',
                  'mean', 'std', 'interp', 'trapz', 'isfinite', 'conjugate')),
            (np.linalg, ('qr', 'cholesky', 'norm')),
            (np.fft, ('fft', 'ifft')),
            (sp.linalg, ('cho_solve', 'solve_triangular')),
            (sp.optimize, ('bisect', 'newton')),
            (sp.integrate, ('quad',)),
            (sp.signal, ('sosfilt',)),
        ):
            if any(not hasattr(module, name) for name in names):
                raise RuntimeError("The installed ulab configuration is incomplete.")
        _modules = np, sp
    return _modules


def information():
    """Describe the actual loaded library rather than a simulator substitute."""
    np, _ = require()
    import ulab
    return {'version': ulab.__version__, 'float_bits': np.zeros(1).itemsize * 8,
            'max_dims': 2, 'complex': True, 'fft_layout': 'real/imag arrays'}


def qr_workspace_bytes(rows, columns):
    """Conservative estimate including upstream's full temporary Q and R."""
    if rows < 1 or columns < 1 or rows < columns:
        raise ValueError("QR needs a nonempty matrix with rows >= columns.")
    # Full Q, full R, reduced Q/R and overhead. Caller already owns the input.
    return 4 * (rows * rows + 2 * rows * columns + columns * columns) + 4096


def guarded_qr(matrix):
    """QR for small, finite real float matrices with a protected heap reserve.

    Upstream computes a full square Q before reducing the outputs. Restrict
    dimensions and dtype before entering its C routine, including complex and
    wide matrices which that implementation does not safely handle.
    """
    np, _ = require()
    if not isinstance(matrix, np.ndarray) or matrix.ndim != 2:
        raise ValueError("QR input must be a two-dimensional ndarray.")
    if matrix.dtype != np.float:
        raise ValueError("QR input must use real float32 values.")
    rows, columns = matrix.shape
    workspace = qr_workspace_bytes(rows, columns)
    if rows > MAX_QR_ROWS or columns > MAX_QR_COLUMNS or workspace > MAX_QR_WORKSPACE:
        raise ValueError("QR exceeds the small-matrix workspace limit.")
    from gc import collect, mem_free
    collect()
    if workspace + HEAP_RESERVE > mem_free():
        raise MemoryError("Not enough free heap for QR and the UI reserve.")
    if not np.all(np.isfinite(matrix)):
        raise ValueError("QR input must contain finite values.")
    return np.linalg.qr(matrix, mode='reduced')
