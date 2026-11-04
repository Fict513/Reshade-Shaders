# Signal and dither contract

## What this injection point supplies

ReShade FX documents `texture2D : COLOR` as the back-buffer contents. At the pinned runtime source revision, `add_effect_permutation` creates `color_tex` in the effect target's format, with raw and sRGB views. `render_technique` copies the preceding back buffer to it before the pass. A pass without an explicit custom target writes the supplied effect back buffer. These paths do not magically provide the previous shader's unquantized arithmetic results. An add-on may supply a different target; inspect that setup rather than assuming ordinary presentation behavior. Source anchors are in SOURCES.md.

The sampler explicitly sets `SRGBTexture=false`; the pass explicitly sets `SRGBWriteEnable=false` and `BlendEnable=false`. Runtime binding selects the corresponding raw view. Both COLOR and noise use point filtering and explicit mip zero. Thus sRGB/PQ encoded numbers remain encoded numbers. There is no hardware sRGB decode/re-encode requested, no interpolation of input codes, and no shader-controlled change to the back-buffer storage format. Writing to UNORM still quantizes even with sRGB writes disabled.

The GPU fixture binds matching raw views independently of ReShade. It verifies this shader on D3D11, not the runtime's installation or every API's view creation. A successful bytecode compile is not a successful driver compile, and driver execution is not an in-game inspection.

## Three distinct cases

Let L=255 or 1023 and Q(x)=floor(L*clamp(x,0,1)+0.5)/L, an ideal nearest-code full-range quantizer. Let n be the centered mask sample and S the strength.

1. **Precise input:** evaluate Q(x+S*n/L). At S=1 the finite uniform mask approximates stochastic rounding: the proportion of adjacent codes represents the sub-code fraction, subject to spatial correlation, finite samples, clipping and actual hardware conversion behavior. Quantization error is not removed; some low-frequency structure becomes high-frequency noise. RMS can increase.
2. **Already quantized:** x=k/L. Since abs(S*n)<0.5 for S<=1, Q(k/L+S*n/L)=k/L for the ideal quantizer. Example: k=100, L=255, n in [-0.498046875,+0.498046875]; all perturbed values still round to 100. For a precise value (100.25)/255, one quarter of the full-tile mask values produce 101 and three quarters 100. Once that value was rounded to 100, that fractional information is gone. Doubling the span in a CPU-only experiment moves roughly half the existing codes but increases error relative to the original gradient.
3. **Unknown downstream conversion:** the composition is Q_unknown(F(x+dither)). Without knowing F, its local derivatives, range handling and quantizer, this package cannot claim the intended distribution, code amplitude or benefit.

Actual D3D11 FLOAT→UNORM conversion permits 0.6-code tolerance, rather than requiring exact 0.5-code rounding. Consequently the ideal equality in case 2 is not a hardware invariance guarantee. On this RTX 4070 Ti test configuration, about 3.1% of channels on a full-range same-grid ramp moved down one code at S=1. This is a measured limitation, not a reason to increase strength or claim standalone debanding. The production shader does not quantize explicitly or add a compensating brightness offset.

## Static blue noise and finite statistics

The original generator implements toroidal Gaussian void-and-cluster ranking with sigma=1.5, 128×128 samples, PCG64 seed 20261104, and a 1,638-point initial population. It relaxes that pattern, ranks removed clusters downward, adds voids to half occupancy, then removes clusters of the inverted pattern to complete all 16,384 ranks. Consecutive groups of 64 ranks become bytes 0…255. This is a generated void-and-cluster mask, not a renamed hash, Bayer matrix or filtered white-noise texture. Spectrum tests include the scalar mask and thresholded point patterns.

R8 sampling returns b/255. The shader maps this to

    n = (255*sample + 0.5)/256 - 0.5 = (b+0.5)/256 - 0.5

This centers **midpoint bins**. Every byte occurs exactly 64 times. Over the full tile:

- Mean = 0 exactly in the ideal representation.
- Peak = ±127.5/256 = ±0.498046875.
- Actual peak-to-peak = 255/256 = 0.99609375.
- RMS = sqrt((256²−1)/(12*256²)) = 0.2886729321699181.
- At strength S, these amplitudes are multiplied by S and expressed in target code steps; encoded-value amplitudes are additionally divided by L.

The shader samples `(floor(uv*resolution)+0.5)/128` using point/wrap addressing, mip zero. It does not stretch the mask to the viewport, rotate it, vary it with time, use half-pixel-dependent linear filtering, or generate mipmaps. The toroidal construction includes edge neighbors. Wrapping is statistically comparable to interior transitions, not a guarantee that repeated patterns are invisible.

Tiling periods are 15×8.4375, 15×9.375, 20×11.25 and 26.875×11.25 tiles at the four requested resolutions. Small crops need not have zero mean: the full-frame mean at 1920×1080 is -0.0000119527 code-step units before multiplying by S, while a 1×1 crop is simply one value (-0.337890625 at the origin). Static noise has no temporal convergence; panning content can still make the screen-fixed pattern apparent. No downstream temporal accumulation is assumed. Frame generation, resampling or subsequent processing can alter it. No temporal mode is supplied.

## RGB choice

One scalar sample is added to all three **encoded** channels by default and exclusively in production. It avoids visible colored speckle on neutrals at the same channel grid, and costs one noise lookup. Quantization errors are then correlated; neutral luminance fluctuations can be greater than with decorrelated channels.

Tests compare this with three spatially shifted copies of the same tile. Pairwise correlations were about 0.01114, 0.00211 and -0.00267, not exact independence. On a neutral 0.5 sRGB field, ideal quantization gives zero opponent-channel difference with correlated noise, versus 0.70425-code opponent RMS with the shifted alternative. On a non-neutral color, correlated noise still changes chroma. Nonlinear decoding also changes linear luminance even when encoded noise has zero mean. **No exact hue, luminance or saturation preservation is claimed.** A decorrelation control was omitted to keep the useful default simple.

## Endpoints, alpha and invalid values

For valid normalized SDR/PQ RGB, each exact 0 or 1 channel returns itself before arithmetic. Thus black, white and pure RGB/CMY endpoint colors remain exact in the shader; signed zero is retained in that branch. Other channels in a partially saturated color may still change.

For other valid channels, output is explicitly `clamp(x+S*n/L,0,1)`. Clipped noise is **not unbiased before quantization**. There is no symmetric fade that would create an additional low-strength region. At S<=1, out-of-range pre-clamp values would already map to endpoint codes under the ideal quantizer, so this clamp leaves the ideal quantized result unchanged. For a constant field enumerating the whole mask at S=1, the finite probability error is at most 1/512 code in the ideal quantized mean, excluding implementation floating-point tolerance. That is not a local-image, lower-strength or hardware guarantee.

Example at x=0.1/L: clipping raises the prequantizer mean by 0.07999878/L, while the ideal finite-mask quantized bias is +0.0015625/L. At x=0 the exact-endpoint branch overrides noise entirely. At very small fractions below the first finite threshold, no sample rounds up; finite 256-level dithering cannot represent arbitrarily small probabilities. Hardware testing showed larger low-end bias; consult the measured tables.

If **any RGB channel** is NaN, infinite, negative or above 1 in a supported mode, the entire original sample returns. Comparisons are ordered and fail the valid-domain predicate for NaN. Alpha is not sanitized or used to gate RGB: it is always the original sampled alpha, including a nonfinite alpha. Unknown/scRGB, mismatched or corrupted contracts, master bypass, and strength 0 return the original sample without arithmetic on color. Negative, >1 or nonfinite strengths also bypass. Signed and extended scRGB are never clamped by the shader.

These are **sample-level** return guarantees. Texture decoding, denormal flushing, NaN payload canonicalization, render-target format conversion and the platform can still change storage bits. Use a compatible floating-point target to preserve signed/extended scRGB; a UNORM target cannot store it. Turning the technique off avoids even its copy/write path. Tested FP32 and FP16 bypass fixtures preserved the tested bits, not every possible NaN payload on every API.

## Why linear scRGB is unsupported

Uniform encoded dither must be applied in the domain of the assumed quantizer. An equal linear-light increment has a strongly varying sRGB/PQ code increment. The CPU fixtures include both transfer curves, with PQ linear values normalized to 10,000 nits for this deliberately incorrect example. This is distinct from scRGB's 80 nits/unit scale. A fixed scRGB step cannot account for subsequent BT.709→BT.2020 conversion, white scaling, tone mapping, gamut management and PQ encoding. Implementing inverse downstream processing without knowing it would violate the input/output contract. scRGB therefore always bypasses.
