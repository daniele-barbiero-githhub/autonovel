#!/usr/bin/env python3
"""
Draft a single chapter using the writer model.
Usage: python draft_chapter.py 1
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
CHAPTERS_DIR = BASE_DIR / "chapters"

def call_writer(prompt, max_tokens=16000):
    return call_llm(
        prompt,
        role="writer",
        model=WRITER_MODEL,
        max_tokens=max_tokens,
        temperature=0.8,
        system=(
            "You are drafting a Chinese Overwatch: Invasion AU fan novel chapter. "
            "Write in Simplified Chinese. Use third-person limited POV, constrained by "
            "the current focal character's knowledge. Follow the project voice, canon, "
            "truth gates, and chapter outline exactly. Hit every beat as lived scenes, "
            "not summary. Preserve official Overwatch anchors while making AU elements "
            "clearly non-canon branch material. Never reveal truths earlier than canon "
            "allows. Write the FULL chapter -- do not truncate, summarize, or skip ahead."
        ),
        timeout=600,
    )

def load_file(path):
    try:
        return Path(path).read_text()
    except FileNotFoundError:
        return ""

def extract_chapter_outline(outline_text, chapter_num):
    """Extract a specific chapter's outline entry."""
    pattern = (
        rf'###\s+(?:Ch|Chapter)\s+0*{chapter_num}\s*:.*?'
        rf'(?=###\s+(?:Ch|Chapter)\s+0*{chapter_num + 1}\s*:|##\s+Foreshadowing|$)'
    )
    match = re.search(pattern, outline_text, re.DOTALL)
    return match.group(0).strip() if match else "(not found)"

def extract_next_chapter_outline(outline_text, chapter_num):
    """Extract the next chapter's outline (just first few lines for continuity)."""
    next_entry = extract_chapter_outline(outline_text, chapter_num + 1)
    if next_entry == "(not found)":
        return "(final chapter)"
    lines = next_entry.split('\n')[:10]
    return '\n'.join(lines)

def main():
    chapter_num = int(sys.argv[1])
    
    # Load all context
    voice = load_file(BASE_DIR / "voice.md")
    world = load_file(BASE_DIR / "world.md")
    characters = load_file(BASE_DIR / "characters.md")
    outline = load_file(BASE_DIR / "outline.md")
    canon = load_file(BASE_DIR / "canon.md")
    
    # Chapter-specific context
    chapter_outline = extract_chapter_outline(outline, chapter_num)
    next_chapter = extract_next_chapter_outline(outline, chapter_num)
    
    # Previous chapter (if exists)
    prev_path = CHAPTERS_DIR / f"ch_{chapter_num - 1:02d}.md"
    if prev_path.exists():
        prev_text = prev_path.read_text()
        prev_tail = prev_text[-2000:] if len(prev_text) > 2000 else prev_text
    else:
        prev_tail = "(first chapter -- no previous)"
    
    prompt = f"""Write Chapter {chapter_num} of "{STORY_TITLE}".

VOICE DEFINITION (follow this exactly):
{voice}

THIS CHAPTER'S OUTLINE (hit every beat):
{chapter_outline}

NEXT CHAPTER'S OUTLINE (for continuity -- end this chapter so it flows into the next):
{next_chapter}

PREVIOUS CHAPTER'S ENDING (continue from here):
{prev_tail}

WORLD BIBLE (reference for worldbuilding details):
{world}

CHARACTER REGISTRY (reference for speech patterns and behavior):
{characters}

CANON / TRUTH GATES (do not violate these):
{canon}

WRITING INSTRUCTIONS:
1. Write the COMPLETE chapter in Simplified Chinese. Target ~3,000-4,500 Chinese characters unless the outline demands more.
2. Use third-person limited POV. Follow this chapter's focus; default to 林彻 only when the outline does not imply another focal character.
3. Hit ALL beats from the outline in order, but dramatize them as scenes with action, dialogue, tactical pressure, and physical consequence.
4. Plant all foreshadowing elements listed under Plants / restrictions. Keep them subtle unless the canon says this chapter reveals them.
5. Before Chapter 20, do NOT reveal that the protagonists are machines or candidates. Body horror must appear as stress, smoke, low blood sugar, visual noise, dry throat, pulse-checking, or other misread pseudo-physiology.
6. In Chapter 20, reveal the black-rainbow training field and A/C/K/P/S candidate identities, but 林彻 still shows only **[数据缺失]**.
7. Before Chapter 24, do NOT confirm 林彻 as R-732 Shepherd. Before Chapter 48, do NOT name the testimony broadcast solution as the final plan.
8. Official Overwatch heroes are not converted machines. They are the original heroes; the protagonists are AU omnic copies/countermeasure bodies built from combat data.
9. Dialogue follows characters.md and voice.md: 林彻短句压情绪，唐晚医生式分诊，韩序用嘴碎抗压，周砚嘴硬少说，裴临承担落点，沈清禾以结构和出口表达秩序边界。
10. Do not make Ramattra a shallow villain. His question must hurt because the world gives it evidence.
11. Every power use has cost: injury, overheated joints, trust fracture, collateral damage, permission-chain pollution, lost resources, or delayed rescue.
12. Show emotion through actions, tactical choices, body feedback, interrupted speech, and sensory detail. Do not explain what the scene already proves.
13. Start in scene, not exposition. End on the chapter's specific hook or irreversible turn.

PATTERNS TO AVOID (these have been flagged in previous chapters):
14. NO triadic sensory lists. Never "X. Y. Z." or "X and Y and Z" as three
    separate items in a row. Combine two, cut one, or restructure.
15. Avoid formulaic negative narration and repeated "不是X，而是Y" sentence shapes.
16. Avoid "他想起/她意识到" exposition loops. Replace with concrete image, physical response, action, or dialogue.
17. Do not overuse fixed simile connectors. Metaphors must come from Overwatch war tech, omnic bodies, damaged city infrastructure, hard light, ballistics, medical triage, cooling fans, optics, and battlefield comms.
18. NO over-explaining after showing. If a scene demonstrates something,
    do not have the narrator restate it. Trust the scene.
19. NO section breaks (---) as rhythm crutches. Only use for genuine
    time/location jumps. Max 2 per chapter.
20. VARY paragraph length deliberately. Never more than 3 consecutive
    paragraphs of similar length. Include at least one 1-2 sentence
    paragraph and one 6+ sentence paragraph.
21. END the chapter on the hook required by this chapter, not on a generic ominous beat.
22. INCLUDE at least one moment that surprises -- a character saying
    the wrong thing, an emotional beat arriving early or late, a detail
    that doesn't fit the expected pattern. Predictable excellence is
    still predictable.
23. FAVOR scene over summary. At least 70% of the chapter should be
    in-scene (moment by moment, with dialogue and action) rather than
    summary (narrator compressing time).
24. DIALOGUE should sound like speech, not prose. Characters should
    occasionally stumble, interrupt, trail off, or say something
    slightly wrong. Nobody speaks in polished thesis statements during a firefight.

Write the chapter now. Full text, beginning to end.
"""

    print(f"Drafting Chapter {chapter_num}...", file=sys.stderr)
    result = call_writer(prompt)
    
    # Save
    out_path = CHAPTERS_DIR / f"ch_{chapter_num:02d}.md"
    CHAPTERS_DIR.mkdir(exist_ok=True)
    out_path.write_text(result, encoding="utf-8")
    print(f"Saved to {out_path}", file=sys.stderr)
    print(f"Word count: {len(result.split())}", file=sys.stderr)
    print(result)

if __name__ == "__main__":
    main()
