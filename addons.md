# Add-ons

The add-on catalogue lives in the main FollowTheLyrics repository. There is no separate dashboard to manage, and add-on authors can't publish directly into the app.

## Getting an add-on listed

When somebody makes an integration, they publish the code and provide a downloadable ZIP. They then open a pull request adding an entry to `addons/catalog.json`.

Before merging it, check that:

- The download works and the ZIP contains what the author says it does.
- The integration works with the current FollowTheLyrics release.
- The author explains how to install it and what else it needs.
- Any code that runs on the user's computer has been reviewed. In particular, check for unrelated network requests, credential access and unexpected file changes.
- The SHA-256 hash in the catalogue matches the actual release ZIP.

If you're happy with it, merge the PR. That's the approval. You don't have to build a new version of FTL just to make an approved add-on appear.

FTL currently reads the catalogue from:

`https://raw.githubusercontent.com/War3l/FollowTheLyrics/main/addons/catalog.json`

That file needs to exist on the `main` branch for the catalogue to load. If you host it somewhere else, change `CATALOGUE_URL` in `src/followthelyrics/addons/catalogue.py`.

## Adding an entry

There are two types of add-on:

- `ftl`: a Python plug-in loaded by FollowTheLyrics itself. The app can install, enable, disable, update and remove it.
- `external`: a separate game or application mod that works alongside FTL. The app downloads the ZIP and shows the installation instructions. It does **not** put files into the game's directory for the user.

An entry looks like this:

```json
{
  "addons": [
    {
      "id": "example-game-integration",
      "name": "Example Game Integration",
      "version": "1.0.0",
      "description": "Displays lyrics inside the game.",
      "type": "external",
      "download_url": "https://example.org/releases/example-game-integration.zip",
      "sha256": "PUT_THE_REAL_64_CHARACTER_SHA256_HASH_HERE",
      "instructions": "Download the ZIP and follow the mod author's installation guide."
    }
  ]
}
```

The URL and hash above are placeholders. Don't put the example into the live catalogue as-is.

Keep each `id` unique and lowercase. Letters, numbers, hyphens and underscores are supported. Use numeric versions such as `1.0.0` or `1.2.3` so FTL can tell when an update is newer.

The download must use HTTPS. FTL checks the ZIP against the published SHA-256 hash before accepting it.

To get the hash:

```powershell
Get-FileHash .\my-addon.zip -Algorithm SHA256
```

Or on Linux:

```bash
sha256sum my-addon.zip
```

Copy the hash into the catalogue entry exactly as shown. If the ZIP changes, recalculate it.

## Packaging an FTL plug-in

An `ftl` ZIP needs `manifest.json` and a Python entry file at the **root** of the archive, not buried inside another folder.

Example `manifest.json`:

```json
{
  "id": "example-addon",
  "name": "Example Add-on",
  "version": "1.0.0",
  "description": "A small example integration.",
  "api_version": 1,
  "entry": "addon.py"
}
```

The entry file can define these functions:

```python
def on_enable(api):
    api.log("Started")


def on_track(track):
    if track:
        print(track["artist"], track["title"])


def on_lyrics(key, lines):
    print(key, len(lines))


def on_disable():
    pass
```

All four functions are optional. `on_enable` receives an API object with `api_version`, `addon_id` and `log(message)`. `on_track` receives a dictionary with song details, or `None` when playback stops. `on_lyrics` receives the track key and a list of lyric dictionaries containing `time`, `text` and `end`.

There is a working example in `addons/examples/hello/`. Put its two files at the root of a ZIP to try manual installation.

## Publishing updates

When an author releases a new version:

1. Download and review the new ZIP.
2. Test it against FTL.
3. Change the version, download URL and SHA-256 hash in `addons/catalog.json`.
4. Merge the catalogue change.

FTL compares numeric versions. Users with an older FTL plug-in see **Update** in the Add-ons tab. FTL verifies the new download, replaces the installed plug-in and keeps its enabled setting. If the replacement cannot start, the previous version is restored.

For external game mods, FTL remembers the version of the ZIP the user last downloaded. It can offer a newer ZIP, but it cannot tell whether the user has actually installed that version in the game.

## Removing an entry

Remove the entry from the catalogue and merge the change. It will disappear from the approved list after the user refreshes. This does **not** remotely uninstall files that users already have.

If an add-on is unsafe, it is worth mentioning that in the release notes or an advisory so existing users know to remove it.

## Manual installation

People can also install an `ftl` ZIP that isn't in the approved catalogue. These are shown as **Unverified** and start disabled. Users must explicitly agree before installing and enabling them.

Approval isn't a security sandbox. Python plug-ins run with the user's own permissions and can access files or the network. SHA-256 verification proves that a download matches the catalogue entry, not that its code is safe. That's why the review step matters.

## Before accepting this upstream

Test the whole flow in packaged Windows and Linux builds, not just from Python. That includes a good plug-in, a broken plug-in, a version update and a game-side ZIP. The catalogue is currently empty until real entries are approved and published.
