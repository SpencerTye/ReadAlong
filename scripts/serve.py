"""Start the reader app at http://127.0.0.1:8321.

Usage: python scripts/serve.py
Playback only needs the cached audio. Generating audio for a new document
also needs the VibeVoice worker (scripts/vibevoice_worker.py).
"""

import sys
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from readalong.app import create_app  # noqa: E402
from readalong.cache import AudioCache  # noqa: E402
from readalong.engines import VibeVoiceEngine  # noqa: E402


def main() -> None:
    app = create_app(
        library_dir=ROOT / "library",
        cache=AudioCache(ROOT / "cache"),
        engine=VibeVoiceEngine(),
        voice="alice",
        batch_size=32,
    )
    uvicorn.run(app, host="127.0.0.1", port=8321, log_level="warning")


if __name__ == "__main__":
    main()
