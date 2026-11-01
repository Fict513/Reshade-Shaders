#include "cpu_shim.hpp"
#include "../Shaders/Adaptive_Detail_Core.fxh"
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
    return 0.0f;
#endif
}
bool AD_IsActive() { return AD_Master > 0.0f && (AD_Fine > 0.0f || AD_DetailAmount() > 0.0f); }
float2 AD_UV(float2 uv) { return (floor(uv*float2(BUFFER_WIDTH,BUFFER_HEIGHT))+0.5f)*float2(BUFFER_RCP_WIDTH,BUFFER_RCP_HEIGHT); }
float AD_Prepare(float4 pos, float2 uv)
{
    int c=AD_GetContract();
    if(c==0 || !AD_IsActive()) return 0.0f;
    float3 v=tex2D(AD_ColorSampler,AD_UV(uv)).rgb();
    if(!AD_Valid(v.r,c) || !AD_Valid(v.g,c) || !AD_Valid(v.b,c)) return -1.0e30f;
    return AD_Y(AD_Decode(v.r,c),AD_Decode(v.g,c),AD_Decode(v.b,c),c);
}
float AD_Tap(float2 uv,int x,int y) { return tex2D(AD_LumaPoint,uv+float2(x,y)*float2(BUFFER_RCP_WIDTH,BUFFER_RCP_HEIGHT)).r; }
float4 AD_Apply(float4 pos, float2 uv)
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
    if(p.c < -1.0e20f || least < -1.0e20f) return original;
    p.broadDelta=0.0f;
#if ADAPTIVE_DETAIL_ENABLE_DETAIL
    if(AD_Detail > 0.0f)
    {
#if ADAPTIVE_DETAIL_QUALITY == 0
        // Exact separable binomial5 pairing in real arithmetic: 4+1 at +/-1.2.
        // Center pair weight 6/16, outer pair weights 5/16.f 8 extra bilinear taps.
         for(int j=-1;j<=1;j++)  for(int i=-1;i<=1;i++)
        {
            if(i==0 && j==0) continue;
            float v=tex2D(AD_LumaLinear,uv+float2(i,j)*1.2f*float2(BUFFER_RCP_WIDTH,BUFFER_RCP_HEIGHT)).r;
            if(v < -1.0e20f) return original;
            p.broadDelta += (v-p.c)*(i==0 ? 6.0f : 5.0f)*(j==0 ? 6.0f : 5.0f)/256.0f;
        }
#else
        // High and Ultra intentionally share exact point evaluation; no invented Ultra cost.
        p.broadDelta=(24.0f*((p.n-p.c)+(p.s-p.c)+(p.e-p.c)+(p.w-p.c))+
                     16.0f*((p.nw-p.c)+(p.ne-p.c)+(p.sw-p.c)+(p.se-p.c)))/256.0f;
         for(int j=-2;j<=2;j++)  for(int i=-2;i<=2;i++)
        {
            if(abs(i)!=2 && abs(j)!=2) continue;
            float v=AD_Tap(uv,i,j);
            if(v < -1.0e20f) return original;
            float wx=abs(i)==2 ? 1.0f : (i==0 ? 6.0f : 4.0f);
            float wy=abs(j)==2 ? 1.0f : (j==0 ? 6.0f : 4.0f);
            p.broadDelta += (v-p.c)*wx*wy/256.0f;
        }
#endif
    }
#endif
    float3 rgb=float3(AD_Decode(original.r,c),AD_Decode(original.g,c),AD_Decode(original.b,c));
    float peak=max(rgb.r,max(rgb.g,rgb.b));
    float up=0.12f;
    if(c!=3) up=max((c==1 ? 1.0f : 125.0f)/max(peak,1.0e-20f)-1.0f,0.0f);
#if BUFFER_COLOR_FORMAT == 10 || BUFFER_COLOR_FORMAT == 0
    // Conservatively use FP16 finite range if destination format is not reported.
    if(c==3) up=max(65504.0f/max(max(abs(rgb.r),abs(rgb.g)),max(abs(rgb.b),1.0e-20f))-1.0f,0.0f);
#endif
    ADResult result=AD_Correction(p,AD_Master,AD_Fine,AD_DetailAmount(),AD_Edge,AD_Noise,up);
    float3 output=original.rgb();
    if(result.delta!=0.0f)
    {
        float gain=1.0f+result.delta/p.c;
        float3 v=rgb*gain;
        output=float3(AD_Encode(v.r,c),AD_Encode(v.g,c),AD_Encode(v.b,c));
    }
    if(AD_View==1 && uv.x < AD_Split) return original;
    if(AD_View>=2)
    {
        float3 palette;
        if(AD_View==2)
        {
            float t=clamp(result.delta/max(abs(p.c),0.002f)/0.05f,-1.0f,1.0f);
            palette=lerp(float3(0.18f,0.18f,0.18f),t>=0.0f ? float3(0.75f,0.22f,0.04f) : float3(0.04f,0.30f,0.75f),abs(t));
        }
        else { float t=AD_View==3 ? result.effective : result.limiter; t=0.02f+0.78f*t; palette=float3(t,t,t); }
        // Palette values are LINEAR in active primaries. HDR unit = 80 nits.
        output=float3(AD_Encode(palette.r,c),AD_Encode(palette.g,c),AD_Encode(palette.b,c));
    }
    return float4(output,original.a);
}

#include "cpu_driver.hpp"
