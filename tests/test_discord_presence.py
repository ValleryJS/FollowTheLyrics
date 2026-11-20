import json
import struct
from io import BytesIO

from followthelyrics.system.discord_presence import DiscordIPC
from followthelyrics.system.discord_presence import activity
from followthelyrics.system.discord_presence import frame


def test_discord_frame_has_opcode_and_byte_length():
    message = frame(1, {"cmd": "SET_ACTIVITY", "args": {}})
    opcode, size = struct.unpack("<II", message[:8])
    assert opcode == 1
    assert size == len(message[8:])
    assert json.loads(message[8:])["cmd"] == "SET_ACTIVITY"


def test_discord_presence_only_shares_playing_tracks():
    assert activity(None) is None
    assert activity({"playing": False, "title": "Private"}) is None
    assert activity({"playing": True, "title": "Track", "artist": "Artist"}) == {
        "details": "Track",
        "state": "Artist",
        "instance": False,
        "buttons": [{
            "label": "Download FTL-Cat's Edition",
            "url": "https://github.com/ValleryJS/FollowTheLyrics/releases/latest",
        }],
    }


def test_discord_waits_for_ready_event():
    class MemoryStream:
        def __init__(self):
            self.readable = BytesIO(frame(1, {"evt": "READY"}))
            self.sent = b""

        def write(self, data):
            self.sent += data

        def read(self, size):
            return self.readable.read(size)

    stream = MemoryStream()
    connection = DiscordIPC(stream)
    connection.handshake("123456789012345678")
    assert struct.unpack("<I", stream.sent[:4])[0] == 0


def test_discord_reports_rejected_response():
    stream = BytesIO(frame(1, {"evt": "ERROR", "data": {"message": "Bad ID"}}))
    connection = DiscordIPC(stream)
    try:
        connection.receive()
    except ConnectionError as exc:
        assert "Bad ID" in str(exc)
    else:
        raise AssertionError("Discord RPC rejection was ignored")
