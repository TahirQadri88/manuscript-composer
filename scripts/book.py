# -*- coding: utf-8 -*-
"""Run a whole book through free chats, one batch per chat, with no files to carry.

The book's state lives in the repo under books/NAME/ on its own branch,
book/NAME. A chat that can run commands only has to read the crops it is
given. Everything else is here:

    python3 scripts/book.py start PDFs/vol1.pdf --name vol1   # once
    python3 scripts/book.py next                               # every chat
    # ... read the crops in books/vol1/next_batch.md, write books/vol1/batch.txt
    python3 scripts/book.py save                               # every chat
    python3 scripts/book.py finish                             # when next says done

next pulls the state from book/NAME, renders the next batch and lists its
crops. save checks the batch, appends it to transcript.txt, commits and
pushes. Nothing here reads ink or calls a model. --no-git keeps it local.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import audit_continuity as continuity
import gate
import init_progress
import next_batch

BOOKS = Path("books")
STATE = ("book.json", "progress.md", "transcript.txt", "lines.json", "next_batch.md")


def git(*args, check=True):
    result = subprocess.run(["git", *args], capture_output=True, text=True)
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {result.stderr.strip() or result.stdout.strip()}")
    return result


def slug(text):
    name = re.sub(r"[^A-Za-z0-9_-]+", "-", text).strip("-").lower()
    return name or "book"


def remote_books():
    result = git("ls-remote", "--heads", "origin", "book/*", check=False)
    if result.returncode != 0:
        return []
    return sorted(line.split("refs/heads/book/", 1)[1] for line in result.stdout.splitlines() if "refs/heads/book/" in line)


def find_book(name=None, use_git=False):
    """The book in books/, fetching it from origin/book/NAME in a fresh chat."""
    if use_git and not (name and (BOOKS / name / "book.json").is_file()):
        local = {p.parent.name for p in BOOKS.glob("*/book.json")}
        for remote in remote_books():
            if remote not in local and (name is None or remote == name):
                pull(BOOKS / remote)
    if name:
        path = BOOKS / name
        if not (path / "book.json").is_file():
            raise SystemExit(f"no book named {name}: run book.py start first")
        return path
    found = sorted(p.parent for p in BOOKS.glob("*/book.json"))
    if len(found) == 1:
        return found[0]
    if not found:
        raise SystemExit("no book yet: python3 scripts/book.py start PDFs/your.pdf --name short-name")
    raise SystemExit("more than one book: pass --name " + " | ".join(p.name for p in found))


def branch(book):
    return f"book/{book.name}"


def pull(book):
    """Bring this book's state, and the current scripts, into the working copy."""
    remote = git("ls-remote", "--heads", "origin", branch(book), check=False)
    if remote.returncode != 0 or not remote.stdout.strip():
        return "no saved state on origin yet"
    git("fetch", "-q", "origin", branch(book))
    git("checkout", "FETCH_HEAD", "--", str(book))
    return f"state from origin/{branch(book)}"


def push(book, message):
    """Commit the book's state onto book/NAME and push it, whatever branch is checked out."""
    files = [str(book / name) for name in STATE if (book / name).is_file()]
    files += [str(p) for p in book.glob("*.docx")] + [str(p) for p in book.glob("delivery.md")]
    git("add", "-f", *files)
    staged = git("diff", "--cached", "--quiet", "--", *files, check=False)
    if staged.returncode == 0:
        return "nothing new to save"
    # Build the commit on top of the book branch without moving the checkout.
    tree = git("write-tree").stdout.strip()
    parent = git("rev-parse", "--verify", "-q", f"refs/remotes/origin/{branch(book)}", check=False).stdout.strip()
    if not parent:
        parent = git("rev-parse", "HEAD").stdout.strip()
    commit = git("commit-tree", tree, "-p", parent, "-m", message).stdout.strip()
    git("reset", "-q")
    result = git("push", "origin", f"{commit}:refs/heads/{branch(book)}", check=False)
    if result.returncode != 0:
        return f"saved locally as {commit[:7]}, NOT pushed: {result.stderr.strip()}"
    git("fetch", "-q", "origin", branch(book), check=False)
    return f"pushed to origin/{branch(book)} ({commit[:7]})"


def load(book):
    meta = json.loads((book / "book.json").read_text(encoding="utf-8"))
    progress = (book / "progress.md").read_text(encoding="utf-8")
    transcript_path = book / "transcript.txt"
    transcript = transcript_path.read_text(encoding="utf-8") if transcript_path.is_file() else ""
    lines_path = book / "lines.json"
    counts = json.loads(lines_path.read_text(encoding="utf-8")) if lines_path.is_file() else None
    return meta, progress, transcript, counts


def start(pdf, name=None, page_range=None, use_git=True):
    import pymupdf
    import textlayer_guard
    pdf = Path(pdf)
    if not pdf.is_file():
        raise SystemExit(f"no such PDF: {pdf}")
    book = BOOKS / (name or slug(pdf.stem))
    if (book / "book.json").is_file():
        raise SystemExit(f"{book} already exists: run book.py next")
    book.mkdir(parents=True, exist_ok=True)
    if use_git and git("ls-files", "--error-unmatch", str(pdf), check=False).returncode != 0:
        print(f"warning: {pdf} is not committed. A later chat will not have it. Put it in PDFs/ and commit it.")
    with pymupdf.open(pdf) as doc:
        count = doc.page_count
    first, last = page_range or (None, None)
    (book / "progress.md").write_text(init_progress.progress_text("", count, first, last), encoding="utf-8")
    (book / "lines.json").write_text(
        json.dumps(textlayer_guard.line_counts(str(pdf)), ensure_ascii=False, indent=2), encoding="utf-8")
    (book / "book.json").write_text(json.dumps(
        {"pdf": str(pdf), "pdf_pages": count, "cap": None}, ensure_ascii=False, indent=2), encoding="utf-8")
    (book / "transcript.txt").write_text("", encoding="utf-8")
    print(f"{book}: {count} PDF pages")
    if use_git:
        print(push(book, f"Start {book.name}: {count} PDF pages"))
    return book


def crops_for(book, meta, pages):
    """Render each page of the batch; return its layout record."""
    import pymupdf
    import render_regions
    if meta.get("cap"):
        render_regions.VISION_CAP = int(meta["cap"])
    records = []
    with pymupdf.open(meta["pdf"]) as doc:
        for index in pages:
            info = render_regions.save_regions(doc[index - 1], book / "pages", index)
            records.append(render_regions.layout_record(info, index))
    with (book / "pages" / "layout.jsonl").open("a", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return records


def handoff(state, book):
    """next_batch.handoff, with the finished case pointing at book.py finish."""
    text = next_batch.handoff(state, str(book))
    if "## Done reading" in text:
        text = text.split("## Done reading")[0] + (
            "## Done reading\n\nEvery index is claimed. Build the single Word file and run the gate:\n\n"
            "```bash\npython3 scripts/book.py finish\n```\n")
    return text


def batch_sheet(book, state, records):
    """next_batch.md for a chat: what to fix, then each page's crops in reading order."""
    text = handoff(state, book)
    if not state.get("batch"):
        return text
    head = text.split("## Read PDF")[0]
    lines = [head.rstrip(), "", f"## Read PDF {', '.join(map(str, state['batch']))}", ""]
    for record in records:
        body = record.get("body") or record.get("grid")
        body = body if isinstance(body, list) else [body]
        lines.append(f"- PDF {record['pdf']} ({record['kind']}):")
        if record["kind"] == "blank":
            lines.append("  - blank: write `@skip " + str(record["pdf"]) + " blank`, after looking at `full`")
        for label, path in (("header", record.get("header")),):
            if path:
                lines.append(f"  - {label}: {path}")
        for n, path in enumerate(p for p in body if p):
            part = ("top half", "bottom half")[n] if len(body) > 1 else "body"
            lines.append(f"  - {part}: {path}")
        if record.get("footer"):
            lines.append(f"  - footer: {record['footer']}")
        lines.append(f"  - full page: {record['full']}")
    lines.append("")
    if state.get("cont_from"):
        lines += [f"PDF {state['cont_from']} ends mid-sentence. The first text line of PDF {state['batch'][0]} is `@cont`.", ""]
    lines += [
        f"Follow SKILL.md role by role. Write ONLY this batch, in PDF order, to `{book}/batch.txt`:",
        "one `@pdf N` (or `@skip N reason`) per page above, `@page`, then the text. "
        "Do not copy earlier pages. Then run `python3 scripts/book.py save` and stop.",
    ]
    return "\n".join(lines) + "\n"


def next_step(name=None, size=15, cap=None, use_git=True):
    book = find_book(name, use_git)
    if use_git:
        print(pull(book))
    meta, progress, transcript, _counts = load(book)
    if cap:
        meta["cap"] = cap
        (book / "book.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    state = next_batch.plan(progress, transcript, size)
    if "error" in state:
        raise SystemExit(state["error"])
    redo = {k: v for k, v in state["redo"].items() if v}
    if redo:
        # Claimed pages that are broken come before new pages.
        meta["pending"] = []
        sheet = "\n".join(
            ["# Fix first", ""]
            + [f"- {k}: {v}" for k, v in redo.items()]
            + ["",
               f"Open each page's image (`python3 scripts/render_regions.py \"{meta['pdf']}\" N {book}/pages`) and fix "
               f"`{book}/transcript.txt` in place: keep the copy of a duplicate that matches the image, read a bare "
               "page, start the page after an unpaired one with `@cont`, and re-read a repeat "
               "(add `# repeat-checked` under its @pdf if the book prints it twice).",
               "Then run `python3 scripts/book.py save --fixed` and stop."]) + "\n"
    else:
        records = crops_for(book, meta, state["batch"]) if state["batch"] else []
        meta["pending"] = state["batch"]
        sheet = batch_sheet(book, state, records)
    (book / "book.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    (book / "next_batch.md").write_text(sheet, encoding="utf-8")
    print(sheet, end="")
    return 0


def save(name=None, fixed=False, use_git=True):
    book = find_book(name)
    meta, progress, transcript, counts = load(book)
    batch_path = book / "batch.txt"
    batch = batch_path.read_text(encoding="utf-8") if batch_path.is_file() else ""
    pending = meta.get("pending") or []
    if not fixed:
        if not batch.strip():
            raise SystemExit(f"{batch_path} is empty: write the batch there first")
        pages = continuity.split_pages(batch)
        claimed = [p["pdf"] for p in pages]
        problems = []
        if sorted(claimed) != sorted(pending):
            problems.append(f"batch claims {claimed}, next_batch.md asked for {pending}")
        bare = continuity.bare_pages(pages)
        if bare:
            problems.append(f"@pdf with no text under it: {bare}")
        if problems:
            print("NOT SAVED:\n- " + "\n- ".join(problems), file=sys.stderr)
            return 2
        transcript = transcript.rstrip("\n") + ("\n" if transcript.strip() else "") + batch.strip("\n") + "\n"
        (book / "transcript.txt").write_text(transcript, encoding="utf-8")
        batch_path.write_text("", encoding="utf-8")
    report = gate.check(progress, transcript, counts, meta["pdf_pages"])
    state = next_batch.plan(progress, transcript)
    meta["pending"] = []
    (book / "book.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    (book / "next_batch.md").write_text(
        "Run `python3 scripts/book.py next` in a new chat.\n\n" + handoff(state, book).split("## Read PDF")[0],
        encoding="utf-8")
    print(f"{state['claimed']} of {state['total']} PDF pages claimed")
    for key in ("duplicates", "out_of_range", "bare", "thin", "unpaired"):
        if report.get(key):
            print(f"{key.upper()}: {report[key]}  (the next chat fixes this first)")
    if use_git:
        done = ",".join(map(str, pending)) if pending else "fixes"
        print(push(book, f"{book.name}: PDF {done} ({state['claimed']}/{state['total']})"))
    print("Done for this chat. Start a new chat and say: continue the book.")
    return 0


def finish(name=None, use_git=True):
    book = find_book(name, use_git)
    if use_git:
        print(pull(book))
    meta, progress, transcript, counts = load(book)
    state = next_batch.plan(progress, transcript)
    if state["batch"]:
        raise SystemExit(f"not finished: {state['total'] - state['claimed']} PDF pages unclaimed, next {state['batch'][:5]}")
    sys.path.insert(0, str(HERE.parent / "composer"))
    import composer
    first, last = state["range"]
    out = book / f"{book.name}_pdf{first}-{last}_of_{meta['pdf_pages']}.docx"
    app = composer.Composer()
    app.build(str(book / "transcript.txt"))
    app.finalize(str(out))
    report = gate.check(progress, transcript, counts, meta["pdf_pages"])
    gate.write_delivery(book / "delivery.md", report, out.name)
    print((book / "delivery.md").read_text(encoding="utf-8"), end="")
    if use_git:
        print(push(book, f"{book.name}: final docx and gate"))
    return 0 if gate.ok(report) else 2


def main(argv):
    args = list(argv[1:])
    use_git = "--no-git" not in args
    args = [a for a in args if a != "--no-git"]
    fixed = "--fixed" in args
    args = [a for a in args if a != "--fixed"]
    opts = {}
    for flag in ("--name", "--size", "--cap", "--range"):
        if flag in args:
            at = args.index(flag)
            opts[flag] = args[at + 1]
            del args[at:at + 2]
    if not args or args[0] not in ("start", "next", "save", "finish"):
        print(__doc__, file=sys.stderr)
        return 1
    command = args[0]
    name = opts.get("--name")
    if command == "start":
        if len(args) != 2:
            print("usage: book.py start PDF [--name NAME] [--range A-B]", file=sys.stderr)
            return 1
        page_range = None
        if "--range" in opts:
            a, b = opts["--range"].split("-")
            page_range = (int(a), int(b))
        start(args[1], name, page_range, use_git)
        return 0
    if command == "next":
        return next_step(name, int(opts.get("--size", 15)), opts.get("--cap"), use_git)
    if command == "save":
        return save(name, fixed, use_git)
    return finish(name, use_git)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
