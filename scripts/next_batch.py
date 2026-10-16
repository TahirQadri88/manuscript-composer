# -*- coding: utf-8 -*-
"""Where the book stands, and the next batch for a fresh chat.

A free chat cannot hold a whole book. Each new chat runs this first, reads
work/next_batch.md, does that batch, appends to transcript.txt and stops.
Nothing here reads ink or calls a model: it counts the ledger.

    python3 scripts/next_batch.py work            # 15 pages
    python3 scripts/next_batch.py work --size 8   # handwriting
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_continuity as continuity
import gate


def plan(progress_text, transcript_text, size=15):
    """The ledger's state and the next unclaimed PDF indexes, in order."""
    report = gate.check(progress_text, transcript_text)
    if "error" in report:
        return report
    import re
    count = re.search(r"^pdf_pages:\s*(\d+)", progress_text, re.M)
    start, end = report["range"]
    pages = continuity.split_pages(transcript_text)
    by_pdf = {p["pdf"]: p for p in pages}
    batch = report["missing"][:size]
    cont_from = None
    if batch:
        before = by_pdf.get(batch[0] - 1)
        if before and before["kind"] == "read" and continuity.needs_cont(before["lines"]):
            cont_from = before["pdf"]
    return {
        "range": (start, end),
        "pdf_pages": int(count.group(1)) if count else end,
        "claimed": (end - start + 1) - len(report["missing"]),
        "total": end - start + 1,
        "batch": batch,
        "cont_from": cont_from,
        # Fix these before reading on. They are pages already claimed.
        "redo": {
            "duplicates": report["duplicates"],
            "bare": report["bare"],
            "unpaired": report["unpaired"],
            "repeated": [r["pdf"] for r in report["repeated"]],
        },
    }


def handoff(state, work="work", cap=None):
    """The text a fresh chat follows. Commands, then the one rule that carries over."""
    if "error" in state:
        return state["error"] + "\n"
    start, end = state["range"]
    lines = [
        "# Next batch",
        "",
        f"Range {start}-{end}: {state['claimed']} of {state['total']} PDF pages claimed.",
        "",
    ]
    redo = {k: v for k, v in state["redo"].items() if v}
    if redo:
        lines += ["## Fix first", ""]
        for name, value in redo.items():
            lines.append(f"- {name}: {value}")
        lines += [
            "",
            "Duplicates: keep the copy that matches the image, delete the other.",
            "Bare: the @pdf has no text under it. Read that page now.",
            "Unpaired: the next page must start with @cont.",
            "Repeated: re-read the image. If the book prints it twice, change nothing and add `# repeat-checked` under that @pdf.",
            "",
        ]
    if not state["batch"]:
        lines += [
            "## Done reading",
            "",
            "Every index is claimed. Build the single file and run the gate:",
            "",
            "```bash",
            f"python3 composer/composer.py {work}/transcript.txt {work}/Final_Book_pdf{start}-{end}_of_{state['pdf_pages']}.docx",
            f"python3 scripts/gate.py {work}/progress.md {work}/transcript.txt {work}/lines.json {work}/book.pdf",
            "```",
        ]
        return "\n".join(lines) + "\n"
    batch = state["batch"]
    flag = f" --cap {cap}" if cap else ""
    lines += [
        f"## Read PDF {batch[0]}-{batch[-1]}" if batch == list(range(batch[0], batch[-1] + 1))
        else f"## Read PDF {', '.join(map(str, batch))}",
        "",
        "```bash",
    ]
    lines += [
        f"python3 scripts/render_regions.py {work}/book.pdf {i} {work}/pages {work}/layout.jsonl{flag}"
        for i in batch
    ]
    lines += ["```", ""]
    if state["cont_from"]:
        lines += [
            f"PDF {state['cont_from']} ends mid-sentence. "
            f"The first text line of PDF {batch[0]} is `@cont`.",
            "",
        ]
    lines += [
        "Follow SKILL.md role by role. Append to transcript.txt; do not rewrite earlier pages.",
        "When the batch is written, run this script again and stop. The next chat continues.",
    ]
    return "\n".join(lines) + "\n"


def main(argv):
    args = list(argv[1:])
    size, cap = 15, None
    for flag in ("--size", "--cap"):
        if flag in args:
            at = args.index(flag)
            value = int(args[at + 1])
            del args[at:at + 2]
            if flag == "--size":
                size = value
            else:
                cap = value
    if len(args) != 1:
        print("usage: next_batch.py work_dir [--size 15] [--cap 2000]", file=sys.stderr)
        return 1
    work = Path(args[0])
    progress = work / "progress.md"
    if not progress.is_file():
        print(f"no {progress}: run scripts/init_progress.py {work}/book.pdf {progress} first", file=sys.stderr)
        return 1
    transcript = work / "transcript.txt"
    state = plan(
        progress.read_text(encoding="utf-8"),
        transcript.read_text(encoding="utf-8") if transcript.is_file() else "",
        size,
    )
    text = handoff(state, str(work), cap)
    (work / "next_batch.md").write_text(text, encoding="utf-8")
    print(text, end="")
    return 1 if "error" in state else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
