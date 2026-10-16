/* Shared ulab configuration for PicoCalc and its MicroPython simulator. */
#pragma once

/* Vectors/matrices and phasors; retain direct loops for execution speed. */
#define ULAB_MAX_DIMS 2
#define ULAB_SUPPORTS_COMPLEX 1
#define ULAB_HAS_SCIPY 1
#define ULAB_HAS_FUNCTION_ITERATOR 0
#define NDARRAY_BINARY_USES_FUN_POINTER 0
#define ULAB_VECTORISE_USES_FUN_POINTER 0
#define ULAB_MATH_FUNCTIONS_OUT_KEYWORD 1

/* Keep slicing, shapes, transpose, copying and numeric buffer conversion. */
#define ULAB_HAS_DTYPE_OBJECT 0
#define ULAB_HAS_PRINTOPTIONS 0
#define ULAB_NUMPY_HAS_NDINFO 0
#define NDARRAY_HAS_BYTESWAP 0
#define NDARRAY_HAS_SORT 0
#define NDARRAY_HAS_FLATITER 0
#define NDARRAY_HAS_BINARY_OP_AND 0
#define NDARRAY_HAS_BINARY_OP_OR 0
#define NDARRAY_HAS_BINARY_OP_XOR 0
#define NDARRAY_HAS_BINARY_OP_FLOOR_DIVIDE 0
#define NDARRAY_HAS_BINARY_OP_MODULO 0
#define NDARRAY_HAS_INPLACE_MODULO 0
#define NDARRAY_HAS_UNARY_OP_INVERT 0

/* Arrays, broadcasting, common maths, reductions and interpolation remain.
 * Keep native sort for calculator quantiles. Exclude bitwise utilities,
 * additional reordering, generic Python callback vectorize,
 * redundant fitting, and file formats handled by the engineering package. */
#define ULAB_NUMPY_HAS_BITWISE_AND 0
#define ULAB_NUMPY_HAS_BITWISE_OR 0
#define ULAB_NUMPY_HAS_BITWISE_XOR 0
#define ULAB_NUMPY_HAS_LEFT_SHIFT 0
#define ULAB_NUMPY_HAS_RIGHT_SHIFT 0
#define ULAB_NUMPY_HAS_BINCOUNT 0
#define ULAB_NUMPY_HAS_NONZERO 0
#define ULAB_NUMPY_HAS_ARGSORT 0
#define ULAB_NUMPY_HAS_COMPRESS 0
#define ULAB_NUMPY_HAS_CONVOLVE 0
#define ULAB_NUMPY_HAS_CROSS 0
#define ULAB_NUMPY_HAS_DELETE 0
#define ULAB_NUMPY_HAS_FLIP 0
#define ULAB_NUMPY_HAS_MEDIAN 0
#define ULAB_NUMPY_HAS_POLYFIT 0
#define ULAB_NUMPY_HAS_ROLL 0
#define ULAB_NUMPY_HAS_SORT 1
#define ULAB_NUMPY_HAS_SORT_COMPLEX 0
#define ULAB_NUMPY_HAS_TAKE 0
#define ULAB_NUMPY_HAS_LOAD 0
#define ULAB_NUMPY_HAS_LOADTXT 0
#define ULAB_NUMPY_HAS_SAVE 0
#define ULAB_NUMPY_HAS_SAVETXT 0
#define ULAB_NUMPY_HAS_VECTORIZE 0
#define ULAB_NUMPY_HAS_ACOSH 0
#define ULAB_NUMPY_HAS_ASINH 0
#define ULAB_NUMPY_HAS_ATANH 0
#define ULAB_NUMPY_HAS_AROUND 0
#define ULAB_NUMPY_HAS_SINC 0

/* Small real linear systems and least squares through factorisations. */
#define ULAB_NUMPY_HAS_LINALG_MODULE 1
#define ULAB_LINALG_HAS_CHOLESKY 1
#define ULAB_LINALG_HAS_QR 1
#define ULAB_LINALG_HAS_NORM 1
#define ULAB_LINALG_HAS_DET 0
#define ULAB_LINALG_HAS_INV 0
#define ULAB_LINALG_HAS_EIG 0
#define ULAB_SCIPY_HAS_LINALG_MODULE 1
#define ULAB_SCIPY_LINALG_HAS_CHO_SOLVE 1
#define ULAB_SCIPY_LINALG_HAS_SOLVE_TRIANGULAR 1

/* One function integrator plus numpy.trapz for sampled data. */
#define ULAB_SCIPY_HAS_INTEGRATE_MODULE 1
#define ULAB_INTEGRATE_HAS_QUAD 1
#define ULAB_INTEGRATE_HAS_ROMBERG 0
#define ULAB_INTEGRATE_HAS_SIMPSON 0
#define ULAB_INTEGRATE_HAS_TANHSINH 0

/* Scalar roots; optimisation and curve fitting will use bounded wrappers. */
#define ULAB_SCIPY_HAS_OPTIMIZE_MODULE 1
#define ULAB_SCIPY_OPTIMIZE_HAS_BISECT 1
#define ULAB_SCIPY_OPTIMIZE_HAS_NEWTON 1
#define ULAB_SCIPY_OPTIMIZE_HAS_FMIN 0
#define ULAB_SCIPY_OPTIMIZE_HAS_CURVE_FIT 0

/* Spectrum/filter tools. Split real/imag FFT outputs avoid an extra complex
 * output copy; complex ndarray arithmetic remains available independently. */
#define ULAB_NUMPY_HAS_FFT_MODULE 1
#define ULAB_FFT_HAS_FFT 1
#define ULAB_FFT_HAS_IFFT 1
#define ULAB_FFT_IS_NUMPY_COMPATIBLE 0
#define ULAB_SCIPY_HAS_SIGNAL_MODULE 1
#define ULAB_SCIPY_SIGNAL_HAS_SOSFILT 1

/* No random, special-function, spectrogram or custom user modules. */
#define ULAB_NUMPY_HAS_RANDOM_MODULE 0
#define ULAB_NUMPY_RANDOM_HAS_NORMAL 0
#define ULAB_NUMPY_RANDOM_HAS_RANDOM 0
#define ULAB_NUMPY_RANDOM_HAS_UNIFORM 0
#define ULAB_SCIPY_HAS_SPECIAL_MODULE 0
#define ULAB_SCIPY_SPECIAL_HAS_ERF 0
#define ULAB_SCIPY_SPECIAL_HAS_ERFC 0
#define ULAB_SCIPY_SPECIAL_HAS_GAMMA 0
#define ULAB_SCIPY_SPECIAL_HAS_GAMMALN 0
#define ULAB_HAS_UTILS_MODULE 0
#define ULAB_UTILS_HAS_FROM_INT16_BUFFER 0
#define ULAB_UTILS_HAS_FROM_UINT16_BUFFER 0
#define ULAB_UTILS_HAS_FROM_INT32_BUFFER 0
#define ULAB_UTILS_HAS_FROM_UINT32_BUFFER 0
#define ULAB_UTILS_HAS_SPECTROGRAM 0
#define ULAB_HAS_USER_MODULE 0
