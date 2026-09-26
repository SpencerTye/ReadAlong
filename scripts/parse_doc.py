"""Print how a .docx will be split into chunks and sentences, before generating audio.

Usage: python scripts/parse_doc.py library/your.docx
The flags turn off the matching filters in readalong.extractor.ExtractOptions.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from readalong.chunker import chunk
from readalong.extractor import ExtractOptions, extract
from readalong.report import format_structure


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("docx_path")
    p.add_argument("--max-chars", type=int, default=700)
    p.add_argument("--keep-tables", action="store_true")
    p.add_argument("--keep-captions", action="store_true")
    p.add_argument("--keep-citations", action="store_true")
    p.add_argument("--no-headings", action="store_true")
    a = p.parse_args()

    options = ExtractOptions(
        skip_tables=not a.keep_tables,
        skip_captions=not a.keep_captions,
        strip_citations=not a.keep_citations,
        read_headings=not a.no_headings,
    )
    sentences = extract(a.docx_path, options)
    chunks = chunk(sentences, max_chars=a.max_chars)
    print(format_structure(chunks, sentences, title=a.docx_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
