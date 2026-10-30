#!/usr/bin/env python3
"""Run CPU checks and optionally the pinned ReShade FX compiler harness."""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIN = "7bf9de8b33bcc76c3177007e65d73c72dd0f34c0"


def run(command, cwd=ROOT):
    print("+", " ".join(map(str, command)), flush=True)
    subprocess.run(list(map(str, command)), cwd=cwd, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reshade-source", type=Path,
                        help="Existing crosire/reshade checkout at the pinned commit")
    parser.add_argument("--cxx", default="g++", help="C++17 compiler (default: g++)")
    args = parser.parse_args()
    for generator in ("generate_ips_suite_includes.py", "generate_ips_suite_presets.py"):
        run([sys.executable, ROOT / "validation" / generator, "--check"])
    run([sys.executable, ROOT / "tests" / "IPS_Suite" / "test_generate_includes.py"])
    for shader in ("IPS_Depth_v2", "Selective_Deband", "Adaptive_Clarity", "IPS_Suite"):
        run([sys.executable, ROOT / "tests" / shader / "test_reference.py"])
    if args.reshade_source is None:
        print("FX parser/code generation NOT RUN: supply --reshade-source at pinned commit", flush=True)
    else:
        source = args.reshade_source.resolve()
        revision = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
        if revision != PIN:
            raise SystemExit(f"Wrong ReShade source revision: {revision}, expected {PIN}")
        files = ("effect_preprocessor", "effect_lexer", "effect_expression", "effect_symbol_table",
                 "effect_parser_exp", "effect_parser_stmt", "effect_codegen_hlsl", "effect_codegen_glsl")
        with tempfile.TemporaryDirectory(prefix="ips-suite-fx-") as work:
            work = Path(work)
            flags = ["-std=c++17", "-w", "-O1", "-DSH_DENYWR=0x20",
                     "-I" + str(source / "source"), "-I" + str(source / "include"),
                     "-I" + str(source / "deps" / "spirv")]
            run([args.cxx, *flags, "-c", *(source / "source" / (f + ".cpp") for f in files)], cwd=work)
            for shader in ("IPS_Depth_v2", "Selective_Deband", "Adaptive_Clarity", "IPS_Suite"):
                exe = work / ("check_fx.exe" if sys.platform == "win32" else "check_fx")
                run([args.cxx, *flags, ROOT / "tests" / shader / "check_fx.cpp",
                     *(work / (f + ".o") for f in files), "-o", exe])
                run([exe, ROOT / "Shaders" / (shader + ".fx")])
    print("GPU driver compilation and in-game rendering, motion and timing NOT RUN.", flush=True)


if __name__ == "__main__":
    main()
