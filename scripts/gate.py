# -*- coding: utf-8 -*-
"""Coverage gate.

Exit 0 means every index in the range is claimed exactly once, no @pdf is
empty, no index is outside the PDF (when the PDF is given), no claimed page
is thin against its line-box count, and a page that ends mid-sentence is
paired with @cont. It does not mean a person compared the ink line by line.
Exit 2 when any of those mechanical checks fail.

A clause repeated inside one page is reported as REPEATED for a re-read of
the image. It does not fail the gate: a book can repeat itself.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_continuity as continuity


def uncertain_count(transcript_text):
    return transcript_text.count("{{")


def pdf_page_count(path):
    import pymupdf
    with pymupdf.open(path) as doc:
        return doc.page_count


def check(progress_text, transcript_text, line_counts=None, pdf_pages=None):
    import re
    match = re.search(r"^range:\s*(\d+)\s*-\s*(\d+)\s*$", progress_text, re.M)
    if not match:
        return {"error": "progress.md needs a line: range: 1-217"}
    start, end = int(match.group(1)), int(match.group(2))
    seen = set()
    claims = []
    for line in transcript_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("@pdf ") or stripped.startswith("@skip "):
            parts = stripped.split()
            if len(parts) > 1 and parts[1].isdigit():
                seen.add(int(parts[1]))
                claims.append(int(parts[1]))
    pages = continuity.split_pages(transcript_text)
    last = pdf_pages if pdf_pages is not None else float("inf")
    return {
        "range": (start, end),
        "missing": [i for i in range(start, end + 1) if i not in seen],
        "duplicates": sorted({i for i in claims if claims.count(i) > 1}),
        "out_of_range": sorted({i for i in claims if i < 1 or i > last}),
        "pdf_pages": pdf_pages,
        "bare": continuity.bare_pages(pages),
        "repeated": continuity.repeated_runs(pages),
        "unclosed_footnotes": [
            s for s in transcript_text.splitlines()
            if "^[" in s and "]^" not in s
        ],
        "glued_markers": [
            s for s in transcript_text.splitlines()
            if "[ص" in s and not s.strip().startswith("@")
        ],
        "unpaired": continuity.unpaired(pages),
        "thin": continuity.thin_pages(pages, line_counts or {}),
        "thin_checked": line_counts is not None,
        "uncertain": uncertain_count(transcript_text),
    }


def ok(report):
    return (
        "error" not in report
        and not report["missing"]
        and not report["duplicates"]
        and not report["out_of_range"]
        and not report["bare"]
        and not report["unclosed_footnotes"]
        and not report["glued_markers"]
        and not report["unpaired"]
        and not report["thin"]
    )


def delivery_text(report, docx_name=""):
    if "error" in report:
        return report["error"] + "\n"
    head = "CLAIMED" if ok(report) else "NATAMAM"
    lines = [
        head,
        f"range: {report['range'][0]}-{report['range'][1]}",
        f"missing: {report['missing']}",
        f"duplicates: {report['duplicates']}",
        f"out_of_range: {report['out_of_range']}",
        f"bare: {report['bare']}",
        f"thin: {report['thin']}",
        f"thin_checked: {report['thin_checked']}",
        f"unpaired: {report['unpaired']}",
        f"unclosed_footnotes: {len(report['unclosed_footnotes'])}",
        f"glued_markers: {len(report['glued_markers'])}",
        f"uncertain: {report['uncertain']}",
        f"repeated: {[r['pdf'] for r in report['repeated']]}",
    ]
    if docx_name:
        lines.append(f"docx: {docx_name}")
    if not report["thin_checked"]:
        lines.append("THIN_CHECK not run (no lines.json). A claimed page can still be half empty.")
    if report["pdf_pages"] is None:
        lines.append("PDF_CHECK not run (no book.pdf). An index the PDF does not have was not looked for.")
    for r in report["repeated"]:
        lines.append(f"REPEATED pdf {r['pdf']}: re-read the image before delivery: {r['words']}")
    lines.append(
        "Exit 0 means the ledger and the mechanical checks passed. "
        "It does not mean the ink was compared line by line."
    )
    return "\n".join(lines) + "\n"


def write_delivery(path, report, docx_name=""):
    Path(path).write_text(delivery_text(report, docx_name), encoding="utf-8")


def main(argv):
    if len(argv) not in (3, 4, 5):
        print("usage: gate.py progress.md transcript.txt [lines.json] [book.pdf]", file=sys.stderr)
        return 1
    progress = Path(argv[1]).read_text(encoding="utf-8")
    transcript = Path(argv[2]).read_text(encoding="utf-8")
    extra = [Path(a) for a in argv[3:]]
    pdfs = [a for a in extra if a.suffix.lower() == ".pdf"]
    others = [a for a in extra if a.suffix.lower() != ".pdf"]
    lines_path = others[0] if others else Path(argv[1]).parent / "lines.json"
    line_counts = None
    if lines_path.is_file():
        line_counts = json.loads(lines_path.read_text(encoding="utf-8"))
    pdf_pages = None
    if pdfs:
        if not pdfs[0].is_file():
            print(f"no such PDF: {pdfs[0]}", file=sys.stderr)
            return 1
        pdf_pages = pdf_page_count(pdfs[0])
    report = check(progress, transcript, line_counts, pdf_pages)
    if "error" in report:
        print(report["error"], file=sys.stderr)
        return 1
    dest = Path(argv[2]).parent / "delivery.md"
    docx = sorted(Path(argv[2]).parent.glob("*.docx"))
    write_delivery(dest, report, docx[0].name if docx else "")
    print("MISSING", report["missing"])
    print("DUPLICATES", report["duplicates"])
    print("OUT_OF_RANGE", report["out_of_range"], "" if pdf_pages else "(not checked: no book.pdf)")
    print("BARE", report["bare"])
    print("THIN", report["thin"])
    print("UNPAIRED", report["unpaired"])
    print("UNCLOSED_FOOTNOTES", len(report["unclosed_footnotes"]))
    print("GLUED_MARKERS", len(report["glued_markers"]))
    print("REPEATED", [r["pdf"] for r in report["repeated"]])
    print("DELIVERY", dest)
    return 0 if ok(report) else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
