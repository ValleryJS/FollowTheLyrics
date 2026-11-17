# Optional lyric text glow

Based on FollowTheLyrics 2.1.5.

- **Style > Text effects > Text glow** is off by default.
- Switching it on restores the original coloured glow and blurred dark shadow around lyric text.
- Switching it off removes those blurred halos; lyric colour, animations, and solid glyphs remain intact.
- The typewriter cursor also loses its decorative glow when disabled.
- The toggle updates the live overlay and style preview without restarting and persists in `config.json` as `text_glow`.
- Includes English, French, Spanish, and Chinese labels.

Validation: Python compileall and settings tests passed. Full GUI test suite requires PyQt6, which was unavailable in the build environment.
