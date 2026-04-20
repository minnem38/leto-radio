#!/usr/bin/env python3
"""
Leto Radio - Stream Server
Serves the current song as a continuous stream at /stream
Also exposes /queue and /nowplaying as JSON for the web UI
"""

import os
import json
import time
import threading
from pathlib import Path
from flask import Flask, Response, jsonify, stream_with_context
from queue_manager import QueueManager

app = Flask(__name__)
queue = QueueManager()

# --- Streaming state ---
current_song = {"info": None, "start_time": None}
stream_lock = threading.Lock()


def song_generator():
    """Generator that streams the current song, then moves to the next."""
    chunk_size = 4096

    while True:
        song = queue.get_current()

        if not song:
            # Nothing in queue — send silence (empty bytes) and wait
            time.sleep(1)
            yield b""
            continue

        filepath = song.get("filepath")
        if not filepath or not Path(filepath).exists():
            queue.advance()
            continue

        with stream_lock:
            current_song["info"] = song
            current_song["start_time"] = time.time()

        print(f"[stream] Now playing: {song.get('title', 'Unknown')}")

        try:
            with open(filepath, "rb") as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
        except GeneratorExit:
            return
        except Exception as e:
            print(f"[stream] Error reading file: {e}")

        # Song finished — advance queue
        queue.advance()
        time.sleep(0.1)


@app.route("/stream")
def stream():
    """The main stream endpoint — point your Etched disc here."""
    return Response(
        stream_with_context(song_generator()),
        mimetype="audio/mpeg",
        headers={
            "Cache-Control": "no-cache, no-store",
            "X-Content-Type-Options": "nosniff",
            "Connection": "keep-alive",
        },
    )


@app.route("/nowplaying")
def now_playing():
    """Returns the currently playing song as JSON."""
    with stream_lock:
        info = current_song["info"]
        start = current_song["start_time"]

    if not info:
        return jsonify({"playing": False})

    elapsed = int(time.time() - start) if start else 0
    return jsonify({
        "playing": True,
        "title": info.get("title", "Unknown"),
        "requested_by": info.get("requested_by", "Unknown"),
        "url": info.get("original_url", ""),
        "elapsed_seconds": elapsed,
    })


@app.route("/queue")
def get_queue():
    """Returns the full queue as JSON."""
    return jsonify(queue.get_all())


@app.route("/skip", methods=["POST"])
def skip():
    """Skips the current song (admin use)."""
    queue.advance()
    return jsonify({"status": "skipped"})


if __name__ == "__main__":
    print("🎵 Leto Radio stream server starting on port 8765...")
    app.run(host="0.0.0.0", port=8765, threaded=True)
