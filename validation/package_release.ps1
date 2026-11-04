param(
    [string]$Version = "v1.3.0",
    [string]$OutputDirectory = ""
)

$ErrorActionPreference = "Stop"
$repository = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $env:TEMP "reshade-release-$Version"
}
$OutputDirectory = [System.IO.Path]::GetFullPath($OutputDirectory)
if (!(Test-Path $OutputDirectory)) {
    New-Item -ItemType Directory -Path $OutputDirectory | Out-Null
}

$collectionName = "Reshade-Shaders-$Version-Collection.zip"
$effects = @(
    @{
        Name = "IPS Depth v2"
        Version = "v2.0"
        Asset = "IPS-Depth-v2.0-$Version.zip"
        Source = @("Shaders/IPS_Depth_v2.fx")
        Presets = "Presets/IPS_Depth_v2"
        Guide = "docs/IPS_Depth_v2.md"
        Tests = @("tests/IPS_Depth_v2")
        Validation = @()
        PresetCount = 6
        License = $true
    },
    @{
        Name = "Selective Deband"
        Version = "1.0"
        Asset = "Selective-Deband-1.0-$Version.zip"
        Source = @("Shaders/Selective_Deband.fx")
        Presets = "Presets/Selective_Deband"
        Guide = "docs/Selective_Deband.md"
        Tests = @("tests/Selective_Deband")
        Validation = @()
        PresetCount = 6
        License = $true
    },
    @{
        Name = "Adaptive Clarity"
        Version = "1.0"
        Asset = "Adaptive-Clarity-1.0-$Version.zip"
        Source = @("Shaders/Adaptive_Clarity.fx")
        Presets = "Presets/Adaptive_Clarity"
        Guide = "docs/Adaptive_Clarity.md"
        Tests = @("tests/Adaptive_Clarity")
        Validation = @()
        PresetCount = 6
        License = $true
    },
    @{
        Name = "HDR Bloom"
        Version = "1.0.0"
        Asset = "HDR-Bloom-1.0.0-$Version.zip"
        Source = @("Shaders/HDR_Bloom.fx", "Shaders/HDR_Bloom_Math.fxh")
        Presets = "Presets/HDR_Bloom"
        Guide = "docs/HDR_Bloom/README.md"
        Docs = @("docs/HDR_Bloom")
        Tests = @("tests/HDR_Bloom")
        Validation = @()
        PresetCount = 9
        LicenseFile = "licenses/HDR_Bloom.txt"
    },
    @{
        Name = "Adaptive Detail"
        Version = "1.0.0"
        Asset = "Adaptive-Detail-1.0.0-$Version.zip"
        Source = @("Shaders/Adaptive_Detail.fx", "Shaders/Adaptive_Detail_Core.fxh")
        Presets = "Presets/Adaptive_Detail"
        Guide = "docs/Adaptive_Detail/README.md"
        Docs = @("docs/Adaptive_Detail")
        Tests = @()
        Validation = @("validation/Adaptive_Detail")
        PresetCount = 9
        LicenseFile = "licenses/Adaptive_Detail.txt"
    },
    @{
        Name = "HDR IPS Enhance"
        Version = "1.0.1"
        Asset = "HDR-IPS-Enhance-1.0.1-$Version.zip"
        Source = @("Shaders/HDR_IPS_Enhance.fx", "Shaders/HDRIPS_Math.fxh")
        Presets = "Presets/HDR_IPS_Enhance"
        Guide = "docs/HDR_IPS_Enhance/README.md"
        Docs = @("docs/HDR_IPS_Enhance")
        Tests = @("tests/HDR_IPS_Enhance")
        Validation = @("validation/HDR_IPS_Enhance")
        PresetCount = 3
        LicenseFile = "licenses/HDR_IPS_Enhance.txt"
    },
    @{
        Name = "Output Dither"
        Version = "1.0.0"
        Asset = "Output-Dither-1.0.0-$Version.zip"
        Source = @("Shaders/Output_Dither.fx", "Shaders/Output_Dither_Core.fxh")
        Textures = @("Textures/Output_Dither_BN128.png", "Textures/provenance.json", "Textures/PROVENANCE.md")
        Presets = ""
        Guide = "docs/Output_Dither/README.md"
        Docs = @("docs/Output_Dither")
        Tests = @()
        Validation = @("validation/Output_Dither")
        PresetCount = 0
        LicenseFile = "licenses/Output_Dither.txt"
    }
)

$forbiddenExtensions = @(".zip", ".exe", ".dll", ".pdb", ".so", ".dylib", ".pyc", ".pyo", ".tmp", ".cache")
$textExtensions = @(".md", ".txt")
$testExtensions = @(".py", ".cpp", ".h", ".hpp", ".md", ".txt", ".json", ".csv", ".sh")
$validationExtensions = @(".py", ".ps1", ".cpp", ".h", ".hpp", ".inl", ".md", ".txt", ".json", ".csv", ".sh", ".png")
$stageRoot = Join-Path $env:TEMP ("reshade-release-stage-" + [Guid]::NewGuid().ToString("N"))
$script:currentStage = ""

Add-Type -AssemblyName System.IO.Compression.FileSystem

function Copy-RelativeFile([string]$relativePath) {
    $source = Join-Path $repository $relativePath
    if (!(Test-Path -LiteralPath $source -PathType Leaf)) {
        throw "Required release file is missing: $relativePath"
    }
    $destination = Join-Path $script:currentStage $relativePath
    $parent = Split-Path -Parent $destination
    if (!(Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    Copy-Item -LiteralPath $source -Destination $destination -Force
}

function Copy-FilteredTree([string]$relativePath, [string[]]$extensions) {
    $sourceRoot = Join-Path $repository $relativePath
    if (!(Test-Path -LiteralPath $sourceRoot -PathType Container)) {
        throw "Required release directory is missing: $relativePath"
    }
    Get-ChildItem -LiteralPath $sourceRoot -File -Recurse | ForEach-Object {
        $relativeWithinTree = $_.FullName.Substring($sourceRoot.Length).TrimStart("\")
        $segments = $relativeWithinTree -split "[\\/]"
        if ($segments -contains ".work" -or $segments -contains "__pycache__" -or $segments -contains ".pytest_cache") {
            return
        }
        if ($extensions -notcontains $_.Extension.ToLowerInvariant()) {
            return
        }
        $destination = Join-Path (Join-Path $script:currentStage $relativePath) $relativeWithinTree
        $parent = Split-Path -Parent $destination
        if (!(Test-Path -LiteralPath $parent)) {
            New-Item -ItemType Directory -Path $parent -Force | Out-Null
        }
        Copy-Item -LiteralPath $_.FullName -Destination $destination -Force
    }
}

function Write-Utf8File([string]$path, [string[]]$lines) {
    $parent = Split-Path -Parent $path
    if (!(Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    [System.IO.File]::WriteAllText(
        $path,
        (($lines -join "`r`n") + "`r`n"),
        [System.Text.UTF8Encoding]::new($false)
    )
}

function New-Archive([string]$name) {
    $path = Join-Path $OutputDirectory $name
    if (Test-Path -LiteralPath $path) {
        throw "Refusing to overwrite existing release asset: $path"
    }
    [System.IO.Compression.ZipFile]::CreateFromDirectory(
        $script:currentStage,
        $path,
        [System.IO.Compression.CompressionLevel]::Optimal,
        $false
    )
    return $path
}

function Test-Archive(
    [string]$archivePath,
    [string]$expectedEffect = "",
    [int]$expectedEffectCount = 0,
    [int]$expectedPresetCount = 0
) {
    $verifyRoot = Join-Path $stageRoot ("verify-" + [Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $verifyRoot | Out-Null
    [System.IO.Compression.ZipFile]::ExtractToDirectory($archivePath, $verifyRoot)
    $entries = [System.IO.Compression.ZipFile]::OpenRead($archivePath)
    try {
        $names = @($entries.Entries | ForEach-Object { $_.FullName })
        if (($names | Select-Object -Unique).Count -ne $names.Count) {
            throw "Duplicate archive paths in $archivePath"
        }
        foreach ($entryName in $names) {
            $extension = [System.IO.Path]::GetExtension($entryName).ToLowerInvariant()
            if ($forbiddenExtensions -contains $extension) {
                throw "Forbidden file extension '$extension' in $archivePath"
            }
            if ($entryName -match "(^|/)(\.work|__pycache__|\.pytest_cache)(/|$)") {
                throw "Cache directory included in $archivePath`: $entryName"
            }
        }
    }
    finally {
        $entries.Dispose()
    }

    $shaderRoot = Join-Path $verifyRoot "Shaders"
    $shaderFiles = @(Get-ChildItem -LiteralPath $shaderRoot -Filter "*.fx" -File -Recurse)
    if ($expectedEffectCount -gt 0 -and $shaderFiles.Count -ne $expectedEffectCount) {
        throw "Expected $expectedEffectCount effects, found $($shaderFiles.Count) in $archivePath"
    }
    if ($expectedEffect) {
        if ($shaderFiles.Count -ne 1 -or $shaderFiles[0].BaseName -ne $expectedEffect) {
            throw "Unexpected shader set in $archivePath"
        }
    }
    foreach ($shader in (Get-ChildItem -LiteralPath $shaderRoot -Include "*.fx", "*.fxh" -File -Recurse)) {
        $source = Get-Content -LiteralPath $shader.FullName -Raw
        foreach ($include in [regex]::Matches($source, '#include\s*["<]([^">]+)[">]')) {
            $includePath = Join-Path $shader.DirectoryName $include.Groups[1].Value
            if (!(Test-Path -LiteralPath $includePath -PathType Leaf)) {
                throw "Missing shader include '$($include.Groups[1].Value)' from $($shader.FullName)"
            }
        }
        foreach ($texture in [regex]::Matches($source, '\bsource\s*=\s*"([^"]+)"')) {
            $textureName = [System.IO.Path]::GetFileName($texture.Groups[1].Value)
            $texturePath = Join-Path $verifyRoot "Textures/$textureName"
            if (!(Test-Path -LiteralPath $texturePath -PathType Leaf)) {
                throw "Missing texture asset '$textureName' referenced by $($shader.FullName)"
            }
        }
    }
    $presetRoot = Join-Path $verifyRoot "Presets"
    $presets = if (Test-Path -LiteralPath $presetRoot -PathType Container) {
        @(Get-ChildItem -LiteralPath $presetRoot -Filter "*.ini" -File -Recurse)
    }
    else {
        @()
    }
    if ($expectedPresetCount -gt 0 -and $presets.Count -ne $expectedPresetCount) {
        throw "Expected $expectedPresetCount presets, found $($presets.Count) in $archivePath"
    }
    foreach ($preset in $presets) {
        $presetText = Get-Content -LiteralPath $preset.FullName -Raw
        foreach ($reference in [regex]::Matches($presetText, '(?m)^(?:Techniques|TechniqueSorting)=(.*)$')) {
            foreach ($item in $reference.Groups[1].Value.Split(",")) {
                if ($item.Trim() -match "^[^@]+@(.+\.fx)$") {
                    $effectPath = Join-Path $shaderRoot $Matches[1]
                    if (!(Test-Path -LiteralPath $effectPath -PathType Leaf)) {
                        throw "Preset '$($preset.FullName)' references missing effect '$($Matches[1])'"
                    }
                }
            }
        }
    }
}

New-Item -ItemType Directory -Path $stageRoot | Out-Null
$archives = [System.Collections.Generic.List[string]]::new()
try {
    $script:currentStage = Join-Path $stageRoot "collection"
    New-Item -ItemType Directory -Path $script:currentStage | Out-Null
    foreach ($file in @("README.md", "RELEASE_NOTES.md", "LICENSE")) {
        Copy-RelativeFile $file
    }
    Copy-FilteredTree "Shaders" @(".fx", ".fxh")
    Copy-FilteredTree "Presets" @(".ini")
    Copy-FilteredTree "Textures" @(".png", ".json", ".md")
    Copy-FilteredTree "docs" @(".md", ".txt")
    Copy-FilteredTree "licenses" @(".md", ".txt")
    Copy-FilteredTree "tests" $testExtensions
    Copy-FilteredTree "validation" $validationExtensions
    $archive = New-Archive $collectionName
    Test-Archive $archive "" 9 51
    $archives.Add($archive)

    foreach ($effect in $effects) {
        $script:currentStage = Join-Path $stageRoot ("effect-" + ($effect.Name -replace "[^A-Za-z0-9]+", "-"))
        New-Item -ItemType Directory -Path $script:currentStage | Out-Null
        foreach ($sourceFile in $effect.Source) {
            Copy-RelativeFile $sourceFile
        }
        foreach ($textureFile in $effect.Textures) {
            Copy-RelativeFile $textureFile
        }
        if ($effect.Presets) {
            Copy-FilteredTree $effect.Presets @(".ini")
        }
        if ($effect.Guide -like "docs/*/README.md") {
            Copy-FilteredTree (Split-Path $effect.Guide -Parent) $textExtensions
        }
        else {
            Copy-RelativeFile $effect.Guide
        }
        foreach ($testPath in $effect.Tests) {
            Copy-FilteredTree $testPath $testExtensions
        }
        foreach ($validationPath in $effect.Validation) {
            Copy-FilteredTree $validationPath $validationExtensions
        }
        Copy-RelativeFile "validation/RELEASE_VALIDATION.md"
        if ($effect.ContainsKey("License")) {
            Copy-RelativeFile "LICENSE"
        }
        else {
            Copy-RelativeFile $effect.LicenseFile
        }
        $readme = @(
            "# $($effect.Name) $($effect.Version)",
            "",
            "This archive contains the installation source and presets for this effect.",
            "",
            "1. Copy the listed `.fx` file and any required sibling `.fxh` files from `Shaders/` into a directory in ReShade's effect search paths."
        )
        if ($effect.Textures) {
            $readme += "2. Copy the files under `Textures/` into a configured ReShade texture search path, preserving their filenames."
        }
        if ($effect.Presets) {
            $readme += "3. Reload effects, then select a preset from `Presets/$($effect.Presets.Split('/')[-1])/`."
        }
        else {
            $readme += "3. Reload effects and select the technique manually; no preset enables it."
        }
        $readme += @(
            "4. Read the complete installation, contract, and tuning guide at ``$($effect.Guide)`` before enabling the effect.",
            "",
            "The original source version is unchanged. This archive contains no compiled shader binaries."
        )
        Write-Utf8File (Join-Path $script:currentStage "README.md") $readme
        $archive = New-Archive $effect.Asset
        Test-Archive $archive ([System.IO.Path]::GetFileNameWithoutExtension($effect.Source[0])) 1 $effect.PresetCount
        $archives.Add($archive)
    }

    $sumLines = foreach ($asset in ($archives | Sort-Object)) {
        $hash = (Get-FileHash -LiteralPath $asset -Algorithm SHA256).Hash.ToLowerInvariant()
        "$hash  $([System.IO.Path]::GetFileName($asset))"
    }
    $sumPath = Join-Path $OutputDirectory "SHA256SUMS.txt"
    if (Test-Path -LiteralPath $sumPath) {
        throw "Refusing to overwrite existing checksum file: $sumPath"
    }
    Write-Utf8File $sumPath $sumLines
    foreach ($line in (Get-Content -LiteralPath $sumPath)) {
        $parts = $line -split "\s+", 2
        $assetPath = Join-Path $OutputDirectory $parts[1]
        if ((Get-FileHash -LiteralPath $assetPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $parts[0]) {
            throw "Checksum verification failed: $($parts[1])"
        }
    }
    Write-Output "Verified $($archives.Count) ZIP assets and $($sumLines.Count) SHA-256 entries in $OutputDirectory"
    $archives | ForEach-Object {
        $item = Get-Item -LiteralPath $_
        Write-Output "$($item.Name) $($item.Length) bytes"
    }
    Write-Output "SHA256SUMS.txt"
}
finally {
    if (Test-Path -LiteralPath $stageRoot) {
        Remove-Item -LiteralPath $stageRoot -Recurse -Force
    }
}
