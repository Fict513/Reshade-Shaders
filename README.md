# FakeHDR Advanced

> **IPS Suite:** a coordinated single-effect pipeline based on IPS Depth v2,
> Selective Deband and Adaptive Clarity, with six combined presets. Start with
> [the IPS Suite guide](docs/IPS_Suite.md) and
> `Presets/IPS_Suite/IPS_Suite_RTX_Companion_High.ini`. The original standalone
> effects and older three-technique presets remain available; see
> [docs/Suite.md](docs/Suite.md). FakeHDR Advanced below is unchanged.

An SDR "HDR-look" post-processing shader for [ReShade](https://reshade.me) and GShade. It adds local contrast, a protected tone curve, highlight brilliance and soft gamut handling to an ordinary SDR image.

> **What it is not.** This is an artistic SDR effect. It does not produce HDR output and it **cannot restore detail that is already clipped** in the game's image. It processes the whole frame, so **HUD, menus and text are affected too**.

Version: **1.0.0** · License: MIT (see [LICENSE](LICENSE)) · File: `Shaders/FakeHDR_Advanced.fx`

## Attribution

Original implementation, inspired by the *purpose* of CeeJay.dk's [FakeHDR](https://github.com/Mortalitas/GShade/blob/master/Shaders/FakeHDR.fx). No source code from that shader is incorporated. Copyright (c) 2026 OpenAI, MIT license; the notice must stay with copies of the shader.

## Requirements

- ReShade (any version that supports `.fx` effects with `RG32F` render targets and `SV_VertexID`) or a GShade build based on it.
- No depth buffer, add-on, include file or external texture.
- A float32 render-target format with linear filtering. This is normal on desktop GPUs but was **not tested on any real GPU** (see [Validation](#validation)).

## Installation

**ReShade**

1. Copy `FakeHDR_Advanced.fx` into the game's `reshade-shaders\Shaders` folder (or whichever Effects search path your ReShade setup uses).
2. In the ReShade overlay, press **Reload**.
3. Enable **FakeHDR Advanced**.

**GShade**

1. Copy `FakeHDR_Advanced.fx` into `gshade-shaders\Shaders` (the folder that holds GShade's other `.fx` files).
2. Reload shaders in the GShade overlay and enable **FakeHDR Advanced**.

## Effect ordering

Place it **after** the game's own tone mapping and color grading and after any LUT or levels effect you use, and **before** effects that should not be locally contrast-enhanced, such as film grain, vignette, borders or a final sharpener. If you use an anti-aliasing effect, run it before this one so edges are already smooth. This is guidance from the design, not a tested compatibility matrix.

Do **not** stack it with:

- the original **FakeHDR** (it targets the same look; the effects compound),
- **IPS Depth / IPS Depth HQ** (it also applies local contrast and tone curves).

Disable those before enabling this shader. Other local-contrast, clarity or HDR-look effects will compound in the same way.

## Defaults

| Category | Control | Default | Range |
|---|---|---|---|
| 1. Look | Overall strength | 1.00 | 0–1 |
| | Tonal contrast | 0.40 | 0–0.75 |
| | Highlight brilliance | 0.18 | 0–0.40 |
| | Brightness trim (stops) | 0.00 | −0.5–0.5 |
| | Shadow protection | 0.85 | 0–1 |
| 2. Local contrast | Fine detail | 0.12 | 0–0.5 |
| | Medium detail | 0.25 | 0–0.6 |
| | Broad detail | 0.18 | 0–0.5 |
| | Local illumination compression | 0.04 | 0–0.25 |
| | Analysis radius (1080p pixels) | 3.0 | 2–6 |
| 3. Artifact control | Bilateral edge protection | 0.75 | 0–1 |
| | Strong-edge suppression | 0.85 | 0–1 |
| | Highlight detail protection | 0.75 | 0–1 |
| | Noise threshold (stops) | 0.025 | 0–0.15 |
| | Micro sharpening | 0.06 | 0–0.3 |
| 4. Color and output | Vibrance | 0.06 | 0–0.3 |
| | Static dither (8-bit steps) | 0.35 | 0–1 |
| 5. Compare | Split-screen comparison | off | |
| | Comparison position | 0.50 | 0–1 |
| | View | Final image | Final image / Local exposure map / Gamut compression map |

## Tuning

Start with the defaults, then use **Split-screen comparison** to judge the effect against the original.

- **More dramatic:** Medium detail 0.35, Broad detail 0.25, Highlight brilliance 0.25.
- **Dark areas lose visibility:** reduce *Tonal contrast*, raise *Shadow protection*, or use *Brightness trim*. The effect cannot lower your display's physical black.
- **Halos around bright/dark boundaries:** lower *Broad detail* or *Medium detail*, or raise *Bilateral edge protection* and *Strong-edge suppression*.
- **Grainy or noisy image looks gritty:** raise *Noise threshold* and lower *Fine detail* and *Micro sharpening*.
- **Already using another sharpener:** set *Micro sharpening* to 0.
- **Washed or over-saturated colors:** adjust *Vibrance*. Use the **Gamut compression map** view to see where colors are being pulled back into range.
- **See what the local exposure does:** use the **Local exposure map** view (neutral gray = no change, lighter = brighter, darker = darker).
- **Overall strength = 0** returns the original image but the filter passes still run. Disable the technique to remove its GPU cost entirely.

## Quality options

Set the preprocessor definition `FHDRA_QUALITY` (ReShade overlay → Preprocessor definitions, then reload). Default is `1`.

| `FHDRA_QUALITY` | Taps per filter axis | Texture fetches per output pixel (7 passes) |
|---|---|---|
| 0 | 17 | 114 |
| 1 (default) | 25 | 162 |
| 2 | 33 | 210 |

Higher quality adds samples (a smoother, more accurate filter), not more contrast. Fetch counts are counted from the shader source; **no frame-time or FPS figures have been measured**, and none are implied. Radius scales with output height, and very large radii use spaced taps.

## Design and memory cost

The technique runs **seven passes**:

| # | Pass | Output |
|---|---|---|
| 1 | `FineX` – horizontal joint-bilateral filter of log luminance | `RG32F` |
| 2 | `FineY` – vertical, fine scale | `RG32F` |
| 3 | `MidX` – horizontal, 4× radius | `RG32F` |
| 4 | `MidY` – vertical, medium scale | `RG32F` |
| 5 | `BroadX` – horizontal, 12× radius | `RG32F` |
| 6 | `BroadY` – vertical, broad scale | `RG32F` |
| 7 | `Finish` – combine bands, tone curve, color reconstruction, dither | back buffer |

Each filter scale is a cascaded, separable approximation of a bilateral filter (not an exact 2D bilateral). The smoothed signal is stored in R and the original log-luminance guidance in G.

**Memory:** six full-resolution `RG32F` render targets = **48 bytes per pixel**.

| Resolution | Working target storage |
|---|---|
| 1920×1080 | ≈ 94.9 MiB |
| 2560×1440 | ≈ 168.8 MiB |
| 3440×1440 | ≈ 226.8 MiB |
| 3840×2160 | ≈ 379.7 MiB |

These are the effect's own targets only, computed from the format and size; they exclude ReShade's other allocations.

## HDR color spaces

When ReShade reports an HDR presentation color space (`BUFFER_COLOR_SPACE` greater than 1: scRGB, HDR10 PQ, HDR10 HLG), the shader compiles to a **single pass-through pass** and allocates no filter targets. The shader assumes SDR sRGB/Rec.709 otherwise. If the color space is unknown (0), the macro is absent, or the game reports its non-sRGB output incorrectly, the shader cannot detect this and will process it as sRGB.

## Troubleshooting

| Symptom | Check |
|---|---|
| Effect missing from the list | Press Reload; confirm the file is in a configured Effects search path; read the ReShade log for compile errors. |
| Compile error mentioning `RG32F`, `SV_VertexID` or sampler state | The renderer/ReShade version may not support them; report the log. |
| No visible change | Strength is 0, the technique is below a disabled effect, or the game is in an HDR mode (bypass). |
| Result looks doubled or too strong | FakeHDR, IPS Depth or another local-contrast effect is also enabled. |
| HUD/menu text looks crunchy or haloed | Expected: the whole frame is processed. Raise *Strong-edge suppression*, lower detail sliders, or toggle the effect for menus. |
| Banding in gradients | Raise *Static dither* slightly; the dither is static (no shimmer). |
| Dark scenes too dark/contrasty | Lower *Tonal contrast*, raise *Shadow protection*. |
| High GPU load or low FPS | Set `FHDRA_QUALITY=0`, reduce resolution, or disable the technique. Strength 0 does not remove the cost. |

## Removal

1. Disable **FakeHDR Advanced** in the overlay (this stops all cost).
2. Delete `FakeHDR_Advanced.fx` from the `Shaders` folder.
3. Reload. Remove any saved `FHDRA_*` preprocessor definitions and `[FakeHDR_Advanced.fx]` presets entries if desired; they are harmless otherwise.

## Validation

See [validation/README.md](validation/README.md). Summary, for v1.0.0:

- Verified with the **actual ReShade FX preprocessor/parser** (ReShade commit `7bf9de8`) for qualities 0/1/2 and `BUFFER_COLOR_SPACE` 0–4, generating HLSL; GLSL generation was also checked for quality 1 in sRGB. This is shader-**code generation**.
- Generated HLSL compiled to DXBC (SM 5.0) with the Windows D3DCompiler for every entry point.
- Shader math and the complete pass chain executed on the D3D11 **WARP software device** with synthetic images.
- **Not tested:** GPU-driver compilation, ReShade's DX9/OpenGL/Vulkan back ends, GShade, any in-game use, visual quality comparisons, and performance.

## Changes from the supplied source

v1.0.0 is the supplied `FakeHDR_Advanced.fx` plus three small fixes found during review; see [RELEASE_NOTES.md](RELEASE_NOTES.md).
