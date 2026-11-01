// Adaptive Detail 1.0.0 -- MIT. Requires no ReShade.fxh or other shader pack.
#ifndef ADAPTIVE_DETAIL_QUALITY
#define ADAPTIVE_DETAIL_QUALITY 1
#endif
#ifndef ADAPTIVE_DETAIL_ENABLE_DETAIL
#define ADAPTIVE_DETAIL_ENABLE_DETAIL 1
#endif
// Set ONLY after establishing both sampled COLOR and destination contracts.
// 0 unknown, 1 sRGB/709, 2 full-range PQ/2020, 3 linear scRGB/709 (80 nit/unit).
#ifndef ADAPTIVE_DETAIL_VERIFIED_CONTRACT
#define ADAPTIVE_DETAIL_VERIFIED_CONTRACT 0
#endif
#ifndef BUFFER_COLOR_FORMAT
#define BUFFER_COLOR_FORMAT 0
#endif
#if ADAPTIVE_DETAIL_QUALITY < 0 || ADAPTIVE_DETAIL_QUALITY > 2
#error ADAPTIVE_DETAIL_QUALITY must be 0, 1, or 2
#endif
#if ADAPTIVE_DETAIL_ENABLE_DETAIL != 0 && ADAPTIVE_DETAIL_ENABLE_DETAIL != 1
#error ADAPTIVE_DETAIL_ENABLE_DETAIL must be 0 or 1
#endif
#include "Adaptive_Detail_Core.fxh"

uniform float AD_Master < ui_type="slider"; ui_label="Master strength"; ui_min=0.0; ui_max=1.0; ui_step=0.01;
 ui_tooltip="Overall correction. Zero returns the original sampled float4, including in diagnostics."; > = 0.65;
uniform float AD_Fine < ui_type="slider"; ui_label="Fine sharpening"; ui_min=0.0; ui_max=1.0; ui_step=0.01;
 ui_tooltip="Fine residual above the 3x3 binomial low-pass. Start low with TAA/DLSS/FSR sharpening enabled."; > = 0.45;
#if ADAPTIVE_DETAIL_ENABLE_DETAIL
uniform float AD_Detail < ui_type="slider"; ui_label="Small-scale detail"; ui_min=0.0; ui_max=1.0; ui_step=0.01;
 ui_tooltip="Band between 3x3 and 5x5 low-passes; fixed two-pixel support, shared correction budget with fine sharpening."; > = 0.10;
#endif
uniform float AD_Edge < ui_type="slider"; ui_label="Edge / halo protection"; ui_min=0.0; ui_max=1.0; ui_step=0.01;
 ui_tooltip="Reduces strong-edge corrections. At 1, no expansion of local luminance extrema; true peaks also sharpen less."; > = 0.85;
uniform float AD_Noise < ui_type="slider"; ui_label="Noise protection"; ui_min=0.0; ui_max=1.0; ui_step=0.01;
 ui_tooltip="Heuristic suppression of weak and alternating detail. Cannot identify grain, skin, foliage or UI reliably."; > = 0.80;
uniform int AD_Contract < ui_type="combo"; ui_label="Input and output contract";
 ui_items="Verified integration / otherwise bypass\0SDR sRGB / BT.709\0HDR PQ / BT.2020 / full range\0HDR linear scRGB / BT.709\0Force bypass\0";
 ui_tooltip="Explicit selection asserts BOTH COLOR and destination encoding. Never infer from bpc, FP16 or Windows HDR. Default bypasses unless VERIFIED_CONTRACT was set."; > = 0;
uniform int AD_View < ui_type="combo"; ui_label="Diagnostic view";
 ui_items="Normal\0Original / effected split\0Signed luminance correction\0Effective strength\0Limiter activity\0";
 ui_tooltip="Split: original left. Correction: blue negative, orange positive, gray zero. Strength: pre-limiter master times protection. Limiter: removed fraction, smoothly downweighted for negligible requests."; > = 0;
uniform float AD_Split < ui_type="slider"; ui_label="Split position"; ui_min=0.0; ui_max=1.0; ui_step=0.01; > = 0.5;

texture2D AD_Color : COLOR;
sampler2D AD_ColorSampler { Texture=AD_Color; AddressU=CLAMP; AddressV=CLAMP; MinFilter=POINT; MagFilter=POINT; MipFilter=POINT; SRGBTexture=false; };
texture2D AD_Luma { Width=BUFFER_WIDTH; Height=BUFFER_HEIGHT; Format=R32F; MipLevels=1; };
sampler2D AD_LumaPoint { Texture=AD_Luma; AddressU=CLAMP; AddressV=CLAMP; MinFilter=POINT; MagFilter=POINT; MipFilter=POINT; SRGBTexture=false; };
#if ADAPTIVE_DETAIL_ENABLE_DETAIL && ADAPTIVE_DETAIL_QUALITY == 0
sampler2D AD_LumaLinear { Texture=AD_Luma; AddressU=CLAMP; AddressV=CLAMP; MinFilter=LINEAR; MagFilter=LINEAR; MipFilter=POINT; SRGBTexture=false; };
#endif
int AD_GetContract()
{
    int c = AD_Contract == 0 ? ADAPTIVE_DETAIL_VERIFIED_CONTRACT : AD_Contract;
    if (c < 1 || c > 3) return 0;
    // Format checks are numerical compatibility checks, NEVER encoding detection.
    // Unknown metadata requires the user to verify representability externally.
#if BUFFER_COLOR_FORMAT != 0
    if (c == 3 && BUFFER_COLOR_FORMAT != 10 && BUFFER_COLOR_FORMAT != 2) return 0;
#endif
    return c;
}
float AD_DetailAmount()
{
#if ADAPTIVE_DETAIL_ENABLE_DETAIL
    return AD_Detail;
#else
    return 0.0;
#endif
}
bool AD_IsActive() { return AD_Master > 0.0 && (AD_Fine > 0.0 || AD_DetailAmount() > 0.0); }
float2 AD_UV(float2 uv) { return (floor(uv*float2(BUFFER_WIDTH,BUFFER_HEIGHT))+0.5)*float2(BUFFER_RCP_WIDTH,BUFFER_RCP_HEIGHT); }
void AD_VS(uint id : SV_VertexID, out float4 pos : SV_Position, out float2 uv : TEXCOORD)
{
    uv = float2((id << 1) & 2, id & 2);
    pos = float4(uv*float2(2.0,-2.0)+float2(-1.0,1.0),0.0,1.0);
}
float AD_Prepare(float4 pos : SV_Position, float2 uv : TEXCOORD) : SV_Target
{
    int c=AD_GetContract();
    if(c==0 || !AD_IsActive()) return 0.0;
    float3 v=tex2D(AD_ColorSampler,AD_UV(uv)).rgb;
    if(!AD_Valid(v.r,c) || !AD_Valid(v.g,c) || !AD_Valid(v.b,c)) return -1.0e30;
    return AD_Y(AD_Decode(v.r,c),AD_Decode(v.g,c),AD_Decode(v.b,c),c);
}
float AD_Tap(float2 uv,int x,int y) { return tex2D(AD_LumaPoint,uv+float2(x,y)*float2(BUFFER_RCP_WIDTH,BUFFER_RCP_HEIGHT)).r; }
float4 AD_Apply(float4 pos : SV_Position, float2 uv : TEXCOORD) : SV_Target
{
    uv=AD_UV(uv);
    float4 original=tex2D(AD_ColorSampler,uv);
    int c=AD_GetContract();
    if(c==0 || !AD_IsActive()) return original;
    if(!AD_Valid(original.r,c)||!AD_Valid(original.g,c)||!AD_Valid(original.b,c)) return original;
    ADNeighborhood p;
    p.c=AD_Tap(uv,0,0); p.n=AD_Tap(uv,0,-1); p.s=AD_Tap(uv,0,1);
    p.e=AD_Tap(uv,1,0); p.w=AD_Tap(uv,-1,0);
    p.nw=AD_Tap(uv,-1,-1); p.ne=AD_Tap(uv,1,-1); p.sw=AD_Tap(uv,-1,1); p.se=AD_Tap(uv,1,1);
    float least=min(min(min(p.n,p.s),min(p.e,p.w)),min(min(p.nw,p.ne),min(p.sw,p.se)));
    if(p.c < -1.0e20 || least < -1.0e20) return original;
    p.broadDelta=0.0;
#if ADAPTIVE_DETAIL_ENABLE_DETAIL
    if(AD_Detail > 0.0)
    {
#if ADAPTIVE_DETAIL_QUALITY == 0
        // Exact separable binomial5 pairing in real arithmetic: 4+1 at +/-1.2.
        // Center pair weight 6/16, outer pair weights 5/16. 8 extra bilinear taps.
        [unroll] for(int j=-1;j<=1;j++) [unroll] for(int i=-1;i<=1;i++)
        {
            if(i==0 && j==0) continue;
            float v=tex2D(AD_LumaLinear,uv+float2(i,j)*1.2*float2(BUFFER_RCP_WIDTH,BUFFER_RCP_HEIGHT)).r;
            if(v < -1.0e20) return original;
            p.broadDelta += (v-p.c)*(i==0 ? 6.0 : 5.0)*(j==0 ? 6.0 : 5.0)/256.0;
        }
#else
        // High and Ultra intentionally share exact point evaluation; no invented Ultra cost.
        p.broadDelta=(24.0*((p.n-p.c)+(p.s-p.c)+(p.e-p.c)+(p.w-p.c))+
                     16.0*((p.nw-p.c)+(p.ne-p.c)+(p.sw-p.c)+(p.se-p.c)))/256.0;
        [unroll] for(int j=-2;j<=2;j++) [unroll] for(int i=-2;i<=2;i++)
        {
            if(abs(i)!=2 && abs(j)!=2) continue;
            float v=AD_Tap(uv,i,j);
            if(v < -1.0e20) return original;
            float wx=abs(i)==2 ? 1.0 : (i==0 ? 6.0 : 4.0);
            float wy=abs(j)==2 ? 1.0 : (j==0 ? 6.0 : 4.0);
            p.broadDelta += (v-p.c)*wx*wy/256.0;
        }
#endif
    }
#endif
    float3 rgb=float3(AD_Decode(original.r,c),AD_Decode(original.g,c),AD_Decode(original.b,c));
    float peak=max(rgb.r,max(rgb.g,rgb.b));
    float up=0.12;
    if(c!=3) up=max((c==1 ? 1.0 : 125.0)/max(peak,1.0e-20)-1.0,0.0);
#if BUFFER_COLOR_FORMAT == 10 || BUFFER_COLOR_FORMAT == 0
    // Conservatively use FP16 finite range if destination format is not reported.
    if(c==3) up=max(65504.0/max(max(abs(rgb.r),abs(rgb.g)),max(abs(rgb.b),1.0e-20))-1.0,0.0);
#endif
    ADResult result=AD_Correction(p,AD_Master,AD_Fine,AD_DetailAmount(),AD_Edge,AD_Noise,up);
    float3 output=original.rgb;
    if(result.delta!=0.0)
    {
        float gain=1.0+result.delta/p.c;
        float3 v=rgb*gain;
        output=float3(AD_Encode(v.r,c),AD_Encode(v.g,c),AD_Encode(v.b,c));
    }
    if(AD_View==1 && uv.x < AD_Split) return original;
    if(AD_View>=2)
    {
        float3 palette;
        if(AD_View==2)
        {
            float t=clamp(result.delta/max(abs(p.c),0.002)/0.05,-1.0,1.0);
            palette=lerp(float3(0.18,0.18,0.18),t>=0.0 ? float3(0.75,0.22,0.04) : float3(0.04,0.30,0.75),abs(t));
        }
        else { float t=AD_View==3 ? result.effective : result.limiter; t=0.02+0.78*t; palette=t.xxx; }
        // Palette values are LINEAR in active primaries. HDR unit = 80 nits.
        output=float3(AD_Encode(palette.r,c),AD_Encode(palette.g,c),AD_Encode(palette.b,c));
    }
    return float4(output,original.a);
}
technique Adaptive_Detail < ui_label="Adaptive Detail"; ui_tooltip="Spatial luminance sharpening. Default safe bypass: verify the COLOR/destination contract before selecting an encoding."; >
{
    pass PrepareLuminance { VertexShader=AD_VS; PixelShader=AD_Prepare; RenderTarget=AD_Luma; SRGBWriteEnable=false; BlendEnable=false; }
    pass ApplyDetail { VertexShader=AD_VS; PixelShader=AD_Apply; SRGBWriteEnable=false; BlendEnable=false; }
}
