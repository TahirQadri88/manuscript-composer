# -*- coding: utf-8 -*-
"""Render one PDF page at its own pixel size and classify the layout.

Does not upscale. A scanned page whose image is already ~800 px wide stays
that size. Table pages are detected from ruled lines. A faint footnote rule
on a low-resolution scan is not invented: the footnote agent reads the body
crop and lifts a note only when it can see one.
"""
import sys
from pathlib import Path

import pymupdf


def page_pixmap(page):
    # 72 dpi: one PDF point is one pixel. These scans are stored at page size.
    return page.get_pixmap(matrix=pymupdf.Matrix(1, 1), alpha=False, colorspace=pymupdf.csGRAY)


def _bands(rows, gap=3):
    if not rows:
        return []
    bands = [[rows[0], rows[0]]]
    for y in rows[1:]:
        if y - bands[-1][1] <= gap:
            bands[-1][1] = y
        else:
            bands.append([y, y])
    return bands


def content_box(pix, threshold=160, min_hits=8):
    """Left and right of the ink, ignoring a blank margin."""
    w, h = pix.width, pix.height
    buf = pix.samples
    xs = []
    for x in range(0, w, 4):
        hits = sum(1 for y in range(0, h, 3) if buf[y * w + x] < threshold)
        if hits >= min_hits:
            xs.append(x)
    if not xs:
        return 0, w
    return max(0, xs[0] - 4), min(w, xs[-1] + 4)


def rule_bands(pix, threshold=80, min_frac=0.72):
    """Horizontal rules measured inside the text block, not the white margin."""
    w, h = pix.width, pix.height
    buf = pix.samples
    x0, x1 = content_box(pix)
    span = max(1, x1 - x0)
    rows = []
    for y in range(h):
        dark = sum(1 for x in range(x0, x1) if buf[y * w + x] < threshold)
        if dark / span >= min_frac:
            rows.append(y)
    return [b for b in _bands(rows) if 6 < b[0] < h - 6]


def classify(pix):
    """cover | blank | table | prose. Ruled lines only. No model."""
    w, h = pix.width, pix.height
    ink = sum(1 for b in pix.samples if b < 200) / max(1, len(pix.samples))
    rules = rule_bands(pix)
    if ink < 0.015:
        kind = "blank"
    elif len(rules) >= 6:
        kind = "table"
    elif ink > 0.25 and len(rules) < 2:
        kind = "cover"
    else:
        kind = "prose"
    return {
        "kind": kind,
        "ink": round(ink, 4),
        "rules": len(rules),
        "width": w,
        "height": h,
    }


def save_regions(page, dest_dir, pdf_index):
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    pix = page_pixmap(page)
    info = classify(pix)
    h = pix.height
    rules = rule_bands(pix)
    header_y = rules[0][1] + 2 if rules and rules[0][0] < h * 0.14 else int(h * 0.09)
    rect = page.rect
    scale = h / rect.height

    def clip_save(name, y0, y1):
        if y1 - y0 < 8:
            return
        clip = pymupdf.Rect(0, y0 / scale, rect.width, y1 / scale)
        path = dest / f"p{pdf_index}_{name}.png"
        page.get_pixmap(matrix=pymupdf.Matrix(1, 1), clip=clip, alpha=False).save(path)
        info.setdefault("regions", {})[name] = str(path)

    clip_save("header", 0, header_y)
    body_name = "grid" if info["kind"] == "table" else "body"
    clip_save(body_name, header_y, h)
    # native full page, for the verifier's second look. Not upscaled.
    full = dest / f"p{pdf_index}_full.png"
    pix.save(full)
    info.setdefault("regions", {})["full"] = str(full)
    return info


def inspect(pdf_path):
    doc = pymupdf.open(pdf_path)
    rows = []
    for i, page in enumerate(doc):
        rows.append({
            "pdf": i + 1,
            "text_chars": len(page.get_text("text").strip()),
            "rect": tuple(round(v, 1) for v in page.rect),
        })
    return doc.page_count, rows


def main(argv):
    if len(argv) < 2:
        print("usage: render_regions.py file.pdf [pdf_index] [dest]", file=sys.stderr)
        return 1
    if len(argv) == 2:
        n, rows = inspect(argv[1])
        print("pages", n)
        for row in rows[:8]:
            print(row)
        return 0
    doc = pymupdf.open(argv[1])
    index = int(argv[2])
    info = save_regions(doc[index - 1], argv[3] if len(argv) > 3 else "pages", index)
    print(info["kind"], "rules", info["rules"], "ink", info["ink"])
    for name, path in info["regions"].items():
        print(name, path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
