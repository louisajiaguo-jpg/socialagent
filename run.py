#!/usr/bin/env python3
"""
Daily run: gather signal → propose one tweet → write to drafts/<date>.md
and append to history.

Usage:
    python run.py            # propose today's tweet
    python run.py --dry      # show signal counts only, no LLM call
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from agent import history, sources
from agent.propose import propose_tweet

DRAFTS_DIR = Path(__file__).parent / "drafts"


def write_draft(draft: dict, signal_count: int) -> Path:
    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    path = DRAFTS_DIR / f"{today}.md"

    body = (
        f"# Tweet draft — {today}\n\n"
        f"## Topic\n{draft['topic']}\n\n"
        f"## Why this angle\n{draft['why_unique']}\n\n"
        f"## Draft ({len(draft['tweet'])} chars)\n"
        f"```\n{draft['tweet']}\n```\n\n"
        f"## Sources\n"
        + "\n".join(f"- {u}" for u in draft.get("source_urls", []))
        + f"\n\n---\n_Drawn from {signal_count} signal items._\n"
    )
    path.write_text(body)
    return path


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry", action="store_true",
                        help="Gather signal only, skip LLM call")
    args = parser.parse_args()

    print("Gathering signal...")
    signal = sources.gather_all()
    print(f"  {len(signal)} items collected")

    if args.dry:
        by_source: dict[str, int] = {}
        for it in signal:
            by_source[it["source"]] = by_source.get(it["source"], 0) + 1
        for src, n in sorted(by_source.items(), key=lambda x: -x[1]):
            print(f"  {src}: {n}")
        return 0

    if not signal:
        print("No signal gathered — aborting.", file=sys.stderr)
        return 1

    print(f"Asking Claude for a draft...")
    draft = propose_tweet(signal)

    path = write_draft(draft, len(signal))
    history.append({
        "date": datetime.now().isoformat(),
        "topic": draft["topic"],
        "tweet": draft["tweet"],
    })

    print(f"\n{'='*60}")
    print(f"DRAFT ({len(draft['tweet'])} chars)")
    print(f"{'='*60}")
    print(draft["tweet"])
    print(f"{'='*60}")
    print(f"Topic: {draft['topic']}")
    print(f"Why:   {draft['why_unique']}")
    print(f"\nWritten to: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
