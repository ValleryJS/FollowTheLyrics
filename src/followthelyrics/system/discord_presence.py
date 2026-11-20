import json
import logging
import os
import socket
import struct
import sys
import threading
import uuid

logger = logging.getLogger(__name__)
MAX_FRAME = 1_048_576


def frame(opcode, payload):
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return struct.pack("<II", opcode, len(body)) + body


def activity(track):
    if not track or not track.get("playing"):
        return None
    title = str(track.get("title") or "Music")[:128]
    artist = str(track.get("artist") or "Unknown artist")[:128]
    return {"details": title, "state": artist, "instance": False}


class DiscordIPC:
    def __init__(self, stream, is_socket=False):
        self.stream = stream
        self.is_socket = is_socket

    def _read_exact(self, size):
        chunks = []
        while size:
            part = self.stream.recv(size) if self.is_socket else self.stream.read(size)
            if not part:
                raise ConnectionError("Discord closed the connection")
            chunks.append(part)
            size -= len(part)
        return b"".join(chunks)

    def receive(self):
        opcode, size = struct.unpack("<II", self._read_exact(8))
        if size > MAX_FRAME:
            raise ConnectionError("Invalid Discord response size")
        payload = json.loads(self._read_exact(size))
        if opcode == 2 or payload.get("evt") == "ERROR":
            raise ConnectionError(f"Discord RPC rejected request: {payload}")
        if opcode != 1:
            raise ConnectionError(f"Unexpected Discord opcode: {opcode}")
        return payload

    def write(self, opcode, payload):
        data = frame(opcode, payload)
        if self.is_socket:
            self.stream.sendall(data)
        else:
            self.stream.write(data)

    def handshake(self, client_id):
        self.write(0, {"v": 1, "client_id": client_id})
        response = self.receive()
        if response.get("evt") != "READY":
            raise ConnectionError("Discord did not acknowledge the handshake")

    def update(self, track):
        nonce = str(uuid.uuid4())
        self.write(1, {
            "cmd": "SET_ACTIVITY",
            "args": {"pid": os.getpid(), "activity": activity(track)},
            "nonce": nonce,
        })
        response = self.receive()
        if response.get("nonce") != nonce:
            raise ConnectionError("Discord returned an unexpected response")

    def close(self):
        self.stream.close()


def connect(client_id):
    if sys.platform == "win32":
        for index in range(10):
            try:
                stream = open(rf"\\.\pipe\discord-ipc-{index}", "r+b", buffering=0)
                connection = DiscordIPC(stream)
                try:
                    connection.handshake(client_id)
                    return connection
                except Exception:
                    connection.close()
                    raise
            except OSError:
                continue
        raise ConnectionError("Discord desktop client not found")
    bases = [os.environ.get(key, "") for key in
             ("XDG_RUNTIME_DIR", "TMPDIR", "TMP", "TEMP")]
    bases.append("/tmp")
    for base in bases:
        if not base:
            continue
        for index in range(10):
            path = os.path.join(base, f"discord-ipc-{index}")
            stream = socket.socket(socket.AF_UNIX)
            stream.settimeout(2)
            try:
                stream.connect(path)
                connection = DiscordIPC(stream, is_socket=True)
                connection.handshake(client_id)
                return connection
            except OSError:
                stream.close()
                continue
            except Exception:
                stream.close()
                raise
    raise ConnectionError("Discord desktop client not found")


class DiscordPresence:
    def __init__(self):
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._changed = threading.Event()
        self._client_id = ""
        self._track = None
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="ftl-discord-presence"
        )
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
        connection = None
        connected_id = ""
        while not self._stop.is_set():
            with self._lock:
                client_id = self._client_id
                track = self._track
            if client_id != connected_id and connection:
                connection.close()
                connection = None
                connected_id = ""
            if client_id and not (client_id.isdigit() and 16 <= len(client_id) <= 22):
                logger.warning("Discord Application ID is invalid")
                client_id = ""
            if client_id:
                try:
                    if connection is None:
                        connection = connect(client_id)
                        connected_id = client_id
                        logger.info("Discord Rich Presence connected")
                    connection.update(track)
                except (OSError, ConnectionError, ValueError) as exc:
                    logger.warning("Discord Rich Presence: %s", exc)
                    if connection:
                        connection.close()
                        connection = None
                        connected_id = ""
            self._changed.wait(15 if connection else 5)
            self._changed.clear()
        if connection:
            connection.close()

    def shutdown(self):
        self._stop.set()
        self._changed.set()
        self._thread.join(timeout=2)
