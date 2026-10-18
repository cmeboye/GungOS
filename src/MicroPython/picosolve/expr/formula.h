/*
 * Formulas: compile a Python arithmetic expression once, then evaluate it at
 * many points without the interpreter. Plots, implicit surfaces and, later,
 * solver inputs (load functions, boundary conditions) evaluate the same
 * formula thousands of times; this is that loop in C.
 *
 * The language is the subset of Python the plot tools accept:
 *   numbers, named variables and constants, + - * / // % ** and unary -,
 *   parentheses, and calls to sin cos tan asin acos atan atan2 sqrt exp
 *   log (1 or 2 arguments) log10 sinh cosh tanh floor ceil int round float
 *   abs min max pow degrees radians, and _finite(v), which makes a point
 *   undefined unless v is finite (for evaluators stricter than Python's).
 *
 * Results match MicroPython's own evaluation bit for bit (float32, the same
 * C library functions, the same rules). A point where Python would raise
 * (division by zero, a math domain error, a complex power, converting inf to
 * int) is undefined and comes back as NaN.
 *
 * Python's integers are exact at any size; float32 holds whole numbers
 * exactly only up to 2^24 = 16,777,216. Whole-number arithmetic is checked
 * against that range, and a point that leaves it is flagged inexact: the
 * caller evaluates that point in Python (the binding does this through its
 * fallback). Powers whose base and exponent may both be ints and whole
 * literals over 7 digits are refused at compile time.
 *
 * One difference remains, tested: where min/max mixes whole and fractional
 * numbers, a zero result may carry a minus sign Python's int 0 lacks (it
 * compares and computes the same; atan2, the one place it would matter, is
 * refused). Anything else the compiler cannot match exactly, such as abs() of
 * a power that may turn complex, is refused, so the caller keeps using Python
 * for that formula.
 *
 * Evaluation runs 32 points at a time through each operation, which spreads
 * the cost of decoding the program over the whole block.
 */
#ifndef PICOSOLVE_FORMULA_H
#define PICOSOLVE_FORMULA_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define PSF_MAX_CODE 512
#define PSF_MAX_CONSTANTS 64
#define PSF_MAX_STACK 32
#define PSF_MAX_VARIABLES 8
#define PSF_MAX_NESTING 32
#define PSF_BLOCK 32

typedef enum
{
    PSF_OK = 0,
    PSF_ERR_SYNTAX,      /* not an expression this compiler reads */
    PSF_ERR_NAME,        /* unknown name, or a name used the wrong way */
    PSF_ERR_ARGUMENTS,   /* wrong number of arguments */
    PSF_ERR_UNSUPPORTED, /* valid Python, but not reproducible exactly here */
    PSF_ERR_TOO_LONG,    /* program, constants or stack over the limits */
} psf_status;

/* Converts a number literal exactly as the interpreter's lexer would. */
typedef float (*psf_number_fn)(const char *text, int length, bool integer, void *context);

typedef struct
{
    const char *const *variables; /* evaluation inputs, in order */
    int variable_count;
    const char *const *constant_names;
    const float *constant_values;
    int constant_count;
    /* Names that stand for another expression, such as r = sqrt(x*x+y*y+z*z). */
    const char *const *derived_names;
    const char *const *derived_texts;
    int derived_count;
    psf_number_fn number;
    void *context;
    /* MicroPython port options that change results (MICROPY_PY_MATH_*). */
    bool pow_fix_nan, atan2_fix_infnan;
} psf_options;

typedef struct
{
    uint16_t length;
    uint8_t constant_count, variable_count, depth;
    bool pow_fix_nan, atan2_fix_infnan;
    uint8_t code[PSF_MAX_CODE];
    float constant[PSF_MAX_CONSTANTS];
} psf_program;

/* error_at (optional) receives the text offset of the problem. */
psf_status psf_compile(psf_program *p, const char *text, int length, const psf_options *o, int *error_at);

/* Scratch memory psf_eval needs for this program. */
size_t psf_scratch_bytes(const psf_program *p);

/* One input per variable: data[i * stride] for point i, or value at every
 * point when data is NULL. */
typedef struct
{
    const float *data;
    int stride;
    float value;
} psf_input;

/*
 * Evaluate count points into out. A result is kept when it is finite and its
 * magnitude is at most limit; otherwise out holds NaN. inexact (optional,
 * count bytes) marks points Python must evaluate instead; they hold NaN and
 * are not kept. Returns the number of results kept.
 */
int psf_eval(const psf_program *p, const psf_input *inputs, int count, float limit, float *out,
             uint8_t *inexact, void *scratch);

#endif
