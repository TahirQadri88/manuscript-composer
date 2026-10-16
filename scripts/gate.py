# -*- coding: utf-8 -*-
"""Coverage gate.

Exit 0 means every index in the range is claimed, no claimed page is thin
against its line-box count, and a page that ends mid-sentence is paired
with @cont. It does not mean a person compared the ink line by line.
Exit 2 when any of those mechanical checks fail.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_continuity as continuity


def uncertain_count(transcript_text):
    return transcript_text.count("{{")


def check(progress_text, transcript_text, line_counts=None):
    import re
    match = re.search(r"^range:\s*(\d+)\s*-\s*(\d+)\s*$", progress_text, re.M)
    if not match:
        return {"error": "progress.md needs a line: range: 1-217"}
    start, end = int(match.group(1)), int(match.group(2))
    seen = set()
    for line in transcript_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("@pdf ") or stripped.startswith("@skip "):
            parts = stripped.split()
            if len(parts) > 1 and parts[1].isdigit():
                seen.add(int(parts[1]))
    pages = continuity.split_pages(transcript_text)
    return {
        "range": (start, end),
        "missing": [i for i in range(start, end + 1) if i not in seen],
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
        f"thin: {report['thin']}",
        f"thin_checked: {report['thin_checked']}",
        f"unpaired: {report['unpaired']}",
        f"unclosed_footnotes: {len(report['unclosed_footnotes'])}",
        f"glued_markers: {len(report['glued_markers'])}",
        f"uncertain: {report['uncertain']}",
    ]
    if docx_name:
        lines.append(f"docx: {docx_name}")
    if not report["thin_checked"]:
        lines.append("THIN_CHECK not run (no lines.json). A claimed page can still be half empty.")
    lines.append(
        "Exit 0 means the ledger and the mechanical checks passed. "
        "It does not mean the ink was compared line by line."
    )
    return "\n".join(lines) + "\n"


def write_delivery(path, report, docx_name=""):
    Path(path).write_text(delivery_text(report, docx_name), encoding="utf-8")


def main(argv):
    if len(argv) not in (3, 4):
        print("usage: gate.py progress.md transcript.txt [lines.json]", file=sys.stderr)
        return 1
    progress = Path(argv[1]).read_text(encoding="utf-8")
    transcript = Path(argv[2]).read_text(encoding="utf-8")
    lines_path = Path(argv[3]) if len(argv) == 4 else Path(argv[1]).parent / "lines.json"
    line_counts = None
    if lines_path.is_file():
        line_counts = json.loads(lines_path.read_text(encoding="utf-8"))
    report = check(progress, transcript, line_counts)
    if "error" in report:
        print(report["error"], file=sys.stderr)
        return 1
    dest = Path(argv[2]).parent / "delivery.md"
    docx = sorted(Path(argv[2]).parent.glob("*.docx"))
    write_delivery(dest, report, docx[0].name if docx else "")
    print("MISSING", report["missing"])
    print("THIN", report["thin"])
    print("UNPAIRED", report["unpaired"])
    print("UNCLOSED_FOOTNOTES", len(report["unclosed_footnotes"]))
    print("GLUED_MARKERS", len(report["glued_markers"]))
    print("DELIVERY", dest)
    return 0 if ok(report) else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
