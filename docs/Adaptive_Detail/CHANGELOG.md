# 1.0.0

Initial implementation: verified-contract bypass by default; exact sRGB/PQ transfer functions; signed scRGB; two linear-luminance bands; common RGB gain; shared smooth correction budget; continuous edge/noise/shadow protection; four diagnostic modes; three artistic presets in three encodings; FP32 analysis; Normal/High and explicit Ultra alias; optional detail compilation.

Validation refinement: regularized the limiter-activity diagnostic after investigating sensitivity to near-zero residuals in float32 PQ arithmetic. Normal image output was not changed by that diagnostic fix.

Known integration limit: no GPU driver or in-game validation in the build environment. See VALIDATION.md before treating the package as hardware-verified.
