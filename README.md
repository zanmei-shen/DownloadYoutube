# YouTube downloader

Small Streamlit app for downloading a single authorized YouTube video or track
as MP4, MP3, or the best available audio format.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Or double-click `run.bat`.

MP3 and MP4 output require [FFmpeg](https://ffmpeg.org/) installed and
available on your `PATH`. The app can download a single YouTube URL, including
a YouTube radio or playlist URL, by extracting the video ID.

If YouTube returns HTTP 403, first update the dependencies and select the
browser where the track plays successfully. The app reads that browser's
cookies locally; it does not upload them. YouTube may additionally require a
JavaScript runtime or proof-of-origin token for some networks and clients.

If browser cookie copying fails, sign in to YouTube in Microsoft Edge and use
the Cookie-Editor extension. Export cookies in **Netscape/cookies.txt** format
and upload the file in the app. Treat that file like a password and do not
share it.

Only download tracks you own or have permission to save. The app intentionally
does not support playlists or DRM bypassing.
