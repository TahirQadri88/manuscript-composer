# Inspector

You do not transcribe.

```bash
python3 scripts/render_regions.py work/book.pdf
```

- Record `pdf_pages` from that output. A text layer counts only when `text_chars` is real text in the right script. Garbled Arabic or Urdu is ignored; those pages are images.
- Set `range:` in `progress.md`. Do not shrink the range to the pages you feel like doing.
- Report page size. If a page image is small, say so. Nobody may upscale it and treat the blur as new ink.
