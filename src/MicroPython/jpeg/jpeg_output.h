/* JPEGDEC tiles can have padding on their right edge. Preserve source stride. */
#pragma once
#include <stddef.h>
#include <stdint.h>

typedef void (*jpeg_blit_fn)(int x, int y, int w, int h, const uint16_t *pixels);

static inline int jpeg_output(JPEGDRAW *draw, jpeg_blit_fn blit)
{
    if (!draw || !draw->pPixels || draw->iWidth <= 0 || draw->iHeight <= 0)
        return 0;
    int width = draw->iWidthUsed;
    if (width <= 0)
        return 1;
    if (width >= draw->iWidth)
        blit(draw->x, draw->y, draw->iWidth, draw->iHeight, draw->pPixels);
    else
        for (int row = 0; row < draw->iHeight; row++)
            blit(draw->x, draw->y + row, width, 1,
                 draw->pPixels + (size_t)row * draw->iWidth);
    return 1;
}
