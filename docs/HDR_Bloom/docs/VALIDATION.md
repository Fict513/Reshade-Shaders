# Supplied-package validation report — HDR Bloom 1.0.0

This is the historical report shipped with the supplied HDR Bloom 1.0.0
package, executed on 2026-10-31 by its package author. It is retained for
provenance and is not a new validation claim for this repository. New
integration checks are recorded separately in
[`validation/RELEASE_VALIDATION.md`](../../../validation/RELEASE_VALIDATION.md).

Executed on 2026-10-31. All numerical evidence describes this package, not a game/GPU/display capture.

**352 checks passed; 0 failed.** The main compiler check comprises 288 actual FX preprocessor/parser/code-generation runs.

## What ran

| Evidence level | Status | Scope |
|---|---|---|
| Analytical argument | Completed | Extraction continuity, Gaussian normalization, mirrored borders, mean-preservation conditions, limiter direction |
| Independent float64 CPU reference | Executed | Transfers, area resampling, integer-tap filtering, reconstruction, compositing and rounding |
| Production scalar float32 functions | Executed | Same shipped Math.fxh compiled directly as C++ using float overloads; transfer, extraction fraction and channel limit |
| Adapted production float32 spatial arithmetic | Executed | Nine-tap area-overlap loop and paired Gaussian arithmetic compared with independent reference; ideal CPU bilinear sampling |
| Modeled full pipeline / intermediate quantization | Executed | CPU reference with float32 arithmetic and optional FP16 quantization after each intermediate write |
| Official ReShade FX front end | Executed | Unmodified upstream preprocessor/parser, HLSL shader-model-5 and GLSL generation; all valid compile-time features and dimension overrides |
| Offline DXBC/DXIL or driver shader compiler | Not executed | No installed dxc/glslang or Windows driver compiler was found |
| GPU driver/runtime execution | Not executed | No available GPU device/runtime was found |
| In-game visual/display measurement | Not executed | No game or target display available |

Native C++ float32 is not GPU execution. GPU pow/exp, FMA, denormal handling, bilinear interpolation precision and target rounding may differ. CPU pipeline alpha/identity assertions plus source inspection and FX code generation are evidence for implementation logic, not a captured GPU bit-comparison.

## Transfer functions

- Dense PQ float32 encoded roundtrip (100,001 values): maximum absolute encoded error **1.42998314e-05** (~0.01463 of a 10-bit code). All 1,024 PQ input codes roundtrip to the same rounded code.
- Dense sRGB float32 roundtrip: maximum error **1.04045868e-07**. All **256 grayscale input codes** roundtrip to the same rounded 8-bit code.

| Linear nits | Production float32 PQ | Decoded float32 nits |
|---:|---:|---:|
| 0 | 7.3095589e-07 | 0 |
| 0.001 | 0.00630235439 | 0.000999994343 |
| 0.01 | 0.0214861799 | 0.00999996811 |
| 0.1 | 0.0623371676 | 0.100001268 |
| 1 | 0.149945453 | 0.999990642 |
| 80 | 0.485857099 | 80.0008621 |
| 100 | 0.50807786 | 99.9997253 |
| 203 | 0.580690324 | 203.004486 |
| 1000 | 0.751829386 | 1000.04376 |
| 4000 | 0.902573347 | 3999.95679 |
| 10000 | 1 | 10000 |

PQ encode(0) has the standards-defined tiny nonzero mathematical code; it rounds to zero at 10 bits. Zero-strength/bypass does not roundtrip through it. The measured errors include cancellation/rounding in CPU float32.

## Preservation, units and color

- Source inspection confirms an immediate `return original` before transformations for zero strength, Auto-unknown and Safe bypass; split-original and invalid-source paths likewise bypass. CPU float4 bit-identity tests cover zero strength in all five mode selector values. Every valid mode has a modeled active alpha bit-identity test; all FX diagnostic variants compile and directly carry original alpha. No blending is enabled.
- Tests cover black, neutral gray, near-black/high-nit PQ reference points, saturated primaries, signed positive-Y out-of-gamut lights, nonpositive-Y colors, and finite FP16 scRGB maximum values converted into nits. A negative component remains negative through extracted signed-color examples and isolated spatial diffusion.
- Isolated light tests verify common linear RGB component ratios across the redistributed field when no limiter applies. This is not a perceptual hue metric, a gamut proof, or evidence that mixed neighboring lights keep an unchanged hue.
- Output-domain tests use random SDR/PQ source and bloom values, saturated faces and production scalar limiter functions. A blocked channel can veto all of the proposed delta. Numerical common-scale limiting is verified against the independent implementation.
- Knee tests cover normal, zero-width and oversized knees; they verify bounded fractions, monotonic extracted luminance and continuity at both transition endpoints. SDR extraction uses reference-white fractions and HDR extraction uses nits. All nine preset parameter sets produce finite modeled output and retain alpha.

## Spatial normalization and conservation

Constant fields, impulses, thin lines, checkerboards and strong edges were evaluated. 1×1, 17×1, 1×19, 3×2, 65×33, 192×128 and 3440×1440 numerical cases include center/edge/corner impulses. Mirrored Gaussian matrix row/column sums were checked for all tiers and small/odd grid sizes. Constants remain constant to the floating-point tolerances in the test code.

| Size | Impulse location | Blurred sum / extracted sum |
|---|---|---:|
| 65 × 33 | center | 1.0150313367 |
| 65 × 33 | corner | 0.9999604065 |
| 65 × 33 | edge | 1.0049984657 |
| 192 × 128 | center | 1.0000000250 |
| 192 × 128 | corner | 1.0000000058 |
| 192 × 128 | edge | 1.0000000213 |
| 3440 × 1440 | center | 0.9999980549 |
| 3440 × 1440 | corner | 0.9999980705 |
| 3440 × 1440 | edge | 0.9999980449 |

The largest measured sum-ratio departure across the tested dimensions was **1.7301%** (17×1, center). This is predominantly odd-ratio bilinear reconstruction, not a claim of exact conservation. At 3440×1440 the tested ratios are much closer to one; these samples are not a worst-case bound for every image. Signed RGB sums, output-limited images, diagnostics and split view have the exceptions described in ARCHITECTURE.md.

## Compositing comparison

Same normalized filters and 0.065 strength, without an extra tone mapper. Y sums are source-unit sums across pixels, not total physical emitted power.

| Mode, isolated light RGB | Source Y sum | Additive Y sum | Redistribution Y sum | Core max before / after |
|---|---:|---:|---:|---|
| 1, [1, 1, 1] | 64 | 65.664 | 64 | 1 / 0.99031 |
| 1, [1, 0, 0] | 13.606 | 13.808 | 13.606 | 1 / 0.99447 |
| 1, [0, 1, 0] | 45.773 | 47.999 | 45.773 | 1 / 0.98187 |
| 1, [0, 0, 1] | 4.6208 | 4.6221 | 4.6208 | 1 / 0.9999 |
| 2, [1000, 1000, 1000] | 64000 | 67120 | 64000 | 1000 / 981.83 |
| 2, [3000, 0, 0] | 50438 | 52677 | 50438 | 3000 / 2950.4 |
| 2, [0, 0, 10000] | 37952 | 39379 | 37952 | 10000 / 9859.9 |
| 3, [2000, -200, 100] | 18520 | 18702 | 18520 | 2000 / 1992.7 |

Redistribution keeps these unrestricted test totals close to their source totals while reducing bright cores. Additive raises them. Overlapping lights at encoding boundaries can activate the shared-increment limiter and break that balance. Neither approach preserves shadow values near an emitter.

## Quality consistency

At spread 1, height 1440 and width 256, a central extracted impulse gives:

| Tier | Filtered sum | RMS radial spread, px | Peak |
|---|---:|---:|---:|
| Normal | 10000.00000000 | 29.27866854 | 90.82147118 |
| High | 10000.00000000 | 29.27866854 | 90.82147118 |
| Ultra | 10000.00000000 | 29.27866854 | 90.82147118 |

This narrow synthetic strip uses the documented mirrored boundary; the measured RMS is not a universal infinite-image radius. At the largest tested sigma (3.014 texels), a wider independent reference measures decreasing tail-approximation error as quality increases. Small residual radius differences are caused by Gaussian tail truncation, not different strength/spread settings. At ordinary/default sigma all tiers agree to practical precision.

## Motion: what the filter cannot fix

- A fixed-energy **already extracted** light moved through 17 subpixel positions over two pixels: sum ranges 10000.000000000–10000.000000000; peak changes by **5.210%** relative to mean peak. This remaining phase variation is the discrete pyramid/reconstruction approximation.
- A 1,000-nit one-pixel light, linearly divided across neighboring pixels before the threshold, moved through 33 phases with T=250, K=150: extracted-light sum varies by **43.815%** relative to its mean. Total source luminance is fixed. This isolates nonlinear threshold/coverage sensitivity: extracted light need not stay fixed as the game's rasterized source crosses pixels.
- These are adversarial synthetic point sources, not a prediction of all game content or a percentage of overall scene brightness. Lower strength reduces the visible amplitude; wider knee can soften transitions but cannot guarantee temporal invariance. The game's temporal antialiasing, emissive antialiasing and existing bloom matter. No temporal stabilization or flicker-free claim is made.

## Precision evidence

For a mixed 144×256 HDR/signed scene, full-chain storage error versus float64: FP32 max **0.000443800144 nits**, RMS **7.79067913e-05**; simulated FP16 max **0.689762161 nits**, RMS **0.134159986**. This measures storage quantization and CPU arithmetic with ideal sampling, not GPU interpolation error.

Adapted production nine-tap area-loop maximum error in the tested sizes: 0.00540577993 nits. Paired-blur float32 arithmetic versus independent integer-tap convolution: 0.000854930112 nits maximum across three tiers and spreads 0.5/1/2. FP16 direct-nit storage overflows at 65504 scRGB units × 80; FP32 does not.

## Actual encoded-domain rounding in CPU tests

No dither is applied. Values are encoded then rounded to integer codes with `round(encoded*(2^bits-1))`, then decoded for error measurements. This is a modeled final UNORM quantization stage, not an inference from the display link.

| Format | Test tail range, linear | Unique codes | Samples rounded to zero | Maximum linear rounding error |
|---|---|---:|---:|---:|
| 8-bit sRGB | 1e-8–0.1 reference white | 90 | 2446 / 4096 | 0.0010725969 |
| 10-bit PQ | 0.0001–1000 nits | 768 | 0 / 4096 | 4.2454762 |

These logarithmic ramps stay monotonic after rounding. An actual modeled spatial bloom tail on a dark field also stays monotonic: it contains 13 distinct SDR codes and 63 PQ codes along the sampled tail. The weak SDR tail visibly runs out of codes; mathematical smoothness cannot remove 8-bit banding or preserve sub-half-LSB effects. The PQ error is luminance-dependent and largest near the bright end of the tested range.

## Compiler matrix and reproducibility

Actual preprocessor dimensions: 1×1, 1×17, 19×1, 2×3, 65×33 and 3440×1440. Cartesian product with quality 0/1/2, diagnostics 0/1, Auto contract 0/1/2/3 and HLSL/GLSL gives **288** builds. The harness reads the compiled module and asserts each texture's actual width, height and RGBA32F format, plus 12 passes and 11 owned resources. COLOR's declared placeholder size is excluded because the runtime supplies it. No ineffective test-only dimension macro is used.

Source SHA256: `428d9f7d2c6349bc55d6e373b4d7dfbe7cfbd01d588fdd0ac1ffe7f983cd1945`. Upstream ReShade commit: `7bf9de8b33bcc76c3177007e65d73c72dd0f34c0`.

Environment: Linux-6.18.57-x86_64-with-glibc2.39, Python 3.12.14, NumPy 2.3.5, SciPy 1.17.0. C++ compiler: g++ (Ubuntu 13.3.0-6ubuntu2~24.04) 13.3.0.

On Linux (or an equivalent C++17 environment):

```bash
python3 -m pip install -r tests/requirements.txt
git clone https://github.com/crosire/reshade.git reshade-source
git -C reshade-source checkout 7bf9de8b33bcc76c3177007e65d73c72dd0f34c0
bash tests/build_frontend.sh reshade-source
python3 tests/run_tests.py
python3 tests/extended_tests.py
python3 tests/accounting.py
python3 tests/make_report.py
```

Run from the package directory. `run_tests.py` compiles the production scalar include as a native shared library. Generated compiler executable/shared libraries are local test outputs, not shader dependencies. Raw results are in `results/validation.json`, `extended_validation.json` and `compiler_matrix.json`; generated representative HLSL/GLSL is included. Optional plots are created with `tests/plots.py` and Matplotlib.

## Remaining in-game acceptance checks

After proving the contract: test a still scene and slow pans, fine bright geometry, black surrounds, saturated signs, HUD, scene cuts, dynamic-resolution changes and window/fullscreen transitions. Confirm near-zero unintended output-limit activity, original alpha, no additional haze at the chosen strength, and acceptable GPU cost. GPU performance or display-appearance claims require measurements; none are made here.
