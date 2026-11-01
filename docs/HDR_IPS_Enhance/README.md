# HDR IPS Enhance 1.0.1 — independently audited

An original, standalone ReShade FX effect for **final-buffer native HDR**. It adjusts perceived contrast and color without replacing a game's HDR tone mapper. Includes full source, three artistic presets, diagnostics, and reproducible tests. No third-party shader pack, LUT, depth access, or native add-on is required.

**Start with Natural HDR, High quality. The supplied presets initially bypass processing until you establish the input color contract.** This is intentional: Windows HDR and NVIDIA's RGB 10 bpc setting do not identify the encoding of an arbitrary sampled buffer.

See **AUDIT.md** for the three evidence-based fixes and **VALIDATION.md** for the revised 23-test CPU and 127-configuration FX results. Artistic presets and controls are unchanged.

## Installation and first use

1. Use a current ReShade release for the game's actual rendering API. This source uses facilities documented in ReShade 5.1 and later; its front end was validated against the specific upstream source revision listed in VALIDATION.md. Target D3D11/D3D12 or equivalent modern rendering. ReShade 5.1 itself was not tested.
2. Copy **both** files from `Shaders/` into the game's `reshade-shaders/Shaders/` directory: `HDR_IPS_Enhance.fx` and `HDRIPS_Math.fxh`. Keep them together; no ReShade.fxh is needed.
3. Put the three `.ini` files from `Presets/` somewhere convenient, such as beside the game's existing ReShade presets. In ReShade's Home tab, select `Natural_HDR.ini` and enable `HDR IPS Enhance`.
4. Establish the contract below. Then either leave Input color space on Auto and enable **Auto: sampled buffer contract verified**, or choose the verified explicit PQ/scRGB mode. If it is uncertain, use Bypass. Each supplied preset resets Auto verification to off; establish your game-specific contract again after loading it and save your own preset.
5. Keep RTX Dynamic Vibrance, RTX HDR, other color filters, ReShade tone mappers and additional contrast/saturation shaders disabled initially. Native HDR is the intended source. Combining filters requires retuning: their effects interact through luminance, saturation, and gamut boundaries.

The effect has no automatic exposure, frame history, temporal adaptation, sharpening, or added dithering. It affects any HUD already composited into the sampled frame.

## Establish the input/output contract

The effect reads `texture2D : COLOR` through the non-sRGB resource view, uses integer point fetches for the original signal, and writes back in **the same encoding**. `SRGBTexture=false`, `SRGBWriteEnable=false`, and blending is disabled. Alpha always comes from the original sample. The guide pass writes only its private texture. These choices follow the official FX semantics [2]; the current runtime creates a color-copy resource matching the effect permutation's format and chooses its non-sRGB/sRGB SRV according to the sampler flag [3].

| Verified sampled COLOR contract | Mode | Output written by this effect |
|---|---|---|
| Full-range RGB ST 2084 PQ, D65 BT.2020 primaries | HDR10 PQ / BT.2020 | Full-range RGB ST 2084 PQ / BT.2020 |
| Linear extended RGB, BT.709 primaries, 1.0 = nominal 80 nits | Linear scRGB | Same signed extended linear scRGB |
| Unknown, HLG, SDR, studio-range PQ, linear BT.2020, custom HDR scale, pre-tone-map scene buffer | Bypass | Original sampled float4 |

ReShade's `BUFFER_COLOR_SPACE` describes **presentation**: 0 unknown, 1 sRGB, 2 scRGB, 3 HDR10 ST2084, 4 HDR10 HLG [2]. The effect displays the supported reported presentation type above its controls. Auto accepts only 2 or 3 and only after the verification checkbox. It does not infer transfer functions from `BUFFER_COLOR_BIT_DEPTH`, RGB10A2/FP16 format, histograms, or Windows HDR status.

To verify a normal installation:

- Establish that ReShade renders at the ordinary final presentation point, after the game's HDR mapping, with no relocated effects, swapchain conversion, or earlier shader changing encoding. In this standard path the sampled COLOR copy represents the final game backbuffer [3]. Ensure the game actually uses the signaled color space.
- Match that final buffer with the game's renderer documentation, a frame capture/resource inspection, or a known renderer implementation. For DXGI, `RGB_FULL_G2084_NONE_P2020` means full-range PQ/BT.2020; `RGB_FULL_G10_NONE_P709` identifies linear BT.709 scRGB [4]. Read the **resource and SRV actually bound to the effect**, and the last producer/conversion, when inspecting an intermediate or modified pipeline. Format alone cannot settle this.
- A trusted linear-scRGB test patch with RGB=1 should correspond to nominal 80-nit gray before downstream display mapping; PQ code approximately 0.508078 represents 100 nits. A value greater than 1 or a negative component can support a linear extended-range interpretation, but their absence proves nothing. The false-color view is a sanity check **after** establishing encoding, not a detector.
- If an add-on injects elsewhere, its advertised buffer contract takes precedence over swapchain metadata. The inspected runtime deliberately assigns unknown color space to certain non-backbuffer effect permutations [3]. Leave Auto unverified unless the exact target is understood. No add-on is necessary for the intended final-buffer path.

Reload ReShade effects after an HDR/output-mode change. Revalidate after changing injection, swapping HDR mods, or adding an encoding conversion. The shader cannot discover a game's arbitrary render graph, override OS color management, or change HDR metadata.

## Display limits and calibration

A shader cannot lower a display's physical black level, eliminate IPS glow, or
add local dimming capability. Manufacturer specifications are not measurements
of a particular display's black, peak brightness or gamut. The effect does not
estimate black level, infer exact panel primaries, or use a nominal display
peak as a hard clipping threshold.

It can redistribute already available signal levels to improve visible
separation. This curve leaves its protected near-black region intact, increases
the contrast slope around an anchor, and returns high highlights to the game's
existing mapping. Lowering every shadow would hide information rather than
necessarily improve useful contrast.

Use the game's own HDR calibration with this effect bypassed. Set black visibility and clipping patterns as the game instructs; choose a comfortable diffuse/paper white. Do not treat a manufacturer's nominal brightness specification as a measured calibration result. Restore the shader afterward. A dedicated source paper-white, display-peak or measured black-level control would be misleading here, so none is provided.

## Color pipeline

PQ uses the ST 2084 EOTF and its inverse, with the exact standard rational constants: `m1=2610/16384`, `m2=2523/32`, `c1=3424/4096`, `c2=2413/128`, `c3=2392/128`. Version 1.0.1 evaluates algebraically equivalent expressions with better observed float32 behavior; see AUDIT.md. Decoded components are expressed in cd/m² (nits), on the standard 0–10000 range [5]. Code zero decodes to zero; the encoder explicitly emits code zero at zero luminance. It does not sRGB-decode PQ. Out-of-domain PQ pixels bypass instead of being silently reinterpreted.

scRGB components are multiplied by **80**, then converted from linear BT.709 to linear BT.2020. This is the Windows HDR nominal luminance convention [6], not a measurement of emitted screen light. The inverse conversion divides by 80. Negative BT.709 components and values above 1 remain signed/extended. Positive-luminance pixels may be rescaled without clipping those components. Nonpositive-luminance pixels bypass unchanged. Finite signals that overflow processing or output conversion also return the original sample; ordinary signed/extended values are not clipped. Color expansion leaves source colors beyond the P3 proxy alone. No arbitrary 0–1 clamp is applied to linear RGB.

All shaping uses `Y=0.2627R+0.6780G+0.0593B` in linear BT.2020 component-nit units. Master strength blends original and processed RGB in linear light. There is no second scene-to-display transform, peak remapping, or exposure normalization. The 10000-nit bound is used only to prevent **new** gain/chroma from exceeding PQ's encoding domain. It is not a display-peak target or a 400-nit shoulder.

The small color adjustment uses a constant-Y linear chroma ray: `chroma=RGB-Y`, `RGB'=RGB+k*chroma`. Thus it preserves defined luminance and linear chromatic direction around gray. I considered ICtCp, which BT.2100 defines for HDR [5], but chose this simpler operation because it needs no nonlinear signed-LMS extension for scRGB and makes luminance preservation and incremental bounds explicit. **It is not perceptually uniform or a claim of constant perceived hue.** Restrained strengths and boundary protection are essential, especially for strong blues.

Protection fades enhancement near gray, in dark noise-prone regions, in highlights, and as saturation approaches a P3-D65 proxy boundary. The P3 matrix is derived from standardized primaries with D65 white [7]. BT.2020 is a signal container, not an assumed display gamut. P3 is only a conservative enhancement guard, not a calibration profile or a promise of panel coverage. Source colors outside it are retained rather than forced inside it.

The proposed **addition** has a smooth knee at half its available chroma budget and asymptotically approaches the boundary. PQ component bounds are also included in that budget. This avoids hard per-channel clipping and preserves existing colors at zero enhancement. It does not repair source clipping or replace downstream gamut mapping. There is no semantic skin detection.

## Global and local contrast

The global curve is piecewise cubic displacement in `log2(Y)`. Let `L=log2(toe)`, `A=log2(anchor)`, `H=log2(highEnd)`. In the lower segment, `t=(log2(Y)-L)/(A-L)` and displacement is `-c*(A-L)*t²*(1-t)`. In the upper segment, `t=(log2(Y)-A)/(H-A)` and displacement is `c*(H-A)*t*(1-t)²`. The output is `Y*2^displacement`.

The curve fixes toe, anchor and highEnd, and is identity outside the two segments. Its log-domain derivative is at least `1-c/3`, so the allowed contrast range 0–0.5 is strictly monotonic. The curve is C1 at its joins. This is a modest anchored contrast adjustment, not a display tone mapper. Highly saturated PQ pixels can receive less positive gain when required to remain within the encoding domain.

The separate local stage gathers an original **log-luminance** guide with spatial and range weights. Range scale is 0.75 stop. Residual is bounded with `0.5*r/(0.5+abs(r))`, so the requested local correction is less than `LocalContrast/2` stops before shadow/highlight masks. It is then constrained to sampled neighborhood log-luminance extrema. Flat fields remain flat; large brightness edges receive little cross-edge influence. Low-contrast halos and sparse-kernel artifacts remain possible; this is a small-radius bilateral detail stage, not multiscale photographic local tone mapping. It cannot guarantee frame-average brightness conservation. At a local strength of 0.16 the pre-mask limit is 0.08 stop, about 5.7% gain; master strength reduces the visible change further.

## Controls and artistic presets

| Control | Purpose | Conservative range |
|---|---|---|
| Master strength | Linear-light mix; exact original-sample return at zero | 0–1 |
| Global contrast | Anchored monotonic luminance curve; zero neutral | 0–0.5 |
| Midtone anchor | Invariant **source luminance**, not display calibration/paper white | 40–250 nits |
| Shadow protection | Untouched toe `2^(-10+10*s)` nits | 0–1 |
| Highlight protection | Identity return by `min(10000,anchor*2^(6-4.5*h))` source nits | 0–1 |
| Local contrast | Optional bounded bilateral detail; zero skips gathers | 0–0.5 |
| Local radius | Square-kernel half-width in actual render pixels | 1–24 px |
| Color enhancement | Protected constant-Y chroma addition | 0–0.3 |
| Saturation protection | Higher fades expansion earlier near P3 proxy saturation | 0–1 |
| Input color space | Verified Auto, explicit PQ, explicit scRGB, or Bypass | Contract selection |

These are starting looks, not validated display-calibration presets. Anchor is 100 source nits in all three; saturation protection and highlight protection are 0.90. Changing quality does not select an artistic preset.

| Preset | Master | Global | Shadow protect | Local | Radius | Color |
|---|---:|---:|---:|---:|---:|---:|
| Natural HDR | 0.70 | 0.10 | 0.85 | 0.08 | 6 px | 0.04 |
| IPS Depth HDR | 0.85 | 0.22 | 0.90 | 0.16 | 8 px | 0.06 |
| Rich Color HDR | 0.80 | 0.08 | 0.85 | 0.08 | 6 px | 0.16 |

At the common 100-nit anchor and 0.90 highlight protection, global changes end near 386 source nits. This is an artistic threshold derived from the formula, not an estimate of display peak brightness.

## Quality, resources and precision

Use ReShade's **Edit global preprocessor definitions** or the effect's preprocessor controls; reload after changes:

```text
HDRIPS_QUALITY=1
HDRIPS_ENABLE_LOCAL=1
HDRIPS_ENABLE_COLOR=1
```

| Quality definition | Bilateral taps/pixel | Passes | Total texture reads/pixel when active | Effect-owned intermediate memory at 3440×1440 |
|---|---:|---:|---:|---:|
| `HDRIPS_QUALITY=0` Normal | 9 (3×3) | 2 | 11 | 18.90 MiB |
| `HDRIPS_QUALITY=1` High, default | 25 (5×5) | 2 | 27 | 18.90 MiB |
| `HDRIPS_QUALITY=2` Ultra | 49 (7×7) | 2 | 51 | 18.90 MiB |
| `HDRIPS_ENABLE_LOCAL=0`, any quality | 0 | 1 | 1 | 0 |

Counts include one COLOR read in the guide pass, one in the final pass, and all guide taps including the center. They exclude ReShade's shared COLOR copy, driver allocation alignment, render-target stores, and any other effects. Setting Local contrast to zero skips its source read/gathers but still allocates its pass/texture; compiling it out removes both, confirmed by FX module inspection. Color expansion adds arithmetic, not texture reads; `HDRIPS_ENABLE_COLOR=0` removes its code and controls.

All tiers use the same radius, weights, range scale and strength. They approximate the same filter with denser coverage; output can differ slightly because of discretization, particularly at small radii and thin edges. Pixel offsets are rounded symmetrically; borders clamp to valid texel centers. No UV assumption depends on a 16:9 resolution.

The sole effect-owned texture is full-resolution **R32F log2(nits)** with one mip. At 3440×1440 it uses 19,814,400 bytes. There is no intermediate color render target or chain of quantized color passes. Shader math uses `float`, not `half`/`min16float`. The source and destination retain the game's actual format: often RGB10A2 PQ or RGBA16F scRGB, which the shader does not upgrade. A 10 bpc link setting neither proves the source transfer function nor specifies the precision of HDR intermediates.

The numerical guide test found R32F storage error of about `2.24e-7` stop versus a double guide, compared with `0.00186` stop for an R16F guide at maximum local strength in that test. This motivated R32F. CPU PQ float round-trip error was under 0.00226% across the sampled range; all 1024 normalized 10-bit codes decoded/re-encoded/requantized to themselves. GPU math implementations can differ. There are **no measured GPU timings or FPS claims**.

## Diagnostics and tuning

1. Calibrate in-game HDR with this effect bypassed. Verify the input contract. Load Natural HDR; confirm a true bypass with Master strength=0.
2. Use the original/effected split on a fixed view containing dark texture, a face or neutral material, and a bright highlight. Start with local contrast and color at zero; tune global contrast first. If useful dark texture disappears, increase Shadow protection or reduce Global contrast/Master strength. Do not compensate with a guessed panel black-level subtraction.
3. Move the anchor only if the important midtone becomes too bright/dim. The anchor is unchanged by the global curve. Signed correction shows where the adjustment is acting.
4. Add local contrast around 0.08–0.16, radius 6–8. Inspect bright objects against dark walls, thin text, foliage, and screen edges. Reduce strength or radius if a bright/dark rim appears. Quality improves coverage; it is not a stronger-look control.
5. Add color last. Check saturated red/blue lights, neutral grays, subtle gradients, and dark noise. Prefer more saturation protection to a stronger global saturation filter. Evaluate whole scenes and motion; these presets have not been visually tuned on your unit.

| Diagnostic | Meaning |
|---|---|
| Original left / effect right | Exact sampled original on the left; no overlaid divider |
| Source luminance | Bins below refer to **decoded pre-effect source Y**, not measured screen light |
| Signed luminance correction | Gray unchanged; blue darker, orange brighter; full color at ±0.25 stop, after master blend |
| Protection / compression activity | Red: fraction of requested positive gain removed by PQ-domain protection. Green: fraction of proposed chroma addition removed by its smooth budget. Blue: highlight-protection envelope, not a measured compression amount or display clipping detector |

False-color bins use lower-inclusive/upper-exclusive bounds: `<0.01` nit black; `0.01–0.1` violet; `0.1–1` blue; `1–10` cyan; `10–80` green; `80–203` yellow; `203–400` orange; `400–1000` red; `>=1000` magenta. Palette components are linear BT.709 with a maximum component of **100 nits**, then converted and encoded for the active output mode. Alpha remains original. Master zero and unsupported modes bypass diagnostics too. Neutral artistic settings bypass exactly in normal/split view; deliberately selecting a diagnostic displays that visualization.

## Validation and limitations

The supplied package's CPU and FX results are historical; see **VALIDATION.md**
for their scope and [`../../validation/HDR_IPS_Enhance/results/`](../../validation/HDR_IPS_Enhance/results/)
for machine-readable reports. New repository checks are summarized in
[`../../validation/RELEASE_VALIDATION.md`](../../validation/RELEASE_VALIDATION.md).
CPU testing, FX parsing/code generation, driver compilation and in-game visual
testing are distinct. No GPU driver compilation, performance measurement or
in-game visual testing is claimed for this integration.

Final PQ gradients were explicitly rounded to 10-bit PQ code values. The tested contrast curve reduced distinct codes in a shadow interval, as expected from redistributing fixed output precision; no inversions or jumps larger than one code occurred in the dense ramps. This does not prove absence of visible banding. No dithering is added because the final quantization/dither stage is not established for every supported path, particularly scRGB followed by Windows composition. If future pipeline-specific dithering is justified, PQ amplitude must be specified in normalized **PQ code space** (e.g. fractions of 1/1023), not as a fixed linear-nit offset.

No shader can restore already crushed/clipped source information. High contrast, multiple color processors, downstream clipping, and misidentified encoding can still produce poor results. Bypass is the appropriate choice for unsupported/custom contracts.

## Primary sources

The supplied package's source review was dated 2026-10-31. No display
measurements were performed or borrowed from reviews.
2. [Official ReShade FX language reference](https://github.com/crosire/reshade-shaders/blob/slim/REFERENCE.md) — presentation macros, COLOR semantic, samplers, formats, pass states and intrinsics.
3. [Official ReShade runtime source, inspected revision](https://github.com/crosire/reshade/blob/7bf9de8b33bcc76c3177007e65d73c72dd0f34c0/source/runtime.cpp) — macro injection around lines 1663–1665; COLOR bindings around 2762; effect color allocation around 3588; unknown non-backbuffer permutations around 4012. [DXGI swapchain implementation](https://github.com/crosire/reshade/blob/7bf9de8b33bcc76c3177007e65d73c72dd0f34c0/source/dxgi/dxgi_swapchain.cpp) — SetColorSpace1 handling.
4. [Microsoft DXGI_COLOR_SPACE_TYPE](https://learn.microsoft.com/en-us/windows/win32/api/dxgicommon/ne-dxgicommon-dxgi_color_space_type) — encoding/primary meanings; these enum numbers are not the ReShade macro's numbers.
5. [ITU-R BT.2100-3, February 2025](https://www.itu.int/rec/R-REC-BT.2100-3-202502-I/en), Tables 2, 4 and 7 — BT.2020 colorimetry, PQ EOTF/inverse, and ICtCp. The effect uses the inverse EOTF, not the scene-light OETF/OOTF.
6. [Microsoft: DirectX with Advanced Color](https://learn.microsoft.com/en-us/windows/win32/direct3darticles/high-dynamic-range) — scRGB, nominal 80-nit unit, extended signed range, FP16 composition and downstream output conversion.
7. [W3C CSS Color 4: conversion algorithms](https://www.w3.org/TR/css-color-4/#color-conversion-code) — standardized sRGB/BT.709, Display-P3/D65 and BT.2020 matrix definitions. Only linear-primary conversion is used; CSS transfer curves and gamut-mapping algorithms are not applied to this HDR signal.

Original effect code is MIT licensed; see
[`licenses/HDR_IPS_Enhance.txt`](../../licenses/HDR_IPS_Enhance.txt). Upstream
ReShade compiler source is not bundled. Its own license applies if you fetch it
to reproduce the FX tests.
