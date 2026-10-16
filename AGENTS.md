# Agents

This repo is a crew, not a single prompt. Read `SKILL.md` first.

## "Continue the book"

When the user says continue, next, or carry on, and you can run commands, do exactly this and nothing more:

1. `python3 scripts/book.py next` (add `--cap 2000` if your host resizes images above 2000 px). It fetches the book's state from the `book/NAME` branch and writes `books/NAME/next_batch.md`.
2. If it says **Fix first**, fix those pages in `books/NAME/transcript.txt` from the images, run `python3 scripts/book.py save --fixed`, and stop.
3. Otherwise open every crop it lists, play the roles in `SKILL.md` in order, and write that batch, and only that batch, to `books/NAME/batch.txt`.
4. `python3 scripts/book.py save`. It checks the batch, appends it, commits and pushes to `book/NAME`. If it prints NOT SAVED, fix `batch.txt` and save again.
5. Stop. Do not start a second batch in the same chat. Tell the user how many pages are claimed and to say "continue the book" in a new chat.

When `next` says **Done reading**, run `python3 scripts/book.py finish` instead. It builds the single Word file and runs the gate. If no book exists yet: `python3 scripts/book.py start PDFs/FILE.pdf --name SHORT-NAME`.

If you can spawn subagents, spawn one per file in `agents/` and do not let a reader see the composer's tools. Pass only the crop paths and the transcript lines that role is allowed to touch.

If you are one model, announce the role in a heading (`## layout`, `## body-reader`) and finish that role's file before the next heading. Do not transcribe during layout. Do not classify during reading.

The tests in `tests/test_skill.py` are the law for the Python half. Do not weaken them to make a book look finished.

A green gate means the ledger and the mechanical checks passed. It does not mean the page was finished. If `lines.json` was missing, the thin check did not run. Archive.org hOCR and DjVu text are not a source for Urdu. The JP2 is.
