/*
FakeHDR Advanced 1.0 - SDR HDR-look grading for ReShade / GShade
Copyright (c) 2026 OpenAI. MIT license below.

Original implementation, inspired by the purpose of CeeJay.dk's FakeHDR:
https://github.com/Mortalitas/GShade/blob/master/Shaders/FakeHDR.fx
No source code from that shader is incorporated here.

INSTALL: Copy into reshade-shaders/Shaders (or gshade-shaders/Shaders), Reload,
enable FakeHDR Advanced. Disable FakeHDR and IPS Depth/HQ to avoid stacking.
No includes, depth buffer, external textures, or add-ons required.
Assumes SDR sRGB/Rec.709 primaries and sRGB transfer. Known HDR presentation
spaces bypass processing. Unknown presentation spaces cannot be detected.
Use after game tone mapping/color grading. Menus and HUD are affected too.
This is an artistic SDR effect, not HDR output or recovery of clipped detail.

PIPELINE:
* sRGB decoding and log2(linear luminance + epsilon) analysis.
* Three cascaded, full-resolution separable joint bilateral scales. Every
  stage retains ORIGINAL log-luminance guidance in G, smoothed signal in R.
  This is a separable approximation, not an exact circular 2D bilateral.
* Independent fine, medium and broad contrast bands avoid counting each
  high-frequency detail in all three controls.
* Bounded local exposure in stops, with edge/noise/shadow/highlight protection.
* Endpoint-preserving SDR tone curve and adjustable highlight brilliance.
* RGB-ratio reconstruction in linear light; neutral-axis soft gamut compression.
  Brightening is capped by each pixel's channel headroom so saturated bright
  colors are not washed out toward white.
* Optional subtle static monochrome dither; no temporal adaptation or history.

QUALITY: FHDRA_QUALITY=0/1/2 means 17/25/33 taps per filter axis.
Default 1: seven passes, approximately 162 texture fetches/output pixel.
Six full-resolution RG32F targets keep log-luma filtering free of half-float
quantization. Working target storage is 48 bytes/pixel (~226.8 MiB at 3440x1440).
No FPS estimate is implied. Quality 2 adds samples, not more contrast.
Radius is scaled with output height; very large radii use spaced taps.
Overall strength=0 bypasses grading but not the filter passes. Disable the
technique to recover its full GPU cost. Compile-time HDR bypass uses one pass.

START: use defaults. For more dramatic HDR look, try Medium detail 0.35,
Broad detail 0.25 and Highlight brilliance 0.25. Reduce Tonal contrast if dark
areas lose visibility. The effect cannot lower your display's physical black.
*/
#ifndef FHDRA_QUALITY
#define FHDRA_QUALITY 1
#endif
#if FHDRA_QUALITY <= 0
#define _FHDRA_TAPS 8
#elif FHDRA_QUALITY == 1
#define _FHDRA_TAPS 12
#else
#define _FHDRA_TAPS 16
#endif
#if defined(BUFFER_COLOR_SPACE) && BUFFER_COLOR_SPACE > 1
#define _FHDRA_HDR 1
#else
#define _FHDRA_HDR 0
#endif
namespace FHDRA
{
uniform float Strength <
 ui_type = "slider"; ui_label = "Overall strength"; ui_category = "1. Look";
 ui_min = 0.0; ui_max = 1.0; ui_step = 0.01;
 ui_tooltip = "Blend with original. Disable the technique to recover all GPU cost.";
> = 1.0;
uniform float Contrast <
 ui_type = "slider"; ui_label = "Tonal contrast"; ui_category = "1. Look";
 ui_min = 0.0; ui_max = 0.75; ui_step = 0.01;
 ui_tooltip = "Deepens lower midtones. Zero disables the base S-curve.";
> = 0.4;
uniform float Brilliance <
 ui_type = "slider"; ui_label = "Highlight brilliance"; ui_category = "1. Look";
 ui_min = 0.0; ui_max = 0.4; ui_step = 0.01;
 ui_tooltip = "Raises upper-midtones toward white without moving white or clipping the tone curve.";
> = 0.18;
uniform float Brightness <
 ui_type = "slider"; ui_label = "Brightness trim (stops)"; ui_category = "1. Look";
 ui_min = -0.5; ui_max = 0.5; ui_step = 0.01;
 ui_tooltip = "Bounded exposure adjustment. Preserves black and white; not photographic exposure.";
> = 0.0;
uniform float ShadowProtection <
 ui_type = "slider"; ui_label = "Shadow protection"; ui_category = "1. Look";
 ui_min = 0.0; ui_max = 1.0; ui_step = 0.01;
 ui_tooltip = "Protects near-black detail without raising absolute black.";
> = 0.85;
uniform float Fine <
 ui_type = "slider"; ui_label = "Fine detail"; ui_category = "2. Local contrast";
 ui_min = 0.0; ui_max = 0.5; ui_step = 0.01;
 ui_tooltip = "Contrast below the smallest analysis scale.";
> = 0.12;
uniform float Medium <
 ui_type = "slider"; ui_label = "Medium detail"; ui_category = "2. Local contrast";
 ui_min = 0.0; ui_max = 0.6; ui_step = 0.01;
 ui_tooltip = "Contrast between fine and medium scales. Main shape/texture control.";
> = 0.25;
uniform float Broad <
 ui_type = "slider"; ui_label = "Broad detail"; ui_category = "2. Local contrast";
 ui_min = 0.0; ui_max = 0.5; ui_step = 0.01;
 ui_tooltip = "Contrast between medium and broad scales. Higher settings may produce halos.";
> = 0.18;
uniform float Adaptation <
 ui_type = "slider"; ui_label = "Local illumination compression"; ui_category = "2. Local contrast";
 ui_min = 0.0; ui_max = 0.25; ui_step = 0.01;
 ui_tooltip = "Gently brightens locally dark regions and restrains bright regions. Zero disables.";
> = 0.04;
uniform float Radius <
 ui_type = "slider"; ui_label = "Analysis radius (1080p pixels)"; ui_category = "2. Local contrast";
 ui_min = 2.0; ui_max = 6.0; ui_step = 0.25;
 ui_tooltip = "Fine radius; medium = 4x, broad = 12x. Scales with output height.";
> = 3.0;
uniform float EdgeProtection <
 ui_type = "slider"; ui_label = "Bilateral edge protection"; ui_category = "3. Artifact control";
 ui_min = 0.0; ui_max = 1.0; ui_step = 0.01;
 ui_tooltip = "Higher values reduce mixing across brightness boundaries; can weaken detail enhancement.";
> = 0.75;
uniform float HaloProtection <
 ui_type = "slider"; ui_label = "Strong-edge suppression"; ui_category = "3. Artifact control";
 ui_min = 0.0; ui_max = 1.0; ui_step = 0.01;
 ui_tooltip = "Reduces local enhancement at high-contrast edges and HUD text.";
> = 0.85;
uniform float HighlightProtection <
 ui_type = "slider"; ui_label = "Highlight detail protection"; ui_category = "3. Artifact control";
 ui_min = 0.0; ui_max = 1.0; ui_step = 0.01;
 ui_tooltip = "Reduces local exposure changes near white to keep bright surfaces smooth.";
> = 0.75;
uniform float NoiseFloor <
 ui_type = "slider"; ui_label = "Noise threshold (stops)"; ui_category = "3. Artifact control";
 ui_min = 0.0; ui_max = 0.15; ui_step = 0.005;
 ui_tooltip = "Gates tiny log-luminance differences. Increase for noisy or grainy content.";
> = 0.025;
uniform float Sharpen <
 ui_type = "slider"; ui_label = "Micro sharpening"; ui_category = "3. Artifact control";
 ui_min = 0.0; ui_max = 0.3; ui_step = 0.01;
 ui_tooltip = "Small additional 3x3 detail boost with bounded overshoot. Zero if using another sharpener.";
> = 0.06;
uniform float Vibrance <
 ui_type = "slider"; ui_label = "Vibrance"; ui_category = "4. Color and output";
 ui_min = 0.0; ui_max = 0.3; ui_step = 0.01;
 ui_tooltip = "Adds chroma mainly to less saturated colors. Zero preserves RGB ratios before gamut mapping.";
> = 0.06;
uniform float Dither <
 ui_type = "slider"; ui_label = "Static dither (8-bit steps)"; ui_category = "4. Color and output";
 ui_min = 0.0; ui_max = 1.0; ui_step = 0.05;
 ui_tooltip = "Subtle monochrome dither. Zero removes added noise; no frame-varying shimmer.";
> = 0.35;
uniform float SplitPosition <
 ui_type = "slider"; ui_label = "Comparison position"; ui_category = "5. Compare";
 ui_min = 0.0; ui_max = 1.0; ui_step = 0.01;
 ui_tooltip = "Original on left; processed on right when comparison is enabled.";
> = 0.5;
uniform bool SplitView < ui_label = "Split-screen comparison"; ui_category = "5. Compare"; > = false;
uniform int View <
 ui_type = "combo"; ui_label = "View"; ui_category = "5. Compare";
 ui_items = "Final image\0Local exposure map\0Gamut compression map\0";
 ui_tooltip = "Exposure map: neutral gray = no change, light = brighter, dark = darker. Gamut map: white = more compression.";
> = 0;
texture2D InputTexture : COLOR;
sampler2D InputSampler
{
 Texture = InputTexture; AddressU = CLAMP; AddressV = CLAMP;
 MinFilter = LINEAR; MagFilter = LINEAR; MipFilter = POINT; SRGBTexture = false;
};
#if !_FHDRA_HDR
texture2D FineXTexture { Width = BUFFER_WIDTH; Height = BUFFER_HEIGHT; Format = RG32F; };
sampler2D FineXSampler
{
 Texture = FineXTexture; AddressU = CLAMP; AddressV = CLAMP;
 MinFilter = LINEAR; MagFilter = LINEAR; MipFilter = POINT; SRGBTexture = false;
};
texture2D FineYTexture { Width = BUFFER_WIDTH; Height = BUFFER_HEIGHT; Format = RG32F; };
sampler2D FineYSampler
{
 Texture = FineYTexture; AddressU = CLAMP; AddressV = CLAMP;
 MinFilter = LINEAR; MagFilter = LINEAR; MipFilter = POINT; SRGBTexture = false;
};
texture2D MidXTexture { Width = BUFFER_WIDTH; Height = BUFFER_HEIGHT; Format = RG32F; };
sampler2D MidXSampler
{
 Texture = MidXTexture; AddressU = CLAMP; AddressV = CLAMP;
 MinFilter = LINEAR; MagFilter = LINEAR; MipFilter = POINT; SRGBTexture = false;
};
texture2D MidYTexture { Width = BUFFER_WIDTH; Height = BUFFER_HEIGHT; Format = RG32F; };
sampler2D MidYSampler
{
 Texture = MidYTexture; AddressU = CLAMP; AddressV = CLAMP;
 MinFilter = LINEAR; MagFilter = LINEAR; MipFilter = POINT; SRGBTexture = false;
};
texture2D BroadXTexture { Width = BUFFER_WIDTH; Height = BUFFER_HEIGHT; Format = RG32F; };
sampler2D BroadXSampler
{
 Texture = BroadXTexture; AddressU = CLAMP; AddressV = CLAMP;
 MinFilter = LINEAR; MagFilter = LINEAR; MipFilter = POINT; SRGBTexture = false;
};
texture2D BroadYTexture { Width = BUFFER_WIDTH; Height = BUFFER_HEIGHT; Format = RG32F; };
sampler2D BroadYSampler
{
 Texture = BroadYTexture; AddressU = CLAMP; AddressV = CLAMP;
 MinFilter = LINEAR; MagFilter = LINEAR; MipFilter = POINT; SRGBTexture = false;
};
#endif
float Decode(float c) { return c <= 0.04045 ? c / 12.92 : pow(max((c + 0.055) / 1.055, 0.0), 2.4); }
float Encode(float c) { return c <= 0.0031308 ? c * 12.92 : 1.055 * pow(max(c, 0.0), 1.0 / 2.4) - 0.055; }
float3 DecodeRGB(float3 c) { return float3(Decode(c.r), Decode(c.g), Decode(c.b)); }
float3 EncodeRGB(float3 c) { return float3(Encode(c.r), Encode(c.g), Encode(c.b)); }
float Luma(float3 c) { return dot(c, float3(0.2126, 0.7152, 0.0722)); }
float LogLuma(float2 uv) { return log2(Luma(DecodeRGB(saturate(tex2D(InputSampler, uv).rgb))) + 0.00001); }
float SoftLimit(float v, float limit) { return v * limit / (limit + abs(v)); }
float Gate(float v) { return smoothstep(NoiseFloor, NoiseFloor + 0.06, abs(v)); }
float BoundedExposure(float y, float stops)
{
 float gain = exp2(stops);
 return y * gain / (1.0 + y * (gain - 1.0));
}
float Tone(float p)
{
 float protection = lerp(1.0, smoothstep(0.015, 0.18, p), ShadowProtection);
 float upper = lerp(1.0, 0.30, smoothstep(0.45, 0.70, p));
 float t = p + Contrast * p * (1.0 - p) * (2.0 * p - 1.0) * protection * upper;
 return t + Brilliance * t * (1.0 - t) * smoothstep(0.45, 0.85, t);
}
// Compress near gamut limits, preserving the headroom-capped linear luminance.
// The soft knee starts at 0.90 of the available headroom, or at the source pixel's
// own headroom use if that is higher, so in-gamut colors are not desaturated
// when nothing pushes them outward (e.g. pure primaries at zero amounts).
// Brightening is limited to y / max(rgb): the most a pixel can gain without
// clipping its brightest channel, so saturated highlights are not washed out.
float3 ColorReconstruct(float3 rgb, float y, float target, out float compression)
{
 if (y <= 0.0000001) { compression = 0.0; return float3(target, target, target); }
 float high = max(rgb.r, max(rgb.g, rgb.b));
 float low = min(rgb.r, min(rgb.g, rgb.b));
 target = min(target, y / max(high, 0.000001));
 float3 scaled = rgb * (target / y);
 float saturation = (high - low) / max(high, 0.000001);
 float3 chroma = (scaled - target) * (1.0 + Vibrance * (1.0 - saturation));
 float positive = max(chroma.r, max(chroma.g, chroma.b)) / max(1.0 - target, 0.000001);
 float negative = -min(chroma.r, min(chroma.g, chroma.b)) / max(target, 0.000001);
 float use = max(positive, negative);
 float sourcePositive = (high - y) / max(1.0 - y, 0.000001);
 float sourceNegative = (y - low) / max(y, 0.000001);
 float knee = clamp(max(sourcePositive, sourceNegative), 0.90, 0.9999);
 float compressed = use;
 if (use > knee) compressed = knee + (1.0 - knee) * (1.0 - exp(-(use - knee) / (1.0 - knee)));
 float factor = min(1.0, compressed / max(use, 0.000001));
 compression = 1.0 - factor;
 return saturate(target + chroma * factor);
}
void VS(uint id : SV_VertexID, out float4 position : SV_Position, out float2 uv : TEXCOORD0)
{
 uv = float2(id == 2 ? 2.0 : 0.0, id == 1 ? 2.0 : 0.0);
 position = float4(uv * float2(2.0, -2.0) + float2(-1.0, 1.0), 0.0, 1.0);
}
#if !_FHDRA_HDR
float Weight(float i, float difference)
{
 float sigma = lerp(1.50, 0.25, EdgeProtection);
 float n = i / float(_FHDRA_TAPS);
 float r = difference / sigma;
 return exp2(-6.49212768 * n * n - 0.72134752 * r * r);
}
float2 FineHorizontal(float4 pos : SV_Position, float2 uv : TEXCOORD0) : SV_Target
{
 float center = LogLuma(uv);
 float total = center, weights = 1.0;
 float stride = Radius * (BUFFER_HEIGHT / 1080.0) * BUFFER_RCP_WIDTH / float(_FHDRA_TAPS);
 [unroll]
 for (int i = -_FHDRA_TAPS; i <= _FHDRA_TAPS; ++i)
 {
  if (i != 0)
  {
   float value = LogLuma(uv + float2(float(i) * stride, 0.0));
   float w = Weight(float(i), value - center);
   total += value * w; weights += w;
  }
 }
 return float2(total / weights, center);
}
float2 Filter(sampler2D source, float2 uv, float2 direction, float scale)
{
 float2 center = tex2D(source, uv).rg;
 float total = center.r, weights = 1.0;
 float2 stride = direction * Radius * scale * (BUFFER_HEIGHT / 1080.0) / float(_FHDRA_TAPS);
 [unroll]
 for (int i = -_FHDRA_TAPS; i <= _FHDRA_TAPS; ++i)
 {
  if (i != 0)
  {
   float2 value = tex2D(source, uv + float(i) * stride).rg;
   float w = Weight(float(i), value.g - center.g);
   total += value.r * w; weights += w;
  }
 }
 return float2(total / weights, center.g);
}
float2 FineVertical(float4 pos : SV_Position, float2 uv : TEXCOORD0) : SV_Target
{ return Filter(FineXSampler, uv, float2(0.0, BUFFER_RCP_HEIGHT), 1.0); }
float2 MidHorizontal(float4 pos : SV_Position, float2 uv : TEXCOORD0) : SV_Target
{ return Filter(FineYSampler, uv, float2(BUFFER_RCP_WIDTH, 0.0), 4.0); }
float2 MidVertical(float4 pos : SV_Position, float2 uv : TEXCOORD0) : SV_Target
{ return Filter(MidXSampler, uv, float2(0.0, BUFFER_RCP_HEIGHT), 4.0); }
float2 BroadHorizontal(float4 pos : SV_Position, float2 uv : TEXCOORD0) : SV_Target
{ return Filter(MidYSampler, uv, float2(BUFFER_RCP_WIDTH, 0.0), 12.0); }
float2 BroadVertical(float4 pos : SV_Position, float2 uv : TEXCOORD0) : SV_Target
{ return Filter(BroadXSampler, uv, float2(0.0, BUFFER_RCP_HEIGHT), 12.0); }
#endif
float Hash(float2 p) { return frac(52.9829189 * frac(dot(p, float2(0.06711056, 0.00583715)))); }
float4 Composite(float4 position : SV_Position, float2 uv : TEXCOORD0) : SV_Target
{
 float4 original = tex2D(InputSampler, uv);
#if _FHDRA_HDR
 return original;
#else
 if (Strength <= 0.0 || (SplitView && uv.x < SplitPosition)) return original;
 float3 rgb = DecodeRGB(saturate(original.rgb));
 float y = Luma(rgb);
 float p = Encode(y);
 float logY = log2(y + 0.00001);
 float fineBase = tex2D(FineYSampler, uv).r;
 float midBase = tex2D(MidYSampler, uv).r;
 float broadBase = tex2D(BroadYSampler, uv).r;
 float a = logY - fineBase;
 float b = fineBase - midBase;
 float c = midBase - broadBase;
 float local = Fine * a * Gate(a) + Medium * b * Gate(b) + Broad * c * Gate(c);
 local = SoftLimit(local, 0.65);
 // Reference middle gray is 18% linear. This is spatial, not temporal adaptation.
 float adapt = SoftLimit(Adaptation * (log2(0.18 + 0.00001) - broadBase), 0.25);

 float2 pixel = float2(BUFFER_RCP_WIDTH, BUFFER_RCP_HEIGHT);
 float lo = logY, hi = logY, blur = 4.0 * logY;
 [unroll]
 for (int j = -1; j <= 1; ++j)
 {
  [unroll]
  for (int i = -1; i <= 1; ++i)
  {
   if (i != 0 || j != 0)
   {
    float v = LogLuma(uv + float2(i, j) * pixel);
    blur += v * ((i == 0 || j == 0) ? 2.0 : 1.0);
    lo = min(lo, v); hi = max(hi, v);
   }
  }
 }
 float edgeMask = 1.0 - HaloProtection * smoothstep(0.60, 2.50, hi - lo);
 float highpass = logY - blur / 16.0;
 float sharp = SoftLimit(Sharpen * highpass * Gate(highpass), 0.08);
 float margin = 0.04 * (hi - lo);
 sharp = clamp(sharp, lo - margin - logY, hi + margin - logY);
 float shadowMask = smoothstep(0.015, 0.12, p);
 float highlightMask = 1.0 - HighlightProtection * smoothstep(0.65, 0.98, p);
 float stops = ((local + sharp) * edgeMask + adapt) * shadowMask * highlightMask;
 stops = clamp(stops, -0.80, 0.80);

 float target = BoundedExposure(Decode(Tone(p)), stops + Brightness);
 float compression;
 float3 graded = EncodeRGB(ColorReconstruct(rgb, y, target, compression));
 if (View == 1) return float4(float3(0.5, 0.5, 0.5) + stops * 0.5, original.a);
 if (View == 2) return float4(compression, compression, compression, original.a);
 float2 coord = floor(position.xy);
 float noise = Hash(coord) - Hash(coord + float2(37.0, 17.0));
 float minimum = min(graded.r, min(graded.g, graded.b));
 float maximum = max(graded.r, max(graded.g, graded.b));
 float ditherMask = smoothstep(0.0, 2.0 / 255.0, min(minimum, 1.0 - maximum));
 graded += noise * (Dither / 255.0) * ditherMask;
 return float4(lerp(original.rgb, saturate(graded), Strength), original.a);
#endif
}
}
technique FakeHDR_Advanced <
 ui_label = "FakeHDR Advanced";
 ui_tooltip = "SDR HDR-look grading: three log-luminance scales, protected highlights, soft gamut compression. Disable other FakeHDR/IPS Depth effects.";
>
{
#if !_FHDRA_HDR
 pass FineX
 {
  VertexShader = FHDRA::VS; PixelShader = FHDRA::FineHorizontal;
  RenderTarget = FHDRA::FineXTexture; SRGBWriteEnable = false;
 }
 pass FineY
 {
  VertexShader = FHDRA::VS; PixelShader = FHDRA::FineVertical;
  RenderTarget = FHDRA::FineYTexture; SRGBWriteEnable = false;
 }
 pass MidX
 {
  VertexShader = FHDRA::VS; PixelShader = FHDRA::MidHorizontal;
  RenderTarget = FHDRA::MidXTexture; SRGBWriteEnable = false;
 }
 pass MidY
 {
  VertexShader = FHDRA::VS; PixelShader = FHDRA::MidVertical;
  RenderTarget = FHDRA::MidYTexture; SRGBWriteEnable = false;
 }
 pass BroadX
 {
  VertexShader = FHDRA::VS; PixelShader = FHDRA::BroadHorizontal;
  RenderTarget = FHDRA::BroadXTexture; SRGBWriteEnable = false;
 }
 pass BroadY
 {
  VertexShader = FHDRA::VS; PixelShader = FHDRA::BroadVertical;
  RenderTarget = FHDRA::BroadYTexture; SRGBWriteEnable = false;
 }
#endif
 pass Finish
 {
  VertexShader = FHDRA::VS; PixelShader = FHDRA::Composite;
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
