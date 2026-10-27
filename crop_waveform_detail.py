#!/usr/bin/env python3
"""Recursively crop the lower-left waveform pane from *_5ms.png screenshots.

Run from any directory:
    python3 crop_waveform_detail.py [root] [--dry-run]

The default root is the script's directory, including all subdirectories.
Matches are case-insensitive and include *__5ms.png. Each output is saved
beside its source as <source-stem>--波形细节.png; outputs are not cropped again.
Original screenshots are preserved, and differing existing outputs are rejected.
Requires Pillow (``python3 -m pip install Pillow``).
"""

from __future__ import annotations

import argparse
import filecmp
import os
import re
import tempfile
from pathlib import Path

from PIL import Image


SOURCE_SIZE = (1920, 1080)
LEFT, RIGHT, BOTTOM = 0, 876, 996  # Pillow crop uses exclusive right/bottom.
SOURCE_SUFFIX = re.compile(r"_5ms\.png$", re.IGNORECASE)


def lower_pane_top(image: Image.Image) -> int:
    """Locate the bottom of the gray zoom-control bar above the lower pane.

    These screenshots contain a ~25-pixel gray bar whose height varies between
    saved sessions. A long horizontal gray run distinguishes it from traces and
    grid lines. Fail instead of silently cropping the wrong area if the layout
    differs from the inspected screenshots.
    """
    rgb = image.convert("RGB")
    samples = range(20, 855, 8)
    rows = []
    for y in range(440, 590):
        gray = sum(
            70 <= r <= 125 and abs(r - g) < 10 and abs(g - b) < 10
            for r, g, b in (rgb.getpixel((x, y)) for x in samples)
        )
        if gray / len(samples) > 0.5:
            rows.append(y)

    runs = []
    for y in rows:
        if runs and y == runs[-1][-1] + 1:
            runs[-1].append(y)
        else:
            runs.append([y])
    bars = [run for run in runs if 24 <= len(run) <= 27]
    if len(bars) != 1:
        raise ValueError(f"cannot uniquely locate lower-pane toolbar: {runs}")
    return bars[0][-1] + 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path(__file__).resolve().parent,
                        help="directory to search recursively (default: script directory)")
    parser.add_argument("--dry-run", action="store_true", help="list crops without writing")
    args = parser.parse_args()

    root = args.root.expanduser().resolve()
    if not root.is_dir():
        parser.error(f"not a directory: {root}")

    sources = sorted(
        p for p in root.rglob("*") if p.is_file() and SOURCE_SUFFIX.search(p.name)
    )
    planned = created = skipped = failed = 0
    for source in sources:
        target = source.with_name(f"{source.stem}--波形细节.png")

        try:
            with Image.open(source) as image:
                if image.size != SOURCE_SIZE:
                    raise ValueError(f"expected {SOURCE_SIZE}, got {image.size}")
                top = lower_pane_top(image)
                crop = image.crop((LEFT, top, RIGHT, BOTTOM))

            if args.dry_run:
                print(f"CROP {source.relative_to(root)} -> {target.name} "
                      f"(0,{top},{RIGHT},{BOTTOM}; {crop.width}x{crop.height})")
                planned += 1
                continue

            # Write and compare a temporary PNG first. An existing differing
            # target is preserved; a matching target makes reruns harmless.
            with tempfile.NamedTemporaryFile(dir=source.parent, suffix=".png", delete=False) as tmp:
                temporary = Path(tmp.name)
            try:
                crop.save(temporary, format="PNG")
                if target.exists():
                    if not filecmp.cmp(temporary, target, shallow=False):
                        raise FileExistsError(f"existing output differs: {target}")
                    print(f"SKIP {target.relative_to(root)} (identical)")
                    skipped += 1
                else:
                    os.link(temporary, target)  # publish only if target does not exist
                    print(f"CREATED {target.relative_to(root)} ({crop.width}x{crop.height})")
                    created += 1
            finally:
                temporary.unlink(missing_ok=True)
        except (OSError, ValueError) as exc:
            print(f"ERROR {source.relative_to(root)}: {exc}")
            failed += 1

    if args.dry_run:
        print(f"Sources: {len(sources)}; planned: {planned}; errors: {failed}")
    else:
        print(f"Sources: {len(sources)}; created: {created}; identical: {skipped}; errors: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
