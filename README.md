# Manuscript Composer

A downloadable skill for turning a scanned Arabic, Urdu, or Persian book into a Word file. Any vision model can sit in the crew: Grok, Claude, Gemini, GPT, Gemma, Qwen. The model reads the page. Python builds the `.docx` and will not call a half-finished book done.

The kit was first written by Abu Ameer Khusraw for Arena agent mode. This repo is that kit split into nine roles, after a composed file of *al-Taʿlīqāt al-Riḍawiyya* was checked against the scan. That file stopped at printed page 120 of 216, dropped pages inside the range, glued a page marker into a sentence, cut a footnote at شعر, and expanded a short honorific into حفظہ اللہ. The roles and the tests exist to stop those.

## Use it

1. Clone this repo.
2. `pip install -r requirements.txt`
3. `python3 -m unittest tests.test_skill`
4. Open a new chat with a vision model. Attach `SKILL.md`, or point the model at this repo, and attach the PDF.
5. If the host can spawn agents, it should spawn one per file in `agents/`. If it cannot, the same model plays the roles in order. Grok does either: one chat that follows `SKILL.md`, or a crew if the host has subagents.

The model writes `work/transcript.txt`. Then:

```bash
python3 composer/composer.py work/transcript.txt work/Book_pdf1-15_of_217.docx
python3 scripts/gate.py work/progress.md work/transcript.txt
```

Exit code 2 means the file is not the whole range. The reply has to start with NATAMAM.

## What the model is not allowed to do

Translate, modernize, finish a cut ayah, expand ﷺ or ؒ into words, sort a fihrist, or edit the Word XML. Unreadable ink is `{{|not read}}`, in yellow in the docx.

## Tests

`tests/test_skill.py` builds a docx from a marked-up transcript and checks the four failures above. It also classifies pages of a scanned fiqh book when that PDF is on the machine: a ruled fihrist is a table, a title page is prose, a photo cover is a cover, and there is no text layer to cheat from. The classifier does not invent a footnote rule the scan does not contain. The footnote role reads the bottom of the page instead.

## Fonts

The docx names Traditional Arabic, Jameel Noori Nastaleeq, B Nazanin, and Times New Roman. They have to be installed on the computer that opens the file.
