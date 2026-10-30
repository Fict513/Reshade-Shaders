/*
Selective Deband 1.0 - restrained SDR gradient smoothing for ReShade/GShade
Copyright (c) 2026 OpenAI. MIT license at end.

Install in the Shaders directory, reload, enable Selective Deband. Start with
other debanders disabled. Typical order: IPS Depth / FakeHDR -> Selective Deband
-> Adaptive Clarity. Disable dithering in earlier grades initially. A later
sharpener may emphasize remaining banding, so compare the complete stack.
No includes, external textures, depth or add-on. SDR encoded RGB / Rec.709 only.
Declared HDR spaces pass through unchanged; unknown spaces cannot be verified.

SDB_QUALITY=0 Normal / 1 High / 2 Ultra: 4 / 8 / 16 paired angular directions.
Every direction samples both signs at radius 0.5*Radius and Radius. The common
3x3 protects local edges and fine changes. Ring weights are normalized across
tiers, not strengthened. One pass, no intermediate targets; nominal 25 / 41 /
73 texture reads per pixel. Counts are not GPU timings. SDB_HUD_MASKS=0 strips
manual rectangles; SDB_DITHER=0 strips dithering. Defaults are 1 for both.

Algorithm: encoded-RGB luma/chroma gates reject unlike paired samples. A
center-weighted convex average estimates the shallow gradient. Local range and
second differences reduce eligibility at edges and fine patterns. The RGB
correction is bounded, endpoint protected and blended. Dither is static,
monochrome, output-bit-depth scaled and gated by eligibility + actual change.
All threshold/correction sliders are measured in 8-bit code steps (1/255),
independent of output bit depth because banding may originate in an 8-bit asset.

Eligibility is a spatial heuristic, NOT semantic banding recognition. Genuine
subtle texture and low-contrast contours can also be smoothed. Wide plateaus,
severe/compressed bands or noise can defeat it. It cannot restore lost colors
or detail. Fixed rectangles are not automatic HUD detection. Dither can become
visible, especially after NVIDIA color enhancement. No time-varying samples or
temporal history are used; motion stability still requires in-game testing.
Original implementation; not a copy of haasn/JPulowski Deband.fx.
*/
#ifndef SDB_QUALITY
#define SDB_QUALITY 1
#endif
#ifndef SDB_HUD_MASKS
#define SDB_HUD_MASKS 1
#endif
#ifndef SDB_DITHER
#define SDB_DITHER 1
#endif
#if SDB_QUALITY <= 0
#define _SDB_PAIRS 4
#elif SDB_QUALITY == 1
#define _SDB_PAIRS 8
#else
#define _SDB_PAIRS 16
#endif
#if defined(BUFFER_COLOR_SPACE) && BUFFER_COLOR_SPACE > 1
#define _SDB_HDR 1
#else
#define _SDB_HDR 0
#endif

namespace SelectiveDeband
{
uniform float Strength <
    ui_type = "slider"; ui_label = "Overall strength"; ui_category = "1. Debanding";
    ui_min = 0.0; ui_max = 1.0; ui_step = 0.01;
> = 0.85;
uniform float Radius <
    ui_type = "slider"; ui_label = "Search radius (output pixels)"; ui_category = "1. Debanding";
    ui_min = 2.0; ui_max = 32.0; ui_step = 1.0;
    ui_tooltip = "Samples at half and full radius. Wider bands may need a larger radius, at the risk of crossing real features.";
> = 8.0;
uniform float LumaThreshold <
    ui_type = "slider"; ui_label = "Brightness threshold (8-bit steps)"; ui_category = "1. Debanding";
    ui_min = 0.5; ui_max = 12.0; ui_step = 0.25;
    ui_tooltip = "Maximum brightness difference allowed in paired reference samples. Higher values can smooth real contours.";
> = 3.0;
uniform float ChromaThreshold <
    ui_type = "slider"; ui_label = "Color threshold (8-bit steps)"; ui_category = "1. Debanding";
    ui_min = 0.5; ui_max = 12.0; ui_step = 0.25;
    ui_tooltip = "Maximum difference in RGB-minus-luma chroma. Lower to protect color boundaries.";
> = 2.0;
uniform float TextureThreshold <
    ui_type = "slider"; ui_label = "Texture threshold (8-bit steps)"; ui_category = "2. Protection";
    ui_min = 0.5; ui_max = 8.0; ui_step = 0.25;
    ui_tooltip = "Threshold for local second differences. Lower protects more texture but can reject shallow band edges too.";
> = 1.0;
uniform float EdgeThreshold <
    ui_type = "slider"; ui_label = "Edge threshold (8-bit steps)"; ui_category = "2. Protection";
    ui_min = 1.0; ui_max = 24.0; ui_step = 0.5;
    ui_tooltip = "Local RGB range above this is protected. Lower protects more HUD/text boundaries.";
> = 4.0;
uniform float MaxCorrection <
    ui_type = "slider"; ui_label = "Maximum correction (8-bit steps)"; ui_category = "2. Protection";
    ui_min = 0.25; ui_max = 4.0; ui_step = 0.25;
    ui_tooltip = "Caps the strongest RGB component of smoothing before final strength. Does not include dither.";
> = 1.0;
uniform float Dither <
    ui_type = "slider"; ui_label = "Selective dither (output steps)"; ui_category = "3. Output";
    ui_min = 0.0; ui_max = 1.0; ui_step = 0.05;
    ui_tooltip = "Static monochrome noise only where correction is made. Scales for 8/10-bit output, off for 16-bit. Can be enhanced by RTX Dynamic Vibrance.";
> = 0.80;
uniform bool Mask1Enabled < ui_label = "Protect HUD rectangle 1"; ui_category = "4. HUD protection"; > = false;
uniform float4 Mask1Rect <
    ui_type = "slider"; ui_label = "Rectangle 1: left, top, right, bottom"; ui_category = "4. HUD protection";
    ui_min = 0.0; ui_max = 1.0; ui_step = 0.001;
> = float4(0.0, 0.82, 0.35, 1.0);
uniform bool Mask2Enabled < ui_label = "Protect HUD rectangle 2"; ui_category = "4. HUD protection"; > = false;
uniform float4 Mask2Rect <
    ui_type = "slider"; ui_label = "Rectangle 2: left, top, right, bottom"; ui_category = "4. HUD protection";
    ui_min = 0.0; ui_max = 1.0; ui_step = 0.001;
> = float4(0.65, 0.82, 1.0, 1.0);
uniform float MaskFeather <
    ui_type = "slider"; ui_label = "HUD feather (output pixels)"; ui_category = "4. HUD protection";
    ui_min = 0.0; ui_max = 48.0; ui_step = 1.0;
    ui_tooltip = "Complete protection inside each rectangle, fading outside. Zero is a hard boundary.";
> = 12.0;
uniform bool SplitView < ui_label = "Compare: original left / processed right"; ui_category = "5. Compare"; > = false;
uniform float SplitPosition <
    ui_type = "slider"; ui_label = "Comparison position"; ui_category = "5. Compare";
    ui_min = 0.0; ui_max = 1.0; ui_step = 0.01;
> = 0.5;
uniform int View <
    ui_type = "combo"; ui_label = "View"; ui_category = "5. Compare";
    ui_items = "Final image\0Eligible areas\0Smoothing correction\0HUD protection\0";
    ui_tooltip = "Eligible areas are flat-enough candidates, not proven banding. Correction is amplified RGB around neutral gray, before dither.";
> = 0;

texture2D InputTexture : COLOR;
sampler2D InputSampler
{
    Texture = InputTexture; AddressU = CLAMP; AddressV = CLAMP;
    MinFilter = LINEAR; MagFilter = LINEAR; MipFilter = POINT; SRGBTexture = false;
};
float Luma(float3 rgb) { return dot(rgb,float3(0.2126,0.7152,0.0722)); }
float Largest(float3 value) { return max(value.r,max(value.g,value.b)); }
float3 ReadColor(float2 uv) { return saturate(tex2D(InputSampler,uv).rgb); }
float Accept(float difference,float threshold)
{ return 1.0 - smoothstep(0.5*threshold,threshold,difference); }
float RectangleMask(float2 uv,float4 rect)
{
    float2 lo=min(rect.xy,rect.zw),hi=max(rect.xy,rect.zw);
    float2 outside=max(max(lo-uv,uv-hi),0.0);
    float distance=length(outside*float2(BUFFER_WIDTH,BUFFER_HEIGHT));
    if (MaskFeather<=0.0) return distance<=0.0 ? 1.0 : 0.0;
    return 1.0-smoothstep(0.0,MaskFeather,distance);
}
float HUDMask(float2 uv)
{
    float value=0.0;
#if SDB_HUD_MASKS
    if (Mask1Enabled) value=max(value,RectangleMask(uv,Mask1Rect));
    if (Mask2Enabled) value=max(value,RectangleMask(uv,Mask2Rect));
#endif
    return value;
}
float DitherStep()
{
#if defined(BUFFER_COLOR_BIT_DEPTH) && BUFFER_COLOR_BIT_DEPTH >= 16
    return 0.0;
#elif defined(BUFFER_COLOR_BIT_DEPTH) && BUFFER_COLOR_BIT_DEPTH == 10
    return 1.0/1023.0;
#else
    return 1.0/255.0;
#endif
}
float Hash(float2 p) { return frac(52.9829189*frac(dot(p,float2(0.06711056,0.00583715)))); }
void VS(uint id : SV_VertexID,out float4 position : SV_Position,out float2 uv : TEXCOORD0)
{
    uv=float2(id==2 ? 2.0 : 0.0,id==1 ? 2.0 : 0.0);
    position=float4(uv*float2(2.0,-2.0)+float2(-1.0,1.0),0.0,1.0);
}
float4 PS(float4 position : SV_Position,float2 uv : TEXCOORD0) : SV_Target
{
    float4 original=tex2D(InputSampler,uv);
#if _SDB_HDR
    return original;
#else
    if (Strength<=0.0 || (SplitView && uv.x<SplitPosition)) return original;
    float protection=HUDMask(uv);
    if (View==3) return float4(protection,protection,protection,original.a);
    if (protection>=1.0)
    {
        if (View==1) return float4(0.0,0.0,0.0,original.a);
        if (View==2) return float4(0.5,0.5,0.5,original.a);
        return original;
    }
    const float step8=1.0/255.0;
    float3 center=saturate(original.rgb);
    float centerY=Luma(center);
    float3 centerChroma=center-centerY;
    float2 pixel=float2(BUFFER_RCP_WIDTH,BUFFER_RCP_HEIGHT);
    float3 a=ReadColor(uv+pixel*float2(-1.0,-1.0));
    float3 b=ReadColor(uv+pixel*float2( 0.0,-1.0));
    float3 c=ReadColor(uv+pixel*float2( 1.0,-1.0));
    float3 d=ReadColor(uv+pixel*float2(-1.0, 0.0));
    float3 f=ReadColor(uv+pixel*float2( 1.0, 0.0));
    float3 g=ReadColor(uv+pixel*float2(-1.0, 1.0));
    float3 h=ReadColor(uv+pixel*float2( 0.0, 1.0));
    float3 i=ReadColor(uv+pixel*float2( 1.0, 1.0));
    float3 lo=min(center,min(min(a,b),min(c,min(d,min(f,min(g,min(h,i)))))));
    float3 hi=max(center,max(max(a,b),max(c,max(d,max(f,max(g,max(h,i)))))));
    float span=Largest(hi-lo);
    // Second differences distinguish some alternating fine changes from shallow
    // steps. This cannot distinguish every real contour from a band boundary.
    float3 curvatureRGB=max(max(abs(a-2.0*b+c),abs(g-2.0*h+i)),
                            max(abs(a-2.0*d+g),abs(c-2.0*f+i)));
    curvatureRGB=max(curvatureRGB,max(abs(d-2.0*center+f),abs(b-2.0*center+h)));
    float curvature=Largest(curvatureRGB);
    float edgeMask=Accept(span,EdgeThreshold*step8);
    float textureMask=1.0-smoothstep(TextureThreshold*step8,2.0*TextureThreshold*step8,curvature);
    float endpoint=smoothstep(0.0,0.02,centerY)*(1.0-smoothstep(0.98,1.0,centerY));
    float localMask=edgeMask*textureMask*endpoint*(1.0-protection);
    if (localMask<=0.0)
    {
        if (View==1) return float4(0.0,0.0,0.0,original.a);
        if (View==2) return float4(0.5,0.5,0.5,original.a);
        return original;
    }

    float3 total=center;
    float weights=1.0,accepted=0.0;
    [unroll]
    for (int pair=0;pair<_SDB_PAIRS;++pair)
    {
        float angle=3.14159265359*float(pair)/float(_SDB_PAIRS);
        float2 direction=float2(cos(angle),sin(angle));
        [unroll]
        for (int ring=0;ring<2;++ring)
        {
            float radius=Radius*(ring==0 ? 0.5 : 1.0);
            float2 offset=direction*pixel*radius;
            float3 positive=ReadColor(uv+offset);
            float3 negative=ReadColor(uv-offset);
            float yp=Luma(positive),yn=Luma(negative);
            float brightness=max(abs(yp-centerY),abs(yn-centerY));
            float color=max(Largest(abs((positive-yp)-centerChroma)),
                            Largest(abs((negative-yn)-centerChroma)));
            float w=Accept(brightness,LumaThreshold*step8)*Accept(color,ChromaThreshold*step8);
            w*=(ring==0 ? 1.0 : 0.65)/float(_SDB_PAIRS);
            total+=0.5*(positive+negative)*w;
            weights+=w;accepted+=w;
        }
    }
    float eligible=localMask*smoothstep(0.05,0.35,saturate(accepted/1.65));
    if (View==1) return float4(eligible,eligible,eligible,original.a);
    float3 delta=total/weights-center;
    float maximum=Largest(abs(delta));
    delta*=min(1.0,MaxCorrection*step8/max(maximum,0.00000001));
    delta*=Strength*eligible;
    if (View==2) return float4(saturate(0.5+delta*32.0),original.a);
    float change=Largest(abs(delta));
    if (change<=0.0000001) return original;
    float3 result=center+delta;
#if SDB_DITHER
    if (Dither>0.0 && DitherStep()>0.0)
    {
        float2 p=floor(position.xy);
        float noise=Hash(p)-Hash(p+float2(37.0,17.0));
        float minimum=min(result.r,min(result.g,result.b));
        float maximumChannel=max(result.r,max(result.g,result.b));
        float headroom=smoothstep(0.0,2.0*DitherStep(),min(minimum,1.0-maximumChannel));
        float changed=smoothstep(0.01*step8,0.25*step8,change);
        float ditherEligible=smoothstep(0.0,0.25,eligible);
        result+=noise*Dither*DitherStep()*ditherEligible*Strength*changed*headroom;
    }
#endif
    return float4(saturate(result),original.a);
#endif
}
}
technique Selective_Deband <
    ui_label = "Selective Deband";
    ui_tooltip = "SDR shallow-gradient smoothing with edge/texture gates, quality presets and optional selective dither.";
>
{
    pass
    {
        VertexShader=SelectiveDeband::VS; PixelShader=SelectiveDeband::PS;
        SRGBWriteEnable=false;
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
