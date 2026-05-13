# YouTube Downloader

A Python script that downloads YouTube videos and playlists as high-quality MP3 files, with automatic artwork embedding optimized for **Rekordbox** and **Pioneer CDJs**. Created to download musics directly in RekordBox or any other DJ software :)

Supports **Windows** and **macOS**.

---

## Requirements

- **Python 3.8+** — [python.org](https://www.python.org/downloads/)
- **FFmpeg** — [ffmpeg.org](https://ffmpeg.org/download.html)
- **yt-dlp**, **mutagen**, **Pillow** — installed via pip

Install the Python dependencies:

```bash
pip install yt-dlp mutagen pillow
```

For **FFmpeg**, either install it globally so it is available on your system PATH, or place the `ffmpeg` / `ffmpeg.exe` binary directly inside the script directory — the script will find it automatically either way.

---

## Getting YouTube Cookies

YouTube requires authentication to access age-restricted content and avoid rate limiting. Export your browser cookies using a browser extension such as **Get cookies.txt LOCALLY** (available for Chrome and Firefox), and place the resulting `cookies.txt` file inside the script directory.

---

## Running the Script

**Windows:**
```bash
python yt_download_manager.py
```

**macOS:**
```bash
python3 yt_download_manager.py
```

You will be prompted to enter a YouTube URL. After each download session, the script will ask if you want to download another URL. Type `y` to continue or `n` to exit.

---

## How It Works

### Single Video
Paste a regular YouTube video URL. The MP3 is saved directly into the **library root** (the parent folder of the script directory).

### Playlist
Paste a YouTube playlist URL. The script automatically creates a new folder inside the **library root** named after the playlist with the current date appended:

```
PlaylistName_DD_MM/
```

Each track is saved inside that folder.

### Artwork Processing
After each track is downloaded, the script automatically:

1. Reads the thumbnail saved by yt-dlp
2. Center-crops it to a square (fixes YouTube's 16:9 thumbnails)
3. Resizes it to **800×800px** (Pioneer CDJ maximum)
4. Re-saves it as **JPEG at 300 DPI** (Rekordbox requirement)
5. Embeds it into the MP3 as an **ID3v2.3 APIC tag**

This happens track by track in real time, not after the full playlist finishes.

### Duplicate Detection
At startup, the script scans every MP3 in all subdirectories of the library root and reads the `YOUTUBE_ID` tag embedded in each file. Any video already present in your library — regardless of which folder it lives in — will be skipped automatically, without relying on an external `archive.txt` file.

---

## Supported Platforms

| Feature | Windows | macOS |
|---|---|---|
| Single video download | ✅ | ✅ |
| Playlist download | ✅ | ✅ |
| Automatic artwork embedding | ✅ | ✅ |
| Duplicate detection | ✅ | ✅ |
| FFmpeg auto-detection (PATH or local) | ✅ | ✅ |
