"""Choose the active lyric output without losing the desktop fallback."""

import time


class RendererGate:
    def __init__(self, timeout=2.0):
        self.timeout = timeout
        self.mode = "desktop"
        self.last_ack = None

    def acknowledge(self, addon_id, now=None):
        if addon_id == "fivem-reshade":
            self.last_ack = time.monotonic() if now is None else now

    def route_to_external(self, now=None):
        if self.mode != "fivem" or self.last_ack is None:
            return False
        current = time.monotonic() if now is None else now
        return 0 <= current - self.last_ack <= self.timeout
