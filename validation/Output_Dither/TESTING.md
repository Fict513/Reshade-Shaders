# Reproduce the validation

Use Python 3.12, Git and PowerShell on Windows for the complete suite. The CPU
numerical suite and generator also run without Windows; the C++/DXBC/D3D11 stages
require the described Windows setup. Test dependencies are not shader dependencies.
Run the following from the repository root. Use `python` pointing to a real Python
installation, not the Store alias. All generated files are written under the ignored
`validation/.work/Output_Dither/` directory.

```powershell
python -m venv validation/.work/Output_Dither/venv
.\validation\.work\Output_Dither\venv\Scripts\Activate.ps1
python -m pip install -r validation/Output_Dither/requirements.txt
python -m pip install --target validation/.work/Output_Dither/tools ziglang==0.14.1
git clone https://github.com/crosire/reshade.git validation/.work/Output_Dither/reshade
git -C validation/.work/Output_Dither/reshade checkout 7bf9de8b33bcc76c3177007e65d73c72dd0f34c0
./validation/Output_Dither/build_tools.ps1
python validation/Output_Dither/validate.py --cpu-dll validation/.work/Output_Dither/tools/core_cpu.dll --fx-compiler validation/.work/Output_Dither/tools/fx_probe.exe
python validation/Output_Dither/validate_gpu.py --dll validation/.work/Output_Dither/tools/gpu_d3d11.dll
python validation/Output_Dither/make_report.py
```

To verify the asset independently, run `python validation/Output_Dither/generate_noise.py`.
It overwrites the production PNG and provenance file. Compare the decoded pixel hash
with the shipped `43a71c12dc12bb53ea67c7fb4958fa4b53da4156fbdc68a5d0e258a7011c01bf`.
An alternate NumPy implementation/version could differ in floating-point tie resolution;
the shipped asset and its measured statistics remain the production reference.

`python validation/Output_Dither/validate.py` without options runs the NumPy reference
and analytics only, explicitly marking the adapted C++ and parser stages NOT RUN.
Results are written under `validation/.work/Output_Dither/`, leaving the supplied
historical reports intact. GPU validation never silently substitutes Microsoft's WARP
software device.

To build the standalone source package from the repository checkout, run
`python validation/Output_Dither/package.py`. It writes the ZIP and SHA-256 file
under the ignored `validation/.work/Output_Dither/` directory.

## What the tools execute

- `generate_noise.py`: an independent void-and-cluster implementation, no third-party
  texture download. NumPy FFT initializes circular energy; incremental updates assign
  the full rank permutation. Pillow writes grayscale bytes.
- `validate.py`: analytical and NumPy float64/float32 reference tests; finite histogram,
  spectra, threshold patterns, wrapping, resolutions, ideal quantizers, transfer-function
  counterexamples, near endpoints, RGB correlations, chromatic changes and invalid values.
- `core_cpu.cpp`: includes the exact production scalar `.fxh`; a manually adapted C++
  wrapper substitutes array reads for texture operations and ports the PS guards.
  This does not execute the generated HLSL on the CPU. Compiled with float contraction off.
- `fx_probe.cpp`: actual upstream ReShade preprocessor, parser and HLSL SM5/GLSL generators.
  Zig's libc++ 0.14.1 lacks floating `from_chars`; `build_tools.ps1` makes a **build copy**
  of `effect_lexer.cpp` replacing that one conversion with bounded `std::strtof`.
  The unmodified upstream checkout is retained. `SH_DENYWR=0x20` supplies a MinGW
  header portability constant. This is an adapted front end build, not a release ReShade binary.
  No shader syntax is stripped to make it parse. No codegen backend is replaced.
- Resolution checks declare a separate `ResolutionProbe` texture in the **validation fixture**
  and inspect parser dimensions; each enabled HLSL also embeds the supplied width/height.
  Overrides are supplied before preprocessing, not shadowed by a default. The fixture's
  extra texture is unused and absent from the production shader.
- Microsoft `d3dcompiler_47.dll`: CPU HLSL→DXBC compilation of both production entry points.
  This is a separate stage from ReShade FX parsing and from GPU driver compilation.
- `gpu_d3d11.cpp` + `validate_gpu.py`: create a hardware D3D11 device, instantiate shaders
  from the generated production DXBC, bind raw views and matching point samplers, draw an
  offscreen full-screen triangle, copy the result to staging and read it back. No production
  shader arithmetic is substituted. Inputs are RGBA32F, RGBA16F, RGBA8 UNORM and RGB10A2
  UNORM; outputs use the corresponding test format. The 10→8 and FP16→integer examples
  explicitly identify the later **ideal CPU** quantizer; other UNORM tests use actual GPU writes.

The shader's main pass is tested with supported contract pairs, bypasses and resource
removal. `OUTPUT_DITHER_ENABLE=0` is also compiled with the include/asset omitted.
The active missing-include build must fail. The FX parser does not load image files;
a missing-PNG ReShade runtime launch was not performed. Runtime source inspection and
asset integrity checks cover that dependency, not a claim of graceful GPU auto-bypass.

All four requested resolutions, 1919×1079, 1×137, 137×1 and 1×1 are tested numerically,
through parsing and offscreen GPU execution. Singleton sizes stress indexing; the ordinary
ReShade runtime rejects very small swap chains, so they are not an in-game compatibility claim.

No game, swap chain, DWM composition, physical display link, monitor capture, Signal Inspector
installation, Vulkan/OpenGL/D3D12 GPU execution or performance measurement is performed.
No animated mode exists; temporal statistics are not applicable.

## Evidence

- `validation/.work/Output_Dither/results/results.json`: check names, spectrum metrics, CPU error/color/endpoint tables,
  backend logs, code hashes and Microsoft bytecode compile results.
- `validation/.work/Output_Dither/results/gpu_results.json`: hardware identity, draw/check counts, actual UNORM biases,
  same-grid code changes and precise-input comparisons.
- `validation/.work/Output_Dither/results/analysis.png`: numerical visualization, with magnified error explicitly labeled.
- `validation/.work/Output_Dither/generated/`: created on rerun; HLSL/GLSL/DXBC and isolated resource test inputs. These
  derived files and build tools are excluded from the small release ZIP; sources and logs suffice
  to recreate them. External ReShade, Zig and Python packages retain their own licenses.

Initial GPU same-grid equality was a **rejected hypothesis**. The final checks bound changes
to adjacent codes and record the actual negative bias; they do not relabel equality as proven.
Likewise hardware constant-field mean error is measured with a broad 0.1-code sanity bound,
not the ideal 1/512-code expectation. Read the actual values in VALIDATION.md and the JSON.
