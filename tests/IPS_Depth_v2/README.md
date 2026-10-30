# Verification

`reference.py` is a CPU model; it is not execution of the compiled shader.
`test_reference.py` asserts image-processing properties over that model.
Install NumPy and SciPy, then run `python Tests/test_reference.py` from the pack
root (or use an absolute path).

`check_fx.cpp` builds against crosire/reshade's effect compiler sources and
checks parsing, module/entry-point generation, pass counts and target layouts.
It generates HLSL SM5 and GLSL with Vulkan semantics. It does not invoke the
Windows D3D compiler, a SPIR-V driver, or a GPU.

On Linux, from a checkout of crosire/reshade at commit
`7bf9de8b33bcc76c3177007e65d73c72dd0f34c0`, build with the actual absolute path
to this pack replacing `/path/to/pack`:

```bash
g++ -std=c++17 -O1 -include strings.h -D_stricmp=strcasecmp -Isource \
  /path/to/pack/Tests/check_fx.cpp \
  source/effect_preprocessor.cpp source/effect_lexer.cpp \
  source/effect_expression.cpp source/effect_symbol_table.cpp \
  source/effect_parser_exp.cpp source/effect_parser_stmt.cpp \
  source/effect_codegen_hlsl.cpp source/effect_codegen_glsl.cpp \
  -o /path/to/pack/check_fx
/path/to/pack/check_fx /path/to/pack/Shaders/IPS_Depth_v2.fx
```

The source commit is the version used for this validation, not a claim that it
is the latest release. Other platforms/versions may require build adjustments.
The pack includes no compiler or third-party source checkout.
