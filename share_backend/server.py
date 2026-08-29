"""Optional self-hosted temporary clip sharing backend for Cammetry.

This is NOT needed for normal local use. Deploy it only if you want the app's optional
Share button to create internet links. Files expire automatically after 48 hours.
"""
from __future__ import annotations

import json
import os
import secrets
import time
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_file
from werkzeug.utils import secure_filename

app = Flask(__name__)
ROOT = Path(os.environ.get("TTS_SHARE_DIR", "./shared_clips")).resolve()
ROOT.mkdir(parents=True, exist_ok=True)
META = ROOT / "metadata.json"
TTL_SECONDS = int(os.environ.get("TTS_SHARE_TTL", str(48 * 3600)))
MAX_MB = int(os.environ.get("TTS_SHARE_MAX_MB", "750"))
app.config["MAX_CONTENT_LENGTH"] = MAX_MB * 1024 * 1024


def load_meta():
    try:
        data = json.loads(META.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_meta(data):
    META.write_text(json.dumps(data, indent=2), encoding="utf-8")


def cleanup():
    now = time.time(); data = load_meta(); changed = False
    for token, item in list(data.items()):
        if float(item.get("expires", 0)) <= now:
            try: (ROOT / item["stored_name"]).unlink(missing_ok=True)
            except Exception: pass
            data.pop(token, None); changed = True
    if changed: save_meta(data)


@app.post("/upload")
def upload():
    cleanup()
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify(error="missing file"), 400
    original = secure_filename(f.filename) or "clip.mp4"
    if not original.lower().endswith(".mp4"):
        return jsonify(error="only mp4 files are accepted"), 400
    token = secrets.token_urlsafe(12)
    delete_key = secrets.token_urlsafe(18)
    stored = f"{token}.mp4"
    f.save(ROOT / stored)
    expires = time.time() + TTL_SECONDS
    data = load_meta(); data[token] = {"stored_name": stored, "original_name": original, "expires": expires, "delete_key": delete_key}; save_meta(data)
    base = os.environ.get("TTS_SHARE_BASE_URL", request.url_root.rstrip("/"))
    return jsonify(url=f"{base}/c/{token}", delete_url=f"{base}/c/{token}?key={delete_key}", expires_at=int(expires))


@app.get("/c/<token>")
def clip(token):
    cleanup(); data = load_meta(); item = data.get(token)
    if not item: abort(404)
    path = ROOT / item["stored_name"]
    if not path.exists(): abort(404)
    return send_file(path, mimetype="video/mp4", download_name=item.get("original_name", "clip.mp4"), conditional=True)


@app.delete("/c/<token>")
def delete_clip(token):
    data = load_meta(); item = data.get(token)
    if not item: abort(404)
    if request.args.get("key") != item.get("delete_key"): abort(403)
    try: (ROOT / item["stored_name"]).unlink(missing_ok=True)
    except Exception: pass
    data.pop(token, None); save_meta(data)
    return jsonify(ok=True)


@app.get("/health")
def health():
    cleanup(); return jsonify(ok=True, ttl_hours=TTL_SECONDS / 3600, max_mb=MAX_MB)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
