# FollowTheLyrics fork: Windows releases and automatic updates

This fork retains the upstream release pipeline, built-in update prompt, and Windows installer/shortcut support. The updater now downloads a replacement executable, closes the running application, replaces it from a separate PowerShell helper, and relaunches the new version. Configuration and profiles are kept in `%APPDATA%\FollowTheLyrics` by frozen builds.

## One-time setup

1. Use the existing public fork at **https://github.com/ValleryJS/FollowTheLyrics**. Commit and push the updated project files to its `main` branch (or open a pull request and merge it).
2. The update source is already configured in `src/followthelyrics/version.py` as `ValleryJS/FollowTheLyrics`.
3. Ensure GitHub Actions is enabled and workflow permissions allow **Read and write** where required by your repository policy. `release.yml` declares `contents: write`.
4. GitHub → Actions → **Release** → **Run workflow**. Specify a **newer** version than `2.1.5`, for example `2.1.6`, and optionally add release notes. Run from the `main` branch.
5. The workflow runs tests, builds the Windows EXE (and Linux binary), tags the version, then publishes GitHub Release assets. Download your `FollowTheLyrics.exe` from **your** Releases page once, launch it, and choose the built-in install option to get a Start Menu shortcut.
6. Future releases: push changes and run **Release** again with the next version. The installed executable checks automatically (startup and every six hours). Click Update when prompted. It will close, update, and reopen.

## Important limitations

- **The GitHub repository exists, but this ZIP has not been pushed to it.** You must commit and push the updated files.
- A release EXE has **not** been built in this environment. GitHub Actions must build it on Windows.
- The built-in updater requires a public GitHub Releases API endpoint. For private repositories, authorization would need a different update design.
- Windows update installation uses PowerShell, which may be disabled by company policies or endpoint security tools. Failure details are written to `%TEMP%\FollowTheLyrics-update-error.log`.
- Installing a single EXE under `Program Files` without elevated permissions can prevent self-updates. Use the app's normal per-user installation location.
- Windows binaries will be unsigned unless you provide your own code signing certificate. SmartScreen can warn about unsigned files.
- No hot reload: changes still require a released new build and a restart; users no longer need to run `run.bat`.
- Use your fork's releases only; do not publish modified code under the original author's account.

## Local development

Keep using `run.bat` *only while developing from Python source*. End users launch the compiled `FollowTheLyrics.exe` directly or via Start Menu shortcut. Testing a GitHub update requires running a previously installed version and publishing a newer release.
