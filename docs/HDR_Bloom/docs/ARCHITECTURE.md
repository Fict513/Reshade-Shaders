# Architecture and color decisions

## Linear signal path

Point-sample encoded COLOR -> validate the asserted contract -> decode each source sample -> luminance-based extraction -> equal-area prefiltered pyramid -> three separable Gaussian blurs -> linear reconstruction and normalized mixture -> highlight redistribution -> incremental domain limiter where needed -> original transfer function -> original alpha.

The first averaging pass decodes and extracts **each participating full-resolution pixel before averaging**. PQ and sRGB codes are never blurred. Thresholding the average instead would make small highlights disappear when a downsampled footprint dilutes them. Filtering remains floating point even with an 8-bit source or destination.

HDR working RGB is in absolute component nits; luminance is `dot(RGB, weights)`. PQ uses BT.2020 weights (0.2627, 0.6780, 0.0593). scRGB and SDR use BT.709 weights (0.2126, 0.7152, 0.0722). SDR instead uses dimensionless linear reference-white fractions. Primaries never change inside the effect, and no second display tone mapper, exposure adjustment, highlight shoulder, guessed panel peak or black correction is introduced.

## Extraction

Let Y be linear luminance, T positive threshold, and K full knee width clamped to [0,2T]. Extracted luminance q is:

- 0 when Y <= T-K/2;
- `(Y-(T-K/2))^2/(2K)` inside the nonzero knee;
- `Y-T` when Y >= T+K/2.

For K=0, q=`max(Y-T,0)`. For Y>0, `E=RGB*min(q/Y,1)`; for Y<=0, E=0. This gives a continuous bright-pass with a continuous first derivative for K>0. The quadratic uses a bounded normalized knee coordinate to avoid squaring large HDR magnitudes unnecessarily. The max/min operations protect the scalar mask; they do not independently threshold or saturate color channels.

For a uniform positive color, extraction preserves its linear RGB ratios. That does **not** prove perceptual hue preservation: intensity-dependent appearance, gamut boundaries, surrounding colors and mixture with other lights still matter.

## Pyramid and profile

The downsample chain has five levels with dimensions `ceil(W/2^l) × ceil(H/2^l)`, l=1..5. Every level integrates the source's piecewise-constant pixel cells over equal-area destination footprints. At most three source pixels per axis overlap a footprint; there are no skipped right/bottom pixels and no duplicated padding pixels. Weights are actual overlap areas divided by footprint area.

Levels 1, 3 and 5 are blurred horizontally then vertically. Levels 2 and 4 are necessary prefilter stages, but have no blur or reconstruction textures. Gaussian weights at integer offset i are `exp(-i*i/(2*sigma*sigma))`, normalized by their finite sum. Adjacent positive offsets (1,2), (3,4), ... are combined by weighted bilinear sampling and mirrored on the negative side. The center weight is 1 before normalization. This is algebraically the same as a discrete convolution with all the individual taps, under ideal bilinear interpolation.

Normal retains offsets -10..10, High -12..12, Ultra -14..14. All target the same discrete Gaussian, and normalization is independent of tier. Extra tail support improves the approximation; at default spread the difference is below practical visual relevance. At the target's largest coarsest-axis sigma, approximately 3.014 texels, L1 error versus a 81-tap reference falls from 0.000932 through 0.0000619 to 0.00000269. This small truncation effect is not an artistic radius change. The kernel is positive and monotonic away from its center; no negative lobes or channel-dependent weights create ringing.

Nominal full-resolution sigmas are 3/12/48 pixels × spread × H/1440. Actual level dimensions determine texel-space sigma separately on each axis. Mixture weights are **0.55 / 0.30 / 0.15**, summing to one. Three bilinear reconstructions are mixed in the final pass, avoiding extra upsample targets. The actual point-spread function also includes area prefiltering and the reconstruction tent. It is not exactly a continuous Gaussian mixture, especially at small resolutions/spread. There is no temporal history, depth or motion-vector dependency.

A first implementation used continuous quadrature nodes; the CPU profile test found a quality-dependent RMS radius error. It was replaced before delivery by this discrete-tap construction. Only the final implementation is shipped.

## Borders

Gaussian samplers use MIRROR: reflection about the outer half-texel boundary, with bilinear interpolation. This keeps constants constant and neither injects black border samples nor repeats an edge pixel outward as an infinite bright strip. A symmetric normalized mirrored convolution has row and column sums of one on its own grid, including a one-pixel dimension. Mathematically it conserves the sum on that grid. It reflects in-frame light back into the frame; it does not estimate light just outside the camera's field of view. The cropped spatial appearance of an edge light therefore differs from an interior light, even though constant fields have no edge falloff or boost.

Equal-area downsampling conserves the **mean**, equivalently the pixel-area-weighted total across grids. Bilinear upsampling preserves constants. It also preserves mean for exact integer scale ratios with this boundary convention, but generally not exactly for arbitrary odd ratios. This exception is measured in the report; the shader is not advertised as exactly energy-conserving for arbitrary images/resolutions.

## Compositing investigation

Conventional additive bloom is `source + s*B(E)`. With normalized filtering its scene mean increases by approximately s*mean(E). It retains bright cores, but raises average light and needs more headroom. This can increase the broad haze the target look seeks to avoid.

The implemented choice is:

`candidate = source - s*E + s*B(E)`

Strength s is clamped to [0,0.25]. At supported nonnegative PQ/SDR inputs, E is a fraction of source; subtraction alone therefore cannot make a component negative. Redistribution lowers the bright core and deposits that light nearby. On a constant field B(E)=E, so the intended change is zero. It still spreads light into shadows: conservation does not mean local contrast or dark visibility is invariant. Restrained strengths and a low 0.15 weight on the broadest component limit, rather than eliminate, that effect.

The tests compare additive and redistribution on neutral, saturated and signed patches. Additive is **not** offered as a second runtime mode: the chosen default directly serves the requested restrained look.

## What conservation does and does not mean

For an unlimited, valid, all-in-frame signal, exact mean preservation by B would make the signed RGB channel sums and luminance sum of the redistribution unchanged. This follows from a linear normalized B, consistent extraction at subtraction and filtering, and the same linear RGB basis/units at both ends. The first pass uses exactly the same Extract function as the final subtraction; there is no alternate low-resolution threshold mask.

The implemented stages support that argument as follows: equal-area downsampling preserves mean; symmetric mirrored blur preserves mean on each level; mixture weights sum to one; equal-ratio mirrored linear reconstruction preserves mean. Exceptions are non-integer/odd reconstruction, arithmetic and texture quantization, output limiting, invalid pixels, split/diagnostic views, target encoding/quantization, and downstream transforms. A split only shows the right-side result; its displayed half-frame is not a closed energy system.

For signed scRGB the conserved quantity is a **signed linear component/luminance sum**, not a sum of positive radiometric energies or absolute RGB magnitudes. Negative components are neither clipped nor converted to positive energy. No claim is made that all mathematical signed colors are physically realizable or that the monitor can display them.

## scRGB: signed and extended

For positive Y, one scalar extraction fraction multiplies the entire signed RGB vector. A negative component travels with that color through all downsampling, blurring and recombination. Nonpositive-Y source pixels extract nothing, but their original values remain and may receive neighboring signed diffusion. No 0..1 clamp, 7.5 limit or arbitrary monitor-nit ceiling exists. An isolated out-of-gamut light can spread negative components into adjacent pixels; this is deliberate preservation of its signed linear representation, not an accidental channel clamp.

Every finite FP16 source value fits comfortably in FP32 nit storage after multiplication by 80. For arithmetic robustness, a source component that is nonfinite or exceeds 1e30 in magnitude is not processed: it is excluded from the bloom source, and the original local sample is returned. The 1e30 threshold is an arithmetic guard, not a display gamut or brightness limit. Exceptional nonfinite input samples themselves are passed through, not sanitized; the effect prevents them from contaminating neighbors. All tested valid signed/extended inputs produce finite output. Downstream display conversion can still map or clip colors.

## PQ and SDR output domain

PQ's representable linear component box is [0,10000] nits, irrespective of monitor peak. SDR's box is [0,1] reference-white units. Even redistribution can move light onto an already bright or saturated neighbor and exceed a box face.

For these modes only, the proposed delta is shortened along **one shared RGB line segment** starting at the valid source. For every component, compute the maximum fraction of delta that remains inside its legal interval; accept the minimum across all channels, at most 1. If limiting occurs, a 2e-6 relative safety margin reduces the accepted increment. There is no per-channel final clip and no full-image tone-mapping curve. Unexpected residual invalid arithmetic falls back to the original pixel.

This preserves the RGB **direction of the proposed change**, not the absolute source chromaticity or perceptual hue. At a saturated boundary, one blocked component can veto the entire increment; that is preferable here to clipping one channel and manufacturing a new fringe. It can suppress otherwise useful bloom at saturated edges. The limiter changes the redistributed light balance and is explicitly observable in the output-limit diagnostic. It limits only the encoding domain; an HDR signal can still be above the real display's capabilities.

## Precision and quantization

All filtering targets are RGBA32F; alpha in these targets is unused zero. FP32 arithmetic handles PQ's full 10,000-nit domain and extended/signed scRGB. FP16 directly storing nits can overflow even when the original FP16 scRGB source is finite (65504 × 80 = 5,240,320 nits). Scaling FP16 storage could avoid overflow for a chosen range, but would add a range policy and quantize weak tails. The measured full-chain FP16/FP32 error comparison justified choosing FP32 consistently, including for SDR. Sampling/filter interpolation precision on actual hardware remains untested.

The final output may still be quantized by its real target or later presentation stages. Exact sRGB encoding is used, not a power approximation; PQ uses the ST 2084 EOTF and inverse. The finite precision of those operations is measured. No transfer roundtrip is performed on explicit bypass, zero strength, the original split half, or an exactly zero delta.

Dithering was considered and omitted: no final target quantization contract was established. If added in a verified future integration, an 8-bit sRGB target would require noise measured in encoded sRGB code units (one LSB = 1/255), and a 10-bit full-range PQ target in PQ code units (one LSB = 1/1023), not in linear nits or scRGB. Bypass paths must remain untouched. This release makes no assumption that a display-link setting identifies that stage.
