Place platform binaries here before packaging so they ship inside the app:

- macOS: `ffmpeg`, `ffprobe` (static builds from https://evermeet.cx/ffmpeg/) and `deno` (https://deno.com)
- Windows: `ffmpeg.exe`, `ffprobe.exe` (https://www.gyan.dev/ffmpeg/builds/) and `deno.exe`

UMUPY looks here first, then in `Dependencies/`, then on the system PATH.
