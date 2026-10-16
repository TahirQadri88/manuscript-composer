# -*- coding: utf-8 -*-
"""Write range: and pdf_pages: in progress.md from the PDF itself.

The gate trusts range: completely. A hand-typed 1-200 on a 217-page book
lets an unfinished book pass, so both numbers come from doc.page_count.
Other lines already in progress.md (header_once, skipped, ...) are kept.
"""
import re
import sys
from pathlib import Path

import pymupdf


def progress_text(existing, page_count, start=None, end=None):
    start = 1 if start is None else start
    end = page_count if end is None else end
    if not 1 <= start <= end <= page_count:
        raise ValueError(f"range {start}-{end} is outside the PDF's 1-{page_count}")
    kept = [
        line for line in existing.splitlines()
        if not re.match(r"^(range|pdf_pages):", line)
    ]
    head = [f"range: {start}-{end}", f"pdf_pages: {page_count}"]
    if not kept:
        kept = ["header_once:", "skipped:"]
    return "\n".join(head + kept) + "\n"


def main(argv):
    if len(argv) not in (3, 4):
        print("usage: init_progress.py book.pdf progress.md [A-B]", file=sys.stderr)
        return 1
    with pymupdf.open(argv[1]) as doc:
        count = doc.page_count
    start = end = None
    if len(argv) == 4:
        match = re.fullmatch(r"(\d+)-(\d+)", argv[3])
        if not match:
            print("range must look like 12-26", file=sys.stderr)
            return 1
        start, end = int(match.group(1)), int(match.group(2))
    path = Path(argv[2])
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    try:
        text = progress_text(existing, count, start, end)
    except ValueError as err:
        print(err, file=sys.stderr)
        return 1
    path.write_text(text, encoding="utf-8")
    print(text.splitlines()[0], "pdf_pages", count)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
