# UMUPY — Urso Music Uploader Python

Desktop app to download YouTube music as high-quality MP3 files with artwork embedding optimized for **Rekordbox** and **Pioneer CDJs**, convert Spotify playlists to YouTube, create Rekordbox playlists and keep local folders in sync with Spotify.

Supports **Windows** and **macOS**.

---

## Running the App

```bash
python3 app.py
```

The UMUPY window opens with one card per feature. The YouTube Downloader flow: paste a URL, optionally scan Downloads folders for duplicates, review the track list with checkboxes and start the batch download with live progress.

Development mode (frontend hot reload):

```bash
cd UI && npm run dev &
python3 app.py --dev
```

After changing the frontend, rebuild it once so the app picks it up:

```bash
cd UI && npm run build
```

---

## Project Structure

```
UMUPY/
├── app.py                       Desktop app entry point (pywebview)
├── Features/                    Backend scripts (one per feature)
│   ├── yt_downloader.py         Download YouTube videos/playlists as MP3
│   ├── fix_artwork.py           Embed square 800x800 artwork + tags into MP3s
│   ├── rekordbox_playlist_creator.py  Create RekordBox playlists from .txt/.xml
│   ├── spotify_converter.py     Convert Spotify playlists to YouTube downloads
│   ├── sync_playlists.py        Sync a local folder against a Spotify playlist
│   └── history.py               Operation history (SQLite + txt logs)
├── Dependencies/                External binaries and credentials (not versioned)
│   ├── ffmpeg.exe               FFmpeg binary (Windows fallback)
│   ├── ffprobe.exe              FFprobe binary (Windows fallback)
│   └── cookies.txt
├── Downloads/                   Where downloaded music lands (contents not versioned)
├── History/                     Operation logs and local database (not versioned)
├── UI/                          Frontend (React + Vite + Tailwind, via pywebview)
└── requirements.txt
```

## Requirements

- **Python 3.10+** — [python.org](https://www.python.org/downloads/)
- **FFmpeg** — [ffmpeg.org](https://ffmpeg.org/download.html)
- Python dependencies:

```bash
pip install -r requirements.txt
```

For **FFmpeg**, either install it globally so it is available on your system PATH (recommended on macOS: `brew install ffmpeg`), or place the `ffmpeg` / `ffmpeg.exe` binary inside `Dependencies/` — it is detected automatically either way.

## YouTube Cookies

YouTube requires authentication to access age-restricted content and avoid rate limiting. Export your browser cookies using an extension such as **Get cookies.txt LOCALLY** and place the resulting file inside `Dependencies/`. Prefer a throwaway Google account for this.

## Spotify Converter

`spotify_converter.py` reads a Spotify playlist through the official Web API, finds the best YouTube equivalent for each track (fuzzy matching on title, artist and duration) and downloads everything through the regular download pipeline, embedding both `YOUTUBE_ID` and `SPOTIFY_ID` tags.

Setup (one time):

1. Create a free app at [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) with redirect URI `http://127.0.0.1:8888/callback`
2. Save `Dependencies/spotify_credentials.json`:

```json
{"client_id": "...", "client_secret": "...", "redirect_uri": "http://127.0.0.1:8888/callback"}
```

Then run:

```bash
python3 Features/spotify_converter.py [playlist_url]
```

The first run opens the browser once for Spotify login; the token is cached afterwards.

## Running the Downloader (CLI)

```bash
python3 Features/yt_downloader.py
```

You will be prompted for a YouTube video or playlist URL.

- **Single video**: the MP3 is saved into the project's `Downloads/` folder.
- **Playlist**: a `Downloads/PlaylistName_DD_MM/` folder is created and each track is saved inside it.

### Artwork Processing

After each track downloads, `fix_artwork.py` runs automatically and:

1. Reads the thumbnail saved by yt-dlp
2. Center-crops it to a square
3. Resizes it to **800×800px** (Pioneer CDJ maximum)
4. Re-saves it as **JPEG at 300 DPI** (Rekordbox requirement)
5. Embeds it into the MP3 as an **ID3v2.3 APIC tag**, along with a `YOUTUBE_ID` tag used for duplicate detection

It can also be run manually:

```bash
python3 Features/fix_artwork.py "path/to/file.mp3" "youtube_video_id"
```

### Duplicate Detection

At startup the downloader can scan every MP3 inside the project's `Downloads/` folder (recursively) and read the `YOUTUBE_ID` tag embedded in each file. Any video already present is skipped automatically.
