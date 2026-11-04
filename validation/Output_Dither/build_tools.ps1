param(
    [string]$ReShade = 'validation/.work/Output_Dither/reshade',
    [string]$Cxx = 'validation/.work/Output_Dither/tools/ziglang/zig.exe',
    [string]$Output = 'validation/.work/Output_Dither/tools'
)
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
New-Item -ItemType Directory -Force $Output | Out-Null
# Zig 0.14.1 libc++ lacks float from_chars; use a bounded strtof in a build copy.
# The upstream checkout is unchanged. This affects lexical float conversion only.
$lexer = Get-Content -Raw (Join-Path $ReShade 'source/effect_lexer.cpp')
$needle = 'std::from_chars(begin, end, tok.literal_as_float);'
if (-not $lexer.Contains($needle)) { throw 'Unexpected upstream lexer' }
$lexer = "#include <cstdlib>`n" + $lexer.Replace($needle,
    'tok.literal_as_float = std::strtof(std::string(begin, end).c_str(), nullptr);')
$lexerPath = Join-Path $Output 'effect_lexer_portable.cpp'
[IO.File]::WriteAllText([IO.Path]::GetFullPath($lexerPath), $lexer)
$names = @('effect_codegen_hlsl.cpp','effect_codegen_glsl.cpp','effect_expression.cpp',
    'effect_parser_exp.cpp','effect_parser_stmt.cpp','effect_preprocessor.cpp','effect_symbol_table.cpp')
$sources = $names | ForEach-Object { Join-Path $ReShade ('source/' + $_) }
& $Cxx c++ -std=c++17 -O2 -DNDEBUG -DSH_DENYWR=0x20 -I (Join-Path $ReShade 'source') (Join-Path $here 'fx_probe.cpp') $lexerPath @sources -o (Join-Path $Output 'fx_probe.exe')
if ($LASTEXITCODE) { throw 'FX compiler build failed' }
& $Cxx c++ -std=c++17 -O2 -ffp-contract=off -shared (Join-Path $here 'core_cpu.cpp') -o (Join-Path $Output 'core_cpu.dll')
if ($LASTEXITCODE) { throw 'Adapted CPU library build failed' }
& $Cxx c++ -std=c++17 -O2 -shared (Join-Path $here 'gpu_d3d11.cpp') -ld3d11 -ldxgi -ldxguid -o (Join-Path $Output 'gpu_d3d11.dll')
if ($LASTEXITCODE) { throw 'D3D11 harness build failed' }
