# -*- coding: utf-8 -*-
"""Coverage gate. Exit 0 when the transcript accounts for every PDF index
in progress.md. Exit 2 when pages are missing, a footnote is unclosed,
or a page marker was typed into a sentence.
"""
import re
import sys
from pathlib import Path


def check(progress_text, transcript_text):
    m = re.search(r"^range:\s*(\d+)\s*-\s*(\d+)\s*$", progress_text, re.M)
    if not m:
        return {"error": "progress.md needs a line: range: 1-217"}
    start, end = int(m.group(1)), int(m.group(2))
    seen = set()
    for line in transcript_text.splitlines():
        s = line.strip()
        if s.startswith("@pdf ") or s.startswith("@skip "):
            parts = s.split()
            if len(parts) > 1 and parts[1].isdigit():
                seen.add(int(parts[1]))
    missing = [i for i in range(start, end + 1) if i not in seen]
    unclosed = [
        s for s in transcript_text.splitlines()
        if "^[" in s and "]^" not in s
    ]
    glued = [
        s for s in transcript_text.splitlines()
        if "[ص" in s and not s.strip().startswith("@")
    ]
    return {
        "range": (start, end),
        "missing": missing,
        "unclosed_footnotes": unclosed,
        "glued_markers": glued,
    }


def ok(report):
    return (
        "error" not in report
        and not report["missing"]
        and not report["unclosed_footnotes"]
        and not report["glued_markers"]
    )


def main(argv):
    if len(argv) != 3:
        print("usage: gate.py progress.md transcript.txt", file=sys.stderr)
        return 1
    report = check(
        Path(argv[1]).read_text(encoding="utf-8"),
        Path(argv[2]).read_text(encoding="utf-8"),
    )
    if "error" in report:
        print(report["error"], file=sys.stderr)
        return 1
    print("MISSING", report["missing"])
    print("UNCLOSED_FOOTNOTES", len(report["unclosed_footnotes"]))
    print("GLUED_MARKERS", len(report["glued_markers"]))
    return 0 if ok(report) else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
