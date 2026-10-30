# Adaptive Clarity 1.0

A self-contained SDR ReShade/GShade sharpener with separate texture and edge
controls, noise gates, ringing limits, fine-pattern protection and two optional
HUD rectangles. It is intended to complement IPS Depth without another global
contrast or saturation grade. It is an original implementation, not AMD CAS.

## Quick start

1. Copy `Shaders/Adaptive_Clarity.fx` into your existing
   `reshade-shaders/Shaders` folder, or configured GShade Shaders folder.
2. Extract `Presets` to a permanent local folder.
3. In the overlay, select **Balanced_High.ini**, or **RTX_Companion_High.ini**
   if you use RTX Dynamic Vibrance. Reload shaders if needed.
4. Start with other sharpening disabled: IPS Depth's Micro sharpening, NVIDIA
   Sharpen/Sharpen+, and any separate sharpening filter. Avoid overlapping
   sharpening while judging the result.
5. Use a static scene with skin, fabric, foliage, a smooth sky and HUD text.
   Enable split comparison, then check camera pans for shimmer or outlines.

The supplied presets enable only Adaptive Clarity. Save your existing preset
before switching if it contains other effects you want to keep.

## Combine with IPS Depth

After selecting an Adaptive Clarity preset, enable IPS Depth again in that
preset and drag its technique ABOVE Adaptive Clarity in the ReShade effect
list. Keep IPS Depth's Micro sharpening at zero. Save the preset.

Alternatively, retain your current preset: enable Adaptive Clarity after IPS
Depth and adjust its controls manually. Add AC_QUALITY=1 to that preset's
preprocessor definitions. Copy only the Adaptive_Clarity.fx section from a
supplied INI if you want its exact values; merge definitions rather than
replacing definitions used by other shaders.

These instructions order ReShade effects only. They neither determine the
ordering relative to NVIDIA Freestyle nor control the game's own sharpening.
If texture becomes crunchy, lower Adaptive Clarity Texture strength and/or
IPS Depth Fine detail contrast before raising protection thresholds further.

## Normal / High / Ultra

| Tier | AC_QUALITY | Wide-ring directions | Guide samples in final pass |
| --- | --- | --- | --- |
| Normal | 0 | 4 | 9 + 4 |
| High | 1 | 8 | 9 + 8 |
| Ultra | 2 | 16 | 9 + 16 |

The same 3x3 neighborhood supplies the structure estimate and near detail term.
A second ring at twice the radius supplies a slightly broader texture band.
The total ring weight is normalized across quality tiers; more directions do
not intentionally increase gain, radius, saturation or sharpening strength.
Quadrature differences can still change the precise image.

Start with High. Ultra costs more sampling work but is not guaranteed to look
better in every scene. Normal/High/Ultra keep identical ordinary settings within
each style. All tiers use the same target dimensions and memory allocation.
The change is directional sampling, not AI quality or internal game resolution.

### Preprocessor definitions

```ini
AC_QUALITY=1
AC_HUD_MASKS=1
```

QUALITY=0 selects Normal, 1 selects High, 2 selects Ultra. The preset root line
for High is:

```ini
PreprocessorDefinitions=AC_QUALITY=1,AC_HUD_MASKS=1
```

The six INIs include their definitions automatically. Compilation may briefly
stall when switching tiers. Reload if necessary and remove conflicting global
or per-effect AC_QUALITY definitions if the selected tier is not taking effect.
Do not override private names beginning `_AC_`.

AC_HUD_MASKS=0 removes rectangle calculations from the active shader path.
Rectangle controls then have no effect. These are compile-time definitions,
not ordinary shader sliders. No add-on or external texture is needed.

## Controls

- **Overall strength:** scales the final correction. Lower first if the whole
  effect is too strong. Zero returns the original final image but still runs
  the brightness-cache pass.
- **Texture strength:** gain in less directional neighborhoods and the small
  band between the near and wide estimates. This is the main clarity control.
- **Edge strength:** gain where the neighborhood has a coherent edge direction.
  Keep modest to avoid brittle text and outlines. The classification is a
  local heuristic; it does not know whether a feature is skin, foliage or UI.
- **Detail radius:** output pixel spacing of the near 3x3 samples, from 0.75 to
  1.5. The ring uses twice that radius. Start at 1.0. It is not the game's
  internal resolution or DLSS render scale, neither of which is detected here.
- **Noise threshold / Extra noise protection:** gates small changes, more
  strongly in less coherent regions. Can also suppress subtle real detail.
  These controls avoid boosting some noise; they do not denoise the source.
- **Cross-edge protection:** reduces weight of unlike-brightness samples and
  samples across a coherent edge. Too much can make sharpening very subtle.
- **Fine-pattern protection:** restrains checker-like pixel patterns. Can
  also weaken real high-frequency texture; compare it on moving foliage.
- **Ringing protection / Permitted overshoot:** bound correction against the
  original near neighborhood. Overshoot=0 is strict local extrema clipping.
  A low nonzero value permits restrained sharpening of extrema.
- **Maximum correction:** soft limit on encoded-luminance change before the
  final strength and headroom protections. It is not an exposure adjustment.

No saturation, global contrast, automatic exposure or dithering is added.
Constant fields and zero-strength operation are tested to remain unchanged.
A local sharpening operation can still change mean brightness slightly in
an asymmetric scene; global brightness preservation is not guaranteed.

## HUD rectangles

Two fixed screen rectangles can protect HUD regions such as a minimap or
ability bar. Both are DISABLED in all shipped presets because HUD layouts vary.

1. Select View -> HUD protection.
2. Enable Protect HUD rectangle 1 (and optionally rectangle 2).
3. Set left, top, right, bottom in normalized coordinates: top-left is (0,0),
   bottom-right is (1,1). For a 3440x1440 screen, a HUD box spanning x=0..688
   and y=1152..1440 would use `(0,0.8,0.2,1)`.
4. White is protected, black is processed, gray is the feather outside the box.
5. Return View to Final image.

Inside each rectangle the final image is unchanged. Feathering fades protection
outside the rectangle; zero gives a hard edge. Rectangles are not automatic HUD
recognition and will protect world content occupying the same screen area.
They do not track menus, camera motion, resolution-independent game anchors or
HUD elements that move. Reversed rectangle coordinates are sorted automatically.

## Comparison views

- Final image: normal output.
- Correction: gray is no change, lighter is a positive correction, darker is
  a negative correction. This is an amplified diagnostic, not the final image.
- Edge coherence: white is strongly directional; black is less directional.
- HUD protection: white is protected; black is unprotected.

Overall strength=0 and the original side of split view show the unmodified
input even in diagnostic modes. Fully protected rectangles retain the original
input in the correction/coherence views; use HUD protection view to position
masks. Alpha is retained from the input in every output path.

## RTX Dynamic Vibrance companion

RTX Companion uses reduced texture/edge gains, stronger noise/pattern/ringing
protection and a lower correction cap. It does not set NVIDIA controls or detect
the filter's settings. Suggested initial RTX Dynamic Vibrance settings are
Intensity 20%, Saturation Boost 0%, separately configured in NVIDIA App.
These are conservative starting values, not calibration or a measured optimum.
Keep NVIDIA sharpening off initially. Existing noise can become more visible
in the combined pipeline, so inspect dark gradients and moving vegetation.

Keep the game in SDR. Native HDR, RTX HDR and other HDR conversion paths are
outside the intended preset. Recognized HDR presentation spaces pass through
unchanged; unknown color spaces cannot be verified.

## Processing and resource cost

The first pass caches sRGB-encoded linear luminance to one full-resolution R32F
texture. The second uses that guide for small-scale spatial processing, then
reconstructs RGB in linear light. Chroma moves toward neutral only when needed
to project the result into the SDR RGB gamut. This is not a perceptually uniform
hue model or sharpening of color-only edges.

Two passes; one 4-byte intermediate per output pixel: about **18.9 MiB at
3440x1440**, excluding driver overhead. Normal/High/Ultra use roughly 15/19/27
nominal texture fetches per output pixel across both passes with Texture strength
above zero. Counts do not establish bandwidth, speed or FPS. Arithmetic and
cache behavior matter. Declared HDR needs one passthrough pass and no guide.
There is no temporal history, depth use or frame-generation integration.

Disable the technique, rather than only setting Overall strength=0, to measure
its full GPU cost. No FPS estimates or claims of being faster than CAS are made.

## Validation

- FX parsing, module and entry-point code generation passed **80 configurations**
  using HLSL SM5 and GLSL Vulkan semantics: all qualities, HUD mask switches,
  unknown/SDR/scRGB/HDR10/HLG declarations, absent color-space macro, odd and
  tiny sizes. Pass counts, guide format and allocation are checked.
- **15 CPU tests** check constant fields, exact bypasses, alpha/grayscale
  preservation, color bounds/target luminance, local extrema/ringing limits,
  hard edges and thin features at several phases, subthreshold noise,
  enhancement of a synthetic blurred texture, checker-pattern attenuation,
  90-degree rotation, HUD masks, smooth gradients and supported radii.
- Gamut tests include 100,008 RGB samples and four target-luminance sets.
- Six preset INIs, their ranges, quality definitions and consistent per-style
  look settings are checked. ZIP contents and SHA-256 checksums are verified.

These are not Windows GPU-driver compilation, real-game rendering or measured
GPU timings. CPU tests simulate R32F writes and bilinear sampling with NumPy/
SciPy; GPU arithmetic can differ. Shader compiler source used for validation:
crosire/reshade commit `7bf9de8b33bcc76c3177007e65d73c72dd0f34c0`.

There is no established in-game comparison against CAS, no test on your RTX
4070 Ti, and no verified NVIDIA filter-stack ordering or motion-quality result.
The shader can amplify aliasing, noise and UI edges in some scenes. No spatial
sharpener can recover information absent from the final game image.

## Compare against CAS in your game

Use the same fixed camera, resolution, AA/upscaling settings and color grade.
Keep only one sharpener active at a time. Capture original, Adaptive Clarity
and CAS with roughly matched apparent edge strength. Inspect skin, fabrics,
foliage, small text, bright/dark boundaries and smooth areas. Then pan the
camera and compare shimmer. Measure frame time at the same scene with each
technique enabled/disabled. Stronger apparent edges alone do not prove better
image quality. CAS is a useful baseline, not bundled or reimplemented here.

## Reproduce checks

```bash
python -m pip install numpy scipy
python Tests/test_reference.py
```

See `Tests/README.md` for effect-compiler harness build instructions. No compiler
binary or ReShade runtime is bundled.

## License and references

MIT; see LICENSE and the shader's license text. No third-party shader code or
NVIDIA SDK is included. ReShade, GShade and NVIDIA filters are separate software.

- [ReShade FX reference](https://github.com/crosire/reshade-shaders/blob/slim/REFERENCE.md)
- [AMD CAS documentation](https://gpuopen.com/manuals/fidelityfx_sdk/techniques/contrast-adaptive-sharpening/)
- [NVIDIA RTX Dynamic Vibrance documentation](https://github.com/NVIDIA-RTX/Streamline/blob/main/docs/ProgrammingGuideDeepDVC.md)
