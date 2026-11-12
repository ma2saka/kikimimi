#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["google-auth==2.40.3", "requests==2.32.4"]
# ///
"""聞き耳: ブラウザで書き起こした発話を Gemini Decision 1 にかけ、感情ごとの確率を返すローカルサーバ。

usage: GOOGLE_AI_STUDIO_KEY=<key> ./server.py [port]
       GOOGLE_CLOUD_PROJECT=<project-id> ./server.py [port]   # ADC（generative-language スコープ付き）
"""

import json
import os
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import google.auth
import google.auth.transport.requests
import requests

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/decisions"
MODEL = "gemini-decision-1"
SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/generative-language",
]
INDEX = Path(__file__).with_name("index.html")

EMOTIONS: dict[str, str] = {
    "angry": "話者は怒っている、または苛立っている",
    "hungry": "話者は空腹である",
    "question": "話者は疑問を抱いている、何かを尋ねている",
    "happy": "話者は喜んでいる、楽しんでいる",
    "sad": "話者は悲しんでいる、落ち込んでいる",
    "tired": "話者は疲れている、眠い",
    "surprised": "話者は驚いている",
}

session = requests.Session()
api_key = os.environ.get("GOOGLE_AI_STUDIO_KEY")
if api_key:
    session.headers["x-goog-api-key"] = api_key
else:
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    assert project, "GOOGLE_AI_STUDIO_KEY か GOOGLE_CLOUD_PROJECT を設定してください"
    session.headers["x-goog-user-project"] = project
    credentials, _ = google.auth.default(scopes=SCOPES)
    auth_request = google.auth.transport.requests.Request(session)


def auth_headers() -> dict[str, str]:
    """ADC のときだけ、期限切れなら更新した Bearer トークンを返す。"""
    if api_key:
        return {}
    if not credentials.valid:
        credentials.refresh(auth_request)
    return {"Authorization": f"Bearer {credentials.token}"}


def decide(text: str, audio_b64: str | None, mime: str | None) -> dict[str, float]:
    """発話テキスト（と任意の音声）から、感情ごとの確率 0..1 を返す。"""
    blocks: list[dict[str, str]] = [{"type": "text", "text": f"日本語の話し言葉の書き起こし:\n{text}\n"}]
    if audio_b64 and mime:
        blocks.append({"type": "text", "text": "同じ発話の音声（声色も判断材料にする）:\n"})
        blocks.append({"type": "audio", "data": audio_b64, "mime_type": mime})
    body = {
        "model": MODEL,
        "input": blocks,
        "questions": {key: {"type": "noul", "instructions": desc} for key, desc in EMOTIONS.items()},
    }
    res = session.post(
        ENDPOINT,
        json=body,
        headers=auth_headers(),
        timeout=15,
    )
    res.raise_for_status()
    return {key: answer["noul"] for key, answer in res.json()["answers"].items()}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        match self.path:
            case "/":
                self._reply(HTTPStatus.OK, INDEX.read_bytes(), "text/html; charset=utf-8")
            case "/emotions":
                self._json(HTTPStatus.OK, EMOTIONS)
            case _:
                self._reply(HTTPStatus.NOT_FOUND, b"", "text/plain")

    def do_POST(self) -> None:
        if self.path == "/log":
            print("client:", self.rfile.read(int(self.headers["Content-Length"])).decode(), flush=True)
            self._reply(HTTPStatus.NO_CONTENT, b"", "text/plain")
            return
        if self.path != "/decide":
            self._reply(HTTPStatus.NOT_FOUND, b"", "text/plain")
            return
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        text: str = req["text"]
        print(f"decide: {text!r} audio={req.get('mime')} {len(req.get('audio') or '')}", flush=True)
        try:
            self._json(HTTPStatus.OK, decide(text, req.get("audio"), req.get("mime")))
        except requests.HTTPError as e:
            print("error:", e.response.text, flush=True)
            self._json(HTTPStatus.BAD_GATEWAY, {"error": e.response.text})

    def _json(self, status: HTTPStatus, obj: object) -> None:
        self._reply(status, json.dumps(obj, ensure_ascii=False).encode(), "application/json")

    def _reply(self, status: HTTPStatus, body: bytes, ctype: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 18960
    print(f"http://localhost:{port}/")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
