# Composer

You do not open page images. You do not edit the transcript except to refuse it.

```bash
python3 composer/composer.py work/transcript.txt work/Book_pdfA-B_of_N.docx
```

- `A-B` is the batch you were given, `N` is `pdf_pages`.
- If `composer.py` exits with an unknown directive, stop and name the line. Do not patch the docx.
- Do not open `document.xml`.
