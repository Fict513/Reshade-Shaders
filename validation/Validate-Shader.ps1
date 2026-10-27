<#
.SYNOPSIS
  Reproducible validation of Shaders\FakeHDR_Advanced.fx (Windows PowerShell 5.1+).

.DESCRIPTION
  1. Builds ReShade's own FX preprocessor/parser + HLSL/GLSL code generators (pinned
     ReShade commit) with Zig's bundled clang. Pure shader-code generation; no GPU.
  2. Parses the shader for FHDRA_QUALITY 0/1/2 and BUFFER_COLOR_SPACE 0..4, emitting HLSL
     (and GLSL for one variant).
  3. Compiles every generated HLSL entry point to DXBC with the Windows D3DCompiler.
  4. Executes the shader's color math and all seven passes on the D3D11 WARP *software*
     device with synthetic images.

  NOT covered: GPU-driver compilation, ReShade's DX9/OpenGL/Vulkan back ends, real
  game content, visual quality and performance.

.PARAMETER WorkDir  Scratch directory for downloads/builds (default: validation\.work).
.PARAMETER Zig      Path to an existing zig.exe (otherwise Zig 0.17.0 is downloaded).
#>
[CmdletBinding()]
param(
    [string]$WorkDir = (Join-Path $PSScriptRoot '.work'),
    [string]$Zig
)
$ErrorActionPreference = 'Stop'
$ReShadeCommit = '7bf9de8b33bcc76c3177007e65d73c72dd0f34c0'
$ZigUrl = 'https://ziglang.org/download/0.17.0/zig-x86_64-windows-0.17.0.zip'
$ZigSha256 = 'b5663f69581dcf391293fbf16c06cb80d81d806545ce618b4d0bab7f0eb8c428'
$repo = Split-Path $PSScriptRoot -Parent
$shader = Join-Path $repo 'Shaders\FakeHDR_Advanced.fx'
New-Item -ItemType Directory -Force $WorkDir | Out-Null
$WorkDir = (Resolve-Path $WorkDir).Path
$script:failed = 0
function Step($m) { Write-Host "`n== $m" -ForegroundColor Cyan }
function Native { param([string]$Exe) $old = $ErrorActionPreference; $ErrorActionPreference = 'Continue'; & $Exe @args 2>&1 | ForEach-Object { "$_" }; $script:rc = $LASTEXITCODE; $ErrorActionPreference = $old }

Step 'Toolchain'
if (-not $Zig) {
    $cmd = Get-Command zig -ErrorAction SilentlyContinue
    if ($cmd) { $Zig = $cmd.Source }
    else {
        $zipPath = Join-Path $WorkDir 'zig.zip'
        if (-not (Test-Path (Join-Path $WorkDir 'zig'))) {
            Invoke-WebRequest $ZigUrl -OutFile $zipPath
            if ((Get-FileHash $zipPath -Algorithm SHA256).Hash -ne $ZigSha256) { throw 'Zig archive SHA-256 mismatch' }
            Expand-Archive $zipPath (Join-Path $WorkDir 'zig') -Force
        }
        $Zig = (Get-ChildItem (Join-Path $WorkDir 'zig') -Recurse -Filter zig.exe | Select-Object -First 1).FullName
    }
}
Write-Host "zig: $Zig"

$rs = Join-Path $WorkDir 'reshade'
if (-not (Test-Path (Join-Path $rs '.git'))) {
    git init --quiet $rs
    if ($LASTEXITCODE -ne 0) { throw 'Failed to initialize ReShade source checkout' }
    git -C $rs remote add origin https://github.com/crosire/reshade.git
    if ($LASTEXITCODE -ne 0) { throw 'Failed to add ReShade remote' }
}
git -C $rs fetch --quiet --depth 1 origin $ReShadeCommit
if ($LASTEXITCODE -ne 0) { throw 'Failed to fetch pinned ReShade source' }
git -C $rs checkout --quiet FETCH_HEAD
if ($LASTEXITCODE -ne 0) { throw 'Failed to check out pinned ReShade source' }
$actualCommit = git -C $rs rev-parse HEAD
if ($LASTEXITCODE -ne 0 -or $actualCommit -ne $ReShadeCommit) { throw 'ReShade source commit mismatch' }
Write-Host "ReShade source: $actualCommit"

Step 'Build ReShade FX parser (rsfxc) and validator'
$bin = Join-Path $WorkDir 'bin'
New-Item -ItemType Directory -Force $bin | Out-Null
$fxcSrc = (Get-Content (Join-Path $rs 'tools\fxc.cpp') -Raw) `
    -replace 'backend\.reset\(reshadefx::create_codegen_dxbc[^\n]*\n', 'backend.reset(nullptr);' `
    -replace 'backend\.reset\(reshadefx::create_codegen_spirv[^\n]*\n', 'backend.reset(nullptr);' `
    -replace '#include "version.h"', ''
Set-Content (Join-Path $bin 'fxc_min.cpp') $fxcSrc
$srcs = 'effect_expression', 'effect_lexer', 'effect_parser_exp', 'effect_parser_stmt', 'effect_preprocessor', 'effect_symbol_table', 'effect_codegen_hlsl', 'effect_codegen_glsl' | ForEach-Object { Join-Path $rs "source\$_.cpp" }
$rsfxc = Join-Path $bin 'rsfxc.exe'
if (Test-Path $rsfxc) { Remove-Item -LiteralPath $rsfxc -Force }
Native $Zig c++ -std=c++17 -w -O1 -DSH_DENYWR=0x20 '-DVERSION_STRING_PRODUCT=\"local\"' -DVERSION_MAJOR=6 -DVERSION_MINOR=0 -DVERSION_REVISION=0 `
    "-I$(Join-Path $rs 'source')" "-I$(Join-Path $rs 'include')" "-I$(Join-Path $rs 'deps\spirv')" @srcs (Join-Path $bin 'fxc_min.cpp') -o $rsfxc | Write-Host
if ($script:rc -ne 0 -or -not (Test-Path $rsfxc)) { throw 'failed to build rsfxc' }
$val = Join-Path $bin 'fhdra_validate.exe'
if (Test-Path $val) { Remove-Item -LiteralPath $val -Force }
Native $Zig c++ -std=c++17 -O1 (Join-Path $PSScriptRoot 'fhdra_validate.cpp') -ld3d11 -ld3dcompiler_47 -ldxguid -o $val | Write-Host
if ($script:rc -ne 0 -or -not (Test-Path $val)) { throw 'failed to build fhdra_validate' }

Step 'ReShade FX parse + HLSL/GLSL generation (shader-code generation only)'
$gen = Join-Path $WorkDir 'gen'
New-Item -ItemType Directory -Force $gen | Out-Null
foreach ($q in 0, 1, 2) {
    foreach ($cs in 0, 1, 2, 3, 4) {
        $o = Join-Path $gen "q$q-cs$cs.hlsl"
        Native $rsfxc $shader --hlsl --width 1920 --height 1080 -D "FHDRA_QUALITY=$q" -D "BUFFER_COLOR_SPACE=$cs" -Fo $o | Write-Host
        $ok = ($script:rc -eq 0)
        $passes = if ($ok) { ([regex]::Matches((Get-Content $o -Raw), 'F__FHDRA__(FineHorizontal|FineVertical|MidHorizontal|MidVertical|BroadHorizontal|BroadVertical|Composite)\(')).Count } else { 0 }
        $expected = if ($cs -ge 2) { 1 } else { 7 }
        $good = $ok -and ($passes -eq $expected)
        if (-not $good) { $script:failed++ }
        '{0,-4} q{1} BUFFER_COLOR_SPACE={2}: parse {3}, pixel entry points={4} (expected {5})' -f $(if ($good) { 'OK' } else { 'FAIL' }), $q, $cs, $(if ($ok) { 'ok' } else { 'FAILED' }), $passes, $expected
    }
}
Native $rsfxc $shader --glsl --width 1920 --height 1080 -D BUFFER_COLOR_SPACE=1 -Fo (Join-Path $gen 'q1.glsl') | Write-Host
if ($script:rc -ne 0) { $script:failed++; 'FAIL GLSL generation' } else { 'OK   GLSL generation (q1, sRGB)' }

Step 'Compile generated HLSL to DXBC (D3DCompiler; no GPU driver)'
$entries = 'FineHorizontal', 'FineVertical', 'MidHorizontal', 'MidVertical', 'BroadHorizontal', 'BroadVertical'
foreach ($q in 0, 1, 2) {
    $f = Join-Path $gen "q$q-cs1.hlsl"
    Native $val compile $f F__FHDRA__VS vs_5_0 | Write-Host
    if ($script:rc -ne 0) { $script:failed++ }
    foreach ($e in $entries + 'Composite') {
        Native $val compile $f "F__FHDRA__$e" ps_5_0 | Write-Host
        if ($script:rc -ne 0) { $script:failed++ }
    }
}
foreach ($cs in 3) {
    $f = Join-Path $gen "q1-cs$cs.hlsl"
    Native $val compile $f F__FHDRA__Composite ps_5_0 | Write-Host
    if ($script:rc -ne 0) { $script:failed++ }
}

Step 'Execute shader color math on WARP (software D3D11)'
Native $val math $shader | Write-Host
if ($script:rc -ne 0) { $script:failed++ }

Step 'Execute full pass chain on WARP, synthetic 640x360 image'
$sizeGen = Join-Path $WorkDir 'gen640'
New-Item -ItemType Directory -Force $sizeGen | Out-Null
$variants = @(@{ n = 'q0'; q = 0; cs = 1 }, @{ n = 'q1'; q = 1; cs = 1 }, @{ n = 'q2'; q = 2; cs = 1 }, @{ n = 'hdr-pq'; q = 1; cs = 3 }, @{ n = 'hdr-scrgb'; q = 1; cs = 2 }, @{ n = 'hdr-hlg'; q = 1; cs = 4 })
foreach ($v in $variants) {
    $f = Join-Path $sizeGen "$($v.n).hlsl"
    Native $rsfxc $shader --hlsl --width 640 --height 360 -D "FHDRA_QUALITY=$($v.q)" -D "BUFFER_COLOR_SPACE=$($v.cs)" -Fo $f | Write-Host
    if ($script:rc -ne 0) { $script:failed++; Write-Host "FAIL generating $($v.n)"; continue }
    Write-Host "-- $($v.n)"
    Native $val pipeline $f $shader | Write-Host
    if ($script:rc -ne 0) { $script:failed++ }
}

Step 'Result'
if ($script:failed -eq 0) { Write-Host 'ALL CHECKS PASSED' -ForegroundColor Green; exit 0 }
Write-Host "$($script:failed) CHECK GROUP(S) FAILED" -ForegroundColor Red; exit 1
