# Filter design and limitations

## Linear luminance and two bands

Decode RGB according to the established contract. Let Y be linear BT.709 luminance for SDR/scRGB, or linear BT.2020 luminance for PQ. HDR component values are analyzed in nits/80, while SDR uses relative linear values. There is no log transform or nonlinear inverse reconstruction.

Define a separable binomial filter G₁ with 1D weights [1,2,1]/4 and G₂ with [1,4,6,4,1]/16. G₂ = G₁ convolved with G₁. The fine residual is **F = Y − G₁(Y)**; detail is **D = G₁(Y) − G₂(Y)**. G₁ has per-axis variance 0.5 pixel², G₂ variance 1 pixel². The maximum support is one pixel for F and two for D.

These are different, overlapping bands, not two copies of an unsharp mask. On a one-dimensional sinusoid, G₁'s response is cos²(ω/2), so F has response 1−cos²(ω/2), and D has response cos²(ω/2)[1−cos²(ω/2)]. Detail vanishes at Nyquist and peaks at an intermediate frequency. Fine includes higher frequencies. Two-dimensional responses are products of their separable low-pass responses. Adaptation and limiting make the complete filter nonlinear.

Difference-form weighted sums subtract the center before summation. This preserves constant fields exactly in the adapted FP32 implementation and avoids cancellation between independently accumulated bright blur estimates. A flat 3×3 neighborhood returns no correction even if the broader kernel sees variation outside it.

## Continuous protection

The raw correction is master × gate × (fine × F + detail × D). The gate is the product of:

- **Edge gate:** 1/[1 + 12 × edge × (local span / scale)²], with scale = max(|Y|, |G₁(Y)|) + 0.01.
- **Noise gate:** combines local span / [span + 0.04 × noise × scale] with an odd-gradient-to-total-variation coherence score. Alternating patterns, isolated points and weak signals are downweighted. No hard threshold selects a different filter.
- **Near-black gate:** positive Y / (Y + 0.002). Only the correction fades; the source is not blurred. Y ≤ 0 is unchanged.

The contrast ratio is capped at 1e10 before squaring to prevent overflow on extreme signed cancellation; this is far above ordinary display-image contrast.

The constants 0.01 and 0.002 are numerical/perceptual regularizers, not monitor black/peak calibration. In HDR units they correspond to 0.8 and 0.16 nits respectively. These are not hard cutoffs. In SDR they are fractions of relative white. The coherence heuristic cannot separate all noise from real texture, distinguish skin from stone, identify UI, or predict temporal stability. Grayscale texture and noise with similar spatial spectra can receive similar enhancement.

## One limiter for both controls

The shared absolute correction budget is the minimum of:

1. 12% of the local 3×3 luminance range;
2. distance to the local minimum/maximum in the requested direction, plus an extension of (1−edge) × 2% of that range;
3. 12% of positive center luminance;
4. upward gain headroom allowed by the output representation.

For raw correction r and budget B, the applied correction is **δ = r B / (B + |r|)**, or zero when B=0. This is a continuous asymptotic limit. The min operations have continuous values but not continuous derivatives; protection is not an abrupt threshold switch. The only bypass decisions concern exact identities, invalid contracts/values, and nonpositive luminance.

Enabling both bands can increase the requested correction but cannot double this budget. With Edge=1, extrema extension is zero. Strict extrema protection also suppresses useful sharpening of genuine peaks and valleys. The small relaxation at lower settings allows restrained peak strengthening at the cost of permitting correspondingly small overshoot/undershoot. It is not a promise of zero halos at every setting.

## RGB reconstruction

For positive Y, set gain = 1 + δ/Y and RGB′ = gain × RGB. Otherwise keep the source unchanged. Since |δ| ≤ 0.12Y, gain is in [0.88,1.12] before tighter limits. There is no unstable division by an arbitrarily small Y: the bound follows Y and the near-black gate tends to zero. The scalar gain preserves linear RGB ratios and CIE chromaticity, including signed scRGB components; it does not independently sharpen color channels. Equal-luminance chromatic edges therefore receive little or no sharpening. Perceived saturation may still change with local brightness, and finite output quantization can alter channel ratios slightly.

SDR has maximum linear channel value 1; PQ has 10000 component nits (125 analysis units). The upward budget uses the brightest RGB component to avoid crossing those encoding boundaries. This protects saturated highlights without channel-by-channel clipping. For FP16 scRGB the largest absolute component constrains representable magnitude. Negative components are never clamped to zero. The effect adds no gamut mapper and no second tone mapper.

A zero computed correction returns original RGB rather than needlessly re-encoding it. Alpha always remains the original sampled alpha.

## Quality evaluation

Normal pairs the outer [4,1] weights of each 5-tap axis into bilinear samples at ±1.2 pixels, each weighted 5/16, with the center weighted 6/16. In real arithmetic this is the same G₂ kernel as High. The center sample is reused. Clamp addressing makes the pairing work at borders too, including one-pixel dimensions.

High evaluates the full 5×5 kernel with point reads, reusing the 3×3 samples. This avoids finite bilinear coordinate/weight precision; the measured Normal–High differences were small. Ultra is an explicit alias for High, because further sampling has no demonstrated benefit for this kernel. There is no random jitter, temporal history, motion-vector dependency or resolution scaling.

## Diagnostics

Every palette is defined in linear active RGB primaries and encoded through the same output transfer function. HDR palette unit 1 means 80 component nits, not the display peak. These views are inspection tools, not colorimetric comparison images between SDR and HDR.

| View | Exact meaning |
|---|---|
| Split | Original on the left of Split Position; effected image on the right. No drawn divider. |
| Signed correction | t = clamp[(δ / max(abs(Y),0.002)) / 0.05, −1,1]. Linear gray (0.18,0.18,0.18) at zero; interpolates toward orange (0.75,0.22,0.04) for +5% or blue (0.04,0.30,0.75) for −5%. |
| Effective strength | Pre-limiter master × combined protection gates, independent of component-control multipliers. Linear gray = 0.02 + 0.78 × value. Black/constant/nonpositive-Y cases report zero. It is not a measured image-sharpness score. |
| Limiter activity | Removed fraction abs(r)/(B+abs(r)), weighted by abs(r)/(abs(r)+0.001×scale). Linear gray = 0.02 + 0.78 × activity. Zero requests report zero. The weighting fades misleading percentage changes when the request is negligible; therefore this is not an unweighted percentage display. |

## Comparison with existing approaches

A basic unsharp mask adds a fixed center-minus-blur residual. This implementation adds contract-aware linear-light processing, a separate adjacent detail band, coherence/noise and strong-edge gates, common-gain color preservation, output-domain headroom, and one shared limiter. These are design choices, not a claim of a new general sharpening theory.

AMD FidelityFX CAS is the comparison baseline, not a dependency of the shader. Its published sharpening-only path uses contrast-dependent negative-lobe weights and normalized output limits; its default implementation can share green-derived weights across channels. This effect instead computes a luminance correction and applies one gain to the center color, explicitly supports signed/extended scRGB, and controls two bands. The extra pass and R32F texture are costs. CAS also offers efficient GPU implementations and optional scaling; this effect does not scale.

`validation/compare_baselines.py` compares simple unsharp masking, a mathematical grayscale adaptation of AMD's no-scaling CAS path, and this shader on synthetic inputs. Both raw settings and one-texture gain-matched comparisons are recorded. This is not the official GPU CAS implementation, does not cover all CAS modes, and establishes no general perceptual or performance superiority.

## Remaining limitations

There is no semantic protection, denoiser or temporal rejection. Fine grass, wires, grain and specular points can still shimmer more during movement. Small UI text is part of the sampled image and can sharpen. Strict protection may leave genuine peaks almost unchanged. Local asymmetric limiting can cause small mean-luminance shifts. Final 8-bit/10-bit quantization can hide subtle corrections or change a threshold-adjacent code. No dithering or debanding is added. No GPU, display or in-game testing was performed.
