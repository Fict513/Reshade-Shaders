# Selective Deband 1.0

A self-contained SDR ReShade/GShade shader for shallow banding in skies, fog,
dark backgrounds and other smooth gradients. Brightness/color gates, local
edge/texture protection, bounded corrections and optional selective dithering
restrain its effect on detail. Includes Normal, High and Ultra quality presets
in Balanced and RTX Companion styles.

This is a spatial heuristic. Eligible pixels are not proven banding, and subtle
real texture or low-contrast contours can also be smoothed. No lost detail or
colors are recovered. No external textures, add-on, depth buffer or assets are
required. This is an original implementation, not a copy of Deband.fx.

## Install and start

1. Copy `Shaders/Selective_Deband.fx` into your existing
   `reshade-shaders/Shaders` folder or configured GShade Shaders directory.
2. Extract `Presets` to a permanent local folder.
3. Select **Balanced_High.ini** in the overlay preset selector, or
   **RTX_Companion_High.ini** if using RTX Dynamic Vibrance. Reload if necessary.
4. Start with other debanders disabled. Save your old preset before switching
   if it contains effects/settings you want to keep.
5. Use split comparison on a visible banded gradient. Inspect foliage, fabric,
   fine text, dark areas and camera motion before increasing thresholds.

The supplied INIs enable only Selective Deband. To combine effects, re-enable
existing effects in that preset, order them as below, then save it. Or retain
your existing preset, enable Selective Deband, and merge its INI section and
preprocessor definitions rather than replacing definitions for other shaders.

## Suggested ReShade order

**IPS Depth (or FakeHDR) -> Selective Deband -> Adaptive Clarity**

Use one main contrast grade. Disable dithering in the earlier grade initially
so dithering is not stacked. Keep IPS Depth's micro sharpening at zero if using
Adaptive Clarity. A later sharpener can re-emphasize residual contours; compare
the complete stack and reduce sharpening if needed. In some scenes it may be
preferable to place debanding last, at the risk of smoothing sharpened texture.
ReShade ordering does not establish execution order relative to NVIDIA filters.

## Normal / High / Ultra

| Tier | SDB_QUALITY | Paired angles | Nominal maximum color samples/pixel |
| --- | --- | --- | --- |
| Normal | 0 | 4 | 25 |
| High | 1 | 8 | 41 |
| Ultra | 2 | 16 | 73 |

Each angle samples both signs at half and full search radius. A common 3x3
neighborhood supplies local protection. Pair weights are normalized, so tiers
change angular sampling rather than intentionally increasing strength, radius,
thresholds or dithering. The precise result can still vary with sample locations.
Ultra is not guaranteed to look better in every scene. All tiers have one pass
and no intermediate targets of their own. Sampling counts are not GPU timings.

### Preprocessor definitions

```ini
SDB_QUALITY=1
SDB_HUD_MASKS=1
SDB_DITHER=1
```

Set QUALITY=0 for Normal, 1 for High, 2 for Ultra. The preset root line for High:

```ini
PreprocessorDefinitions=SDB_QUALITY=1,SDB_HUD_MASKS=1,SDB_DITHER=1
```

All six presets include these definitions. Wait for compilation when changing
tiers; reload if necessary. Remove conflicting global/per-effect definitions
if switching presets does not select the expected quality.

SDB_HUD_MASKS=0 strips the rectangle math from the active shader path.
SDB_DITHER=0 strips dithering regardless of its ordinary slider value.
These are compile-time settings, not ordinary sliders. Do not edit private
names starting `_SDB_`. All grades remain one pass; masks/dither are arithmetic
options rather than additional rendering passes.

## Controls and tuning

Thresholds and Maximum correction use **8-bit code steps: one step = 1/255**.
They do not automatically shrink when the backbuffer is 10-bit because banding
may originate in an 8-bit asset or earlier render stage. Dither, separately,
scales with the declared output/backbuffer bit depth.

- **Overall strength:** blend the permitted correction. Zero returns the
  original. Disable the technique entirely to measure its full GPU cost.
- **Search radius:** output pixels, with samples at half and full radius.
  Start at 8. Increase gradually if bands span wider plateaus; a larger radius
  can cross genuine features and is not automatically higher quality.
- **Brightness threshold:** reference samples farther away in luma are rejected.
  Start at 3 steps. Increase cautiously for larger jumps in a banded gradient.
- **Color threshold:** rejects reference samples with unlike RGB-minus-luma
  chroma. Lower it if color boundaries smear. It is not a perceptual color metric.
- **Texture threshold:** local second differences above this reduce eligibility.
  Lower protects more fine detail, but also rejects some band transitions.
- **Edge threshold:** local RGB range above this protects the pixel. Lower
  protects more HUD/text edges. Genuine shallow contours can still be eligible.
- **Maximum correction:** cap on the strongest RGB component of smoothing
  before final strength. The cap excludes dither, which has its own amplitude.
- **Selective dither:** static monochrome noise only where a nontrivial
  correction is made. 8-bit and 10-bit steps are scaled separately; disabled
  for 16-bit buffers. No time-varying sample rotation or animated noise is used.

If banding remains, first inspect the Eligible areas view. If the band boundaries
are dark in that view, protection/thresholds are rejecting them; adjust the
relevant controls carefully. If very wide bands are untouched, increase Radius.
If the floating-point change disappears at final 8-bit output, raise selective
dither cautiously: a sub-half-step change can round back to the same code value.
If detail softens, lower Strength, thresholds or Radius, or protect the region.

## RTX Dynamic Vibrance companion

RTX Companion uses lower dithering (0.60 vs Balanced 0.80), a stricter color
threshold and a stricter edge threshold. It does not set or detect NVIDIA
settings and cannot guarantee execution order relative to NVIDIA Freestyle.
Suggested initial NVIDIA RTX Dynamic Vibrance settings are Intensity 20%,
Saturation Boost 0%, set separately. These are starting suggestions, not an
in-game calibration. No NVIDIA code or integration is included.

NVIDIA enhancement may make noise more visible. Lower Dither if necessary, but
expect some loss of debanding at final 8-bit output. High is a more useful
starting tier than Normal when using reduced dithering. Check the combined
pipeline on static gradients and during camera movement.

## HUD protection and comparison

Both manual rectangles are disabled in every preset because HUD layouts vary.
Enable one, select View -> HUD protection, and enter normalized left, top,
right, bottom coordinates. Top-left is (0,0); bottom-right is (1,1).
For example, `(0,0.8,0.2,1)` covers the lower-left fifth of the screen.
Coordinates are sorted if reversed. Feathering fades protection outside the
rectangle, and zero gives a hard boundary. Pixels inside it remain unchanged.
Fixed rectangles also protect world content occupying those screen regions;
they do not automatically identify or track HUD elements.

Views:
- **Final image:** normal processed result.
- **Eligible areas:** white is an eligible flat-enough area with sufficient
  accepted references; black is protected/rejected. This is not a band detector.
  A flat field can be eligible yet remain unchanged.
- **Smoothing correction:** RGB difference amplified around neutral gray,
  before selective dithering. Gray means no smoothing correction.
- **HUD protection:** white is protected, black is unprotected.

Split view keeps original on the left. Strength=0 and declared HDR show the
original regardless of diagnostic view. Alpha is preserved in every path.

## Processing and limitations

Encoded RGB is processed directly because the targeted contours are code-value
steps in SDR gradients. Weighted symmetric pairs plus the center form a convex
estimate; correction is capped and blended. Local RGB range and second
differences help reject strong boundaries and fine alternating patterns.
The filter is not semantic, not a true reconstruction of the underlying image,
and not a general denoiser. Color averaging can change subtle hue/detail.

Dither is monochrome, stationary in screen space, applied only where smoothing
changes the image, and faded near gamut boundaries. It can still become visible
or vary during motion because the image-dependent eligibility changes. It is
not guaranteed temporal stability. Exact black/white fields remain unchanged.

One pass, no intermediate textures allocated by this effect. ReShade may still
need its normal backbuffer copies/driver resources. No measured FPS cost is
available. HDR presentation spaces pass through; unknown color spaces cannot
be verified. Input must be SDR encoded RGB with Rec.709 primaries. There is no
depth access, HDR conversion, added contrast, saturation boost or sharpening.

Strong compression, severe banding, wide plateaus and noise can defeat the
heuristic. A true low-contrast object edge may be smoothed like a band boundary.
Far bilinear samples can cause tiny changes beside color boundaries even when
the immediate boundary is rejected. Use masks and the diagnostic views where
needed. No spatial filter can unambiguously distinguish every band from art.

## Validation

FX parsing, module and per-entry-point HLSL SM5 and GLSL Vulkan-semantics code
generation pass **98 configurations**, covering all quality levels, HUD masks,
dither disabled/enabled, unknown/SDR/scRGB/HDR10/HLG declarations, absent space
macro, 8/10/16-bit macros, tiny and odd dimensions. Every case has one pass and
no intermediate targets. Official compiler source used: crosire/reshade commit
`7bf9de8b33bcc76c3177007e65d73c72dd0f34c0`.

**15 CPU tests** cover constant-field identity with dither enabled, SDR/HDR
bypasses, reduced error on a synthetic quantized gradient, final 8-bit rounding,
smooth-gradient preservation, strong edges/thin lines, an isolated one-code-step
fine feature, checker texture, an isoluminant color boundary, correction bounds,
alpha, neutral colors, deterministic sampling, 10/16-bit dither behavior, masks,
rotation and finite results at parameter extremes.

On the single test ramp, before output rounding, the mean-square error ratio
relative to the quantized input is about 0.508/0.390/0.327 for Normal/High/Ultra
with dither off. With defaults and 8-bit output rounding, spatially averaged
error ratios are about 0.869/0.869/0.785. These are specific synthetic CPU results,
not percentages of image quality, general improvements or GPU measurements.
The color-edge test requires exact preservation at the immediate edge and
bounds the adjacent bilinear-sampling change to less than 0.05 of one 8-bit step.

Tests model the equations with NumPy/SciPy. GPU arithmetic and the dither hash
can differ. There is no Windows GPU-driver compilation, actual game screenshot,
NVIDIA-stack validation or camera-motion/FPS test. Quality must be judged on
real scenes. Existing Deband.fx is a useful comparison baseline; no superiority
claim is made and its implementation is not bundled.

## Reproduce checks

```bash
python -m pip install numpy scipy
python Tests/test_reference.py
```

See `Tests/README.md` to build the compiler harness. No compiler or ReShade/GShade
runtime binary is included. Six INIs and their values/definitions, equality of
look controls across tiers, archive integrity and SHA-256 checksums are checked.

## License and references

MIT. License is in `LICENSE` and the shader. No third-party shader code is
incorporated. ReShade, GShade and NVIDIA software are separate products.

- [ReShade FX reference](https://github.com/crosire/reshade-shaders/blob/slim/REFERENCE.md)
- [Existing ReShade Deband.fx](https://github.com/crosire/reshade-shaders/blob/slim/Shaders/Deband.fx)
- [RTX Dynamic Vibrance documentation](https://github.com/NVIDIA-RTX/Streamline/blob/main/docs/ProgrammingGuideDeepDVC.md)
