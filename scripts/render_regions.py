# -*- coding: utf-8 -*-
"""Render one PDF page at the embedded scan's pixel size and classify it.

Zoom is embedded_ppi / 72, and never past the embedded image. A 1:1 render
of a 150 ppi scan is 72 dpi and drops detail. Table pages are detected from
ruled lines. A faint footnote rule is not invented.
"""
import sys
from pathlib import Path

import pymupdf


def render_zoom(page):
    """Match the embedded scan. Never render wider than that image.

    An A4 page (595 pt) whose scan is 1240 px is 150 ppi. A 1:1 render
    is 72 dpi and drops detail. Zoom is px / page_width, so the pixmap
    stays at the embedded pixel size and no higher.
    """
    width = page.rect.width
    pixels = 0
    for image in page.get_image_info():
        pixels = max(pixels, int(image.get("width") or 0))
    if pixels <= 0 or width <= 0:
        return 1.0, 72.0
    zoom = pixels / width
    ppi = pixels / (width / 72.0)
    return zoom, ppi


def page_pixmap(page):
    zoom, _ppi = render_zoom(page)
    return page.get_pixmap(
        matrix=pymupdf.Matrix(zoom, zoom), alpha=False, colorspace=pymupdf.csGRAY,
    )


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
    zoom, ppi = render_zoom(page)
    pix = page_pixmap(page)
    info = classify(pix)
    info["ppi"] = round(ppi, 1)
    info["zoom"] = round(zoom, 3)
    h = pix.height
    rules = rule_bands(pix)
    header_y = rules[0][1] + 2 if rules and rules[0][0] < h * 0.14 else int(h * 0.09)
    rect = page.rect
    matrix = pymupdf.Matrix(zoom, zoom)

    def clip_save(name, y0, y1):
        if y1 - y0 < 8:
            return
        clip = pymupdf.Rect(0, y0 / zoom, rect.width, y1 / zoom)
        path = dest / f"p{pdf_index}_{name}.png"
        page.get_pixmap(matrix=matrix, clip=clip, alpha=False).save(path)
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
    print(info["kind"], "rules", info["rules"], "ink", info["ink"], "ppi", info["ppi"])
    for name, path in info["regions"].items():
        print(name, path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
