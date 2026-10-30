# Validating FakeHDR_Advanced.fx

Windows only. Requires PowerShell 5.1+, `git`, internet access (to fetch a pinned ReShade source commit and, if `zig` is not on `PATH`, Zig 0.17.0), and the Windows D3DCompiler/D3D11 runtime (present on supported Windows versions).

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File validation\Validate-Shader.ps1
```

Optional: `-WorkDir <dir>` (default `validation\.work`, git-ignored) and `-Zig <path\to\zig.exe>`. The script exits 0 only if every check passes.

## What it does

| Stage | Tool | Proves | Does **not** prove |
|---|---|---|---|
| 1. Parse + generate | ReShade's own `reshadefx` preprocessor, parser and HLSL/GLSL code generators (ReShade commit `7bf9de8b33bcc76c3177007e65d73c72dd0f34c0`, built with Zig/clang). HLSL: `FHDRA_QUALITY` 0/1/2 × `BUFFER_COLOR_SPACE` 0–4. GLSL: quality 1, sRGB. | The `.fx` parses for those variants; sRGB/unknown spaces yield 7 pixel entry points, HDR spaces (2, 3, 4) yield exactly 1 | Anything about GPUs |
| 2. DXBC compile | `D3DCompile` (`vs_5_0`/`ps_5_0`) on every generated entry point | The generated HLSL compiles under Microsoft's compiler | Driver-level compilation or GPU limits |
| 3. Math on WARP | `FakeHDR_Advanced.fx` color functions (`Tone`, `BoundedExposure`, `Gate`, `SoftLimit`, `ColorReconstruct`) extracted verbatim and run as a compute shader on D3D11 WARP over ~13.5k edge cases × 4 slider presets | Finite outputs; all outputs in [0,1]; `Tone(0)=0`, `Tone(1)=1`, monotonic; `BoundedExposure(0)=0`; luminance equals the (headroom-capped) target; neutral stays neutral | Appearance |
| 4. Pass chain on WARP | The generated HLSL of all seven passes, executed on WARP over a 640×360 synthetic scene (ramp, black, white, primaries, hard edge, noise, flat gray) | No NaN/Inf; pure black and white unchanged; near-black not lifted beyond 2/255; saturated yellow preserved; Strength=0 and split-view left half return the input; views 1/2 finite; deterministic dither; alpha preserved; all-zero amounts ≈ identity; HDR variants pass the SDR sample and a few extended-range values through unchanged; qualities 0/1/2 all run | Real-game behavior, performance, visual quality, other back ends |

WARP is a CPU rasterizer; it demonstrates the shader's logic executes as intended, not that any GPU/driver will compile or run it identically.

## Manual in-game checks (not automated)

1. Enable the technique at each `FHDRA_QUALITY` (0, 1, 2) and confirm it compiles without errors in the ReShade log.
2. Toggle *Split-screen comparison*, *Local exposure map* and *Gamut compression map*.
3. Run an HDR-enabled game or the HDR swap chain and confirm there is no change to the image.
4. Check HUD, menus, a pure-black area and a bright sky for halos or crushed blacks.

## Suite validation (v1.1.0)

`validation\Validate-Suite.ps1` checks the preset bundles (ordering, quality definitions, equality with the individual presets apart from IPS Sharpen/Dither = 0), runs the CPU reference tests in `tests\<shader>\` (Python with NumPy and SciPy) and builds/runs each `tests\<shader>\check_fx.cpp` against the pinned ReShade source. It is shader-code generation and CPU modelling only: no GPU, driver, in-game or performance testing, and the merged presets are not rendered.

