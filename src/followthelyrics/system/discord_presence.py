import json
import logging
import os
import socket
import struct
import sys
import threading
import uuid

logger = logging.getLogger(__name__)


def frame(opcode, payload):
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return struct.pack("<II", opcode, len(body)) + body


def activity(track):
    if not track or not track.get("playing"):
        return None
    title = str(track.get("title") or "Music")[:128]
    artist = str(track.get("artist") or "Unknown artist")[:128]
    return {"type": 2, "details": title, "state": artist,
            "instance": False}


def send(client_id, track):
    if not client_id.isdigit() or not 16 <= len(client_id) <= 22:
        return
    payload = {"cmd": "SET_ACTIVITY", "args": {"pid": os.getpid(),
               "activity": activity(track)}, "nonce": str(uuid.uuid4())}
    if sys.platform == "win32":
        for index in range(10):
            try:
                with open(rf"\\.\pipe\discord-ipc-{index}", "r+b", buffering=0) as pipe:
                    pipe.write(frame(0, {"v": 1, "client_id": client_id}))
                    pipe.write(frame(1, payload))
                return
            except OSError:
                continue
        return
    bases = [os.environ.get("XDG_RUNTIME_DIR", ""),
             os.environ.get("TMPDIR", ""), "/tmp"]
    for base in bases:
        if not base:
            continue
        for index in range(10):
            path = os.path.join(base, f"discord-ipc-{index}")
            try:
                with socket.socket(socket.AF_UNIX) as connection:
                    connection.settimeout(1.5)
                    connection.connect(path)
                    connection.sendall(frame(0, {"v": 1, "client_id": client_id}))
                    connection.sendall(frame(1, payload))
                return
            except OSError:
                continue


class DiscordPresence:
    def __init__(self):
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._changed = threading.Event()
        self._client_id = ""
        self._track = None
        self._last_id = ""
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name="ftl-discord-presence")
        self._thread.start()

    def configure(self, enabled, client_id, track=None):
        next_id = str(client_id).strip() if enabled else ""
        with self._lock:
            if self._client_id == next_id and self._track == track:
                return
            self._client_id = next_id
            self._track = track
        self._changed.set()

    def _run(self):
        while not self._stop.is_set():
            with self._lock:
                client_id = self._client_id
                track = self._track
            try:
                if self._last_id and self._last_id != client_id:
                    send(self._last_id, None)
                if client_id:
                    send(client_id, track)
                self._last_id = client_id
            except Exception:
                logger.debug("Discord presence update failed", exc_info=True)
            self._changed.wait(15)
            self._changed.clear()

    def shutdown(self):
        self._stop.set()
        self._changed.set()
        self._thread.join(timeout=2)
