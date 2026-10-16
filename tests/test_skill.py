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
def nastaliq_pdf():
    """A real A4 scan of Nastaliq print, ten text pages or more, above ~220 ppi."""
    candidates = []
    if os.environ.get("NASTALIQ_PDF"):
        candidates.append(Path(os.environ["NASTALIQ_PDF"]))
    candidates.append(ROOT / "samples" / "nastaliq.pdf")
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


class LedgerTests(unittest.TestCase):
    """Failure modes of a transcript assembled by hand from a chat."""

    def run_gate(self, transcript, progress="range: 1-3\n", pdf_pages=None):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        work = Path(tmp.name)
        (work / "progress.md").write_text(progress, encoding="utf-8")
        (work / "transcript.txt").write_text(transcript, encoding="utf-8")
        argv = ["gate.py", str(work / "progress.md"), str(work / "transcript.txt")]
        if pdf_pages is not None:
            import pymupdf
            doc = pymupdf.open()
            for _ in range(pdf_pages):
                doc.new_page(width=595, height=842)
            doc.save(work / "book.pdf")
            argv.append(str(work / "book.pdf"))
        code = gate.main(argv)
        return code, (work / "delivery.md").read_text(encoding="utf-8")

    GOOD = "@pdf 1\n@page 1\nعنوان\n@skip 2 blank-verso\n@pdf 3\n@page 9\nمتن۔\n"

    def test_existing_exit_codes_are_unchanged(self):
        code, text = self.run_gate(self.GOOD)
        self.assertEqual(code, 0)
        self.assertTrue(text.startswith("CLAIMED"))
        code, text = self.run_gate(self.GOOD, pdf_pages=3)
        self.assertEqual(code, 0)
        code, text = self.run_gate("@pdf 1\n@page 1\nعنوان\n@skip 2 blank-verso\n")
        self.assertEqual(code, 2)
        self.assertTrue(text.startswith("NATAMAM"))

    def test_duplicated_page_fails(self):
        pasted_twice = self.GOOD + "@pdf 3\n@page 9\nمتن۔\n"
        report = gate.check("range: 1-3\n", pasted_twice)
        self.assertEqual(report["missing"], [])
        self.assertEqual(report["duplicates"], [3])
        self.assertFalse(gate.ok(report))
        self.assertEqual(self.run_gate(pasted_twice)[0], 2)
        skipped_and_read = "@skip 1 cover\n" + self.GOOD
        self.assertEqual(gate.check("range: 1-3\n", skipped_and_read)["duplicates"], [1])

    def test_index_the_pdf_does_not_have_fails_when_the_pdf_is_given(self):
        invented = self.GOOD + "@pdf 4\n@page 10\nمتن۔\n"
        report = gate.check("range: 1-3\n", invented)
        self.assertEqual(report["out_of_range"], [])
        self.assertIsNone(report["pdf_pages"])
        self.assertIn("PDF_CHECK not run", gate.delivery_text(report))
        report = gate.check("range: 1-3\n", invented, pdf_pages=3)
        self.assertEqual(report["out_of_range"], [4])
        self.assertFalse(gate.ok(report))
        code, text = self.run_gate(invented, pdf_pages=3)
        self.assertEqual(code, 2)
        self.assertIn("out_of_range: [4]", text)

    def test_bare_pdf_fails(self):
        bare = "@pdf 1\n@page 1\nعنوان\n@skip 2 blank-verso\n@pdf 3\n@page 9\n"
        report = gate.check("range: 1-3\n", bare)
        self.assertEqual(report["missing"], [])
        self.assertEqual(report["bare"], [3])
        self.assertFalse(gate.ok(report))
        self.assertEqual(self.run_gate(bare)[0], 2)
        self.assertEqual(gate.check("range: 1-1\n", "@pdf 1\n")["bare"], [1])
        table = "@pdf 1\n@page 1\n@row 2 ||| اظہارِ خیال ||| 18\n"
        self.assertEqual(gate.check("range: 1-1\n", table)["bare"], [])


class RepeatTests(unittest.TestCase):
    """PDF 21 came back with a clause read twice, fluent and unmarked."""

    CLAUSE = "اور جو شخص اپنی کاہلی سے نماز میں دیر کرے وہ گنہگار ہے"

    def test_eight_word_run_repeated_in_one_page_is_flagged(self):
        transcript = (
            "@lang ur\n@pdf 21\n@page 19\n"
            "فرمایا " + self.CLAUSE + " اور پھر " + self.CLAUSE + "۔\n"
        )
        report = gate.check("range: 21-21\n", transcript)
        self.assertEqual([r["pdf"] for r in report["repeated"]], [21])
        self.assertIn("کاہلی", report["repeated"][0]["words"])
        # Flag for re-read. A book can repeat itself, so it does not fail the gate.
        self.assertTrue(gate.ok(report))
        self.assertIn("REPEATED pdf 21", gate.delivery_text(report))

    def test_repeat_across_lines_and_a_quote_is_flagged(self):
        transcript = "@pdf 21\n@page 19\n" + self.CLAUSE + "\n@quote " + self.CLAUSE + "\n"
        self.assertEqual(len(gate.check("range: 21-21\n", transcript)["repeated"]), 1)

    def test_ordinary_pages_stay_quiet(self):
        example = (ROOT / "examples" / "page.txt").read_text(encoding="utf-8")
        self.assertEqual(gate.check("range: 12-13\n", example)["repeated"], [])
        seven = " ".join(self.CLAUSE.split()[:7])
        short = "@pdf 1\n@page 1\n" + seven + " پھر " + seven + "۔\n"
        self.assertEqual(gate.check("range: 1-1\n", short)["repeated"], [])
        # The same clause on two different pages is not this failure.
        apart = "@pdf 21\n@page 19\n" + self.CLAUSE + "\n@pdf 23\n@page 21\n" + self.CLAUSE + "\n"
        self.assertEqual(gate.check("range: 21-23\n", apart + "@skip 22 x\n")["repeated"], [])

    def test_ink_rule_is_in_the_skill(self):
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Never output the same sentence twice", skill)


class ProgressTests(unittest.TestCase):
    def test_range_comes_from_the_page_count(self):
        progress = load("init_progress", ROOT / "scripts" / "init_progress.py")
        text = progress.progress_text("", 217)
        self.assertIn("range: 1-217\n", text)
        self.assertIn("pdf_pages: 217\n", text)
        kept = progress.progress_text("range: 1-200\npdf_pages: 200\nheader_once: x\n", 217, 12, 26)
        self.assertIn("range: 12-26\n", kept)
        self.assertIn("pdf_pages: 217\n", kept)
        self.assertIn("header_once: x", kept)
        self.assertNotIn("1-200", kept)
        with self.assertRaises(ValueError):
            progress.progress_text("", 217, 1, 220)

    def test_script_reads_the_pdf(self):
        import pymupdf
        progress = load("init_progress", ROOT / "scripts" / "init_progress.py")
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        work = Path(tmp.name)
        doc = pymupdf.open()
        for _ in range(5):
            doc.new_page(width=595, height=842)
        doc.save(work / "book.pdf")
        self.assertEqual(progress.main(["x", str(work / "book.pdf"), str(work / "progress.md")]), 0)
        text = (work / "progress.md").read_text(encoding="utf-8")
        self.assertIn("range: 1-5", text)
        self.assertTrue(gate.ok(gate.check(text, "".join(f"@skip {i} blank\n" for i in range(1, 6)))))


class SplitTests(unittest.TestCase):
    """The split arithmetic, on ink profiles. The images are in ReaderCropTests."""

    def framed(self, rows=200, quiet_at=(96, 104)):
        # A printed frame down both margins puts a floor of 5 under every row.
        # Measured: floor 5 on a page whose typical row was 22.
        ink = [22 if (y // 6) % 4 else 9 for y in range(rows)]
        for y in range(*quiet_at):
            ink[y] = 5
        return ink

    def test_cut_is_the_centre_of_the_quiet_run_above_the_frame_floor(self):
        ink = self.framed()
        band = ink[60:140]
        # A fraction of the median alone sits under the floor and finds nothing.
        self.assertLess(0.12 * sorted(band)[len(band) // 2], min(band))
        self.assertNotIn(0, band)
        self.assertEqual(regions.quiet_cut(ink), 100)

    def test_no_quiet_band_means_no_split(self):
        self.assertIsNone(regions.quiet_cut([22] * 200))
        one_row = self.framed(quiet_at=(100, 101))
        one_row = [max(v, 9) for v in one_row]
        one_row[100] = 5
        self.assertIsNone(regions.quiet_cut(one_row))

    def test_only_a_crop_over_the_cap_splits(self):
        import pymupdf
        body = pymupdf.Rect(0, 76, 595, 842)
        self.assertTrue(regions.needs_split(body, 300 / 72))
        self.assertFalse(regions.needs_split(body, 150 / 72))
        self.assertFalse(regions.needs_split(pymupdf.Rect(0, 0, 595, 300), 300 / 72))
        zoom = regions.capped_zoom(400 / 72, body)
        self.assertLessEqual(766 * zoom, regions.VISION_CAP + 0.5)

    def test_layout_record_keeps_a_single_path_for_an_unsplit_crop(self):
        info = {"kind": "prose", "regions": {"header": "h.png", "body": "b.png", "full": "f.png"}}
        self.assertEqual(regions.layout_record(info, 12)["body"], "b.png")
        info["regions"] = {"header": "h.png", "body_a": "a.png", "body_b": "b.png", "full": "f.png"}
        self.assertEqual(regions.layout_record(info, 12)["body"], ["a.png", "b.png"])

    def test_spread_image_ppi_uses_its_own_box(self):
        import pymupdf
        doc = pymupdf.open()
        page = doc.new_page(width=370, height=570)
        pix = pymupdf.Pixmap(pymupdf.csGRAY, pymupdf.IRect(0, 0, 1540, 1188), 0)
        pix.clear_with(255)
        # One scan of a two-page spread, shown on a page half its width.
        page.insert_image(pymupdf.Rect(-370, 0, 370, 570), pixmap=pix, keep_proportion=False)
        self.assertAlmostEqual(regions.embedded_ppi(page), 1540 / (740 / 72), delta=2)


class ReaderCropTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = nastaliq_pdf()
        if path is None:
            raise unittest.SkipTest(
                "no real scanned A4 Nastaliq PDF on this machine: set NASTALIQ_PDF "
                "(ten text pages, above ~220 ppi). A synthetic page would only prove "
                "that the synthetic page was synthesised."
            )
        import pymupdf
        cls.pymupdf = pymupdf
        cls.doc = pymupdf.open(path)
        cls.tmp = tempfile.TemporaryDirectory()
        cls.infos = {}
        for index in range(1, 11):
            cls.infos[index] = regions.save_regions(cls.doc[index - 1], cls.tmp.name, index)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def size(self, path):
        pix = self.pymupdf.Pixmap(path)
        return pix.width, pix.height

    def test_reader_crop_is_over_three_times_72_dpi_and_classify_stays_at_72(self):
        seen = []
        original = regions.classify
        def spy(pix):
            seen.append(pix.width)
            return original(pix)
        regions.classify = spy
        try:
            info = regions.save_regions(self.doc[0], self.tmp.name, 101)
        finally:
            regions.classify = original
        page_width = round(self.doc[0].rect.width)
        self.assertEqual(seen, [page_width])
        self.assertEqual(info["width"], page_width)
        for name, path in info["regions"].items():
            # Every crop spans the page width, so width / page width is the scale.
            width, _height = self.size(path)
            self.assertGreater(width, 3 * page_width, name)

    def test_every_page_splits_through_a_quiet_row(self):
        for index, info in self.infos.items():
            self.assertIsInstance(info.get("split"), dict, index)
            self.assertIn("body_a", info["regions"])
            self.assertIn("body_b", info["regions"])
            self.assertNotIn("body", info["regions"])
            page = self.doc[index - 1]
            top = info["split"]["top"]
            clip = self.pymupdf.Rect(page.rect.x0, page.rect.y0 + top, page.rect.x1, page.rect.y1)
            scale = regions.SPLIT_DPI / 72
            pix = page.get_pixmap(
                matrix=self.pymupdf.Matrix(scale, scale), clip=clip,
                alpha=False, colorspace=self.pymupdf.csGRAY,
            )
            ink = regions.row_ink(pix)
            band = sorted(ink[int(len(ink) * 0.30):int(len(ink) * 0.70)])
            quietest_quarter = band[len(band) // 4]
            self.assertLessEqual(ink[info["split"]["row"]], quietest_quarter, index)

    def test_halves_fit_the_cap(self):
        for index, info in self.infos.items():
            for name in ("body_a", "body_b"):
                self.assertLessEqual(max(self.size(info["regions"][name])), regions.VISION_CAP, index)
            record = regions.layout_record(info, index)
            self.assertEqual(record["body"], [info["regions"]["body_a"], info["regions"]["body_b"]])

    def test_a_crop_under_the_cap_is_not_split(self):
        original = regions.VISION_CAP
        regions.VISION_CAP = 100000
        try:
            info = regions.save_regions(self.doc[0], self.tmp.name, 102)
        finally:
            regions.VISION_CAP = original
        self.assertNotIn("split", info)
        self.assertIsInstance(regions.layout_record(info, 102)["body"], str)


if __name__ == "__main__":
    unittest.main()

