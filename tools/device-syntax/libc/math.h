#pragma once
float sinf(float); float cosf(float); float tanf(float); float asinf(float); float acosf(float);
float atanf(float); float atan2f(float, float); float sqrtf(float); float fabsf(float);
float expf(float); float logf(float); float log10f(float); float powf(float, float);
float sinhf(float); float coshf(float); float tanhf(float); float fmodf(float, float);
float floorf(float); float ceilf(float); float truncf(float); float nearbyintf(float);
float copysignf(float, float);
double sin(double); double cos(double); double sqrt(double); double fabs(double);
#define NAN __builtin_nanf("")
#define INFINITY __builtin_inff()
#define isfinite(x) __builtin_isfinite(x)
#define isnan(x) __builtin_isnan(x)
#define isinf(x) __builtin_isinf(x)
#define signbit(x) __builtin_signbit(x)
