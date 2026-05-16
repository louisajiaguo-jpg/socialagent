"""
Streamlit UI for the GMI Cloud tweet draft agent.

Run with:
    streamlit run app.py
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from agent import history, sources
from agent.propose import propose_tweet

load_dotenv()

st.set_page_config(
    page_title="GMI Cloud — Daily Tweet Drafter",
    page_icon="🐦",
    layout="wide",
)

# ---------- Sidebar: history ----------
with st.sidebar:
    st.header("Past drafts")
    past = history.load()
    if not past:
        st.caption("No drafts yet. Generate one to start building history.")
    else:
        for entry in reversed(past[-30:]):
            date = entry["date"][:10]
            with st.expander(f"{date} — {entry['topic'][:50]}"):
                st.write(entry["tweet"])

    st.divider()
    st.caption(f"Total drafts: {len(past)}")

# ---------- Main pane ----------
st.title("GMI Cloud — Daily Tweet Drafter")
st.caption("Pulls signal from HN, Reddit, tech RSS, OpenRouter → Claude Opus 4.7 → one unique draft.")

col_gen, col_test = st.columns([3, 1])

with col_gen:
    generate = st.button("✨ Generate today's draft", type="primary", use_container_width=True)

with col_test:
    test_sources = st.button("🔍 Test sources only", use_container_width=True,
                              help="Fetches news without calling Claude — useful to confirm network access.")

# ---------- Source test mode ----------
if test_sources:
    with st.spinner("Fetching from all sources..."):
        t0 = time.time()
        signal = sources.gather_all()
        elapsed = time.time() - t0

    st.success(f"Collected {len(signal)} items in {elapsed:.1f}s")

    by_source: dict[str, int] = {}
    for it in signal:
        by_source[it["source"]] = by_source.get(it["source"], 0) + 1

    if by_source:
        st.subheader("Items per source")
        for src, n in sorted(by_source.items(), key=lambda x: -x[1]):
            st.write(f"- **{src}**: {n}")
    else:
        st.error(
            "No items came back. Either every source is blocked on this network, "
            "or you're rate-limited. Check your internet connection."
        )

    with st.expander(f"Show all {len(signal)} headlines"):
        for it in signal:
            st.markdown(f"- *{it['source']}* — [{it['title']}]({it['url']})")

# ---------- Draft generation ----------
if generate:
    with st.spinner("Gathering signal from HN, Reddit, RSS, OpenRouter..."):
        signal = sources.gather_all()

    if not signal:
        st.error(
            "Couldn't gather any signal — every news source failed. "
            "Check your internet connection, then try the **Test sources only** button."
        )
        st.stop()

    st.info(f"Pulled {len(signal)} items. Asking Claude for a unique angle...")

    with st.spinner("Claude is thinking (this takes ~20-40 seconds)..."):
        try:
            draft = propose_tweet(signal)
        except Exception as e:
            st.error(f"Claude call failed: {e}")
            st.caption("Check that your ANTHROPIC_API_KEY is set in .env and has billing credit.")
            st.stop()

    # Save to history + drafts file
    history.append({
        "date": datetime.now().isoformat(),
        "topic": draft["topic"],
        "tweet": draft["tweet"],
    })

    drafts_dir = Path(__file__).parent / "drafts"
    drafts_dir.mkdir(exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    (drafts_dir / f"{today}.md").write_text(
        f"# {today}\n\n## Topic\n{draft['topic']}\n\n"
        f"## Why\n{draft['why_unique']}\n\n"
        f"## Draft\n```\n{draft['tweet']}\n```\n\n"
        f"## Sources\n" + "\n".join(f"- {u}" for u in draft.get("source_urls", []))
    )

    # Stash in session so it survives reruns from edits
    st.session_state["last_draft"] = draft
    st.session_state["last_signal_count"] = len(signal)

# ---------- Show the draft (if we have one) ----------
if "last_draft" in st.session_state:
    draft = st.session_state["last_draft"]
    st.divider()

    # The tweet itself — big, editable
    st.subheader("Draft tweet")
    edited = st.text_area(
        "Edit before posting:",
        value=draft["tweet"],
        height=120,
        max_chars=280,
        label_visibility="collapsed",
    )

    char_count = len(edited)
    color = "green" if char_count <= 280 else "red"
    st.markdown(
        f"<p style='color:{color}; font-size: 0.9em'>{char_count} / 280 characters</p>",
        unsafe_allow_html=True,
    )

    # Quick actions
    c1, c2, c3 = st.columns(3)
    with c1:
        st.code(edited, language=None)  # easy to copy
    with c2:
        # Open in X compose
        import urllib.parse
        x_url = "https://twitter.com/intent/tweet?text=" + urllib.parse.quote(edited)
        st.link_button("📤 Open in X to post", x_url, use_container_width=True)
    with c3:
        if st.button("🔄 Regenerate", use_container_width=True):
            del st.session_state["last_draft"]
            st.rerun()

    # Rationale
    st.divider()
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("📌 Topic")
        st.write(draft["topic"])
    with col_b:
        st.subheader("💡 Why this angle")
        st.write(draft["why_unique"])

    st.subheader("📰 Sources")
    for url in draft.get("source_urls", []):
        st.markdown(f"- {url}")

    st.caption(f"Drawn from {st.session_state.get('last_signal_count', '?')} signal items.")
