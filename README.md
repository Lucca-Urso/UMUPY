# UMUPY — Urso Music Uploader Python

Desktop app that turns online playlists into MP3 files ready for **RekordBox** and **Pioneer CDJs**, and keeps your local folders and RekordBox playlists in sync with them. Works on **macOS** and **Windows**, fully offline except for the downloads themselves.

## What it does

- **Downloader** — paste YouTube, Spotify or SoundCloud links (as many as you want). Tracks are matched across services when one of them does not have the song, downloaded in parallel as MP3 with square 800×800 artwork, and tagged so duplicates are recognised later.
- **Synchronizer** — pick what should stay in sync (a local folder or a RekordBox playlist) and where the music comes from (online playlists or a local folder). Shows what is missing and what is extra; nothing is downloaded, deleted or written to RekordBox without your confirmation.
- **Playlist Builder** — create RekordBox playlists from a `.xml`/`.txt` playlist file or a folder of music.
- **History** — every operation with per-track results and the reason for each failure.
- **Setup** — connect Spotify and your YouTube login from inside the app. No files to edit.

## Install and run

Requirements: [Python 3.10+](https://www.python.org/downloads/), [Node.js 18+](https://nodejs.org) (only to build the interface), [FFmpeg](https://ffmpeg.org/download.html) and [Deno](https://deno.com) (or drop their binaries in `bin/`).

```bash
./project --setup     # Windows: project --setup
./project --run
```

`--setup` installs the Python packages, builds the interface and runs the tests. Other commands: `--test`, `--ui` (rebuild the interface), `--dev` (interface with hot reload).

Packaged app: `python3 -m PyInstaller --noconfirm umupy.spec` produces `dist/UMUPY.app` (macOS) or `dist/UMUPY/UMUPY.exe` (Windows). Binaries placed in `bin/` are shipped inside it. The packaged app keeps its data in `~/UMUPY/`.

## Dependencies

| Package | Role |
|---|---|
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) + [yt-dlp-ejs](https://github.com/yt-dlp/yt-dlp/wiki/EJS) | Download and metadata for YouTube and SoundCloud |
| [spotipy](https://spotipy.readthedocs.io) | Read Spotify playlists |
| [ytmusicapi](https://ytmusicapi.readthedocs.io) | Find YouTube equivalents of Spotify tracks |
| [thefuzz](https://github.com/seatgeek/thefuzz) | Fuzzy title/artist matching |
| [mutagen](https://mutagen.readthedocs.io) | Read and write MP3 tags |
| [Pillow](https://pillow.readthedocs.io) | Artwork processing |
| [pyrekordbox](https://pyrekordbox.readthedocs.io) | Read and write the RekordBox database |
| [pywebview](https://pywebview.flowrl.com) | Desktop window for the React interface |
| FFmpeg, Deno | Audio conversion and YouTube challenge solving |

## Project structure

```
app.py                Entry point (window, packaged-app helpers)
project.py            Task runner behind the `project` command
api/                  Methods exposed to the interface, one module per action
  downloader.py       Link analysis and downloads
  synchronizer.py     Folder comparison and orphan cleanup
  chain.py            Online playlist → folder → RekordBox in one flow
  playlist_builder.py RekordBox playlist creation and folder sync
  setup.py            Spotify keys, browser cookies, tool checks
Features/             Core logic, also usable from the terminal
  providers/          youtube, spotify, soundcloud (common interface)
  matching.py         Cross-provider fallback search
  download_engine.py  Parallel downloads, rate limits, automatic pause on blocks
  library.py          Index of local MP3s by provider id
  rekordbox_sync.py   Folder ↔ RekordBox playlist diff and apply
  fix_artwork.py      Artwork + YOUTUBE_ID / SPOTIFY_ID / SOUNDCLOUD_ID tags
  history.py          SQLite log of every run
UI/                   React + Vite + Tailwind interface (views, components, hooks)
tests/                Unit tests, one file per feature (pytest, ≥95% coverage)
Dependencies/         Your credentials and settings (never committed)
Downloads/ History/   Music and logs (never committed)
```

## Interface

Home → **Downloader · Synchronizer · Playlist Builder · History**, plus a Setup link in the footer. Every screen has a `?` button with a three-line explanation. The Synchronizer always follows one direction: online playlist → local folder → RekordBox.

## Setup notes

- **Spotify**: create a free app at [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) with redirect URI `http://127.0.0.1:8888/callback` and paste its Client ID and Secret in Setup. The first use opens the browser once to authorize.
- **YouTube login (optional)**: in Setup, choose the browser where you are signed in. Safari and Firefox are read directly; Chrome-family browsers ask macOS for permission to unlock their cookies. Use a secondary Google account when possible.
- **RekordBox**: close it before applying changes. A copy of `master.db` is saved in `History/rekordbox_backups/` before every write.

## Safety

Downloads run at most 3 at a time for YouTube and 2 for SoundCloud, with delays and a global hourly cap. If a service answers with a rate limit or a bot check, all downloads pause automatically and resume later. Credentials stay in `Dependencies/` with restricted permissions and are ignored by git.

## References

[yt-dlp](https://github.com/yt-dlp/yt-dlp) · [Spotify for Developers](https://developer.spotify.com) · [pyrekordbox](https://github.com/dylanljones/pyrekordbox) · [RekordBox XML format](https://cdn.rekordbox.com/files/20200410160904/xml_format_list.pdf) · [FFmpeg](https://ffmpeg.org) · [Deno](https://deno.com)
