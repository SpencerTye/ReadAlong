"""Plain-text report of how a document was split into chunks and sentences."""

from readalong.chunker import Chunk
from readalong.extractor import Sentence


def format_structure(chunks: list[Chunk], sentences: list[Sentence], title: str) -> str:
    by_id = {s.id: s.text for s in sentences}
    lines = [
        f"Document: {title}",
        f"{len(chunks)} chunks, {len(sentences)} sentences",
        "",
    ]
    for c in chunks:
        tag = " HEADING" if c.is_heading else ""
        lines.append(
            f"[{c.id}]{tag} para {c.para_index}, "
            f"{len(c.sentence_ids)} sentence(s), {len(c.text)} chars"
        )
        for sid in c.sentence_ids:
            lines.append(f"    {sid}  {by_id.get(sid, '<missing>')}")
        lines.append("")
    text = "\n".join(lines)
    return text.encode("ascii", errors="replace").decode("ascii")
