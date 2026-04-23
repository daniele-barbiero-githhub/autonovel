#!/usr/bin/env python3
"""
Build a condensed arc summary for full-novel evaluation.
For each chapter: opening, closing, plus key dialogue.
Gives the reader panel enough to evaluate the ARC without the full manuscript.
"""
import re
from pathlib import Path
from dotenv import load_dotenv
from llm import call_llm, model_for

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

WRITER_MODEL = model_for("writer", "claude-sonnet-4-6")
CHAPTERS_DIR = BASE_DIR / "chapters"

def call_writer(prompt, max_tokens=4000):
    return call_llm(
        prompt,
        role="writer",
        model=WRITER_MODEL,
        max_tokens=max_tokens,
        temperature=0.1,
        system="You summarize novel chapters precisely. State what HAPPENS, what CHANGES, and what QUESTIONS are left open. No evaluation. No praise. Just events and shifts.",
        timeout=120,
    )

def extract_key_passages(text):
    """Get opening, closing, and best dialogue from a chapter."""
    words = text.split()
    if len(words) > 20:
        opening = ' '.join(words[:150])
        closing = ' '.join(words[-150:])
    else:
        opening = text[:450]
        closing = text[-450:]
    
    # Extract dialogue lines
    dialogue = re.findall(r'[“"「](.{20,}?)[”"」]', text)
    # Pick up to 3 longest dialogue lines
    dialogue.sort(key=len, reverse=True)
    top_dialogue = dialogue[:3]
    
    return opening, closing, top_dialogue

def main():
    summaries = []
    chapter_files = sorted(CHAPTERS_DIR.glob("ch_*.md"))
    if not chapter_files:
        print("No chapter files found.")
        return
    
    for path in chapter_files:
        match = re.search(r"ch_(\d+)\.md$", path.name)
        if not match:
            continue
        ch = int(match.group(1))
        text = path.read_text(encoding="utf-8")
        wc = len(text.split())
        opening, closing, dialogue = extract_key_passages(text)
        
        # Get a 100-word summary from the model
        summary = call_writer(
            f"Summarize this chapter in exactly 3 sentences. What happens, what changes, what question is left open.\n\nCHAPTER {ch}:\n{text}",
            max_tokens=200
        )
        
        entry = f"""### Chapter {ch} ({wc} words)
**Summary:** {summary}

**Opening:** {opening}...

**Closing:** ...{closing}

**Key dialogue:**
"""
        for d in dialogue:
            entry += f'> "{d}"\n\n'
        
        summaries.append(entry)
        print(f"Ch {ch}: summarized ({wc}w)")
    
    # Calculate total word count
    total_wc = sum(len(path.read_text(encoding="utf-8").split()) for path in chapter_files)
    
    # Assemble
    full = f"""# 守望先锋：黑虹孤魂
## Full-Arc Summary for Reader Panel

This document contains chapter summaries, opening/closing passages,
and key dialogue for {len(chapter_files)} drafted chapters. Total tokenized word count: {total_wc:,}.

PREMISE: In an Overwatch: Invasion AU, Null Sector starts the Black
Rainbow Protocol to manufacture omnic officer-candidates from the
combat data of human heroes. The candidates are given false human lives
inside a stitched training city built from Rio, Toronto, Gothenburg, and
King's Row mission data. They are meant to wake, delete the human dream,
and become weapons for Ramattra. Instead, the dream teaches them to refuse.

---

"""
    full += '\n---\n\n'.join(summaries)
    
    out_path = BASE_DIR / "arc_summary.md"
    out_path.write_text(full, encoding="utf-8")
    print(f"\nSaved to {out_path} ({len(full.split())} words)")

if __name__ == "__main__":
    main()
