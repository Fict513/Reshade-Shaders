/*
IPS Suite - coordinated SDR contrast, deband, clarity and output dither
Copyright (c) 2026 OpenAI. MIT license; see LICENSE distributed with this suite.
The algorithm modules are adapted from the three standalone shaders.
*/
#ifndef IPS_SUITE_QUALITY
#define IPS_SUITE_QUALITY 1
#endif
#ifndef IPS_SUITE_CONTRAST
#define IPS_SUITE_CONTRAST 1
#endif
#ifndef IPS_SUITE_DEBAND
#define IPS_SUITE_DEBAND 1
#endif
#ifndef IPS_SUITE_CLARITY
#define IPS_SUITE_CLARITY 1
#endif
#ifndef IPS_SUITE_DITHER
#define IPS_SUITE_DITHER 1
#endif
#if IPS_SUITE_QUALITY < 0 || IPS_SUITE_QUALITY > 2
#error IPS_SUITE_QUALITY must be 0, 1 or 2
#endif
#if defined(BUFFER_COLOR_SPACE) && BUFFER_COLOR_SPACE > 1
#define _SUITE_HDR 1
#else
#define _SUITE_HDR 0
#endif

#undef IPSD2_QUALITY
#undef IPSD2_LOCAL
#undef IPSD2_BROAD
#undef SDB_QUALITY
#undef SDB_HUD_MASKS
#undef SDB_DITHER
#undef AC_QUALITY
#undef AC_HUD_MASKS
#define IPSD2_QUALITY IPS_SUITE_QUALITY
#define IPSD2_LOCAL 1
#define IPSD2_BROAD 1
#define SDB_QUALITY IPS_SUITE_QUALITY
#define SDB_HUD_MASKS 0
#define SDB_DITHER 0
#define AC_QUALITY IPS_SUITE_QUALITY
#define AC_HUD_MASKS 0

namespace IPSSuite
{
texture2D OriginalTexture : COLOR;
sampler2D OriginalSampler
{
    Texture = OriginalTexture; AddressU = CLAMP; AddressV = CLAMP;
    MinFilter = LINEAR; MagFilter = LINEAR; MipFilter = POINT; SRGBTexture = false;
};
#if !_SUITE_HDR && IPS_SUITE_CONTRAST && (IPS_SUITE_DEBAND || IPS_SUITE_CLARITY)
texture2D ContrastTexture { Width = BUFFER_WIDTH; Height = BUFFER_HEIGHT; Format = RGBA32F; };
sampler2D ContrastSampler
{
    Texture = ContrastTexture; AddressU = CLAMP; AddressV = CLAMP;
    MinFilter = LINEAR; MagFilter = LINEAR; MipFilter = POINT; SRGBTexture = false;
};
#endif
#if !_SUITE_HDR && IPS_SUITE_DEBAND && IPS_SUITE_CLARITY
texture2D DebandTexture { Width = BUFFER_WIDTH; Height = BUFFER_HEIGHT; Format = RGBA32F; };
sampler2D DebandSampler
{
    Texture = DebandTexture; AddressU = CLAMP; AddressV = CLAMP;
    MinFilter = LINEAR; MagFilter = LINEAR; MipFilter = POINT; SRGBTexture = false;
};
#endif

#if !_SUITE_HDR
#if IPS_SUITE_DEBAND && IPS_SUITE_DITHER
uniform float OutputDither <
    ui_type = "slider"; ui_label = "Selective output dither (output steps)"; ui_category = "4. Output";
    ui_min = 0.0; ui_max = 1.0; ui_step = 0.05;
    ui_tooltip = "Static monochrome noise after clarity, only where debanding changed the image. Off for unknown or non-8/10-bit output.";
> = 0.80;
#endif
uniform bool Mask1Enabled < ui_label = "Protect rectangle 1"; ui_category = "4. Output"; > = false;
uniform float4 Mask1Rect <
    ui_type = "slider"; ui_label = "Rectangle 1: left, top, right, bottom"; ui_category = "4. Output";
    ui_min = 0.0; ui_max = 1.0; ui_step = 0.001;
> = float4(0.0, 0.82, 0.35, 1.0);
uniform bool Mask2Enabled < ui_label = "Protect rectangle 2"; ui_category = "4. Output"; > = false;
uniform float4 Mask2Rect <
    ui_type = "slider"; ui_label = "Rectangle 2: left, top, right, bottom"; ui_category = "4. Output";
    ui_min = 0.0; ui_max = 1.0; ui_step = 0.001;
> = float4(0.65, 0.82, 1.0, 1.0);
uniform float MaskFeather <
    ui_type = "slider"; ui_label = "Exclusion feather (output pixels)"; ui_category = "4. Output";
    ui_min = 0.0; ui_max = 48.0; ui_step = 1.0;
    ui_tooltip = "Restores the input inside rectangles, fading outside. Nearby filter samples can still include excluded pixels.";
> = 12.0;
uniform bool SplitView < ui_label = "Compare: original left / suite right"; ui_category = "5. Diagnostics"; > = false;
uniform float SplitPosition <
    ui_type = "slider"; ui_label = "Comparison position"; ui_category = "5. Diagnostics";
    ui_min = 0.0; ui_max = 1.0; ui_step = 0.01;
> = 0.5;
uniform int View <
    ui_type = "combo"; ui_label = "View"; ui_category = "5. Diagnostics";
    ui_items = "Final image\0Exclusion protection\0";
> = 0;

float RectangleMask(float2 uv, float4 rect)
{
    float2 lo = min(rect.xy, rect.zw), hi = max(rect.xy, rect.zw);
    float2 outside = max(max(lo - uv, uv - hi), 0.0);
    float distance = length(outside * float2(BUFFER_WIDTH, BUFFER_HEIGHT));
    if (MaskFeather <= 0.0) return distance <= 0.0 ? 1.0 : 0.0;
    return 1.0 - smoothstep(0.0, MaskFeather, distance);
}
float Protection(float2 uv)
{
    float value = 0.0;
    if (Mask1Enabled) value = max(value, RectangleMask(uv, Mask1Rect));
    if (Mask2Enabled) value = max(value, RectangleMask(uv, Mask2Rect));
    return value;
}
#if IPS_SUITE_DEBAND && IPS_SUITE_DITHER
float DitherStep()
{
#if defined(BUFFER_COLOR_BIT_DEPTH) && BUFFER_COLOR_BIT_DEPTH == 8
    return 1.0 / 255.0;
#elif defined(BUFFER_COLOR_BIT_DEPTH) && BUFFER_COLOR_BIT_DEPTH == 10
    return 1.0 / 1023.0;
#else
    return 0.0;
#endif
}
float Hash(float2 p) { return frac(52.9829189 * frac(dot(p, float2(0.06711056, 0.00583715)))); }
#endif
#endif
void VS(uint id : SV_VertexID, out float4 position : SV_Position, out float2 uv : TEXCOORD0)
{
    uv = float2(id == 2 ? 2.0 : 0.0, id == 1 ? 2.0 : 0.0);
    position = float4(uv * float2(2.0, -2.0) + float2(-1.0, 1.0), 0.0, 1.0);
}
}

#if !_SUITE_HDR && IPS_SUITE_CONTRAST
#include "IPS_Suite/Contrast.fxh"
#endif
#if !_SUITE_HDR && IPS_SUITE_DEBAND
#if IPS_SUITE_CONTRAST
#define _SUITE_DEBAND_INPUT IPSSuite::ContrastSampler
#else
#define _SUITE_DEBAND_INPUT IPSSuite::OriginalSampler
#endif
#include "IPS_Suite/Deband.fxh"
#endif
#if !_SUITE_HDR && IPS_SUITE_CLARITY
#if IPS_SUITE_DEBAND
#define _SUITE_CLARITY_INPUT IPSSuite::DebandSampler
#elif IPS_SUITE_CONTRAST
#define _SUITE_CLARITY_INPUT IPSSuite::ContrastSampler
#else
#define _SUITE_CLARITY_INPUT IPSSuite::OriginalSampler
#endif
#include "IPS_Suite/Clarity.fxh"
#endif

namespace IPSSuite
{
#if !_SUITE_HDR && IPS_SUITE_DEBAND && IPS_SUITE_CLARITY
float4 StoreDeband(float4 position : SV_Position, float2 uv : TEXCOORD0) : SV_Target
{
    float eligibility;
    float4 color = SelectiveDeband::Process(position, uv, eligibility);
    return float4(color.rgb, eligibility);
}
#endif
float4 Final(float4 position : SV_Position, float2 uv : TEXCOORD0) : SV_Target
{
    float4 original = tex2D(OriginalSampler, uv);
#if _SUITE_HDR
    return original;
#else
    if (SplitView && uv.x < SplitPosition) return original;
    bool active = false;
#if IPS_SUITE_CONTRAST
    active = active || IPSD2::ContrastStrength > 0.0;
#endif
#if IPS_SUITE_DEBAND
    active = active || SelectiveDeband::DebandStrength > 0.0;
#endif
#if IPS_SUITE_CLARITY
    active = active || AdaptiveClarity::ClarityStrength > 0.0;
#endif
    if (!active) return original;
    float protection = Protection(uv);
    if (View == 1) return float4(protection.xxx, original.a);
    if (protection >= 1.0) return original;
    float4 result = original;
    float eligibility = 0.0;
#if IPS_SUITE_CLARITY
    result = AdaptiveClarity::Composite(position, uv);
#if IPS_SUITE_DEBAND
    eligibility = tex2D(DebandSampler, uv).a;
#endif
#elif IPS_SUITE_DEBAND
    result = SelectiveDeband::Process(position, uv, eligibility);
#elif IPS_SUITE_CONTRAST
    result = IPSD2::Composite(position, uv);
#endif
#if IPS_SUITE_DEBAND && IPS_SUITE_DITHER
    float step = DitherStep();
    if (OutputDither > 0.0 && step > 0.0 && eligibility > 0.0)
    {
        float2 p = floor(position.xy);
        float noise = Hash(p) - Hash(p + float2(37.0, 17.0));
        float low = min(result.r, min(result.g, result.b));
        float high = max(result.r, max(result.g, result.b));
        float headroom = smoothstep(0.0, 2.0 * step, min(low, 1.0 - high));
        result.rgb = saturate(result.rgb + noise * OutputDither * step * eligibility * headroom);
    }
#endif
    return float4(lerp(original.rgb, result.rgb, 1.0 - protection), original.a);
#endif
}
}

technique IPS_Suite <
    ui_label = "IPS Suite";
    ui_tooltip = "SDR contrast, selective deband, clarity and final dither. Declared HDR passes through.";
>
{
#if !_SUITE_HDR && IPS_SUITE_CONTRAST
    pass ContrastLuma { VertexShader = IPSSuite::VS; PixelShader = IPSD2::CacheLuma; RenderTarget = IPSD2::LumaTexture; SRGBWriteEnable = false; }
    pass ContrastFineX { VertexShader = IPSSuite::VS; PixelShader = IPSD2::FineHorizontal; RenderTarget = IPSD2::FineXTexture; SRGBWriteEnable = false; }
    pass ContrastFineY { VertexShader = IPSSuite::VS; PixelShader = IPSD2::FineVertical; RenderTarget = IPSD2::FineYTexture; SRGBWriteEnable = false; }
    pass ContrastBroadPrepare { VertexShader = IPSSuite::VS; PixelShader = IPSD2::BroadPrepare; RenderTarget = IPSD2::BroadPrepTexture; SRGBWriteEnable = false; }
    pass ContrastBroadX { VertexShader = IPSSuite::VS; PixelShader = IPSD2::BroadHorizontal; RenderTarget = IPSD2::BroadXTexture; SRGBWriteEnable = false; }
    pass ContrastBroadY { VertexShader = IPSSuite::VS; PixelShader = IPSD2::BroadVertical; RenderTarget = IPSD2::BroadYTexture; SRGBWriteEnable = false; }
#if IPS_SUITE_DEBAND || IPS_SUITE_CLARITY
    pass ContrastOutput { VertexShader = IPSSuite::VS; PixelShader = IPSD2::Composite; RenderTarget = IPSSuite::ContrastTexture; SRGBWriteEnable = false; }
#endif
#endif
#if !_SUITE_HDR && IPS_SUITE_DEBAND && IPS_SUITE_CLARITY
    pass DebandOutput { VertexShader = IPSSuite::VS; PixelShader = IPSSuite::StoreDeband; RenderTarget = IPSSuite::DebandTexture; SRGBWriteEnable = false; }
#endif
#if !_SUITE_HDR && IPS_SUITE_CLARITY
    pass ClarityGuide { VertexShader = IPSSuite::VS; PixelShader = AdaptiveClarity::CacheGuide; RenderTarget = AdaptiveClarity::GuideTexture; SRGBWriteEnable = false; }
#endif
    pass Output { VertexShader = IPSSuite::VS; PixelShader = IPSSuite::Final; SRGBWriteEnable = false; }
}
