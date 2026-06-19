"""Fetch the latest YouTube videos and update index.html in place.

Reads YOUTUBE_CHANNEL_ID from the environment (required).
Rewrites the block between <!-- YOUTUBE_VIDEOS_START --> and
<!-- YOUTUBE_VIDEOS_END --> in index.html with fresh card HTML,
then exits 0. No external dependencies — stdlib only.
"""
from __future__ import annotations

import html
import os
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML_PATH = ROOT / "index.html"
YOUTUBE_FEED_BASE = "https://www.youtube.com/feeds/videos.xml"
YOUTUBE_VIDEOS_START = "<!-- YOUTUBE_VIDEOS_START -->"
YOUTUBE_VIDEOS_END = "<!-- YOUTUBE_VIDEOS_END -->"
LIMIT = 3


def _download_bytes(url: str, timeout: int = 12) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0 Safari/537.36"
            )
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _strip_html_tags(value: str) -> str:
    plain = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", plain).strip()


def _truncate(value: str, limit: int = 220) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "\u2026"


def fetch_videos(channel_id: str) -> list[dict[str, str]]:
    feed_url = f"{YOUTUBE_FEED_BASE}?channel_id={urllib.parse.quote(channel_id)}"
    print(f"Fetching {feed_url}")
    feed_bytes = _download_bytes(feed_url)
    root = ET.fromstring(feed_bytes)

    atom_ns = "{http://www.w3.org/2005/Atom}"
    media_ns = "{http://search.yahoo.com/mrss/}"
    yt_ns = "{http://www.youtube.com/xml/schemas/2015}"

    videos: list[dict[str, str]] = []
    for entry in root.findall(f"{atom_ns}entry")[:LIMIT]:
        video_id = (entry.findtext(f"{yt_ns}videoId") or "").strip()
        title = (entry.findtext(f"{atom_ns}title") or "Untitled Video").strip()
        description = (
            entry.findtext(f"{media_ns}group/{media_ns}description")
            or entry.findtext(f"{atom_ns}summary")
            or ""
        )
        description = _truncate(_strip_html_tags(description), 220)
        if video_id:
            videos.append({"title": title, "video_id": video_id, "description": description})

    return videos


def render_cards(videos: list[dict[str, str]]) -> str:
    cards: list[str] = []
    for video in videos:
        vid = html.escape(video["video_id"], quote=True)
        title_esc = html.escape(video["title"])
        desc_esc = html.escape(video["description"])
        onerror = (
            f"this.onerror=null;this.src="
            f"'https://i.ytimg.com/vi/{vid}/hqdefault.jpg';"
        )
        cards.append(
            "\n".join([
                f'            <a class="video-card" href="https://youtu.be/{vid}" target="_blank" rel="noopener">',
                f'                <div class="video-thumb" style="background: linear-gradient(135deg, #1a1a1a 0%, #222 100%);">',
                f'                    <img src="https://i.ytimg.com/vi/{vid}/maxresdefault.jpg" alt="{title_esc} thumbnail" loading="lazy" onerror="{onerror}">',
                f'                    <div class="play-btn">',
                f'                        <svg viewBox="0 0 24 24"><polygon points="5,3 19,12 5,21"/></svg>',
                f'                    </div>',
                f'                </div>',
                f'                <div class="video-info">',
                f'                    <h3>{title_esc}</h3>',
                f'                    <p>{desc_esc}</p>',
                f'                </div>',
                f'            </a>',
            ])
        )
    return "\n".join(cards)


def update_index_html(videos: list[dict[str, str]]) -> bool:
    """Inject video cards into index.html. Returns True if file changed."""
    text = INDEX_HTML_PATH.read_text(encoding="utf-8")

    start_idx = text.find(YOUTUBE_VIDEOS_START)
    end_idx = text.find(YOUTUBE_VIDEOS_END)
    if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
        print("ERROR: marker comments not found in index.html", file=sys.stderr)
        sys.exit(1)

    new_content = "\n" + render_cards(videos) + "\n        "
    new_text = (
        text[: start_idx + len(YOUTUBE_VIDEOS_START)]
        + new_content
        + text[end_idx:]
    )

    if new_text == text:
        print("index.html already up to date — no changes written.")
        return False

    INDEX_HTML_PATH.write_text(new_text, encoding="utf-8")
    print(f"index.html updated with {len(videos)} video(s).")
    return True


def main() -> None:
    channel_id = os.environ.get("YOUTUBE_CHANNEL_ID", "").strip()
    if not channel_id:
        print("ERROR: YOUTUBE_CHANNEL_ID environment variable is required.", file=sys.stderr)
        sys.exit(1)

    videos = fetch_videos(channel_id)
    if not videos:
        print("No videos found in feed — index.html not changed.")
        sys.exit(0)

    for v in videos:
        print(f"  [{v['video_id']}] {v['title']}")

    update_index_html(videos)


if __name__ == "__main__":
    main()
