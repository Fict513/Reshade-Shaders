"""Generate the human-readable measured report from actual result JSON files.
SPDX-License-Identifier: MIT
"""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[2]
RUN=ROOT/'validation'/'.work'/'Output_Dither'
r=json.loads((RUN/'results/results.json').read_text())
g=json.loads((RUN/'results/gpu_results.json').read_text())
def f(x):return f'{x:.6g}'
lines=[
'# Validation report',
'',
'Measured on 2026-11-04. This report is generated from the included JSON evidence, not estimated performance.',
'',
f"**{r['checks_passed']}/{r['checks_total']} analytical/reference/adapted-CPU/compiler assertions passed; {g['checks_passed']} offscreen GPU assertions passed across {g['draws']} draws.** Check counts include variants and individual invariants; they are not independent perceptual trials.",
'',
'## Evidence levels',
'',
'| Level | Status and scope |',
'|---|---|',
'| Analytical reasoning | Ideal full-range nearest quantization, finite-mask mean/probability error and same-grid limitation derived |',
'| CPU reference | NumPy float64/float32 tests, all requested resolutions, endpoint/color/error/spectrum tables |',
f"| Adapted production CPU | {r['adapted_production_cpu']}: exact scalar .fxh plus adapted C++ pixel wrapper; not a shader interpreter |",
f"| ReShade FX parsing/code generation | {r['fx_parsing']['variants']} HLSL/GLSL variants; resolution overrides and resource removal verified; disclosed lexer portability change |",
f"| Microsoft HLSL bytecode compilation | {r['d3dcompile']['variants']} entry-point compilations using d3dcompiler_47.dll; a CPU stage |",
f"| GPU driver compilation and execution | {g['adapter']}; D3D11 hardware FL11_0, generated production bytecode, raw offscreen targets, readback |",
'| In-game ReShade / Signal Inspector | NOT RUN; no game or Signal Inspector source was supplied |',
'| DWM / HDR composition / display-link / panel | NOT RUN; offscreen tests do not verify physical HDR or monitor appearance |',
'| Temporal statistics | Not applicable; only static spatial noise is implemented |',
'',
'The host reported NVIDIA driver version **32.0.16.2101**. This is one hardware/driver/API configuration. Other APIs and driver versions may differ. No GPU timing or FPS was measured.',
'',
'## Ideal quantization: useful result and deliberate negative result',
'',
'1920×1080 encoded ramp spanning codes 32…48; span=1.0. Error statistics are in target code steps. Both 8-bit and 10-bit results match to displayed precision.',
'',
'| Metric | Without dither | With dither |',
'|---|---:|---:|',
f"| Total error RMS | {f(r['gradients'][0]['without']['rms'])} | {f(r['gradients'][0]['with_dither']['rms'])} |",
f"| RMS of column-mean error | {f(r['gradients'][0]['column_mean_rms_without'])} | {f(r['gradients'][0]['column_mean_rms_with'])} |",
f"| Error-energy fraction below 0.1 cycles/pixel | {f(r['gradients'][0]['error_low_frequency_without'])} | {f(r['gradients'][0]['error_low_frequency_with'])} |",
f"| Mean error | {f(r['gradients'][0]['without']['mean'])} | {f(r['gradients'][0]['with_dither']['mean'])} |",
'',
'Dither increases total RMS error while reducing its spatially structured low-frequency component. Column-mean error is one banding proxy, not a universal visibility metric.',
'',
f"Already-quantized ramps passed through the **same ideal quantizer changed {r['gradients'][0]['same_grid_changed_pixels']} pixels**, for both code grids. Exhaustive tests also cover every code, every mask byte and spans 0.25/0.5/1.0. Doubling the span in a CPU-only test changed {100*r['gradients'][0]['double_strength_changed_fraction']:.3f}% of codes and increased RMS error to {f(r['gradients'][0]['double_strength_error_to_original']['rms'])}. Production rejects this strength. No lost detail was recovered.",
'',
'## Actual GPU writes: important negative finding',
'',
'At 1920×1080, full-range same-grid ramps gave:',
'',
'| Raw input/output | Contract | Changed RGB fraction | Mean code change |',
'|---|---|---:|---:|',
]
for row in g['same_grid'][:3]:
    lines.append(f"| {'RGBA8 UNORM' if row['format']==28 else 'RGB10A2 UNORM'} | {'sRGB' if row['contract']==1 else 'PQ'} | {100*row['changed_rgb_fraction']:.4f}% | {f(row['delta_codes']['mean'])} |")
lines += [
'',
'The changes were down by one code, not reconstruction of fractional input. The initial ideal-equality expectation was rejected by the GPU measurement. D3D11 permits 0.6-code FLOAT→UNORM conversion tolerance. No exact vendor rounding algorithm is inferred, and no compensating bias is applied. **Do not enable this effect on same-grid input on the strength of a visual noise change.**',
'',
'Constant near-black fields expose the difference from the ideal unbiased expectation:',
'',
'| Assumption | Input (codes) | Actual GPU mean error (codes) | Mismatch with ideal CPU codes |',
'|---|---:|---:|---:|',
]
for row in g['constant_quantization']:
    if row['input_code'] in (.05,.25,.5,12.25):
        lines.append(f"| {row['levels']+1} levels / {'sRGB' if row['contract']==1 else 'PQ'} | {row['input_code']} | {f(row['error']['mean'])} | {100*row['cpu_code_mismatch_fraction']:.3f}% |")
lines += [
'',
'The hardware sanity assertions bound error; they do **not** establish the ideal 1/512-code bias bound on GPU. For example the 0.05-code field produced no upward code coverage in these GPU tests. Near-black dithering effectiveness is limited here.',
'',
'## Controlled higher-precision GPU cases',
'',
'These separate cases establish that the implementation can meaningfully distribute error when fractional information exists. They do not prove that an ordinary ReShade COLOR buffer has that information.',
'',
'| Path | Column-mean RMS without | Column-mean RMS with | Total RMS with |',
'|---|---:|---:|---:|',
]
for row in g['usefulness']:
    lines.append(f"| {row['path']} | {f(row['plain_column_mean_rms'])} | {f(row['dither_column_mean_rms'])} | {f(row['dither_error']['rms'])} |")
lines += [
'',
'All values are target code steps. “Then ideal” explicitly means a CPU downstream quantizer after GPU readback; the final physical conversion is unverified. FP32→UNORM tests are also evidence for dithering integrated inside a preceding high-precision effect, not a claim that standalone ReShade normally changes the target format.',
'',
f"On FP32 input/output, maximum absolute GPU-versus-CPU sample difference across the resolution/contract matrix was **{f(max(x['max_abs_difference'] for x in g['precise_input']))}**. Tested FP32 and FP16 bypass bits, signed/extended values, NaN/infinities, alpha, and exact UNORM pass-through at zero strength/master bypass were preserved. This is not a universal NaN-payload or denormal guarantee.",
'',
'## Asset, tiling and spectrum',
'',
f"128×128 R8, one mip. Exactly 64 samples per byte value. Centered mean {f(r['asset']['stats']['mean'])}; extrema {f(r['asset']['stats']['min'])}…{f(r['asset']['stats']['max'])}; RMS {f(r['asset']['stats']['rms'])}. At span 1 these are target-code units before clipping.",
'',
'| Signal | Fraction of spectral energy below 0.1 cycles/pixel |',
'|---|---:|',
]
for name,value in r['spectrum_energy_below_0_1_cycles_per_pixel'].items():lines.append(f'| {name} | {f(value)} |')
lines += ['', 'DC is removed; frequency radius is Euclidean. The white control is a shuffled identical histogram. Threshold tests examine approximately 10%, 50% and 90% occupancy. The low-frequency hole supports the blue-noise classification; it is not a claim of perfect isotropy or invisible repetition.', '', '| Axis | Internal neighbor-difference RMS | Wrap seam RMS |','|---|---:|---:|']
for axis,s in r['seams'].items():lines.append(f"| {axis} | {f(s['internal_rms'])} | {f(s['seam_rms'])} |")
lines += ['', 'No discontinuity is introduced by a nonperiodic generator. The mask still repeats every 128 pixels. Cropped images do not inherit exact tile mean:', '', '| Resolution | Tiles across × down | Cropped noise mean |', '|---|---:|---:|']
for row in r['resolutions']:
    lines.append(f"| {row['width']}×{row['height']} | {f(row['tiles_across'])} × {f(row['tiles_down'])} | {f(row['noise_stats']['mean'])} |")
lines += [
'',
'All dimensions were used in CPU, FX generation and GPU rendering, not just filenames. A parser fixture independently verifies BUFFER_WIDTH/HEIGHT. Singleton sizes are synthetic indexing stress tests; ordinary ReShade rejects very small swap chains.',
'',
'## Endpoint and color checks',
'',
'Exact black, white and saturated endpoint primaries remain exact. Per-channel endpoint locking allows other channels to change on partially saturated colors. At x=0.1/L, explicit clipping shifts the prequantizer tile mean upward by 0.07999878 code; ideal finite-mask quantized mean error is +0.0015625 code. No claim of unbiased clipped prequantizer noise is made. Full CPU tables include near-white counterparts and finite probability limitations.',
'',
'Correlated and spatially shifted channel noise were compared on neutral, colored, saturated, near-black and near-white patches in sRGB and PQ. Correlated noise retained exact neutrality under the tested ideal common grid; shifted channels gave 0.70425-code opponent RMS on neutral 0.5 sRGB. A colored [0.123,0.457,0.789] patch still had chromatic changes in correlated mode. Linear luminance changed too. Per-channel means, RMS, opponent differences and linear luminance shifts are included in results.json; hue/saturation preservation is not asserted.',
'',
'Incorrect linear-domain examples are intentionally extreme for PQ: the fixture adds a uniform 1/1023 step to linear values normalized to 10,000 nits, then encodes. This is not a proposed scRGB algorithm. At encoded PQ 0.5 its perturbation RMS is about 3.125 target codes, versus 0.288673 for encoded-domain dither. At encoded sRGB 0.05 with an 8-bit target it is about 3.249 codes. The distribution varies with brightness; a fixed linear step is not a fixed encoded step.',
'',
'## Resource and feature checks',
'',
'Production has one pass, two samplers, COLOR plus a 128×128 R8 asset, and no other render target. Compile-time disable removes the noise texture, its sampler, helpers and uniforms. A disabled isolated build succeeds without the include/asset; an active missing-include build correctly fails. All contract/target pairs, invalid enum values and strength bounds were exercised by CPU tests. Runtime missing-PNG behavior was source-inspected, not launched in ReShade; install the asset and resolve load errors.',
'',
'![Numerical spectrum and quantization analysis](results/analysis.png)',
'',
'## Conclusion',
'',
'This standalone shader can reduce structured quantization error for a verified encoded signal that retains finer information than a known later quantizer. Controlled tests include encoded FP16 and 10-bit sRGB preceding coarser quantization. It offers no recovery of an already-quantized same-grid gradient and can add biased code perturbations on real UNORM writes. Unknown downstream conversion and physical display behavior remain unverified; scRGB is deliberately bypassed. When the preceding effect first discards the useful fractional signal, integrate dithering into that effect before its lossy write. Default bypass is intentional.',
'',
]
(RUN/'VALIDATION.md').write_text('\n'.join(lines),encoding='utf-8')
print(f"Report: {r['checks_passed']} CPU/compiler + {g['checks_passed']} GPU checks; {g['draws']} draws")
