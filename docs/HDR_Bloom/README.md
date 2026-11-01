# HDR Bloom 1.0.0

License: [MIT](../../licenses/HDR_Bloom.txt).

Restrained, original ReShade FX light diffusion for an **already display-mapped game image**. Supports verified full-range PQ/BT.2020, linear scRGB/BT.709, and conventional sRGB-encoded SDR/BT.709. No external shader pack or native add-on is required.

**Safe default: Auto bypasses.** Choose an explicit input mode only after identifying the actual sampled `COLOR` and destination encodings. Windows HDR, a 10-bpc link, FP16 storage, and swap-chain metadata are not sufficient evidence for an intermediate injection point.

The shader redistributes a small portion of bright-source light into its surroundings. It does not lower a display's physical black level, remove IPS glow, create local dimming, or convert SDR into HDR.

## Install

1. Copy **both `HDR_Bloom.fx` and `HDR_Bloom_Math.fxh`** into the same directory in your ReShade effect search path, normally `reshade-shaders/Shaders`.
2. Reload effects. Enable **HDR Bloom - restrained diffusion**. The technique identifier is `HDR_Bloom`.
3. Follow [the input-contract procedure](docs/INPUT_CONTRACT.md). In the shader controls select **SDR sRGB**, **HDR10 PQ**, or **Linear scRGB** as established by that procedure. Input and destination must use the same contract.
4. Start with **Natural Light**. The nine preset INI files provide three looks in SDR, HDR_PQ and HDR_scRGB variants. Import one through the ReShade preset selector, or copy its `[HDR_Bloom.fx]` values into an existing preset. Selecting a standalone INI enables only this technique; preserve your existing technique list when merging.
5. Toggle the effect at a stationary bright source, then move the camera slowly. Check the original/effected split, extraction and signed-change diagnostics. Start with the game's own bloom low or disabled if it already adds too much glow.

Designed for modern ReShade on DX11/DX12, Vulkan or OpenGL with RGBA32F render targets and filtering. Official FX parsing and HLSL/GLSL generation were tested; actual API/driver execution was **not** available. DX9 is not a supported target. If resource creation or driver compilation fails, disable the technique and retain the log; do not substitute UNORM intermediates.

## Controls that matter

- **Strength:** default 0.04, permitted 0–0.25. Fraction of extracted RGB redistributed. Zero immediately returns the original sampled float4, even with diagnostics enabled. The return occurs before decoding. This is a shader-level identity; a later render-target conversion is outside that guarantee.
- **HDR threshold:** default 250 source nits. These are the decoded signal's absolute luminance units, not a measurement of panel output. Choose relative to the game's diffuse white and highlight content: if diffuse white is 200 nits, a threshold around 250–400 nits can favor highlights; a game with highlights below 250 needs a lower threshold.
- **HDR knee full width:** default 150 nits. Extraction starts at threshold minus half this width and reaches ordinary `Y-threshold` excess above threshold plus half the width. Width is capped at twice the threshold, and zero retains continuity but has a slope corner.
- **SDR threshold / knee:** default 0.60 / 0.30 in **linear reference-white fractions**, not measured nits. Linear 1 is reference white. For example, encoded sRGB 0.8 decodes to about 0.604; the threshold is compared with linear luminance, not with encoded RGB. HDR controls have no effect in SDR, and SDR controls have no effect in HDR.
- **Spread:** default 1.0, range 0.5–2.0. At 1440 pixels high, the Gaussian components have nominal sigmas 3, 12 and 48 pixels, multiplied by spread. Scale follows image height and stays isotropic in pixel coordinates. Downsampling and reconstruction add a minimum footprint: halving spread does not exactly halve the entire point-spread function. This is spatial screen-space diffusion, not camera optics in world units.

Threshold is luminance-based. A pure blue primary is much less luminous than equal-valued neutral white; it will not necessarily bloom at the same channel value. Raising saturation is not part of this effect. Bright HUD elements already composited into COLOR can bloom. A luminance threshold cannot identify UI semantically.

## Artistic starting points

| Look | Strength | Spread | HDR threshold / knee, nits | SDR threshold / knee, white fractions |
|---|---:|---:|---:|---:|
| Natural Light | 0.040 | 0.8 | 250 / 150 | 0.60 / 0.30 |
| Cinematic Glow | 0.065 | 1.6 | 300 / 200 | 0.65 / 0.40 |
| Neon Control | 0.025 | 0.7 | 250 / 200 | 0.18 / 0.24 |

Neon Control uses less redistribution; its lower SDR threshold lets saturated red/green lights participate without independently thresholding channels. These settings are artistic presets, **not monitor calibration**. No preset assumes that 10,000 nits is the monitor peak.

## Diagnostics

All diagnostic RGB is constructed in the selected linear primaries, then encoded correctly to the selected destination. Original alpha is retained. HDR diagnostic component white is 80 nits; SDR diagnostic component white is reference white. These views are false-color measurements, not HDR scene previews.

| View | Meaning |
|---|---|
| Extracted source | Gray `Y(E)/(Y(E)+T)`, where E is full-resolution extracted RGB and T is threshold. Half-gray at extracted Y=T. Does not display source chromaticity. |
| Incoming bloom | Gray `Y(strength*blur(E))/(Y(strength*blur(E))+T)`, before source subtraction and output limiting. This is the incoming light, not net change. |
| Signed luminance change | Actual linear `Y(result-source)` after limiting. Cyan = increase; magenta = decrease; black = zero. Magnitude `abs(change)/(abs(change)+0.1*T)`. Does not include final encoded quantization. |
| Output-limit activity | Red intensity `1-accepted_fraction` of the proposed RGB increment. Black = unchanged increment; full red = increment vetoed. Normally black in scRGB. |
| Original/effected split | Left of the split is original; right is effect or selected diagnostic. No line drawn. |

Strength zero, unknown contract, Safe bypass, invalid source pixels and exceptional arithmetic fallback return original samples. Invalid-source fallback is not separately color-coded.

## Quality and cost

Set a ReShade preprocessor definition and reload:

```c
HDRBLOOM_QUALITY=0  // Normal
HDRBLOOM_QUALITY=1  // High, default
HDRBLOOM_QUALITY=2  // Ultra
```

All tiers use the same pyramid, mixture weights, nominal radius and strength. They retain progressively more of the same normalized discrete Gaussian tail. At default spread the difference is negligible; at maximum spread High and Ultra reduce tail truncation error. No artificial intensity or spread boost is attached to a tier.

`HDRBLOOM_DIAGNOSTICS=0` removes diagnostic/split uniforms and code. Default is 1. These are the only optional compile-time features, alongside the verified Auto contract described below. Unneeded blur levels are never allocated. No dithering feature is included: the final quantization stage has not been established, and a display-link bit depth does not establish it.

At 3440×1440 all tiers use **12 passes, 11 RGBA32F intermediates, 65.47 MiB of nominal texture storage**. High uses approximately **12.266 full-resolution-equivalent logical texture samples per output pixel**, excluding ReShade's own COLOR copying. No GPU time or FPS has been measured. [Full accounting](docs/PERFORMANCE.md).

## Alongside HDR IPS Enhance and Adaptive Detail

Both shaders are included in this repository. HDR IPS Enhance processes verified
PQ/BT.2020 or scRGB/BT.709 and preserves that encoding; HDR Bloom has matching
explicit modes. Adaptive Detail also supports verified SDR sRGB. This shared
contract does not establish that a specific game's injection path honors it,
and their combination has not been rendered or compatibility-tested. For
verified native HDR, **HDR IPS Enhance -> Adaptive Detail -> HDR Bloom** is a
source-based starting order: contrast and detail before diffusion. Do not use
HDR IPS Enhance in SDR; keep each shader bypassed until its actual sampled
`COLOR` and destination encodings are established.

## Validation and limits

Read [VALIDATION.md](docs/VALIDATION.md) for actual executed checks and measured limits, [ARCHITECTURE.md](docs/ARCHITECTURE.md) for the compositing and conservation analysis, and [INPUT_CONTRACT.md](docs/INPUT_CONTRACT.md) before enabling the effect.

This is a delivered implementation with reproducible numerical and real FX front-end checks. It has not been tested in-game or on a GPU/display. There is no GPU runtime here, no physical display measurement, no HDR screenshot judgment, and no GPU driver compilation result. Smooth mathematical tails can still band after 8-bit rounding; tiny moving highlights can still change extraction as their pixel coverage crosses the threshold. Those limitations are measured rather than hidden.
