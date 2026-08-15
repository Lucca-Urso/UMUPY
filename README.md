# UMUPY — Urso Music Uploader Python

Desktop app to download YouTube music as high-quality MP3 files with artwork embedding optimized for **Rekordbox** and **Pioneer CDJs**, convert Spotify playlists to YouTube, create Rekordbox playlists and keep local folders in sync with Spotify.

Supports **Windows** and **macOS**.

---

## Project Structure

```
UMUPY/
├── Features/                    Backend scripts (one per feature)
│   ├── yt_downloader.py         Download YouTube videos/playlists as MP3
│   └── fix_artwork.py           Embed square 800x800 artwork + tags into MP3s
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
