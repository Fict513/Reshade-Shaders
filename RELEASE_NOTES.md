# FakeHDR Advanced v1.0.0

Initial release of the supplied SDR HDR-look shader. The seven-pass effect
provides fine, medium and broad local contrast, shadow and highlight controls,
gamut handling, comparison views and optional static dither.

Changes from the supplied source:

- Keep in-gamut saturated colors unchanged by the gamut knee when grading
  amounts are zero.
- Limit brightening to available channel headroom to avoid washing saturated
  highlights toward white. This can limit brightening of saturated colors.
- Guard the sRGB decode power operation against negative inputs.

ReShade FX parsing and HLSL generation passed for quality levels 0, 1 and 2;
the generated HLSL compiled to DXBC and ran on the D3D11 WARP software
rasterizer. This is not GPU-driver or in-game validation. No performance or
visual comparisons have been measured. HDR color spaces reported by ReShade
are passed through; unknown color spaces are treated as SDR.

See the README for installation, limitations and tuning, and
`validation/README.md` for reproducible checks and their scope.
