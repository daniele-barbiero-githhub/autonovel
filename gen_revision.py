#!/usr/bin/env python3
"""
Revision chapter generator. Rewrites a chapter from a specific revision brief.
Usage: python gen_revision.py <chapter_num> <brief_file>
"""
import os
import re
import sys
from pathlib import Path
from dotenv import load_dotenv
from llm import call_llm, model_for

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

WRITER_MODEL = model_for("writer", "claude-sonnet-4-6")
STORY_TITLE = os.environ.get("AUTONOVEL_STORY_TITLE", "守望先锋：黑虹孤魂")

def call_writer(prompt, max_tokens=16000):
    return call_llm(
        prompt,
        role="writer",
        model=WRITER_MODEL,
        max_tokens=max_tokens,
        temperature=0.8,
        system=(
            "You are rewriting a Chinese Overwatch: Invasion AU fan novel chapter. "
            "Follow the revision brief exactly while preserving the project's voice, "
            "canon, truth gates, world rules, and character speech patterns. Never reveal "
            "truths earlier than the chapter plan allows. Write the FULL chapter. "
            "Do not truncate or summarize."
        ),
        timeout=600,
    )

def extract_chapter_outline(outline_text, chapter_num):
    pattern = (
        rf'###\s+(?:Ch|Chapter)\s+0*{chapter_num}\s*:.*?'
        rf'(?=###\s+(?:Ch|Chapter)\s+0*{chapter_num + 1}\s*:|##\s+Foreshadowing|$)'
    )
    match = re.search(pattern, outline_text, re.DOTALL)
    return match.group(0).strip() if match else "(not found)"

def main():
    ch_num = int(sys.argv[1])
    brief_file = sys.argv[2]
    
    voice = (BASE_DIR / "voice.md").read_text()
    characters = (BASE_DIR / "characters.md").read_text()
    world = (BASE_DIR / "world.md").read_text()
    canon = (BASE_DIR / "canon.md").read_text()
    outline = (BASE_DIR / "outline.md").read_text()
    chapter_outline = extract_chapter_outline(outline, ch_num)
    brief = Path(brief_file).read_text()
    
    # Load adjacent chapters for continuity
    prev_path = BASE_DIR / "chapters" / f"ch_{ch_num - 1:02d}.md"
    next_path = BASE_DIR / "chapters" / f"ch_{ch_num + 1:02d}.md"
    prev_tail = prev_path.read_text()[-2000:] if prev_path.exists() else "(first chapter)"
    next_head = next_path.read_text()[:1500] if next_path.exists() else "(last chapter)"
    
    # Load old version if exists
    old_path = BASE_DIR / "chapters" / f"ch_{ch_num:02d}.md"
    old_text = old_path.read_text() if old_path.exists() else "(no existing draft)"
    
    prompt = f"""Rewrite Chapter {ch_num} of "{STORY_TITLE}".

REVISION BRIEF (follow this exactly):
{brief}

THIS CHAPTER'S OUTLINE:
{chapter_outline}

VOICE DEFINITION:
{voice}

CHARACTER REGISTRY:
{characters}

WORLD BIBLE:
{world}

CANON / TRUTH GATES:
{canon}

PREVIOUS CHAPTER ENDING (maintain continuity):
{prev_tail}

NEXT CHAPTER OPENING (end so this flows into it):
{next_head}

THE EXISTING DRAFT (use as raw material -- keep what works, cut what doesn't):
{old_text}

ANTI-PATTERN RULES:
- NO triadic sensory lists (X. Y. Z.)
- NO "He did not [verb]" more than once
- NO "He thought about [X]" constructions
- NO "the way [X] did [Y]" more than twice
- NO formulaic "不是X，而是Y" narration
- NO over-explaining after showing
- MAX 2 section breaks
- At least one moment that genuinely surprises
- 70%+ in-scene (dialogue and action, not summary)
- Dialogue should sound like speech, not prose
- Do not violate the chapter's truth gate. Chapter 20, Chapter 24, and Chapter 48 have hard reveal boundaries.

Write the FULL revised chapter now."""

    print(f"Rewriting Chapter {ch_num}...", file=sys.stderr)
    result = call_writer(prompt)
    
    out_path = BASE_DIR / "chapters" / f"ch_{ch_num:02d}.md"
    out_path.write_text(result, encoding="utf-8")
    print(f"Saved to {out_path}", file=sys.stderr)
    print(f"Word count: {len(result.split())}", file=sys.stderr)

if __name__ == "__main__":
    main()
