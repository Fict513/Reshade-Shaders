// HDR IPS Enhance 1.0.1 -- original implementation, SPDX-License-Identifier: MIT
// Requires ReShade FX with BUFFER_COLOR_SPACE support (5.1+; current 6.x preferred).
// See README.md for the injection contract. Does not infer encoding from bit depth.
// No third-party includes, depth buffer, native add-ons, LUTs or external textures.

#ifndef HDRIPS_QUALITY
    #define HDRIPS_QUALITY 1 // 0 Normal: 3x3; 1 High: 5x5; 2 Ultra: 7x7
#endif
#ifndef HDRIPS_ENABLE_LOCAL
    #define HDRIPS_ENABLE_LOCAL 1
#endif
#ifndef HDRIPS_ENABLE_COLOR
    #define HDRIPS_ENABLE_COLOR 1
#endif
#ifndef BUFFER_COLOR_SPACE
    #define BUFFER_COLOR_SPACE 0
#endif
#if HDRIPS_QUALITY < 0 || HDRIPS_QUALITY > 2
    #error HDRIPS_QUALITY must be 0, 1 or 2
#endif

#include "HDRIPS_Math.fxh"

uniform int InputColorSpace <
    ui_type = "combo";
    ui_label = "Input color space";
    #if BUFFER_COLOR_SPACE == 3
        ui_text = "Reported presentation: HDR10 PQ. Verify that COLOR is this final buffer before enabling Auto.";
    #elif BUFFER_COLOR_SPACE == 2
        ui_text = "Reported presentation: scRGB. Verify the 80-nit linear COLOR contract before enabling Auto.";
    #else
        ui_text = "Reported presentation is not supported HDR (unknown, SDR or HLG). Auto safely bypasses.";
    #endif
    ui_items = "Auto (requires verified injection)\0HDR10 PQ / BT.2020\0Linear scRGB / BT.709, 80 nit unit\0Bypass\0";
    ui_tooltip = "Select the encoding actually sampled by COLOR. Auto uses BUFFER_COLOR_SPACE only after the verification checkbox below. Unknown/sRGB/HLG bypass. Overrides are a contract, not a detector.";
> = 0;
uniform bool AutoContractVerified <
    ui_label = "Auto: sampled buffer contract verified";
    ui_tooltip = "Enable only after verifying COLOR is the final presentation buffer, with no add-on relocation or preceding encoding conversion. This effect cannot inspect an arbitrary game's render graph. Off safely bypasses Auto.";
> = false;
uniform float MasterStrength <
    ui_type = "slider"; ui_label = "Master strength"; ui_min = 0.0; ui_max = 1.0;
    ui_tooltip = "Linear-light blend of original and processed RGB. Zero directly returns the original sampled float4, including alpha; diagnostics also bypass.";
> = 0.75;
uniform float GlobalContrast <
    ui_type = "slider"; ui_label = "Global contrast"; ui_min = 0.0; ui_max = 0.5;
    ui_tooltip = "Monotonic anchored luminance shaping. Zero is neutral. Preserves the protected toe, chosen anchor, and high highlights. Start around 0.1.";
> = 0.12;
uniform float MidtoneAnchor <
    ui_type = "slider"; ui_label = "Midtone anchor (source nits)"; ui_min = 40.0; ui_max = 250.0; ui_units = " nits";
    ui_tooltip = "Artistic invariant point in decoded source luminance. Not measured panel brightness or a paper-white conversion. Match an important midtone, not necessarily the game's diffuse white.";
> = 100.0;
uniform float ShadowProtection <
    ui_type = "slider"; ui_label = "Shadow protection"; ui_min = 0.0; ui_max = 1.0;
    ui_tooltip = "Raises the untouched source-luminance toe from 0.000977 to 1 nit and suppresses local contrast there. Does not subtract the display black level. Higher protects more dark detail.";
> = 0.80;
uniform float HighlightProtection <
    ui_type = "slider"; ui_label = "Highlight protection"; ui_min = 0.0; ui_max = 1.0;
    ui_tooltip = "Returns tone changes to identity by anchor*2^(6-4.5*value), capped at 10000 source nits. Also reduces local/color changes in highlights. No display peak limiter or tone-mapping shoulder.";
> = 0.85;
#if HDRIPS_ENABLE_LOCAL
uniform float LocalContrast <
    ui_type = "slider"; ui_label = "Local contrast"; ui_min = 0.0; ui_max = 0.5;
    ui_tooltip = "Separate edge-aware log-luminance detail. Maximum correction is less than strength/2 stops, further masked in shadows/highlights and constrained to neighborhood extrema. Zero bypasses filtering; HDRIPS_ENABLE_LOCAL=0 removes its pass and R32F texture.";
> = 0.12;
uniform float LocalRadius <
    ui_type = "slider"; ui_label = "Local radius (render pixels)"; ui_min = 1.0; ui_max = 24.0; ui_units = " px";
    ui_tooltip = "Half-width of the square bilateral kernel in source render pixels. Same footprint and artistic strength in every quality tier; higher quality samples it more densely. Start at 6-10 pixels at 3440x1440.";
> = 8.0;
#endif
#if HDRIPS_ENABLE_COLOR
uniform float ColorEnhancement <
    ui_type = "slider"; ui_label = "Color enhancement"; ui_min = 0.0; ui_max = 0.3;
    ui_tooltip = "Luminance-preserving linear BT.2020 chroma expansion. Protects neutrals, dark noise, saturated colors and highlights. A P3-D65 proxy limits added color; it is not a measured monitor gamut. Existing extended scRGB is preserved.";
> = 0.06;
uniform float SaturationProtection <
    ui_type = "slider"; ui_label = "Saturation protection"; ui_min = 0.0; ui_max = 1.0;
    ui_tooltip = "Higher fades color enhancement earlier toward a P3-D65 boundary. Existing source color is never forcibly mapped into P3; there is no semantic skin detection.";
> = 0.85;
#endif
uniform int DiagnosticView <
    ui_type = "combo"; ui_label = "Diagnostic view";
    ui_items = "Off\0Original left / effect right\0Source luminance (nits)\0Signed luminance correction\0Protection / compression activity\0";
    ui_tooltip = "False color: <.01 black, .01-.1 violet, .1-1 blue, 1-10 cyan, 10-80 green, 80-203 yellow, 203-400 orange, 400-1000 red, >=1000 magenta. Signed: blue darker, orange brighter, gray unchanged; full scale .25 stop. Activity: R positive gain limited, G chroma addition limited, B highlight protection envelope. See README.";
> = 0;
uniform float SplitPosition <
    ui_type = "slider"; ui_label = "Split position"; ui_min = 0.0; ui_max = 1.0;
    ui_tooltip = "Original to the left, processed image to the right. No divider line modifies the source.";
> = 0.5;

texture2D HDRIPS_Source : COLOR;
sampler2D HDRIPS_SourceSampler
{
    Texture = HDRIPS_Source;
    MinFilter = POINT; MagFilter = POINT; MipFilter = POINT;
    AddressU = CLAMP; AddressV = CLAMP;
    SRGBTexture = false;
};

static const float3 HDRIPS_Y2020 = float3(0.2627, 0.6780, 0.0593);
static const float2 HDRIPS_Size = float2(BUFFER_WIDTH, BUFFER_HEIGHT);

int HDRIPS_Mode()
{
    if (InputColorSpace == 1 || InputColorSpace == 2) return InputColorSpace;
    if (InputColorSpace == 3 || !AutoContractVerified) return 0;
    #if BUFFER_COLOR_SPACE == 3
        return 1;
    #elif BUFFER_COLOR_SPACE == 2
        return 2;
    #else
        return 0;
    #endif
}
bool HDRIPS_Neutral()
{
    bool neutral = GlobalContrast == 0.0;
    #if HDRIPS_ENABLE_LOCAL
        neutral = neutral && LocalContrast == 0.0;
    #endif
    #if HDRIPS_ENABLE_COLOR
        neutral = neutral && ColorEnhancement == 0.0;
    #endif
    return neutral;
}
float HDRIPS_Min3(float3 v) { return min(v.x, min(v.y, v.z)); }
float HDRIPS_Max3(float3 v) { return max(v.x, max(v.y, v.z)); }
float3 HDRIPS_709To2020(float3 v)
{
    return float3(dot(v, float3(0.627403896, 0.329283038, 0.043313066)),
                  dot(v, float3(0.069097289, 0.919540395, 0.011362316)),
                  dot(v, float3(0.016391439, 0.088013308, 0.895595253)));
}
float3 HDRIPS_2020To709(float3 v)
{
    return float3(dot(v, float3(1.660491002, -0.587641139, -0.072849863)),
                  dot(v, float3(-0.124550475, 1.132899897, -0.008349422)),
                  dot(v, float3(-0.018150763, -0.100578898, 1.118729661)));
}
float3 HDRIPS_2020ToP3(float3 v)
{
    // P3 primaries with D65 white, not cinema DCI white; only an enhancement guard.
    return float3(dot(v, float3(1.343578253, -0.282179670, -0.061398583)),
                  dot(v, float3(-0.065297452, 1.075787916, -0.010490464)),
                  dot(v, float3(0.002821787, -0.019598495, 1.016776708)));
}
bool HDRIPS_Valid(float3 signal, int mode)
{
    if (any(isnan(signal)) || any(isinf(signal))) return false;
    if (mode == 1) return all(signal >= 0.0) && all(signal <= 1.0);
    // Preserve finite signed extended range. No arbitrary scRGB 0..1 clipping.
    return mode == 2;
}
float3 HDRIPS_Decode(float3 signal, int mode)
{
    if (mode == 2) return HDRIPS_709To2020(signal * 80.0);
    return float3(HDRIPS_PQDecode(signal.r), HDRIPS_PQDecode(signal.g), HDRIPS_PQDecode(signal.b));
}
float3 HDRIPS_Encode(float3 nits, int mode)
{
    if (mode == 2) return HDRIPS_2020To709(nits) / 80.0;
    return float3(HDRIPS_PQEncode(nits.r), HDRIPS_PQEncode(nits.g), HDRIPS_PQEncode(nits.b));
}
void HDRIPS_VS(uint id : SV_VertexID, out float4 position : SV_Position, out float2 uv : TEXCOORD)
{
    uv = float2((id << 1) & 2, id & 2);
    position = float4(uv * float2(2.0, -2.0) + float2(-1.0, 1.0), 0.0, 1.0);
}

#if HDRIPS_ENABLE_LOCAL
texture2D HDRIPS_LogGuide
{
    Width = BUFFER_WIDTH; Height = BUFFER_HEIGHT;
    Format = R32F; MipLevels = 1;
};
sampler2D HDRIPS_GuideSampler
{
    Texture = HDRIPS_LogGuide;
    MinFilter = POINT; MagFilter = POINT; MipFilter = POINT;
    AddressU = CLAMP; AddressV = CLAMP; SRGBTexture = false;
};
float HDRIPS_Prepare(float4 position : SV_Position, float2 uv : TEXCOORD) : SV_Target
{
    int mode = HDRIPS_Mode();
    if (mode == 0 || MasterStrength == 0.0 || LocalContrast == 0.0) return 0.0;
    float3 signal = tex2Dfetch(HDRIPS_SourceSampler, int2(position.xy), 0).rgb;
    if (!HDRIPS_Valid(signal, mode)) return -13.28771238; // log2(0.0001)
    float y = dot(HDRIPS_Decode(signal, mode), HDRIPS_Y2020);
    if (isnan(y) || isinf(y)) return -13.28771238;
    return log2(max(y, 0.0001));
}
float HDRIPS_LocalDelta(float2 uv, float y)
{
    const int q = HDRIPS_QUALITY + 1;
    float center = log2(max(y, 0.0001));
    float total = 0.0, weights = 0.0;
    float low = center, high = center;
    [loop] for (int j = -q; j <= q; ++j)
    {
        [loop] for (int i = -q; i <= q; ++i)
        {
            float2 n = float2(i, j) / float(q);
            float2 offset = round(n * LocalRadius);
            float2 tapUV = clamp(uv + offset / HDRIPS_Size, 0.5 / HDRIPS_Size, 1.0 - 0.5 / HDRIPS_Size);
            float sampleLog = tex2Dlod(HDRIPS_GuideSampler, float4(tapUV, 0.0, 0.0)).r;
            float d = (sampleLog - center) / 0.75;
            float w = exp2(-2.0 * dot(n, n) - 2.0 * d * d);
            total += w * sampleLog;
            weights += w;
            low = min(low, sampleLog); high = max(high, sampleLog);
        }
    }
    float residual = center - total / max(weights, 0.000001);
    float bounded = 0.5 * residual / (0.5 + abs(residual));
    float delta = LocalContrast * bounded
        * HDRIPS_LocalGate(y, MidtoneAnchor, ShadowProtection, HighlightProtection);
    // Do not create extrema outside the sampled neighborhood in original log Y.
    return clamp(center + delta, low, high) - center;
}
#endif

// Restrict only NEW positive exposure gain near the PQ component ceiling.
// No display peak is inferred; 10000 nits is the ST 2084 encoding boundary.
float HDRIPS_LimitGain(float wanted, float maximum, int mode)
{
    if (mode == 2 || wanted <= 1.0) return wanted;
    float budget = max(10000.0 / max(maximum, 0.000001) - 1.0, 0.0);
    return 1.0 + HDRIPS_SoftBudget(wanted - 1.0, budget);
}

#if HDRIPS_ENABLE_COLOR
float3 HDRIPS_Color(float3 rgb, float y, int mode, out float compression)
{
    compression = 0.0;
    if (ColorEnhancement == 0.0 || y <= 0.0) return rgb;
    float3 proxy = HDRIPS_2020ToP3(rgb);
    float3 chroma = rgb - y;
    // At fixed Y, min(primary)/Y measures distance to the nonnegative cone.
    // Negative P3 components imply existing color beyond the proxy; leave it alone.
    float s = max(0.0, 1.0 - HDRIPS_Min3(proxy) / y);
    float chromaRatio = (HDRIPS_Max3(rgb) - HDRIPS_Min3(rgb)) / max(y, 0.0001);
    float gate = smoothstep(0.015, 0.08, chromaRatio)
        * smoothstep(MidtoneAnchor * 0.005, MidtoneAnchor * 0.15, y)
        * (1.0 - smoothstep(MidtoneAnchor, HDRIPS_HighEnd(MidtoneAnchor, HighlightProtection), y));
    gate *= 1.0 - smoothstep(0.95 - 0.45 * SaturationProtection, 1.0, s);
    float wanted = ColorEnhancement * gate;
    if (wanted <= 0.0) return rgb;
    float budget = max(1.0 / max(s, 0.000001) - 1.0, 0.0);
    if (mode == 1)
    {
        // Also honor the actual BT.2020 PQ component domain along the chroma ray.
        if (chroma.r > 0.0) budget = min(budget, max((10000.0 - rgb.r) / chroma.r, 0.0));
        if (chroma.g > 0.0) budget = min(budget, max((10000.0 - rgb.g) / chroma.g, 0.0));
        if (chroma.b > 0.0) budget = min(budget, max((10000.0 - rgb.b) / chroma.b, 0.0));
        if (chroma.r < 0.0) budget = min(budget, max(-rgb.r / chroma.r, 0.0));
        if (chroma.g < 0.0) budget = min(budget, max(-rgb.g / chroma.g, 0.0));
        if (chroma.b < 0.0) budget = min(budget, max(-rgb.b / chroma.b, 0.0));
    }
    float allowed = HDRIPS_SoftBudget(wanted, budget);
    compression = saturate((wanted - allowed) / max(wanted, 0.000001));
    return rgb + chroma * allowed;
}
#endif

float3 HDRIPS_FalseColor(float y)
{
    if (y < 0.01) return float3(0.0, 0.0, 0.0);
    if (y < 0.1) return float3(0.35, 0.0, 0.6);
    if (y < 1.0) return float3(0.0, 0.1, 1.0);
    if (y < 10.0) return float3(0.0, 0.75, 0.75);
    if (y < 80.0) return float3(0.0, 0.7, 0.1);
    if (y < 203.0) return float3(0.9, 0.75, 0.0);
    if (y < 400.0) return float3(1.0, 0.25, 0.0);
    if (y < 1000.0) return float3(1.0, 0.0, 0.0);
    return float3(1.0, 0.0, 1.0);
}
// Diagnostic palettes are defined as linear BT.709, brightest component 100 nits.
float3 HDRIPS_EncodeDiagnostic(float3 palette, int mode)
{
    return HDRIPS_Encode(HDRIPS_709To2020(palette * 100.0), mode);
}

float4 HDRIPS_Main(float4 position : SV_Position, float2 uv : TEXCOORD) : SV_Target
{
    float4 original = tex2Dfetch(HDRIPS_SourceSampler, int2(position.xy), 0);
    int mode = HDRIPS_Mode();
    // Exact sampled-signal paths: no decode, encode, dither or alpha modification.
    if (mode == 0 || MasterStrength == 0.0) return original;
    if (HDRIPS_Neutral() && DiagnosticView == 0) return original;
    if (DiagnosticView == 1 && uv.x < SplitPosition) return original;
    if (!HDRIPS_Valid(original.rgb, mode)) return original;
    float3 inputRGB = HDRIPS_Decode(original.rgb, mode);
    float y = dot(inputRGB, HDRIPS_Y2020);
    // Nonpositive-Y signed scRGB is not forced into an artificial positive gamut.
    // Finite input can overflow during absolute-unit/matrix arithmetic.
    if (!HDRIPS_Valid(inputRGB, 2) || isnan(y) || isinf(y) || y <= 0.0) return original;
    float target = HDRIPS_Global(y, GlobalContrast, MidtoneAnchor, ShadowProtection, HighlightProtection);
    #if HDRIPS_ENABLE_LOCAL
        if (LocalContrast > 0.0)
            target *= exp2(HDRIPS_LocalDelta(uv, y));
    #endif
    float requestedGain = target / y;
    float gain = HDRIPS_LimitGain(requestedGain, HDRIPS_Max3(inputRGB), mode);
    float gainLimited = saturate((requestedGain - gain) / max(abs(requestedGain - 1.0), 0.000001));
    float3 result = inputRGB * gain;
    float gamutLimited = 0.0;
    #if HDRIPS_ENABLE_COLOR
        result = HDRIPS_Color(result, y * gain, mode, gamutLimited);
    #endif
    result = lerp(inputRGB, result, MasterStrength);
    if (!HDRIPS_Valid(result, 2)) return original;
    if (DiagnosticView == 2)
        return float4(HDRIPS_EncodeDiagnostic(HDRIPS_FalseColor(y), mode), original.a);
    if (DiagnosticView == 3)
    {
        float stops = log2(max(dot(result, HDRIPS_Y2020), 0.000001) / max(y, 0.000001));
        float3 palette = lerp(float3(0.18, 0.18, 0.18),
            stops < 0.0 ? float3(0.0, 0.25, 1.0) : float3(1.0, 0.2, 0.0), saturate(abs(stops) / 0.25));
        return float4(HDRIPS_EncodeDiagnostic(palette, mode), original.a);
    }
    if (DiagnosticView == 4)
    {
        float protection = smoothstep(MidtoneAnchor, HDRIPS_HighEnd(MidtoneAnchor, HighlightProtection), y);
        return float4(HDRIPS_EncodeDiagnostic(float3(gainLimited, gamutLimited, protection), mode), original.a);
    }
    if (HDRIPS_Neutral()) return original; // also exact in split view
    // Preserve unmodified pixels without a needless PQ/matrix round trip.
    if (all(result == inputRGB)) return original;
    float3 encoded = HDRIPS_Encode(result, mode);
    if (!HDRIPS_Valid(encoded, 2)) return original;
    return float4(encoded, original.a);
}

technique HDR_IPS_Enhance <
    ui_label = "HDR IPS Enhance";
    ui_tooltip = "Final-buffer HDR contrast and restrained color. Establish the input contract first; Auto bypasses until verified. Native HDR games only. See the supplied guide.";
>
{
    #if HDRIPS_ENABLE_LOCAL
    pass PrepareLogLuminance
    {
        VertexShader = HDRIPS_VS; PixelShader = HDRIPS_Prepare;
        RenderTarget = HDRIPS_LogGuide;
        SRGBWriteEnable = false; BlendEnable = false;
    }
    #endif
    pass Enhance
    {
        VertexShader = HDRIPS_VS; PixelShader = HDRIPS_Main;
        SRGBWriteEnable = false; BlendEnable = false;
    }
}
