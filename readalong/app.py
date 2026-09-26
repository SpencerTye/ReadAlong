"""FastAPI app that parses documents, generates their audio and serves the reader page.

create_app takes the engine, cache and library folder as arguments, so the tests
run the whole app against a fake engine. scripts/serve.py passes the real client.
"""

import hashlib
import threading
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from readalong.cache import AudioCache
from readalong.chunker import Chunk, chunk as make_chunks
from readalong.dispatcher import fill
from readalong.extractor import extract

_PAGE = Path(__file__).with_name("static") / "reader.html"


@dataclass
class DocState:
    filename: str
    chunks: list[Chunk]
    total: int
    done: int = 0
    state: str = "idle"  # idle | filling | complete
    unvalidated: list[str] = field(default_factory=list)


class OpenRequest(BaseModel):
    filename: str
    fill: bool = True


def _doc_hash(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()[:16]


def create_app(
    library_dir: str | Path,
    cache: AudioCache,
    engine,
    voice: str = "alice",
    batch_size: int = 32,
    fill_in_background: bool = True,
) -> FastAPI:
    library = Path(library_dir)
    app = FastAPI(title="ReadAlong")
    docs: dict[str, DocState] = {}

    def run_fill(doc: str) -> None:
        st = docs[doc]
        st.state = "filling"

        def on_progress(done: int, total: int) -> None:
            st.done = st.total - total + done if total else st.total

        try:
            result = fill(
                doc,
                st.chunks,
                engine,
                cache,
                voice=voice,
                batch_size=batch_size,
                on_progress=on_progress,
            )
            st.unvalidated = result.unvalidated
            st.done = st.total
            st.state = "complete"
        except Exception as exc:  # surface, never crash the app
            st.state = f"error: {type(exc).__name__}: {exc}"

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return _PAGE.read_text(encoding="utf-8")

    @app.get("/api/library")
    def api_library() -> dict:
        names = sorted(p.name for p in library.glob("*.docx"))
        return {"documents": names}

    @app.post("/api/open")
    def api_open(req: OpenRequest) -> dict:
        path = library / req.filename
        if not path.is_file():
            raise HTTPException(404, f"not in library: {req.filename}")
        doc = _doc_hash(path)
        if doc not in docs:
            sentences = extract(path)
            chunks = make_chunks(sentences)
            docs[doc] = DocState(req.filename, chunks, total=len(chunks))
        st = docs[doc]
        cached = sum(1 for c in st.chunks if cache.has(doc, engine.name, voice, c.id))
        st.done = cached
        if cached == st.total and st.total > 0:
            st.state = "complete"
        if req.fill and st.state not in ("filling", "complete"):
            if fill_in_background:
                threading.Thread(target=run_fill, args=(doc,), daemon=True).start()
            else:
                run_fill(doc)
        return {
            "doc": doc,
            "filename": st.filename,
            "chunks": [
                {
                    "id": c.id,
                    "text": c.text,
                    "para_index": c.para_index,
                    "is_heading": c.is_heading,
                }
                for c in st.chunks
            ],
        }

    @app.get("/api/audio/{doc}/{chunk_id}")
    def api_audio(doc: str, chunk_id: str) -> FileResponse:
        path = cache.path_for(doc, engine.name, voice, chunk_id)
        if not path.exists():
            raise HTTPException(404, "chunk audio not generated yet")
        return FileResponse(path, media_type="audio/wav")

    @app.get("/api/progress/{doc}")
    def api_progress(doc: str) -> dict:
        st = docs.get(doc)
        if st is None:
            raise HTTPException(404, "document not opened")
        return {
            "state": st.state,
            "done": st.done,
            "total": st.total,
            "unvalidated": st.unvalidated,
        }

    @app.get("/api/status")
    def api_status() -> dict:
        return {"engine": engine.name, "voice": voice}

    return app
