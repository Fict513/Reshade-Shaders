# Resource and performance accounting

Computed from actual FX module texture metadata and the implementation. No GPU timings/FPS are inferred.

## At 3440 × 1440

| Intermediate | Dimensions | Format | Bytes |
|---|---:|---|---:|
| D1 | 1720 × 720 | RGBA32F | 19,814,400 |
| X1 | 1720 × 720 | RGBA32F | 19,814,400 |
| B1 | 1720 × 720 | RGBA32F | 19,814,400 |
| D2 | 860 × 360 | RGBA32F | 4,953,600 |
| D3 | 430 × 180 | RGBA32F | 1,238,400 |
| X3 | 430 × 180 | RGBA32F | 1,238,400 |
| B3 | 430 × 180 | RGBA32F | 1,238,400 |
| D4 | 215 × 90 | RGBA32F | 309,600 |
| D5 | 108 × 45 | RGBA32F | 77,760 |
| X5 | 108 × 45 | RGBA32F | 77,760 |
| B5 | 108 × 45 | RGBA32F | 77,760 |

**Total: 68,654,880 bytes = 65.4744 MiB.** This is logical texture storage, excluding alignment, descriptors, drivers, ReShade COLOR copies, game targets and swap-chain images. All tiers allocate the same resources. Eleven intermediates are used; COLOR is external and excluded.

## Passes and sampling

Five area-prefilter/downsample passes, six blur passes (three horizontal/vertical pairs), one final composite = **12 passes**. Intermediate alpha channels are not used; all intermediate alpha is zero. Every output path carries original COLOR alpha.

| Pass group | Output size | Logical samples per output pixel |
|---|---|---:|
| Down 1 | 1720 × 720 | up to 9; mean 4.00000 at this size |
| Down 2 | 860 × 360 | up to 9; mean 4.00000 at this size |
| Down 3 | 430 × 180 | up to 9; mean 4.00000 at this size |
| Down 4 | 215 × 90 | up to 9; mean 4.00000 at this size |
| Down 5 | 108 × 45 | up to 9; mean 5.96296 at this size |
| Blur H/V at levels 1,3,5 | Matching level | 11 / 13 / 15 for Normal / High / Ultra, maximum |
| Final composite, normal active view | Full resolution | 4: original + 3 reconstructed blur levels |

The loops in Downsample have nine candidate taps, but zero-overlap taps are branched out. Counts below include only positive overlaps, assuming branches avoid those fetches. A compiler may schedule zero-weight fetches anyway: the separate upper bound counts all nine. At tiny sigma some Gaussian pair weights underflow to zero and can skip fetches. Blur counts below assume all pairs are active.

| Tier | Logical blur fetches / blur pixel | Total logical fetches / full-res pixel | Nine-candidate upper bound |
|---|---:|---:|---:|
| Normal | 11 | 11.199310 | 12.862445 |
| High | 13 | 12.265734 | 13.928870 |
| Ultra | 15 | 13.332158 | 14.995294 |

A logical bilinear sample can involve up to four texels; it is not four shader sample instructions. Pairing converts 21/25/29 integer Gaussian taps into 11/13/15 bilinear fetches. Axis-aligned centers ideally use two texels for each pair; actual texture hardware, interpolation precision and caching determine physical bandwidth. No byte-bandwidth number is asserted from these logical counts.

The first downsample performs transfer decoding, luminance and extraction for each positive-overlap source sample. The final pass decodes/extracts original and encodes the result again. Blurs evaluate exponential weights and normalize them; wider tiers add weight arithmetic as well as fetches. These costs, register pressure and driver optimization are not captured by sample counts alone.

At zero strength/unknown mode, downsample and blur pixel shaders return zero without samples and final returns one original sample. The technique still submits 12 passes and writes intermediates; disable the technique to remove that overhead. Split/diagnostic mode does not reduce the preceding filter passes. `HDRBLOOM_DIAGNOSTICS=0` removes its code/uniforms, not textures used by the main effect. There are no unused levels or blur textures to prune by quality: all five downsample levels contribute to the three-scale profile.

Reproduction: `python3 tests/accounting.py` after building the FX front end.
