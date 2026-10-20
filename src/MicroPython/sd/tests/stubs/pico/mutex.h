/* Host stand-in: the tests run on one thread. */
#pragma once
typedef struct
{
    int depth;
} recursive_mutex_t;
#define auto_init_recursive_mutex(name) static recursive_mutex_t name
static inline void recursive_mutex_enter_blocking(recursive_mutex_t *m) { m->depth++; }
static inline void recursive_mutex_exit(recursive_mutex_t *m) { m->depth--; }
