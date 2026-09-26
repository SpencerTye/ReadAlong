"""Extract ordered, stably-identified sentences from a .docx document."""

import hashlib
import logging
import re
from dataclasses import dataclass
from pathlib import Path

import docx
import pysbd

logger = logging.getLogger(__name__)

_SEGMENTER = pysbd.Segmenter(language="en", clean=False)

# Bracketed numeric citations: [12], [3,5], [7-9], [ 14 ], [1, 2-4].
_CITATION_RE = re.compile(r"\s*\[\s*\d+(?:\s*[,–-]\s*\d+)*\s*\]")

# "Figure 3." / "Fig. 2" / "Table 12:" openers mark caption paragraphs.
_CAPTION_RE = re.compile(r"^\s*(figure|fig\.|table)\s*\d+", re.IGNORECASE)

# A fragment must contain at least one letter to be worth speaking.
_SPEAKABLE_RE = re.compile(r"[A-Za-z]")


def _strip_citations(text: str) -> str:
    text = _CITATION_RE.sub("", text)
    text = re.sub(r"\s{2,}", " ", text)
    return re.sub(r"\s+([.,;:!?])", r"\1", text).strip()


@dataclass(frozen=True)
class ExtractOptions:
    skip_tables: bool = True
    skip_captions: bool = True
    strip_citations: bool = True
    read_headings: bool = True
    # Filters for scientific papers. Each one applies only when its section
    # heading is present, so other documents pass through unchanged.
    skip_front_matter: bool = True
    stop_at_references: bool = True
    skip_acknowledgements: bool = True


_ABSTRACT = {"abstract"}
_REFERENCES = {"references", "bibliography"}
_ACKNOWLEDGE = {"acknowledgements", "acknowledgments"}
_CAPTION_SECTIONS = {"figure legends", "figure captions", "table legends"}


def _is_section_title(text: str) -> bool:
    t = text.strip()
    return (
        0 < len(t) <= 60
        and len(t.split()) <= 6
        and not t.endswith((".", "!", "?", ",", ";", ":"))
    )


@dataclass(frozen=True)
class Sentence:
    id: str
    text: str
    para_index: int
    is_heading: bool = False


def _sentence_id(index: int, text: str) -> str:
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]
    return f"s{index:05d}_{digest}"


def _iter_paragraphs(document, options: ExtractOptions):
    """Yield block-level paragraphs in document order, honoring toggles."""
    for block in document.iter_inner_content():
        if isinstance(block, docx.table.Table):
            if options.skip_tables:
                continue
            for row in block.rows:
                for cell in row.cells:
                    yield from cell.paragraphs
        else:
            yield block


def extract(path: str | Path, options: ExtractOptions | None = None) -> list[Sentence]:
    options = options or ExtractOptions()
    document = docx.Document(str(path))

    def title_of(paragraph) -> str | None:
        text = paragraph.text.strip()
        return text.lower() if _is_section_title(text) else None

    has_abstract = options.skip_front_matter and any(
        title_of(p) in _ABSTRACT for p in _iter_paragraphs(document, options)
    )

    def starts_skipped_section(title: str | None) -> bool:
        return (options.skip_acknowledgements and title in _ACKNOWLEDGE) or (
            options.skip_captions and title in _CAPTION_SECTIONS
        )

    sentences: list[Sentence] = []
    started = not has_abstract
    in_skipped_section = False
    for para_index, paragraph in enumerate(_iter_paragraphs(document, options)):
        try:
            title = title_of(paragraph)
            if not started:
                if title in _ABSTRACT:
                    started = True
                else:
                    continue
            if options.stop_at_references and title in _REFERENCES:
                break
            if in_skipped_section:
                if title is not None and not starts_skipped_section(title):
                    in_skipped_section = False
                else:
                    continue
            if starts_skipped_section(title):
                in_skipped_section = True
                continue
            style_name = (paragraph.style.name if paragraph.style else "") or ""
            is_heading = style_name.startswith("Heading") or style_name == "Title"
            raw = paragraph.text
            if is_heading and not options.read_headings:
                continue
            if options.skip_captions and (
                style_name == "Caption" or _CAPTION_RE.match(raw)
            ):
                continue
            cleaned = _strip_citations(raw) if options.strip_citations else raw
            for text in _SEGMENTER.segment(cleaned):
                text = text.strip()
                if not text or not _SPEAKABLE_RE.search(text):
                    continue
                sentences.append(
                    Sentence(
                        _sentence_id(len(sentences), text),
                        text,
                        para_index,
                        is_heading,
                    )
                )
        except Exception:
            logger.warning("skipping malformed paragraph %d", para_index, exc_info=True)
    return sentences
