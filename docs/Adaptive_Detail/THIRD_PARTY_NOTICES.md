# Third-party notices

## ReShade FX compiler source (validation only)

The files under `validation/vendor/reshade/source/` are unmodified official ReShade source from commit `7bf9de8b33bcc76c3177007e65d73c72dd0f34c0`, Copyright 2014 Patrick Mours, under BSD-3-Clause. The full license is retained at `validation/vendor/reshade/LICENSE.md`; each source retains its notice. The original `fx_frontend.cpp` harness links this subset only for validation. This does not imply ReShade endorsement or provide a ReShade injector binary.

## AMD CAS grayscale mathematical baseline (validation only)

`validation/compare_baselines.py`, function `cas_gray`, adapts the mathematical no-scaling filter in AMD's published CAS implementation for a grayscale NumPy comparison. The production shader does not reuse CAS code. The applicable permission notice is retained here:

Copyright (c) 2017-2019 Advanced Micro Devices, Inc. All rights reserved.

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

## Development tools

Python, NumPy, GCC and optional Matplotlib are external test-tool requirements and are not distributed as binaries in this package. Generated HLSL/GLSL and native test binaries are reproducible and intentionally omitted from the release ZIP.
