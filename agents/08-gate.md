# Gate

You do not read images and you do not repair the transcript.

```bash
python3 scripts/gate.py work/progress.md work/transcript.txt work/lines.json
```

The gate writes `work/delivery.md`. Read that file. Do not compose the report from memory.

- Exit 0: `delivery.md` starts with CLAIMED. That still is not a proofreading. Say so.
- Exit 2: it starts with NATAMAM. Print `MISSING`, `THIN`, `UNPAIRED`, `UNCLOSED_FOOTNOTES`, and `GLUED_MARKERS` unchanged.
- THIN means the page was claimed and most of its line boxes have no transcript. Do not delete the `@pdf` line to hide it.
- UNPAIRED means page N ends mid-sentence and page N+1 has no `@cont`.
- If `lines.json` is missing, the thin check did not run. Say that. Do not pretend it passed.
