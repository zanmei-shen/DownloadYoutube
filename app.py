from __future__ import annotations

import re
import shutil
import tempfile
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import streamlit as st
import yt_dlp


DOWNLOAD_DIR = Path(__file__).parent / "downloads"
YOUTUBE_HOSTS = {"music.youtube.com", "www.youtube.com", "youtube.com", "youtu.be"}
APP_VERSION = "2026.11.03.2"


def extract_video_id(url: str) -> str | None:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in YOUTUBE_HOSTS:
        return None

    if parsed.hostname == "youtu.be":
        video_id = parsed.path.strip("/")
    elif parsed.path == "/watch":
        video_id = parse_qs(parsed.query).get("v", [None])[0]
    elif parsed.path.startswith("/shorts/"):
        video_id = parsed.path.split("/")[2]
    else:
        video_id = None

    if video_id and re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        return video_id
    return None


def has_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def retry_download(operation, max_attempts: int = 3):
    for attempt in range(max_attempts):
        try:
            return operation()
        except yt_dlp.utils.DownloadError as error:
            if "The page needs to be reloaded" not in str(error):
                raise
            if attempt == max_attempts - 1:
                raise
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("Download retry failed.")


def youtube_watch_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def select_available_video_format(info: dict) -> str:
    formats = info.get("formats") or []

    combined = [
        item for item in formats
        if item.get("vcodec") not in (None, "none")
        and item.get("acodec") not in (None, "none")
    ]
    mp4_combined = [item for item in combined if item.get("ext") == "mp4"]
    if mp4_combined:
        return str(max(mp4_combined, key=lambda item: item.get("height") or 0)["format_id"])
    if combined:
        return str(max(combined, key=lambda item: item.get("height") or 0)["format_id"])

    videos = [
        item for item in formats
        if item.get("vcodec") not in (None, "none")
        and item.get("acodec") in (None, "none")
    ]
    audios = [
        item for item in formats
        if item.get("acodec") not in (None, "none")
        and item.get("vcodec") in (None, "none")
    ]
    if videos and audios:
        video = max(videos, key=lambda item: item.get("height") or 0)
        audio = max(
            audios,
            key=lambda item: item.get("abr") or item.get("tbr") or 0,
        )
        return f"{video['format_id']}+{audio['format_id']}"

    if formats:
        return str(formats[-1]["format_id"])
    return "best"


def download_track(
    url: str,
    output_format: str,
    browser: str,
    cookie_file: str | None,
    progress_callback,
) -> tuple[Path, dict]:
    DOWNLOAD_DIR.mkdir(exist_ok=True)
    output_template = str(DOWNLOAD_DIR / "%(title)s [%(id)s].%(ext)s")
    options: dict = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [progress_callback],
        "extractor_args": {
            "youtube": {
                "player_client": ["android"],
            }
        },
    }
    for runtime in ("node", "deno", "bun"):
        runtime_path = shutil.which(runtime)
        if runtime_path:
            options["js_runtimes"] = {runtime: {"path": runtime_path}}
            break
    if cookie_file:
        options["cookiefile"] = cookie_file
    elif browser != "None":
        options["cookiesfrombrowser"] = (browser.lower(),)

    if output_format == "mp3":
        options["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ]

    try:
        try:
            with yt_dlp.YoutubeDL(options) as downloader:
                def extract() -> tuple[dict, Path]:
                    info = downloader.extract_info(url, download=True)
                    return info, Path(downloader.prepare_filename(info))
                info, downloaded_path = retry_download(extract)
        except yt_dlp.utils.DownloadError as error:
            if "Requested format is not available" not in str(error):
                raise
            fallback_options = {**options, "format": "best"}
            try:
                with yt_dlp.YoutubeDL(fallback_options) as downloader:
                    info = downloader.extract_info(url, download=True)
                    downloaded_path = Path(downloader.prepare_filename(info))
            except yt_dlp.utils.DownloadError:
                fallback_options = {**options, "format": None}
                with yt_dlp.YoutubeDL(fallback_options) as downloader:
                    info = downloader.extract_info(url, download=True)
                    downloaded_path = Path(downloader.prepare_filename(info))
    except yt_dlp.utils.DownloadError as error:
        if "Requested format is not available" not in str(error):
            raise
        fallback_options = {**options, "format": None}
        with yt_dlp.YoutubeDL(fallback_options) as downloader:
            info = downloader.extract_info(url, download=True)
            downloaded_path = Path(downloader.prepare_filename(info))

    if output_format == "mp3":
        downloaded_path = downloaded_path.with_suffix(".mp3")
    elif not downloaded_path.is_file():
        candidates = sorted(downloaded_path.parent.glob(f"{downloaded_path.stem}.*"))
        if candidates:
            downloaded_path = candidates[0]

    if not downloaded_path.is_file():
        raise RuntimeError("The download completed, but the output file was not found.")
    return downloaded_path, info


def download_video(
    url: str,
    browser: str,
    cookie_file: str | None,
    progress_callback,
) -> tuple[Path, dict]:
    DOWNLOAD_DIR.mkdir(exist_ok=True)
    output_template = str(DOWNLOAD_DIR / "%(title)s [%(id)s].%(ext)s")
    options: dict = {
        "format": "18/b/best",
        "merge_output_format": "mp4",
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [progress_callback],
        "extractor_args": {
            "youtube": {
                "player_client": ["android"],
            }
        },
    }
    for runtime in ("node", "deno", "bun"):
        runtime_path = shutil.which(runtime)
        if runtime_path:
            options["js_runtimes"] = {runtime: {"path": runtime_path}}
            break
    if cookie_file:
        options["cookiefile"] = cookie_file
    elif browser != "None":
        options["cookiesfrombrowser"] = (browser.lower(),)

    format_attempts = (
        "18",
        "18/b",
        "b/best",
        "bv*+ba/b",
        None,
    )
    last_format_error: yt_dlp.utils.DownloadError | None = None
    for selected_format in format_attempts:
        attempt_options = {**options}
        if selected_format is None:
            attempt_options.pop("format", None)
        else:
            attempt_options["format"] = selected_format
        try:
            with yt_dlp.YoutubeDL(attempt_options) as downloader:
                def extract() -> tuple[dict, Path]:
                    info = downloader.extract_info(url, download=True)
                    return info, Path(downloader.prepare_filename(info))
                info, downloaded_path = retry_download(extract)
            break
        except yt_dlp.utils.DownloadError as error:
            last_format_error = error
            error_text = str(error)
            if (
                "Requested format is not available" not in error_text
                and "The page needs to be reloaded" not in error_text
            ):
                raise
    else:
        assert last_format_error is not None
        raise last_format_error

    downloaded_path = downloaded_path.with_suffix(".mp4")
    if not downloaded_path.is_file():
        candidates = sorted(downloaded_path.parent.glob(f"{downloaded_path.stem}.*"))
        candidates = [candidate for candidate in candidates if candidate.suffix.lower() in {
            ".mp4", ".mkv", ".webm"
        }]
        if candidates:
            downloaded_path = candidates[0]

    if not downloaded_path.is_file():
        raise RuntimeError("The download completed, but the video file was not found.")
    return downloaded_path, info


st.set_page_config(page_title="Music downloader", page_icon="♪", layout="centered")
st.title("YouTube downloader")
st.caption(f"App version {APP_VERSION}")
st.caption("Download one item at a time for which you have permission to save a local copy.")

with st.form("download_form"):
    url = st.text_input(
        "YouTube URL",
        placeholder="https://www.youtube.com/watch?v=...",
    )
    media_format = st.selectbox(
        "Download format",
        ("best available audio", "mp3", "mp4 video"),
    )
    browser = st.selectbox(
        "YouTube login cookies",
        ("None", "Chrome", "Edge", "Firefox", "Brave"),
        help=(
            "Choose the browser where YouTube Music works and you are signed in. "
            "Cookies are read locally and are not uploaded by this app."
        ),
    )
    cookie_upload = st.file_uploader(
        "Or upload a Netscape-format cookies.txt file",
        type=["txt"],
        help=(
            "Use this if browser cookie copying fails. Keep the exported file private."
        ),
    )
    with st.expander("How to export cookies.txt with Cookie-Editor"):
        st.markdown(
            """
1. Sign in to [YouTube](https://www.youtube.com/) in Microsoft Edge.
2. Open [Cookie-Editor for Microsoft Edge](https://microsoftedge.microsoft.com/addons/detail/ipgijfejghfgeijfkaeifmiljcmomleo).
3. Add the extension, then open its toolbar menu.
4. On YouTube, select **Export**.
5. Choose **Netscape** or **cookies.txt**, not Header or JSON.
6. Save the file as `cookies.txt`.
7. Upload that file using **Or upload a Netscape-format cookies.txt file** above.

Keep `cookies.txt` private. It contains login session information.
"""
        )
    submitted = st.form_submit_button("Download", type="primary")

if submitted:
    video_id = extract_video_id(url)
    if video_id is None:
        st.error("Enter a valid single YouTube or YouTube Music URL.")
        st.stop()
    canonical_url = youtube_watch_url(video_id)
    if media_format in {"mp3", "mp4 video"} and not has_ffmpeg():
        st.error(
            "MP3 conversion and MP4 video downloads require FFmpeg. Install FFmpeg "
            "and add it to PATH, or choose best available audio."
        )
        st.stop()

    progress = st.progress(0, text="Starting download...")

    def update_progress(status: dict) -> None:
        if status.get("status") == "downloading":
            total = status.get("total_bytes") or status.get("total_bytes_estimate")
            current = status.get("downloaded_bytes", 0)
            if total:
                progress.progress(min(current / total, 1.0), text="Downloading...")
        elif status.get("status") == "finished":
            progress.progress(1.0, text="Processing audio...")

    cookie_path: str | None = None
    try:
        if cookie_upload is not None:
            with tempfile.NamedTemporaryFile(
                mode="wb", suffix=".txt", delete=False
            ) as temporary_cookie_file:
                temporary_cookie_file.write(cookie_upload.getvalue())
                cookie_path = temporary_cookie_file.name

        with st.spinner("Fetching media metadata..."):
            if media_format == "mp4 video":
                output_path, info = download_video(
                    canonical_url, browser, cookie_path, update_progress
                )
            else:
                output_format = "mp3" if media_format == "mp3" else "best available"
                output_path, info = download_track(
                    canonical_url, output_format, browser, cookie_path, update_progress
                )
    except yt_dlp.utils.DownloadError as error:
        progress.empty()
        error_text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", str(error))
        if "Could not copy Chrome cookie database" in error_text:
            st.error(
                "yt-dlp could not copy Chrome's cookie database. Close every Chrome "
                "window and retry, or export a Netscape-format cookies.txt file and "
                "upload it above. You can also try Edge or Firefox."
            )
        elif "The page needs to be reloaded" in error_text:
            st.error(
                "YouTube temporarily returned a reload-required response. The app "
                "retried automatically. Wait a moment, refresh the page, and retry."
            )
        elif "This video is not available" in error_text:
            st.error(
                "YouTube reports that this video is unavailable. It may be private, "
                "deleted, blocked in this region, or require you to sign in. Try "
                "opening the URL directly in a browser and confirm that it is playing."
            )
        elif "403" in error_text or "Forbidden" in error_text:
            st.error(
                "YouTube rejected the media request (HTTP 403). Update yt-dlp, "
                "verify the track plays in your selected browser, then retry."
            )
        else:
            st.error(f"Download failed: {error_text}")
        st.stop()
    except RuntimeError as error:
        progress.empty()
        st.error(str(error))
        st.stop()
    except OSError as error:
        progress.empty()
        st.error(f"Could not save the file: {error}")
        st.stop()
    finally:
        if cookie_path:
            Path(cookie_path).unlink(missing_ok=True)

    progress.progress(1.0, text="Ready")
    title = info.get("title", output_path.stem)
    st.success(f"Ready: {title}")
    if media_format == "mp4 video":
        mime = "video/mp4"
    elif media_format == "mp3":
        mime = "audio/mpeg"
    else:
        mime = "audio/*"
    st.download_button(
        "Save file",
        data=output_path.read_bytes(),
        file_name=output_path.name,
        mime=mime,
        type="primary",
    )

st.divider()
st.caption(
    "Use this only for content you own or are authorized to download. "
    "YouTube's terms and copyright law may restrict downloading."
)
