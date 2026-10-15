# Layout

For each PDF index in the batch:

```bash
python3 scripts/render_regions.py work/book.pdf INDEX work/pages
```

Append one JSON line to `work/layout.jsonl`:

```json
{"pdf": 12, "kind": "prose", "header": "work/pages/p12_header.png", "body": "work/pages/p12_body.png"}
```

- `table`: the next role is the table reader, and it receives the `grid` crop.
- `prose`: body reader, then footnote reader, both receive the `body` crop.
- `cover` with no writing, `blank`, a watermark, or a scanner back: tell the orchestrator to `@skip`. Say what you saw.
- A title page, including one that repeats later in the book, is `prose` or whatever the script printed. It is transcribed. It is not a skip.
- Read the header crop once per book. Store the running title in `progress.md` under `header_once`. The digits in the header are what `@page` must use. Do not type the running title on every page.
- You do not write transcript lines.
