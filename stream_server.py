#!/usr/bin/env python3
"""
Leto Radio - Stream Server
Serves the current song as a continuous stream at /stream
Also exposes /queue and /nowplaying as JSON for the web UI
Serves the web UI at /
"""

import os
import time
import threading
from pathlib import Path
from flask import Flask, Response, jsonify, send_from_directory

from queue_manager import QueueManager

app = Flask(__name__)
queue = QueueManager()

WEB_DIR = Path(__file__).parent / "web"

# --- Shared stream state ---
# All listeners read from the same in-memory buffer so everyone
# hears the same thing at the same time.
stream_lock = threading.Lock()
current_song = {"info": None, "start_time": None}
stream_buffer = []
stream_buffer_lock = threading.Lock()
stream_done = threading.Event()


def stream_loader():
    """
    Background thread — loads the current song into stream_buffer
    chunk by chunk, then advances the queue when done.
    """
    global stream_buffer

    while True:
        song = queue.get_current()

        if not song:
            time.sleep(1)
            continue

        filepath = song.get("filepath")
        if not filepath or not Path(filepath).exists():
            print(f"[loader] File missing: {filepath}, skipping.")
            queue.advance()
            continue

        with stream_lock:
            current_song["info"] = song
            current_song["start_time"] = time.time()

        print(f"[loader] Now playing: {song.get('title', 'Unknown')}")

        with stream_buffer_lock:
            stream_buffer = []
            stream_done.clear()

        try:
            with open(filepath, "rb") as f:
                while True:
                    chunk = f.read(4096)
                    if not chunk:
                        break
                    with stream_buffer_lock:
                        stream_buffer.append(chunk)
                    time.sleep(0.01)
        except Exception as e:
            print(f"[loader] Error reading file: {e}")

        stream_done.set()
        queue.advance()
        time.sleep(0.1)


# Start background loader thread
loader_thread = threading.Thread(target=stream_loader, daemon=True)
loader_thread.start()


def listener_generator():
    """
    Generator for each connected listener.
    Reads from the shared stream_buffer as chunks arrive.
    """
    index = 0
    while True:
        with stream_buffer_lock:
            available = len(stream_buffer)

        if index < available:
            with stream_buffer_lock:
                chunk = stream_buffer[index]
            yield chunk
            index += 1
        elif stream_done.is_set() and index >= available:
            # Song finished, wait for next
            index = 0
            time.sleep(0.5)
        else:
            time.sleep(0.05)


@app.route("/")
def index():
    """Serves the now-playing web UI."""
    return send_from_directory(WEB_DIR, "index.html")


@app.route("/stream")
def stream():
    """The main stream endpoint — point your Etched disc here."""
    return Response(
        listener_generator(),
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
    """Skips the current song."""
    queue.advance()
    return jsonify({"status": "skipped"})


if __name__ == "__main__":
    print("🎵 Leto Radio stream server starting on port 8765...")
    app.run(host="0.0.0.0", port=8765, threaded=True)