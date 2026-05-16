"""
Signal collectors. Each function returns a list of dicts:
    {"source": str, "title": str, "url": str, "summary": str}

Failures degrade silently — if Reddit is down, we still get HN + RSS.
"""

from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

import requests

UA = {"User-Agent": "gmi-social-agent/0.1 (CMO daily brief)"}
TIMEOUT = 10


def _safe(fn: Callable[[], list[dict]]) -> list[dict]:
    try:
        return fn()
    except Exception as e:
        print(f"[sources] {fn.__name__} failed: {e}")
        return []


def hacker_news(limit: int = 15) -> list[dict]:
    """Top stories from HN — high-signal for tech/AI/infra."""
    ids = requests.get(
        "https://hacker-news.firebaseio.com/v0/topstories.json",
        timeout=TIMEOUT,
    ).json()[:limit]

    out = []
    for sid in ids:
        item = requests.get(
            f"https://hacker-news.firebaseio.com/v0/item/{sid}.json",
            timeout=TIMEOUT,
        ).json()
        if not item or item.get("type") != "story":
            continue
        out.append({
            "source": "Hacker News",
            "title": item.get("title", ""),
            "url": item.get("url") or f"https://news.ycombinator.com/item?id={sid}",
            "summary": f"{item.get('score', 0)} points, {item.get('descendants', 0)} comments",
        })
    return out


def reddit_ai(limit: int = 15) -> list[dict]:
    """Hot posts from AI-flavored subreddits."""
    subs = ["LocalLLaMA", "singularity", "MachineLearning", "OpenAI"]
    out = []
    for sub in subs:
        r = requests.get(
            f"https://www.reddit.com/r/{sub}/hot.json?limit={limit}",
            headers=UA,
            timeout=TIMEOUT,
        )
        if r.status_code != 200:
            continue
        for child in r.json().get("data", {}).get("children", []):
            d = child["data"]
            if d.get("stickied"):
                continue
            out.append({
                "source": f"r/{sub}",
                "title": d.get("title", ""),
                "url": "https://reddit.com" + d.get("permalink", ""),
                "summary": (d.get("selftext", "") or "")[:280],
            })
    return out


_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(s: str) -> str:
    return _TAG_RE.sub("", s or "").strip()


def _parse_feed(xml_bytes: bytes, source: str, limit: int) -> list[dict]:
    """Minimal RSS 2.0 / Atom parser using stdlib. Handles both formats."""
    root = ET.fromstring(xml_bytes)
    out = []

    # RSS 2.0: <rss><channel><item>...
    for item in root.findall(".//item")[:limit]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        desc = item.findtext("description") or ""
        out.append({
            "source": source,
            "title": title,
            "url": link,
            "summary": _strip_html(desc)[:400],
        })

    # Atom: <feed><entry>...
    atom_ns = "{http://www.w3.org/2005/Atom}"
    for entry in root.findall(f".//{atom_ns}entry")[:limit]:
        title = (entry.findtext(f"{atom_ns}title") or "").strip()
        link_el = entry.find(f"{atom_ns}link")
        link = link_el.get("href") if link_el is not None else ""
        summary = (entry.findtext(f"{atom_ns}summary")
                   or entry.findtext(f"{atom_ns}content") or "")
        out.append({
            "source": source,
            "title": title,
            "url": link,
            "summary": _strip_html(summary)[:400],
        })

    return out


def rss_feeds(limit_per_feed: int = 8) -> list[dict]:
    """Major tech publications. RSS/Atom parsed with stdlib."""
    feeds = {
        "TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/",
        "The Verge": "https://www.theverge.com/rss/index.xml",
        "Ars Technica": "https://feeds.arstechnica.com/arstechnica/index",
        "VentureBeat AI": "https://venturebeat.com/category/ai/feed/",
    }
    out: list[dict] = []
    for name, url in feeds.items():
        try:
            r = requests.get(url, headers=UA, timeout=TIMEOUT)
            r.raise_for_status()
            out.extend(_parse_feed(r.content, name, limit_per_feed))
        except Exception as e:
            print(f"[sources] {name} feed failed: {e}")
    return out


def openrouter_trending(limit: int = 20) -> list[dict]:
    """Trending models on OpenRouter — proxy for which models people actually use."""
    r = requests.get("https://openrouter.ai/api/v1/models", timeout=TIMEOUT)
    r.raise_for_status()
    models = r.json().get("data", [])
    # OpenRouter doesn't expose a 'trending' endpoint publicly, but we can
    # surface recently-added models which is a strong leading indicator.
    models.sort(key=lambda m: m.get("created", 0), reverse=True)
    out = []
    for m in models[:limit]:
        ctx = m.get("context_length", 0)
        pricing = m.get("pricing", {})
        prompt_price = pricing.get("prompt", "?")
        out.append({
            "source": "OpenRouter",
            "title": f"{m.get('name', m.get('id', ''))} — {ctx//1000}k ctx, ${prompt_price}/tok in",
            "url": f"https://openrouter.ai/{m.get('id', '')}",
            "summary": (m.get("description", "") or "")[:400],
        })
    return out


def x_trends() -> list[dict]:
    """X/Twitter trends — STUB. The free X API tier no longer exposes trends.
    Returns [] unless you wire up paid API access. Left in as a placeholder
    so you remember this signal source exists."""
    return []


def gather_all() -> list[dict]:
    """Run all collectors in parallel. Returns combined list, deduped on URL."""
    collectors = [hacker_news, reddit_ai, rss_feeds, openrouter_trending, x_trends]
    results: list[dict] = []

    with ThreadPoolExecutor(max_workers=len(collectors)) as ex:
        futures = {ex.submit(_safe, c): c.__name__ for c in collectors}
        for f in as_completed(futures):
            results.extend(f.result())

    # Dedupe by URL
    seen = set()
    deduped = []
    for r in results:
        url = r.get("url", "")
        if url and url not in seen:
            seen.add(url)
            deduped.append(r)
    return deduped


if __name__ == "__main__":
    t0 = time.time()
    items = gather_all()
    print(f"Gathered {len(items)} items in {time.time()-t0:.1f}s")
    by_source: dict[str, int] = {}
    for it in items:
        by_source[it["source"]] = by_source.get(it["source"], 0) + 1
    for src, n in sorted(by_source.items(), key=lambda x: -x[1]):
        print(f"  {src}: {n}")
