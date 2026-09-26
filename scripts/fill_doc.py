"""Generate audio for a whole document and store it in the cache.

Usage: python scripts/fill_doc.py library/your.docx --batch 32
Needs the VibeVoice worker running on localhost:8100.
"""

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from readalong.cache import AudioCache
from readalong.chunker import chunk
from readalong.dispatcher import fill
from readalong.engines import VibeVoiceEngine
from readalong.extractor import extract


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("docx_path")
    p.add_argument("--batch", type=int, default=32)
    p.add_argument("--voice", default="alice")
    p.add_argument("--cache", default="cache")
    a = p.parse_args()

    path = Path(a.docx_path)
    doc = hashlib.sha1(path.read_bytes()).hexdigest()[:16]
    sentences = extract(path)
    chunks = chunk(sentences)
    print(f"doc={doc} chunks={len(chunks)} sentences={len(sentences)}", flush=True)

    engine = VibeVoiceEngine(voice=a.voice)
    cache = AudioCache(a.cache)
    t0 = time.perf_counter()
    result = fill(
        doc,
        chunks,
        engine,
        cache,
        voice=a.voice,
        batch_size=a.batch,
        on_progress=lambda done, total: print(
            f"progress {done}/{total} ({time.perf_counter() - t0:.0f}s)",
            flush=True,
        ),
    )
    wall = time.perf_counter() - t0
    summary = {
        "doc": doc,
        "generated": result.generated,
        "skipped": result.skipped,
        "retried": result.retried,
        "unvalidated": result.unvalidated,
        "wall_s": round(wall, 1),
    }
    print("FILL COMPLETE " + json.dumps(summary), flush=True)
    manifest = {c.id: c.text for c in chunks}
    Path(a.cache, doc, "chunk_texts.json").write_text(
        json.dumps(manifest, indent=1), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
