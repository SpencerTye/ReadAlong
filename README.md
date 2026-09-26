# ReadAlong

ReadAlong turns a Word document into an audiobook you can read along with. It
generates narration for the whole document once, on a local GPU, and saves it.
A browser page then plays the audio and highlights and scrolls the text in sync.
After the audio is generated, playback does not use a model at all.

I built it to study dense scientific papers by listening and reading at the same
time, without paying for or streaming a cloud voice. On an RTX 3090, a paper
that reads aloud in 64 minutes (146 chunks) took about 11 minutes to generate.

## How it works

1. `readalong/extractor.py` reads the .docx into sentences. It strips bracketed
   citations like [12] and skips tables, figure captions, figure-legend
   sections and acknowledgements. For papers, it starts at the abstract and
   stops at the references. These filters only apply when the matching
   headings exist.
2. `readalong/chunker.py` groups sentences into chunks of a few sentences (up to
   ~700 characters), never crossing a paragraph. Headings get their own chunk.
3. `readalong/dispatcher.py` sends chunks to the voice model in batches and
   saves each result as a WAV file. Chunks that already exist are skipped, so a
   stopped run picks up where it left off.
4. `readalong/app.py` and `readalong/static/reader.html` serve the reader. Click
   any paragraph to play from there. The page has a speed slider, remembers
   your place in each document, and marks chunks whose audio is still being
   generated.

The voice model runs in a separate worker process (`scripts/vibevoice_worker.py`)
that loads the model once and generates a batch of chunks per request. It runs
under Linux (WSL2 on Windows). The app and the reader run on Windows.

## Choosing the voice model

I compared two models that can clone a reference voice, VibeVoice-1.5B and
Higgs Audio V3 (4B). Both cloned the same voice, and every concurrent slot read
a different passage. I transcribed every output with Whisper and compared it
word by word with its source text. I also required at least 4 GB of GPU memory
to stay free during generation.

Minutes of GPU time per hour of finished audio, measured on test passages
(lower is better):

| Batch size | Higgs V3 4B | VibeVoice 1.5B |
|---|---|---|
| 2 | 33.6 | 47.1 |
| 4 | 16.9 | 26.2 |
| 8 | did not keep 4 GB free | 13.4 |
| 16 | did not keep 4 GB free | 6.6 |
| 32 | not tested | 4.1 |

VibeVoice at batch 32 was about four times faster than the best Higgs setting
that kept 4 GB free. It also uses no GPU memory once the worker is stopped,
while the Higgs server held 18.6 GB even when idle. In both models every output
matched its own text, and both garbled the start or end of about 1 in 12 chunks
when run in batches. A real paper generates more slowly than these test
passages; see the 11-minute figure at the top.

In the first full-document run, headings and other text without closing
punctuation made VibeVoice keep talking past the end of the text. The fill step
now adds a period to any chunk that lacks one before sending it to the model.

## Setup

### App and reader (Windows, Python 3.12)

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pytest -q
```

### Voice worker (Linux or WSL2, CUDA GPU)

The worker uses the community fork of VibeVoice, since Microsoft took down the
original repository. The weights download from `vibevoice/VibeVoice-1.5B` on
first use.

```
python3.12 -m venv ~/vibevoice-env
git clone https://github.com/vibevoice-community/VibeVoice.git ~/VibeVoice
~/vibevoice-env/bin/pip install -e ~/VibeVoice
```

The worker reads these environment variables: `VV_MODEL`, `VV_VOICE` (path to a
reference voice clip; the default is one of VibeVoice's demo voices),
`VV_CFG_SCALE` and `VV_PORT` (default 8100).

## Usage

1. Put .docx files in `library/`.
2. Start the worker:
   `~/vibevoice-env/bin/python scripts/vibevoice_worker.py`
3. Optional: preview how a document will be split:
   `python scripts/parse_doc.py library/paper.docx`
4. Generate the audio (a stopped run resumes where it left off):
   `python scripts/fill_doc.py library/paper.docx --batch 32`
5. Stop the worker, then start the reader and open http://127.0.0.1:8321:
   `python scripts/serve.py`

Opening a document in the reader also starts generation for any missing
chunks, if the worker is running.

## Limitations

- The fill step accepts a validator function that can reject a chunk and have
  it regenerated (see `readalong/dispatcher.py` and its tests). The Whisper
  checks I used while comparing models ran as a separate script, and no
  validator is wired into `fill_doc.py` yet.
- Input is .docx only.
- The app is meant to run on your own machine. It has no authentication.

## Tests

43 tests cover extraction, chunking, the cache, the fill step, the worker client
and the app API. They use a fake engine, so they run without a GPU or the model.

## License

MIT
