/*
Adaptive Clarity 1.0 - restrained SDR texture/edge sharpening for ReShade/GShade
Copyright (c) 2026 OpenAI. MIT license at end.

Install in your configured Shaders directory, reload, enable Adaptive Clarity.
Use after IPS Depth; disable IPS Depth's micro sharpening and other sharpeners
for the initial comparison. No includes, depth buffer, add-on or external asset.
SDR sRGB / Rec.709 only; declared HDR presentation spaces bypass processing.
Unknown spaces cannot be detected. This enhances existing detail, not missing
geometry, texture data, true resolution, or motion-vector-based reconstruction.

AC_QUALITY=0 Normal / 1 High / 2 Ultra: 4 / 8 / 16 wide-ring directions, plus
one common 3x3 neighborhood. All tiers keep the same radii and user settings.
Two passes, one R32F intermediate (~18.9 MiB at 3440x1440). Nominal maximum
texture fetch count is 15 / 19 / 27 per output pixel across both passes when
texture processing is enabled. Estimates are not GPU benchmarks.
AC_HUD_MASKS=0 strips the manual rectangle math. Default=1. With Strength=0,
the final pass returns original, but the cache pass still executes. Disable
the technique for complete GPU-cost recovery. Known HDR uses one passthrough.

Algorithm: cache sRGB-encoded linear luminance in R32F; estimate a 2x2-cell
structure tensor from the 3x3 neighborhood; use coherence for separate texture
and edge gains. Directional and brightness weights restrain cross-edge mixing.
A bounded micro-detail term and a band between near/wide estimates sharpen
at two small spatial scales. Noise gates, high-frequency pattern attenuation,
local extrema and shadow/highlight headroom limit the correction. RGB is
reconstructed in linear light and projected into gamut only when necessary.

Noise and pattern detection are spatial heuristics, not semantic classification.
Masks are fixed screen rectangles, not automatic HUD detection. There is no
history, reprojection, frame-generation integration, dither, saturation boost,
or global tone curve. Real motion stability and GPU cost require game testing.
Original implementation; not AMD CAS and not asserted superior to CAS.
*/
#ifndef AC_QUALITY
#define AC_QUALITY 1
#endif
#ifndef AC_HUD_MASKS
#define AC_HUD_MASKS 1
#endif
#if AC_QUALITY <= 0
#define _AC_DIRECTIONS 4
#elif AC_QUALITY == 1
#define _AC_DIRECTIONS 8
#else
#define _AC_DIRECTIONS 16
#endif
#if defined(BUFFER_COLOR_SPACE) && BUFFER_COLOR_SPACE > 1
#define _AC_HDR 1
#else
#define _AC_HDR 0
#endif

namespace AdaptiveClarity
{
uniform float Strength <
    ui_type = "slider"; ui_label = "Overall strength"; ui_category = "1. Clarity";
    ui_min = 0.0; ui_max = 1.0; ui_step = 0.01;
    ui_tooltip = "Blend the correction with the original. Disable the technique for full GPU-cost recovery.";
> = 0.75;
uniform float TextureStrength <
    ui_type = "slider"; ui_label = "Texture strength"; ui_category = "1. Clarity";
    ui_min = 0.0; ui_max = 1.0; ui_step = 0.01;
    ui_tooltip = "Gain in less directional texture and in the small near-to-wide detail band. Raise gradually.";
> = 0.40;
uniform float EdgeStrength <
    ui_type = "slider"; ui_label = "Edge strength"; ui_category = "1. Clarity";
    ui_min = 0.0; ui_max = 0.75; ui_step = 0.01;
    ui_tooltip = "Gain near strongly directional edges. Keep below texture strength to limit outlines and brittle text.";
> = 0.15;
uniform float Radius <
    ui_type = "slider"; ui_label = "Detail radius (output pixels)"; ui_category = "1. Clarity";
    ui_min = 0.75; ui_max = 1.50; ui_step = 0.05;
    ui_tooltip = "Near samples use this radius, the wide ring uses 2x. Output pixels only; no DLSS render-resolution detection.";
> = 1.0;
uniform float NoiseThreshold <
    ui_type = "slider"; ui_label = "Noise threshold"; ui_category = "2. Protection";
    ui_min = 0.0; ui_max = 0.015; ui_step = 0.0005;
    ui_tooltip = "Gate small brightness differences. Higher values protect grain but may suppress subtle real detail.";
> = 0.0025;
uniform float NoiseProtection <
    ui_type = "slider"; ui_label = "Extra noise protection"; ui_category = "2. Protection";
    ui_min = 0.0; ui_max = 1.0; ui_step = 0.01;
    ui_tooltip = "Raises the noise gate in less directional neighborhoods. This does not denoise the input.";
> = 0.65;
uniform float DirectionProtection <
    ui_type = "slider"; ui_label = "Cross-edge protection"; ui_category = "2. Protection";
    ui_min = 0.0; ui_max = 1.0; ui_step = 0.01;
    ui_tooltip = "Weights samples along an edge more strongly than samples across it.";
> = 0.80;
uniform float PatternProtection <
    ui_type = "slider"; ui_label = "Fine-pattern protection"; ui_category = "2. Protection";
    ui_min = 0.0; ui_max = 1.0; ui_step = 0.01;
    ui_tooltip = "Attenuates checker-like patterns near the pixel grid; may also weaken some genuine fine textures.";
> = 0.70;
uniform float RingingProtection <
    ui_type = "slider"; ui_label = "Ringing protection"; ui_category = "2. Protection";
    ui_min = 0.0; ui_max = 1.0; ui_step = 0.01;
    ui_tooltip = "Tightens permitted extrema overshoot beside coherent edges.";
> = 0.85;
uniform float Overshoot <
    ui_type = "slider"; ui_label = "Permitted overshoot"; ui_category = "2. Protection";
    ui_min = 0.0; ui_max = 0.10; ui_step = 0.005;
    ui_tooltip = "Fraction of the original 3x3 brightness range allowed beyond its extrema. Zero is strict local clipping.";
> = 0.03;
uniform float MaxCorrection <
    ui_type = "slider"; ui_label = "Maximum correction"; ui_category = "2. Protection";
    ui_min = 0.005; ui_max = 0.060; ui_step = 0.001;
    ui_tooltip = "Soft bound in encoded luminance before strength, local extrema and endpoint protection.";
> = 0.025;
uniform bool Mask1Enabled <
    ui_label = "Protect HUD rectangle 1"; ui_category = "3. HUD rectangles";
> = false;
uniform float4 Mask1Rect <
    ui_type = "slider"; ui_label = "Rectangle 1: left, top, right, bottom"; ui_category = "3. HUD rectangles";
    ui_min = 0.0; ui_max = 1.0; ui_step = 0.001;
    ui_tooltip = "Normalized screen coordinates, top-left origin. Enable the HUD mask view to position it. Requires AC_HUD_MASKS=1.";
> = float4(0.0, 0.82, 0.35, 1.0);
uniform bool Mask2Enabled <
    ui_label = "Protect HUD rectangle 2"; ui_category = "3. HUD rectangles";
> = false;
uniform float4 Mask2Rect <
    ui_type = "slider"; ui_label = "Rectangle 2: left, top, right, bottom"; ui_category = "3. HUD rectangles";
    ui_min = 0.0; ui_max = 1.0; ui_step = 0.001;
> = float4(0.65, 0.82, 1.0, 1.0);
uniform float MaskFeather <
    ui_type = "slider"; ui_label = "HUD feather (output pixels)"; ui_category = "3. HUD rectangles";
    ui_min = 0.0; ui_max = 48.0; ui_step = 1.0;
    ui_tooltip = "Protection is complete inside each rectangle and fades outside it. Zero gives a hard boundary.";
> = 12.0;
uniform bool SplitView <
    ui_label = "Compare: original left / processed right"; ui_category = "4. Compare";
> = false;
uniform float SplitPosition <
    ui_type = "slider"; ui_label = "Comparison position"; ui_category = "4. Compare";
    ui_min = 0.0; ui_max = 1.0; ui_step = 0.01;
> = 0.50;
uniform int View <
    ui_type = "combo"; ui_label = "View"; ui_category = "4. Compare";
    ui_items = "Final image\0Correction: gray is neutral\0Edge coherence\0HUD protection\0";
> = 0;

texture2D InputTexture : COLOR;
sampler2D InputSampler
{
    Texture = InputTexture; AddressU = CLAMP; AddressV = CLAMP;
    MinFilter = LINEAR; MagFilter = LINEAR; MipFilter = POINT; SRGBTexture = false;
};
#if !_AC_HDR
texture2D GuideTexture { Width = BUFFER_WIDTH; Height = BUFFER_HEIGHT; Format = R32F; };
sampler2D GuideSampler
{
    Texture = GuideTexture; AddressU = CLAMP; AddressV = CLAMP;
    MinFilter = LINEAR; MagFilter = LINEAR; MipFilter = POINT; SRGBTexture = false;
};
#endif
float Decode(float c) { return c <= 0.04045 ? c / 12.92 : pow((c + 0.055) / 1.055, 2.4); }
float Encode(float c) { return c <= 0.0031308 ? c * 12.92 : 1.055 * pow(max(c, 0.0), 1.0 / 2.4) - 0.055; }
float3 DecodeRGB(float3 c) { return float3(Decode(c.r), Decode(c.g), Decode(c.b)); }
float3 EncodeRGB(float3 c) { return float3(Encode(c.r), Encode(c.g), Encode(c.b)); }
float Luma(float3 c) { return dot(c, float3(0.2126, 0.7152, 0.0722)); }
float3 ReconstructColor(float3 rgb, float y, float target)
{
    if (y <= 0.0) return float3(target, target, target);
    float3 chroma = rgb * (target / y) - target;
    float high = max(chroma.r, max(chroma.g, chroma.b));
    float low = min(chroma.r, min(chroma.g, chroma.b));
    float scale = 1.0;
    if (high > 0.0) scale = min(scale, (1.0 - target) / high);
    if (low < 0.0) scale = min(scale, target / (-low));
    return saturate(target + chroma * scale);
}
void VS(uint id : SV_VertexID, out float4 position : SV_Position, out float2 uv : TEXCOORD0)
{
    uv = float2(id == 2 ? 2.0 : 0.0, id == 1 ? 2.0 : 0.0);
    position = float4(uv * float2(2.0, -2.0) + float2(-1.0, 1.0), 0.0, 1.0);
}
float RectangleMask(float2 uv, float4 rect)
{
    float2 lo = min(rect.xy, rect.zw), hi = max(rect.xy, rect.zw);
    float2 outside = max(max(lo - uv, uv - hi), 0.0);
    float distance = length(outside * float2(BUFFER_WIDTH, BUFFER_HEIGHT));
    if (MaskFeather <= 0.0) return distance <= 0.0 ? 1.0 : 0.0;
    return 1.0 - smoothstep(0.0, MaskFeather, distance);
}
float HUDMask(float2 uv)
{
    float value = 0.0;
#if AC_HUD_MASKS
    if (Mask1Enabled) value = max(value, RectangleMask(uv, Mask1Rect));
    if (Mask2Enabled) value = max(value, RectangleMask(uv, Mask2Rect));
#endif
    return value;
}
#if !_AC_HDR
float ReadGuide(float2 uv) { return tex2D(GuideSampler, uv).r; }
float CacheGuide(float4 position : SV_Position, float2 uv : TEXCOORD0) : SV_Target
{ return Encode(Luma(DecodeRGB(saturate(tex2D(InputSampler, uv).rgb)))); }
// Coherence of four 2x2-cell gradient estimates, not a semantic edge detector.
float3 Structure(float a, float b, float c, float d, float e, float f, float g, float h, float i)
{
    float4 gx = 0.5 * float4(b-a+e-d, c-b+f-e, e-d+h-g, f-e+i-h);
    float4 gy = 0.5 * float4(d-a+e-b, e-b+f-c, g-d+h-e, h-e+i-f);
    float xx = dot(gx, gx), yy = dot(gy, gy), xy = dot(gx, gy);
    float trace = xx + yy;
    float anisotropy = sqrt(max((xx-yy)*(xx-yy) + 4.0*xy*xy, 0.0));
    float coherence = saturate(anisotropy / max(trace, 0.00000001));
    float lambda = 0.5 * (trace + anisotropy);
    float2 v = float2(xy, lambda - xx);
    if (dot(v,v) <= 0.000000000001) v = xx >= yy ? float2(1.0,0.0) : float2(0.0,1.0);
    v *= rsqrt(max(dot(v,v), 0.000000000001));
    return float3(v, coherence);
}
float SampleWeight(float value, float center, float2 direction, float3 structure)
{
    float alignment = dot(direction, structure.xy);
    float directional = lerp(1.0, 1.0 / (1.0 + 4.0 * alignment * alignment),
                             structure.z * DirectionProtection);
    float sigma = lerp(0.30, 0.06, DirectionProtection);
    float delta = (value - center) / sigma;
    return directional / (1.0 + delta * delta);
}
float NoiseGate(float delta, float coherence)
{
    float threshold = NoiseThreshold * (1.0 + NoiseProtection * (1.0 - coherence));
    return smoothstep(threshold, threshold + 0.006, abs(delta));
}
float SoftLimit(float delta) { return delta * MaxCorrection / (MaxCorrection + abs(delta)); }
#endif
float4 Composite(float4 position : SV_Position, float2 uv : TEXCOORD0) : SV_Target
{
    float4 original = tex2D(InputSampler, uv);
#if _AC_HDR
    return original;
#else
    if (Strength <= 0.0 || (SplitView && uv.x < SplitPosition)) return original;
    float protection = HUDMask(uv);
    if (View == 3) return float4(protection, protection, protection, original.a);
    if (protection >= 1.0) return original;
    if (TextureStrength <= 0.0 && EdgeStrength <= 0.0 && View == 0) return original;
    float2 texel = float2(BUFFER_RCP_WIDTH, BUFFER_RCP_HEIGHT) * Radius;
    float a = ReadGuide(uv + texel * float2(-1.0,-1.0));
    float b = ReadGuide(uv + texel * float2( 0.0,-1.0));
    float c = ReadGuide(uv + texel * float2( 1.0,-1.0));
    float d = ReadGuide(uv + texel * float2(-1.0, 0.0));
    float e = ReadGuide(uv);
    float f = ReadGuide(uv + texel * float2( 1.0, 0.0));
    float g = ReadGuide(uv + texel * float2(-1.0, 1.0));
    float h = ReadGuide(uv + texel * float2( 0.0, 1.0));
    float i = ReadGuide(uv + texel * float2( 1.0, 1.0));
    float3 structure = Structure(a,b,c,d,e,f,g,h,i);
    if (View == 2) return float4(structure.zzz, original.a);
    float lo = min(e,min(min(a,b),min(c,min(d,min(f,min(g,min(h,i)))))));
    float hi = max(e,max(max(a,b),max(c,max(d,max(f,max(g,max(h,i)))))));

    // Gaussian 3x3 spatial weights, modulated by orientation and brightness.
    float nearSum = 4.0 * e, nearWeight = 4.0;
    [unroll]
    for (int j = -1; j <= 1; ++j)
    {
        [unroll]
        for (int k = -1; k <= 1; ++k)
        {
            if (k != 0 || j != 0)
            {
                float value;
                if (j < 0) value = k < 0 ? a : (k == 0 ? b : c);
                else if (j == 0) value = k < 0 ? d : f;
                else value = k < 0 ? g : (k == 0 ? h : i);
                float2 dir = float2(k,j) * rsqrt(float(k*k+j*j));
                float spatial = (k == 0 || j == 0) ? 2.0 : 1.0;
                float weight = spatial * SampleWeight(value,e,dir,structure);
                nearSum += value * weight; nearWeight += weight;
            }
        }
    }
    float nearBase = nearSum / nearWeight;
    float fine = e - nearBase;
    float gain = lerp(TextureStrength, EdgeStrength, structure.z);
    float correction = gain * fine * NoiseGate(fine, structure.z);
    if (TextureStrength > 0.0)
    {
        // Uniform angular quadrature at radius 2*Radius. The center is included
        // to keep the broad estimate local even when all ring samples differ.
        float wideSum = e, wideWeight = 1.0;
        [unroll]
        for (int k = 0; k < _AC_DIRECTIONS; ++k)
        {
            float angle = 6.28318530718 * float(k) / float(_AC_DIRECTIONS);
            float2 dir = float2(cos(angle),sin(angle));
            float value = ReadGuide(uv + texel * dir * 2.0);
            float weight = SampleWeight(value,e,dir,structure) * (4.0 / float(_AC_DIRECTIONS));
            wideSum += value * weight; wideWeight += weight;
        }
        float band = nearBase - wideSum / wideWeight;
        correction += 0.5 * TextureStrength * (1.0 - 0.75 * structure.z)
                    * band * NoiseGate(band, structure.z);
    }

    float axialMean = 0.25 * (b+d+f+h);
    float diagonalMean = 0.25 * (a+c+g+i);
    float alternating = abs(e-axialMean) / max(abs(e-axialMean)+abs(e-diagonalMean),0.0000001);
    float pattern = smoothstep(0.60,0.90,alternating) * smoothstep(0.01,0.10,hi-lo);
    correction *= 1.0 - PatternProtection * pattern;
    correction = SoftLimit(correction);
    float margin = Overshoot * (hi-lo) * (1.0 - 0.8 * RingingProtection * structure.z);
    correction = clamp(correction,lo-margin-e,hi+margin-e);
    float endpoint = smoothstep(0.02,0.12,e) * (1.0-smoothstep(0.90,0.995,e));
    correction *= endpoint * Strength * (1.0-protection);
    if (View == 1) return float4(saturate(0.5+correction*12.0).xxx,original.a);
    if (correction == 0.0) return original;

    float3 rgb = DecodeRGB(saturate(original.rgb));
    float y = Luma(rgb);
    // Add the correction to a fresh full-precision center, so the cached guide
    // does not impose an output brightness change of its own.
    float target = Decode(saturate(Encode(y) + correction));
    float3 result = EncodeRGB(ReconstructColor(rgb,y,target));
    return float4(saturate(result),original.a);
#endif
}
}
technique Adaptive_Clarity <
    ui_label = "Adaptive Clarity";
    ui_tooltip = "SDR texture/edge sharpening. Start with other sharpeners disabled; no global tone/saturation grade.";
>
{
#if !_AC_HDR
    pass CacheBrightness
    {
        VertexShader = AdaptiveClarity::VS; PixelShader = AdaptiveClarity::CacheGuide;
        RenderTarget = AdaptiveClarity::GuideTexture; SRGBWriteEnable = false;
    }
#endif
    pass Sharpen
    {
        VertexShader = AdaptiveClarity::VS; PixelShader = AdaptiveClarity::Composite;
        SRGBWriteEnable = false;
    }
}
/*
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
*/
