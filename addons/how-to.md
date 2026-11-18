# Making an add-on for FollowTheLyrics

There are two ways to make an add-on. Which one you need depends on where your code runs.

If your add-on runs **inside FTL**, use the Python plug-in API below. If you're making a mod for a game, you can submit it to the catalogue as a separate download, but read the section about game mods first.

## A small Python add-on

Create a folder with two files:

```text
my-addon/
    manifest.json
    addon.py
```

Put this in `manifest.json`:

```json
{
  "id": "my-addon",
  "name": "My Add-on",
  "version": "1.0.0",
  "description": "What this add-on does, in one sentence.",
  "api_version": 1,
  "entry": "addon.py"
}
```

An ID must be lowercase, at least two characters long, and contain only letters, numbers, hyphens or underscores. Keep it the same when publishing updates.

Here's a working `addon.py`:

```python
api = None


def on_enable(ftl):
    global api
    api = ftl
    api.log("My add-on started")


def on_track(track):
    if track is None:
        return
    api.log(f"Playing {track['title']} by {track['artist']}")


def on_lyrics(key, lines):
    api.log(f"Received {len(lines)} lines")


def on_disable():
    api.log("My add-on stopped")
```

You don't have to define every callback. Just use the ones you need.

### What data do you get?

`on_track(track)` receives a dictionary with:

- `title`, `artist`, `album`
- `playing` (true or false)
- `duration`, `position` (seconds)
- `app` (the music application's name)

When playback goes away, `track` can be `None`.

`on_lyrics(key, lines)` receives the track identifier as a string and a list of dictionaries. Each line has `time`, `text` and `end`. Times are in seconds. This is the full line data, not a continuous stream of individual displayed words.

The `api` object passed to `on_enable` currently provides `api_version`, `addon_id` and `log(message)`. There isn't a larger control API yet.

## Try it in FTL

Make a ZIP containing `manifest.json` and `addon.py` at the **top level** of the ZIP. Don't ZIP the parent folder itself.

On Windows, open PowerShell inside your `my-addon` folder:

```powershell
Compress-Archive -Path manifest.json,addon.py -DestinationPath ..\my-addon.zip
```

Or on Linux:

```bash
zip ../my-addon.zip manifest.json addon.py
```

In FTL, open **Add-ons**, choose **Install ZIP manually**, select your archive and then enable it under **Installed add-ons**. Your ZIP will be marked *Unverified* because it hasn't gone through the official catalogue.

If you change the code, remove the old add-on and install your new ZIP while testing. For releases in the approved catalogue, FTL has a separate update button.

## Making a game mod

A Cyberpunk 2077, ETS2 or other game mod can be published as an `external` catalogue entry. That lets people find the mod, download its ZIP and follow your installation instructions.

**An external mod cannot yet subscribe to live FTL lyrics.** The current API runs Python code inside the FTL process. There is no public HTTP, WebSocket or named-pipe API for a separate game process. You'll need to wait for that bridge before claiming your game mod can receive synchronized lyrics from FTL.

The catalogue entry only handles distribution. It doesn't install files into game directories.

## Getting your add-on approved

1. Publish your source code and a ZIP release. People should be able to see what they're installing.
2. Test the ZIP with the latest FTL. If it's a game mod, test the game-side installation too.
3. Fork the FollowTheLyrics repository and add your entry to `addons/catalog.json`.
4. Calculate the SHA-256 hash of your published ZIP and put it in the entry. See [addons.md](../addons.md) for the required fields and hash commands.
5. Open a pull request to the original project. Say what you've tested and link to the source code.

GitHub Actions will check the catalogue format, download the ZIP, verify its hash and, for Python plug-ins, check the manifest. It does **not** execute or approve the code. The maintainer still reviews it and decides whether to merge.

Once the change is merged into the catalogue used by FTL, people can find your add-on by refreshing the Add-ons tab.

## Releasing an update

Publish another ZIP, then open a PR changing the version, URL and SHA-256 in `addons/catalog.json`. Keep the same ID. Use numeric versions like `1.0.1` and `1.1.0` so FTL can compare them.

Don't replace a ZIP at the same URL without updating the hash. Existing catalogue entries should point to an exact release, not a moving "latest" download.

## A note about trust

Python plug-ins run as part of FTL with the same file and network access as the user running it. They are **not sandboxed**. Stick to what your add-on needs, avoid collecting information you don't need, and make any network access clear in the source code and description.

For a minimal starting point, see `addons/examples/hello/` in the repository.
