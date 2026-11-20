import json
import struct

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
        "type": 2,
        "details": "Track",
        "state": "Artist",
        "instance": False,
    }
