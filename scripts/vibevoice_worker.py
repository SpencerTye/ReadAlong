"""VibeVoice worker: loads the model once and serves batched speech synthesis.

Runs in a Linux environment with a CUDA GPU (WSL2 on Windows works) and listens
on port 8100, which Windows reaches as localhost:8100. It uses the standard
library's http.server because its only client is the fill step.

  GET  /health  -> {"ok": true, "model": ...}
  POST /batch   {"texts": [...]} -> {"wavs_b64": [...]}

Settings: VV_MODEL, VV_VOICE (reference voice clip), VV_CFG_SCALE, VV_PORT.
"""

import base64
import json
import os
import tempfile
import traceback
from http.server import BaseHTTPRequestHandler, HTTPServer

import torch
from vibevoice.modular.modeling_vibevoice_inference import (
    VibeVoiceForConditionalGenerationInference,
)
from vibevoice.processor.vibevoice_processor import VibeVoiceProcessor

MODEL = os.environ.get("VV_MODEL", "vibevoice/VibeVoice-1.5B")
VOICE = os.environ.get("VV_VOICE", "/root/VibeVoice/demo/voices/en-Alice_woman.wav")
CFG_SCALE = float(os.environ.get("VV_CFG_SCALE", "1.3"))
PORT = int(os.environ.get("VV_PORT", "8100"))

print("loading model...", flush=True)
model = VibeVoiceForConditionalGenerationInference.from_pretrained(
    MODEL,
    torch_dtype=torch.bfloat16,
    device_map="cuda",
    attn_implementation="sdpa",
)
model.eval()
model.set_ddpm_inference_steps(num_steps=10)
processor = VibeVoiceProcessor.from_pretrained(MODEL)
print("model loaded", flush=True)


def generate_batch(texts: list[str]) -> list[bytes]:
    scripts = [f"Speaker 1: {t}" for t in texts]
    inputs = processor(
        text=scripts,
        voice_samples=[[VOICE]] * len(scripts),
        padding=True,
        return_tensors="pt",
        return_attention_mask=True,
    )
    for k, v in inputs.items():
        if torch.is_tensor(v):
            inputs[k] = v.to("cuda")
    outputs = model.generate(
        **inputs,
        max_new_tokens=None,
        cfg_scale=CFG_SCALE,
        tokenizer=processor.tokenizer,
        generation_config={"do_sample": False},
        verbose=False,
        is_prefill=True,
    )
    wavs: list[bytes] = []
    for audio in outputs.speech_outputs:
        with tempfile.NamedTemporaryFile(
            suffix=".wav", dir="/tmp", delete=False
        ) as tmp:
            path = tmp.name
        try:
            processor.save_audio(audio, output_path=path)
            with open(path, "rb") as f:
                wavs.append(f.read())
        finally:
            os.unlink(path)
    return wavs


# one warmup so the first real request isn't paying CUDA init
generate_batch(["Warm up the graphics pipeline."])
print("warmup done, serving", flush=True)


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self._send(200, {"ok": True, "model": MODEL})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/batch":
            self._send(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            req = json.loads(self.rfile.read(length))
            texts = req["texts"]
            wavs = generate_batch(texts)
            self._send(200, {"wavs_b64": [base64.b64encode(w).decode() for w in wavs]})
        except Exception as exc:
            traceback.print_exc()
            self._send(500, {"error": f"{type(exc).__name__}: {exc}"})

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args), flush=True)


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
