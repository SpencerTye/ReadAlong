"""Audio cache: file layout, atomic writes and existence checks."""

import os

import pytest

from readalong.cache import AudioCache


@pytest.fixture
def cache(tmp_path):
    return AudioCache(tmp_path / "cache")


def test_write_then_read_back_at_layout_path(cache, tmp_path):
    path = cache.write("doc1", "vibevoice", "alice", "c00000_ab12cd34", b"RIFFdata")

    assert path == (
        tmp_path / "cache" / "doc1" / "vibevoice" / "alice" / "c00000_ab12cd34.wav"
    )
    assert path.read_bytes() == b"RIFFdata"


def test_has_flips_after_write(cache):
    key = ("doc1", "vibevoice", "alice", "c00001_ffffffff")

    assert cache.has(*key) is False
    cache.write(*key, b"x")
    assert cache.has(*key) is True


def test_write_is_atomic_no_part_files_remain(cache):
    path = cache.write("doc1", "vibevoice", "alice", "c00002_12345678", b"abc")

    leftovers = list(path.parent.glob("*.part"))
    assert leftovers == []


def test_interrupted_write_leaves_no_final_file(cache, monkeypatch):
    def boom(src, dst):
        raise OSError("simulated crash mid-replace")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        cache.write("doc1", "vibevoice", "alice", "c00003_deadbeef", b"abc")
    monkeypatch.undo()

    assert cache.has("doc1", "vibevoice", "alice", "c00003_deadbeef") is False
    # and a later clean write succeeds
    cache.write("doc1", "vibevoice", "alice", "c00003_deadbeef", b"abc")
    assert cache.has("doc1", "vibevoice", "alice", "c00003_deadbeef") is True
