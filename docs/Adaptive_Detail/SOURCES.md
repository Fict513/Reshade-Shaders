# Primary sources and provenance

Research used official source/documentation, inspected 2026-10-31. The production shader is original; it does not contain CAS shader code. Validation-only adaptations and vendored compiler code have their own notices.

1. **ReShade FX language reference:** https://github.com/crosire/reshade-shaders/blob/slim/REFERENCE.md
   Verified COLOR semantics, texture formats/dimensions, sampler filters and sRGB flags, pass state, and the fact that BUFFER_COLOR_SPACE describes presentation. This effect therefore requires a separate verified sampled-buffer contract.
2. **ReShade official source, commit `7bf9de8b33bcc76c3177007e65d73c72dd0f34c0`:** https://github.com/crosire/reshade/tree/7bf9de8b33bcc76c3177007e65d73c72dd0f34c0
   Inspected `source/runtime.cpp`: macro definitions near 1663, COLOR SRV selection near 2762, non-sRGB format normalization near 3593, intermediate-target color-space handling near 4012, COLOR snapshot copying near 4120, and render-target selection/refresh near 4190. These observations support the two-pass snapshot assumption for the standard runtime, not every add-on integration. `effect_module.hpp` confirms texture format enum values. The compiler subset used in validation is included with its license and hashes under `validation/vendor/reshade/`.
3. **Microsoft, Use DirectX with Advanced Color on high/standard dynamic range displays:** https://learn.microsoft.com/en-us/windows/win32/direct3darticles/high-dynamic-range
   Verified the HDR scRGB 80-nit unit, signed/out-of-[0,1] color representation, and HDR10/PQ/BT.2020 swap-chain conventions. These describe presentation contracts; they do not establish an arbitrary intermediate buffer's encoding.
4. **ITU-R BT.2100-3 (02/2025), especially Table 4:** https://www.itu.int/rec/R-REC-BT.2100-3-202502-I/en
   Verified ST 2084 equations, constants and absolute component-nit interpretation. The effect uses the inverse EOTF for already display-mapped images; it does not apply the scene OOTF. Full-range normalized RGB codes are this effect's explicit contract, not a claim that every broadcast/video signal uses full range.
5. **ICC sRGB registry:** https://registry.color.org/rgb-registry/srgb
   **W3C exact sRGB/relative-luminance equations:** https://www.w3.org/WAI/WCAG21/Understanding/relative-luminance.html
   Verified the piecewise transfer functions and BT.709 relative-luminance coefficients. These are used without a guessed gamma approximation.
6. **AMD GPUOpen CAS technique documentation:** https://gpuopen.com/manuals/fidelityfx_sdk/techniques/contrast-adaptive-sharpening/
   **Official CAS source, commit `9fabcc9a2c45f958aff55ddfda337e74ef894b7f`:** https://github.com/GPUOpen-Effects/FidelityFX-CAS/blob/9fabcc9a2c45f958aff55ddfda337e74ef894b7f/ffx-cas/ffx_cas.h
   Examined `CasSetup` and the no-scaling `CasFilter` path, contrast-dependent weights, normalized limits, optional arithmetic variants and license. The included grayscale CPU comparison selects exact sqrt/reciprocal arithmetic without better-diagonal extrema. It is not an execution of the full official GPU implementation.

No copied standards PDF or proprietary SDK is bundled. No third-party code is used in the production effect beyond independently implemented standard transfer equations.
