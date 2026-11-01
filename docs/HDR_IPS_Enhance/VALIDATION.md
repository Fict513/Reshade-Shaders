# Supplied-package validation report — HDR IPS Enhance 1.0.1

This is the historical report shipped with the supplied HDR IPS Enhance 1.0.1
package, including its 2026-10-31 audit. It is retained for provenance and is
not a new validation claim for this repository. New integration checks are
recorded separately in
[`validation/RELEASE_VALIDATION.md`](../../validation/RELEASE_VALIDATION.md).

**23 CPU tests passed; 127 official ReShade FX parsing/code-generation configurations passed. No GPU driver compilation or in-game visual testing was performed.** This report supersedes the original package's report, including its invalid resolution-testing claim.

## What actually ran

Python 3.12.14, NumPy 2.3.5 and g++ 13.3.0 on Linux. Official, unmodified ReShade front-end sources pinned to `7bf9de8b33bcc76c3177007e65d73c72dd0f34c0` were built with the included CLI. No usable DXBC/DXIL/NVIDIA compilation or graphics runtime was established. No timings, FPS, monitor measurements or visual approval are claimed.

The 16 existing tests were rerun, followed by seven new test methods. Scalar math is compiled directly from the production include. New adapters extract production vector/Main or local-filter bodies into C++ float, with float constants and contraction disabled. They strip FX semantic/loop annotations and emulate vector operations and texture reads. Main's adapter compiles local out; the separate local adapter executes each quality's filter with emulated R32F guide and point sampling. NumPy provides an independent predominantly double reference. CPU libm, vector evaluation and sampling emulation are not GPU instructions or the ReShade runtime; FMA, compiler reassociation, pow/log accuracy and resource conversions can differ.

## Results

| Check | Observed result and limits |
|---|---|
| PQ reference values / dense round trip | 200001 samples, 1e-6–10000 nits: maximum relative error **2.2568311e-5 (0.00225684%)**, down from baseline 0.01333362%. Reference points include zero, near-black, 100, 203, 400, 1000, 4000 and 10000 nits; exact chosen points are in tests. |
| 10-bit code round trips | All 1024 normalized PQ codes decode/encode/requantize to their original integer codes. |
| Global curve | 81 parameter combinations, 60001 log samples plus zero; no reversals. Protected near-black and anchors return identity. Analytical monotonicity/C1 proof in AUDIT.md. |
| Exact original paths | Production-body CPU tests: zero master in every diagnostic and tested mode; fully neutral normal output; unverified Auto, explicit bypass and invalid PQ. Bit-identical sampled RGBA. |
| Alpha | Original float32 alpha bits retained in all five output/diagnostic choices tested, both supported contracts and bypass. Source audit covers every return path. |
| Gray | Production PQ gray channels equal. scRGB maximum channel spread **1.90735e-6 signal unit** from matrix/float arithmetic; assertions allow 1e-6 relative plus 2e-7 absolute. Neutral bypass remains exact. |
| Signed scRGB | Negative components, >1 values, nonpositive Y, high luminance and 20000 random vectors spanning finite FP16 component range remain finite. Extreme finite FP32 case now returns original rather than NaN. No imposed 0–1 clamp. |
| Saturated PQ / boundaries | 100000 deterministic random colors plus 216 boundary combinations: finite output in 0–1 at maximum global/color controls. Color-only out-of-P3 BT.2020 primary samples retain original. Reference tests separately stress added local gain. |
| Production vs NumPy | Maximum PQ signal difference **5.48363e-6**, about 0.00561 of a 10-bit code, in the random/boundary test. This is measured, not a universal error bound. |
| Diagnostic encoding | 100-nit neutral source selects the documented yellow bin; decoded palette matches linear BT.709 (90,75,0) component nits within stated float tolerance in both modes. Other palette paths execute and preserve alpha; their appearance is not visually tested. |
| Local production function | All 3 qualities × radii 1/6/24 × 5 resolutions (1×1, 1×17, 19×1, 17×31, 48×96) × flat/step/thin-line/noise/ramp: finite, bounded corrections and extrema within float tolerance. Maximum difference from NumPy **1.76320e-6 stop**. Flat correction zero in these cases. |
| Local mean shift | Extracted production filter: maximum absolute mean shift **0.42354%** in its tested images at maximum local strength. Separate original NumPy image set: **0.60013%**. Neither is a general bound or brightness-conservation guarantee. |
| Guide precision | Original independent storage test: R32F vs double guide difference **2.23392e-7 stop**; R16F **0.00185611 stop**. Color is not repeatedly stored in an HDR intermediate. |

## Final PQ gradients after actual 10-bit rounding

65536 log-spaced source samples per interval, input cast to float32 before executing production bodies. Global 0.22, master 0.85, anchor 100 nits, shadow 0.8, highlight 0.85; local/color off. Rounding is `rint(PQ_signal*1023)` in code space.

| Source nits | Original distinct codes | Revised distinct codes | Largest adjacent jump | Revised reversals |
|---|---:|---:|---:|---:|
| 0.001–1 | 148 | 146 | 1 | 0 |
| 0.01–10 | 286 | 273 | 1 | 0 |
| 80–1000 | 273 | 277 | 1 | 0 |

The original production-body float adapter had **three one-code reversals** in the highlight row, despite the original NumPy reference showing none. The revised algebra removes those observed reversals. This is not proof of monotonic quantized output for every GPU or image. Shadow code-count reduction remains the expected consequence of redistributing finite precision. No dithering was added without a verified final quantization stage.

## Actual FX front end

120 HLSL/GLSL × quality 0/1/2 × local off/on × color off/on × presentation 0/1/2/3/4 configurations passed. Seven additional HLSL resolution cases passed at 1×1, 1×17, 19×1, 17×31, 1920×1080, 3440×1440 and 5120×1440. Logs now contain and assert the compiled intermediate texture dimensions. Local enabled produces two passes and one texture; local compiled out produces one pass and no private textures.

This verifies FX preprocessing, parsing, code generation and module declarations. It does not invoke a GPU driver compiler or execute all combinations on a GPU. ReShade host allocation, pass scheduling, sampling views and destination format were reviewed in official source, not captured from a game.

## Remaining limitations and reproduction

GPU driver compilation, real resource/encoding verification, in-game HDR calibration, visible banding/halos, motion and physical monitor response require the target machine. Sparse bilateral filtering can differ across tiers and produce low-contrast rims; higher quality is not proof of convergence on every pattern. Neither global nor local contrast guarantees unchanged scene-average brightness. Begin with Natural HDR and retune with other color processors disabled.

Reproduce with `python3 tools/run_audit.py` and the compiler instructions in `tools/README.md`, then `python3 tools/validate_fx_audit.py /path/to/fxcheck`. Machine-readable results are `validation/audit_numerical_results.json`, `validation/audit_fx_results.json` and `validation/baseline_regressions.json`. The SHA-256 manifest identifies the delivered sources. No third-party shader pack or native add-on is required.
