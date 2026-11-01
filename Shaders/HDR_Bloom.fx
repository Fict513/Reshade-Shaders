// HDR Bloom 1.0.0 -- see README.md and LICENSE.txt.
// No ReShade.fxh / shader-pack dependency. COLOR must be a verified final image.
#ifndef HDRBLOOM_QUALITY
#define HDRBLOOM_QUALITY 1
#endif
#ifndef HDRBLOOM_DIAGNOSTICS
#define HDRBLOOM_DIAGNOSTICS 1
#endif
#ifndef HDRBLOOM_AUTO_CONTRACT
#define HDRBLOOM_AUTO_CONTRACT 0
#endif
#if HDRBLOOM_QUALITY < 0 || HDRBLOOM_QUALITY > 2
#error HDRBLOOM_QUALITY must be 0, 1 or 2
#endif
#if HDRBLOOM_DIAGNOSTICS < 0 || HDRBLOOM_DIAGNOSTICS > 1
#error HDRBLOOM_DIAGNOSTICS must be 0 or 1
#endif
#if HDRBLOOM_AUTO_CONTRACT < 0 || HDRBLOOM_AUTO_CONTRACT > 3
#error HDRBLOOM_AUTO_CONTRACT must be 0, 1, 2 or 3
#endif
#include "HDR_Bloom_Math.fxh"
namespace HDRBloom
{
uniform int InputMode <
    ui_type = "combo"; ui_label = "Input / output contract";
    ui_items = "Auto (verified contract only)\0SDR sRGB / BT.709\0HDR10 PQ / BT.2020\0Linear scRGB / BT.709\0Safe bypass\0";
    ui_tooltip = "Input and destination must use the SAME verified encoding. Auto bypasses unless HDRBLOOM_AUTO_CONTRACT is established for this injection point. Neither bit depth nor presentation metadata is proof.";
> = 0;
uniform float Strength < ui_type="slider"; ui_category="Artistic"; ui_label="Bloom strength";
    ui_min=0.0; ui_max=0.25; ui_step=0.005;
    ui_tooltip="Fraction of extracted light redistributed. 0 returns the original sample exactly, including in diagnostic views. Start at 0.04.";
> = 0.04;
uniform float ThresholdNits < ui_type="slider"; ui_category="Artistic"; ui_label="HDR threshold (source nits)";
    ui_min=20.0; ui_max=2000.0; ui_step=5.0;
    ui_tooltip="PQ/scRGB only. Use above the game's diffuse white; this is source luminance, not your panel's measured peak. Bright HUD may bloom.";
> = 250.0;
uniform float KneeNits < ui_type="slider"; ui_category="Artistic"; ui_label="HDR knee full width (nits)";
    ui_min=0.0; ui_max=1000.0; ui_step=5.0;
    ui_tooltip="Transition from threshold minus width/2 to threshold plus width/2. Effective width is capped at twice threshold. Zero gives a continuous hard knee with a slope corner.";
> = 150.0;
uniform float ThresholdSDR < ui_type="slider"; ui_category="Artistic"; ui_label="SDR threshold (reference-white fraction)";
    ui_min=0.05; ui_max=1.0; ui_step=0.01;
    ui_tooltip="Linear SDR units, NOT measured nits. Linear 1.0 is reference white. Below 1 allows ordinary SDR highlights to diffuse.";
> = 0.60;
uniform float KneeSDR < ui_type="slider"; ui_category="Artistic"; ui_label="SDR knee full width (white fraction)";
    ui_min=0.0; ui_max=1.0; ui_step=0.01;
    ui_tooltip="Linear reference-white units. Transition is threshold +/- width/2; effective width <= twice threshold.";
> = 0.30;
uniform float Spread < ui_type="slider"; ui_category="Artistic"; ui_label="Bloom spread";
    ui_min=0.5; ui_max=2.0; ui_step=0.05;
    ui_tooltip="At 1440p and spread 1, Gaussian component sigmas are approximately 3, 12 and 48 pixels, plus pyramid footprints. Scales with image height; aspect ratio stays isotropic in pixels. Pyramid imposes a minimum footprint.";
> = 1.0;
#if HDRBLOOM_DIAGNOSTICS
uniform int View < ui_type="combo"; ui_category="Inspection"; ui_label="Diagnostic view";
    ui_items="Effect\0Extracted source (luminance)\0Incoming bloom (luminance)\0Signed luminance change\0Output-limit activity\0";
    ui_tooltip="Scalar diagnostic colors, encoded for the selected output. Extraction and incoming light use a compressive false-color scale; not scene color previews. See README for units and legend.";
> = 0;
uniform bool Split < ui_category="Inspection"; ui_label="Original / effected split";
    ui_tooltip="Left is exact original; right is effect or selected diagnostic. No divider is drawn.";
> = false;
uniform float SplitPosition < ui_type="slider"; ui_category="Inspection"; ui_label="Split position"; ui_min=0.0; ui_max=1.0; ui_step=0.01; > = 0.5;
#endif
texture2D Source : COLOR;
sampler2D SourcePoint { Texture=Source; MinFilter=POINT; MagFilter=POINT; MipFilter=POINT; AddressU=CLAMP; AddressV=CLAMP; SRGBTexture=false; };

int Mode() { return InputMode == 0 ? HDRBLOOM_AUTO_CONTRACT : InputMode; }
bool Active() { int m=Mode(); return m>=1 && m<=3 && Strength>0.0; }
float3 LumaWeights(int m) { return m==2 ? float3(0.2627,0.6780,0.0593) : float3(0.2126,0.7152,0.0722); }
bool Valid(float3 v, int m)
{
    // Reject NaN/Inf and arithmetic-hostile values from processing, not from
    // the passthrough. This comfortably includes every finite FP16 value.
    if (!all(abs(v) <= 1.0e30)) return false;
    return m==3 || (all(v>=0.0) && all(v<=1.0));
}
float3 Decode(float3 v, int m)
{
    if (m==1) return float3(HB_SRGBDecode(v.r),HB_SRGBDecode(v.g),HB_SRGBDecode(v.b));
    if (m==2) return float3(HB_PQDecode(v.r),HB_PQDecode(v.g),HB_PQDecode(v.b));
    return v*80.0;
}
float3 Encode(float3 v, int m)
{
    if (m==1) return float3(HB_SRGBEncode(v.r),HB_SRGBEncode(v.g),HB_SRGBEncode(v.b));
    if (m==2) return float3(HB_PQEncode(v.r),HB_PQEncode(v.g),HB_PQEncode(v.b));
    return v/80.0;
}
float Threshold(int m) { return m==1 ? clamp(ThresholdSDR,0.05,1.0) : clamp(ThresholdNits,20.0,2000.0); }
float3 Extract(float3 linearRGB,int m)
{
    float y=dot(linearRGB,LumaWeights(m));
    float k=m==1 ? max(KneeSDR,0.0) : max(KneeNits,0.0);
    // Positive-Y signed colors retain ALL signed components. Y<=0 extracts zero.
    return linearRGB*HB_Fraction(y,Threshold(m),k);
}
float3 ExtractEncoded(float3 v)
{
    int m=Mode();
    if (!Valid(v,m)) return 0.0;
    return Extract(Decode(v,m),m);
}
void VS(uint id : SV_VertexID, out float4 position : SV_Position, out float2 uv : TEXCOORD0)
{
    uv=float2((id<<1)&2,id&2);
    position=float4(uv*float2(2.0,-2.0)+float2(-1.0,1.0),0.0,1.0);
}

// Equal-area box integration, including odd dimensions; extract BEFORE average.
// Each output cell covers <=2 input cells in length, at most 3 intersected
// texels per axis. Integral areas tile the source without padding or dropped edges.
float4 Downsample(sampler2D src,float2 uv,float2 inputSize,float2 outputSize,bool first)
{
    if (!Active()) return 0.0;
    float2 cell=floor(uv*outputSize);
    float2 lo=cell*inputSize/outputSize;
    float2 hi=(cell+1.0)*inputSize/outputSize;
    float2 start=floor(lo);
    float3 sum=0.0;
    [unroll] for(int j=0;j<3;++j)
    [unroll] for(int i=0;i<3;++i)
    {
        float2 p=start+float2(i,j);
        float2 overlap=max(0.0,min(hi,p+1.0)-max(lo,p));
        float weight=overlap.x*overlap.y;
        if(weight>0.0)
        {
            float3 c=tex2Dlod(src,float4((p+0.5)/inputSize,0.0,0.0)).rgb;
            sum+=(first ? ExtractEncoded(c) : c)*weight;
        }
    }
    return float4(sum/((hi.x-lo.x)*(hi.y-lo.y)),0.0);
}

// Same intended normalized discrete Gaussian at every quality. Higher tiers
// retain more tail support. Adjacent integer taps are combined with bilinear
// interpolation: 11/13/15 fetches, equivalent to 21/25/29 discrete taps.
#if HDRBLOOM_QUALITY == 0
#define HB_PAIRS 5
#elif HDRBLOOM_QUALITY == 1
#define HB_PAIRS 6
#else
#define HB_PAIRS 7
#endif
float4 Blur(sampler2D src,float2 uv,float2 size,float2 axis,float nominalScale)
{
    if(!Active()) return 0.0;
    float sigmaFull=1.5*nominalScale*clamp(Spread,0.5,2.0)*(BUFFER_HEIGHT/1440.0);
    float sigma=sigmaFull*dot(axis,size/float2(BUFFER_WIDTH,BUFFER_HEIGHT));
    float invTwoVariance=0.5/(sigma*sigma);
    float3 total=tex2Dlod(src,float4(uv,0.0,0.0)).rgb;
    float norm=1.0;
    [unroll] for(int i=0;i<HB_PAIRS;++i)
    {
        float a=2.0*i+1.0;
        float wa=exp(-a*a*invTwoVariance);
        float wb=exp(-(a+1.0)*(a+1.0)*invTwoVariance);
        float weight=wa+wb;
        // This branch also prevents 0/0 at tiny resolutions.
        if(weight>0.0)
        {
            float offset=a+wb/weight;
            float2 stepUV=axis*offset/size;
            total+=weight*(tex2Dlod(src,float4(uv+stepUV,0.0,0.0)).rgb
                          +tex2Dlod(src,float4(uv-stepUV,0.0,0.0)).rgb);
            norm+=2.0*weight;
        }
    }
    return float4(total/norm,0.0);
}
#define HB_W1 ((BUFFER_WIDTH+1)/2)
#define HB_H1 ((BUFFER_HEIGHT+1)/2)
texture2D D1 { Width=HB_W1; Height=HB_H1; Format=RGBA32F; MipLevels=1; };
sampler2D D1Point { Texture=D1; MinFilter=POINT; MagFilter=POINT; MipFilter=POINT; AddressU=CLAMP; AddressV=CLAMP; SRGBTexture=false; };
sampler2D D1Linear { Texture=D1; MinFilter=LINEAR; MagFilter=LINEAR; MipFilter=POINT; AddressU=MIRROR; AddressV=MIRROR; SRGBTexture=false; };
texture2D X1 { Width=HB_W1; Height=HB_H1; Format=RGBA32F; MipLevels=1; };
sampler2D X1Linear { Texture=X1; MinFilter=LINEAR; MagFilter=LINEAR; MipFilter=POINT; AddressU=MIRROR; AddressV=MIRROR; SRGBTexture=false; };
texture2D B1 { Width=HB_W1; Height=HB_H1; Format=RGBA32F; MipLevels=1; };
sampler2D B1Linear { Texture=B1; MinFilter=LINEAR; MagFilter=LINEAR; MipFilter=POINT; AddressU=MIRROR; AddressV=MIRROR; SRGBTexture=false; };
float4 Down1(float4 pos:SV_Position,float2 uv:TEXCOORD0):SV_Target { return Downsample(SourcePoint,uv,float2(BUFFER_WIDTH,BUFFER_HEIGHT),float2(HB_W1,HB_H1),true); }
float4 BlurH1(float4 pos:SV_Position,float2 uv:TEXCOORD0):SV_Target { return Blur(D1Linear,uv,float2(HB_W1,HB_H1),float2(1.0,0.0),2.0); }
float4 BlurV1(float4 pos:SV_Position,float2 uv:TEXCOORD0):SV_Target { return Blur(X1Linear,uv,float2(HB_W1,HB_H1),float2(0.0,1.0),2.0); }
#define HB_W2 ((BUFFER_WIDTH+3)/4)
#define HB_H2 ((BUFFER_HEIGHT+3)/4)
texture2D D2 { Width=HB_W2; Height=HB_H2; Format=RGBA32F; MipLevels=1; };
sampler2D D2Point { Texture=D2; MinFilter=POINT; MagFilter=POINT; MipFilter=POINT; AddressU=CLAMP; AddressV=CLAMP; SRGBTexture=false; };
float4 Down2(float4 pos:SV_Position,float2 uv:TEXCOORD0):SV_Target { return Downsample(D1Point,uv,float2(HB_W1,HB_H1),float2(HB_W2,HB_H2),false); }
#define HB_W3 ((BUFFER_WIDTH+7)/8)
#define HB_H3 ((BUFFER_HEIGHT+7)/8)
texture2D D3 { Width=HB_W3; Height=HB_H3; Format=RGBA32F; MipLevels=1; };
sampler2D D3Point { Texture=D3; MinFilter=POINT; MagFilter=POINT; MipFilter=POINT; AddressU=CLAMP; AddressV=CLAMP; SRGBTexture=false; };
sampler2D D3Linear { Texture=D3; MinFilter=LINEAR; MagFilter=LINEAR; MipFilter=POINT; AddressU=MIRROR; AddressV=MIRROR; SRGBTexture=false; };
texture2D X3 { Width=HB_W3; Height=HB_H3; Format=RGBA32F; MipLevels=1; };
sampler2D X3Linear { Texture=X3; MinFilter=LINEAR; MagFilter=LINEAR; MipFilter=POINT; AddressU=MIRROR; AddressV=MIRROR; SRGBTexture=false; };
texture2D B3 { Width=HB_W3; Height=HB_H3; Format=RGBA32F; MipLevels=1; };
sampler2D B3Linear { Texture=B3; MinFilter=LINEAR; MagFilter=LINEAR; MipFilter=POINT; AddressU=MIRROR; AddressV=MIRROR; SRGBTexture=false; };
float4 Down3(float4 pos:SV_Position,float2 uv:TEXCOORD0):SV_Target { return Downsample(D2Point,uv,float2(HB_W2,HB_H2),float2(HB_W3,HB_H3),false); }
float4 BlurH3(float4 pos:SV_Position,float2 uv:TEXCOORD0):SV_Target { return Blur(D3Linear,uv,float2(HB_W3,HB_H3),float2(1.0,0.0),8.0); }
float4 BlurV3(float4 pos:SV_Position,float2 uv:TEXCOORD0):SV_Target { return Blur(X3Linear,uv,float2(HB_W3,HB_H3),float2(0.0,1.0),8.0); }
#define HB_W4 ((BUFFER_WIDTH+15)/16)
#define HB_H4 ((BUFFER_HEIGHT+15)/16)
texture2D D4 { Width=HB_W4; Height=HB_H4; Format=RGBA32F; MipLevels=1; };
sampler2D D4Point { Texture=D4; MinFilter=POINT; MagFilter=POINT; MipFilter=POINT; AddressU=CLAMP; AddressV=CLAMP; SRGBTexture=false; };
float4 Down4(float4 pos:SV_Position,float2 uv:TEXCOORD0):SV_Target { return Downsample(D3Point,uv,float2(HB_W3,HB_H3),float2(HB_W4,HB_H4),false); }
#define HB_W5 ((BUFFER_WIDTH+31)/32)
#define HB_H5 ((BUFFER_HEIGHT+31)/32)
texture2D D5 { Width=HB_W5; Height=HB_H5; Format=RGBA32F; MipLevels=1; };
sampler2D D5Point { Texture=D5; MinFilter=POINT; MagFilter=POINT; MipFilter=POINT; AddressU=CLAMP; AddressV=CLAMP; SRGBTexture=false; };
sampler2D D5Linear { Texture=D5; MinFilter=LINEAR; MagFilter=LINEAR; MipFilter=POINT; AddressU=MIRROR; AddressV=MIRROR; SRGBTexture=false; };
texture2D X5 { Width=HB_W5; Height=HB_H5; Format=RGBA32F; MipLevels=1; };
sampler2D X5Linear { Texture=X5; MinFilter=LINEAR; MagFilter=LINEAR; MipFilter=POINT; AddressU=MIRROR; AddressV=MIRROR; SRGBTexture=false; };
texture2D B5 { Width=HB_W5; Height=HB_H5; Format=RGBA32F; MipLevels=1; };
sampler2D B5Linear { Texture=B5; MinFilter=LINEAR; MagFilter=LINEAR; MipFilter=POINT; AddressU=MIRROR; AddressV=MIRROR; SRGBTexture=false; };
float4 Down5(float4 pos:SV_Position,float2 uv:TEXCOORD0):SV_Target { return Downsample(D4Point,uv,float2(HB_W4,HB_H4),float2(HB_W5,HB_H5),false); }
float4 BlurH5(float4 pos:SV_Position,float2 uv:TEXCOORD0):SV_Target { return Blur(D5Linear,uv,float2(HB_W5,HB_H5),float2(1.0,0.0),32.0); }
float4 BlurV5(float4 pos:SV_Position,float2 uv:TEXCOORD0):SV_Target { return Blur(X5Linear,uv,float2(HB_W5,HB_H5),float2(0.0,1.0),32.0); }

#if HDRBLOOM_DIAGNOSTICS
float3 Diagnostic(float3 e,float3 b,float3 actualDelta,float limit,int m)
{
    float3 lw=LumaWeights(m);
    float t=Threshold(m);
    float3 color=0.0;
    if(View==1 || View==2)
    {
        float y=max(dot(View==1 ? e : clamp(Strength,0.0,0.25)*b,lw),0.0);
        float a=y/(y+t); // half-scale at extraction threshold
        color=a.xxx;
    }
    if(View==3)
    {
        float dy=dot(actualDelta,lw);
        float a=abs(dy)/(abs(dy)+0.1*t);
        color=dy>=0.0 ? float3(0.0,a,a) : float3(a,0.0,a);
    }
    if(View==4) color=float3(1.0-limit,0.0,0.0);
    // HDR diagnostic components top out at 80 nits, SDR at reference white.
    return Encode(color*(m==1 ? 1.0 : 80.0),m);
}
#endif
float4 Composite(float4 pos:SV_Position,float2 uv:TEXCOORD0):SV_Target
{
    float4 original=tex2Dlod(SourcePoint,float4(uv,0.0,0.0));
    // Exact sampled float4 return: no decode, encode, diagnostic or dither.
    if(!Active()) return original;
#if HDRBLOOM_DIAGNOSTICS
    if(Split && uv.x<SplitPosition) return original;
#endif
    int m=Mode();
    if(!Valid(original.rgb,m)) return original;
    float3 source=Decode(original.rgb,m);
    float3 e=Extract(source,m);
    float3 b=0.55*tex2Dlod(B1Linear,float4(uv,0.0,0.0)).rgb
            +0.30*tex2Dlod(B3Linear,float4(uv,0.0,0.0)).rgb
            +0.15*tex2Dlod(B5Linear,float4(uv,0.0,0.0)).rgb;
    float3 delta=clamp(Strength,0.0,0.25)*(b-e);
    if(!all(abs(delta)<=1.0e33)) return original;
    float limit=1.0;
    if(m!=3)
    {
        float cap=m==1 ? 1.0 : 10000.0;
        limit=min(HB_ChannelLimit(source.r,delta.r,cap),
              min(HB_ChannelLimit(source.g,delta.g,cap),HB_ChannelLimit(source.b,delta.b,cap)));
        // Small numerical margin only when limiter engages, along the SAME RGB
        // segment. No independent per-channel truncation, no whole-image shoulder.
        if(limit<1.0) limit=max(limit,0.0)*(1.0-2.0e-6);
    }
    float3 result=source+limit*delta;
    if(!all(abs(result)<=1.0e34)) return original;
    // Reject an unexpected arithmetic failure rather than manufacture a color.
    if(m!=3 && (!all(result>=0.0) || !all(result<=(m==1 ? 1.0 : 10000.0)))) return original;
#if HDRBLOOM_DIAGNOSTICS
    if(View!=0) return float4(Diagnostic(e,b,result-source,limit,m),original.a);
#endif
    if(limit==0.0 || all(delta==0.0)) return original;
    return float4(Encode(result,m),original.a);
}
technique HDR_Bloom < ui_label="HDR Bloom - restrained diffusion"; ui_tooltip="Verify the sampled COLOR and destination contract first. Auto defaults to bypass. See README.md."; >
{
    pass Down1 { VertexShader=VS; PixelShader=Down1; RenderTarget=D1; SRGBWriteEnable=false; BlendEnable=false; }
    pass Down2 { VertexShader=VS; PixelShader=Down2; RenderTarget=D2; SRGBWriteEnable=false; BlendEnable=false; }
    pass Down3 { VertexShader=VS; PixelShader=Down3; RenderTarget=D3; SRGBWriteEnable=false; BlendEnable=false; }
    pass Down4 { VertexShader=VS; PixelShader=Down4; RenderTarget=D4; SRGBWriteEnable=false; BlendEnable=false; }
    pass Down5 { VertexShader=VS; PixelShader=Down5; RenderTarget=D5; SRGBWriteEnable=false; BlendEnable=false; }
    pass Horizontal1 { VertexShader=VS; PixelShader=BlurH1; RenderTarget=X1; SRGBWriteEnable=false; BlendEnable=false; }
    pass Vertical1 { VertexShader=VS; PixelShader=BlurV1; RenderTarget=B1; SRGBWriteEnable=false; BlendEnable=false; }
    pass Horizontal3 { VertexShader=VS; PixelShader=BlurH3; RenderTarget=X3; SRGBWriteEnable=false; BlendEnable=false; }
    pass Vertical3 { VertexShader=VS; PixelShader=BlurV3; RenderTarget=B3; SRGBWriteEnable=false; BlendEnable=false; }
    pass Horizontal5 { VertexShader=VS; PixelShader=BlurH5; RenderTarget=X5; SRGBWriteEnable=false; BlendEnable=false; }
    pass Vertical5 { VertexShader=VS; PixelShader=BlurV5; RenderTarget=B5; SRGBWriteEnable=false; BlendEnable=false; }
    pass Output { VertexShader=VS; PixelShader=Composite; SRGBWriteEnable=false; BlendEnable=false; }
}
}
