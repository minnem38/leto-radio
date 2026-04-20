#!/usr/bin/env python3
"""
Leto Radio - Stream Server
Serves the current song as a static file at /stream
When the file finishes, the next song in the queue takes over.
"""

import time
import threading
from pathlib import Path
from flask import Flask, Response, jsonify, send_from_directory, send_file
from queue_manager import QueueManager

app = Flask(__name__)
queue = QueueManager()

WEB_DIR = Path(__file__).parent / "web"
CURRENT_FILE = Path("/data/music/current.mp3")

stream_lock = threading.Lock()
current_song = {"info": None, "start_time": None}


def queue_runner():
    """
    Background thread — watches the queue, copies the next song to
    current.mp3 when the previous one finishes.
    """
    while True:
        song = queue.get_current()

        if not song:
            # Clear current if queue is empty
            if CURRENT_FILE.exists():
                CURRENT_FILE.unlink()
            with stream_lock:
                current_song["info"] = None
                current_song["start_time"] = None
            time.sleep(1)
            continue

        filepath = Path(song.get("filepath", ""))
        if not filepath.exists():
            print(f"[runner] File missing: {filepath}, skipping.")
            queue.advance()
            continue

        # Copy to current.mp3
        CURRENT_FILE.write_bytes(filepath.read_bytes())

        with stream_lock:
            current_song["info"] = song
            current_song["start_time"] = time.time()

        print(f"[runner] Now playing: {song.get('title', 'Unknown')}")

        # Wait for the song to finish playing
        # We estimate duration from file size (~16KB/s for 128kbps mp3)
        file_size = filepath.stat().st_size
        estimated_duration = file_size / 16000
        time.sleep(max(estimated_duration, 1))

        queue.advance()
        time.sleep(0.5)


# Start background runner thread
runner_thread = threading.Thread(target=queue_runner, daemon=True)
runner_thread.start()


@app.route("/")
def index():
    """Serves the now-playing web UI."""
    return send_from_directory(WEB_DIR, "index.html")


@app.route("/stream")
@app.route("/stream.mp3")
def stream():
    """Serves the current song as a static MP3 file."""
    if not CURRENT_FILE.exists():
        return Response("Nothing playing", status=204)

    return send_file(
        CURRENT_FILE,
        mimetype="audio/mpeg",
        conditional=False,
        as_attachment=True,
        download_name="current.mp3",
    )


@app.route("/nowplaying")
def now_playing():
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
    return jsonify(queue.get_all())


@app.route("/skip", methods=["POST"])
def skip():
    queue.advance()
    return jsonify({"status": "skipped"})


if __name__ == "__main__":
    print("🎵 Leto Radio stream server starting on port 8765...")
    app.run(host="0.0.0.0", port=8765, threaded=True)
