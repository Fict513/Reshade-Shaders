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

## Shader catalog

The color-space contract below describes the shader implementation, not a
promise that every game's injection point uses that encoding. Unless a shader's
guide says otherwise, no external texture, include pack or native add-on is
required. Copy required `.fxh` files alongside their `.fx` files in the
configured ReShade `Shaders` path. Keep versions and presets distinct; choosing
a preset may replace the active technique list.

| Effect and source version | Purpose | Supported input/output contract | Required files / dependencies | Presets and quality | Guide |
|---|---|---|---|---|---|
| FakeHDR Advanced 1.0.0 | SDR local contrast and artistic tone shaping | SDR sRGB/Rec.709; reported HDR presentation spaces bypass; unknown presentation is treated as SDR | None beyond `Shaders/FakeHDR_Advanced.fx` | UI controls; no bundled effect preset | [Installation and tuning](#installation) |
| IPS Suite 1.2.0 | Coordinated contrast, selective deband, clarity and final dither | SDR sRGB/Rec.709; declared HDR spaces bypass; unknown is treated as SDR | `Shaders/IPS_Suite.fx` plus all three `.fxh` files in `Shaders/IPS_Suite/` | Six `Presets/IPS_Suite/` files; `IPS_SUITE_QUALITY` 0/1/2 and independent stage switches | [IPS Suite guide](docs/IPS_Suite.md) |
| Output Dither 1.0.0 | Optional static blue-noise finishing stage for a known later quantizer | Explicit matching SDR sRGB/BT.709 with 8- or 10-bit sRGB target assumption, or full-range PQ/BT.2020 with 10-bit PQ target assumption; unknown, mismatched and linear scRGB bypass | `Shaders/Output_Dither.fx`, sibling `Output_Dither_Core.fxh`, and `Textures/Output_Dither_BN128.png` in ReShade's texture search path | Manual controls; no bundled preset; `OUTPUT_DITHER_ENABLE=0` compiles out its texture and controls | [Installation, contracts and limitations](docs/Output_Dither/README.md) |
| IPS Depth v2.0 | SDR local contrast and tone shaping | SDR sRGB/Rec.709; declared HDR spaces bypass; unknown is treated as SDR | None beyond `Shaders/IPS_Depth_v2.fx` | Six `Presets/IPS_Depth_v2/` files; `IPSD2_QUALITY` 0/1/2 | [IPS Depth v2 guide](docs/IPS_Depth_v2.md) |
| Selective Deband 1.0 | Spatial, edge- and texture-gated gradient smoothing | SDR sRGB/Rec.709; declared HDR spaces bypass; unknown is treated as SDR | None beyond `Shaders/Selective_Deband.fx` | Six `Presets/Selective_Deband/` files; `SDB_QUALITY` 0/1/2 | [Selective Deband guide](docs/Selective_Deband.md) |
| Adaptive Clarity 1.0 | SDR noise- and edge-protected local detail enhancement | SDR sRGB/Rec.709; declared HDR spaces bypass; unknown is treated as SDR | None beyond `Shaders/Adaptive_Clarity.fx` | Six `Presets/Adaptive_Clarity/` files; `AC_QUALITY` 0/1/2 | [Adaptive Clarity guide](docs/Adaptive_Clarity.md) |
| HDR Bloom 1.0.0 | Restrained light diffusion over an already display-mapped image | Explicit verified full-range SDR sRGB/BT.709, HDR10 PQ/BT.2020, or linear signed scRGB/BT.709 at 80 nits/unit. Auto defaults to bypass; HLG and unverified/custom contracts are unsupported. | `Shaders/HDR_Bloom.fx` + sibling `HDR_Bloom_Math.fxh`; no external pack | Nine mode-specific `Presets/HDR_Bloom/` files; `HDRBLOOM_QUALITY` 0/1/2 | [HDR Bloom guide](docs/HDR_Bloom/README.md) |
| Adaptive Detail 1.0.0 | Two-band, luminance-driven sharpening | Explicit verified SDR sRGB/BT.709, full-range HDR10 PQ/BT.2020, or signed/extended linear scRGB/BT.709 at 80 nits/unit. Unknown/default and unsupported contracts bypass. | `Shaders/Adaptive_Detail.fx` + sibling `Adaptive_Detail_Core.fxh`; no external pack | Nine mode-specific `Presets/Adaptive_Detail/` files; `ADAPTIVE_DETAIL_QUALITY` 0/1/2 | [Adaptive Detail guide](docs/Adaptive_Detail/README.md) |
| HDR IPS Enhance 1.0.1 | Native-HDR contrast, local detail and restrained color enhancement | Verified full-range HDR10 PQ/BT.2020 or signed/extended linear scRGB/BT.709; SDR, HLG and unknown contracts bypass. Auto requires verification. | `Shaders/HDR_IPS_Enhance.fx` + sibling `HDRIPS_Math.fxh`; no external pack | Three native-HDR `Presets/HDR_IPS_Enhance/` files; `HDRIPS_QUALITY` 0/1/2 | [HDR IPS Enhance guide](docs/HDR_IPS_Enhance/README.md) |

### Overlap and starting combinations

**IPS Depth v2 and HDR IPS Enhance are distinct alternatives, not replacements.**
Both adjust global/local contrast, but IPS Depth v2 assumes SDR sRGB and bypasses
declared HDR; HDR IPS Enhance is for verified native PQ/scRGB and bypasses SDR.
Likewise, **Adaptive Clarity and Adaptive Detail overlap in local sharpening but
remain separate effects**: Adaptive Clarity is the existing SDR effect, while
Adaptive Detail has explicit SDR/PQ/scRGB contracts and a two-band correction.
No supplied source designates either pair as a replacement.

For SDR, choose either the single-effect **IPS Suite** or a deliberately tuned
subset of IPS Depth v2, Selective Deband and Adaptive Clarity. Avoid running
IPS Suite and those same standalone effects together. For verified HDR,
HDR IPS Enhance -> Adaptive Detail -> HDR Bloom is a source-based starting
order: contrast/detail before light diffusion. Both shaders preserve the
selected signal encoding by design, but this order and the combined effects
have **not** been tested in-game. Reconfirm the sampled `COLOR` and destination
contract after changing injection points or adding any effect that converts
encoding. Do not stack every shader by default; overlapping contrast, clarity,
sharpening and bloom can compound. HDR-specific input-contract and safe-bypass
details are in each linked guide.

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

**Optional Output Dither**

1. Copy `Output_Dither.fx` and `Output_Dither_Core.fxh` into a configured
   ReShade effect search path.
2. Copy `Output_Dither_BN128.png` into a configured ReShade texture search
   path. Preserve the filename and resolve any texture-load errors.
3. Reload effects. Select **Output Dither (static blue noise)** manually; no
   preset enables it. It defaults to bypass. Read the
   [contract and ordering guide](docs/Output_Dither/README.md) before clearing
   Master bypass or selecting an input/target pair.

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
