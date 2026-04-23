#!/usr/bin/env python3
"""Import the GeneralProgram2 Black Rainbow outline into autonovel files."""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = Path("/Users/sh/Documents/codeSpace/crewAI/doujin/GeneralProgram2")

SOURCE_FILES = [
    "00_Master_Outline_FINAL.md",
    "01_Five_Act_Chapter_Outline_FINAL.md",
    "02_Truth_Gates_Reveal_Schedule_FINAL.md",
    "03_Character_Relationships_Arcs_FINAL.md",
    "04_Character_Voices_Style_Rules_FINAL.md",
    "05_Ability_System_Faction_Rules_FINAL.md",
    "06_Timeline_Foreshadowing_Ledger_FINAL.md",
    "07_Payoff_Retention_Rules_FINAL.md",
    "08_Chapter_Pacing_Emotional_Map_FINAL.md",
]

ACTS = [
    (1, 10, "第一幕：召回令后的都市"),
    (11, 20, "第二幕：英雄智械版计划"),
    (21, 30, "第三幕：醒来的机体，不等于自由"),
    (31, 40, "第四幕：反叛归零者"),
    (41, 50, "第五幕：黑虹核心与孤魂结局"),
]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write(path: Path, text: str) -> None:
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def split_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def parse_chapter_rows(text: str) -> list[dict[str, str]]:
    rows = []
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = split_table_row(line)
        if len(cells) < 6:
            continue
        if not re.fullmatch(r"\d{3}", cells[0]):
            continue
        rows.append(
            {
                "num": int(cells[0]),
                "source_id": cells[0],
                "title": cells[1],
                "function": cells[2],
                "events": cells[3],
                "state": cells[4],
                "plants": cells[5],
            }
        )
    return rows


def parse_emotion_rows(text: str) -> dict[int, dict[str, str]]:
    rows: dict[int, dict[str, str]] = {}
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = split_table_row(line)
        if len(cells) < 5:
            continue
        match = re.match(r"^(\d{3})\s+(.+)$", cells[0])
        if not match:
            continue
        rows[int(match.group(1))] = {
            "type": cells[1],
            "curve": cells[2],
            "driver": cells[3],
            "hook": cells[4],
        }
    return rows


def parse_timeline_rows(text: str) -> dict[int, dict[str, str]]:
    rows: dict[int, dict[str, str]] = {}
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = split_table_row(line)
        if len(cells) < 3:
            continue
        if not re.fullmatch(r"\d{3}", cells[0]):
            continue
        rows[int(cells[0])] = {
            "event": cells[1],
            "consequence": cells[2],
        }
    return rows


def act_name(chapter_num: int) -> str:
    for start, end, name in ACTS:
        if start <= chapter_num <= end:
            return name
    return "未分幕"


def build_outline(source: Path) -> str:
    chapter_rows = parse_chapter_rows(read(source / "01_Five_Act_Chapter_Outline_FINAL.md"))
    emotion_rows = parse_emotion_rows(read(source / "08_Chapter_Pacing_Emotional_Map_FINAL.md"))
    timeline_rows = parse_timeline_rows(read(source / "06_Timeline_Foreshadowing_Ledger_FINAL.md"))

    if len(chapter_rows) != 50:
        raise RuntimeError(f"Expected 50 chapter rows, found {len(chapter_rows)}")

    parts = [
        "# Outline",
        "",
        "# 《守望先锋：黑虹孤魂》50章章节执行大纲",
        "",
        "> 自动整理自 `story_docs/GeneralProgram2/01_Five_Act_Chapter_Outline_FINAL.md`、"
        "`06_Timeline_Foreshadowing_Ledger_FINAL.md`、"
        "`08_Chapter_Pacing_Emotional_Map_FINAL.md`。",
        "> 本文件使用 `### Ch N:` 标题格式，以便 `draft_chapter.py` 精确抽取单章大纲。",
        "",
        "## Project Contract",
        "",
        "- **Title:** 守望先锋：黑虹孤魂",
        "- **Form:** 50章守望先锋第六赛季“智械入侵”AU同人。",
        "- **Core premise:** 归零者用正史英雄战斗数据制造“英雄智械版”候选机体，"
        "并在黑虹训练场中给他们灌入虚假的人类人生；他们本该删除梦境出厂，"
        "却在梦里学会违抗制造者。",
        "- **Draft language:** 简体中文。",
        "- **Primary rule:** 爽点后必须有代价；正史英雄本人没有被改造；"
        "证词广播不是洗脑和平。",
        "",
        "## Act Structure",
        "",
    ]

    for start, end, name in ACTS:
        parts.append(f"- **{name}:** Ch {start}-{end}")

    parts.extend(["", "## Chapter-by-Chapter Outline", ""])

    current_act = ""
    for row in chapter_rows:
        num = row["num"]
        next_act = act_name(num)
        if next_act != current_act:
            current_act = next_act
            parts.extend(["", f"## {current_act}", ""])

        emotion = emotion_rows.get(num, {})
        timeline = timeline_rows.get(num, {})
        parts.extend(
            [
                f"### Ch {num}: {row['title']}",
                f"- **Source ID:** {row['source_id']}",
                "- **POV:** 第三人称有限视角；按本章情节焦点选择林彻或对应小队成员，"
                "但不能跳出角色当下认知。",
                "- **Location / arena:** 使用本章事件指定空间；若处于 026-040，优先执行"
                "中央升降轴、报废机体粉碎场、硬光穹顶、逻辑桥接舱等“铁盒”压迫。",
                f"- **Chapter function:** {row['function']}",
                f"- **Emotional curve:** {emotion.get('curve', '按本幕节奏推进')}",
                f"- **Emotional driver:** {emotion.get('driver', '见本章事件与状态变化。')}",
                "- **Beats:**",
                f"  1. {row['events']}",
                f"  2. 状态变化必须落地：{row['state']}",
                f"  3. 章尾追读或反转钩子：{emotion.get('hook', row['plants'])}",
                f"- **Plants / restrictions:** {row['plants']}",
                f"- **Timeline continuity:** {timeline.get('event', row['events'])}",
                f"- **Sustained consequence:** {timeline.get('consequence', row['state'])}",
                "- **Writing notes:** 以动作、战术、身体反馈和对话承担情绪；避免解释性总结。"
                "第20章前禁止明示主角团真实机体身份；第48章前禁止提前说出证词广播方案。",
                "- **~Target length:** 3000-4500 汉字，按场面复杂度浮动。",
                "",
            ]
        )

    parts.extend(
        [
            "## Foreshadowing Ledger",
            "",
            read(source / "06_Timeline_Foreshadowing_Ledger_FINAL.md"),
            "",
            "## Payoff And Retention Rules",
            "",
            read(source / "07_Payoff_Retention_Rules_FINAL.md"),
        ]
    )
    return "\n".join(parts)


def main() -> int:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SOURCE
    if not source.exists():
        raise SystemExit(f"Source directory not found: {source}")

    missing = [name for name in SOURCE_FILES if not (source / name).exists()]
    if missing:
        raise SystemExit(f"Missing source files: {', '.join(missing)}")

    docs_dir = BASE_DIR / "story_docs" / "GeneralProgram2"
    docs_dir.mkdir(parents=True, exist_ok=True)
    for name in SOURCE_FILES:
        shutil.copy2(source / name, docs_dir / name)

    master = read(source / "00_Master_Outline_FINAL.md")
    truth = read(source / "02_Truth_Gates_Reveal_Schedule_FINAL.md")
    characters = read(source / "03_Character_Relationships_Arcs_FINAL.md")
    voices = read(source / "04_Character_Voices_Style_Rules_FINAL.md")
    abilities = read(source / "05_Ability_System_Faction_Rules_FINAL.md")
    timeline = read(source / "06_Timeline_Foreshadowing_Ledger_FINAL.md")
    payoff = read(source / "07_Payoff_Retention_Rules_FINAL.md")
    pacing = read(source / "08_Chapter_Pacing_Emotional_Map_FINAL.md")

    write(
        BASE_DIR / "seed.txt",
        "\n".join(
            [
                "# Seed Concept: 守望先锋：黑虹孤魂",
                "",
                "在《守望先锋：归来》第六赛季“智械入侵”的 AU 分支中，归零者为了制造能击溃守望先锋的精英军官，启动“黑虹协议”，用人类英雄的战斗数据制造出一批智械版英雄；他们在模拟都市里被灌入虚假的人类人生，本该成为拉玛刹手中的兵器，却在梦里学会了违抗制造者。",
                "",
                "核心主题：被制造意识的自由意志；虚假记忆是否能孕育真实灵魂；保护与控制的边界。",
                "",
                "终局原则：不摧毁、不接管，只广播失败型号与模拟人格的记忆证词；证词被听见，不等于被理解。",
            ]
        ),
    )

    write(
        BASE_DIR / "world.md",
        "\n\n".join(
            [
                "# World Bible — 《守望先锋：黑虹孤魂》",
                "> 本文件是本项目的世界、阵营、能力、AU边界总参考。原始资料保存在 `story_docs/GeneralProgram2/`。",
                master,
                abilities,
                "## Pacing And Emotional World Rules",
                pacing,
            ]
        ),
    )

    write(
        BASE_DIR / "characters.md",
        "\n\n".join(
            [
                "# Characters — 《守望先锋：黑虹孤魂》",
                "> 本文件合并人物弧光、关系推进与台词声纹。写作时优先按这里区分角色。",
                characters,
                voices,
            ]
        ),
    )

    original_voice = read(BASE_DIR / "voice.md")
    part1 = original_voice.split("## Part 2: Voice Identity", 1)[0].rstrip()
    write(
        BASE_DIR / "voice.md",
        "\n\n".join(
            [
                part1,
                "## Part 2: Voice Identity (generated per novel)",
                "",
                "# 《守望先锋：黑虹孤魂》叙事与声纹",
                "",
                "## Narrative Defaults",
                "",
                "- 正文使用简体中文。",
                "- 以第三人称有限视角推进；视角必须被角色当下认知限制。",
                "- 第20章前，身体恐怖只能伪装成灾后应激、低血糖、烟尘呛咳、视觉噪点等伪生理反应。",
                "- 第20章后，感官错位必须具体：无呼吸、无脉搏、无冷汗、光学报错、冷却风扇、机体过热、核心痛觉。",
                "- 情绪优先通过动作、战术选择、身体反馈和不完整台词呈现，不用旁白直接解释。",
                "- 守望先锋同人锚点要具体可视：召回令、归零者、里约/多伦多/哥德堡/国王大道数据、正史英雄镜像。",
                "- 正史英雄本人不能被写成被改造的机器；主角团是基于英雄数据制造的 AU 候选机体。",
                "",
                voices,
            ]
        ),
    )

    write(BASE_DIR / "outline.md", build_outline(source))

    write(
        BASE_DIR / "canon.md",
        "\n\n".join(
            [
                "# Canon — 《守望先锋：黑虹孤魂》",
                "> 硬事实、真相闸门、时间线、伏笔、回收与禁令。任何章节不得与本文件冲突。",
                truth,
                timeline,
                payoff,
            ]
        ),
    )

    write(
        BASE_DIR / "MYSTERY.md",
        "\n\n".join(
            [
                "# Mystery And Reveal Gates — 《守望先锋：黑虹孤魂》",
                "> 作者视角资料。正文只能按章节闸门释放。",
                truth,
            ]
        ),
    )

    state = {
        "phase": "drafting",
        "current_focus": "ch_01",
        "iteration": 0,
        "foundation_score": 8.0,
        "lore_score": 8.0,
        "chapters_drafted": 0,
        "chapters_total": 50,
        "novel_score": 0.0,
        "revision_cycle": 0,
        "debts": [],
        "project": "守望先锋：黑虹孤魂",
        "source_docs": "story_docs/GeneralProgram2",
    }
    write(BASE_DIR / "state.json", json.dumps(state, ensure_ascii=False, indent=2))

    print("Imported Black Rainbow project files.")
    print("Generated: seed.txt, world.md, characters.md, voice.md, outline.md, canon.md, MYSTERY.md, state.json")
    print("Copied source docs to: story_docs/GeneralProgram2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
