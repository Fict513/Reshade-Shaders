from pathlib import Path
import json, subprocess
P=Path(__file__).resolve().parents[1];w,h=3440,1440;n=w*h
meta=json.loads(subprocess.check_output([str(P/'tests/fx_frontend'),str(P/'HDR_Bloom.fx'),str(w),str(h),'1','1','0','h',str(P/'results/default.hlsl')],text=True))
subprocess.run([str(P/'tests/fx_frontend'),str(P/'HDR_Bloom.fx'),str(w),str(h),'1','1','0','g',str(P/'results/default.glsl')],check=True,stdout=subprocess.DEVNULL)
textures=[t for t in meta['textures'] if not t['name'].endswith('Source')]
mem=sum(t['width']*t['height']*16 for t in textures)
def overlap_sum(n,m):
 import math
 return sum(sum(min((j+1)*n/m,i+1)>max(j*n/m,i) for i in range(math.floor(j*n/m),min(n,math.ceil((j+1)*n/m)))) for j in range(m))
a,b=w,h;levels=[];fetch=0
for i in range(1,6):
 x,y=(a+1)//2,(b+1)//2;lookups=overlap_sum(a,x)*overlap_sum(b,y);fetch+=lookups
 levels.append((i,x,y,lookups));a,b=x,y
blurpixels=2*sum(x*y for i,x,y,_ in levels if i in [1,3,5])
lines=['# Resource and performance accounting\n','Computed from actual FX module texture metadata and the implementation. No GPU timings/FPS are inferred.\n','## At 3440 × 1440\n','| Intermediate | Dimensions | Format | Bytes |','|---|---:|---|---:|']
for t in textures:lines.append(f"| {t['name'].split('__')[-1]} | {t['width']} × {t['height']} | RGBA32F | {t['width']*t['height']*16:,} |")
lines += [f'\n**Total: {mem:,} bytes = {mem/2**20:.4f} MiB.** This is logical texture storage, excluding alignment, descriptors, drivers, ReShade COLOR copies, game targets and swap-chain images. All tiers allocate the same resources. Eleven intermediates are used; COLOR is external and excluded.\n','## Passes and sampling\n','Five area-prefilter/downsample passes, six blur passes (three horizontal/vertical pairs), one final composite = **12 passes**. Intermediate alpha channels are not used; all intermediate alpha is zero. Every output path carries original COLOR alpha.\n','| Pass group | Output size | Logical samples per output pixel |','|---|---|---:|']
for i,x,y,c in levels:lines.append(f'| Down {i} | {x} × {y} | up to 9; mean {c/(x*y):.5f} at this size |')
lines += ['| Blur H/V at levels 1,3,5 | Matching level | 11 / 13 / 15 for Normal / High / Ultra, maximum |','| Final composite, normal active view | Full resolution | 4: original + 3 reconstructed blur levels |','\nThe loops in Downsample have nine candidate taps, but zero-overlap taps are branched out. Counts below include only positive overlaps, assuming branches avoid those fetches. A compiler may schedule zero-weight fetches anyway: the separate upper bound counts all nine. At tiny sigma some Gaussian pair weights underflow to zero and can skip fetches. Blur counts below assume all pairs are active.\n','| Tier | Logical blur fetches / blur pixel | Total logical fetches / full-res pixel | Nine-candidate upper bound |','|---|---:|---:|---:|']
for name,taps in [('Normal',11),('High',13),('Ultra',15)]:
 normal=(fetch+blurpixels*taps+4*n)/n;upper=(9*sum(x*y for _,x,y,_ in levels)+blurpixels*taps+4*n)/n
 lines.append(f'| {name} | {taps} | {normal:.6f} | {upper:.6f} |')
lines += ['\nA logical bilinear sample can involve up to four texels; it is not four shader sample instructions. Pairing converts 21/25/29 integer Gaussian taps into 11/13/15 bilinear fetches. Axis-aligned centers ideally use two texels for each pair; actual texture hardware, interpolation precision and caching determine physical bandwidth. No byte-bandwidth number is asserted from these logical counts.\n','The first downsample performs transfer decoding, luminance and extraction for each positive-overlap source sample. The final pass decodes/extracts original and encodes the result again. Blurs evaluate exponential weights and normalize them; wider tiers add weight arithmetic as well as fetches. These costs, register pressure and driver optimization are not captured by sample counts alone.\n','At zero strength/unknown mode, downsample and blur pixel shaders return zero without samples and final returns one original sample. The technique still submits 12 passes and writes intermediates; disable the technique to remove that overhead. Split/diagnostic mode does not reduce the preceding filter passes. `HDRBLOOM_DIAGNOSTICS=0` removes its code/uniforms, not textures used by the main effect. There are no unused levels or blur textures to prune by quality: all five downsample levels contribute to the three-scale profile.\n','Reproduction: `python3 tests/accounting.py` after building the FX front end.']
(P/'docs/PERFORMANCE.md').write_text('\n'.join(lines)+'\n')
print(json.dumps({'bytes':mem,'MiB':mem/2**20,'active_downsample_fullres_equivalent':fetch/n,'blur_pixels_fullres_equivalent':blurpixels/n}))
