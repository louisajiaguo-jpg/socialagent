"""
Core agent: takes signal + brand + history, asks Claude to pick ONE unique
angle and draft a tweet. Returns the draft plus rationale.
"""

from __future__ import annotations

import json
from datetime import datetime

import anthropic

from .brand import BRAND_CONTEXT
from .history import recent

MODEL = "claude-opus-4-7"


def _format_signal(items: list[dict], max_items: int = 80) -> str:
    """Render the day's signal as a compact, scannable brief."""
    lines = []
    for i, it in enumerate(items[:max_items], 1):
        lines.append(
            f"[{i}] ({it['source']}) {it['title']}\n"
            f"    {it.get('summary','')[:200]}\n"
            f"    {it['url']}"
        )
    return "\n".join(lines)


def _format_history(history: list[dict]) -> str:
    if not history:
        return "(no prior drafts)"
    return "\n".join(
        f"- {h['date'][:10]}: {h['tweet']}"
        for h in history[-30:]
    )


SYSTEM_PROMPT = BRAND_CONTEXT + """

Your job today:
1. Read the day's signal brief (tech news, model releases, infra news, Reddit/HN discussion).
2. Identify ONE specific, unique, non-obvious angle — something most CMOs would miss
   but a technical CMO would catch.
3. Avoid topics covered in the last 30 days of drafts (provided).
4. Draft ONE tweet. 280 chars max. No emojis. No hashtags. No threads.
5. Output as JSON with these exact fields:
   - "topic": the specific thing you're commenting on (1 sentence)
   - "why_unique": why this angle is non-obvious (1 sentence)
   - "tweet": the draft text (≤280 chars)
   - "source_urls": list of 1–3 URLs that informed the take

Return ONLY the JSON object, no preamble."""


def propose_tweet(signal: list[dict]) -> dict:
    """Run one proposal pass. Returns dict with topic/tweet/rationale."""
    client = anthropic.Anthropic()
    history = recent(days=30)

    user_msg = (
        f"# Today's signal ({datetime.now():%Y-%m-%d})\n\n"
        f"{_format_signal(signal)}\n\n"
        f"# Tweets we've already posted (do not repeat these angles)\n\n"
        f"{_format_history(history)}\n\n"
        f"Pick one unique angle and draft the tweet."
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        thinking={"type": "adaptive"},
        output_config={
            "effort": "high",
            "format": {
                "type": "json_schema",
                "schema": {
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string"},
                        "why_unique": {"type": "string"},
                        "tweet": {"type": "string"},
                        "source_urls": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["topic", "why_unique", "tweet", "source_urls"],
                    "additionalProperties": False,
                },
            },
        },
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )

    text = next(b.text for b in response.content if b.type == "text")
    draft = json.loads(text)

    # Hard-enforce the 280 char ceiling — model occasionally drifts.
    if len(draft["tweet"]) > 280:
        draft["tweet"] = draft["tweet"][:277] + "..."
        draft["_truncated"] = True

    return draft
