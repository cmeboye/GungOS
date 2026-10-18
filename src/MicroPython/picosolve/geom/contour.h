/*
 * Contours of a sampled 2-D field: where f = 0 crosses a row of cells
 * (marching squares), as line segments. Used for implicit curves in Graph
 * and, later, isotherms and other contour plots.
 *
 * Cells lie between two rows of samples: upper (at y0) and lower (at y1),
 * n samples at xs, plus one sample at each cell's centre. NaN means
 * undefined; cells touching an undefined sample are skipped.
 *
 * Fields with poles (like 1/x) change sign without crossing zero. Callers
 * that need to guard against that make two passes: contour_queries lists the
 * midpoint of every edge that changes sign, the caller evaluates the field
 * there, and contour_segments drops edges whose midpoint value is undefined
 * or implausibly large. Without midpoint values every sign change counts.
 */
#ifndef PICOSOLVE_CONTOUR_H
#define PICOSOLVE_CONTOUR_H

/* Edge midpoints to evaluate: 2 floats (x, y) each. Returns the count. */
int ps_contour_queries(const float *upper, const float *lower, const float *centres,
                       const float *xs, int n, float y0, float y1, float *queries, int capacity);

/* Segments: 4 floats (x0, y0, x1, y1) each. mids may be NULL. Returns the count. */
int ps_contour_segments(const float *upper, const float *lower, const float *centres,
                        const float *xs, int n, float y0, float y1, const float *mids,
                        float *segments, int capacity);

#endif
