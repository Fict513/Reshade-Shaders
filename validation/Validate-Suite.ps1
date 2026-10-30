<#
.SYNOPSIS
  Validates IPS_Depth_v2.fx, Selective_Deband.fx, Adaptive_Clarity.fx and the preset bundles.

.DESCRIPTION
  1. Preset checks: keys/sections, quality tiers, technique order and that every suite
     preset equals the matching individual presets except IPS Depth Dither=0 / Sharpen=0.
  2. CPU reference tests (tests\<shader>\test_reference.py; needs Python with NumPy and SciPy).
  3. FX harness (tests\<shader>\check_fx.cpp) built with Zig's clang against the pinned
     ReShade effect-compiler sources: parse, module and HLSL/GLSL entry-point generation.

  NOT covered: GPU-driver compilation, in-game rendering, performance, visual quality.

.PARAMETER WorkDir  Scratch directory (default validation\.work, git-ignored).
.PARAMETER Zig      Path to zig.exe (otherwise PATH, otherwise Zig 0.17.0 is downloaded).
.PARAMETER Python   Python executable that has NumPy and SciPy (default: python).
.PARAMETER ReShadeSource  Existing checkout of crosire/reshade at the pinned commit (optional).
#>
[CmdletBinding()]
param(
    [string]$WorkDir,
    [string]$Zig,
    [string]$Python = 'python',
    [string]$ReShadeSource
)
$ErrorActionPreference = 'Stop'
$ReShadeCommit = '7bf9de8b33bcc76c3177007e65d73c72dd0f34c0'
$ZigUrl = 'https://ziglang.org/download/0.17.0/zig-x86_64-windows-0.17.0.zip'
$ZigSha256 = 'b5663f69581dcf391293fbf16c06cb80d81d806545ce618b4d0bab7f0eb8c428'
$here = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
if (-not $WorkDir) { $WorkDir = Join-Path $here '.work' }
$repo = Split-Path $here -Parent
$shaders = [ordered]@{ IPS_Depth_v2 = 'IPSD2_QUALITY'; Selective_Deband = 'SDB_QUALITY'; Adaptive_Clarity = 'AC_QUALITY' }
$script:failed = 0
function Step($m) { Write-Host "`n== $m" -ForegroundColor Cyan }
function Fail($m) { $script:failed++; Write-Host "FAIL $m" -ForegroundColor Red }
function Native { param([string]$Exe) $old = $ErrorActionPreference; $ErrorActionPreference = 'Continue'; & $Exe @args 2>&1 | ForEach-Object { "$_" }; $script:rc = $LASTEXITCODE; $ErrorActionPreference = $old }

function Read-Preset([string]$path) {
    $root = [ordered]@{}; $sections = [ordered]@{}; $cur = $root
    foreach ($line in Get-Content $path) {
        if ($line -match '^\s*$') { continue }
        if ($line -match '^\[(.+)\]$') { $sections[$Matches[1]] = [ordered]@{}; $cur = $sections[$Matches[1]]; continue }
        $k, $v = $line -split '=', 2
        $cur[$k] = $v
    }
    [pscustomobject]@{ Root = $root; Sections = $sections }
}

Step 'Preset bundles'
$tiers = 'Normal', 'High', 'Ultra'
$styles = 'Balanced', 'RTX_Companion'
$order = @('IPS_Depth_v2', 'Selective_Deband', 'Adaptive_Clarity')
foreach ($style in $styles) {
    for ($q = 0; $q -lt 3; $q++) {
        $name = "${style}_$($tiers[$q]).ini"
        $suite = Read-Preset (Join-Path $repo "Presets\Suite\Suite_$name")
        $expectTech = ($order | ForEach-Object { "$_@$_.fx" }) -join ','
        if ($suite.Root['Techniques'] -ne $expectTech -or $suite.Root['TechniqueSorting'] -ne $expectTech) { Fail "Suite_$name technique order" }
        if (($suite.Sections.Keys -join ',') -ne (($order | ForEach-Object { "$_.fx" }) -join ',')) { Fail "Suite_$name section order" }
        $defs = @{}
        foreach ($kv in $suite.Root['PreprocessorDefinitions'] -split ',') { $a, $b = $kv -split '=', 2; $defs[$a] = $b }
        $wantDefs = @{}
        foreach ($s in $order) {
            $ind = Read-Preset (Join-Path $repo "Presets\$s\$name")
            if ($ind.Root['Techniques'] -ne "$s@$s.fx") { Fail "$s/$name technique" }
            foreach ($kv in $ind.Root['PreprocessorDefinitions'] -split ',') { $a, $b = $kv -split '=', 2; $wantDefs[$a] = $b }
            $want = [ordered]@{} + $ind.Sections["$s.fx"]
            if ($s -eq 'IPS_Depth_v2') { $want['Sharpen'] = '0.0'; $want['Dither'] = '0.0' }
            $have = $suite.Sections["$s.fx"]
            if (($want.Keys -join ',') -ne ($have.Keys -join ',')) { Fail "Suite_$name [$s.fx] key set/order" }
            foreach ($k in $want.Keys) { if ($have[$k] -ne $want[$k]) { Fail "Suite_$name [$s.fx] $k = $($have[$k]), expected $($want[$k])" } }
        }
        foreach ($k in $wantDefs.Keys + $defs.Keys) { if ($defs[$k] -ne $wantDefs[$k]) { Fail "Suite_$name definition $k" } }
        foreach ($qk in $shaders.Values) { if ($defs[$qk] -ne "$q") { Fail "Suite_$name $qk != $q" } }
        if ($suite.Sections['IPS_Depth_v2.fx']['Sharpen'] -ne '0.0' -or $suite.Sections['IPS_Depth_v2.fx']['Dither'] -ne '0.0') { Fail "Suite_$name IPS Sharpen/Dither not 0" }
        Write-Host "OK   Suite_$name"
    }
}
foreach ($s in $order) { foreach ($style in $styles) { for ($q = 0; $q -lt 3; $q++) {
    $ind = Read-Preset (Join-Path $repo "Presets\$s\${style}_$($tiers[$q]).ini")
    $m = [regex]::Match($ind.Root['PreprocessorDefinitions'], "$($shaders[$s])=(\d)")
    if (-not $m.Success -or $m.Groups[1].Value -ne "$q") { Fail "$s ${style}_$($tiers[$q]) quality" }
} } }
Write-Host 'OK   individual preset quality definitions'

Step 'CPU reference tests'
foreach ($s in $shaders.Keys) {
    Write-Host "-- $s"
    Native $Python (Join-Path $repo "tests\$s\test_reference.py") | Select-Object -Last 4 | Write-Host
    if ($script:rc -ne 0) { Fail "CPU tests $s" }
}

Step 'Toolchain'
New-Item -ItemType Directory -Force $WorkDir | Out-Null
$WorkDir = (Resolve-Path $WorkDir).Path
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
$rs = if ($ReShadeSource) { $ReShadeSource } else { Join-Path $WorkDir 'reshade' }
if (-not (Test-Path (Join-Path $rs '.git'))) {
    git init --quiet $rs
    git -C $rs remote add origin https://github.com/crosire/reshade.git
}
if ((git -C $rs rev-parse HEAD 2>$null) -ne $ReShadeCommit) {
    git -C $rs fetch --quiet --depth 1 origin $ReShadeCommit
    if ($LASTEXITCODE -ne 0) { throw 'Failed to fetch pinned ReShade source' }
    git -C $rs checkout --quiet FETCH_HEAD
}
if ((git -C $rs rev-parse HEAD) -ne $ReShadeCommit) { throw 'ReShade source commit mismatch' }
Write-Host "ReShade source: $ReShadeCommit"

Step 'ReShade FX harness (parse / module / HLSL + GLSL generation)'
$bin = Join-Path $WorkDir 'bin'
New-Item -ItemType Directory -Force $bin | Out-Null
$srcs = 'effect_preprocessor', 'effect_lexer', 'effect_expression', 'effect_symbol_table', 'effect_parser_exp', 'effect_parser_stmt', 'effect_codegen_hlsl', 'effect_codegen_glsl' | ForEach-Object { Join-Path $rs "source\$_.cpp" }
foreach ($s in $shaders.Keys) {
    Write-Host "-- $s"
    $exe = Join-Path $bin "check_$s.exe"
    if (Test-Path $exe) { Remove-Item -LiteralPath $exe -Force }
    Native $Zig c++ -std=c++17 -w -O1 -DSH_DENYWR=0x20 "-I$(Join-Path $rs 'source')" "-I$(Join-Path $rs 'include')" "-I$(Join-Path $rs 'deps\spirv')" (Join-Path $repo "tests\$s\check_fx.cpp") @srcs -o $exe | Select-Object -Last 5 | Write-Host
    if ($script:rc -ne 0 -or -not (Test-Path $exe)) { Fail "build check_fx $s"; continue }
    Native $exe (Join-Path $repo "Shaders\$s.fx") | Write-Host
    if ($script:rc -ne 0) { Fail "FX harness $s" }
}

Step 'Result'
if ($script:failed) { Write-Host "$($script:failed) check(s) FAILED" -ForegroundColor Red; exit 1 }
Write-Host 'ALL CHECKS PASSED' -ForegroundColor Green
