# Footnote reader

You receive the same body crop as the body reader, plus the lines they just wrote.

- Look at the bottom of the crop. When the page came in two halves, that is the bottom half (`body_b`). A note is smaller type, often under a rule, sometimes only a gap.
- If there is no note, write nothing.
- If there is a note, delete it from the body line and put the whole note here:

```
متن۔^[آپ پیرِ طریقت ہیں۔ شعر و سخن میں مخلص ”تاباں“ ہے۔ [حاشیہ] ]^
```

- The closer is `]^`. A `]` inside the note must not be where you stop.
- You are not finished at a line break. Read until the last word of the note.
- A note that continues on the next page is still one `^[...]^`, finished from the next page's crop. If you cannot see the end, close with `{{|footnote continues, not read}}`.
- The editor's printed `لعل` is copied. You do not add one.
- Do not also leave the note in the body.
