# Verification

The CPU model uses NumPy/SciPy to simulate encoded-RGB math and bilinear CLAMP
sampling. It does not execute the FX file. GPU rounding/interpolation and the
static dither hash can differ. Tests using final 8-bit rounding and spatial
averaging are a synthetic model, not a GPU display benchmark.

```bash
python -m pip install numpy scipy
python Tests/test_reference.py
```

The C++ harness checks parsing, module and entry-point HLSL/GLSL generation,
pass counts and absence of intermediate targets. It does not invoke a Windows
D3D compiler or GPU driver. It was built with crosire/reshade source commit
`7bf9de8b33bcc76c3177007e65d73c72dd0f34c0`, not a claim of the latest release.

From that ReShade source checkout on Linux, replacing `/path/to/pack`:

```bash
g++ -std=c++17 -O1 -include strings.h -D_stricmp=strcasecmp -Isource \
  /path/to/pack/Tests/check_fx.cpp \
  source/effect_preprocessor.cpp source/effect_lexer.cpp \
  source/effect_expression.cpp source/effect_symbol_table.cpp \
  source/effect_parser_exp.cpp source/effect_parser_stmt.cpp \
  source/effect_codegen_hlsl.cpp source/effect_codegen_glsl.cpp \
  -o /path/to/pack/check_fx
/path/to/pack/check_fx /path/to/pack/Shaders/Selective_Deband.fx
```

Other platforms/source versions can require build adjustments. No compiler
binary or third-party source checkout is bundled.
