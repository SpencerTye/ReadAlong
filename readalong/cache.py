"""Permanent per-chunk audio cache: cache/<doc>/<engine>/<voice>/<chunk>.wav.

Writes are atomic (.part then os.replace) so a crash mid-write can never
leave a truncated WAV that playback or resume logic would trust.
"""

import os
from pathlib import Path


class AudioCache:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def path_for(self, doc_hash: str, engine: str, voice: str, chunk_id: str) -> Path:
        return self.root / doc_hash / engine / voice / f"{chunk_id}.wav"

    def has(self, doc_hash: str, engine: str, voice: str, chunk_id: str) -> bool:
        return self.path_for(doc_hash, engine, voice, chunk_id).exists()

    def write(
        self, doc_hash: str, engine: str, voice: str, chunk_id: str, data: bytes
    ) -> Path:
        final = self.path_for(doc_hash, engine, voice, chunk_id)
        final.parent.mkdir(parents=True, exist_ok=True)
        part = final.with_suffix(".wav.part")
        try:
            part.write_bytes(data)
            os.replace(part, final)
        finally:
            part.unlink(missing_ok=True)
        return final
