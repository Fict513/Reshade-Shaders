# Output Dither repository integration checks

This report covers checks performed while adding the supplied Output Dither
1.0.0 package to this repository. Figures in
[`../../docs/Output_Dither/VALIDATION.md`](../../docs/Output_Dither/VALIDATION.md)
are the original package's historical results, not results from this integration.

## Source and dependency checks

- Confirmed no existing `Output_Dither.fx` was present before integration.
- Preserved the supplied shader, helper include, and texture source basename.
  The `Output_Dither_Core.fxh` include resolves alongside the effect, and
  `Output_Dither_BN128.png` plus its provenance files are installed under the
  repository's top-level `Textures/` path.
- Checked the added `OD_` symbols, `OUTPUT_DITHER_ENABLE` macro, include guard,
  texture/sampler identifiers, and `Output_Dither` technique name against the
  other repository shader sources; no identifier or effect-file collision was
  found.
- Source inspection confirms the unknown/mismatched/scRGB, master-bypass,
  invalid-strength, invalid-domain, and zero-strength paths return the sampled
  input; the output alpha is taken from the original sample. No shader
  algorithm, uniform, technique, macro or texture identifier was changed.
- The supplied test source lists all four requested resolutions:
  1920×1080, 1920×1200, 2560×1440 and 3440×1440. This source-matrix inspection
  does not mean those tests were executed in this integration.
- Adapted the supplied harness paths to the repository layout. The generated FX
  fixture computes its include path relative to its scratch directory, and test
  results/build artifacts are directed to the ignored `validation/.work/` tree.
- Adapted the standalone package builder to use repository-relative allowlists
  and ignored scratch output instead of packaging the entire `validation/` tree.

## Package checks

The PowerShell release packager was parsed successfully after adding Output
Dither to its effect manifest. The dedicated IPS Suite packager now
allowlists the effect, include, texture/provenance, separate license,
documentation and reproducible validation materials, including its repository-
layout test instructions. The updated collection archive
`dist/output-dither-integration/ReShade-Shaders-v1.3.0-Collection.zip` was
built with the collection's source/package allowlist and extracted into a clean
temporary directory. It contains 9 top-level effects and 51 presets, with no
Output Dither preset activation. Include paths, texture paths, preset effect
references, unique archive paths, cache/binary exclusions and SHA-256 were
verified; the checksum is in the adjacent `SHA256SUMS.txt`.

The PowerShell release script could not be executed because this environment
prohibits running `.ps1` files by execution policy. The archive was therefore
built and inspected with an equivalent one-off PowerShell/.NET ZIP procedure;
the release script itself was syntax-parsed, not run.

The tracked `IPS_Suite_Distribution.zip` was also regenerated and cleanly
extracted. It contains 80 files, five effect shaders and 24 presets, including
Output Dither's shader, include, texture, license, guide and test instructions;
no preset enables Output Dither. Include and texture paths, the package README
guide link, the SHA-256 sidecar and the absence of generated binaries were
verified.

## Not run

The package CPU/reference and adapted-C++ tests were not run: Python with
NumPy/SciPy, a C++ compiler and Zig are unavailable in this worktree. No
Output-Dither-specific ReShade FX front-end/code-generation run was available;
cached front ends in the worktree are shader-specific harnesses for other
effects. No Microsoft HLSL bytecode compilation, GPU-driver compilation,
GPU execution, ReShade/game integration, Signal Inspector comparison,
display-link behavior, performance or visual testing was performed.

Accordingly, no GPU performance, monitor-calibration, displayed-image,
recovered-precision or in-game compatibility claim is made for this
integration. The supplied package's validation report remains attributed to
that package and its original environment.
