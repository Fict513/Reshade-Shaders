#!/usr/bin/env python3
"""Build a deterministic, explicitly allowlisted IPS Suite distribution."""
import argparse
import hashlib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def contents():
    paths = [
        "LICENSE", "Shaders/IPS_Suite.fx", "Shaders/IPS_Depth_v2.fx",
        "Shaders/Selective_Deband.fx", "Shaders/Adaptive_Clarity.fx",
        "validation/generate_ips_suite_includes.py", "validation/generate_ips_suite_presets.py",
        "validation/validate_ips_suite.py", "validation/package_ips_suite.py",
        "docs/IPS_Suite.md", "docs/IPS_Depth_v2.md", "docs/Selective_Deband.md", "docs/Adaptive_Clarity.md",
    ]
    for directory, pattern in (
        ("Shaders/IPS_Suite", "*.fxh"), ("Presets/IPS_Suite", "*.ini"),
        ("Presets/IPS_Depth_v2", "*.ini"), ("Presets/Selective_Deband", "*.ini"),
        ("Presets/Adaptive_Clarity", "*.ini"), ("tests/IPS_Depth_v2", "*.py"),
        ("tests/Selective_Deband", "*.py"), ("tests/Adaptive_Clarity", "*.py"),
        ("tests/IPS_Depth_v2", "*.cpp"), ("tests/Selective_Deband", "*.cpp"),
        ("tests/Adaptive_Clarity", "*.cpp"), ("tests/IPS_Suite", "*.py"),
        ("tests/IPS_Suite", "*.cpp"),
    ):
        paths.extend(str(p.relative_to(ROOT)) for p in (ROOT / directory).glob(pattern))
    result = {path: ROOT / path for path in paths}
    result["README.md"] = ROOT / "docs" / "IPS_Suite.md"
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "IPS_Suite_Distribution.zip")
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.parent.is_dir():
        raise SystemExit(f"Output directory does not exist: {output.parent}")
    files = contents()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, path in sorted(files.items()):
            info = zipfile.ZipInfo(name, (2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    checksum = output.with_name(output.name + ".sha256")
    checksum.write_text(f"{digest}  {output.name}\n")
    print(f"{output}\n{checksum}\n{digest}")


if __name__ == "__main__":
    main()
