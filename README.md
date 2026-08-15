# UMUPY — Urso Music Uploader Python

Desktop app to download YouTube music as high-quality MP3 files with artwork embedding optimized for **Rekordbox** and **Pioneer CDJs**, convert Spotify playlists to YouTube, create Rekordbox playlists and keep local folders in sync with Spotify.

Supports **Windows** and **macOS**.

---

## Requirements

- **Python 3.10+** — [python.org](https://www.python.org/downloads/)
- **FFmpeg** — `brew install ffmpeg` (macOS) or [ffmpeg.org](https://ffmpeg.org/download.html)
- **Deno** — `brew install deno` (macOS) or [deno.com](https://deno.com). Required by yt-dlp to solve YouTube's JavaScript challenges; without it downloads fail with 403 errors.
- **Node.js 18+** — only for building the frontend
- Python dependencies:

```bash
pip install -r requirements.txt
```

For **FFmpeg**, either install it globally so it is available on your system PATH, or place the `ffmpeg` / `ffmpeg.exe` binary inside `Dependencies/` — it is detected automatically either way.

## Running the App

```bash
cd UI && npm install && npm run build && cd ..   # first time only
python3 app.py
```

The UMUPY window opens with one card per feature:

- **YouTube Downloader** — paste a video or playlist URL, optionally scan `Downloads/` folders for duplicates, review the track list with checkboxes and run the batch download with live progress and a final failure report.
- **Spotify Converter** — paste a Spotify playlist URL; each track is matched to its best YouTube equivalent with live progress, then downloaded through the same pipeline.
- **RekordBox Playlists** — pick a `.txt`/`.xml` export, a folder of exports, or a downloaded music folder; preview every playlist and track before writing them into the RekordBox database (RekordBox must be closed).
- **Playlist Sync** — compare a Spotify playlist against a local folder: delete local orphans (with confirmation) and download missing tracks straight into the folder.
- **History** — browse every past operation with per-track status and error messages.

Development mode (frontend hot reload):

```bash
cd UI && npm run dev &
python3 app.py --dev
```

After changing the frontend, rebuild it once so the app picks it up: `cd UI && npm run build`

## Packaging (clickable app)

```bash
pip install pyinstaller
cd UI && npm run build && cd ..
python3 -m PyInstaller --noconfirm umupy.spec
```

On macOS the bundle lands in `dist/UMUPY.app` — move it to Applications if you like. On Windows the same command produces `dist/UMUPY/UMUPY.exe`. The packaged app keeps its data in `~/UMUPY/` (`Downloads/`, `Dependencies/` with cookies and Spotify credentials, `History/`). FFmpeg and Deno must be installed on the system.

---

## Project Structure

```
UMUPY/
├── app.py                       Desktop app entry point (pywebview)
├── umupy.spec                   PyInstaller packaging recipe
├── Features/                    Backend scripts (one per feature)
│   ├── yt_downloader.py         Download YouTube videos/playlists as MP3
│   ├── fix_artwork.py           Embed square 800x800 artwork + tags into MP3s
│   ├── rekordbox_playlist_creator.py  Create RekordBox playlists from exports or folders
│   ├── spotify_converter.py     Convert Spotify playlists to YouTube downloads
│   ├── sync_playlists.py        Sync a local folder against a Spotify playlist
│   └── history.py               Operation history (SQLite + txt logs)
├── Dependencies/                External binaries and credentials (not versioned)
│   ├── ffmpeg.exe               FFmpeg binary (Windows fallback)
│   ├── ffprobe.exe              FFprobe binary (Windows fallback)
│   ├── cookies.txt              YouTube cookies (optional)
│   └── spotify_credentials.json Spotify API credentials
├── Downloads/                   Where downloaded music lands (contents not versioned)
├── History/                     Operation logs and local database (not versioned)
├── UI/                          Frontend (React + Vite + Tailwind, via pywebview)
└── requirements.txt
```

## YouTube Cookies

YouTube requires authentication to access age-restricted content and avoid rate limiting. Export your browser cookies using an extension such as **Get cookies.txt LOCALLY** and place the resulting file inside `Dependencies/`. Prefer a throwaway Google account, and export from a private/incognito session so the browser does not rotate the cookies right after export.

## Spotify Setup (one time)

Required by the Spotify Converter and Playlist Sync:

1. Create a free app at [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) with redirect URI `http://127.0.0.1:8888/callback`
2. Save `Dependencies/spotify_credentials.json`:

```json
{"client_id": "...", "client_secret": "...", "redirect_uri": "http://127.0.0.1:8888/callback"}
```

The first conversion opens the browser once for Spotify login; the token is cached afterwards.

## Command Line Usage

Every feature also works standalone in the terminal:

```bash
python3 Features/yt_downloader.py
python3 Features/spotify_converter.py [playlist_url]
python3 Features/rekordbox_playlist_creator.py [source_path]
python3 Features/sync_playlists.py [playlist_url] [local_folder]
python3 Features/fix_artwork.py "path/to/file.mp3" [youtube_video_id] [spotify_track_id]
```

### Downloader behavior

- **Single video**: the MP3 is saved into the project's `Downloads/` folder.
- **Playlist**: a `Downloads/PlaylistName_DD_MM/` folder is created and each track is saved inside it.
- **Duplicate detection**: choose which `Downloads/` subfolders to scan (or all); every MP3 is indexed by its embedded `YOUTUBE_ID`/`SPOTIFY_ID` tags and already-downloaded tracks are skipped.

### Artwork processing

After each track downloads, `fix_artwork.py` runs automatically and:

1. Reads the thumbnail saved by yt-dlp
2. Center-crops it to a square
3. Resizes it to **800×800px** (Pioneer CDJ maximum)
4. Re-saves it as **JPEG at 300 DPI** (Rekordbox requirement)
5. Embeds it into the MP3 as an **ID3v2.3 APIC tag**, along with the `YOUTUBE_ID` (and `SPOTIFY_ID` when converted from Spotify) tags used for duplicate detection and sync

## History

Every operation (downloads, conversions, RekordBox imports, sync checks and deletions) is recorded in `History/history.db` (SQLite) with a unique run id, timestamps and per-track status including error messages, plus a human-readable log file per run in `History/logs/`. Browse it in the app through the History screen.
