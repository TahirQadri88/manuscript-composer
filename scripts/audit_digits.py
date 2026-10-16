# -*- coding: utf-8 -*-
"""Crop every text-layer line that contains a digit.

The crop is what a reader looks at. The layer string is not the reading.
This is the check that caught reversed and expanded numbers.
"""
import sys
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_regions import render_zoom
from textlayer_guard import DIGIT, line_boxes


def numeric_lines(page):
    found = []
    for box in line_boxes(page):
        runs = DIGIT.findall(box["layer"])
        if not runs:
            continue
        found.append({
            "bbox": box["bbox"],
            "layer_runs": runs,
            "copy": False,
        })
    return found


def crop_numeric_lines(page, dest_dir, pdf_index):
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    crops = []
    for n, line in enumerate(numeric_lines(page), start=1):
        rect = pymupdf.Rect(line["bbox"])
        path = dest / f"p{pdf_index}_digits_{n}.png"
        zoom, _ppi = render_zoom(page)
        page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=rect, alpha=False).save(path)
        crops.append({**line, "path": str(path)})
    return crops


def main(argv):
    if len(argv) < 3:
        print("usage: audit_digits.py file.pdf pdf_index [dest]", file=sys.stderr)
        return 1
    doc = pymupdf.open(argv[1])
    index = int(argv[2])
    crops = crop_numeric_lines(doc[index - 1], argv[3] if len(argv) > 3 else "pages", index)
    print("numeric_lines", len(crops))
    for crop in crops:
        print(crop["path"], crop["layer_runs"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
