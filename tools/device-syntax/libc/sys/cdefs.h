#pragma once
#define __CONCAT1(x, y) x##y
#define __CONCAT(x, y) __CONCAT1(x, y)
#define __STRING(x) #x
#define __XSTRING(x) __STRING(x)
#define __unused __attribute__((__unused__))
#define __used __attribute__((__used__))
#define __packed __attribute__((__packed__))
#define __aligned(x) __attribute__((__aligned__(x)))
#define __always_inline __inline__ __attribute__((__always_inline__))
#define __noinline __attribute__((__noinline__))
#define __printflike(a, b) __attribute__((__format__(__printf__, a, b)))
