"""Group sentences into chunks for speech synthesis.

A chunk holds a few sentences from one paragraph (up to ~700 characters), which
gives the voice model enough context for natural phrasing. Headings get their
own chunk. Chunk IDs are c<index>_<first 8 hex digits of the text's SHA-1>.
"""

import hashlib
from dataclasses import dataclass

from readalong.extractor import Sentence

MAX_CHARS = 700


@dataclass(frozen=True)
class Chunk:
    id: str
    text: str
    sentence_ids: list[str]
    para_index: int
    is_heading: bool = False


def _chunk_id(index: int, text: str) -> str:
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]
    return f"c{index:05d}_{digest}"


def _flush(chunks: list[Chunk], group: list[Sentence]) -> None:
    if not group:
        return
    text = " ".join(s.text for s in group)
    chunks.append(
        Chunk(
            _chunk_id(len(chunks), text),
            text,
            [s.id for s in group],
            group[0].para_index,
            group[0].is_heading,
        )
    )


def chunk(sentences: list[Sentence], max_chars: int = MAX_CHARS) -> list[Chunk]:
    chunks: list[Chunk] = []
    group: list[Sentence] = []
    for sentence in sentences:
        breaks_para = group and sentence.para_index != group[-1].para_index
        overflows = (
            group
            and len(" ".join(s.text for s in group)) + 1 + len(sentence.text)
            > max_chars
        )
        if sentence.is_heading or breaks_para or overflows:
            _flush(chunks, group)
            group = []
        group.append(sentence)
        if sentence.is_heading:
            _flush(chunks, group)
            group = []
    _flush(chunks, group)
    return chunks
