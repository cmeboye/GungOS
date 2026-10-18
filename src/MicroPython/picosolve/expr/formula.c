#include "formula.h"
#include "../core/ps_base.h"
#include <math.h>
#include <string.h>

/* Python rounds after every operation; a fused multiply-add would not, and
 * this code must reproduce Python's arithmetic exactly. */
#if defined(__clang__)
#pragma STDC FP_CONTRACT OFF
#elif defined(__GNUC__)
#pragma GCC optimize("fp-contract=off")
#endif

/* The same float constant MicroPython's math module uses (MP_PI). */
#define PSF_PI 3.14159265358979323846f

enum
{
    OP_END,
    OP_VAR,   /* + variable index */
    OP_CONST, /* + constant index */
    OP_NEG,
    OP_ZERO, /* -0 -> +0: whole numbers have no negative zero */
    OP_ADD,
    OP_SUB,
    OP_MUL,
    OP_DIV,
    OP_FLOORDIV,
    OP_MOD,
    OP_POW,
    OP_ABS,
    OP_FN1, /* + index into FN1 */
    OP_LOG,
    OP_LOGB,
    OP_ATAN2,
    OP_FLOOR,
    OP_CEIL,
    OP_TRUNC,
    OP_ROUND,
    OP_DEGREES,
    OP_RADIANS,
    OP_MIN, /* + argument count */
    OP_MAX, /* + argument count */
    OP_NONE, /* identity: float() */
    OP_FINITE /* _finite(): undefined unless finite */
};

/* math functions that follow MicroPython's math_generic_1 rule. */
static float (*const FN1[])(float) = {sinf, cosf, tanf, asinf, acosf, atanf, sqrtf, expf,
                                      log10f, sinhf, coshf, tanhf};

typedef struct
{
    const char *name;
    uint8_t op, arg, min_args, max_args;
} function;

static const function FUNCTIONS[] = {
    {"sin", OP_FN1, 0, 1, 1},
    {"cos", OP_FN1, 1, 1, 1},
    {"tan", OP_FN1, 2, 1, 1},
    {"asin", OP_FN1, 3, 1, 1},
    {"acos", OP_FN1, 4, 1, 1},
    {"atan", OP_FN1, 5, 1, 1},
    {"sqrt", OP_FN1, 6, 1, 1},
    {"exp", OP_FN1, 7, 1, 1},
    {"log10", OP_FN1, 8, 1, 1},
    {"sinh", OP_FN1, 9, 1, 1},
    {"cosh", OP_FN1, 10, 1, 1},
    {"tanh", OP_FN1, 11, 1, 1},
    {"log", OP_LOG, 0, 1, 2},
    {"atan2", OP_ATAN2, 0, 2, 2},
    {"floor", OP_FLOOR, 0, 1, 1},
    {"ceil", OP_CEIL, 0, 1, 1},
    {"int", OP_TRUNC, 0, 1, 1},
    {"round", OP_ROUND, 0, 1, 1},
    {"float", OP_NONE, 0, 1, 1},
    {"abs", OP_ABS, 0, 1, 1},
    {"min", OP_MIN, 0, 2, 255},
    {"max", OP_MAX, 0, 2, 255},
    {"pow", OP_POW, 0, 2, 2},
    {"degrees", OP_DEGREES, 0, 1, 1},
    {"radians", OP_RADIANS, 0, 1, 1},
    /* For callers whose own evaluator rejects every non-finite step (the
     * calculator); the plot tools never accept names starting with _. */
    {"_finite", OP_FINITE, 0, 1, 1},
};

/* ------------------------------------------------------------------------ */
/* Compiler: recursive descent over Python's grammar, emitting postfix code  */
/* ------------------------------------------------------------------------ */

enum
{
    K_END,
    K_NUM,
    K_NAME,
    K_PLUS,
    K_MINUS,
    K_STAR,
    K_SLASH,
    K_FLOORDIV,
    K_PERCENT,
    K_POW,
    K_LPAREN,
    K_RPAREN,
    K_COMMA,
    K_BAD
};

/* What Python would hold at run time: an int, a float, or either one
 * (min/max over both kinds, int ** int with an exponent of unknown sign). */
enum
{
    T_INT,
    T_FLOAT,
    T_EITHER
};

typedef struct
{
    uint8_t type;
    bool complex_risk;  /* a power that may be complex in Python */
    bool whole_literal; /* a non-negative integer literal */
    bool zero_sign;     /* may be -0 where Python has the int 0 (see below) */
} value;

/*
 * Python's ints have no negative zero. Where the compiler cannot tell whether
 * a value is an int (T_EITHER), -x, x*y, x//y and x%y may give -0.0 where
 * Python gives 0. Zeros of either sign compare, add and divide the same, so
 * only atan2 can turn that into a different value; such formulas are refused.
 */

typedef struct
{
    const char *text;
    int length, pos;
    int kind, start, len;
    bool integer;
} lexer;

typedef struct
{
    lexer lex;
    psf_program *p;
    const psf_options *o;
    int sp, nesting;
    psf_status status;
    int error_at;
} compiler;

static void fail(compiler *c, psf_status status)
{
    if (c->status == PSF_OK)
    {
        c->status = status;
        c->error_at = c->lex.start;
    }
}

static bool digit(char ch)
{
    return ch >= '0' && ch <= '9';
}

static bool name_char(char ch)
{
    return digit(ch) || (ch >= 'a' && ch <= 'z') || (ch >= 'A' && ch <= 'Z') || ch == '_';
}

/* digits [. digits] [e [+-] digits], at least one mantissa digit. Returns
 * 1 for an integer, 0 for a float, -1 when malformed. */
static int number_form(const char *s, int n)
{
    int i = 0, mantissa = 0;
    bool integer = true;
    while (i < n && digit(s[i]))
        i++, mantissa++;
    if (i < n && s[i] == '.')
    {
        integer = false;
        i++;
        while (i < n && digit(s[i]))
            i++, mantissa++;
    }
    if (mantissa == 0)
        return -1;
    if (i < n && (s[i] == 'e' || s[i] == 'E'))
    {
        integer = false;
        i++;
        if (i < n && (s[i] == '+' || s[i] == '-'))
            i++;
        const int first = i;
        while (i < n && digit(s[i]))
            i++;
        if (i == first)
            return -1;
    }
    return i == n ? (integer ? 1 : 0) : -1;
}

static void next(compiler *c)
{
    lexer *l = &c->lex;
    while (l->pos < l->length && (l->text[l->pos] == ' ' || l->text[l->pos] == '\t'))
        l->pos++;
    l->start = l->pos;
    l->len = 0;
    if (l->pos >= l->length)
    {
        l->kind = K_END;
        return;
    }
    const char ch = l->text[l->pos];
    if (digit(ch) || (ch == '.' && l->pos + 1 < l->length && digit(l->text[l->pos + 1])))
    {
        /* Take what MicroPython's lexer takes as one number, then check it. */
        int end = l->pos;
        while (end < l->length)
        {
            const char d = l->text[end];
            if ((d == 'e' || d == 'E') && end + 1 < l->length &&
                (l->text[end + 1] == '+' || l->text[end + 1] == '-'))
                end += 2;
            else if (name_char(d) || d == '.')
                end++;
            else
                break;
        }
        l->len = end - l->pos;
        l->pos = end;
        const int form = number_form(l->text + l->start, l->len);
        l->kind = form < 0 ? K_BAD : K_NUM;
        l->integer = form == 1;
        return;
    }
    if (name_char(ch))
    {
        int end = l->pos;
        while (end < l->length && name_char(l->text[end]))
            end++;
        l->len = end - l->pos;
        l->pos = end;
        l->kind = K_NAME;
        return;
    }
    const char after = l->pos + 1 < l->length ? l->text[l->pos + 1] : 0;
    l->len = 1;
    switch (ch)
    {
    case '+': l->kind = K_PLUS; break;
    case '-': l->kind = K_MINUS; break;
    case '%': l->kind = K_PERCENT; break;
    case '(': l->kind = K_LPAREN; break;
    case ')': l->kind = K_RPAREN; break;
    case ',': l->kind = K_COMMA; break;
    case '*':
        l->kind = after == '*' ? K_POW : K_STAR;
        l->len = after == '*' ? 2 : 1;
        break;
    case '/':
        l->kind = after == '/' ? K_FLOORDIV : K_SLASH;
        l->len = after == '/' ? 2 : 1;
        break;
    default: l->kind = K_BAD; break;
    }
    l->pos += l->len;
}

static bool is_name(const compiler *c, const char *name)
{
    const size_t n = strlen(name);
    return n == (size_t)c->lex.len && memcmp(c->lex.text + c->lex.start, name, n) == 0;
}

static void emit(compiler *c, int byte)
{
    psf_program *p = c->p;
    if (p->length >= PSF_MAX_CODE)
        fail(c, PSF_ERR_TOO_LONG);
    else
        p->code[p->length++] = (uint8_t)byte;
}

/* Track the stack: delta values pushed (negative: popped). */
static void stack(compiler *c, int delta)
{
    c->sp += delta;
    if (c->sp >= PSF_MAX_STACK)
        fail(c, PSF_ERR_TOO_LONG);
    else if (c->sp + 1 > c->p->depth)
        c->p->depth = (uint8_t)(c->sp + 1);
}

static void push_constant(compiler *c, float v)
{
    psf_program *p = c->p;
    int k = 0;
    while (k < p->constant_count && memcmp(&p->constant[k], &v, sizeof v) != 0)
        k++;
    if (k == p->constant_count)
    {
        if (k >= PSF_MAX_CONSTANTS)
        {
            fail(c, PSF_ERR_TOO_LONG);
            return;
        }
        p->constant[p->constant_count++] = v;
    }
    emit(c, OP_CONST);
    emit(c, k);
    stack(c, 1);
}

static uint8_t mixed(uint8_t a, uint8_t b)
{
    if (a == T_FLOAT || b == T_FLOAT)
        return T_FLOAT;
    return a == T_INT && b == T_INT ? T_INT : T_EITHER;
}

static value arith(compiler *c);
static value factor(compiler *c);

/* a ** b, from the operator or pow(a, b). */
static value power_of(compiler *c, value a, value b)
{
    emit(c, OP_POW);
    stack(c, -1);
    value v = {T_FLOAT, a.complex_risk || b.complex_risk || b.type != T_INT, false, a.zero_sign || b.zero_sign};
    if (a.type == T_INT && b.type == T_INT)
        v.type = b.whole_literal ? T_INT : T_EITHER;
    else if (a.type != T_FLOAT && b.type != T_FLOAT)
        v.type = T_EITHER;
    return v;
}

static value call(compiler *c, const function *f)
{
    value result = {T_FLOAT, false, false, false};
    next(c); /* ( */
    if (c->lex.kind == K_RPAREN)
    {
        fail(c, PSF_ERR_ARGUMENTS);
        return result;
    }
    value args[2];
    int count = 0;
    bool all_int = true, all_float = true, zero_sign = false;
    for (;;)
    {
        const value v = arith(c);
        if (c->status != PSF_OK)
            return result;
        if (count < 2)
            args[count] = v;
        count++;
        all_int = all_int && v.type == T_INT;
        all_float = all_float && v.type == T_FLOAT;
        zero_sign = zero_sign || v.zero_sign;
        if (c->lex.kind != K_COMMA)
            break;
        next(c);
    }
    if (c->lex.kind != K_RPAREN)
    {
        fail(c, PSF_ERR_SYNTAX);
        return result;
    }
    next(c);
    if (count < f->min_args || count > f->max_args)
    {
        fail(c, PSF_ERR_ARGUMENTS);
        return result;
    }
    switch (f->op)
    {
    case OP_FN1:
        emit(c, OP_FN1);
        emit(c, f->arg);
        result.zero_sign = zero_sign;
        break;
    case OP_LOG:
        emit(c, count == 2 ? OP_LOGB : OP_LOG);
        stack(c, 1 - count);
        break;
    case OP_ATAN2:
        if (zero_sign)
            fail(c, PSF_ERR_UNSUPPORTED);
        emit(c, OP_ATAN2);
        stack(c, -1);
        break;
    case OP_FLOOR:
    case OP_CEIL:
        emit(c, f->op);
        result.type = T_INT;
        break;
    case OP_TRUNC:
    case OP_ROUND:
        /* int() and round() return an int argument unchanged. */
        if (args[0].type != T_INT)
            emit(c, f->op);
        result.type = T_INT;
        break;
    case OP_NONE:
        result.zero_sign = zero_sign;
        break;
    case OP_FINITE:
        emit(c, OP_FINITE);
        result = args[0];
        result.whole_literal = false;
        break;
    case OP_ABS:
        /* abs() of a complex power is real in Python; not reproducible here. */
        if (args[0].complex_risk)
            fail(c, PSF_ERR_UNSUPPORTED);
        emit(c, OP_ABS);
        result.type = args[0].type;
        break;
    case OP_MIN:
    case OP_MAX:
        emit(c, f->op);
        emit(c, count);
        stack(c, 1 - count);
        result.type = all_int ? T_INT : all_float ? T_FLOAT : T_EITHER;
        result.zero_sign = zero_sign;
        break;
    case OP_POW:
        result = power_of(c, args[0], args[1]);
        break;
    default: /* degrees, radians */
        emit(c, f->op);
        result.zero_sign = zero_sign;
        break;
    }
    return result;
}

static value name(compiler *c)
{
    value v = {T_FLOAT, false, false, false};
    const psf_options *o = c->o;
    const lexer at = c->lex;
    next(c);
    const bool called = c->lex.kind == K_LPAREN;
    lexer here = c->lex;
    c->lex = at;
    for (int k = 0; k < o->variable_count; k++)
        if (is_name(c, o->variables[k]))
        {
            c->lex = here;
            if (called)
                fail(c, PSF_ERR_NAME);
            emit(c, OP_VAR);
            emit(c, k);
            stack(c, 1);
            return v;
        }
    for (int k = 0; k < o->derived_count; k++)
        if (is_name(c, o->derived_names[k]))
        {
            if (called || ++c->nesting > PSF_MAX_NESTING)
            {
                c->lex = here;
                fail(c, called ? PSF_ERR_NAME : PSF_ERR_TOO_LONG);
                return v;
            }
            /* Compile the definition in place, then continue after the name. */
            lexer inner = {o->derived_texts[k], (int)strlen(o->derived_texts[k]), 0, K_END, 0, 0, false};
            c->lex = inner;
            next(c);
            v = arith(c);
            if (c->lex.kind != K_END)
                fail(c, PSF_ERR_SYNTAX);
            c->nesting--;
            c->lex = here;
            return v;
        }
    for (int k = 0; k < o->constant_count; k++)
        if (is_name(c, o->constant_names[k]))
        {
            c->lex = here;
            if (called)
                fail(c, PSF_ERR_NAME);
            push_constant(c, o->constant_values[k]);
            return v;
        }
    for (size_t k = 0; k < sizeof FUNCTIONS / sizeof FUNCTIONS[0]; k++)
        if (is_name(c, FUNCTIONS[k].name))
        {
            c->lex = here;
            if (!called)
            {
                fail(c, PSF_ERR_NAME);
                return v;
            }
            return call(c, &FUNCTIONS[k]);
        }
    fail(c, PSF_ERR_NAME);
    c->lex = here;
    return v;
}

static value atom(compiler *c)
{
    value v = {T_FLOAT, false, false, false};
    switch (c->lex.kind)
    {
    case K_NUM:
        v.type = c->lex.integer ? T_INT : T_FLOAT;
        v.whole_literal = c->lex.integer;
        push_constant(c, c->o->number(c->lex.text + c->lex.start, c->lex.len, c->lex.integer, c->o->context));
        next(c);
        return v;
    case K_NAME:
        return name(c);
    case K_LPAREN:
        next(c);
        v = arith(c);
        v.whole_literal = false;
        if (c->lex.kind != K_RPAREN)
            fail(c, PSF_ERR_SYNTAX);
        next(c);
        return v;
    default:
        fail(c, PSF_ERR_SYNTAX);
        return v;
    }
}

/* power: atom ['**' factor]  (right-associative, binds tighter than unary -) */
static value power(compiler *c)
{
    const value a = atom(c);
    if (c->status != PSF_OK || c->lex.kind != K_POW)
        return a;
    next(c);
    const value b = factor(c);
    return power_of(c, a, b);
}

/* factor: ('+' | '-') factor | power */
static value factor(compiler *c)
{
    if (++c->nesting > PSF_MAX_NESTING)
    {
        fail(c, PSF_ERR_TOO_LONG);
        return (value){T_FLOAT, false, false, false};
    }
    value v;
    if (c->lex.kind == K_MINUS || c->lex.kind == K_PLUS)
    {
        const bool negate = c->lex.kind == K_MINUS;
        next(c);
        v = factor(c);
        v.whole_literal = v.whole_literal && !negate;
        if (negate)
        {
            emit(c, OP_NEG);
            if (v.type == T_INT)
                emit(c, OP_ZERO);
            v.zero_sign = v.zero_sign || v.type == T_EITHER;
        }
    }
    else
        v = power(c);
    c->nesting--;
    return v;
}

/* term: factor (('*' | '/' | '//' | '%') factor)* */
static value term(compiler *c)
{
    value a = factor(c);
    while (c->status == PSF_OK && (c->lex.kind == K_STAR || c->lex.kind == K_SLASH ||
                                   c->lex.kind == K_FLOORDIV || c->lex.kind == K_PERCENT))
    {
        const int kind = c->lex.kind;
        next(c);
        const value b = factor(c);
        const uint8_t type = mixed(a.type, b.type);
        emit(c, kind == K_STAR ? OP_MUL : kind == K_SLASH ? OP_DIV : kind == K_FLOORDIV ? OP_FLOORDIV : OP_MOD);
        stack(c, -1);
        a.type = kind == K_SLASH ? T_FLOAT : type;
        if (a.type == T_INT)
            emit(c, OP_ZERO);
        a.complex_risk = a.complex_risk || b.complex_risk;
        /* % takes the divisor's sign for a zero result, dropping the dividend's. */
        a.zero_sign = (kind == K_PERCENT ? false : a.zero_sign || b.zero_sign) || a.type == T_EITHER;
        a.whole_literal = false;
    }
    return a;
}

/* arith: term (('+' | '-') term)* */
static value arith(compiler *c)
{
    value a = term(c);
    while (c->status == PSF_OK && (c->lex.kind == K_PLUS || c->lex.kind == K_MINUS))
    {
        const bool add = c->lex.kind == K_PLUS;
        next(c);
        const value b = term(c);
        emit(c, add ? OP_ADD : OP_SUB);
        stack(c, -1);
        a.type = mixed(a.type, b.type);
        a.complex_risk = a.complex_risk || b.complex_risk;
        a.zero_sign = a.zero_sign || b.zero_sign;
        a.whole_literal = false;
    }
    return a;
}

psf_status psf_compile(psf_program *p, const char *text, int length, const psf_options *o, int *error_at)
{
    memset(p, 0, sizeof *p);
    compiler c;
    memset(&c, 0, sizeof c);
    c.lex.text = text;
    c.lex.length = length;
    c.p = p;
    c.o = o;
    c.sp = -1;
    if (o->variable_count > PSF_MAX_VARIABLES)
        fail(&c, PSF_ERR_TOO_LONG);
    p->variable_count = (uint8_t)o->variable_count;
    p->pow_fix_nan = o->pow_fix_nan;
    p->atan2_fix_infnan = o->atan2_fix_infnan;
    next(&c);
    if (c.status == PSF_OK)
        arith(&c);
    if (c.status == PSF_OK && c.lex.kind != K_END)
        fail(&c, PSF_ERR_SYNTAX);
    emit(&c, OP_END);
    if (c.status == PSF_OK && c.sp != 0)
        fail(&c, PSF_ERR_SYNTAX);
    if (error_at)
        *error_at = c.error_at;
    return c.status;
}

size_t psf_scratch_bytes(const psf_program *p)
{
    return (size_t)p->depth * PSF_BLOCK * sizeof(float) + PSF_BLOCK;
}

/* ------------------------------------------------------------------------ */
/* Evaluation: each operation runs over a block of points                     */
/* ------------------------------------------------------------------------ */

/* MicroPython's math_generic_1/2: a NaN or infinity from ordinary inputs
 * raises "math domain error". */
static inline bool raises1(float x, float r)
{
    return (isnan(r) && !isnan(x)) || (isinf(r) && !isinf(x));
}

static inline bool raises2(float x, float y, float r)
{
    return (isnan(r) && !isnan(x) && !isnan(y)) || (isinf(r) && !isinf(x) && !isinf(y));
}

/* Python's float % (objfloat.c). */
static inline float py_mod(float x, float y)
{
    float m = fmodf(x, y);
    if (m == 0.0f)
        m = copysignf(0.0f, y);
    else if ((m < 0.0f) != (y < 0.0f))
        m += y;
    return m;
}

/* Python's float // (mp_obj_float_divmod). */
static inline float py_floordiv(float x, float y)
{
    const float m = fmodf(x, y);
    float div = (x - m) / y;
    if (m != 0.0f && (m < 0.0f) != (y < 0.0f))
        div -= 1.0f;
    if (div == 0.0f)
        return copysignf(0.0f, x / y);
    float f = floorf(div);
    if (div - f > 0.5f)
        f += 1.0f;
    return f;
}

/* Python's float ** (objfloat.c); err for ZeroDivisionError or a complex result. */
static inline float py_pow(float x, float y, bool fix_nan, uint8_t *err)
{
    if (x == 0.0f && y < 0.0f && !isinf(y))
        *err = 1;
    else if (x < 0.0f && y != floorf(y) && !isnan(y))
        *err = 1;
    else if (fix_nan && (x == 1.0f || y == 0.0f))
        return 1.0f;
    else if (fix_nan && isnan(y))
        return y;
    return powf(x, y);
}

static inline float whole(float x)
{
    return x == 0.0f ? 0.0f : x;
}

#define LANES for (int i = 0; i < n; i++)
#define AT(k) (stack + (k) * PSF_BLOCK)

int PS_HOT(psf_eval)(const psf_program *p, const psf_input *inputs, int count, float limit, float *out,
                     void *scratch)
{
    float *stack = scratch;
    uint8_t *err = (uint8_t *)(stack + p->depth * PSF_BLOCK);
    const uint8_t *code = p->code;
    int kept = 0;
    for (int base = 0; base < count; base += PSF_BLOCK)
    {
        const int n = count - base < PSF_BLOCK ? count - base : PSF_BLOCK;
        memset(err, 0, (size_t)n);
        int sp = -1;
        for (int pc = 0;;)
        {
            const int op = code[pc++];
            if (op == OP_END)
                break;
            float *a = sp >= 1 ? AT(sp - 1) : NULL, *b = sp >= 0 ? AT(sp) : NULL;
            switch (op)
            {
            case OP_VAR:
            {
                const psf_input *in = &inputs[code[pc++]];
                float *d = AT(++sp);
                if (in->data == NULL)
                    LANES d[i] = in->value;
                else if (in->stride == 1)
                    memcpy(d, in->data + base, (size_t)n * sizeof(float));
                else
                {
                    const float *s = in->data + (ptrdiff_t)base * in->stride;
                    LANES d[i] = s[(ptrdiff_t)i * in->stride];
                }
                break;
            }
            case OP_CONST:
            {
                const float v = p->constant[code[pc++]];
                float *d = AT(++sp);
                LANES d[i] = v;
                break;
            }
            case OP_NEG: LANES b[i] = -b[i]; break;
            case OP_ZERO: LANES b[i] = whole(b[i]); break;
            case OP_ADD: LANES a[i] += b[i]; sp--; break;
            case OP_SUB: LANES a[i] -= b[i]; sp--; break;
            case OP_MUL: LANES a[i] *= b[i]; sp--; break;
            case OP_DIV:
                LANES
                {
                    err[i] |= b[i] == 0.0f;
                    a[i] /= b[i];
                }
                sp--;
                break;
            case OP_FLOORDIV:
                LANES
                {
                    err[i] |= b[i] == 0.0f;
                    a[i] = py_floordiv(a[i], b[i]);
                }
                sp--;
                break;
            case OP_MOD:
                LANES
                {
                    err[i] |= b[i] == 0.0f;
                    a[i] = py_mod(a[i], b[i]);
                }
                sp--;
                break;
            case OP_POW:
                LANES a[i] = py_pow(a[i], b[i], p->pow_fix_nan, &err[i]);
                sp--;
                break;
            case OP_ABS: LANES b[i] = signbit(b[i]) ? -b[i] : b[i]; break;
            case OP_FN1:
            {
                float (*const f)(float) = FN1[code[pc++]];
                LANES
                {
                    const float x = b[i], r = f(x);
                    err[i] |= raises1(x, r);
                    b[i] = r;
                }
                break;
            }
            case OP_LOG:
                LANES
                {
                    err[i] |= b[i] <= 0.0f;
                    b[i] = logf(b[i]);
                }
                break;
            case OP_LOGB:
                LANES
                {
                    err[i] |= a[i] <= 0.0f || b[i] <= 0.0f || b[i] == 1.0f;
                    a[i] = logf(a[i]) / logf(b[i]);
                }
                sp--;
                break;
            case OP_ATAN2:
                LANES
                {
                    const float y = a[i], x = b[i];
                    float r;
                    if (p->atan2_fix_infnan && isinf(y) && isinf(x))
                        r = copysignf(x < 0.0f ? 3.0f * PSF_PI / 4.0f : PSF_PI / 4.0f, y);
                    else
                        r = atan2f(y, x);
                    err[i] |= raises2(y, x, r);
                    a[i] = r;
                }
                sp--;
                break;
            /* Python returns ints here; converting inf or NaN raises. */
            case OP_FLOOR:
                LANES
                {
                    err[i] |= !isfinite(b[i]);
                    b[i] = whole(floorf(b[i]));
                }
                break;
            case OP_CEIL:
                LANES
                {
                    err[i] |= !isfinite(b[i]);
                    b[i] = whole(ceilf(b[i]));
                }
                break;
            case OP_TRUNC:
                LANES
                {
                    err[i] |= !isfinite(b[i]);
                    b[i] = whole(truncf(b[i]));
                }
                break;
            case OP_ROUND:
                LANES
                {
                    err[i] |= !isfinite(b[i]);
                    b[i] = whole(nearbyintf(b[i]));
                }
                break;
            case OP_DEGREES: LANES b[i] *= 180.0f / PSF_PI; break;
            case OP_RADIANS: LANES b[i] *= PSF_PI / 180.0f; break;
            case OP_MIN:
            case OP_MAX:
            {
                /* Python's chain: keep the first, replace when strictly beyond. */
                const int k = code[pc++];
                float *best = AT(sp - k + 1);
                for (int j = 1; j < k; j++)
                {
                    const float *v = AT(sp - k + 1 + j);
                    if (op == OP_MAX)
                        LANES best[i] = v[i] > best[i] ? v[i] : best[i];
                    else
                        LANES best[i] = v[i] < best[i] ? v[i] : best[i];
                }
                sp -= k - 1;
                break;
            }
            case OP_FINITE: LANES err[i] |= !isfinite(b[i]); break;
            default: break; /* OP_NONE */
            }
        }
        const float *r = AT(0);
        float *o = out + base;
        LANES
        {
            float v = err[i] ? NAN : r[i];
            if (isfinite(v) && fabsf(v) <= limit)
                kept++;
            else
                v = NAN;
            o[i] = v;
        }
    }
    return kept;
}
