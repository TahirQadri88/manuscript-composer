# -*- coding: utf-8 -*-
"""Tests for the parts a model must not do itself: the docx builder,
the coverage gate, and layout classification of a real scan.
"""
import os
import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
def sample_pdf():
    candidates = []
    if os.environ.get("MANUSCRIPT_PDF"):
        candidates.append(Path(os.environ["MANUSCRIPT_PDF"]))
    candidates.append(ROOT / "samples" / "book.pdf")
    for path in candidates:
        if path.is_file():
            return path
    return None
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


composer = load("composer", ROOT / "composer" / "composer.py")
gate = load("gate", ROOT / "scripts" / "gate.py")
regions = load("regions", ROOT / "scripts" / "render_regions.py")


def docx_texts(path):
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
        paragraphs = []
        for p in root.iter(W + "p"):
            parts = []
            for node in p.iter(W + "t"):
                if node.text:
                    parts.append(node.text)
            if parts:
                paragraphs.append("".join(parts))
        notes = []
        if "word/footnotes.xml" in z.namelist():
            fn = ET.fromstring(z.read("word/footnotes.xml"))
            for node in fn.iter(W + "t"):
                if node.text:
                    notes.append(node.text)
        tables = list(root.iter(W + "tbl"))
    return paragraphs, notes, tables


class ComposerTests(unittest.TestCase):
    def build(self, transcript):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        src = Path(tmp.name) / "t.txt"
        out = Path(tmp.name) / "out.docx"
        src.write_text(transcript, encoding="utf-8")
        app = composer.Composer()
        app.build(str(src))
        app.finalize(str(out))
        return docx_texts(out)

    def test_page_marker_is_its_own_paragraph_and_digits_stay(self):
        body, notes, _ = self.build(
            "@lang ur\n@pdf 12\n@page 9\n"
            "پھر ان کی\n"
            "@pdf 13\n@page 10\n"
            "@cont ایک منظم\n"
            "۳۶۲ تا ۳۶۴\n"
            "ی ے ہ ک\n"
        )
        joined = " ".join(body)
        self.assertIn("[ص 9]", body)
        self.assertIn("[ص 10]", body)
        self.assertTrue(all("[ص" not in p or p.startswith("[ص") for p in body))
        self.assertIn("ایک منظم", body)
        self.assertIn("۳۶۲ تا ۳۶۴", joined)
        self.assertIn("ی ے ہ ک", joined)
        self.assertNotIn("ي ه ك", joined)
        self.assertEqual(notes, [])

    def test_honorific_is_not_expanded_by_the_builder(self):
        body, _, _ = self.build("@lang ur\n@pdf 12\n@page 9\nسید وجاہت رسول قادری ؒ\n")
        self.assertIn("ؒ", " ".join(body))
        self.assertNotIn("حفظہ", " ".join(body))

    def test_footnote_keeps_brackets_and_the_rest_of_the_sentence(self):
        _, notes, _ = self.build(
            "@lang ur\n@pdf 12\n@page 9\n"
            "متن۔^[آپ پیرِ طریقت ہیں۔ شعر و سخن میں مخلص ”تاباں“ ہے۔ [حاشیہ] ]^\n"
        )
        note = " ".join(notes)
        self.assertIn("شعر و سخن", note)
        self.assertIn("[حاشیہ]", note)
        self.assertTrue(note.strip().endswith("[حاشیہ]"))

    def test_table_rows_are_not_reordered(self):
        body, _, tables = self.build(
            "@lang ur\n@pdf 4\n@page 1\n"
            "@row 2 ||| اظہارِ خیال ||| 18\n"
            "@row 3 ||| انتساب ||| 12\n"
        )
        self.assertEqual(len(tables), 1)
        flat = " ".join(body)
        self.assertLess(flat.index("اظہارِ خیال"), flat.index("انتساب"))
        self.assertIn("18", flat)
        self.assertIn("12", flat)

    def test_pdf_and_skip_are_not_printed(self):
        body, _, _ = self.build("@lang ar\n@pdf 3\n@skip 2 blank-verso\n@page 1\nعنوان\n")
        flat = " ".join(body)
        self.assertNotIn("@pdf", flat)
        self.assertNotIn("blank-verso", flat)
        self.assertIn("عنوان", flat)
        self.assertIn("[ص 1]", body)


class GateTests(unittest.TestCase):
    def test_missing_page_unclosed_note_and_glued_marker_fail(self):
        progress = "range: 1-3\npdf_pages: 3\n"
        bad = "@pdf 1\n@page 1\nپھر ان کی [ص 2] ایک\nمتن^[حاشیہ کٹی\n"
        report = gate.check(progress, bad)
        self.assertEqual(report["missing"], [2, 3])
        self.assertEqual(len(report["unclosed_footnotes"]), 1)
        self.assertEqual(len(report["glued_markers"]), 1)
        self.assertFalse(gate.ok(report))

    def test_complete_transcript_passes(self):
        progress = "range: 1-3\n"
        good = "@pdf 1\n@page 1\nعنوان\n@skip 2 blank-verso\n@pdf 3\n@page 9\nمتن^[شعر و سخن]^\n"
        report = gate.check(progress, good)
        self.assertEqual(report["missing"], [])
        self.assertEqual(report["unclosed_footnotes"], [])
        self.assertEqual(report["glued_markers"], [])
        self.assertTrue(gate.ok(report))

    def test_progress_without_a_range_is_an_error(self):
        report = gate.check("pdf_pages: 3\n", "@pdf 1\n")
        self.assertIn("error", report)


class LayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = sample_pdf()
        if path is None:
            raise unittest.SkipTest("set MANUSCRIPT_PDF to a scanned book to run layout checks")
        import pymupdf
        cls.doc = pymupdf.open(path)

    def info(self, pdf_index):
        pix = regions.page_pixmap(self.doc[pdf_index - 1])
        return regions.classify(pix), len(self.doc[pdf_index - 1].get_text("text").strip())

    def test_scan_has_no_text_layer_and_known_page_kinds(self):
        self.assertEqual(self.doc.page_count, 217)
        kinds = {}
        for index in (1, 2, 4, 9, 12, 55):
            info, chars = self.info(index)
            kinds[index] = info["kind"]
            self.assertEqual(chars, 0, index)
            self.assertLess(info["width"], 1200)
        self.assertEqual(kinds[1], "cover")
        self.assertEqual(kinds[2], "prose")
        self.assertEqual(kinds[4], "table")
        self.assertEqual(kinds[9], "table")
        self.assertEqual(kinds[12], "prose")
        self.assertEqual(kinds[55], "prose")
        self.assertGreater(self.info(4)[0]["rules"], self.info(12)[0]["rules"])


class CrewTests(unittest.TestCase):
    def test_nine_roles_are_listed_and_the_example_builds(self):
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        agents = sorted((ROOT / "agents").glob("*.md"))
        self.assertEqual(len(agents), 9)
        for path in agents:
            self.assertIn(path.name, skill)
        transcript = (ROOT / "examples" / "page.txt").read_text(encoding="utf-8")
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        src = Path(tmp.name) / "t.txt"
        out = Path(tmp.name) / "out.docx"
        src.write_text(transcript, encoding="utf-8")
        app = composer.Composer()
        app.build(str(src))
        app.finalize(str(out))
        body, notes, _ = docx_texts(out)
        self.assertIn("[ص 9]", body)
        self.assertIn("شعر و سخن", " ".join(notes))
        self.assertIn("[حاشیہ]", " ".join(notes))
        report = gate.check("range: 12-13\n", transcript)
        self.assertTrue(gate.ok(report))


class JobTests(unittest.TestCase):
    """Checks added after a gate passed a page that was only half read."""

    def test_thin_page_is_below_the_median(self):
        full = "کلمہ " * 30
        transcript = (
            "@pdf 1\n@page 1\n" + full + "\n"
            "@pdf 2\n@page 2\n" + full + "\n"
            "@pdf 3\n@page 3\n" + full + "\n"
            "@pdf 8\n@page 8\nصرف یہ۔\n"
        )
        counts = {str(i): 10 for i in (1, 2, 3, 8)}
        report = gate.check("range: 1-8\n", transcript, counts)
        self.assertEqual(report["thin"], [8])
        self.assertFalse(gate.ok(report))
        text = gate.delivery_text(report)
        self.assertTrue(text.startswith("NATAMAM"))

    def test_digit_reversal_is_not_a_repair(self):
        guard = load("textlayer_guard", ROOT / "scripts" / "textlayer_guard.py")
        backwards = guard.assess_layer_digits("2202", "۲۰۲۲")
        self.assertTrue(backwards["reversed"])
        self.assertFalse(backwards["copy"])
        # The layer value from the job. Reversing it does not yield the printed year.
        wrong = guard.assess_layer_digits("20022", "۲۰۲۲")
        self.assertFalse(wrong["reversed"])
        self.assertFalse(wrong["same"])
        self.assertFalse(wrong["copy"])
        self.assertNotEqual(guard.latin_digits("20022")[::-1], guard.latin_digits("۲۰۲۲"))

    def test_cont_pairing(self):
        broken = (ROOT / "examples" / "broken-sentence.txt").read_text(encoding="utf-8")
        report = gate.check("range: 1-2\n", broken)
        self.assertEqual(report["unpaired"], [{"from": 1, "to": 2}])
        paired = broken.replace("@pdf 2\n@page 2\nایک منظم۔\n", "@pdf 2\n@page 2\n@cont ایک منظم۔\n")
        self.assertEqual(gate.check("range: 1-2\n", paired)["unpaired"], [])

    def test_mixed_rtl_and_latin_stay_one_run(self):
        line = "دیکھیے ISBN-10 0-19-853453-1 آخر"
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        src = Path(tmp.name) / "t.txt"
        out = Path(tmp.name) / "out.docx"
        src.write_text("@lang ur\n@pdf 1\n@page 1\n" + line + "\n", encoding="utf-8")
        app = composer.Composer()
        app.build(str(src))
        app.finalize(str(out))
        body, _, _ = docx_texts(out)
        self.assertIn(line, body)

    def test_uncertain_marks_become_highlights_and_comments(self):
        transcript = "@lang ur\n@pdf 1\n@page 1\n{{بت|rest not read}} اور {{|not read}}\n"
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        src = Path(tmp.name) / "t.txt"
        out = Path(tmp.name) / "out.docx"
        src.write_text(transcript, encoding="utf-8")
        app = composer.Composer()
        app.build(str(src))
        app.finalize(str(out))
        with zipfile.ZipFile(out) as z:
            document = z.read("word/document.xml")
            comments = z.read("word/comments.xml") if "word/comments.xml" in z.namelist() else b""
        self.assertEqual(document.count(b"w:highlight"), 2)
        self.assertEqual(comments.count(b"<w:comment "), 2)
        report = gate.check("range: 1-1\n", transcript)
        self.assertEqual(report["uncertain"], 2)

    def test_sheet_marker_and_embedded_ppi(self):
        body, _, _ = ComposerTests.build(self, "@lang ur\n@pdf 1\n@page 1\n@sheet 7 of 9\nعنوان۔\n")
        self.assertIn("[شیٹ 7/9]", body)
        import pymupdf
        doc = pymupdf.open()
        page = doc.new_page(width=595, height=842)
        pix = pymupdf.Pixmap(pymupdf.csGRAY, pymupdf.IRect(0, 0, 1240, 1754), 1)
        pix.clear_with(255)
        page.insert_image(page.rect, pixmap=pix)
        zoom, ppi = regions.render_zoom(page)
        self.assertAlmostEqual(ppi, 150, delta=1)
        self.assertAlmostEqual(zoom, 1240 / 595, delta=0.02)
        rendered = regions.page_pixmap(page)
        self.assertLessEqual(rendered.width, 1240)
        self.assertGreater(rendered.width, 1100)


if __name__ == "__main__":
    unittest.main()

