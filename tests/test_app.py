"""Reader app API: library, opening and filling, audio, progress."""

import docx
import pytest
from fastapi.testclient import TestClient

from readalong.app import create_app
from readalong.cache import AudioCache

from .test_dispatcher import FakeBatchEngine


@pytest.fixture
def library(tmp_path):
    lib = tmp_path / "library"
    lib.mkdir()
    d = docx.Document()
    d.add_paragraph("Abstract")
    d.add_paragraph("First body sentence. Second body sentence.")
    d.save(lib / "paper.docx")
    return lib


@pytest.fixture
def client(library, tmp_path):
    app = create_app(
        library_dir=library,
        cache=AudioCache(tmp_path / "cache"),
        engine=FakeBatchEngine(),
        voice="alice",
        fill_in_background=False,
    )
    return TestClient(app)


def test_library_lists_docx_files(client):
    r = client.get("/api/library")

    assert r.status_code == 200
    assert r.json() == {"documents": ["paper.docx"]}


def test_open_parses_and_fills_and_serves_audio(client):
    r = client.post("/api/open", json={"filename": "paper.docx"})

    assert r.status_code == 200
    body = r.json()
    assert body["chunks"], "expected parsed chunks"
    doc = body["doc"]
    chunk_id = body["chunks"][0]["id"]

    progress = client.get(f"/api/progress/{doc}").json()
    assert progress["state"] == "complete"
    assert progress["done"] == progress["total"] > 0

    audio = client.get(f"/api/audio/{doc}/{chunk_id}")
    assert audio.status_code == 200
    assert audio.content.startswith(b"WAV::")


def test_audio_404_when_not_yet_generated(client):
    r = client.post("/api/open", json={"filename": "paper.docx", "fill": False})
    doc = r.json()["doc"]
    chunk_id = r.json()["chunks"][0]["id"]

    audio = client.get(f"/api/audio/{doc}/{chunk_id}")

    assert audio.status_code == 404


def test_open_missing_file_is_404(client):
    r = client.post("/api/open", json={"filename": "nope.docx"})

    assert r.status_code == 404


def test_root_serves_reader_page(client):
    r = client.get("/")

    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "readalong" in r.text.lower()


def test_status_reports_engine(client):
    r = client.get("/api/status")

    assert r.status_code == 200
    assert r.json()["engine"] == "fakebatch"
