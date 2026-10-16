# -*- coding: utf-8 -*-
"""Text-layer policy.

Boxes are evidence. Glyphs are not, once the page is Arabic or Urdu.

A real scan stored ۲۰۲۲ in the layer as 20022. Reversing 20022 does not
produce ۲۰۲۲, so reversal is a detector, not a repair. Line boxes are safe
to count and to crop. The characters inside them are not safe to copy.
"""
import json
import re
import sys
from pathlib import Path

import pymupdf

ARABIC = re.compile(r"[\u0600-\u06FF]")
DIGIT = re.compile(r"[0-9۰-۹٠-٩]{2,}")
TO_LATIN = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def latin_digits(text):
    return str(text).translate(TO_LATIN)


def assess_layer_digits(layer_run, printed):
    """Never copy a digit run out of the text layer.

    reversed is true only when the layer run is the printed run backwards.
    20022 against ۲۰۲۲ is not that case: the layer is simply wrong.
    """
    layer = latin_digits(layer_run)
    page = latin_digits(printed)
    return {
        "copy": False,
        "reversed": bool(page) and layer == page[::-1] and layer != page,
        "same": bool(page) and layer == page,
        "layer": str(layer_run),
        "printed": str(printed),
    }


def glyphs_unusable(text):
    """Urdu/Arabic in a text layer is visual order. Digits are not evidence."""
    return bool(ARABIC.search(text or "") or re.search(r"\d", text or ""))


def line_boxes(page):
    """One box per visual line. The text is kept only so a crop can be named."""
    boxes = []
    data = page.get_text("dict")
    for block in data.get("blocks", []):
        for line in block.get("lines") or []:
            text = "".join(span.get("text", "") for span in line.get("spans") or [])
            boxes.append({"bbox": tuple(line["bbox"]), "layer": text, "copy": False})
    return boxes


def line_count(page):
    return len(line_boxes(page))


def line_counts(pdf_path):
    doc = pymupdf.open(pdf_path)
    return {str(i + 1): line_count(page) for i, page in enumerate(doc)}


def main(argv):
    if len(argv) != 3:
        print("usage: textlayer_guard.py file.pdf lines.json", file=sys.stderr)
        return 1
    counts = line_counts(argv[1])
    Path(argv[2]).write_text(json.dumps(counts, ensure_ascii=False, indent=2), encoding="utf-8")
    print("pages", len(counts))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
