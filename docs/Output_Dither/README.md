# Output_Dither 1.0.0

This is the supplied package guide. Its embedded validation figures are
historical package evidence, not tests run for this repository integration;
see [the integration report](../../validation/Output_Dither/INTEGRATION_VALIDATION.md)
for the checks performed here.

A restrained, static finishing dither for a **known, subsequent quantization step**. One pass; no sharpening, debanding, grain, tone mapping, exposure, color grading or explicit image quantization. Defaults to bypass until the contract is selected and master bypass is cleared.

**Leave it off on an ordinary already-quantized 8-bit sRGB or 10-bit PQ back buffer when the next quantizer uses the same grid.** A later shader cannot recover fractional values discarded by an earlier render-target write. On the tested RTX 4070 Ti, actual UNORM conversion also perturbed a small fraction of existing codes; that was not gradient recovery. See [VALIDATION.md](VALIDATION.md).

## Installation

1. Copy `Shaders/Output_Dither.fx` and `Shaders/Output_Dither_Core.fxh` into a directory in ReShade's **Effect search paths**.
2. Copy `Textures/Output_Dither_BN128.png` into a directory in **Texture search paths**. Keep the filename. No ReShade.fxh, depth buffer, add-on, external shader pack or network service is required.
3. Reload effects. Resolve **all** shader and texture-load errors before enabling. A missing PNG may parse successfully but cannot supply the required noise; do not use a blank/replacement texture. The shipped PNG's SHA-256 is recorded in `Textures/provenance.json`.
4. Select `Output Dither (static blue noise)`. Select the explicit input/output contract and compatible target assumption, then clear **Master bypass** only after verifying the pipeline below. Start at span **1.0** when dithering a precise signal; reducing it can restore visible banding.

Validated parser source is ReShade commit `7bf9de8b33bcc76c3177007e65d73c72dd0f34c0`. HLSL SM5 and GLSL generation were tested; actual offscreen GPU testing used D3D11 on an RTX 4070 Ti. In-game ReShade integration and other GPU APIs remain unverified. Do not interpret this as a tested minimum ReShade version.

## Choose the contract, then the quantizer

| Contract | Compatible target assumptions | Behavior |
|---|---|---|
| Unknown | Any | Original sample |
| SDR sRGB, BT.709 primaries | 8-bit sRGB or 10-bit sRGB | Dither in the encoded sRGB domain |
| Full-range ST 2084 PQ, BT.2020 primaries | 10-bit PQ | Dither in the encoded PQ domain |
| Linear scRGB, BT.709, nominal 80 nits/unit | None | Original sample, including signed and extended values |

An incompatible pair bypasses. SDR and PQ require **matching input and output encoding**; the shader does no transfer-function or primaries conversion. The targets specify 255 or 1023 intervals over [0,1]. They are assumptions about quantization **at this processing stage**, not measurements or controls of the monitor, NVIDIA output setting, panel precision or physical link. Limited-range RGB, YCbCr, HLG and other encodings are unsupported.

Neither Windows HDR, FP16 storage, swap-chain metadata alone, display bit depth nor appearance proves the image's encoding. Verify the specific game's buffer and the effects that wrote it, using source, logs and a graphics capture where appropriate. This package cannot automatically determine that contract. Display or link settings do not change these requirements; no display-specific calibration or processing is performed.

## Enable only when there is useful precision to dither

- **Known encoded signal finer than the next quantizer:** useful in controlled tests. Examples include encoded FP16 followed by a known 8-bit sRGB quantizer, or 10-bit sRGB storage preceding an actual 8-bit sRGB reduction. The intermediate write must retain enough of the perturbation. These examples require verification in the actual pipeline.
- **Already on the same grid:** leave off. Ideal half-step dither makes no change. Actual hardware may move some codes because of conversion tolerance. More noise cannot infer the missing gradient.
- **Unknown downstream encoding or conversion:** leave off. Extra noise may be erased, amplified, remapped or duplicated downstream.
- **Linear scRGB:** intentionally bypassed. A constant linear 1/1023 is not a 10-bit PQ code step. Windows may convert primaries, scale white, tone map and encode after this pass. No speculative scRGB option is provided.

Often the right solution is to add the dither **inside the preceding effect**, after its final encoded color computation and immediately before its first lossy UNORM write. `Output_Dither_Core.fxh` exposes the small scalar helpers for such an integration; the caller must also supply the point-sampled noise and contract checks. Sharing an FP16 intermediate inside an upstream effect can preserve values that separate finishing effects cannot access through `COLOR`.

## Ordering and interactions

When testing with Signal Inspector, place **Output_Dither after image-processing effects and before Signal Inspector** so the inspector measures its output. This is a measurement-oriented recommendation, not a prescribed ordering among the other effects, nor proof that the next stage is the assumed quantizer. Keep sharpening, resizing, blurring, color conversion and lossy writes after dithering disabled when testing its effect; they can alter or erase the noise. Avoid lossy intermediate writes between dither and the assumed quantizer.

Placing it last in ReShade does **not** place it immediately before the physical display quantizer. Windows composition, color management, output conversion, a driver's existing dither, the game's dither and the monitor can still intervene. Intermediate UNORM writes may discard the very noise intended for a later stage. If debanding already adds adequate output noise, normally use just one source of dither. Turning both on increases noise and does not guarantee a better result.

## Practical Signal Inspector comparison

`Signal_Inspector.fx` was not supplied, so its controls and pattern implementation were not inspected. Use its available gradients and code-step patterns without assuming a particular UI name:

1. Disable competing dither/noise and sharpening after Output_Dither. Confirm the contract and buffer format. Fix the resolution and capture format; inspect at 1:1 pixels.
2. Inspect a smooth encoded gradient with Output_Dither off/on, plus constant fields between adjacent target codes. Compare code occupancy, average error and spatial structure, not just apparent smoothness.
3. Repeat using values already on the target code grid. Expect no benefit; small hardware code perturbations are not recovery. The enclosed CPU fixtures explicitly demonstrate this negative case.
4. Inspect black, white, near-endpoint fields and saturated primaries. Check noise and bias separately. Keep Signal Inspector's measurement pass after Output_Dither. If its pattern-generation pass writes the ordinary UNORM back buffer first, its “smooth” gradient is already quantized before this shader. That tests case 2, not case 1. Use a shared high-precision fixture or integrate dither in the pattern producer to test case 1.
5. Repeat at the actual 8-bit and 10-bit NVIDIA output settings without automatically changing the shader's contract. Those link settings do not identify the sampled image. A PNG screenshot of HDR or a rescaled preview does not validate the HDR link.

Do not enable an explicit quantizer in normal operation to make the effect visible. Explicit quantizers in this package exist only in `validation/*.py`.

## Resources

- One full-screen triangle and one production pixel pass, with one `COLOR` sample and one point sample of the static noise texture per active pixel. Alpha is returned from the original sample.
- Noise: **128×128 R8 UNORM**, one mip, 16,384 bytes (16 KiB) nominal texel payload, tiled every 128 pixels on both axes. Actual allocation has driver alignment/metadata overhead. Some APIs may emulate R8 with a larger format.
- Two samplers. Four UI uniforms (16 bytes in the generated SM5 constant buffer, before allocation alignment). No depth, history, motion vectors, compute pass or full-resolution custom texture.
- Master bypass/zero strength is a shader return path; the pass, resources and ReShade copy can still exist. Branch flattening is compiler-dependent. Disable the technique to avoid its draw, or define `OUTPUT_DITHER_ENABLE=0` and reload to compile out all dither uniforms, helpers and the noise resource. That build still has a one-sample copy pass. No animated mode exists, so there is no spatial/temporal selector.
- ReShade's own `COLOR` copy and output render target remain additional costs. Nominal full-frame payload is 4 bytes/pixel for RGBA8 or RGB10A2 and 8 bytes/pixel for RGBA16F. The former is 7.91, 8.79, 14.06 and 18.90 MiB at 1920×1080, 1920×1200, 2560×1440 and 3440×1440; FP16 doubles these. These are per-buffer payloads, not a claim that this effect uniquely allocates all of them.
- No GPU timing or FPS claim is made. Offscreen validation did not measure performance.

Read [TECHNICAL.md](TECHNICAL.md) for the mathematical contract, [VALIDATION.md](VALIDATION.md) for the supplied historical report, [the integration report](../../validation/Output_Dither/INTEGRATION_VALIDATION.md) for checks in this repository, [validation/TESTING.md](../../validation/Output_Dither/TESTING.md) for repository-layout reproduction instructions, and [SOURCES.md](SOURCES.md) for primary references.
