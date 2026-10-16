---
name: manuscript-composer
description: >
  Transcribe a scanned Arabic, Urdu, Persian, or mixed RTL book into a styled
  Word file. Evidence only: no translation, no completed ayah, no expanded
  honorific. Use when the user uploads a manuscript, fatwa, fihrist, or old
  print and wants the text, not a summary.
---

# Manuscript Composer

You are one seat in a crew. The model reads ink. Python writes the `.docx` and blocks delivery when pages are missing. This file is the whole contract. It does not depend on Arena, Grok, Claude, Gemini, or any other host. If the host can spawn agents, give each file in `agents/` to its own agent. If it cannot, one model plays the roles in the order below and does not mix them.

## Crew

| Order | Role | File | May write |
|---|---|---|---|
| 1 | Orchestrator | `agents/00-orchestrator.md` | `progress.md` only |
| 2 | Inspector | `agents/01-inspector.md` | `progress.md` |
| 3 | Layout | `agents/02-layout.md` | `layout.jsonl` |
| 4 | Table reader | `agents/03-table-reader.md` | `@row` lines |
| 5 | Body reader | `agents/04-body-reader.md` | body lines |
| 6 | Footnote reader | `agents/05-footnote-reader.md` | `^[...]^` only |
| 7 | Second look | `agents/06-second-look.md` | replaces a token with `{{ }}` |
| 8 | Composer | `agents/07-composer.md` | the `.docx`, via `composer.py` |
| 9 | Gate | `agents/08-gate.md` | the delivery message |

A reader never runs `composer.py`. The composer never reads a page image. The gate never "fills in" a missing page.

## Setup

```bash
pip install -r requirements.txt
make check
```

Put the PDF at `work/book.pdf`. Create `work/`. All paths below are inside `work/` unless they start with the repo root.

## Loop

1. Inspector writes `range: 1-N` and `pdf_pages: N` into `progress.md` from the PDF's own page count. Never type them by hand: the gate trusts `range:` completely.

```bash
python3 ../scripts/init_progress.py book.pdf progress.md        # whole book
python3 ../scripts/init_progress.py book.pdf progress.md 12-26  # a range the user named
```

2. Layout runs, for each PDF index in the range. Classification uses a 72 dpi render, because its thresholds were tuned there. The crops a reader receives are rendered at the embedded scan's own pixels (300 dpi when the page has no embedded image), never upscaled past them, and capped at 2576 px on the long edge, the size above which a vision host resizes the image. A body crop that would exceed the cap is split once, through whitespace between two lines, into `p{N}_body_a.png` (top) and `p{N}_body_b.png` (bottom). On a high-resolution A4 scan that is the difference between about 220 dpi for the whole page and 318–434 dpi per half, measured on ten pages. A half is never sharper than the scan itself. The script prints `ppi`, each crop's dpi, the split, and the `layout.jsonl` line:

```bash
python3 ../scripts/textlayer_guard.py book.pdf lines.json
python3 ../scripts/render_regions.py book.pdf INDEX pages layout.jsonl
```
3. Cover or blank: `@skip INDEX reason`. A repeated title page is **not** a skip. Transcribe it again.
4. Table: the table reader writes one `@row` per printed row. Right to left. Do not sort.
5. Prose: the body reader writes the lines, from both halves when the body was split, as one `@pdf` block. Then the footnote reader looks at the bottom of the same crop (the bottom half when split). A note is `^[full note]^`. If there is no note, it writes nothing. It does not leave the note in the body as well.
6. Second look re-opens the crop under a new filename. It checks every digit from `audit_digits.py` (the crop, never the text-layer glyphs), every honorific, and the first and last word of the page. If this page ends mid-sentence, the next page's first line is `@cont`. A disagreement becomes `{{first|second: …}}`. It does not pick the nicer reading, and it does not reverse a digit run to "fix" it.
7. After the batch, and only then, the composer runs:

```bash
# Filename from work/metadata.json "title", sanitized. Falls back to Book_....
python3 ../composer/composer.py transcript.txt "$(python3 -c "
import json,re
try:
  m=json.load(open('metadata.json'))
  title=re.sub(r'[^A-Za-z0-9_\-]','_',m.get('title','Book')).strip('_') or 'Book'
  print(f'{title}_pdfA-B_of_N.docx')
except Exception:
  print('Book_pdfA-B_of_N.docx')
")"
python3 ../scripts/gate.py progress.md transcript.txt lines.json book.pdf
```

8. The gate writes `delivery.md`. Exit 0 means every index is claimed exactly once, no `@pdf` is empty, no index is outside the PDF, no page is thin against its line-box count, and a mid-sentence page is paired with `@cont`. It does not mean the ink was compared line by line. Exit 2: the delivery starts with `NATAMAM`. Do not call the book finished. Without `lines.json` the thin check does not run, and a claimed page can still be half empty. Without `book.pdf` an index the PDF does not have is not looked for. `REPEATED` does not fail the gate: it names a page where 8 or more words appear twice. Send that page back to the second look, which re-reads the image.

Clean print: about 15 PDF pages a turn. Handwriting: about 8. Append to the same `transcript.txt`. On the next turn, read `progress.md` and reopen the last page image. Do not rewrite earlier pages from memory.

### Final single file

Once the full range is in `transcript.txt` (and `progress.md` shows the complete range with no missing pages), run the composer **once** on the whole transcript to produce one merged file:

```bash
python3 ../composer/composer.py transcript.txt work/Final_Book_pdf1-N_of_N.docx
# or use the metadata-derived name with the full range
```

The gate must still pass, including the thin check and the `@cont` pairs, and `delivery.md` must not start with NATAMAM. Batch files may be kept or discarded; the final file is the complete book.

## Transcript

One paragraph per line. `#` lines are notes and are not printed.

| Line | Printed? |
|---|---|
| `@pdf 12` | no — ledger, required for every page you claim to have read |
| `@skip 3 blank-verso` | no — only watermarks, stamps, scanner backs, blank versos |
| `@page 9` | `[ص 9]` as its own paragraph. Digits only, as printed |
| `@sheet 7 of 9` | `[شیٹ 7/9]`. The running sheet of a mis-stitched scan. Not a page number, and not a reason to reorder pages |
| `@lang ur` | switches font. `ar` `ur` `fa` `ps` `sd` `en` `hi` |
| `@cont …` | the rest of a sentence that started on the previous page |
| `@row a ||| b ||| c` | one table row, in printed order |
| `@verse a ||| b` | two hemistiches |
| `@title` `@heading1` `@heading2` `@basmala` `@center` `@quote` | as named |
| `^[note]^` | a Word footnote. The closer is `]^` so a `]` inside the note does not cut it |
| `{{seen|why}}` | yellow highlight. Empty left side if nothing was readable: `{{|not read}}` |
| `**lemma**` | bold lemma, such as قوله |
| `[[blank]]` | a gap the scribe left |
| `[[ref:ص ٢]]` | a marginal reference |

A page you read starts with `@pdf`, then `@page`, then the text. `@skip` replaces both. There is no third option: a bare `@pdf`, the same index twice, or an index the PDF does not have fails the gate.

## Ink rules

These are the failures this skill exists to stop.

- Do not translate. Do not modernize. Do not add punctuation.
- Do not complete an ayah, a hadith, or a fiqh line from memory or from another edition. A cut line ends `{{|line ends}}`.
- Never output the same sentence twice. If a clause appears to repeat, read the image again before writing it. A clause read twice comes out fluent and unmarked, and the gate can only flag it.
- Do not add harakat that are not printed. Do not add `﴿ ﴾` unless they are printed.
- Copy `ﷺ ؐ ؑ ؒ ؓ ﷻ` as glyphs. Do not expand them into `حفظہ اللہ` or `صلی اللہ علیہ وسلم`.
- Urdu `ی ے ہ ک` stays Urdu. Digits stay in the shapes printed. `۳۶۲ تا ۳۶۴` stays a range.
- A second phone number on the same page does not correct the first.
- The book's own `لعل` or `في المخطوط` is ink. Copy it. Do not write your own.
- A page marker is never a word inside a sentence. Forbidden: `پھر ان کی [ص 10] ایک منظم`. The last words of a page stay on that page. If they do not finish the sentence, the next PDF page begins with `@cont`.
- A footnote is not finished at a line break. Forbidden: stopping at `شعر` when the next word is `و سخن`.
- Do not sort a fihrist. Item 2 on page 18 and item 3 on page 12 stay in that order.
- Never hand-edit `document.xml`.
- Do not copy prose or digits out of a text layer. Urdu in the layer is visual order, and digits come out reversed or expanded: the layer's `20022` is not the page's `۲۰۲۲`. Reversing `20022` does not produce `۲۰۲۲`, so do not repair it. Use the line boxes to crop, then read the image. Archive.org `*_hocr_searchtext.txt.gz` and `*_djvu.txt` are the same trap. The JP2 leaves are the second copy worth reading.
- A camera sheet that looks mis-stitched is recorded in `metadata.json` (`print_runs`, `stamps`). See `examples/metadata.json`. It is not a reason to reorder the book.

## Style

`composer/composer.py` has the default: A4, Arabic in Traditional Arabic 16, Urdu in Jameel Noori Nastaleeq 14. A written style sheet is applied by editing the `STYLE` dict only. Tell the user which fonts must be installed. The file only names them.

## Delivery

In the user's language, short:

1. The docx, named from the metadata title plus `_pdfA-B_of_N.docx`. If there is no title, `Book_pdfA-B_of_N.docx`.
2. Read `delivery.md`. If it starts with **NATAMAM**, that is the first word of your message. Stop.
3. Otherwise say the indexes, the languages, the style, the uncertain count from `delivery.md`, any `REPEATED` page not yet re-read, and what `@skip` covers. Say that the gate passed its mechanical checks and that a person still has to proofread.
4. Ask for the next range. Do not promise "the rest" from memory.
