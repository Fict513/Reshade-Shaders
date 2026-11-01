// HDR IPS Enhance 1.0.1 -- original implementation, SPDX-License-Identifier: MIT
// Scalar functions are also compiled unchanged as C++ float code by the tests.
#ifndef _HDRIPS_MATH_INCLUDED
#define _HDRIPS_MATH_INCLUDED

// ST 2084 EOTF: normalized full-range PQ code -> cd/m^2.
// Caller validates 0 <= code <= 1. No sRGB transform is involved.
float HDRIPS_PQDecode(float code)
{
    float p = pow(code, 1.0 / 78.84375);
    float n = max(p - 0.8359375, 0.0);
    float d = max(0.1640625 + 18.6875 * (1.0 - p), 0.000001);
    return 10000.0 * pow(n / d, 1.0 / 0.1593017578125);
}

// Inverse EOTF: cd/m^2 -> normalized full-range PQ code.
// Physical PQ component domain is 0..10000 nits. Zero is encoded as code 0
// deliberately (rather than the negligible mathematical inverse-EOTF offset).
float HDRIPS_PQEncode(float nits)
{
    if (nits <= 0.0) return 0.0;
    float p = pow(nits / 10000.0, 0.1593017578125);
    // Equivalent ST 2084 ratio; avoids division of nearly equal large terms.
    // c2-c3 == 1-c1 == 0.1640625.
    float ratio = 1.0 - 0.1640625 * (1.0 - p) / (1.0 + 18.6875 * p);
    return pow(ratio, 78.84375);
}

// These thresholds are artistic processing thresholds, not panel measurements.
float HDRIPS_Toe(float protection)
{
    return exp2(-10.0 + 10.0 * protection);
}
float HDRIPS_HighEnd(float anchor, float protection)
{
    return min(10000.0, anchor * exp2(6.0 - 4.5 * protection));
}

// Piecewise cubic displacement in log2(nits). Anchored at toe, anchor, highEnd.
// For c in [0,.5], derivative in log space is >= 1-c/3 >= 5/6.
// Slope at toe/highEnd = 1, at anchor = 1+c; C1 throughout.
float HDRIPS_Global(float y, float c, float anchor, float shadow, float highlight)
{
    float toe = HDRIPS_Toe(shadow);
    float end = HDRIPS_HighEnd(anchor, highlight);
    if (c == 0.0 || y <= toe || y >= end || y == anchor) return y;
    float x = log2(y);
    float a = log2(anchor);
    float lo = log2(toe);
    float hi = log2(end);
    float t;
    float displacement;
    if (y < anchor)
    {
        t = (x - lo) / (a - lo);
        displacement = -c * (a - lo) * t * t * (1.0 - t);
    }
    else
    {
        t = (x - a) / (hi - a);
        displacement = c * (hi - a) * t * (1.0 - t) * (1.0 - t);
    }
    return y * exp2(displacement);
}

float HDRIPS_LocalGate(float y, float anchor, float shadow, float highlight)
{
    return smoothstep(HDRIPS_Toe(shadow), anchor * 0.25, y)
         * (1.0 - smoothstep(anchor, HDRIPS_HighEnd(anchor, highlight), y));
}

// Original-preserving smooth cap on an ADDED amount, never on source chroma.
// C1 knee at 50% of the available budget; asymptotically approaches the budget.
float HDRIPS_SoftBudget(float addition, float budget)
{
    if (addition <= 0.0 || budget <= 0.0) return 0.0;
    float knee = 0.5 * budget;
    if (addition <= knee) return addition;
    float d = addition - knee;
    return knee + (budget - knee) * d / (budget - knee + d);
}
#endif
