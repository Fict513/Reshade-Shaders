// HDR Bloom 1.0.0 -- original implementation, MIT license.
// Scalar production functions are also compiled unchanged by tests/math_bridge.cpp.
#ifndef HDR_BLOOM_MATH
#define HDR_BLOOM_MATH
float HB_PQDecode(float v)
{
    float p = pow(v, 1.0f / 78.84375f);
    return 10000.0f * pow(max(p - 0.8359375f, 0.0f) /
                         (18.8515625f - 18.6875f * p), 1.0f / 0.1593017578125f);
}
float HB_PQEncode(float n)
{
    float p = pow(n / 10000.0f, 0.1593017578125f);
    return pow((0.8359375f + 18.8515625f * p) / (1.0f + 18.6875f * p), 78.84375f);
}
float HB_SRGBDecode(float v)
{
    if (v <= 0.04045f) return v / 12.92f;
    return pow((v + 0.055f) / 1.055f, 2.4f);
}
float HB_SRGBEncode(float v)
{
    if (v <= 0.0031308f) return 12.92f * v;
    return 1.055f * pow(v, 1.0f / 2.4f) - 0.055f;
}
// k is the FULL knee width; onset T-k/2, linear excess begins T+k/2.
// k is restricted to [0,2T], so the extracted fraction never exceeds 1.
float HB_Fraction(float y, float t, float k)
{
    if (y <= 0.0f) return 0.0f;
    k = min(max(k, 0.0f), 2.0f * t);
    float e = max(y - t, 0.0f);
    if (k > 0.0f && y < t + 0.5f * k)
    {
        float u = max(y - (t - 0.5f * k), 0.0f) / k;
        e = 0.5f * k * u * u;
    }
    return min(e / y, 1.0f);
}
// Largest admissible fraction of an RGB increment; one shared fraction is
// selected across components. This is a line-segment limiter, not channel clipping.
float HB_ChannelLimit(float source, float delta, float upper)
{
    if (delta > 0.0f && delta > upper - source) return (upper - source) / delta;
    if (delta < 0.0f && -delta > source) return source / (-delta);
    return 1.0f;
}
#endif
