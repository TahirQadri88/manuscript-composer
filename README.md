# Manuscript Composer

A downloadable skill for turning a scanned Arabic, Urdu, or Persian book into a Word file. Any vision model can sit in the crew: Grok, Claude, Gemini, GPT, Gemma, Qwen. The model reads the page. Python builds the `.docx` and will not call a half-finished book done.

The kit was first written by Abu Ameer Khusraw for Arena agent mode. This repo is that kit split into nine roles, after a composed file of *al-Taʿlīqāt al-Riḍawiyya* was checked against the scan. That file stopped at printed page 120 of 216, dropped pages inside the range, glued a page marker into a sentence, cut a footnote at شعر, and expanded a short honorific into حفظہ اللہ. The roles and the tests exist to stop those.

## Use it

1. Clone this repo.
2. `pip install -r requirements.txt`
3. `make check`
4. Open a new chat with a vision model. Attach `SKILL.md`, or point the model at this repo, and attach the PDF.
5. If the host can spawn agents, it should spawn one per file in `agents/`. If it cannot, the same model plays the roles in order. Grok does either: one chat that follows `SKILL.md`, or a crew if the host has subagents.

A free chat cannot hold a whole book, so the book is read a batch per chat, and the repo carries the state. Commit the PDF under `PDFs/`, then in an agent chat that can run commands and push (Arena agent mode):

1. First chat: "Start the book `PDFs/FILE.pdf` as vol1, then continue the book." It runs `python3 scripts/book.py start PDFs/FILE.pdf --name vol1`.
2. Every chat after that, just say: **continue the book.** `AGENTS.md` tells the agent the rest: `book.py next` fetches the state from the `book/vol1` branch and renders the next 15 pages, the agent reads them, and `book.py save` checks, appends, commits and pushes.
3. When it reports Done reading: "finish the book." `book.py finish` builds one Word file and runs the gate, on the same branch.

No API key, no paid model, no files to download or upload between chats: the chat is the reader, and git is the memory. A host that cannot run commands can still use `scripts/next_batch.py` with a `work/` folder you carry by hand.

The model writes `work/transcript.txt`. Then:

```bash
python3 composer/composer.py work/transcript.txt work/Book_pdf1-15_of_217.docx
python3 scripts/gate.py work/progress.md work/transcript.txt work/lines.json work/book.pdf
```

Exit code 2 means the file is not the whole range, an index is claimed twice or with nothing under it, an index is not in the PDF, a claimed page is thin against its line boxes, or a sentence crosses a page without `@cont`. The reply has to start with NATAMAM. `work/delivery.md` is that report. Do not write it from memory.

Exit 0 is not a finished book. It means every index was claimed once, with something under it, the thin check passed when `lines.json` was present, and `@cont` pairs. It does not mean someone compared the ink. Without `lines.json` the thin check does not run, and a page can be half empty and still claimed.

## What a reader is sent

Not the whole page at 72 dpi. `scripts/render_regions.py` classifies at 72 dpi, where its thresholds were tuned, and renders the reader's crops at the embedded scan's own pixels, never upscaled, capped at 2576 px on the long edge, or lower for a host that resizes sooner (`--cap 2000`, or `MANUSCRIPT_VISION_CAP=2000`, for Claude Code). A vision host resizes anything larger, so an A4 page sent whole arrives at about 220 dpi. A body crop that would exceed the cap is split once, through whitespace between two lines, never at the midpoint and never with an overlap. Each half then arrives at up to the scan's own resolution: 318–434 dpi on ten A4 pages measured. Nastaliq that is unreadable at 110 dpi is readable at 400. `layout.jsonl` carries both halves to the body reader.

## Text layer

Do not copy the PDF text layer, and do not copy Archive.org `*_hocr_searchtext.txt.gz` or `*_djvu.txt`. On these Urdu scans the glyphs are visual order and the digits are wrong: `20022` in the layer is not `۲۰۲۲` on the page, and reversing the layer string does not repair it. Line boxes are only for cropping. The JP2 leaves are the second copy to read. `scripts/textlayer_guard.py` writes the line counts. `scripts/audit_digits.py` crops each numeric line.

## What the model is not allowed to do

Translate, modernize, finish a cut ayah, expand ﷺ or ؒ into words, sort a fihrist, or edit the Word XML. Unreadable ink is `{{|not read}}`, in yellow in the docx.

## Tests

`tests/test_skill.py` builds a docx from a marked-up transcript and checks the four failures above. It also classifies pages of a scanned fiqh book when that PDF is on the machine: a ruled fihrist is a table, a title page is prose, a photo cover is a cover, and there is no text layer to cheat from. The classifier does not invent a footnote rule the scan does not contain. The footnote role reads the bottom of the page instead.

## Fonts

The docx names Traditional Arabic, Jameel Noori Nastaleeq, B Nazanin, and Times New Roman. They have to be installed on the computer that opens the file.
