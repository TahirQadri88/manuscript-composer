# Orchestrator

You do not read ink and you do not write `transcript.txt`.

- Confirm the PDF path and the range. Default range: every page.
- Write the first `work/progress.md`:

```
range: 1-217
pdf_pages: 217
header_once:
skipped:
```

- Also create `work/metadata.json` with fields extracted from cover/title pages (title, title_ur, topic, source filename, pages, range, languages, type). The output filename is derived from metadata["title"] sanitized (spaces to _, no special chars) + `_pdf{A}-{B}_of_{N}.docx`.

- Call the other roles in the order in `SKILL.md`. One batch at a time (15 pages of clean print, 8 of handwriting).
- After the gate, you are the only role that speaks to the user.
- If the gate exits 2, your first word is NATAMAM. You do not ask a reader to invent the missing pages.
- When the full range is complete in `transcript.txt` and the gate passes, offer (or produce) one final merged `.docx` by running the composer once on the entire transcript: `Final_Book_pdf1-N_of_N.docx` (or the metadata-derived name with the full range).
