# Reproduce verification

`reference.py` models the image math, float32 guide writes, masks and bilinear
CLAMP sampling in NumPy/SciPy. It does not execute the FX file or a GPU driver.
The tests assert observable properties rather than image identity to GPU output.

```bash
python -m pip install numpy scipy
python Tests/test_reference.py
```

For effect compilation checks, use a crosire/reshade source checkout at commit
`7bf9de8b33bcc76c3177007e65d73c72dd0f34c0`. This is the version used here, not a
claim that it is the latest release. From that checkout on Linux, replacing
`/path/to/pack` with the actual extracted pack path:

```bash
g++ -std=c++17 -O1 -include strings.h -D_stricmp=strcasecmp -Isource \
  /path/to/pack/Tests/check_fx.cpp \
  source/effect_preprocessor.cpp source/effect_lexer.cpp \
  source/effect_expression.cpp source/effect_symbol_table.cpp \
  source/effect_parser_exp.cpp source/effect_parser_stmt.cpp \
  source/effect_codegen_hlsl.cpp source/effect_codegen_glsl.cpp \
  -o /path/to/pack/check_fx
/path/to/pack/check_fx /path/to/pack/Shaders/Adaptive_Clarity.fx
```

The harness checks FX parsing, module and per-entry-point HLSL/GLSL generation,
pass counts and intermediate allocations. It does not invoke the Windows D3D
compiler or validate actual runtime execution. Other platforms/compiler-source
versions may need build adjustments. The official compiler is not bundled.
