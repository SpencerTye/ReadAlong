"""HTTP client for the VibeVoice worker (scripts/vibevoice_worker.py).

The worker keeps the model loaded and returns one WAV per text in each batch.
"""

import base64

import httpx


class EngineError(RuntimeError):
    pass


class VibeVoiceEngine:
    name = "vibevoice"
    sample_rate = 24000

    def __init__(
        self,
        base_url: str = "http://localhost:8100",
        voice: str = "alice",
        timeout: float = 600.0,
        transport: httpx.BaseTransport | None = None,
    ):
        self.voice = voice
        self._client = httpx.Client(
            base_url=base_url, timeout=timeout, transport=transport
        )

    def synthesize_batch(self, texts: list[str]) -> list[bytes]:
        try:
            r = self._client.post("/batch", json={"texts": texts, "voice": self.voice})
        except httpx.HTTPError as exc:
            raise EngineError(f"worker unreachable: {exc}") from exc
        if r.status_code != 200:
            detail = ""
            try:
                detail = r.json().get("error", "")
            except ValueError:
                detail = r.text[:200]
            raise EngineError(f"worker error {r.status_code}: {detail}")
        wavs = [base64.b64decode(w) for w in r.json().get("wavs_b64", [])]
        if len(wavs) != len(texts):
            raise EngineError(f"expected {len(texts)} wavs, got {len(wavs)}")
        return wavs
