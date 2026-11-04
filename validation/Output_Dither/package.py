#!/usr/bin/env python3
"""Build a source-only Output Dither package from the repository checkout."""
from pathlib import Path
import argparse
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[2]
VALIDATION_SUFFIXES = {".cpp", ".json", ".md", ".png", ".ps1", ".py", ".txt"}


def contents():
    paths = [
        "Shaders/Output_Dither.fx",
        "Shaders/Output_Dither_Core.fxh",
        "Textures/Output_Dither_BN128.png",
        "Textures/provenance.json",
        "Textures/PROVENANCE.md",
        "licenses/Output_Dither.txt",
    ]
    for directory in ("docs/Output_Dither", "validation/Output_Dither"):
        root = ROOT / directory
        suffixes = {".md", ".txt"} if directory.startswith("docs/") else VALIDATION_SUFFIXES
        paths.extend(
            path.relative_to(ROOT).as_posix()
            for path in root.rglob("*")
            if path.is_file()
            and path.suffix.lower() in suffixes
            and not any(part in {".work", "__pycache__", ".pytest_cache"} for part in path.parts)
        )
    return {name: ROOT / name for name in sorted(set(paths))}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "validation" / ".work" / "Output_Dither" / "Output-Dither-1.0.0.zip",
    )
    output = parser.parse_args().output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    files = contents()
    manifest = {
        name: hashlib.sha256(path.read_bytes()).hexdigest()
        for name, path in files.items()
    }
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, path in files.items():
            info = zipfile.ZipInfo(name, (2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes(), compresslevel=9)
        archive.writestr(
            "MANIFEST.json",
            json.dumps(manifest, indent=2) + "\n",
            compress_type=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        )
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise SystemExit("Package ZIP failed integrity verification")
        for name, digest in manifest.items():
            if hashlib.sha256(archive.read(name)).hexdigest() != digest:
                raise SystemExit(f"Package file hash mismatch: {name}")
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    checksum = output.with_suffix(output.suffix + ".sha256")
    checksum.write_text(f"{digest}  {output.name}\n", encoding="ascii")
    print(f"{output}\n{checksum}\n{digest}")


if __name__ == "__main__":
    main()
