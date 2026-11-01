# Reproduce the checks

The tests require Python 3, NumPy, and a C++17 g++ toolchain. The optional plot requires Matplotlib. They do not require a game, an HDR monitor, or a GPU. Their results do not replace tests on those devices.

From the package directory:

```bash
python3 tools/run_audit.py
```

This compiles `Shaders/HDRIPS_Math.fxh` into a small C++ float library, using single-precision constants and no fast-math. The source include is unchanged. NumPy reference ports cover vector operations, output quantization and the bilateral filter; their arithmetic is predominantly float64 around explicitly quantized guide storage. The additional production_float.py and production_local.py adapters execute extracted production Main/color/diagnostic and local function bodies as C++ float. They emulate sampling and vector operations and do not execute GPU instructions; Main uses local off and the local filter is tested separately. FX semantics and loop attributes are removed for C++ syntax. Float32 rounding and control flow are tested more directly, but GPU contraction, intrinsics and resource behavior still require in-game verification.

To reproduce ReShade parsing/code generation, obtain the official source. The exact revision used for the accompanying report is pinned below:

```bash
git clone https://github.com/crosire/reshade.git reshade-upstream
git -C reshade-upstream checkout 7bf9de8b33bcc76c3177007e65d73c72dd0f34c0
g++ -std=c++17 -O2 -I reshade-upstream/source \
  tools/fxcheck.cpp \
  reshade-upstream/source/effect_lexer.cpp \
  reshade-upstream/source/effect_preprocessor.cpp \
  reshade-upstream/source/effect_expression.cpp \
  reshade-upstream/source/effect_symbol_table.cpp \
  reshade-upstream/source/effect_parser_exp.cpp \
  reshade-upstream/source/effect_parser_stmt.cpp \
  reshade-upstream/source/effect_codegen_hlsl.cpp \
  reshade-upstream/source/effect_codegen_glsl.cpp \
  -o fxcheck
python3 tools/validate_fx_audit.py ./fxcheck
```

The custom CLI calls the upstream preprocessor, parser, HLSL SM5 and GLSL generators without modifying their source. It inspects module metadata to verify pass/texture removal. It does not invoke DXBC, DXIL, the NVIDIA driver or a GLSL driver. The `__RESHADE__` value in the harness is an unused compatibility stub, not an installed ReShade version claim. Only `BUFFER_COLOR_SPACE` and dimensions/feature macros influence this effect's generated variants.

The matrix covers 120 backend × quality × local × color × presentation combinations, plus seven resolution cases. D3D11/D3D12 execution, actual resource formats, UI operation, diagnostic appearance and HDR screenshots must still be checked in ReShade on the target computer. Shader compilation failures there should be captured from ReShade's error log.

```bash
python3 tools/plot_validation.py
```

That optional command creates a numerical global-curve illustration, with no claim about panel response or in-game appearance.

The audited harness installs supplied dimensions before defaults and asserts module texture sizes. Raw reports use the audit_ prefix; the superseded original resolution logs are not included.
