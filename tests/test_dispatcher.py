"""Fill step: batching, resuming, progress, and validate-and-retry."""

import pytest

from readalong.cache import AudioCache
from readalong.chunker import Chunk
from readalong.dispatcher import fill


def mkchunk(i, text):
    return Chunk(f"c{i:05d}_cafef00d", text, [f"s{i:05d}_cafef00d"], i, False)


class FakeBatchEngine:
    name = "fakebatch"
    sample_rate = 24000

    def __init__(self):
        self.batches: list[list[str]] = []

    def synthesize_batch(self, texts):
        self.batches.append(list(texts))
        return [f"WAV::{t}".encode() for t in texts]


@pytest.fixture
def cache(tmp_path):
    return AudioCache(tmp_path / "cache")


def test_fill_writes_every_chunk_through_engine_batches(cache):
    chunks = [mkchunk(i, f"Text number {i}.") for i in range(5)]
    engine = FakeBatchEngine()

    result = fill("doc1", chunks, engine, cache, voice="alice", batch_size=2)

    assert result.generated == 5 and result.skipped == 0
    for c in chunks:
        assert cache.has("doc1", "fakebatch", "alice", c.id)
    assert [len(b) for b in engine.batches] == [2, 2, 1]


def test_fill_skips_already_cached_chunks(cache):
    chunks = [mkchunk(i, f"Text {i}.") for i in range(3)]
    cache.write("doc1", "fakebatch", "alice", chunks[1].id, b"already")
    engine = FakeBatchEngine()

    result = fill("doc1", chunks, engine, cache, voice="alice", batch_size=8)

    assert result.generated == 2 and result.skipped == 1
    assert engine.batches == [[chunks[0].text, chunks[2].text]]
    # pre-existing audio untouched
    path = cache.path_for("doc1", "fakebatch", "alice", chunks[1].id)
    assert path.read_bytes() == b"already"


def test_fill_adds_terminal_punctuation_for_synthesis(cache):
    heading = Chunk("c00000_cafef00d", "Results", ["s00000_x"], 0, True)
    normal = Chunk("c00001_cafef00d", "A full sentence.", ["s00001_x"], 1, False)
    engine = FakeBatchEngine()

    fill("doc1", [heading, normal], engine, cache, voice="alice", batch_size=8)

    assert engine.batches == [["Results.", "A full sentence."]]


def test_fill_reports_progress(cache):
    chunks = [mkchunk(i, f"Text {i}.") for i in range(4)]
    seen = []

    fill(
        "doc1",
        chunks,
        FakeBatchEngine(),
        cache,
        voice="alice",
        batch_size=2,
        on_progress=lambda done, total: seen.append((done, total)),
    )

    assert seen == [(2, 4), (4, 4)]


def test_fill_validates_and_retries_failed_chunks(cache):
    chunks = [mkchunk(i, f"Text {i}.") for i in range(3)]
    engine = FakeBatchEngine()
    verdicts = {chunks[1].id: [False, True]}  # fails once, passes on retry

    def validator(chunk, wav_bytes):
        return verdicts.get(chunk.id, [True]).pop(0)

    result = fill(
        "doc1",
        chunks,
        engine,
        cache,
        voice="alice",
        batch_size=8,
        validator=validator,
        max_retries=2,
    )

    assert result.generated == 3
    assert result.retried == 1
    # the retry re-synthesized only the failed chunk
    assert engine.batches[-1] == [chunks[1].text]


def test_fill_gives_up_after_max_retries_and_keeps_last_take(cache):
    chunks = [mkchunk(0, "Cursed text.")]
    engine = FakeBatchEngine()

    result = fill(
        "doc1",
        chunks,
        engine,
        cache,
        voice="alice",
        batch_size=8,
        validator=lambda c, w: False,
        max_retries=2,
    )

    assert result.generated == 1
    assert result.unvalidated == [chunks[0].id]
    assert cache.has("doc1", "fakebatch", "alice", chunks[0].id)
