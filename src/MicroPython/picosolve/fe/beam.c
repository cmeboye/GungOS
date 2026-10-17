#include "beam.h"

void ps_beam_stiffness(double ei, double length, double *k)
{
    const double l = length;
    const double c = ei / (l * l * l);
    const double t[16] = {
        12.0, 6.0 * l, -12.0, 6.0 * l,
        6.0 * l, 4.0 * l * l, -6.0 * l, 2.0 * l * l,
        -12.0, -6.0 * l, 12.0, -6.0 * l,
        6.0 * l, 2.0 * l * l, -6.0 * l, 4.0 * l * l};
    for (int i = 0; i < 16; i++)
        k[i] = c * t[i];
}

/* Hermite shape functions and their x-derivatives. */
static void shape(double length, double x, double *n, double *dn)
{
    const double l = length;
    const double s = x / l;
    const double s2 = s * s, s3 = s2 * s;
    n[0] = 1.0 - 3.0 * s2 + 2.0 * s3;
    n[1] = l * (s - 2.0 * s2 + s3);
    n[2] = 3.0 * s2 - 2.0 * s3;
    n[3] = l * (s3 - s2);
    dn[0] = (6.0 * s2 - 6.0 * s) / l;
    dn[1] = 1.0 - 4.0 * s + 3.0 * s2;
    dn[2] = (6.0 * s - 6.0 * s2) / l;
    dn[3] = 3.0 * s2 - 2.0 * s;
}

void ps_beam_load_vector(double length, const ps_beam_load *load, double *f)
{
    double n[4], dn[4];
    switch (load->kind)
    {
    case PS_BEAM_POINT:
        shape(length, load->a, n, dn);
        for (int i = 0; i < 4; i++)
            f[i] += load->w1 * n[i];
        break;
    case PS_BEAM_MOMENT:
        shape(length, load->a, n, dn);
        for (int i = 0; i < 4; i++)
            f[i] += load->w1 * dn[i];
        break;
    case PS_BEAM_TRAP:
    {
        /* Three-point Gauss is exact for a linear load times a cubic. */
        static const double node[3] = {-0.7745966692414834, 0.0, 0.7745966692414834};
        static const double weight[3] = {5.0 / 9.0, 8.0 / 9.0, 5.0 / 9.0};
        const double half = 0.5 * (load->b - load->a);
        const double mid = 0.5 * (load->b + load->a);
        for (int g = 0; g < 3; g++)
        {
            const double x = mid + half * node[g];
            const double w = load->w1 + (load->w2 - load->w1) * (0.5 + 0.5 * node[g]);
            shape(length, x, n, dn);
            for (int i = 0; i < 4; i++)
                f[i] += weight[g] * half * w * n[i];
        }
        break;
    }
    }
}

void ps_beam_section_start(double fy1, double m1, double x, ps_beam_section *s)
{
    s->shear = fy1;
    s->moment = fy1 * x - m1;
    s->slope_ei = fy1 * x * x / 2.0 - m1 * x;
    s->deflection_ei = fy1 * x * x * x / 6.0 - m1 * x * x / 2.0;
}

/*
 * Macaulay term c<x-a>^n of a line load (n = 0 or 1), integrated once for
 * shear, twice for moment, three and four times for EI slope and deflection.
 */
static void line_term(double c, double a, int n, double x, ps_beam_section *s)
{
    const double d = x - a;
    if (!(d > 0.0) || c == 0.0)
        return;
    double p = c;
    for (int i = 0; i <= n; i++)
        p *= d;
    /* p = c d^(n+1); each further integral multiplies by d / (order). */
    p /= (double)(n + 1);
    s->shear += p;
    p *= d / (double)(n + 2);
    s->moment += p;
    p *= d / (double)(n + 3);
    s->slope_ei += p;
    p *= d / (double)(n + 4);
    s->deflection_ei += p;
}

void ps_beam_section_add(const ps_beam_load *load, double x, ps_beam_section *s)
{
    const double d = x - load->a;
    switch (load->kind)
    {
    case PS_BEAM_POINT:
        if (d > 0.0)
        {
            s->shear += load->w1;
            s->moment += load->w1 * d;
            s->slope_ei += load->w1 * d * d / 2.0;
            s->deflection_ei += load->w1 * d * d * d / 6.0;
        }
        break;
    case PS_BEAM_MOMENT:
        if (d > 0.0)
        {
            s->moment -= load->w1;
            s->slope_ei -= load->w1 * d;
            s->deflection_ei -= load->w1 * d * d / 2.0;
        }
        break;
    case PS_BEAM_TRAP:
    {
        const double span = load->b - load->a;
        const double rise = span > 0.0 ? (load->w2 - load->w1) / span : 0.0;
        line_term(load->w1, load->a, 0, x, s);
        line_term(rise, load->a, 1, x, s);
        line_term(-load->w2, load->b, 0, x, s);
        line_term(-rise, load->b, 1, x, s);
        break;
    }
    }
}
