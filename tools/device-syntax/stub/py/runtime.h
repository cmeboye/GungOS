/* MicroPython stub for a syntax-only device compile. */
#pragma once
#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>
typedef void *mp_obj_t;
typedef struct { const void *type; } mp_obj_base_t;
typedef struct { int unused; } mp_obj_type_t;
void *m_tracked_calloc(size_t, size_t); void m_tracked_free(void *);
#define m_new(type, n) ((type *)malloc(sizeof(type) * (n)))
#define m_del(type, p, n) free(p)
#include <stdlib.h>
typedef struct { int unused; } mp_print_t;
typedef int mp_print_kind_t;
typedef size_t qstr;
typedef struct { int unused; } mp_obj_module_t;
