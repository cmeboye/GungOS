#pragma once
#include <stddef.h>
#include <stdint.h>
/* A single, caller-owned workspace, never a full image. */
#define GUNGOS_PNG_WORKSPACE_LIMIT (48 * 1024)
#define GUNGOS_PNG_INPUT_LIMIT (4 * 1024 * 1024)
typedef int (*gungos_png_read)(void *, uint8_t *, int);
typedef int (*gungos_png_row)(void *, int, int, const uint8_t *);
typedef struct {
    int source_width, source_height, width, height;
} gungos_png_info;
size_t gungos_png_workspace_size(void);
/* Sequential input; output rows are RGB332, width <= 320. bg is RGB888. */
const char *gungos_png_decode(void *workspace, gungos_png_read read, void *input,
    unsigned size, int width, int height, uint32_t bg,
    gungos_png_row row, void *output, gungos_png_info *info);
/* ZIP raw-deflate extraction uses the same workspace, in a separate call. */
typedef int (*gungos_png_write)(void *, const uint8_t *, int);
const char *gungos_zip_inflate(void *workspace,gungos_png_read read,void *input,
    unsigned compressed,unsigned plain,uint32_t crc,gungos_png_write write,void *output);
