# v1.2.0 repository integration validation

This report records checks run for the repository integration. The per-effect
CPU reports under `validation/` and `docs/` were supplied with their original
shader packages; they are historical package evidence and are not represented
as newly executed results here.

## ReShade FX front end

Built the supplied small CLI harnesses against the unmodified ReShade FX
preprocessor, parser, and HLSL/GLSL generators from commit
`7bf9de8b33bcc76c3177007e65d73c72dd0f34c0`. Zig C++ 0.17.0 was used on
Windows; `SH_DENYWR=0x20` was defined to accommodate the upstream source's
Windows CRT constant in this toolchain. This definition affects file-sharing
mode only, not shader parsing or generated code.

| Effect(s) | Configurations | Assertions and scope |
|---|---:|---|
| HDR Bloom 1.0.0 | 288 HLSL/GLSL configurations | Six resolutions including one-pixel, odd, and 3440×1440 dimensions; three quality levels; diagnostics on/off; four input modes; both backends. Checked parse/codegen success, 12 passes, 13 entry points, 12 module textures, and expected ceil-divided pyramid dimensions for all 11 owned textures. |
| Adaptive Detail 1.0.0 | 24 configurations, each generating HLSL and GLSL | Two destination-format macro values, all three quality levels, optional detail on/off, and verified-contract on/off. Checked code generation and module metadata. The shared R32F analysis texture remains required by fine sharpening when the optional broad detail stage is disabled. |
| HDR IPS Enhance 1.0.1 | 72 HLSL/GLSL configurations | Three quality levels, local and color stages on/off, three reported presentation spaces, and both backends. Checked successful code generation; compiling out the local stage removed its effect-owned intermediate texture. Disabling color also reduced generated code. |
| All repository effects | 16 HLSL/GLSL modules | Generated both backends for all eight `.fx` effects with the same pinned upstream front end. This is front-end parsing/code generation, not GPU driver compilation. |

## Presets, paths, and source integration

- Checked all 51 `.ini` presets for existing shader/technique references and
  uniform keys. The IPS Suite's generated, renamed controls were checked
  against its ReShade-generated HLSL because those controls originate in
  included modules.
- Checked all shader `#include` paths and preserved sibling/nested include
  filenames. The full collection contains no colliding shader/include paths.
- The supplied IPS Depth v2, Selective Deband, and Adaptive Clarity sources
  match the repository copies; they were retained rather than duplicated or
  rewritten. Their overlapping alternatives remain distinct effects.
- The original package checksum manifests were verified during source
  extraction. No source shader algorithms, techniques, or uniform names were
  changed in this integration.

## Distribution packages

Generated one collection archive and six individual effect archives, then
extracted each into a fresh directory. The collection contains eight effects
and 51 presets; the individual packages contain, respectively, 6, 6, 6, 9, 9
and 3 presets. Verified expected effect files, all relative shader includes,
preset effect-file references, unique archive paths, and absence of compiler
binaries, nested ZIPs and cache directories. `SHA256SUMS.txt` contains and
verifies one entry for each of the seven ZIP assets. The host policy blocked
direct execution of the checked-in PowerShell helper, so these checks were
performed with equivalent direct PowerShell commands without changing the
policy.

## Not run / limitations

The package CPU suites were **not rerun** in this Windows worktree: Python with
NumPy/SciPy and a compatible GNU C++ toolchain are not installed. Existing
package reports are retained and explicitly attributed as historical; they
are not substitutes for this run's checks. No GPU driver compilation, GPU
execution, in-game rendering, visual review, compatibility test on a specific
game, or performance measurement was performed.
