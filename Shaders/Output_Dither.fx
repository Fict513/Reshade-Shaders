// Output_Dither 1.0.0 -- SPDX-License-Identifier: MIT
// Read README.md before enabling. Target assumptions are NOT display-link settings.
// Requires Output_Dither_Core.fxh and Textures/Output_Dither_BN128.png.
#ifndef OUTPUT_DITHER_ENABLE
#define OUTPUT_DITHER_ENABLE 1
#endif

texture2D OD_Color : COLOR;
sampler2D OD_ColorSampler
{
    Texture = OD_Color;
    SRGBTexture = false;
    MinFilter = POINT;
    MagFilter = POINT;
    MipFilter = POINT;
    AddressU = CLAMP;
    AddressV = CLAMP;
};

#if OUTPUT_DITHER_ENABLE
#include "Output_Dither_Core.fxh"
uniform bool OD_Bypass <
    ui_label = "Master bypass";
    ui_tooltip = "Enable only with a verified encoded signal and subsequent quantizer. Already-quantized same-grid input normally stays unchanged.";
> = true;
uniform int OD_Contract <
    ui_type = "combo";
    ui_label = "Explicit input AND output contract";
    ui_items = "Unknown / bypass\0SDR sRGB / BT.709\0Full-range ST 2084 PQ / BT.2020\0Linear scRGB / BT.709 / 80 nits per unit (bypass)\0";
    ui_tooltip = "Input and output must have this SAME encoding. No automatic detection. scRGB is intentionally unsupported and always bypassed.";
> = 0;
uniform int OD_Target <
    ui_type = "combo";
    ui_label = "Assumed quantizer at this stage";
    ui_items = "8-bit sRGB (255 intervals)\0 10-bit sRGB (1023 intervals)\0 10-bit PQ (1023 intervals)\0";
    ui_tooltip = "A processing-stage assumption, not a measurement or control of the physical display link. Mismatched encoding bypasses.";
> = 0;
uniform float OD_Strength <
    ui_type = "slider";
    ui_label = "Static blue-noise span (target code steps)";
    ui_min = 0.0; ui_max = 1.0; ui_step = 0.05;
    ui_tooltip = "1 = nominal one-step peak-to-peak uniform dither; actual peak +/-0.498046875 step, RMS 0.288672932 step away from endpoints. 0 returns the original sample. Lower values can leave banding.";
> = 1.0;

texture2D OD_BlueNoise < source = "Output_Dither_BN128.png"; >
{
    Width = 128; Height = 128;
    MipLevels = 1;
    Format = R8;
};
sampler2D OD_NoiseSampler
{
    Texture = OD_BlueNoise;
    SRGBTexture = false;
    MinFilter = POINT; MagFilter = POINT; MipFilter = POINT;
    AddressU = WRAP; AddressV = WRAP;
};
#endif

void OD_VS(uint id : SV_VertexID, out float4 position : SV_Position,
           out float2 uv : TEXCOORD)
{
    uv = float2((id << 1) & 2, id & 2);
    position = float4(uv * float2(2.0, -2.0) + float2(-1.0, 1.0), 0.0, 1.0);
}
float4 OD_PS(float4 position : SV_Position, float2 uv : TEXCOORD) : SV_Target
{
    float4 original = tex2Dlod(OD_ColorSampler, float4(uv, 0.0, 0.0));
#if OUTPUT_DITHER_ENABLE
    if (OD_Bypass || !OD_ContractValid(OD_Contract, OD_Target) ||
        !(OD_Strength > 0.0 && OD_Strength <= 1.0))
        return original;
    if (!(OD_InDomain(original.r) && OD_InDomain(original.g) && OD_InDomain(original.b)))
        return original;

    // Pixel-index addressing works for odd and singleton dimensions too.
    // Use interpolated UVs consistently with COLOR, including API Y orientation.
    float2 pixel = floor(uv * float2(BUFFER_WIDTH, BUFFER_HEIGHT));
    float2 noise_uv = (pixel + 0.5) / 128.0;
    float n = OD_Noise(tex2Dlod(OD_NoiseSampler, float4(noise_uv, 0.0, 0.0)).r);
    float levels = OD_Target == 0 ? 255.0 : 1023.0;
    return float4(OD_Channel(original.r, n, OD_Strength, levels),
                  OD_Channel(original.g, n, OD_Strength, levels),
                  OD_Channel(original.b, n, OD_Strength, levels), original.a);
#else
    return original;
#endif
}
technique Output_Dither <
    ui_label = "Output Dither (static blue noise)";
    ui_tooltip = "Finishing dither for a verified future quantizer. Unknown, scRGB and mismatched contracts bypass. Read the included feasibility report.";
>
{
    pass Finish
    {
        VertexShader = OD_VS;
        PixelShader = OD_PS;
        SRGBWriteEnable = false;
        BlendEnable = false;
        ColorWriteMask = 15;
    }
}
