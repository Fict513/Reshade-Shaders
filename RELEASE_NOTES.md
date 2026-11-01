# v1.2.0 - HDR shader collection

Adds three supplied, separately licensed effects without changing their
individual source versions:

- `Shaders/HDR_Bloom.fx` 1.0.0 with `HDR_Bloom_Math.fxh`, nine SDR/PQ/scRGB
  presets, and its installation/input-contract guide.
- `Shaders/Adaptive_Detail.fx` 1.0.0 with `Adaptive_Detail_Core.fxh`, nine
  SDR/PQ/scRGB presets, and its guide and third-party notices.
- `Shaders/HDR_IPS_Enhance.fx` 1.0.1 with `HDRIPS_Math.fxh`, three native-HDR
  presets, and its input-contract and tuning guide.

The supplied IPS Depth v2, Selective Deband, and Adaptive Clarity sources were
already present on `main` and match their supplied archives; they remain
unchanged. The existing IPS Suite and FakeHDR Advanced are also retained.
These are alternatives, not replacements: IPS Depth v2 is SDR while HDR IPS
Enhance requires verified PQ/scRGB; Adaptive Clarity is SDR while Adaptive
Detail supports verified SDR/PQ/scRGB. HDR IPS Enhance, Adaptive Detail, and
HDR Bloom have a source-based suggested ordering, but their combined rendering
has not been tested.

**Install:** use the full collection archive or one effect-specific archive.
Copy each `.fx` and its required `.fxh` include together into ReShade's shader
search path, then load only the desired preset. Verify the sampled input and
destination contract before enabling any HDR mode; the HDR shaders default to
bypass or require explicit verification. Existing FakeHDR assets and
individual shader versions are unchanged.

**Validation:** pinned ReShade FX front-end parsing/code generation passed
288 HDR Bloom, 24 Adaptive Detail, 72 HDR IPS Enhance, and 16 full-repository
backend modules. All 51 presets passed technique/uniform reference checks.
See `validation/RELEASE_VALIDATION.md` for exact scope. The supplied CPU reports
are historical; CPU suites were not rerun in this Windows environment because
Python/NumPy/SciPy and a compatible GNU C++ toolchain were unavailable. No GPU
driver, in-game visual, compatibility, or performance results are claimed.
SDR sRGB, full-range HDR10 PQ/BT.2020, and linear scRGB/BT.709 remain distinct
contracts; HLG and unknown/custom HDR paths are not claimed as supported.

# v1.1.0 - IPS Depth v2, Selective Deband, Adaptive Clarity

Adds three SDR ReShade/GShade shaders (original, MIT) with documentation,
individual Balanced / RTX Companion presets at Normal / High / Ultra quality, CPU
reference tests and ReShade FX compiler harnesses:

- `Shaders/IPS_Depth_v2.fx` (`IPSD2_QUALITY`): seven-pass local contrast.
- `Shaders/Selective_Deband.fx` (`SDB_QUALITY`): one-pass selective debanding.
- `Shaders/Adaptive_Clarity.fx` (`AC_QUALITY`): two-pass guarded clarity.
- `Presets/Suite/`: six merged presets (Balanced and RTX Companion x Normal, High,
  Ultra) ordered IPS Depth -> Selective Deband -> Adaptive Clarity, with the
  quality definitions set to 0/1/2 together, IPS Sharpen = 0 and IPS Dither = 0.

FakeHDR Advanced and its validation are unchanged.

Validation (see `validation/README.md` for scope): CPU reference tests passed
(7 IPS Depth v2, 15 Adaptive Clarity, plus the Selective Deband script); the
ReShade FX harness (pinned commit `7bf9de8`) passed 126 / 98 / 80 parse,
module and HLSL SM5 + GLSL generation configurations for IPS Depth v2 /
Selective Deband / Adaptive Clarity; preset structure checks passed. Not tested:
GPU-driver compilation, in-game rendering, visual quality, performance, the
combined stack, or NVIDIA features. No performance or compatibility claims are made.

Release assets: a distribution zip (shaders, presets, docs), a source zip and
`SHA256SUMS.txt`.

# FakeHDR Advanced v1.0.0

Initial release of the supplied SDR HDR-look shader. The seven-pass effect
provides fine, medium and broad local contrast, shadow and highlight controls,
gamut handling, comparison views and optional static dither.

Changes from the supplied source:

- Keep in-gamut saturated colors unchanged by the gamut knee when grading
  amounts are zero.
- Limit brightening to available channel headroom to avoid washing saturated
  highlights toward white. This can limit brightening of saturated colors.
- Guard the sRGB decode power operation against negative inputs.

ReShade FX parsing and HLSL generation passed for quality levels 0, 1 and 2;
the generated HLSL compiled to DXBC and ran on the D3D11 WARP software
rasterizer. This is not GPU-driver or in-game validation. No performance or
visual comparisons have been measured. HDR color spaces reported by ReShade
are passed through; unknown color spaces are treated as SDR.

See the README for installation, limitations and tuning, and
`validation/README.md` for reproducible checks and their scope.
