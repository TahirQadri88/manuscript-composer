# -*- coding: utf-8 -*-
"""Page-boundary checks the gate enforces.

A page that ends mid-sentence must be followed, on the next PDF index,
by @cont. A claimed page whose transcript is far shorter than the
line-box count of that page is THIN: the index was claimed, the page
was not finished.
"""
import re
import statistics

ENDERS = "۔.!?؟؛:…"
STRUCTURAL = (
    "@row", "@heading", "@title", "@subtitle", "@center", "@basmala",
    "@verse", "@quote", "@ornament", "@publisher", "@newpage",
)
FOOTNOTE = re.compile(r"\^\[[\s\S]*?\]\^")
UNCERTAIN = re.compile(r"\{\{.*?\}\}")


def _prose(line):
    if line.startswith("@cont"):
        return line.split(None, 1)[1] if " " in line else ""
    if line.startswith("@"):
        return None
    return line


def _closed(text):
    body = FOOTNOTE.sub("", text).strip()
    if not body or UNCERTAIN.fullmatch(body):
        return True
    return body.endswith(tuple(ENDERS))


def needs_cont(lines):
    last = None
    for line in lines:
        if line.startswith(STRUCTURAL):
            last = None
            continue
        prose = _prose(line)
        if prose is None:
            continue
        last = prose
    return last is not None and not _closed(last)


def starts_with_cont(lines):
    for line in lines:
        if line.startswith(("@page", "@lang", "@sheet", "@pdf")):
            continue
        return line.startswith("@cont")
    return False


def split_pages(transcript):
    pages = []
    current = None
    for raw in transcript.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("@pdf ") or line.startswith("@skip "):
            parts = line.split()
            if len(parts) < 2 or not parts[1].isdigit():
                continue
            current = {
                "pdf": int(parts[1]),
                "kind": "skip" if line.startswith("@skip") else "read",
                "lines": [],
            }
            pages.append(current)
            continue
        if current is not None and current["kind"] == "read":
            current["lines"].append(line)
    return pages


def unpaired(pages):
    fails = []
    reads = [p for p in pages if p["kind"] == "read"]
    for left, right in zip(reads, reads[1:]):
        if right["pdf"] != left["pdf"] + 1:
            continue
        if needs_cont(left["lines"]) and not starts_with_cont(right["lines"]):
            fails.append({"from": left["pdf"], "to": right["pdf"]})
    return fails


def body_chars(lines):
    total = 0
    for line in lines:
        prose = _prose(line)
        if prose is None:
            continue
        body = FOOTNOTE.sub("", prose)
        body = UNCERTAIN.sub("", body)
        total += len(body.strip())
    return total


def thin_pages(pages, line_counts, floor=0.6):
    """chars per source line, against the median of the pages being checked.

    line_counts come from line boxes, not from copying the layer's glyphs.
    Pages with fewer than 8 source lines are covers, titles, or blanks.
    """
    if not line_counts:
        return []
    ratios = {}
    for page in pages:
        if page["kind"] != "read":
            continue
        raw = line_counts.get(page["pdf"], line_counts.get(str(page["pdf"])))
        if not raw or int(raw) < 8:
            continue
        ratios[page["pdf"]] = body_chars(page["lines"]) / int(raw)
    if len(ratios) < 3:
        return []
    median = statistics.median(ratios.values())
    if median <= 0:
        return []
    return sorted(pdf for pdf, ratio in ratios.items() if ratio < floor * median)


# Lines that carry no text of the page.
LEDGER = ("@page", "@lang", "@sheet")
MARKUP = re.compile(r"\|\|\||\^\[|\]\^|\{\{|\}\}|\||\*\*|\[\[|\]\]")
PUNCT = "۔،؛؟.,!?:;\"'“”«»()[]{}<>"


def bare_pages(pages):
    """@pdf with nothing under it: a page claimed and not delivered."""
    return [
        p["pdf"] for p in pages
        if p["kind"] == "read"
        and not [line for line in p["lines"] if not line.startswith(LEDGER)]
    ]


def page_words(lines):
    words = []
    for line in lines:
        if line.startswith(LEDGER):
            continue
        if line.startswith("@"):
            line = line.split(None, 1)[1] if " " in line else ""
        for token in MARKUP.sub(" ", line).split():
            token = token.strip(PUNCT)
            if token:
                words.append(token)
    return words


def repeated_runs(pages, n=8):
    """A run of n or more words that appears twice inside one @pdf block.

    Flag for re-read only. A book can repeat itself; a reader that read
    one passage twice looks the same in the text, and only the image can
    tell them apart.
    """
    found = []
    for page in pages:
        if page["kind"] != "read":
            continue
        words = page_words(page["lines"])
        first = {}
        for i in range(len(words) - n + 1):
            gram = tuple(words[i:i + n])
            if gram not in first:
                first[gram] = i
            elif i - first[gram] >= n:
                found.append({"pdf": page["pdf"], "words": " ".join(gram)})
                break
    return found
