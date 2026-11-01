# Input/output contract and integration

## Supported contracts

The same contract must apply to the actual values returned by the shader's non-sRGB COLOR sampling view and the values expected by its non-sRGB destination view. This effect does not convert one framebuffer encoding into a different encoding.

| UI / verified macro | COLOR values | Processing | Output |
|---|---|---|---|
| 0 | Not established | Bypass, unless a verified integration macro selects 1–3 | Original sampled float4 |
| 1 | Full-range sRGB transfer, BT.709 primaries, RGB in [0,1] | Exact piecewise sRGB decode, relative linear luminance | Exact piecewise sRGB encode |
| 2 | Full-range ST 2084 code values in [0,1], BT.2020 primaries | Decode each component to absolute nits, then divide by 80 for analysis | Multiply by 80, inverse ST 2084 |
| 3 | Linear scRGB, BT.709 primaries, 80 nits per RGB unit, signed/extended | No transfer conversion | Linear signed/extended scRGB |
| 4 or invalid verified value | Unsupported/forced bypass | Bypass | Original sampled float4 |

A generic gamma-2.2 intermediate, HLG, limited-range PQ, scene-linear HDR before tone mapping, log-encoded buffers, other primaries or differently normalized linear buffers are unsupported. **Do not select the nearest-looking mode.** Default bypass is the safe behavior.

scRGB requires a signed floating-point destination. Where ReShade exposes `BUFFER_COLOR_FORMAT`, incompatible formats bypass; RGBA16F (10) and RGBA32F (2) are accepted. This is a representability check, not color-space inference. If format metadata is unavailable, explicit selection asserts this requirement and the shader conservatively guards the FP16 finite range.

## Establish the contract

1. Identify the injection location. It must sample the final, already HDR-mapped game image at its current output resolution. Verify that no prior effect is leaving a different encoding in COLOR.
2. Use engine/integration documentation or a graphics capture that identifies the **resource and view bound to `AD_ColorSampler`** and the destination of `ApplyDetail`. Check their formats, dimensions and view interpretation. A swap-chain description alone is insufficient for a custom/intermediate injection target.
3. Inspect the upstream writer or known encoding conversion. Distinguish sRGB from arbitrary gamma encodings, and PQ from linear component-nit or normalized HDR representations. Verify BT.709 versus BT.2020 primaries and the 80-nit scRGB scale. A histogram, image appearance or a single white patch cannot establish all of these properties.
4. Confirm that COLOR sampling uses the non-sRGB SRV and `ApplyDetail` uses a non-sRGB RTV. Both shader samplers explicitly use `SRGBTexture=false`; both passes use `SRGBWriteEnable=false`. An add-on that supplies incorrectly typed views can invalidate this contract despite these declarations.
5. Check the raw values against controlled patches when available: sRGB code 0.5 decodes to about 0.214041 linear; PQ code 0.508078 represents 100 component nits; scRGB white (1,1,1) represents 80 nits and (12.5,12.5,12.5) represents 1000 nits. These are sanity checks alongside upstream evidence, not automatic detection rules.
6. Select the matching explicit UI mode, or set `ADAPTIVE_DETAIL_VERIFIED_CONTRACT` to 1, 2 or 3 for a **verified integration**, leaving UI mode 0. That macro is a declaration by the integrator, not a detector. Revalidate it after changes to HDR mode, render path, prior effects or injection stage.

No `BUFFER_COLOR_SPACE`, color bit depth or Windows HDR flag is used to select an encoding. The available ReShade color-space macro describes presentation and need not describe intermediate buffers. GPU output bpc also says nothing reliable about the shader's sampled encoding.

## Pass and alpha behavior

The technique first samples COLOR into an R32F luminance texture, then reads that texture and the same COLOR snapshot to compose its output. It never samples a texture while writing that texture. Under the inspected ReShade runtime, the offscreen preparation pass does not update the COLOR snapshot; the final pass writes to the backbuffer. Inspect custom integrations separately.

Sampling is point-filtered at texel centers, except Normal-quality detail taps, which use bilinear filtering **only on decoded linear luminance**. All addressing clamps to edge, and mipmaps are not used. Tiny and odd dimensions are supported; the viewport must match BUFFER_WIDTH × BUFFER_HEIGHT.

All final output paths copy original alpha. Diagnostics replace RGB only. Preparation stores luminance alone; no alpha intermediate is needed. Blending is disabled. Master zero, fully neutral component settings, and unsupported contracts return the original sampled float4 before decoding/re-encoding in the final pass. Unsupported/zero-strength diagnostics also bypass. The initial pass still executes, so bypass does not imply zero rendering overhead.

The identity guarantee is for shader-returned sampled values, not for arbitrary destination conversion: hardware can quantize alpha to two bits in RGB10A2 or canonicalize NaNs. A mismatched destination/view cannot be made bit-identical by shader code.

## Invalid and extreme inputs

Out-of-contract SDR/PQ components bypass locally. A sentinel in the luma intermediate propagates bypass to dependent neighborhoods, preventing invalid samples from being interpreted as light. NaN/Inf RGB also fails validation. Alpha is copied without interpreting it.

Finite signed scRGB RGB components up to magnitude 1e18 are accepted as a conservative arithmetic envelope; this is not a physical display limit. Nonpositive center luminance is left unchanged. Positive-luminance colors with negative components are scaled by the same positive gain, preserving component signs. Extremely large values outside this envelope bypass rather than being clamped. In RGBA16F/unknown destinations, gain is restricted so a valid finite FP16 component cannot be increased beyond 65504; existing out-of-range values are not repaired.

For supported SDR/PQ values, upward gain is bounded by channel-domain headroom. No per-channel hard clipping or second display tone mapper is applied. This does not enforce your display's peak brightness; the game is assumed to have already mapped its image appropriately.
