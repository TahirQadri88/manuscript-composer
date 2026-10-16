# -*- coding: utf-8 -*-
"""Render one PDF page for its readers, and classify it at 72 dpi.

Two renders, kept apart:

- Classification runs on a 72 dpi pixmap, one PDF point to one pixel.
  classify()'s ink and rule thresholds and rule_bands' gap were tuned there.
- A reader's crop is rendered at the embedded scan's own pixels (or READ_DPI
  for a page with no embedded image), never past them, and capped so its long
  edge is at most VISION_CAP. A vision host resizes anything larger.

A body crop that would exceed the cap is split once, through a quiet band of
whitespace near the middle, into p{N}_body_a.png (top) and p{N}_body_b.png
(bottom). Never at the midpoint, never with an overlap. Table pages are
detected from ruled lines. A faint footnote rule is not invented.
"""
import json
import os
import statistics
import sys
from pathlib import Path

import pymupdf

# Long edge, in pixels, above which a vision host resizes the image.
# Claude's documented figure; the conservative target for every host.
# Override per host: MANUSCRIPT_VISION_CAP=2000, or --cap 2000. Claude Code's
# image viewer was measured resizing a 2480 px crop to 2000 px.
VISION_CAP = int(os.environ.get("MANUSCRIPT_VISION_CAP") or 2576)
# Used only when a page has no embedded image to take the pixels from.
READ_DPI = 300
# The split search renders at 150 dpi. At 72 dpi the gap between two lines
# of Nastaliq is under a pixel, so every row reads as inked.
SPLIT_DPI = 150


def embedded_ppi(page, min_cover=0.5):
    """Pixels per inch of the page's scan, or None when it has no scan.

    The scan is the largest image covering at least `min_cover` of the page.
    A logo or an ornament on a typeset page is not a scan: its pixels say
    nothing about the text around it, which is vector and renders at any dpi.
    Measured against the image's own box, not the page: a scan of a
    two-page spread is placed wider than the page it is shown on.
    """
    area = abs(page.rect)
    best = None
    for image in page.get_image_info():
        px = int(image.get("width") or 0)
        box = pymupdf.Rect(image.get("bbox") or (0, 0, 0, 0))
        if px <= 0 or box.width <= 0 or area <= 0:
            continue
        if abs(box & page.rect) < min_cover * area:
            continue
        ppi = px / (box.width / 72.0)
        if best is None or px > best[0]:
            best = (px, ppi)
    return best[1] if best else None


def render_zoom(page):
    """Match the embedded scan. Never render wider than that image.

    An A4 page (595 pt) whose scan is 1240 px is 150 ppi. A 1:1 render
    is 72 dpi and drops detail. Zoom is ppi / 72, so the pixmap stays at
    the embedded pixel size and no higher.
    """
    ppi = embedded_ppi(page)
    if not ppi:
        return 1.0, 72.0
    return ppi / 72.0, ppi


def page_pixmap(page):
    zoom, _ppi = render_zoom(page)
    return page.get_pixmap(
        matrix=pymupdf.Matrix(zoom, zoom), alpha=False, colorspace=pymupdf.csGRAY,
    )


def classify_pixmap(page):
    """72 dpi greyscale: the resolution classify() was tuned on."""
    return page.get_pixmap(matrix=pymupdf.Matrix(1, 1), alpha=False, colorspace=pymupdf.csGRAY)


def native_zoom(page):
    """The reader's zoom before the cap: the scan's pixels, or READ_DPI."""
    ppi = embedded_ppi(page)
    return (ppi or READ_DPI) / 72.0


def capped_zoom(zoom, clip, cap=None):
    cap = VISION_CAP if cap is None else cap
    edge = max(clip.width, clip.height)
    if edge <= 0:
        return zoom
    # MuPDF rounds a clip outward to whole pixels: keep 2 px of headroom.
    return min(zoom, (cap - 2) / edge)


def needs_split(clip, zoom, cap=None):
    """True when the crop's long edge at full resolution exceeds the cap."""
    cap = VISION_CAP if cap is None else cap
    return max(clip.width, clip.height) * zoom > cap


def row_ink(pix, threshold=160, step=3):
    """Dark pixels per row, sampling every `step`-th pixel."""
    w, h = pix.width, pix.height
    buf = pix.samples
    return [
        sum(1 for x in range(0, w, step) if buf[y * w + x] < threshold)
        for y in range(h)
    ]


def quiet_cut(ink, lo=0.30, hi=0.70, min_run=2):
    """Row to cut at, or None. The middle of the longest quiet run.

    The floor is the band's minimum, not zero: a printed frame down both
    margins inks every row. A fraction of the median alone falls below that
    floor and nothing qualifies; an absolute zero never matches at 72 dpi.
    A band inked evenly from edge to edge (a solid block) has no gap to
    find: every row would be "quiet", and its centre is only the midpoint.
    A band with no ink at all is all gap, and its centre is a safe cut. Inside the chosen run the cut moves to the floor-level row
    nearest the run's centre, so a stray dot in the run is not where it lands.
    """
    h = len(ink)
    a, b = int(h * lo), int(h * hi)
    band = ink[a:b]
    if not band:
        return None
    floor = min(band)
    if max(band) == floor and floor > 0:
        return None
    typical = statistics.median(band)
    quiet = floor + max(1, 0.15 * (typical - floor))
    runs = []
    start = None
    for i, value in enumerate(band + [None]):
        if value is not None and value <= quiet:
            if start is None:
                start = i
        elif start is not None:
            runs.append((start, i))
            start = None
    runs = [r for r in runs if r[1] - r[0] >= min_run]
    if not runs:
        return None
    middle = len(band) / 2
    s, e = max(runs, key=lambda r: (r[1] - r[0], -abs((r[0] + r[1]) / 2 - middle)))
    centre = (s + e) // 2
    lowest = min(band[s:e])
    row = min((i for i in range(s, e) if band[i] == lowest), key=lambda i: abs(i - centre))
    return a + row


def ink_rows(page, clip, dpi=SPLIT_DPI):
    scale = dpi / 72.0
    pix = page.get_pixmap(
        matrix=pymupdf.Matrix(scale, scale), clip=clip,
        alpha=False, colorspace=pymupdf.csGRAY,
    )
    return pix, row_ink(pix), scale


def ink_extent(page, clip, margin=6, footer_gap=40, footer_max=30, footer_zone=0.12):
    """(body_bottom, footer) in PDF y for `clip`.

    body_bottom is just below the last line of the book's text, so the white
    under a page that ends high is neither sent nor split through. footer is
    (top, bottom) of an isolated block at the foot of the page (a page number,
    an uploader's watermark) set apart by a wide gap, or None. It is cut out
    of the body, not thrown away. The floor is the clip's emptiest row, so a
    printed frame down both margins is not counted as text.
    """
    _pix, ink, scale = ink_rows(page, clip)
    if not ink:
        return clip.y1, None
    floor = min(ink)
    inked = [y for y, value in enumerate(ink) if value > floor + 1]
    if not inked:
        return clip.y1, None
    blocks = _bands(inked, gap=int(footer_gap * scale))
    to_y = lambda row: clip.y0 + row / scale
    last = blocks[-1]
    zone = page.rect.y1 - page.rect.height * footer_zone
    footer = None
    if (
        len(blocks) > 1
        and to_y(last[0]) >= zone
        and (last[1] - last[0]) / scale <= footer_max
    ):
        footer = (round(max(clip.y0, to_y(last[0]) - margin), 1), round(min(clip.y1, to_y(last[1] + 1) + margin), 1))
        last = blocks[-2]
    bottom = min(clip.y1, to_y(last[1] + 1) + margin)
    if footer is not None:
        bottom = min(bottom, footer[0])
    return round(bottom, 1), footer


def header_rule(page, top=0.22, min_frac=0.6, max_line=40):
    """PDF y just below a running-header rule, or None.

    Measured at 150 dpi: at 72 dpi a hairline renders lighter than the rule
    threshold. The rule must lie in the top `top` of the page, span most of
    the ink's width, and have at most one line of text above it, so a
    heading or a table's top rule is not taken for the running header.
    """
    rect = page.rect
    clip = pymupdf.Rect(rect.x0, rect.y0, rect.x1, rect.y0 + rect.height * top)
    pix, _ink, scale = ink_rows(page, clip)
    w, h = pix.width, pix.height
    buf = pix.samples
    cols = [x for x in range(0, w, 2) if any(buf[y * w + x] < 160 for y in range(0, h, 2))]
    if not cols:
        return None
    span = max(1, cols[-1] - cols[0])
    rows = [
        y for y in range(h)
        if sum(1 for x in range(cols[0], cols[-1] + 1, 2) if buf[y * w + x] < 160) * 2 >= min_frac * span
    ]
    # A double rule (thin over thick) is one band.
    bands = _bands(rows, gap=int(4 * scale))
    if not bands:
        return None
    start, end = bands[0]
    above = [y for y in range(start) if any(buf[y * w + x] < 160 for x in range(0, w, 3))]
    if not above or (start - above[0]) / scale > max_line:
        return None
    return round((end + 1) / scale + 2, 1)


def split_point(page, clip):
    """PDF y of a whitespace cut through `clip`, and the 150 dpi evidence."""
    _pix, ink, scale = ink_rows(page, clip)
    row = quiet_cut(ink)
    floor = min(ink) if ink else 0
    # Each half must carry text. A blank page is not split into two blanks.
    if row is not None and not (
        any(v > floor + 1 for v in ink[:row]) and any(v > floor + 1 for v in ink[row:])
    ):
        row = None
    if row is None:
        return None, ink, None
    return clip.y0 + (row + 0.5) / scale, ink, row


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
    _zoom, ppi = render_zoom(page)
    cpix = classify_pixmap(page)
    info = classify(cpix)
    info["ppi"] = round(ppi, 1) if embedded_ppi(page) else None
    h = cpix.height
    rules = rule_bands(cpix)
    # cpix is 72 dpi, so these rows are PDF points.
    header_y = rules[0][1] + 2 if rules and rules[0][0] < h * 0.14 else int(h * 0.09)
    rect = page.rect
    if info["kind"] != "table":
        ruled = header_rule(page)
        if ruled is not None:
            header_y = ruled
    info["header_y"] = header_y
    full_zoom = native_zoom(page)
    info["regions"] = {}
    info["dpi"] = {}

    def clip_save(name, y0, y1):
        if y1 - y0 < 8:
            return
        clip = pymupdf.Rect(rect.x0, rect.y0 + y0, rect.x1, rect.y0 + y1)
        zoom = capped_zoom(full_zoom, clip)
        path = dest / f"p{pdf_index}_{name}.png"
        page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=clip, alpha=False).save(path)
        info["regions"][name] = str(path)
        info["dpi"][name] = round(zoom * 72)

    clip_save("header", 0, header_y)
    body = pymupdf.Rect(rect.x0, rect.y0 + header_y, rect.x1, rect.y1)
    if info["kind"] == "table":
        clip_save("grid", header_y, rect.height)
        body = None
    else:
        # White below the last line is not sent, and is not split through.
        body.y1, footer = ink_extent(page, body)
        bottom = body.y1 - rect.y0
        info["body_bottom"] = round(bottom, 1)
        if footer is not None:
            clip_save("footer", footer[0] - rect.y0, footer[1] - rect.y0)
    if body is None:
        pass
    elif needs_split(body, full_zoom):
        cut, _ink, row = split_point(page, body)
        if cut is None:
            info["split"] = "none: no quiet band"
            clip_save("body", header_y, bottom)
        else:
            y = cut - rect.y0
            info["split"] = {"top": header_y, "y": round(y, 1), "row": row, "dpi": SPLIT_DPI}
            clip_save("body_a", header_y, y)
            clip_save("body_b", y, bottom)
    else:
        clip_save("body", header_y, bottom)
    # full page, for the verifier's second look. Capped, never upscaled.
    clip_save("full", 0, rect.height)
    return info


def layout_record(info, pdf_index):
    """One line of layout.jsonl. `body` is a path, or [top, bottom]."""
    regions = info["regions"]
    record = {"pdf": pdf_index, "kind": info["kind"]}
    if "header" in regions:
        record["header"] = regions["header"]
    if "grid" in regions:
        record["grid"] = regions["grid"]
    elif "body_a" in regions:
        record["body"] = [regions["body_a"], regions["body_b"]]
    elif "body" in regions:
        record["body"] = regions["body"]
    if "footer" in regions:
        record["footer"] = regions["footer"]
    record["full"] = regions["full"]
    return record


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
    global VISION_CAP
    argv = list(argv)
    if "--cap" in argv:
        at = argv.index("--cap")
        VISION_CAP = int(argv[at + 1])
        del argv[at:at + 2]
    if len(argv) < 2:
        print("usage: render_regions.py file.pdf [pdf_index] [dest] [layout.jsonl] [--cap PX]", file=sys.stderr)
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
        print(name, path, f"{info['dpi'][name]}dpi")
    if "split" in info:
        print("split", info["split"])
    record = json.dumps(layout_record(info, index), ensure_ascii=False)
    print("layout", record)
    if len(argv) > 4:
        with open(argv[4], "a", encoding="utf-8") as handle:
            handle.write(record + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
