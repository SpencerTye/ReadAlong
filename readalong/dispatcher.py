"""Generate audio for every chunk of a document and store it in the cache.

Chunks already in the cache are skipped, so an interrupted run can be restarted.
An optional validator can reject a take, and rejected chunks are regenerated up
to max_retries times. If a chunk never passes, its last take is kept (a flawed
chunk is better than a gap in the audio) and its ID is listed in
FillResult.unvalidated.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from readalong.cache import AudioCache
from readalong.chunker import Chunk

Validator = Callable[[Chunk, bytes], bool]
Progress = Callable[[int, int], None]


@dataclass
class FillResult:
    generated: int = 0
    skipped: int = 0
    retried: int = 0
    unvalidated: list[str] = field(default_factory=list)


def _batches(items: list, size: int):
    for start in range(0, len(items), size):
        yield items[start : start + size]


def _speakable(text: str) -> str:
    # Without closing punctuation (headings, titles) the model tends to keep
    # talking past the end of the text. A period tells it where to stop.
    # Chunk IDs are still computed from the original text.
    text = text.strip()
    return text if text.endswith((".", "!", "?", ":", ";")) else text + "."


def fill(
    doc_hash: str,
    chunks: list[Chunk],
    engine,
    cache: AudioCache,
    voice: str,
    batch_size: int = 32,
    validator: Validator | None = None,
    max_retries: int = 2,
    on_progress: Progress | None = None,
) -> FillResult:
    result = FillResult()
    todo = []
    for chunk in chunks:
        if cache.has(doc_hash, engine.name, voice, chunk.id):
            result.skipped += 1
        else:
            todo.append(chunk)

    done = 0
    for batch in _batches(todo, batch_size):
        wavs = engine.synthesize_batch([_speakable(c.text) for c in batch])
        pending = list(zip(batch, wavs))
        attempts_left = max_retries
        while True:
            failed_pairs = []
            for chunk, wav in pending:
                if validator is None or validator(chunk, wav):
                    cache.write(doc_hash, engine.name, voice, chunk.id, wav)
                    result.generated += 1
                else:
                    failed_pairs.append((chunk, wav))
            if not failed_pairs:
                break
            if attempts_left == 0:
                # out of retries: keep the last take and flag it
                for chunk, wav in failed_pairs:
                    cache.write(doc_hash, engine.name, voice, chunk.id, wav)
                    result.generated += 1
                    result.unvalidated.append(chunk.id)
                break
            attempts_left -= 1
            result.retried += len(failed_pairs)
            retry_texts = [_speakable(c.text) for c, _ in failed_pairs]
            retry_wavs = engine.synthesize_batch(retry_texts)
            pending = list(zip([c for c, _ in failed_pairs], retry_wavs))
        done += len(batch)
        if on_progress:
            on_progress(done, len(todo))
    return result
