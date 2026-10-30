# IPS Depth v2 + Selective Deband + Adaptive Clarity suite

Three independent SDR ReShade/GShade shaders and six merged presets:

| Shader | File | Quality definition | Guide |
|---|---|---|---|
| IPS Depth v2 | `Shaders/IPS_Depth_v2.fx` | `IPSD2_QUALITY` | [IPS_Depth_v2.md](IPS_Depth_v2.md) |
| Selective Deband | `Shaders/Selective_Deband.fx` | `SDB_QUALITY` | [Selective_Deband.md](Selective_Deband.md) |
| Adaptive Clarity | `Shaders/Adaptive_Clarity.fx` | `AC_QUALITY` | [Adaptive_Clarity.md](Adaptive_Clarity.md) |

The per-shader guides are the original package READMEs. Their file references
(`Presets`, `Tests/...`) correspond to this repository as `Presets/<Shader>/` and
`tests/<Shader>/` (tests are in the source archive and repository, not the
distribution zip). FakeHDR Advanced remains unchanged; see the root README.

## Install

1. Copy the three `.fx` files from `Shaders/` into your ReShade/GShade `Shaders` folder.
2. Copy `Presets/` somewhere permanent and pick a preset in the overlay.
3. Let shader compilation finish after changing a preset; quality tiers are compile-time definitions.

## Suite presets (`Presets/Suite/`)

Each preset enables all three effects in this order:

**IPS Depth v2 -> Selective Deband -> Adaptive Clarity**

| Preset | Quality definitions |
|---|---|
| `Suite_Balanced_Normal.ini`, `Suite_RTX_Companion_Normal.ini` | `IPSD2_QUALITY=0`, `SDB_QUALITY=0`, `AC_QUALITY=0` |
| `Suite_Balanced_High.ini`, `Suite_RTX_Companion_High.ini` | `IPSD2_QUALITY=1`, `SDB_QUALITY=1`, `AC_QUALITY=1` |
| `Suite_Balanced_Ultra.ini`, `Suite_RTX_Companion_Ultra.ini` | `IPSD2_QUALITY=2`, `SDB_QUALITY=2`, `AC_QUALITY=2` |

All presets also set `IPSD2_LOCAL=1`, `IPSD2_BROAD=1`, `SDB_HUD_MASKS=1`, `SDB_DITHER=1`, `AC_HUD_MASKS=1`.
Each effect's slider values are those of the matching individual preset, with two
exceptions: in every suite preset **IPS Depth Sharpen = 0** and **IPS Depth Dither = 0**
(Selective Deband supplies selective dither; Adaptive Clarity supplies sharpening-like
clarity, so stacking IPS sharpen/dither is avoided). The Balanced individual
IPS presets use Dither 0.15; the suite deliberately does not.

Both HUD-mask rectangles are disabled in every preset; see the individual guides.

The INIs do not set or detect NVIDIA RTX Dynamic Vibrance. "RTX Companion" only
selects the milder slider values described in the individual guides.

## Notes

- Do not enable FakeHDR Advanced, IPS Depth / IPS Depth HQ or other local-contrast, deband or sharpen effects at the same time; effects compound.
- Everything processes the whole frame, HUD and text included.
- Presets replace the technique list; save your existing preset first.
- Combined-stack cost, visual quality and compatibility were **not measured**. Only the individual shaders were validated (see `validation/README.md`); the suite presets were checked for structure and consistency, not rendered.

## Validation

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File validation\Validate-Suite.ps1
```

See [validation/README.md](../validation/README.md) for scope and limits.
