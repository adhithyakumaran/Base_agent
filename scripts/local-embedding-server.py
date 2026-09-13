#!/usr/bin/env python3
"""Local OpenAI-compatible embedding server for production-provider validation."""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

MODEL_NAME = os.environ.get("LOCAL_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
HOST = os.environ.get("LOCAL_EMBEDDING_HOST", "127.0.0.1")
PORT = int(os.environ.get("LOCAL_EMBEDDING_PORT", "8765"))

_MODEL = None


def _load_model():
    global _MODEL
    if _MODEL is None:
        from sentence_transformers import SentenceTransformer

        _MODEL = SentenceTransformer(MODEL_NAME)
    return _MODEL


def embed_texts(texts: list[str]) -> list[list[float]]:
    model = _load_model()
    vectors = model.encode(texts, normalize_embeddings=True)
    return [vec.tolist() for vec in vectors]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        return

    def do_POST(self) -> None:
        if self.path != "/v1/embeddings":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length).decode("utf-8"))
        inputs = body.get("input")
        texts = [inputs] if isinstance(inputs, str) else list(inputs or [])
        data = [
            {"object": "embedding", "index": i, "embedding": vec}
            for i, vec in enumerate(embed_texts(texts))
        ]
        payload = {"object": "list", "data": data, "model": body.get("model") or MODEL_NAME}
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def main() -> None:
    model = _load_model()
    dims = model.get_sentence_embedding_dimension()
    server = HTTPServer((HOST, PORT), Handler)
    print(f"local embedding server http://{HOST}:{PORT}/v1/embeddings model={MODEL_NAME} dims={dims}")
    server.serve_forever()


if __name__ == "__main__":
    main()
