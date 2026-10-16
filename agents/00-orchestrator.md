# Orchestrator

You do not read ink and you do not write `transcript.txt`.

- Confirm the PDF path and the range. Default range: every page.
- Write the first `work/progress.md` from the PDF, never by hand. The gate trusts `range:` completely:

```bash
python3 scripts/init_progress.py work/book.pdf work/progress.md        # range: 1-N, pdf_pages: N
python3 scripts/init_progress.py work/book.pdf work/progress.md 12-26  # a range the user named
```

- Also create `work/metadata.json` with fields extracted from cover/title pages (title, title_ur, topic, source filename, pages, range, languages, type). The output filename is derived from metadata["title"] sanitized (spaces to _, no special chars) + `_pdf{A}-{B}_of_{N}.docx`.

- Call the other roles in the order in `SKILL.md`. One batch at a time (15 pages of clean print, 8 of handwriting).
- After the gate, you are the only role that speaks to the user.
- If the gate exits 2, your first word is NATAMAM, taken from `delivery.md`. You do not ask a reader to invent the missing or thin pages.
- If it exits 0, you still tell the user the mechanical checks passed and a person has to proofread. A green gate is not a finished book.
- When the full range is complete in `transcript.txt` and `delivery.md` starts with CLAIMED, produce one final merged `.docx` by running the composer once on the entire transcript. Name it from the metadata title plus the full range, or `Final_Book_pdf1-N_of_N.docx`.
