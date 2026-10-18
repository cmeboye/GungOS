/* Host tests for expr/formula: parsing, Python's rules, errors, blocks. */
#include "../expr/formula.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int checks, failures;

static float number(const char *text, int length, bool integer, void *context)
{
    (void)integer;
    (void)context;
    char buf[64];
    memcpy(buf, text, (size_t)length);
    buf[length] = 0;
    return strtof(buf, NULL);
}

static const char *const VARS[] = {"x", "y", "z"};
static const char *const CONST_NAMES[] = {"pi", "e"};
static const float CONST_VALUES[] = {3.14159265358979323846f, 2.71828182845904523536f};
static const char *const DERIVED_NAMES[] = {"r"};
static const char *const DERIVED_TEXTS[] = {"sqrt(x*x+y*y+z*z)"};

static psf_options options(void)
{
    psf_options o;
    memset(&o, 0, sizeof o);
    o.variables = VARS;
    o.variable_count = 3;
    o.constant_names = CONST_NAMES;
    o.constant_values = CONST_VALUES;
    o.constant_count = 2;
    o.derived_names = DERIVED_NAMES;
    o.derived_texts = DERIVED_TEXTS;
    o.derived_count = 1;
    o.number = number;
    return o;
}

static psf_status compile(psf_program *p, const char *text)
{
    const psf_options o = options();
    return psf_compile(p, text, (int)strlen(text), &o, NULL);
}

static float eval3(const char *text, float x, float y, float z)
{
    static psf_program p;
    static float scratch[PSF_MAX_STACK * PSF_BLOCK + PSF_BLOCK];
    if (compile(&p, text) != PSF_OK)
    {
        printf("FAIL compile %s\n", text);
        failures++;
        return NAN;
    }
    const psf_input in[3] = {{NULL, 0, x}, {NULL, 0, y}, {NULL, 0, z}};
    float out;
    psf_eval(&p, in, 1, INFINITY, &out, scratch);
    return out;
}

static void same(const char *text, float x, float y, float want)
{
    checks++;
    const float got = eval3(text, x, y, 0.0f);
    const bool ok = isnan(want) ? isnan(got) : memcmp(&got, &want, sizeof got) == 0;
    if (!ok)
    {
        printf("FAIL %s at (%g, %g): got %.9g want %.9g\n", text, (double)x, (double)y, (double)got, (double)want);
        failures++;
    }
}

static void refused(const char *text, psf_status want)
{
    checks++;
    psf_program p;
    const psf_status got = compile(&p, text);
    if (got != want)
    {
        printf("FAIL %s: status %d, want %d\n", text, got, want);
        failures++;
    }
}

int main(void)
{
    const float nan = NAN;

    /* Numbers, names and precedence as Python reads them. */
    same("2+3*4", 0, 0, 14.0f);
    same("2**3**2", 0, 0, 512.0f);
    same("-2**2", 0, 0, -4.0f);
    same("2**-1", 0, 0, 0.5f);
    same("(2+3)*4", 0, 0, 20.0f);
    same("1.5e3+.5", 0, 0, 1500.5f);
    same("x - y - 1", 5, 2, 2.0f);
    same("x / y / 2", 8, 2, 2.0f);
    same("pi", 0, 0, 3.14159265358979323846f);
    same("2*e", 0, 0, 2.0f * 2.71828182845904523536f);
    same("0.6*sin(x)*cos(y)", 1, 2, 0.6f * sinf(1.0f) * cosf(2.0f));
    same(" x\t*  2 ", 3, 0, 6.0f);
    same("+x", -3, 0, -3.0f);
    same("--x", -3, 0, -3.0f);

    /* Python's % and // follow the divisor's sign. */
    same("x % y", -7, 2, 1.0f);
    same("x % y", 7, -2, -1.0f);
    same("x // y", -7, 2, -4.0f);
    same("x // y", 7.5f, 2, 3.0f);
    same("x % y", 5.5f, 1.5f, 1.0f);

    /* Where Python raises, the point is undefined. */
    same("1/x", 0, 0, nan);
    same("x//y", 1, 0, nan);
    same("x%y", 1, 0, nan);
    same("1/(1/x)", 0, 0, nan);
    same("sqrt(x)", -1, 0, nan);
    same("log(x)", 0, 0, nan);
    same("log(x)", -1, 0, nan);
    same("log(x, 1)", 2, 0, nan);
    same("log(x, 2)", 8, 0, logf(8.0f) / logf(2.0f));
    same("asin(x)", 2, 0, nan);
    same("x**0.5", -4, 0, nan);
    same("x**-1", 0, 0, nan);
    same("x**2", -3, 0, 9.0f);
    same("exp(x)", 100, 0, nan);
    same("exp(x)", -200, 0, 0.0f);
    same("floor(x/y)", 1, 0, nan);
    same("int(exp(x))", 100, 0, nan);
    same("round(x)", 2.5f, 0, 2.0f);
    same("round(x)", 3.5f, 0, 4.0f);
    same("int(x)", -2.7f, 0, -2.0f);
    same("ceil(x)", -0.5f, 0, 0.0f);

    /* Overflow without raising stays IEEE, as in Python. */
    same("x*x*x*1e30", 1e10f, 0, nan);    /* inf: not finite */
    same("1/(x*x*x*1e30)", 1e10f, 0, 0.0f); /* 1/inf = 0, no error */

    /* Whole numbers have no negative zero: atan2 shows the sign. */
    same("atan2(ceil(x), -1)", -0.5f, 0, atan2f(0.0f, -1.0f));
    same("atan2(-0.0, -1)", 0, 0, atan2f(-0.0f, -1.0f));
    same("atan2(0*-1, -1)", 0, 0, atan2f(0.0f, -1.0f));
    same("atan2(0.0*-1, -1)", 0, 0, atan2f(-0.0f, -1.0f));

    /* min/max keep Python's first-wins chain, including NaN. */
    same("max(x, y, 3)", 1, 2, 3.0f);
    same("min(x, y)", 1, 2, 1.0f);
    same("degrees(x)", 1, 0, 1.0f * (180.0f / 3.14159265358979323846f));
    same("abs(x)", -2, 0, 2.0f);
    same("abs(x)**0.5", -4, 0, 2.0f);
    same("pow(x, 2)", 3, 0, 9.0f);

    /* _finite: overflow that Python carries on with becomes undefined. */
    same("1/(x*x*x*1e30)", 1e10f, 0, 0.0f);
    same("1/_finite(x*x*x*1e30)", 1e10f, 0, nan);
    same("_finite(x)+1", 2, 0, 3.0f);

    /* A derived name compiles its definition in place. */
    same("r", 3, 4, 5.0f);
    same("r*r-25", 3, 4, 0.0f);

    /* Refused: not reproducible exactly, or not this language. */
    refused("abs(x**0.5)", PSF_ERR_UNSUPPORTED);
    refused("abs(x**y)", PSF_ERR_UNSUPPORTED);
    refused("atan2(-max(x, 0), -1)", PSF_ERR_UNSUPPORTED);
    refused("atan2(y, 2*min(x, 0)+0.0)", PSF_ERR_UNSUPPORTED);
    same("atan2(-max(x, 0.0), -1)", -1, 0, atan2f(-0.0f, -1.0f));
    same("atan2(-max(x, 0)%5.0, -1)", -1, 0, atan2f(0.0f, -1.0f));
    refused("x(2)", PSF_ERR_NAME);
    refused("sin", PSF_ERR_NAME);
    refused("foo(x)", PSF_ERR_NAME);
    refused("q", PSF_ERR_NAME);
    refused("x,y", PSF_ERR_SYNTAX);
    refused("x+", PSF_ERR_SYNTAX);
    refused("(x", PSF_ERR_SYNTAX);
    refused("2(3)", PSF_ERR_SYNTAX);
    refused("x.y", PSF_ERR_SYNTAX);
    refused("1.2.3", PSF_ERR_SYNTAX);
    refused("2x", PSF_ERR_SYNTAX);
    refused("min(x)", PSF_ERR_ARGUMENTS);
    refused("sin(x, y)", PSF_ERR_ARGUMENTS);
    refused("round(x, 2)", PSF_ERR_ARGUMENTS);
    refused("sin()", PSF_ERR_ARGUMENTS);
    refused("x < y", PSF_ERR_SYNTAX);
    refused("((((((((((((((((((((((((((((((((((x))))))))))))))))))))))))))))))))))", PSF_ERR_TOO_LONG);

    /* Blocks: strided and broadcast inputs, partial last block, limit. */
    {
        psf_program p;
        static float scratch[PSF_MAX_STACK * PSF_BLOCK + PSF_BLOCK];
        compile(&p, "x*10+y+1/(x-50)");
        enum { N = 101 };
        float xs[N], flat[3 * N], out[N], out2[N];
        for (int i = 0; i < N; i++)
        {
            xs[i] = (float)i;
            flat[3 * i] = (float)i, flat[3 * i + 1] = 0.25f, flat[3 * i + 2] = 9.0f;
        }
        const psf_input a[3] = {{xs, 1, 0}, {NULL, 0, 0.25f}, {NULL, 0, 0}};
        const psf_input b[3] = {{flat, 3, 0}, {flat + 1, 3, 0}, {flat + 2, 3, 0}};
        const int kept = psf_eval(&p, a, N, 900.0f, out, scratch);
        psf_eval(&p, b, N, 900.0f, out2, scratch);
        int expect = 0, bad = 0;
        for (int i = 0; i < N; i++)
        {
            const float v = (float)i * 10.0f + 0.25f + 1.0f / ((float)i - 50.0f);
            const bool keep = i != 50 && fabsf(v) <= 900.0f;
            expect += keep;
            if (keep ? memcmp(&out[i], &v, sizeof v) != 0 : !isnan(out[i]))
                bad++;
            if (memcmp(&out[i], &out2[i], sizeof v) != 0 && !(isnan(out[i]) && isnan(out2[i])))
                bad++;
        }
        checks++;
        if (bad || kept != expect)
        {
            printf("FAIL blocks: %d bad, kept %d want %d\n", bad, kept, expect);
            failures++;
        }
    }

    printf("formula: %d checks, %d failures\n", checks, failures);
    return failures != 0;
}
