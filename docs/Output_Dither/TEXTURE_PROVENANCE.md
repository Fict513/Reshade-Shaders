# Blue-noise asset provenance

`Output_Dither_BN128.png` was generated for this package by the original
`validation/generate_noise.py`, not downloaded or copied. See that script,
`provenance.json`, TECHNICAL.md and SOURCES.md for algorithm and parameters.

The generator implements Robert Ulichney's published three-phase void-and-cluster
ranking, using circular Gaussian energy and deterministic PCG64 initialization.
All 16,384 ranks occur once; each byte bin receives 64 ranks. The PNG is grayscale
8-bit, no transfer-function conversion, no mip chain, and is loaded into R8 UNORM.

The asset and generator are distributed under the package's MIT license. Re-run
the generator and compare the **decoded pixel SHA-256** to reproduce the mask;
PNG container bytes can vary with library versions even for identical pixels.
No code or assets from Ulichney, Peters or ReShade are redistributed in the shader.
