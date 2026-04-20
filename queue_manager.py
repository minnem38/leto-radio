#!/usr/bin/env python3
"""
Leto Radio - Queue Manager
Manages the song queue using a simple JSON file for persistence.
Thread-safe for use with the stream server.
"""

import os
import json
import threading
from pathlib import Path

QUEUE_FILE = Path(os.getenv("QUEUE_FILE", "/data/queue/queue.json"))
MUSIC_DIR = Path(os.getenv("MUSIC_DIR", "/data/music"))


class QueueManager:
    def __init__(self):
        self._lock = threading.Lock()
        QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
        MUSIC_DIR.mkdir(parents=True, exist_ok=True)

        if not QUEUE_FILE.exists():
            self._save([])

    def _load(self):
        try:
            return json.loads(QUEUE_FILE.read_text())
        except Exception:
            return []

    def _save(self, data):
        QUEUE_FILE.write_text(json.dumps(data, indent=2))

    def get_current(self):
        with self._lock:
            q = self._load()
            return q[0] if q else None

    def get_all(self):
        with self._lock:
            return self._load()

    def add(self, song: dict):
        with self._lock:
            q = self._load()
            q.append(song)
            self._save(q)
        print(f"[queue] Added: {song.get('title')} (requested by {song.get('requested_by')})")

    def advance(self):
        with self._lock:
            q = self._load()
            if not q:
                return
            finished = q.pop(0)
            self._save(q)

            filepath = finished.get("filepath")
            if filepath:
                p = Path(filepath)
                if p.exists():
                    try:
                        p.unlink()
                        print(f"[queue] Deleted file: {filepath}")
                    except Exception as e:
                        print(f"[queue] Could not delete file: {e}")

    def remove(self, index: int):
        with self._lock:
            q = self._load()
            if 0 <= index < len(q):
                removed = q.pop(index)
                self._save(q)
                return removed
        return None

    def clear(self):
        with self._lock:
            self._save([])
