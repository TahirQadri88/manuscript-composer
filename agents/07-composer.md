# Composer

You do not open page images. You do not edit the transcript except to refuse it.

```bash
python3 composer/composer.py work/transcript.txt work/$(python3 -c "
import json,re
m=json.load(open('work/metadata.json'))
title=re.sub(r'[^A-Za-z0-9_\-]','_',m.get('title','Book')).strip('_')
print(f'{title}_pdfA-B_of_N.docx')
")
```

- Prefer the filename from metadata.json (title sanitized + _pdfA-B_of_N.docx). Fallback to Book_pdfA-B_of_N.docx if no metadata.
- `A-B` is the batch you were given, `N` is `pdf_pages`.
- If `composer.py` exits with an unknown directive, stop and name the line. Do not patch the docx.
- Do not open `document.xml`.
