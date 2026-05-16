# GMI Cloud social agent

Proposes one tweet draft per day for the GMI Cloud CMO. Pulls signal from
Hacker News, Reddit (LocalLLaMA, MachineLearning, OpenAI, singularity),
tech RSS (TechCrunch AI, Verge, Ars, VentureBeat, The Information), and
OpenRouter's model catalog. Asks Claude Opus 4.7 to pick one unique,
non-obvious angle and draft it. Tracks history so it doesn't repeat itself.

Does **not** post to X. Writes a markdown draft you review and post manually.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY
```

## Run

```bash
python run.py              # gather + propose, write to drafts/YYYY-MM-DD.md
python run.py --dry        # show signal counts only, no API call
python -m agent.sources    # test signal gathering directly
```

## Layout

```
agent/
  brand.py     ← GMI voice + topics. Edit when positioning shifts.
  sources.py   ← Signal collectors (HN, Reddit, RSS, OpenRouter)
  propose.py   ← Claude call: signal + history → one tweet
  history.py   ← Past drafts, to avoid repetition
run.py         ← Daily entry point
drafts/        ← Output: YYYY-MM-DD.md + history.json
```

## Tuning

- **Voice off?** Edit `agent/brand.py`. That single file controls tone, topics, anti-patterns.
- **Want different sources?** Add a function to `agent/sources.py` that returns
  `[{"source", "title", "url", "summary"}]` and add it to the `collectors` list.
- **Repeating itself?** Bump the history window in `propose.py` (default 30 days).
- **Too generic?** Raise `effort` to `"max"` in `propose.py` or sharpen anti-patterns in `brand.py`.

## Scheduling

Add to crontab for 8am daily:

```
0 8 * * * cd /path/to/socialagent && /usr/bin/python3 run.py >> daily.log 2>&1
```

## Notes on sources

- **X/Twitter trends** is stubbed — the free API tier dropped trends access. Wire up
  paid API in `sources.x_trends()` if needed.
- **OpenRouter** has no public "trending" endpoint; we sort by recency as a proxy.
