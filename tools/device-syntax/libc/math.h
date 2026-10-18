#pragma once
float sinf(float); float cosf(float); float sqrtf(float); float fabsf(float);
double sin(double); double cos(double); double sqrt(double); double fabs(double);
#define NAN __builtin_nanf("")
#define isfinite(x) __builtin_isfinite(x)
#define isnan(x) __builtin_isnan(x)
