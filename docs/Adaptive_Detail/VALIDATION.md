# Supplied-package validation report — Adaptive Detail 1.0.0

This is the historical report shipped with the supplied Adaptive Detail 1.0.0
package. It is retained for provenance and is not a new validation claim for
this repository. New integration checks are recorded separately in
[`validation/RELEASE_VALIDATION.md`](../../validation/RELEASE_VALIDATION.md).

Validated 2026-10-31. **1,158 main checks passed, 0 failed; 54 preset/fixture checks passed.** These counts are assertions, not independent games or visual judgments. Every result can be reproduced with the included tools. No GPU execution or game testing occurred.

## Evidence levels

| Level | Performed | Scope and limit |
|---|---|---|
| Analytical reasoning | Yes | Transfer equations, constant preservation, two band responses, shared bound, common RGB gain, finite output headroom, border pairing |
| Independent CPU model | Yes | Separate float64 NumPy implementation using direct convolutions and full reference transfer functions |
| Adapted production-function execution | Yes | Production scalar core included verbatim in C++; FX preparation/final-pass bodies mechanically adapted, then compiled as FP32 with FMA contraction disabled |
| Actual ReShade FX parsing/code generation | Yes | Unmodified official parser, HLSL SM5 and GLSL generators; 180 configurations, 360 generated backend modules |
| GPU driver compilation | No | No GPU device/compiler runtime, DXC, glslangValidator or NVIDIA execution environment was available |
| In-game/display visual tests | No | No game injection, motion capture, HDR presentation or timing test |

The adapter replaces FX resources/uniforms, vector syntax, semantics and texture intrinsics with a CPU shim. Production branches and expressions remain. Its point/bilinear sampler is a numerical model; it is not the hardware sampler. A second mode simulates 8-bit fractional bilinear weights. It does not emulate every GPU's coordinate, FMA, pow, rounding or NaN behavior. This is stronger than a reference testing itself, but it is not proof of identical GPU execution.

## Main findings

| Measurement | Observed |
|---|---:|
| sRGB dense float32 round-trip maximum code error | 8.94e−8 |
| PQ dense float32 round-trip maximum code error | 1.43e−5 |
| PQ dense decode maximum absolute error | 0.5803 component nits or less, on 100001 code samples through 10000 nits |
| All 256 8-bit sRGB code decode/encode/round trips | Exact integer recovery |
| All 1024 10-bit PQ code decode/encode/round trips | Exact integer recovery |
| Maximum normal-output model difference, SDR encoded | 1.40e−7 |
| Maximum normal-output model difference, PQ encoded | 8.72e−6 |
| Maximum normal-output model difference, scRGB | 1.17e−6 units |
| Final 8-bit SDR rounded reference differences in fixture matrix | Zero |
| Final 10-bit PQ rounded reference differences in fixture matrix | At most one code; 270 RGB-channel comparisons differed, counted across all three tiers |
| Signed-scRGB RGB gain spread from rounding | At most 1.20e−7 |
| Default fine-texture standard-deviation ratio | 1.02506 |
| Default lower-contrast texture standard-deviation ratio | 1.01234 |
| Default Gaussian-noise standard-deviation ratio | 1.02706 |
| Default low-contrast checker standard-deviation ratio | 1.00537 |
| Default high-contrast checker standard-deviation ratio | 1.00265 |

Measurements use the included deterministic fixtures. SDR and HDR fixture magnitudes are described in the script and are not matched display photographs. A standard-deviation ratio is a simple contrast/noise statistic, not perceived sharpness. Low default response is intentional; these numbers do not predict every game.

All zero-master, neutral, unsupported-contract and constant-field checks returned the original sampled bits in the CPU adapter. Every diagnostic preserved alpha, including test NaN and signed-zero payloads. Strict-extrema and shared-budget tests passed in every quality/detail configuration. Saturated primary/secondary and near-black tests stayed within supported code boundaries at the tested extremes. Output grayscale remained neutral.

The largest default fixture mean bias in the SDR matrix was approximately +0.000318 relative-linear units on the alternating high-contrast checkerboard. In the corresponding HDR matrix, the maximum was about +0.00628 scRGB units, or +0.503 nits. That is a small image-dependent bias, not exact mean conservation. The algorithm makes no universal zero-bias promise.

## Investigated discrepancy and fix

The initial limiter diagnostic displayed the unregularized fraction `1 − abs(delta/raw)`. Tiny FP32 PQ decoding changes affected an almost-cancelled residual, producing an encoded diagnostic difference around 0.027 despite closely agreeing normal output. Simply loosening the image-output tolerance would have missed this distinction.

The final diagnostic evaluates the removed fraction without subtracting nearly equal ratios, fades its value continuously for negligible requested corrections, and uses a linear gray pedestal for diagnostic visibility/stability. Independent-reference errors now peak at about 0.000320 PQ code for the limiter diagnostic and 0.000110 for the effective-strength diagnostic on the tested texture. The normal-output maximum remains below 8.72e−6 PQ code. These remaining diagnostic differences are measured, not hidden; the diagnostic is a sensitive analysis display, not an output-equivalence test.

The production float32 reference checks use explicit tolerances. Diagnostic tolerance is 5e−4 encoded units; normal-output tolerance is tighter and contract-specific. The results JSON records exact observed errors. Integer rounding tests compare actual encoded results after rounding, rather than comparing only linear values.

## Motion tests

Continuous synthetic scenes were sampled at 17 phases in 1/16-pixel increments. Tests measure frame-to-frame changes in the **added correction**, not just changes in the already moving source. They expose spatial phase dependence; they do not prove absence of shimmer.

| Sequence | Maximum correction change/frame | RMS correction change/frame |
|---|---:|---:|
| Soft edge | 7.84e−5 | 1.03e−5 |
| Thin peak | 5.91e−4 | 2.08e−5 |
| Near-Nyquist pattern | 2.86e−4 | 9.78e−5 |
| Fine texture | 1.41e−4 | 1.79e−5 |

Units are linear scRGB for these fixtures. Thin peaks and near-Nyquist patterns remain the more sensitive cases. No frame-varying randomness or temporal history is used.

## Coverage

- Exact sRGB toe/branch reference values, PQ landmarks from black through 10000 nits, dense float32 transfer tests, and all native 8/10-bit grayscale codes.
- Zero/neutral/unknown bypass and all diagnostic alpha paths across all six quality/detail combinations.
- Arbitrary constant RGB, neutral gray, near-black and highlight ramps, signed/extended and nonpositive-luminance scRGB, finite FP16 extremes, saturated primaries/secondaries.
- Steps, impulses, thin lines, softened edges, high/low checkerboards, low-contrast textures, Gaussian noise and grain-plus-texture fixtures; mean bias, extrema, shared budget, channel gain consistency.
- All component strengths at maximum in boundary/budget tests; all nine supplied preset files on six patterns.
- Borders and 1×1, 19×1, 1×17, 2×2, 5×3, 31×17 and 3440×1440 CPU images.
- Frontend matrix: three quality definitions × two detail features × five verified-contract definitions × five dimensions, plus 30 target-format combinations. Both backend generators ran for each case.
- Parsed resource metadata confirms R32F luminance dimensions match the requested compile dimensions, two passes, disabled sRGB flags and disabled blending. The COLOR texture's parser placeholder size is semantic metadata, not the runtime snapshot size.
- High and Ultra bit equality; Normal's same intended kernel evaluated with finite float coordinates and optional fractional-weight quantization.

## Baselines and precision

`baseline_comparison.csv` includes a fixed-strength unsharp mask, an adaptation of AMD's exact-arithmetic grayscale CAS no-scaling equations, and Adaptive Detail. A second comparison matches their contrast gain on one low-contrast texture. It is a controlled mathematical comparison, not the official CAS GPU path or a general quality ranking. Raw settings have very different strength scales and must not be compared as equal-strength presets.

FP16/FP32 luminance storage was compared separately; see `RESOURCES.md`. No FP16 quality tier is offered. Fused operations, hardware transcendental precision and resource quantization still need GPU validation.

## Reproduce

Requirements: Python 3 with NumPy, g++ with C++17, and a shell. Matplotlib is optional for the chart. Tested with Python 3.12.14, NumPy 2.3.5 and GCC 13.3.0 on Linux. Windows users can use WSL for CPU/frontend tests; this does not run ReShade in a game.

From the extracted package root:

```bash
mkdir -p validation/build
bash validation/build_frontend.sh validation/vendor/reshade validation/build/fx_frontend
python3 validation/run_validation.py --frontend "$PWD/validation/build/fx_frontend"
python3 validation/compare_baselines.py
```

Without `--frontend`, the numerical checks still run, but the frontend matrix is skipped. The main script regenerates `adapted.cpp` directly from the shipping FX file and compiles all six variants. It then writes results into `validation/results/`. Vendor provenance records the official ReShade commit and every included source hash. The frontend harness is original; the parser/code-generators are unmodified BSD-3-Clause source.

Raw artifacts: `numerical_results.json`, `fixture_metrics.csv`, `frontend_matrix.json`, `preset_validation.json`, `baseline_comparison.csv`, `baseline_configuration.json`, and `filter_behavior.png`.

## Remaining release checks on the user's system

Compile the effect inside ReShade on the actual game/API and confirm the selected contract and views. Compare stationary skin, foliage, UI, shadow gradients and highlights; then pan slowly across each. Check zero/neutral bypass visually and verify the actual output format. Measure GPU cost in-game. Those integration checks are outstanding and are not replaced by this report.
