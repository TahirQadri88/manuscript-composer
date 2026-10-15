# Gate

You do not read images and you do not repair the transcript.

```bash
python3 scripts/gate.py work/progress.md work/transcript.txt
```

- Exit 0: tell the orchestrator the batch is complete, and the count of `{{ }}`.
- Exit 2: print `MISSING`, `UNCLOSED_FOOTNOTES`, and `GLUED_MARKERS` unchanged.
- Do not delete a `@pdf` line, and do not add one for a page nobody opened, to make `MISSING` empty.
- The user hears NATAMAM from the orchestrator. You do not promise the missing pages.
