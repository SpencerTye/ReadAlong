"""Extractor: .docx into ordered sentences with stable IDs."""

import docx

from readalong.extractor import extract


def make_docx(path, paragraphs):
    d = docx.Document()
    for text in paragraphs:
        d.add_paragraph(text)
    d.save(path)
    return path


def test_headings_are_read_and_flagged(tmp_path):
    d = docx.Document()
    d.add_heading("Cellular Respiration", level=1)
    d.add_paragraph("Glycolysis occurs in the cytosol.")
    path = tmp_path / "doc.docx"
    d.save(path)

    sentences = extract(path)

    assert [s.text for s in sentences] == [
        "Cellular Respiration",
        "Glycolysis occurs in the cytosol.",
    ]
    assert sentences[0].is_heading is True
    assert sentences[1].is_heading is False


def test_bracketed_numeric_citations_are_stripped(tmp_path):
    path = make_docx(
        tmp_path / "doc.docx",
        [
            "The effect was replicated [12] across cohorts [3,5] and "
            "confirmed [7-9], then extended [ 14 ].",
        ],
    )

    sentences = extract(path)

    assert sentences[0].text == (
        "The effect was replicated across cohorts and confirmed, then extended."
    )


def make_docx_with_table(path):
    d = docx.Document()
    d.add_paragraph("Before the table.")
    table = d.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Cell alpha."
    table.cell(0, 1).text = "Cell beta."
    d.add_paragraph("After the table.")
    d.save(path)
    return path


def test_tables_are_skipped_by_default(tmp_path):
    path = make_docx_with_table(tmp_path / "doc.docx")

    texts = [s.text for s in extract(path)]

    assert texts == ["Before the table.", "After the table."]


def test_tables_included_when_toggle_off(tmp_path):
    from readalong.extractor import ExtractOptions

    path = make_docx_with_table(tmp_path / "doc.docx")

    texts = [s.text for s in extract(path, ExtractOptions(skip_tables=False))]

    assert texts == [
        "Before the table.",
        "Cell alpha.",
        "Cell beta.",
        "After the table.",
    ]


def make_docx_with_captions(path):
    d = docx.Document()
    d.add_paragraph("A real sentence.")
    d.add_paragraph("Figure 3. Mitochondrial complexes diagram")
    d.add_paragraph("Table 2: Summary of cohorts")
    d.add_paragraph("A styled caption", style="Caption")
    d.add_paragraph("Another real sentence.")
    d.save(path)
    return path


def test_figure_and_table_captions_skipped_by_default(tmp_path):
    path = make_docx_with_captions(tmp_path / "doc.docx")

    texts = [s.text for s in extract(path)]

    assert texts == ["A real sentence.", "Another real sentence."]


def test_captions_kept_when_toggle_off(tmp_path):
    from readalong.extractor import ExtractOptions

    path = make_docx_with_captions(tmp_path / "doc.docx")

    texts = [s.text for s in extract(path, ExtractOptions(skip_captions=False))]

    assert "Table 2: Summary of cohorts" in texts
    assert "A styled caption" in texts


def test_headings_dropped_when_toggle_off(tmp_path):
    from readalong.extractor import ExtractOptions

    d = docx.Document()
    d.add_heading("Chapter One", level=1)
    d.add_paragraph("Body text here.")
    path = tmp_path / "doc.docx"
    d.save(path)

    texts = [s.text for s in extract(path, ExtractOptions(read_headings=False))]

    assert texts == ["Body text here."]


def test_citations_kept_when_toggle_off(tmp_path):
    from readalong.extractor import ExtractOptions

    path = make_docx(tmp_path / "doc.docx", ["Replicated [12] broadly."])

    texts = [s.text for s in extract(path, ExtractOptions(strip_citations=False))]

    assert texts == ["Replicated [12] broadly."]


def test_unspeakable_fragments_dropped(tmp_path):
    path = make_docx(
        tmp_path / "doc.docx",
        [
            "***",
            "- - -",
            "5.",
            "Real words here.",
        ],
    )

    texts = [s.text for s in extract(path)]

    assert texts == ["Real words here."]


def test_malformed_paragraph_skipped_never_fatal(tmp_path, monkeypatch, caplog):
    import readalong.extractor as ex

    path = make_docx(
        tmp_path / "doc.docx",
        [
            "Good opening sentence.",
            "TRIGGER-MALFORMED",
            "Good closing sentence.",
        ],
    )
    real = ex._strip_citations

    def boom(text):
        if "TRIGGER-MALFORMED" in text:
            raise ValueError("synthetic parse failure")
        return real(text)

    monkeypatch.setattr(ex, "_strip_citations", boom)

    with caplog.at_level("WARNING"):
        texts = [s.text for s in extract(path)]

    assert texts == ["Good opening sentence.", "Good closing sentence."]
    assert any("skip" in r.message.lower() for r in caplog.records)


def test_front_matter_before_abstract_dropped(tmp_path):
    path = make_docx(
        tmp_path / "doc.docx",
        [
            "A Long Paper Title About Mitochondria",
            "Jane Q. Author, John R. Author",
            "1Department of Somewhere, University of Elsewhere",
            "Abstract",
            "We studied a thing carefully.",
        ],
    )

    texts = [s.text for s in extract(path)]

    assert texts == ["Abstract", "We studied a thing carefully."]


def test_everything_from_references_on_dropped(tmp_path):
    path = make_docx(
        tmp_path / "doc.docx",
        [
            "Discussion",
            "Our findings suggest caution.",
            "References",
            "Smith, J., 2020. A cited work. Journal of Things 5, 1-10.",
        ],
    )

    texts = [s.text for s in extract(path)]

    assert texts == ["Discussion", "Our findings suggest caution."]


def test_acknowledgements_section_dropped_until_next_title(tmp_path):
    path = make_docx(
        tmp_path / "doc.docx",
        [
            "Results",
            "The effect was large.",
            "Acknowledgements",
            "We thank the funding agency for grant R01-123456.",
            "Appendix A",
            "Supplemental derivation text here.",
        ],
    )

    texts = [s.text for s in extract(path)]

    assert texts == [
        "Results",
        "The effect was large.",
        "Appendix A",
        "Supplemental derivation text here.",
    ]


def test_figure_legends_section_dropped_with_captions(tmp_path):
    path = make_docx(
        tmp_path / "doc.docx",
        [
            "Results",
            "The effect was found.",
            "Figure Legends",
            "Figure 1. A diagram of the pathway.",
            "Figure 2. Another diagram.",
        ],
    )

    texts = [s.text for s in extract(path)]

    assert texts == ["Results", "The effect was found."]


def test_paper_section_filters_can_be_disabled(tmp_path):
    from readalong.extractor import ExtractOptions

    path = make_docx(
        tmp_path / "doc.docx",
        [
            "Title Line Here",
            "Abstract",
            "Body sentence.",
            "Acknowledgements",
            "Thanks all.",
            "References",
            "Smith, J., 2020. Work.",
        ],
    )
    options = ExtractOptions(
        skip_front_matter=False,
        stop_at_references=False,
        skip_acknowledgements=False,
    )

    texts = [s.text for s in extract(path, options)]

    assert "Title Line Here" in texts
    assert "Thanks all." in texts
    assert "Smith" in " ".join(texts)


def test_extracts_sentences_in_order_with_stable_ids(tmp_path):
    path = make_docx(
        tmp_path / "doc.docx",
        [
            "The mitochondrion produces ATP. It also regulates apoptosis.",
            "A second paragraph follows.",
        ],
    )

    sentences = extract(path)

    texts = [s.text for s in sentences]
    assert texts == [
        "The mitochondrion produces ATP.",
        "It also regulates apoptosis.",
        "A second paragraph follows.",
    ]
    # stable id: s<5-digit index>_<8 hex chars of sha1(text)>
    assert sentences[0].id.startswith("s00000_")
    assert len(sentences[0].id) == len("s00000_") + 8
    # same input -> identical ids on re-extract
    assert [s.id for s in extract(path)] == [s.id for s in sentences]
    # sentences remember which paragraph they came from
    assert sentences[0].para_index == 0
    assert sentences[1].para_index == 0
    assert sentences[2].para_index == 1
