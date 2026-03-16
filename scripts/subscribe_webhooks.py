"""Subscribe to WebSub hubs for YouTube and podcast RSS.

Called automatically at the end of each Netlify build to keep subscriptions
fresh (leases typically expire after 5 days).

Required env vars:
  WEBHOOK_URL         — public URL of the Netlify function,
                        e.g. https://kiwimoto72.com/.netlify/functions/webhook
  NETLIFY_BUILD_HOOK  — set in Netlify env (used by the function, not here)

Optional env vars (same as build.py):
  YOUTUBE_API_KEY     — needed to look up the YouTube channel ID
  PODCAST_RSS_URL     — explicit RSS URL (otherwise auto-discovered)
  PODCAST_SITE_URL    — Buzzsprout site URL used for RSS discovery
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request

WEBSUB_HUB = "https://pubsubhubbub.appspot.com/subscribe"
YOUTUBE_CHANNEL_HANDLE = "kiwimoto72"
YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"
YOUTUBE_FEED_BASE = "https://www.youtube.com/xml/feeds/videos.xml"

# Re-use helpers from build.py (same directory)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _subscribe(hub: str, topic: str, callback: str, lease_seconds: int = 432000) -> bool:
    data = urllib.parse.urlencode(
        {
            "hub.callback": callback,
            "hub.mode": "subscribe",
            "hub.topic": topic,
            "hub.lease_seconds": str(lease_seconds),
        }
    ).encode()
    req = urllib.request.Request(hub, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            status = resp.status
    except Exception as exc:
        print(f"  WebSub subscribe failed: {exc}")
        return False

    if status in (202, 204):
        print(f"  Subscribed OK: {topic}")
        return True
    print(f"  Unexpected status {status} for topic: {topic}")
    return False


def _get_youtube_channel_id(api_key: str) -> str | None:
    url = (
        f"{YOUTUBE_API_BASE}/channels"
        f"?part=id&forHandle={YOUTUBE_CHANNEL_HANDLE}&key={api_key}"
    )
    try:
        with urllib.request.urlopen(url, timeout=12) as resp:
            data = json.loads(resp.read())
        return data["items"][0]["id"]
    except Exception as exc:
        print(f"  Could not get YouTube channel ID: {exc}")
        return None


def subscribe_all() -> None:
    callback = os.getenv("WEBHOOK_URL", "").strip()
    if not callback:
        print("WebSub subscriptions skipped: WEBHOOK_URL not set")
        return

    # --- YouTube ---
    api_key = os.getenv("YOUTUBE_API_KEY", "").strip()
    if api_key:
        channel_id = _get_youtube_channel_id(api_key)
        if channel_id:
            topic = f"{YOUTUBE_FEED_BASE}?channel_id={channel_id}"
            print(f"Subscribing to YouTube feed ({YOUTUBE_CHANNEL_HANDLE})…")
            _subscribe(WEBSUB_HUB, topic, callback)
        else:
            print("YouTube WebSub skipped: could not resolve channel ID")
    else:
        print("YouTube WebSub skipped: YOUTUBE_API_KEY not set")

    # --- Podcast RSS ---
    try:
        from build import discover_podcast_rss_url
        feed_url = discover_podcast_rss_url()
    except Exception:
        feed_url = os.getenv("PODCAST_RSS_URL", "").strip()

    if feed_url:
        print(f"Subscribing to podcast RSS feed…")
        _subscribe(WEBSUB_HUB, feed_url, callback)
    else:
        print("Podcast WebSub skipped: no RSS feed URL found")


if __name__ == "__main__":
    subscribe_all()
