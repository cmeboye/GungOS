/*
 * gfx_mesh - draw a triangle mesh in 3-D: rotate, project, depth-sort, clip
 * to a plot window, flat-shade and outline, in one call.
 *
 * Graph3D's renderer, moved from Python. Its maths is kept as it was:
 *   world point   (x, (z - z_center) * z_scale, y)     z is up in the data
 *   rotation      yaw about the vertical axis, then pitch
 *   projection    perspective with the camera at distance cam; points closer
 *                 than 0.45 are dropped with their triangle
 *   order         far triangles first (painter's algorithm, by centroid)
 *   colour        height along z picks a colour from a 256-step table; solid
 *                 faces are darkened by a fixed light direction
 */
#ifndef GFX_MESH_H
#define GFX_MESH_H

#include "gfx.h"

typedef struct
{
    float yaw, pitch;           /* radians */
    float cam;                  /* camera distance */
    float focal;                /* focal length times zoom, in pixels */
    float cx, cy;               /* screen position of the view centre */
    float z_center, z_scale;    /* data z -> world height */
    float z_min, z_max;         /* data z range for colouring */
    int clip_x0, clip_y0, clip_x1, clip_y1; /* plot window, inclusive */
    bool solid;                 /* filled faces plus outlines, else wireframe */
    uint16_t wire, wire_alt;    /* outline colours over solid faces */
    int stride;                 /* draw every stride-th triangle (previews) */
} gfx_mesh_view;

/*
 * Triangles are 9 floats each (three x, y, z vertices). flags[i] selects the
 * colour table: 0 for the first surface, non-zero for the second. ramp holds
 * two tables of 256 RGB triplets (768 bytes each), indexed by height.
 * order and depth are scratch arrays of count entries.
 * Returns the number of triangles drawn.
 */
int gfx_mesh(gfx_surface *s, const float *triangles, const uint8_t *flags, int count,
             const gfx_mesh_view *view, const uint8_t *ramp,
             int32_t *order, float *depth);

/* Clip a line to the window (Cohen-Sutherland); false if nothing is left. */
bool gfx_clip_line(float *x0, float *y0, float *x1, float *y1,
                   int xmin, int ymin, int xmax, int ymax);

#endif
