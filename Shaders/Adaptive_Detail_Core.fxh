// Adaptive Detail 1.0.0 -- original implementation, MIT (see LICENSE.txt).
// Scalar production core; also compiled verbatim into the CPU validation adapter.
#ifndef ADAPTIVE_DETAIL_CORE
#define ADAPTIVE_DETAIL_CORE
float AD_SRGBDecode(float x) { return x <= 0.04045f ? x / 12.92f : pow((x + 0.055f) / 1.055f, 2.4f); }
float AD_SRGBEncode(float x) { return x <= 0.0031308f ? 12.92f * x : 1.055f * pow(x, 1.0f / 2.4f) - 0.055f; }
float AD_PQDecodeNits(float x)
{
    float p = pow(x, 1.0f / 78.84375f);
    return 10000.0f * pow(max(p - 0.8359375f, 0.0f) / (18.8515625f - 18.6875f * p), 1.0f / 0.1593017578125f);
}
float AD_PQEncodeNits(float x)
{
    float p = pow(max(x, 0.0f) / 10000.0f, 0.1593017578125f);
    return pow((0.8359375f + 18.8515625f * p) / (1.0f + 18.6875f * p), 78.84375f);
}
float AD_Decode(float x, int contract)
{
    if (contract == 1) return AD_SRGBDecode(x);
    if (contract == 2) return AD_PQDecodeNits(x) / 80.0f;
    return x;
}
float AD_Encode(float x, int contract)
{
    if (contract == 1) return AD_SRGBEncode(x);
    if (contract == 2) return AD_PQEncodeNits(x * 80.0f);
    return x;
}
float AD_Y(float r, float g, float b, int contract)
{
    // Difference form preserves equal RGB exactly, unlike an approximate sum of weights.
    if (contract == 2) return g + 0.2627f * (r - g) + 0.0593f * (b - g);
    return g + 0.2126f * (r - g) + 0.0722f * (b - g);
}
bool AD_Valid(float x, int contract)
{
    if (contract == 3) return x >= -1.0e18f && x <= 1.0e18f;
    return x >= 0.0f && x <= 1.0f;
}
struct ADNeighborhood
{
    float c; float n; float s; float e; float w;
    float nw; float ne; float sw; float se;
    float broadDelta;
};
struct ADResult { float delta; float effective; float limiter; };
ADResult AD_Correction(ADNeighborhood p, float master, float fine, float detail, float edge, float noise, float upGain)
{
    ADResult o; o.delta = 0.0f; o.effective = 0.0f; o.limiter = 0.0f;
    if (p.c <= 0.0f) return o;
    float lo = min(p.c, min(min(min(p.n,p.s),min(p.e,p.w)),min(min(p.nw,p.ne),min(p.sw,p.se))));
    float hi = max(p.c, max(max(max(p.n,p.s),max(p.e,p.w)),max(max(p.nw,p.ne),max(p.sw,p.se))));
    float span = hi - lo;
    if (span == 0.0f) return o;
    float bd = (2.0f * ((p.n-p.c)+(p.s-p.c)+(p.e-p.c)+(p.w-p.c)) +
        ((p.nw-p.c)+(p.ne-p.c)+(p.sw-p.c)+(p.se-p.c))) / 16.0f;
    float base = p.c + bd;
    float scale = max(abs(p.c),abs(base)) + 0.01f;
    // Avoid overflow if unusually large signed RGB nearly cancels in Y.
    float contrast = min(span / scale, 1.0e10f);
    float edgeGate = 1.0f / (1.0f + 12.0f * edge * contrast * contrast);
    float variation = abs(p.n-p.c)+abs(p.s-p.c)+abs(p.e-p.c)+abs(p.w-p.c) +
        0.5f*(abs(p.nw-p.c)+abs(p.ne-p.c)+abs(p.sw-p.c)+abs(p.se-p.c));
    float coherent = saturate((abs(p.e-p.w)+abs(p.n-p.s)+
        0.5f*(abs(p.ne-p.sw)+abs(p.nw-p.se))) / max(variation,1.0e-20f));
    float signalGate = span / (span + noise * 0.04f * scale);
    float noiseGate = (1.0f - noise * 0.9f * (1.0f-coherent)) * signalGate;
    // No shadow blur: only the correction fades toward zero.
    float blackGate = p.c / (p.c + 0.002f);
    float gate = edgeGate * noiseGate * blackGate;
    float raw = master * gate * (-fine * bd + detail * (bd-p.broadDelta));
    o.effective = master * gate;
    // A single budget for BOTH bands. Extrema relaxation vanishes at maximum protection.
    float extension = (1.0f-edge) * 0.02f * span;
    float room = raw >= 0.0f ? hi-p.c+extension : p.c-lo+extension;
    float budget = min(0.12f * span, max(room,0.0f));
    budget = min(budget, p.c * (raw >= 0.0f ? min(0.12f,max(upGain,0.0f)) : 0.12f));
    // Smooth asymptotic saturation, with no hard RGB clipping.
    if (budget > 0.0f) o.delta = raw * (budget / (budget + abs(raw)));
    // Regularize the diagnostic near zero requests; avoid subtracting almost-equal ratios.
    if (raw != 0.0f) o.limiter = (abs(raw) / (budget + abs(raw))) *
        (abs(raw) / (abs(raw) + 0.001f * scale));
    return o;
}
#endif
