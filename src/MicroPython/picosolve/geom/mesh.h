/*
 * Turning sampled fields into triangles: z = f(x, y) surfaces and the
 * f(x, y, z) = 0 isosurfaces of implicit plots (marching tetrahedra).
 *
 * The caller samples the field (it evaluates the user's formula); this code
 * does the geometry. Undefined samples are NaN. Triangles are written as 9
 * floats (three x, y, z vertices), in the order Graph3D always produced them.
 */
#ifndef PICOSOLVE_MESH_H
#define PICOSOLVE_MESH_H

#include <stdbool.h>
#include <stdint.h>

/* Below this squared cross product a triangle has no area and is skipped. */
#define PS_MESH_DEGENERATE 1e-20f
/* Most triangles one cube can produce: 6 tetrahedra x 2. */
#define PS_MESH_PER_CUBE 12

/*
 * Triangulate the cells between two rows of a sampled surface: row0 at y0
 * and row1 at y1, n samples at xs. Each cell gives two triangles, kept when
 * all three heights are finite and the triangle has area. Returns how many
 * were written to out (room for capacity triangles, at least 2 * (n - 1)).
 */
int ps_grid_strip(const float *row0, const float *row1, const float *xs, int n,
                  float y0, float y1, float *out, int capacity);

/*
 * Marching tetrahedra in the slab between two sampled planes at z0 and z1
 * (prev and cur, n x n samples, row-major in y then x, both axes at coords).
 * Cubes are visited from *cube; stops before a cube that might not fit in
 * capacity triangles, and sets *cube to resume there (n - 1)^2 when done).
 * For each triangle also writes its centre (3 floats) and the largest |f|
 * that is plausible at that centre, so the caller can reject triangles that
 * join sign changes across a pole: evaluate f at the centre and drop the
 * triangle when it is undefined or larger than the limit.
 */
int ps_iso_slab(const float *prev, const float *cur, const float *coords, int n,
                float z0, float z1, float *triangles, float *centres, float *limits,
                int capacity, int32_t *cube);

#endif
