"""Chunker: sentences into paragraph-bounded chunks of up to ~700 characters."""

from readalong.chunker import chunk
from readalong.extractor import Sentence


def sent(i, text, para, heading=False):
    return Sentence(f"s{i:05d}_deadbeef", text, para, heading)


def test_short_paragraph_becomes_one_chunk():
    sentences = [
        sent(0, "First sentence.", 0),
        sent(1, "Second sentence.", 0),
    ]

    chunks = chunk(sentences)

    assert len(chunks) == 1
    assert chunks[0].text == "First sentence. Second sentence."
    assert chunks[0].sentence_ids == [sentences[0].id, sentences[1].id]
    assert chunks[0].id.startswith("c00000_")
    assert len(chunks[0].id) == len("c00000_") + 8


def test_long_paragraph_splits_at_sentence_boundary():
    a = "Alpha " * 60  # ~360 chars
    b = "Beta " * 60  # ~300 chars
    c = "Gamma " * 60
    sentences = [
        sent(0, a.strip() + ".", 0),
        sent(1, b.strip() + ".", 0),
        sent(2, c.strip() + ".", 0),
    ]

    chunks = chunk(sentences, max_chars=700)

    assert len(chunks) == 2
    assert chunks[0].sentence_ids == [sentences[0].id, sentences[1].id]
    assert chunks[1].sentence_ids == [sentences[2].id]
    assert all(len(ch.text) <= 700 for ch in chunks)


def test_single_oversize_sentence_gets_its_own_chunk():
    big = ("Word " * 200).strip() + "."  # ~1000 chars, indivisible
    sentences = [sent(0, big, 0), sent(1, "Tiny tail.", 0)]

    chunks = chunk(sentences, max_chars=700)

    assert chunks[0].sentence_ids == [sentences[0].id]
    assert chunks[1].sentence_ids == [sentences[1].id]


def test_chunks_never_cross_paragraph_boundaries():
    sentences = [
        sent(0, "Para one, short.", 0),
        sent(1, "Para two, also short.", 1),
    ]

    chunks = chunk(sentences)

    assert len(chunks) == 2


def test_heading_is_always_its_own_chunk():
    sentences = [
        sent(0, "Introduction", 0, heading=True),
        sent(1, "Body sentence one.", 1),
        sent(2, "Body sentence two.", 1),
    ]

    chunks = chunk(sentences)

    assert len(chunks) == 2
    assert chunks[0].text == "Introduction"
    assert chunks[0].is_heading is True
    assert chunks[1].is_heading is False


def test_chunk_ids_are_stable_across_runs():
    sentences = [
        sent(0, "Deterministic text.", 0),
        sent(1, "More deterministic text.", 0),
    ]

    first = [c.id for c in chunk(sentences)]
    second = [c.id for c in chunk(sentences)]

    assert first == second
