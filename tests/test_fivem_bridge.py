from followthelyrics.integrations.fivem_bridge import Bridge
from followthelyrics.integrations.fivem_bridge import encode_packet
from followthelyrics.integrations.fivem_bridge import select_line


def test_select_line_at_current_position():
    lines = [
        {"time": 0.0, "end": 2.0, "text": "First"},
        {"time": 2.0, "end": 4.0, "text": "Second"},
    ]
    assert select_line(lines, 2.5) == "Second"
    assert select_line(lines, 4.5) == ""


def test_packet_contains_ascii_codes():
    packet = encode_packet("Hi", sequence=7)
    assert packet[:4] == b"FTL1"
    assert len(packet) == 4 + 4 + 4 + 64 * 4
    assert packet[12:20] == b"H\0\0\0i\0\0\0"


def test_repeated_track_updates_keep_lyrics():
    bridge = Bridge()
    track = {
        "type": "track",
        "title": "Song",
        "artist": "Singer",
        "playing": True,
    }
    bridge.accept_event(track)
    bridge.accept_event(
        {"type": "lyrics", "lines": [{"time": 0.0, "text": "Hello"}]}
    )
    bridge.accept_event(track)
    assert bridge.lines[0]["text"] == "Hello"
