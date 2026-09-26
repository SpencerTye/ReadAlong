"""VibeVoice client, tested against a mock worker."""

import base64
import json

import httpx
import pytest

from readalong.engines import EngineError, VibeVoiceEngine


def fake_worker(handler):
    """VibeVoiceEngine connected to an in-memory mock worker."""
    transport = httpx.MockTransport(handler)
    return VibeVoiceEngine(
        base_url="http://localhost:8100",
        transport=transport,
    )


def test_synthesize_batch_posts_texts_and_returns_wavs_in_order():
    seen = {}

    def handler(request):
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        wavs = [
            base64.b64encode(f"WAV-{i}".encode()).decode()
            for i in range(len(seen["body"]["texts"]))
        ]
        return httpx.Response(200, json={"wavs_b64": wavs})

    engine = fake_worker(handler)

    out = engine.synthesize_batch(["First text.", "Second text."])

    assert seen["path"] == "/batch"
    assert seen["body"]["texts"] == ["First text.", "Second text."]
    assert out == [b"WAV-0", b"WAV-1"]


def test_worker_error_raises_engine_error_with_detail():
    def handler(request):
        return httpx.Response(500, json={"error": "CUDA exploded"})

    engine = fake_worker(handler)

    with pytest.raises(EngineError, match="CUDA exploded"):
        engine.synthesize_batch(["Text."])


def test_count_mismatch_is_an_engine_error():
    def handler(request):
        return httpx.Response(200, json={"wavs_b64": []})

    engine = fake_worker(handler)

    with pytest.raises(EngineError, match="expected 1"):
        engine.synthesize_batch(["Text."])
