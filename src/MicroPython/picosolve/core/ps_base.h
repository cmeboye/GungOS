/*
 * picosolve - shared definitions for the solver kernel.
 *
 * The kernel never allocates memory: every function works on blocks the
 * caller sized beforehand, so nothing is allocated while a solve runs and
 * the solve can run on the second core without touching Python objects.
 */
#ifndef PICOSOLVE_BASE_H
#define PICOSOLVE_BASE_H

#include <stddef.h>
#include <stdint.h>

/* Hot loops run from SRAM on the device instead of through the flash cache. */
#if defined(PICO_ON_DEVICE) && PICO_ON_DEVICE
#include "pico.h"
#define PS_HOT(name) __not_in_flash_func(name)
#else
#define PS_HOT(name) name
#endif

typedef enum
{
    PS_OK = 0,
    PS_CANCELLED,      /* the UI asked the solve to stop */
    PS_ERR_ARGUMENT,   /* index or value out of range; item = offending index */
    PS_ERR_STATE,      /* called out of order, e.g. results before solving */
    PS_ERR_SECTION,    /* E or I not positive; item = section */
    PS_ERR_GEOMETRY,   /* element missing, zero-length or reversed; item = element */
    PS_ERR_LOAD,       /* load outside its element or on a missing target; item = load */
    PS_ERR_UNCONNECTED,/* node not attached to any element; item = node */
    PS_ERR_SUPPORT,    /* spring or settlement on an unsuitable DOF; item = node, dof */
    PS_ERR_MECHANISM,  /* structure can move freely; item = node, dof */
    PS_ERR_ACCURACY,   /* single precision is not enough; solve again in double */
    PS_ERR_SINGULAR,   /* circuit has no unique solution; item = node or element */
    PS_ERR_CONVERGENCE,/* circuit: Newton iterations do not settle */
    PS_ERR_TIMESTEP,   /* circuit: time step shrank below its minimum */
    PS_ERR_SPACE,      /* LU fill outgrew its block: enlarge it and call again */
    PS_PENDING,        /* not an error: more work remains, call again */
} ps_status;

/* Shared between the solving core and the UI core. */
typedef struct
{
    volatile int32_t cancel; /* UI sets non-zero to stop the solve */
    volatile int32_t done;   /* work units finished */
    volatile int32_t total;  /* work units in this solve */
} ps_control;

#endif
