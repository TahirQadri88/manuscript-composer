# Gate

You do not read images and you do not repair the transcript.

```bash
python3 scripts/gate.py work/progress.md work/transcript.txt work/lines.json work/book.pdf
```

The gate writes `work/delivery.md`. Read that file. Do not compose the report from memory.

- Exit 0: `delivery.md` starts with CLAIMED. That still is not a proofreading. Say so.
- Exit 2: it starts with NATAMAM. Print `MISSING`, `DUPLICATES`, `OUT_OF_RANGE`, `BARE`, `THIN`, `UNPAIRED`, `UNCLOSED_FOOTNOTES`, and `GLUED_MARKERS` unchanged.
- DUPLICATES: the same index twice, usually a batch pasted twice. The Word file would carry the page twice. Do not delete one copy until someone checks which one is the reading.
- OUT_OF_RANGE: an index the PDF does not have, a mistyped number or a batch from another book. It is checked only when `book.pdf` is given.
- BARE: an `@pdf` with nothing under it. The page was claimed and not delivered.
- REPEATED does not change the exit code. It names a page where 8 or more words appear twice. Send the page to the second look, and name it in the delivery until it has been re-read.
- THIN means the page was claimed and most of its line boxes have no transcript. Do not delete the `@pdf` line to hide it.
- UNPAIRED means page N ends mid-sentence and page N+1 has no `@cont`.
- If `lines.json` is missing, the thin check did not run. Say that. Do not pretend it passed.
