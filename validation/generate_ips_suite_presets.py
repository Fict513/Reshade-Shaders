#!/usr/bin/env python3
"""Generate or verify coordinated presets from the supplied standalone INIs."""
import argparse
import configparser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "Presets" / "IPS_Suite"
SOURCES = (("IPS_Depth_v2", "Contrast"), ("Selective_Deband", "Deband"),
           ("Adaptive_Clarity", "Clarity"))
OMIT = {"Sharpen", "Dither", "SplitView", "SplitPosition", "View",
        "Mask1Enabled", "Mask1Rect", "Mask2Enabled", "Mask2Rect", "MaskFeather"}


def read_section(path, section):
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    parser.read_string("[root]\n" + path.read_text())
    return dict(parser[section])


def make_preset(style, tier, quality):
    settings = {}
    for shader, prefix in SOURCES:
        path = ROOT / "Presets" / shader / f"{style}_{tier}.ini"
        source = read_section(path, f"{shader}.fx")
        for key, value in source.items():
            if key not in OMIT:
                settings[prefix + key] = value
        if shader == "Selective_Deband":
            settings["OutputDither"] = source["Dither"]
    settings.update(Mask1Enabled="0", Mask1Rect="0.0, 0.82, 0.35, 1.0",
                    Mask2Enabled="0", Mask2Rect="0.65, 0.82, 1.0, 1.0",
                    MaskFeather="12.0", SplitView="0", SplitPosition="0.50", View="0")
    head = ("Techniques=IPS_Suite@IPS_Suite.fx\n"
            "TechniqueSorting=IPS_Suite@IPS_Suite.fx\n"
            f"PreprocessorDefinitions=IPS_SUITE_QUALITY={quality},IPS_SUITE_CONTRAST=1,"
            "IPS_SUITE_DEBAND=1,IPS_SUITE_CLARITY=1,IPS_SUITE_DITHER=1\n\n"
            "[IPS_Suite.fx]\n")
    return head + "".join(f"{key}={value}\n" for key, value in settings.items())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not args.check:
        DEST.mkdir(exist_ok=True)
    for style in ("Balanced", "RTX_Companion"):
        previous = None
        for quality, tier in enumerate(("Normal", "High", "Ultra")):
            path = DEST / f"IPS_Suite_{style}_{tier}.ini"
            content = make_preset(style, tier, quality)
            settings = content.split("[IPS_Suite.fx]\n", 1)[1]
            if previous is not None and settings != previous:
                raise ValueError(f"{style}: supplied preset strengths differ between tiers")
            previous = settings
            if args.check:
                if not path.exists() or path.read_text() != content:
                    raise SystemExit(f"Out of date: {path}")
            else:
                path.write_text(content)
    print("IPS Suite presets " + ("verified" if args.check else "generated"))


if __name__ == "__main__":
    main()
