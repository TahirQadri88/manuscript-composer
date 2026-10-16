# Layout

For each PDF index in the batch:

```bash
python3 scripts/render_regions.py work/book.pdf INDEX work/pages work/layout.jsonl
```

The script appends one JSON line to `work/layout.jsonl` and prints it. Do not write that line yourself. `body` is one path when the crop fits, or two, top then bottom, when the page was split:

```json
{"pdf": 12, "kind": "prose", "header": "work/pages/p12_header.png", "body": "work/pages/p12_body.png", "full": "work/pages/p12_full.png"}
{"pdf": 13, "kind": "prose", "header": "work/pages/p13_header.png", "body": ["work/pages/p13_body_a.png", "work/pages/p13_body_b.png"], "full": "work/pages/p13_full.png"}
{"pdf": 40, "kind": "prose", "header": "work/pages/p40_header.png", "body": "work/pages/p40_body.png", "footer": "work/pages/p40_footer.png", "full": "work/pages/p40_full.png"}
```

- A body crop is split only when it would exceed the cap on its long edge, 2576 px unless the host resizes sooner (`--cap 2000` for Claude Code). The body ends at the page's last line of text, so a page that ends high is not split through its white and no half is sent blank. The cut runs through whitespace between two lines. There is no overlap, so no line is in both halves. `split none: no quiet band` means the page stayed whole.

- `table`: the next role is the table reader, and it receives the `grid` crop.
- `prose`: body reader, then footnote reader, both receive the `body` crop: every path in `body`, in order.
- `cover` with no writing, `blank`, a watermark, or a scanner back: tell the orchestrator to `@skip`. Say what you saw.
- A title page, including one that repeats later in the book, is `prose` or whatever the script printed. It is transcribed. It is not a skip.
- `footer` is an isolated block at the foot of the page, set apart by a wide gap: a page number, or an uploader's watermark such as an archive.org link. Look at it. A page number printed there is what `@page` uses. A watermark is not the book's ink and is not transcribed. Anything else is passed to the body reader with the body.
- Read the header crop once per book. Store the running title in `progress.md` under `header_once`. The digits in the header are what `@page` must use. Do not type the running title on every page.
- You do not write transcript lines.
