# Establish the actual injection contract

## Modes

| InputMode | Contract | Working units | Destination |
|---:|---|---|---|
| 0 | Auto: only a previously verified per-injection profile | As profile specifies | Same contract |
| 1 | Full-range sRGB transfer, BT.709/sRGB primaries, D65 | Linear 1 = reference white, no measured-nit claim | Full-range sRGB |
| 2 | Full-range ST 2084 PQ, BT.2020 primaries, D65 | Absolute linear component nits; Y is luminance | Same PQ/BT.2020 |
| 3 | Linear scRGB, BT.709 primaries, nominal 80 nits/unit | Source components multiplied by 80; signed/extended | Divide by 80; signed/extended scRGB |
| 4 | Safe bypass | None | Original sampled float4 |

Auto uses `HDRBLOOM_AUTO_CONTRACT` at compile time: 0 = unknown/bypass (default), 1 = verified SDR sRGB, 2 = verified PQ/2020, 3 = verified scRGB/709. No presentation, pixel-format, image-statistics, executable-name or bit-depth heuristic runs. Setting this definition is an assertion backed by the procedure below; it is not a discovery mechanism. Leave 0 when a game can switch HDR state or injection paths without updating the profile. Explicit modes make the same assertion interactively.

An FX-only effect cannot discover an arbitrary intermediate buffer's transfer function or physical meaning from its numeric values. Unsupported HLG, gamma 2.2/2.4, custom/log encodings, narrow-range PQ, PQ in different primaries, scene-referred HDR requiring a display transform, mismatched destination encodings, and premultiplied/translucent intermediate contracts are not supported: leave bypass enabled. The shader cannot detect a wrongly asserted contract.

## Verification procedure

1. **Identify the precise effect injection point.** Record game build, graphics API, HDR setting, ReShade version, other injectors/add-ons and any render-target replacement. Work with an authorized/offline capture when the game permits graphics debugging. Ordinary presentation metadata alone is only a clue.
2. **Inspect the resource actually bound to this effect's COLOR sampler** in PIX, RenderDoc, an equivalent API capture, or reliable injection documentation that explicitly covers this resource. Trace its producer and any copy/resolve to the sampled view. Determine format, primaries, transfer, numeric scale, alpha semantics and whether the image is already HDR/display-mapped. A floating-point resource can contain PQ or scene-linear data; a 10-bit resource can contain SDR.
3. **Inspect the destination RTV and downstream path.** Establish that this effect writes the same encoding it reads. Check that its non-sRGB SRV and non-sRGB RTV are really used; if a custom runtime/add-on substitutes sRGB views, this shader's manual transforms would double-convert. Inspect whether any later pass converts, tone-maps, quantizes, scales SDR white or applies a gamut transform. This also identifies whether final 8/10-bit rounding occurs here or elsewhere.
4. **Cross-check known values**, preferably using controlled content through the same producer path. Examples: neutral 100-nit PQ is approximately 0.508078; 1,000 nits is 0.751827; 10,000 nits is 1. Linear scRGB 1 = 80 nits and 12.5 = 1,000 nits. SDR encoded 0.5 means approximately 0.214041 linear reference white. Values alone are not proof: establish how those values were authored and transformed. OS screenshots, camera photographs and guessed in-game light brightness are not raw-buffer measurements.
5. **Record the evidence.** Suggested record: resource/SRV and destination/RTV identity, source pass, view formats, transfer and primaries, linear scale, alpha semantics, downstream transformations, API/game/HDR/ReShade versions, capture or documentation reference. Then select a mode. Only set Auto's profile for that verified configuration.
6. **Check passthrough and diagnostics.** Strength 0 must be visually unchanged; separately compare captured shader samples/output if exactness matters. Check a neutral bright patch, a near-black ramp, saturated lights and the output-limit view. This catches mistakes but does not replace resource provenance. Reverify after HDR-mode, injection, API or significant game/mod changes.

## Verified implementation behavior

At official ReShade source commit `7bf9de8b33bcc76c3177007e65d73c72dd0f34c0`, `runtime.cpp` creates `BUFFER_COLOR_SPACE` from the presentation-related permutation state (line 1663). COLOR sampling selects `color_srv[binding.srgb]` (line 2763); final output chooses between the linear and sRGB render-target views using `pass.srgb_write_enable` (line 4194). This shader declares `SRGBTexture=false` on every sampler and `SRGBWriteEnable=false` on every pass, then performs its own transfer functions. No ReShade.fxh implicit sampler state is inherited.

The official runtime API also specifies separate non-sRGB and sRGB target views for effect rendering. A modified injection can alter the resource/scale, so verify that path rather than assuming the stock runtime semantics prove all third-party integrations.

## Standards and primary references

- [ReShade FX reference](https://github.com/crosire/reshade-shaders/blob/slim/REFERENCE.md): COLOR semantic, sampler/render-target states and presentation macro.
- [Pinned official runtime source](https://github.com/crosire/reshade/blob/7bf9de8b33bcc76c3177007e65d73c72dd0f34c0/source/runtime.cpp), inspected locally; compiler built from the same checkout.
- [Official effect_runtime API](https://crosire.github.io/reshade-docs/structreshade_1_1api_1_1effect__runtime.html): non-sRGB versus sRGB output-view contract.
- [ITU-R BT.2100-3, February 2025](https://www.itu.int/rec/R-REC-BT.2100-3-202502-I/en): Table 2 primaries and Table 4 PQ EOTF/constants. This shader implements display-light EOTF/inverse, not a scene OOTF. Full-range encoding is explicit here; broadcast narrow-range code values are not used.
- [Microsoft: DirectX with Advanced Color](https://learn.microsoft.com/en-us/windows/win32/direct3darticles/high-dynamic-range): Windows scRGB nominal 80-nit scale, signed/extended components, swap-chain formats and color-space distinction.
- [Khronos Data Format 1.4, §13.3](https://registry.khronos.org/DataFormat/specs/1.4/dataformat.1.4.html#TRANSFER_SRGB): piecewise sRGB transfer. The exact standardized breakpoints 0.04045 and 0.0031308 are used, not a gamma-2.2 approximation.

References consulted during implementation on 2026-10-31. Build identifiers, not a claim about every future ReShade revision, anchor the source inspection.
