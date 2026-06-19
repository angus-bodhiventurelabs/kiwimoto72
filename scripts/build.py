from __future__ import annotations

from pathlib import Path
import html
import json
import os
import re
import shutil
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

import markdown

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
CONTENT_DIR = ROOT / "content" / "posts"
TEMPLATE_PATH = ROOT / "templates" / "post.html"
DIST_DIR = ROOT / "dist"
BLOG_DIR = DIST_DIR / "blog"
ROOT_INDEX_PATH = ROOT / "index.html"
PODCAST_EPISODES_START = "<!-- PODCAST_EPISODES_START -->"
PODCAST_EPISODES_END = "<!-- PODCAST_EPISODES_END -->"
DEFAULT_PODCAST_SITE_URL = "https://kiwimoto72.buzzsprout.com"

YOUTUBE_VIDEOS_START = "<!-- YOUTUBE_VIDEOS_START -->"
YOUTUBE_VIDEOS_END = "<!-- YOUTUBE_VIDEOS_END -->"
YOUTUBE_CHANNEL_HANDLE = os.getenv("YOUTUBE_CHANNEL_HANDLE", "kiwimoto72").lstrip("@")
YOUTUBE_CHANNEL_ID = os.getenv("YOUTUBE_CHANNEL_ID", "").strip()
YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"
YOUTUBE_FEED_BASE = "https://www.youtube.com/feeds/videos.xml"


def _download_bytes(url: str, timeout: int = 12) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def _strip_html_tags(value: str) -> str:
    plain = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", plain).strip()


def _truncate(value: str, limit: int = 220) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def discover_podcast_rss_url() -> str:
    explicit_feed_url = os.getenv("PODCAST_RSS_URL", "").strip()
    if explicit_feed_url:
        return explicit_feed_url

    podcast_site_url = os.getenv("PODCAST_SITE_URL", DEFAULT_PODCAST_SITE_URL).strip()
    if not podcast_site_url:
        return ""

    try:
        page_html = _download_bytes(podcast_site_url, timeout=12).decode("utf-8", errors="ignore")
    except Exception as exc:
        print(f"Podcast sync skipped: unable to fetch podcast site ({exc})")
        return ""

    match = re.search(
        r'<link[^>]+type=["\']application/(?:rss|atom)\+xml["\'][^>]+href=["\']([^"\']+)["\']',
        page_html,
        flags=re.IGNORECASE,
    )
    if not match:
        match = re.search(
            r'<link[^>]+href=["\']([^"\']+)["\'][^>]+type=["\']application/(?:rss|atom)\+xml["\']',
            page_html,
            flags=re.IGNORECASE,
        )
    if not match:
        match = re.search(
            r'href=["\']([^"\']*\.(?:rss|xml)(?:\?[^"\']*)?)["\']',
            page_html,
            flags=re.IGNORECASE,
        )

    if not match:
        print("Podcast sync skipped: RSS link not found on podcast site")
        return ""

    rss_href = match.group(1).strip()
    if not rss_href:
        print("Podcast sync skipped: RSS link was empty")
        return ""

    return urllib.parse.urljoin(podcast_site_url, rss_href)


def fetch_latest_podcast_episodes(limit: int = 3) -> list[dict[str, str]]:
    feed_url = discover_podcast_rss_url()
    if not feed_url:
        print("Podcast sync skipped: no RSS feed URL available")
        return []

    try:
        rss_bytes = _download_bytes(feed_url, timeout=12)
    except Exception as exc:
        print(f"Podcast sync skipped: unable to download RSS feed ({exc})")
        return []

    try:
        root = ET.fromstring(rss_bytes)
    except ET.ParseError as exc:
        print(f"Podcast sync skipped: RSS XML parse failed ({exc})")
        return []

    episodes: list[dict[str, str]] = []

    rss_items = root.findall("./channel/item") or root.findall(".//item")
    if rss_items:
        for item in rss_items[:limit]:
            title = (item.findtext("title") or "Untitled Episode").strip()
            link = (item.findtext("link") or "").strip()
            if not link:
                enclosure = item.find("enclosure")
                if enclosure is not None:
                    enc_url = (enclosure.get("url") or "").strip()
                    if enc_url.endswith(".mp3"):
                        link = enc_url[:-4]
                    elif enc_url:
                        link = enc_url

            description = (
                item.findtext("description")
                or item.findtext("{http://purl.org/rss/1.0/modules/content/}encoded")
                or ""
            )
            clean_description = _truncate(_strip_html_tags(description), 220)

            if not link:
                continue

            episodes.append(
                {
                    "title": title,
                    "link": link,
                    "description": clean_description,
                }
            )
    else:
        atom_entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")
        for entry in atom_entries[:limit]:
            title = (entry.findtext("{http://www.w3.org/2005/Atom}title") or "Untitled Episode").strip()

            link = ""
            for link_el in entry.findall("{http://www.w3.org/2005/Atom}link"):
                rel = (link_el.get("rel") or "alternate").strip().lower()
                href = (link_el.get("href") or "").strip()
                if rel == "alternate" and href:
                    link = href
                    break
                if not link and href:
                    link = href

            description = (
                entry.findtext("{http://www.w3.org/2005/Atom}summary")
                or entry.findtext("{http://www.w3.org/2005/Atom}content")
                or ""
            )
            clean_description = _truncate(_strip_html_tags(description), 220)

            if not link:
                continue

            episodes.append(
                {
                    "title": title,
                    "link": link,
                    "description": clean_description,
                }
            )

    if episodes:
        print(f"Podcast sync: loaded {len(episodes)} episode(s) from RSS")
    else:
        print("Podcast sync skipped: no episodes found in RSS")
    return episodes


def render_episode_cards(episodes: list[dict[str, str]]) -> str:
    cards: list[str] = []
    for index, episode in enumerate(episodes):
        label = "Latest Episode" if index == 0 else "Recent"
        cards.append(
            "\n".join(
                [
                    f'<a class="episode-card" href="{html.escape(episode["link"], quote=True)}" target="_blank" rel="noopener">',
                    f'    <div class="episode-number">{label}</div>',
                    f'    <h4>{html.escape(episode["title"])}</h4>',
                    f'    <p>{html.escape(episode["description"])}</p>',
                    "</a>",
                ]
            )
        )
    return "\n".join(cards)


def inject_podcast_episodes_into_index() -> str | None:
    if not ROOT_INDEX_PATH.exists():
        return None

    index_html = ROOT_INDEX_PATH.read_text(encoding="utf-8")
    episodes = fetch_latest_podcast_episodes(limit=3)
    if not episodes:
        return index_html

    start_index = index_html.find(PODCAST_EPISODES_START)
    end_index = index_html.find(PODCAST_EPISODES_END)
    if start_index == -1 or end_index == -1 or end_index <= start_index:
        print("Podcast sync skipped: marker comments not found in index.html")
        return index_html

    start_content_index = start_index + len(PODCAST_EPISODES_START)
    replacement_html = "\n" + render_episode_cards(episodes) + "\n                    "
    return index_html[:start_content_index] + replacement_html + index_html[end_index:]


def fetch_latest_youtube_videos(limit: int = 3) -> list[dict[str, str]]:
    channel_id = resolve_youtube_channel_id()
    if not channel_id:
        print("YouTube sync skipped: unable to resolve channel ID")
        return []

    feed_url = f"{YOUTUBE_FEED_BASE}?channel_id={urllib.parse.quote(channel_id)}"
    try:
        feed_bytes = _download_bytes(feed_url, timeout=12)
        root = ET.fromstring(feed_bytes)
    except Exception as exc:
        print(f"YouTube sync skipped: unable to fetch/parse channel feed ({exc})")
        return []

    videos: list[dict[str, str]] = []
    atom_ns = "{http://www.w3.org/2005/Atom}"
    media_ns = "{http://search.yahoo.com/mrss/}"
    yt_ns = "{http://www.youtube.com/xml/schemas/2015}"

    entries = root.findall(f"{atom_ns}entry")
    for entry in entries[:limit]:
        video_id = (entry.findtext(f"{yt_ns}videoId") or "").strip()
        title = (entry.findtext(f"{atom_ns}title") or "Untitled Video").strip()
        description = (
            entry.findtext(f"{media_ns}group/{media_ns}description")
            or entry.findtext(f"{atom_ns}summary")
            or ""
        )
        description = _truncate(_strip_html_tags(description), 220)
        if not video_id:
            continue
        videos.append({"title": title, "video_id": video_id, "description": description})

    if videos:
        print(f"YouTube sync: loaded {len(videos)} video(s)")
    else:
        print("YouTube sync skipped: no videos found")
    return videos


def _parse_channel_id_from_youtube_html(page_html: str) -> str:
    patterns = [
        r'"channelId"\s*:\s*"(UC[\w-]{20,})"',
        r'channel_id=(UC[\w-]{20,})',
        r'"externalId"\s*:\s*"(UC[\w-]{20,})"',
    ]
    for pattern in patterns:
        match = re.search(pattern, page_html)
        if match:
            return match.group(1)
    return ""


def _resolve_channel_id_via_api(api_key: str) -> str:
    handles = [YOUTUBE_CHANNEL_HANDLE]
    if not YOUTUBE_CHANNEL_HANDLE.startswith("@"):
        handles.append(f"@{YOUTUBE_CHANNEL_HANDLE}")

    for handle in handles:
        try:
            channel_url = (
                f"{YOUTUBE_API_BASE}/channels"
                f"?part=id&forHandle={urllib.parse.quote(handle)}&key={api_key}"
            )
            channel_data = json.loads(_download_bytes(channel_url, timeout=12))
            items = channel_data.get("items") or []
            if items and items[0].get("id"):
                return str(items[0]["id"])
        except Exception:
            continue

    return ""


def resolve_youtube_channel_id() -> str:
    if YOUTUBE_CHANNEL_ID:
        return YOUTUBE_CHANNEL_ID

    api_key = os.getenv("YOUTUBE_API_KEY", "").strip()
    if api_key:
        api_channel_id = _resolve_channel_id_via_api(api_key)
        if api_channel_id:
            return api_channel_id

    try:
        channel_page_url = f"https://www.youtube.com/@{urllib.parse.quote(YOUTUBE_CHANNEL_HANDLE)}"
        channel_page = _download_bytes(channel_page_url, timeout=12).decode("utf-8", errors="ignore")
        scraped_channel_id = _parse_channel_id_from_youtube_html(channel_page)
        if scraped_channel_id:
            return scraped_channel_id
    except Exception:
        pass

    return ""


def render_video_cards(videos: list[dict[str, str]]) -> str:
    cards: list[str] = []
    for video in videos:
        vid = html.escape(video["video_id"], quote=True)
        title_esc = html.escape(video["title"])
        desc_esc = html.escape(video["description"])
        onerror = f"this.onerror=null;this.src='https://i.ytimg.com/vi/{vid}/hqdefault.jpg';"
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


def inject_youtube_videos(index_html: str) -> str:
    videos = fetch_latest_youtube_videos(limit=3)
    if not videos:
        return index_html

    start_index = index_html.find(YOUTUBE_VIDEOS_START)
    end_index = index_html.find(YOUTUBE_VIDEOS_END)
    if start_index == -1 or end_index == -1 or end_index <= start_index:
        print("YouTube sync skipped: marker comments not found in index.html")
        return index_html

    start_content_index = start_index + len(YOUTUBE_VIDEOS_START)
    replacement_html = "\n" + render_video_cards(videos) + "\n        "
    return index_html[:start_content_index] + replacement_html + index_html[end_index:]


def ensure_dist() -> None:
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    BLOG_DIR.mkdir(parents=True, exist_ok=True)


def copy_static_files() -> None:
    for item in SRC_DIR.iterdir():
        if item.is_file():
            shutil.copy2(item, DIST_DIR / item.name)

    if ROOT_INDEX_PATH.exists():
        rendered_index = inject_podcast_episodes_into_index()
        if rendered_index is None:
            rendered_index = ROOT_INDEX_PATH.read_text(encoding="utf-8")
        rendered_index = inject_youtube_videos(rendered_index)
        (DIST_DIR / "index.html").write_text(rendered_index, encoding="utf-8")


def parse_title(md_text: str, fallback: str) -> str:
    for line in md_text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def build_posts() -> list[tuple[str, str]]:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    posts: list[tuple[str, str]] = []

    for post_path in sorted(CONTENT_DIR.glob("*.md"), reverse=True):
        raw = post_path.read_text(encoding="utf-8")
        html_body = markdown.markdown(raw, extensions=["extra"])
        slug = post_path.stem
        title = parse_title(raw, slug)
        post_html = template.replace("{{ title }}", title).replace("{{ content }}", html_body)

        output_path = BLOG_DIR / f"{slug}.html"
        output_path.write_text(post_html, encoding="utf-8")
        posts.append((title, f"/blog/{slug}.html"))

    return posts


def build_blog_index(posts: list[tuple[str, str]]) -> None:
    items = "\n".join([f'<li><a href="{url}">{title}</a></li>' for title, url in posts])
    page = f"""<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"UTF-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
    <title>Blog | Kiwimoto77</title>
    <link rel=\"stylesheet\" href=\"/styles.css\" />
  </head>
  <body>
    <main>
      <p><a href=\"/\">← Home</a></p>
      <h1>Blog</h1>
      <ul>
        {items if items else '<li>No posts yet.</li>'}
      </ul>
    </main>
  </body>
</html>
"""
    (BLOG_DIR / "index.html").write_text(page, encoding="utf-8")


def main() -> None:
    ensure_dist()
    copy_static_files()
    posts = build_posts()
    build_blog_index(posts)
    print(f"Built site to {DIST_DIR}")
    print(f"Posts generated: {len(posts)}")


if __name__ == "__main__":
    main()
