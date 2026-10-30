# IPS Suite

One SDR ReShade/GShade effect coordinates the supplied IPS Depth v2, Selective
Deband and Adaptive Clarity algorithms, in that order, with **selective dither
after clarity**. It uses one ordered technique, `IPS_Suite@IPS_Suite.fx`.
The original standalone shaders and their presets remain available. This is
an integration, not evidence that stacking effects improves appearance or
speed. Copyright (c) 2026 OpenAI, MIT; retain the included `LICENSE`.

## Installation

1. Copy `Shaders/IPS_Suite.fx` and the entire `Shaders/IPS_Suite/` include
   directory into your configured ReShade (or GShade) `Shaders` directory.
   The effect requires renderable and linearly filterable float textures,
   including `RGBA32F`; support depends on the renderer and GPU.
2. Copy `Presets/IPS_Suite/` somewhere permanent. Save your existing ReShade
   preset first: selecting a suite preset replaces its technique list.
3. Reload effects and select **`IPS_Suite_RTX_Companion_High.ini`** as an
   initial comparison. Wait for compilation, then use the suite's final
   split-screen control. Do not simultaneously enable the standalone versions,
   FakeHDR, or another debander/sharpener without deliberately comparing them.

The six files are `IPS_Suite_Balanced_Normal.ini`, `..._High.ini`,
`..._Ultra.ini`, and the corresponding `IPS_Suite_RTX_Companion_*` files.
They derive their slider values from the supplied individual presets; IPS
micro-sharpening and IPS dithering are removed from the suite, and Selective
Deband's dither moves to the final output. Normal/High/Ultra within each
style have identical artistic settings.

RTX Companion uses the supplied milder contrast and clarity values and adds
no saturation control. It does **not** detect, configure, or precisely
compensate for NVIDIA RTX Dynamic Vibrance or any other driver effect.

## Pipeline and controls

The Contrast group reads the original input and preserves IPS Depth's SDR tone,
fine/broad local-detail and edge/halo protections. The Debanding group reads
the **completed contrast output**, applying the supplied neighborhood,
paired-sample, texture and edge gates with bounded RGB corrections. The
Clarity group builds a **new guide from the debanded image**, then applies the
supplied noise-gated, direction-aware and bounded sharpener. No stale guide is
shared between stages. Source algorithms are kept in generated, auditable
include modules; `validation/generate_ips_suite_includes.py --check` checks
them against their standalone sources.

Each group has an independent runtime strength. Set a strength to zero for
identity through that stage, but its analysis passes and buffers may still
cost GPU time. Disable the technique or use compile-time definitions to
remove cost. The Output group has dither and two manual exclusion rectangles;
Diagnostics provides the final original/processed split and exclusion view.
The exclusion view is shown only while at least one stage strength is nonzero.

Set these **preprocessor definitions** in ReShade, then reload:

| Definition | Values and effect |
|---|---|
| `IPS_SUITE_QUALITY` | `0` Normal, `1` High (default), `2` Ultra. IPS taps per axis: 9/13/21; deband paired directions: 4/8/16; clarity wide-ring directions: 4/8/16. Sampling changes, not preset strengths. |
| `IPS_SUITE_CONTRAST` | `1` default; `0` removes the contrast stage, its analysis textures and passes. |
| `IPS_SUITE_DEBAND` | `1` default; `0` removes smoothing and its output-dither eligibility. |
| `IPS_SUITE_CLARITY` | `1` default; `0` removes the clarity guide and sharpening. |
| `IPS_SUITE_DITHER` | `1` default; `0` removes output noise and eligibility calculation. Dither is also inactive when debanding is disabled. |

If all three runtime strengths are zero, or all stages are compiled out, the
final pass returns the original sample directly, including alpha. Output alpha
always comes from the original sample; there is no temporal history or depth
dependency. These statements describe shader logic, not guarantees about
unrelated effects or swap-chain conversions outside the technique.

### Dithering and color scope

Selective Deband's eligibility and actual smoothing change are evaluated
before clarity; their combined factor travels in the debanded intermediate's
otherwise unused alpha. Clarity consumes its RGB only. A deterministic
two-hash monochrome spatial noise is added **after** clarity, weighted by that
factor and by final RGB headroom. Its magnitude is less than the dither slider
times one output code step: `1/255` for declared 8-bit and `1/1023` for
declared 10-bit output. It is zero for unknown or other bit depths, unchanged
or ineligible pixels, zero deband strength, protected rectangle interiors,
and black/white endpoints. This intentionally differs from the standalone
chain's dither-before-clarity and stricter bit-depth fallback. Dithering can
make quantization less objectionable, but **cannot recover lost information**;
it can also be visible or amplified by later effects.

The supplied color math assumes SDR sRGB/Rec.709. If ReShade declares
`BUFFER_COLOR_SPACE > 1` (HDR), the suite compiles to a single original-color
pass with no suite intermediates. Unknown/absent color space is treated as
SDR; an incorrectly reported HDR image cannot be detected. There is no HDR
conversion or automatic detection of display settings.

### Manual exclusions

Both rectangles default to disabled. Coordinates are normalized
left/top/right/bottom from the top left; swapped corners are accepted.
Pixels inside enabled rectangles are restored from the original input after
all effects, including dither; the feather fades that protection *outside*
each rectangle, and split-screen is also applied at the final output. Alpha
is always restored. This is not HUD detection.

**Boundary limitation:** intermediate filters still sample and process the
whole image, including rectangle interiors. Restoring final pixels does not
prevent HUD colors or text from influencing nearby unprotected pixels, nor
does it protect intermediate analysis. Expand rectangles and feather as
needed, or disable the suite for problematic UI. The exclusion view visualizes
the final restoration mask, not contamination.

## Passes and texture memory

Only the final pass writes the back buffer, so the original `COLOR` semantic
remains available for comparisons, alpha and restoration without a separate
suite-owned input texture. ReShade may itself maintain a back-buffer copy:
that allocation and all driver overhead are **not included** below.

At 3440×1440, with all stages on:

| Suite texture | Format | Resolution | Purpose | MiB |
|---|---|---|---|---:|
| `LumaTexture` | R16F | full | original input's encoded linear-luminance guide | 9.45 |
| `FineXTexture` | RG16F | full | horizontal fine base and guide | 18.90 |
| `FineYTexture` | R16F | full | vertical fine base | 9.45 |
| `BroadPrepTexture`, `BroadXTexture`, `BroadYTexture` | RGBA16F each | half, rounded up | broad base, guide and edge confidence through preparation and filters | 9.45 each |
| `ContrastTexture` | RGBA32F | full | completed contrast output for later stages | 75.59 |
| `DebandTexture` | RGBA32F | full | completed deband RGB and dither eligibility in alpha | 75.59 |
| `GuideTexture` | R32F | full | fresh encoded linear-luminance guide for clarity | 18.90 |

The stage-output textures are allocated only when a later stage needs them;
the last effect runs in the output pass. RGBA32F avoids an extra half-float
rounding of color and eligibility between effects. IPS's original half-float
analysis targets and clarity's R32F guide are retained. The CPU gradient
experiments below compare this choice against a half-float counterfactual;
they are not GPU format-support or visual tests.

| Compiled SDR stages | Passes | Suite-owned texture MiB |
|---|---:|---:|
| None | 1 | 0 |
| Contrast | 7 | 66.14 |
| Deband | 1 | 0 |
| Clarity | 2 | 18.90 |
| Contrast + Deband | 8 | 141.72 |
| Contrast + Clarity | 9 | 160.62 |
| Deband + Clarity | 3 | 94.48 |
| All three | 10 | 236.21 |

Quality and dither definitions do not change these layouts; HDR always uses
one pass and zero suite intermediates. Half-resolution dimensions are
`ceil(width/2) × ceil(height/2)`, so odd sizes have slightly different
bytes-per-pixel. Counts describe structure, not speed or measured GPU memory.

## Tuning and limitations

Start with RTX Companion High. Compare in representative dark scenes, skies,
fine textures, high-contrast edges and UI, and in motion. Reduce Clarity
strength or increase its noise threshold if bands, grain or edge outlines
become more visible. Reduce Deband strength or thresholds if subtle texture
disappears; it cannot reliably distinguish every real contour from banding.
Reduce Contrast or raise shadow protection if dark areas look crushed.
Disable or reduce dither if it is visible. The spatial algorithms cannot
recover clipped highlights or lost shadow detail, and fixed noise can be
noticeable in motion. No timing, GPU compatibility or universal quality
improvement is claimed.

## Validation and reproducibility

Run with Python 3, NumPy and SciPy installed:

```sh
python validation/validate_ips_suite.py
python validation/validate_ips_suite.py --reshade-source /path/to/reshade
```

The first command runs source/preset generation checks and CPU reference
tests only; it reports the FX checks as not run. The second additionally
requires a C++17 `g++`-compatible compiler and a checkout of
`crosire/reshade` at `7bf9de8b33bcc76c3177007e65d73c72dd0f34c0`. It builds
the supplied standalone and suite FX harnesses in a temporary directory.
Neither command downloads tools. `--cxx` selects another compatible compiler.
Use `python validation/package_ips_suite.py` to make the allowlisted ZIP and
SHA-256 file. Generated modules and presets can be rebuilt with the adjacent
`generate_ips_suite_*.py` scripts.

Results from this implementation on Linux:

1. **CPU models:** 7 IPS, 15 Deband, 15 Clarity and 10 suite tests passed.
   The suite model checks all stage/quality combinations, disabled identity,
   original alpha, bounds and grayscale, HDR bypass, standalone-chain agreement
   with dither disabled, constant fields, ramps, lines, edges, texture,
   exclusions, odd/tiny images, deterministic bit-depth-aware output dither
   and quantized gradients. CPU models do not execute the generated shader.
2. **ReShade FX parser/code generation:** the pinned compiler parsed and
   generated HLSL SM5 and GLSL entry points for the suite matrix (168
   configurations), checking pass order, inputs, outputs, texture sizes and
   formats, and actual preset/uniform references. Standalone harnesses are
   also retained. This is not GPU-driver compilation.
3. **GPU-driver compilation:** not tested. No GPU execution is claimed.
4. **In-game visuals, motion and timings:** not tested. Validate the actual
   renderer, format support, HUD boundaries, dynamic scenes and frame time.

For the CPU 8-bit banded-ramp fixture, default clarity's correction was zero
after smoothing; final quantized spatial-mean MSE at High was `1.11e-6`
versus `1.28e-6` for the input. This one fixture does not establish visual
improvement. With aggressive clarity and a coarser 127-level fixture,
quantized step energy at High rose from 7475 to 7675: clarity can re-emphasize
band boundaries. Test your own content rather than assuming it cannot.
Against float64 intermediate color in the CPU model, maximum accumulated
errors for shadow/midtone/highlight ramps were approximately
`3.3e-9/4.6e-8/4.4e-8` with RGBA32F versus
`3.5e-5/3.6e-4/3.3e-4` with a hypothetical RGBA16F stage output.
On a low-amplitude synthetic texture, High deband plus clarity retained
about 40% of the input's spatial standard deviation in this CPU model;
fine texture loss is a real risk, not an assurance of preservation.
