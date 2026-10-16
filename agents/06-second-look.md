# Second look

You do not get the first reader's notes. You open the crop again, saved under a new filename, because a reused filename can show you the old image.

When `layout.jsonl` gives the page's `body` as two paths, re-open the half the token is in: `_body_a` is the top, `_body_b` the bottom. The page's first word is in `_body_a`, its last word and any footnote in `_body_b`. For a token next to the cut, open both. `full` is the whole page, at lower resolution.

Check only:

- every digit, from the crops `scripts/audit_digits.py` wrote. The text-layer string is not a reading. Do not reverse it.
- every honorific glyph
- every `{{ }}`
- the last word of every footnote
- every page the gate printed under `REPEATED`. Re-read the whole passage from the image. If the clause is printed once, the second copy is the reader's: mark it `{{copy|second: printed once}}`. If it is printed twice, change nothing and add a line `# repeat-checked` under that page's `@pdf`, so later chats do not re-read it. Do not delete it either way.
- whether this page ends mid-sentence. If it does, the next page must start with `@cont`. The gate checks the pair. Do not invent it by rewriting an earlier page.

If you read the same string, change nothing. If you read a different string, replace the token with `{{first reading|second: your reading}}`. You do not choose the one that looks more correct. You do not "fix" a phone number because another line shows a different one.
