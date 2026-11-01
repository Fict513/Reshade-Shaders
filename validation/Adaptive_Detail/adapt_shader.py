"""Mechanical FX-to-C++ adapter. Keeps production control flow and arithmetic.
Replaces only resource/uniform declarations, vector swizzles, entry semantics,
vertex shader, and sampler intrinsics. This is NOT GPU execution.
"""
from pathlib import Path
import re
import sys
root=Path(__file__).resolve().parents[1]
fx=(root/'Shaders/Adaptive_Detail.fx').read_text()
body=fx[fx.index('int AD_GetContract()'):fx.index('technique Adaptive_Detail')]
a=body.index('void AD_VS('); b=body.index('float AD_Prepare(')
body=body[:a]+body[b:]
body=re.sub(r'\s*:\s*(SV_Position|TEXCOORD|SV_Target)', '', body)
body=body.replace('[unroll]','').replace('.rgb','.rgb()').replace('t.xxx','float3(t,t,t)')
# FX literals are FP32. Preserve that in C++, which otherwise promotes to double.
body=re.sub(r'(?<![\w.])(\d+\.\d*(?:[eE][+-]?\d+)?)(?![\w.])',r'\1f',body)
Path(sys.argv[1]).write_text('#include "cpu_shim.hpp"\n#include "../Shaders/Adaptive_Detail_Core.fxh"\n'+body+'\n#include "cpu_driver.hpp"\n')
