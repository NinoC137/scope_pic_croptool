#!/usr/bin/env python3
"""递归裁剪 *--波形细节.png，保留图片顶部指定毫米数的区域。

用法（需要 Pillow）：
    python3 crop_waveform_top_mm.py
    python3 crop_waveform_top_mm.py --height-mm 35
    python3 crop_waveform_top_mm.py "/目标文件夹" --height-mm 33 --original-height-mm 68
    python3 crop_waveform_top_mm.py --dry-run

按原图高度约 68 mm 换算：保留像素高度 = 原图像素高度 * 保留毫米数 / 原图毫米高度。
每张图片单独计算并取最近整数，不依赖 DPI，也不缩放图片。
这里的毫米数用于定义裁剪比例，不声明图片实际打印尺寸。
输出在原图旁，文件名为“原文件名--顶部裁剪.png”。重复运行更新该输出。
"""

from __future__ import annotations

import argparse
import math
import os
import tempfile
from pathlib import Path

from PIL import Image


# 手动矫正时主要修改这里；命令行参数可以覆盖这两个默认值。
KEEP_HEIGHT_MM = 33.0  # 从图片最上方往下保留的高度，单位：mm。
ORIGINAL_HEIGHT_MM = 68.0  # 原图对应的完整高度，单位：mm；默认保留 33/68。

SOURCE_SUFFIX = "--波形细节.png"
OUTPUT_SUFFIX = "--顶部裁剪.png"


def positive_number(value: str | float) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be a finite number greater than zero")
    return number


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path,
                        default=Path(__file__).resolve().parent,
                        help="递归查找目录，默认是脚本所在目录")
    parser.add_argument("--height-mm", type=positive_number, default=KEEP_HEIGHT_MM,
                        help=f"从顶部保留的高度，单位 mm（默认 {KEEP_HEIGHT_MM:g}）")
    parser.add_argument("--original-height-mm", type=positive_number, default=ORIGINAL_HEIGHT_MM,
                        help=f"原图对应的完整高度，单位 mm（默认 {ORIGINAL_HEIGHT_MM:g}）")
    parser.add_argument("--dry-run", action="store_true", help="仅检查和列出裁剪范围，不写图片")
    args = parser.parse_args()

    root = args.root.expanduser().resolve()
    if not root.is_dir():
        parser.error(f"not a directory: {root}")
    try:
        height_mm = positive_number(args.height_mm)
        original_height_mm = positive_number(args.original_height_mm)
    except (ValueError, argparse.ArgumentTypeError) as exc:
        parser.error(str(exc))
    ratio = height_mm / original_height_mm
    if not math.isfinite(ratio) or ratio <= 0:
        parser.error("height-mm / original-height-mm must be finite and greater than zero")
    print(f"Height: {height_mm:g} / {original_height_mm:g} mm; keep: {min(ratio, 1):.2%}")

    sources = sorted(p for p in root.rglob("*")
                     if p.is_file() and p.name.lower().endswith(SOURCE_SUFFIX))
    written = planned = failed = 0
    for source in sources:
        target = source.with_name(f"{source.stem}{OUTPUT_SUFFIX}")
        temporary = None
        try:
            with Image.open(source) as image:
                height = max(1, math.floor(image.height * min(ratio, 1) + 0.5))
                crop = image.crop((0, 0, image.width, height))
                icc_profile = image.info.get("icc_profile")
                limited = " (保留高度超过原图，保留整张图)" if ratio > 1 else ""
            description = f"{source.relative_to(root)} -> {target.name} ({crop.width}x{crop.height}){limited}"
            if args.dry_run:
                print(f"PLAN {description}")
                planned += 1
                continue

            # 先完整写入临时文件再替换派生结果，原图始终不变。
            with tempfile.NamedTemporaryFile(dir=source.parent, suffix=".png", delete=False) as tmp:
                temporary = Path(tmp.name)
            crop.save(temporary, format="PNG", icc_profile=icc_profile)
            os.replace(temporary, target)
            written += 1
            print(f"SAVED {description}")
        except (OSError, ValueError) as exc:
            print(f"ERROR {source.relative_to(root)}: {exc}")
            failed += 1
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    count = f"planned: {planned}" if args.dry_run else f"written: {written}"
    print(f"Sources: {len(sources)}; {count}; errors: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
