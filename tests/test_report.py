"""Structure report and the parse_doc.py command."""

import subprocess
import sys
from pathlib import Path

import docx

from readalong.chunker import chunk
from readalong.extractor import Sentence, extract
from readalong.report import format_structure


def test_format_structure_shows_chunks_and_sentences():
    sentences = [
        Sentence("s00000_aaaaaaaa", "Photosynthesis", 0, True),
        Sentence("s00001_bbbbbbbb", "Light reactions come first.", 1, False),
        Sentence("s00002_cccccccc", "The Calvin cycle follows.", 1, False),
    ]
    chunks = chunk(sentences)

    out = format_structure(chunks, sentences, title="demo.docx")

    assert "demo.docx" in out
    assert "2 chunks" in out and "3 sentences" in out
    assert "HEADING" in out
    assert chunks[0].id in out and chunks[1].id in out
    assert "Light reactions come first." in out
    # ASCII only, so any terminal prints it correctly
    assert out.isascii()


def test_parse_doc_cli_prints_structure(tmp_path):
    d = docx.Document()
    d.add_heading("Metabolism", level=1)
    d.add_paragraph("Enzymes lower activation energy. Rates increase.")
    path = tmp_path / "real.docx"
    d.save(path)

    result = subprocess.run(
        [sys.executable, "scripts/parse_doc.py", str(path)],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
    )

    assert result.returncode == 0
    assert "Metabolism" in result.stdout
    assert "Enzymes lower activation energy." in result.stdout
    assert extract(path)[0].text == "Metabolism"  # sanity: same pipeline
