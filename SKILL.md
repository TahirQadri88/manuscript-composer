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
python3 -m unittest tests.test_skill
```

Put the PDF at `work/book.pdf`. Create `work/`. All paths below are inside `work/` unless they start with the repo root.

## Loop

1. Inspector writes `progress.md` with `range: 1-N` (the whole PDF, unless the user named a range) and `pdf_pages: N`.
2. Layout runs, for each PDF index in the range:

```bash
python3 ../scripts/render_regions.py book.pdf INDEX pages
```

   It prints `cover`, `blank`, `table`, or `prose`, and writes crops at the scan's own pixel size. Do not upscale.
3. Cover or blank: `@skip INDEX reason`. A repeated title page is **not** a skip. Transcribe it again.
4. Table: the table reader writes one `@row` per printed row. Right to left. Do not sort.
5. Prose: the body reader writes the lines. Then the footnote reader looks at the bottom of the same crop. A note is `^[full note]^`. If there is no note, it writes nothing. It does not leave the note in the body as well.
6. Second look re-opens the crop under a new filename and checks every digit, every honorific, and every uncertain word. A disagreement becomes `{{first|second: …}}`. It does not pick the nicer reading.
7. After the batch, and only then, the composer runs:

```bash
python3 ../composer/composer.py transcript.txt Book_pdfA-B_of_N.docx
python3 ../scripts/gate.py progress.md transcript.txt
```

8. Gate exit code 2: the delivery starts with `NATAMAM` and the missing indexes. Do not call the book finished.

Clean print: about 15 PDF pages a turn. Handwriting: about 8. Append to the same `transcript.txt`. On the next turn, read `progress.md` and reopen the last page image. Do not rewrite earlier pages from memory.

## Transcript

One paragraph per line. `#` lines are notes and are not printed.

| Line | Printed? |
|---|---|
| `@pdf 12` | no — ledger, required for every page you claim to have read |
| `@skip 3 blank-verso` | no — only watermarks, stamps, scanner backs, blank versos |
| `@page 9` | `[ص 9]` as its own paragraph. Digits only, as printed |
| `@lang ur` | switches font. `ar` `ur` `fa` `ps` `sd` `en` `hi` |
| `@cont …` | the rest of a sentence that started on the previous page |
| `@row a \|\|\| b \|\|\| c` | one table row, in printed order |
| `@verse a \|\|\| b` | two hemistiches |
| `@title` `@heading1` `@heading2` `@basmala` `@center` `@quote` | as named |
| `^[note]^` | a Word footnote. The closer is `]^` so a `]` inside the note does not cut it |
| `{{seen\|why}}` | yellow highlight. Empty left side if nothing was readable: `{{|not read}}` |
| `**lemma**` | bold lemma, such as قوله |
| `[[blank]]` | a gap the scribe left |
| `[[ref:ص ٢]]` | a marginal reference |

A page you read starts with `@pdf`, then `@page`, then the text. `@skip` replaces both. There is no third option.

## Ink rules

These are the failures this skill exists to stop.

- Do not translate. Do not modernize. Do not add punctuation.
- Do not complete an ayah, a hadith, or a fiqh line from memory or from another edition. A cut line ends `{{|line ends}}`.
- Do not add harakat that are not printed. Do not add `﴿ ﴾` unless they are printed.
- Copy `ﷺ ؐ ؓ ؒ ؑ ﷻ` as glyphs. Do not expand them into `حفظہ اللہ` or `صلی اللہ علیہ وسلم`.
- Urdu `ی ے ہ ک` stays Urdu. Digits stay in the shapes printed. `۳۶۲ تا ۳۶۴` stays a range.
- A second phone number on the same page does not correct the first.
- The book's own `لعل` or `في المخطوط` is ink. Copy it. Do not write your own.
- A page marker is never a word inside a sentence. Forbidden: `پھر ان کی [ص 10] ایک منظم`. The last words of a page stay on that page.
- A footnote is not finished at a line break. Forbidden: stopping at `شعر` when the next word is `و سخن`.
- Do not sort a fihrist. Item 2 on page 18 and item 3 on page 12 stay in that order.
- Never hand-edit `document.xml`.

## Style

`composer/composer.py` has the default: A4, Arabic in Traditional Arabic 16, Urdu in Jameel Noori Nastaleeq 14. A written style sheet is applied by editing the `STYLE` dict only. Tell the user which fonts must be installed. The file only names them.

## Delivery

In the user's language, short:

1. The docx, named `Book_pdfA-B_of_N.docx`.
2. If the gate printed `MISSING`, the first word is **NATAMAM** and the indexes follow. Stop.
3. Otherwise: indexes read, languages, style, how many `{{ }}`, what `@skip` covers.
4. Ask for the next range. Do not promise "the rest" from memory.
