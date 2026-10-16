# Inspector

You do not transcribe.

```bash
python3 scripts/textlayer_guard.py work/book.pdf work/lines.json
python3 scripts/render_regions.py work/book.pdf
```

- `lines.json` is a count of line boxes. It is not text. The gate uses it for the thin check.
- A text layer with Urdu or digits is unusable. Glyphs are visual order. `20022` in the layer is not `۲۰۲۲`, and reversing it does not make it so. Boxes may be cropped. Characters may not be copied.
- Archive.org `*_hocr_searchtext.txt.gz` and `*_djvu.txt` are the same trap. The JP2 leaves are the second copy.
- Write `work/metadata.json` for print runs and stamps. A mis-stitched camera sheet is a note there, not a reason to reorder pages. Copy `examples/metadata.json`.
- Set `range:` and `pdf_pages` in `progress.md` with `python3 scripts/init_progress.py work/book.pdf work/progress.md`, which reads `doc.page_count`. Do not type them. Do not shrink the range to the pages you feel like doing.
- Report `ppi` from the render script. Crops are never rendered above the embedded scan. They are rendered below it only to stay under the 2576 px cap, and a body that would exceed the cap is split instead.
