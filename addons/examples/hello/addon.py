_api = None


def on_enable(api):
    global _api
    _api = api
    api.log("Example add-on started")


def on_track(track):
    if track and _api:
        _api.log(f"Now playing: {track['artist']} - {track['title']}")


def on_lyrics(key, lines):
    if _api:
        _api.log(f"Received {len(lines)} lyric lines for {key}")


def on_disable():
    if _api:
        _api.log("Example add-on stopped")
