"""Stress at a point: rotation, principal stresses and yield checks.

Stresses are in MPa, angles in degrees. A state is a dict:
  mode   '2D' (plane stress, sz = tyz = tzx = 0) or '3D'
  s      [sx, sy, sz, txy, tyz, tzx]
  theta  rotation angle about `axis`, counterclockwise looking down the axis
  axis   'x', 'y' or 'z' (always 'z' in 2D)
  yield  yield strength for the safety factors, 0 when unused
"""
from math import sqrt, sin, cos, atan2, acos, pi, radians, degrees

AXES = ('x', 'y', 'z')
# Rotating about an axis turns the next axis toward the one after it.
PLANES = {'z': (0, 1), 'x': (1, 2), 'y': (2, 0)}


def new_state():
    return {'mode': '2D', 's': [80.0, -40.0, 0.0, 30.0, 0.0, 0.0], 'theta': 0.0, 'axis': 'z', 'yield': 0.0}


def components(state):
    s = state['s']
    if state['mode'] == '2D':
        return [s[0], s[1], 0.0, s[3], 0.0, 0.0]
    return list(s)


def tensor(state):
    sx, sy, sz, txy, tyz, tzx = components(state)
    return [[sx, txy, tzx], [txy, sy, tyz], [tzx, tyz, sz]]


def axis(state):
    return 'z' if state['mode'] == '2D' else state['axis']


def plane(state):
    """Indices (i, j) of the rotation plane: theta turns i toward j."""
    return PLANES[axis(state)]


def rotated(state, theta=None):
    """The tensor in axes turned by theta about the rotation axis."""
    S = tensor(state)
    i, j = plane(state)
    t = radians(state['theta'] if theta is None else theta)
    c, s = cos(t), sin(t)
    k = 3 - i - j
    basis = [None, None, None]
    ei, ej = [0.0] * 3, [0.0] * 3
    ei[i], ei[j] = c, s
    ej[i], ej[j] = -s, c
    ek = [0.0] * 3
    ek[k] = 1.0
    basis[i], basis[j], basis[k] = ei, ej, ek
    out = [[0.0] * 3 for _ in range(3)]
    for a in range(3):
        Sa = [S[r][0] * basis[a][0] + S[r][1] * basis[a][1] + S[r][2] * basis[a][2] for r in range(3)]
        for b in range(a, 3):
            v = basis[b][0] * Sa[0] + basis[b][1] * Sa[1] + basis[b][2] * Sa[2]
            out[a][b] = out[b][a] = v
    return out


def plane_circle(state):
    """Centre, radius and principal angle (deg, to the larger stress) of the
    Mohr circle for rotations about the axis; the same at every theta."""
    S = tensor(state)
    i, j = plane(state)
    a = (S[i][i] + S[j][j]) / 2
    b = (S[i][i] - S[j][j]) / 2
    t = S[i][j]
    return a, sqrt(b * b + t * t), degrees(atan2(2 * t, 2 * b)) / 2


def principal(state):
    """Principal stresses s1 >= s2 >= s3 (s3 is the out-of-plane 0 in 2D)."""
    S = tensor(state)
    p1 = S[0][1] ** 2 + S[1][2] ** 2 + S[0][2] ** 2
    diag = [S[0][0], S[1][1], S[2][2]]
    if p1 <= 1e-24 * (1 + sum(d * d for d in diag)):
        values = diag
    else:
        q = sum(diag) / 3
        p = sqrt(((diag[0] - q) ** 2 + (diag[1] - q) ** 2 + (diag[2] - q) ** 2 + 2 * p1) / 6)
        B = [[(S[r][c] - (q if r == c else 0.0)) / p for c in range(3)] for r in range(3)]
        det = (B[0][0] * (B[1][1] * B[2][2] - B[1][2] * B[2][1]) -
               B[0][1] * (B[1][0] * B[2][2] - B[1][2] * B[2][0]) +
               B[0][2] * (B[1][0] * B[2][1] - B[1][1] * B[2][0]))
        phi = acos(min(1.0, max(-1.0, det / 2))) / 3
        e1 = q + 2 * p * cos(phi)
        e3 = q + 2 * p * cos(phi + 2 * pi / 3)
        values = [e1, 3 * q - e1 - e3, e3]
    values.sort()
    return values[2], values[1], values[0]


def results(state):
    centre, radius, angle = plane_circle(state)
    if state['mode'] == '2D':
        # Exact in-plane values; the third principal stress is the zero out of plane.
        s1, s2, s3 = sorted((centre + radius, centre - radius, 0.0), reverse=True)
    else:
        s1, s2, s3 = principal(state)
    R = rotated(state)
    i, j = plane(state)
    out = {'s1': s1, 's2': s2, 's3': s3, 'centre': centre, 'radius': radius, 'angle': angle,
           'si': R[i][i], 'sj': R[j][j], 'tij': R[i][j],
           'tmax': (s1 - s3) / 2,
           'mises': sqrt(((s1 - s2) ** 2 + (s2 - s3) ** 2 + (s3 - s1) ** 2) / 2),
           'tresca': s1 - s3}
    if state['mode'] == '2D':
        out['p1'], out['p2'] = centre + radius, centre - radius
    # Snap single-precision round-off to zero, relative to the stress level.
    tol = 1e-5 * max(abs(v) for v in components(state))
    for key in out:
        if key != 'angle' and abs(out[key]) < tol:
            out[key] = 0.0
    if state['yield'] > 0:
        out['n_mises'] = state['yield'] / out['mises'] if out['mises'] > 1e-12 else None
        out['n_tresca'] = state['yield'] / out['tresca'] if out['tresca'] > 1e-12 else None
    return out


def principal_angle(state, second=False):
    """Theta that puts the larger (or, with second, the smaller) in-plane
    principal stress on the first rotated axis."""
    angle = plane_circle(state)[2] + (90.0 if second else 0.0)
    return wrap(angle)


def shear_angle(state, second=False):
    return wrap(plane_circle(state)[2] + (-45.0 if second else 45.0))


def wrap(angle):
    """An angle in (-180, 180]."""
    angle = angle % 360.0
    return angle - 360.0 if angle > 180.0 else angle
