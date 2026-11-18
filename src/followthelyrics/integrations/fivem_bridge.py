"""Experimental local bridge to the ReShade test add-on."""

import json
import socket
import struct
import sys
import threading
import time

RENDERER_ADDR = ("127.0.0.1", 48790)
ACK_ADDR = ("127.0.0.1", 48791)
MAX_CHARS = 64


def select_line(lines, position):
    chosen = ""
    for line in lines:
        start = line.get("time", 0)
        end = line.get("end")
        if position >= start and (end is None or position < end):
            chosen = line.get("text", "")
        elif start > position:
            break
    return chosen


def encode_packet(text, sequence=0):
    chars = [
        ord(c) if 32 <= ord(c) < 128 else ord("?") for c in text[:MAX_CHARS]
    ]
    chars += [0] * (MAX_CHARS - len(chars))
    return struct.pack(
        "<4sII64I", b"FTL1", sequence, min(len(text), MAX_CHARS), *chars
    )


class Bridge:
    def __init__(self):
        self.lock = threading.Lock()
        self.lines = []
        self.position = 0.0
        self.playing = False
        self.track_key = None
        self.stop = threading.Event()

    def accept_event(self, event):
        with self.lock:
            if event.get("type") == "lyrics":
                self.lines = event.get("lines", [])
            elif event.get("type") == "position":
                self.position = float(event.get("seconds", 0))
                self.playing = bool(event.get("playing"))
            elif event.get("type") == "track":
                next_key = (event.get("title"), event.get("artist"))
                if next_key != self.track_key:
                    self.lines = []
                    self.track_key = next_key
                self.position = float(event.get("position", 0))
                self.playing = bool(event.get("playing"))

    def read_stdin(self):
        for line in sys.stdin:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if isinstance(event, dict):
                self.accept_event(event)
        self.stop.set()

    def run(self):
        threading.Thread(target=self.read_stdin, daemon=True).start()
        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        receiver.bind(ACK_ADDR)
        receiver.settimeout(0.1)
        sequence = 0
        next_frame = 0.0
        try:
            while not self.stop.is_set():
                now = time.monotonic()
                if now >= next_frame:
                    with self.lock:
                        text = (
                            select_line(self.lines, self.position)
                            if self.playing
                            else ""
                        )
                    sequence = (sequence + 1) % (2**32)
                    sender.sendto(encode_packet(text, sequence), RENDERER_ADDR)
                    next_frame = now + 0.1
                try:
                    message, source = receiver.recvfrom(64)
                except TimeoutError:
                    continue
                if message == b"FTL_READY" and source[0] == "127.0.0.1":
                    print('{"type":"rendering","ready":true}', flush=True)
        finally:
            receiver.close()
            sender.close()


def main():
    Bridge().run()


if __name__ == "__main__":
    main()
