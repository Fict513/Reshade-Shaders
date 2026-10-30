# IPS Depth v2

A rewritten SDR ReShade/GShade shader for deeper-looking contrast and texture
on an IPS display. It includes Normal, High, Ultra quality presets in both
Balanced and RTX Companion styles. It does not need external textures, depth
access or a native add-on.

## Install

1. Copy `Shaders/IPS_Depth_v2.fx` into your existing `reshade-shaders/Shaders`
   directory, or your configured GShade Shaders directory.
2. Extract `Presets` to a permanent local folder.
3. In the overlay's preset selector, choose **Balanced_High.ini**, or
   **RTX_Companion_High.ini** when using NVIDIA RTX Dynamic Vibrance.
4. Reload shaders if necessary. The INI enables **IPS Depth v2** and sets its
   quality definitions automatically. Let compilation finish after switching.
5. Disable the earlier IPS Depth, IPS Depth HQ and FakeHDR techniques while
   using this grade. These INIs select only v2; save your previous preset if it
   contains other effects/settings you want to keep.

The filename, namespace and technique are unique so the old files can coexist.
Changing compile-time definitions can trigger a shader reload/stall. These
presets change compile-time sampling quality, not just a cosmetic UI label.

## Quality presets

| Tier | IPSD2_QUALITY | Filter samples per axis | Intended use |
| --- | --- | --- | --- |
| Normal | 0 | 9 | Lowest sampling cost provided |
| High | 1 | 13 | Starting point for everyday play |
| Ultra | 2 | 21 | Denser sampling over the same radius |

Within each style the ordinary sliders are identical across tiers: Ultra does
not intentionally add contrast, brightness, saturation or sharpening. Sampling
can change the precise filtered result. There is no claim that Ultra is visibly
better in every game. All tiers use the same texture dimensions and memory.
FPS/frame-time differences have not been measured on a GPU.

## Preprocessor definitions

All supplied presets enable local and broad filtering. To use your own preset,
add/update these definitions in the overlay and reload:

```ini
IPSD2_QUALITY=1
IPSD2_LOCAL=1
IPSD2_BROAD=1
```

Use QUALITY=0 for Normal or QUALITY=2 for Ultra. This is not an ordinary slider.
The corresponding preset root entry for High is:

```ini
PreprocessorDefinitions=IPSD2_QUALITY=1,IPSD2_LOCAL=1,IPSD2_BROAD=1
```

Remove conflicting global/per-effect definitions if a preset is not selecting
the expected tier. The earlier IPSHQ_TAPS / IPSHQ_BROAD settings do not configure
this rewrite. Do not override private names beginning `_IPSD2_`.

Optional lighter paths:

| Definition | Result |
| --- | --- |
| IPSD2_BROAD=0 | Removes the three broad-filter passes and half-resolution targets; fine local contrast remains |
| IPSD2_LOCAL=0 | Removes all local-filter passes and targets; tone curve and optional sharpening remain |

The broad switch has no effect when LOCAL=0. Controls for disabled features are
ignored. These switches alter processing, so they are not used as Normal/High/
Ultra equivalents. Disable the whole technique to recover its complete cost;
Overall strength=0 bypasses only the final grade.

## Look controls

- **Tonal contrast:** deeper lower midtones. Reduce first if dark areas lose
  visibility. Black, white and the tone curve's encoded-luminance 0.5 pivot stay
  fixed; local texture enhancement can still change pixels around the pivot.
- **Shadow protection:** retains near-black detail without lifting exact black.
- **Highlight contribution:** controls the upper half of the tone curve. Set
  to zero to avoid tone-curve highlight brightening.
- **Fine detail contrast / Broad detail contrast:** texture definition and shape
  separation. Reduce broad detail if edges look outlined.
- **Radius:** the fine analysis radius in pixels at 1080p, scaled by output
  height. Broad radius is three times this. Larger radii are not automatically
  higher quality.
- **Edge protection / Halo suppression:** limit mixing and enhancement around
  bright boundaries or HUD elements. Strong settings can weaken the effect in
  complex textures.
- **Detail noise threshold:** raise for grainy content. Micro sharpening is
  optional and starts at zero in both preset styles.
- **Dither:** subtle static monochrome noise, scaled for 8/10-bit backbuffers;
  disabled for 16-bit backbuffers. RTX presets start at zero.
- **Split comparison / View:** compare the original against the result, inspect
  local correction (gray is neutral), or inspect broad reconstruction confidence
  (white is reliable). The confidence view is black when broad/local is disabled.

## RTX Dynamic Vibrance

The RTX Companion presets use slightly less tonal/local contrast, less upper
highlight lift, a higher noise threshold, and no additional sharpening or dither.
The shader has no saturation/vibrance boost of its own.

Set NVIDIA controls separately. Suggested initial settings are **Intensity 20%**
and **Saturation Boost 0%**. These are conservative starting values, not a
calibrated optimum. Keep ordinary NVIDIA Control Panel Digital Vibrance at its
neutral/default position for comparison. If too dull, first try Intensity 30%,
then consider Saturation Boost 5%. If too strong, reduce Saturation Boost (if
above zero) and Intensity before increasing shader brightness.

The INIs neither detect nor set NVIDIA controls. They do not establish the
execution order between ReShade and NVIDIA Freestyle. End-to-end color gamut,
compatibility and noise behavior must be judged in the game. RTX HDR, native
HDR and other HDR conversion workflows are outside this SDR preset's scope.

## What was rewritten

- A cached sRGB-encoded linear-luminance guide avoids repeatedly decoding RGB
  in the filter taps. Half-float writes are included in the CPU reference tests.
- Fine analysis runs full resolution; broader filtering runs at half resolution.
- Downsampling retains an edge-confidence value. Mixed edge samples are
  discounted during filtering and residual reconstruction, with a smooth
  fallback when nearby reduced-resolution guides do not match.
- Fine and broad bands cover different scales rather than applying the same
  sharpening twice. Noise gates and bounded corrections protect the endpoints.
- Tone grading uses a full-precision center so half-float guide quantization
  does not become a flat-field brightness change.
- Final RGB is reconstructed in linear light. In-gamut colors retain RGB ratios;
  out-of-gamut chroma is projected toward neutral at the requested luminance.
  This is an RGB gamut projection, not a perceptually uniform hue model.
- With tonal/detail/sharpening controls and dither at zero, identity behavior
  is tested. There is no automatic exposure or temporal accumulation.

## Processing cost

The full pipeline has seven passes and about 14 bytes of intermediate storage
per output pixel for even dimensions, approximately **66.1 MiB at 3440x1440**.
The old HQ shader used about 56.7 MiB: this rewrite deliberately uses a little
more target storage to cache luminance and carry edge confidence.

Normal/High/Ultra have nominal source-level texture-fetch estimates of about
42/52/72 per output pixel with the default halo mask active, versus about 111
for the old HQ default. These estimates do not account for cache hits, compiler
optimizations, sample footprint, driver overhead or arithmetic cost. Fewer
fetches do not establish an FPS improvement.

BROAD=0 uses four passes and about 37.8 MiB of intermediate targets at the same
resolution. LOCAL=0 uses one pass and no intermediate textures. Odd dimensions
use ceiling division. Recognized HDR presentation spaces use one ungraded
passthrough pass without filter resources.

## Validation and limits

FX parsing, module generation, per-entry-point HLSL SM5 and GLSL (Vulkan
semantics) generation passed **126 configurations**. The matrix includes all
three qualities, feature switches, unknown/SDR/scRGB/HDR10/HLG declarations,
8/10/16-bit output macros, tiny dimensions and odd dimensions. Pass counts and
resource layouts are checked. The compiler source used is crosire/reshade
commit `7bf9de8b33bcc76c3177007e65d73c72dd0f34c0`.

Seven CPU test methods cover 27 tone-curve combinations, 100,008 linear RGB
samples with four target-luminance sets, near-black color identity, quantized
constant fields, hard edges, thin bright features at several pixel phases,
monotonic ramps and bounded random images. Preset keys, ranges, equal look
settings across tiers, archive integrity and checksums are also checked.

These tests are not Windows GPU-driver compilation or in-game rendering. No
FPS benchmark, NVIDIA filter-stack test, gameplay comparison or motion-stability
assessment has been performed. The CPU model uses NumPy/SciPy interpolation
and simulated half-float target writes; GPU arithmetic can differ. Small test
images can be treated as crops from 1080p to stress realistic kernel radii.

The shader assumes SDR sRGB with Rec.709 primaries and final game tone mapping
already applied. Unknown presentation color spaces cannot be verified. It
cannot reduce IPS glow or physical black level, recover clipped detail, exclude
all HUD elements automatically, or bypass a game's restrictions. All screen
content is processed. Broad analysis can become conservative around intricate
patterns. Compare static scenes and camera pans in your own game.

## Reproduce checks

```bash
python -m pip install numpy scipy
python Tests/test_reference.py
```

See `Tests/README.md` for compiler-check build instructions. Test code is
included for reproducibility; no ReShade binary is bundled.

## License

MIT. `LICENSE` and the shader contain the license text. No third-party shader
implementation or NVIDIA SDK code is bundled. NVIDIA RTX Dynamic Vibrance is
separate NVIDIA software.

References: [ReShade FX reference](https://github.com/crosire/reshade-shaders/blob/slim/REFERENCE.md),
[RTX Dynamic Vibrance documentation](https://github.com/NVIDIA-RTX/Streamline/blob/main/docs/ProgrammingGuideDeepDVC.md).
