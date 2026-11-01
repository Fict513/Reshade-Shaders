# Resource and execution accounting

At 3440×1440, N = 4,953,600 pixels. The effect allocates exactly one full-resolution **R32F** luminance texture, one mip level: **19,814,400 bytes = 18.896484375 MiB** of logical texel data. Actual GPU allocations may include row/tile alignment. No temporal buffers, depth buffers, half-resolution surfaces, external textures or detail-only render targets are allocated.

Two fullscreen passes execute in every quality/feature configuration:

1. PrepareLuminance: one point COLOR read per active pixel, decode RGB, write R32F luminance.
2. ApplyDetail: one point COLOR read, luminance neighborhood reads, composition/diagnostic, write back to the existing destination.

| Quality / feature | Luma taps in final pass | COLOR taps across both passes | Nominal total texture instructions/pixel | Passes | Owned logical memory |
|---|---:|---:|---:|---:|---:|
| Any tier, detail compiled out | 9 point | 2 | 11 | 2 | 18.8965 MiB |
| Any tier, detail strength zero | 9 point | 2 | 11, if uniform branch is honored | 2 | 18.8965 MiB |
| Normal, detail active | 9 point + 8 bilinear | 2 | 19 | 2 | 18.8965 MiB |
| High, detail active | 25 point | 2 | 27 | 2 | 18.8965 MiB |
| Ultra, detail active | 25 point | 2 | 27 | 2 | 18.8965 MiB |

Counts are source-level texture instructions on the active path, not bandwidth or measured hardware instructions. A bilinear instruction can access four texels; caches/coalescing matter. Early bypass skips the final neighborhood and preparation's COLOR read, but still draws both passes. Runtime zero detail is a uniform branch; compiling detail out guarantees its sampling code is absent. No pass or texture is exclusively for detail, so none can be removed without also removing fine analysis.

ReShade also maintains its own COLOR snapshot/resolve and the destination. Those are runtime resources, not new allocations owned by this effect. For orientation, an RGBA8/RGB10A2 full-resolution surface is 18.8965 MiB; RGBA16F is 37.7930 MiB. Runtime sharing, copies, MSAA resolution and other effects affect total application memory. Do not add these figures blindly to effect-owned memory.

Both samplers and passes use non-sRGB views/flags. The luminance texture uses floating point even for SDR 8-bit output. All arithmetic is `float`/FP32; no `half`/`min16float`, packed math or approximate bit-hack transfer functions are used. GPU compilers can still contract/reorder operations; the CPU adapter disables FMA contraction to make its own behavior reproducible.

Numerical consequences measured in the included run:

- A 0.0001-amplitude low-contrast pattern around linear 0.2 had residual RMS error about 1.67e−5 when luminance storage was simulated as FP16, versus 1.37e−9 for FP32 storage. This experiment isolates storage quantization; it is not a second GPU implementation.
- On the full-resolution smooth texture test, Normal versus High differed by at most 2.98e−8 analysis/output scRGB units. Simulating 8-bit bilinear fractional weights increased the maximum to 8.94e−8. Those are small numerical differences, not evidence that High visibly improves games.
- High and Ultra were bit-identical in all adapted comparisons.
- PQ float32 arithmetic has larger transfer errors than sRGB. The full data, final code-space rounding tests, and limits are in `VALIDATION.md`.

There are no measured GPU timings or FPS results. Two passes, a full-resolution intermediate, transfer-function arithmetic and texture reads all carry costs; measure with ReShade's GPU timing UI on the actual game/API before choosing a tier.
