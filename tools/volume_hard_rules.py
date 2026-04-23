#!/usr/bin/env python3
"""Deterministic volume-level hard-rule lint for Black Rainbow."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from chapter_hard_rules import scan_file
from hard_rules_common import (
    Finding,
    VOLUMES,
    context_for,
    emit_findings,
    exit_code,
    finding,
    line_number,
    missing_chapter_finding,
    volume_by_id,
    volume_for_chapter,
    volume_chapter_paths,
)


VOLUME_FORBIDDEN = [
    {
        "id": "v1_no_core_truth_dump",
        "volume": 1,
        "pattern": r"黑虹计划|黑虹协议|候选者状态|拟态环境|R[-\s]?732|Shepherd|拉玛刹|Ramattra",
        "severity": "error",
        "message": "第一卷/幕只能建立灾变与黑虹视觉压迫，不能释放核心真相。",
    },
    {
        "id": "v2_no_late_game_terms",
        "volume": 2,
        "pattern": r"R[-\s]?732|Shepherd|拉玛刹|Ramattra|证词广播|失败型号库|孤魂者",
        "severity": "error",
        "message": "第二卷/幕不得提前释放 R-732、拉玛刹、证词广播、失败型号库或孤魂者。",
    },
    {
        "id": "v3_no_final_solution",
        "volume": 3,
        "pattern": r"证词广播|记忆证词广播|痛觉证据广播|第三条路|失败型号库|孤魂者",
        "severity": "error",
        "message": "第三卷/幕不得提前释放终局方案、失败型号库或孤魂者。",
    },
    {
        "id": "v4_no_final_solution",
        "volume": 4,
        "pattern": r"证词广播|记忆证词广播|痛觉证据广播|第三条路|失败型号库",
        "severity": "error",
        "message": "第四卷/幕不得提前释放证词广播、第三条路或失败型号库。",
    },
]


VOLUME_REQUIRED = [
    {
        "id": "v1_black_rainbow_incident_planted",
        "volume": 1,
        "pattern": r"黑虹|黑色虹膜|黑虹投影|选择已开始",
        "severity": "error",
        "message": "第一卷/幕必须种下黑虹符号、城市异常或“选择已开始”。",
    },
    {
        "id": "v2_first_wakeup",
        "volume": 2,
        "pattern": r"第一次醒来|黑虹训练场|数据缺失",
        "severity": "error",
        "message": "第二卷/幕结尾必须完成第20章第一次醒来和“数据缺失”释放。",
    },
    {
        "id": "v3_r732_reveal",
        "volume": 3,
        "pattern": r"R[-\s]?732|Shepherd",
        "severity": "error",
        "message": "第三卷/幕必须坐实林彻 R-732 Shepherd。",
    },
    {
        "id": "v4_ramattra_pressure",
        "volume": 4,
        "pattern": r"拉玛刹|Ramattra|三问|谁保护弱者",
        "severity": "error",
        "message": "第四卷/幕必须释放拉玛刹压力和三问前置。",
    },
    {
        "id": "v5_final_solution",
        "volume": 5,
        "pattern": r"失败型号库|证词广播|记忆证词广播|孤魂者",
        "severity": "error",
        "message": "第五卷/幕必须释放失败型号库、证词广播和孤魂结局相关信息。",
    },
]


def _scan_volume_forbidden(volume: dict, paths: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    rules = [rule for rule in VOLUME_FORBIDDEN if rule["volume"] == volume["id"]]
    for path in paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for rule in rules:
            for match in re.finditer(rule["pattern"], text, re.DOTALL):
                ch_match = re.search(r"ch_(\d+)\.md$", path.name)
                chapter = int(ch_match.group(1)) if ch_match else None
                findings.append(
                    finding(
                        severity=rule["severity"],
                        rule_id=rule["id"],
                        scope=f"volume:{volume['id']}",
                        chapter=chapter,
                        volume=volume["id"],
                        file=path,
                        line=line_number(text, match.start()),
                        message=rule["message"],
                        match=match.group(0),
                        context=context_for(text, match.start(), match.end()),
                    )
                )
    return findings


def _scan_volume_required(
    volume: dict,
    paths: list[Path],
    *,
    require_complete: bool,
    through_chapter: int | None,
) -> list[Finding]:
    existing = [path for path in paths if path.exists()]
    volume_is_due = through_chapter is not None and through_chapter >= volume["end"]
    if not (require_complete or volume_is_due) or not existing:
        return []

    combined = "\n\n".join(path.read_text(encoding="utf-8") for path in existing)
    findings: list[Finding] = []
    for rule in VOLUME_REQUIRED:
        if rule["volume"] != volume["id"]:
            continue
        if not re.search(rule["pattern"], combined, re.DOTALL):
            findings.append(
                finding(
                    severity=rule["severity"],
                    rule_id=rule["id"],
                    scope=f"volume:{volume['id']}",
                    volume=volume["id"],
                    file=f"volume:{volume['id']}",
                    line=1,
                    message=rule["message"],
                    context="required volume pattern missing",
                )
            )
    return findings


def volume_paths_through(volume: dict, through_chapter: int | None) -> list[Path]:
    paths = volume_chapter_paths(volume)
    if through_chapter is None:
        return paths
    upper = min(volume["end"], through_chapter)
    if upper < volume["start"]:
        return []
    return paths[: upper - volume["start"] + 1]


def scan_volume(
    volume: dict,
    *,
    require_complete: bool = False,
    through_chapter: int | None = None,
) -> list[Finding]:
    paths = volume_paths_through(volume, through_chapter)
    findings: list[Finding] = []

    if require_complete:
        for chapter in range(volume["start"], volume["end"] + 1):
            path = volume_chapter_paths(volume)[chapter - volume["start"]]
            if not path.exists():
                findings.append(
                    missing_chapter_finding(
                        chapter,
                        scope=f"volume:{volume['id']}",
                        volume=volume["id"],
                    )
                )

    for path in paths:
        if path.exists():
            findings.extend(scan_file(path))

    findings.extend(_scan_volume_forbidden(volume, paths))
    findings.extend(
        _scan_volume_required(
            volume,
            paths,
            require_complete=require_complete,
            through_chapter=through_chapter,
        )
    )
    return findings


def selected_volumes(args: argparse.Namespace) -> list[dict]:
    if args.chapter is not None:
        volume = volume_for_chapter(args.chapter)
        if volume is None:
            raise ValueError(f"No volume contains chapter {args.chapter}")
        return [volume]
    if args.volume is not None:
        return [volume_by_id(args.volume)]
    return VOLUMES


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint volume-level hard rules.")
    parser.add_argument("--volume", type=int, choices=[v["id"] for v in VOLUMES], help="Scan one volume.")
    parser.add_argument("--chapter", type=int, help="Infer volume from the current chapter.")
    parser.add_argument("--through-chapter", type=int, help="Scan only chapters up to this current chapter.")
    parser.add_argument("--require-complete", action="store_true", help="Treat missing volume chapters as errors and enforce volume required rules.")
    parser.add_argument("--json", action="store_true", help="Emit JSON findings.")
    args = parser.parse_args()

    if args.chapter is not None and args.through_chapter is None:
        args.through_chapter = args.chapter

    findings: list[Finding] = []
    for volume in selected_volumes(args):
        findings.extend(
            scan_volume(
                volume,
                require_complete=args.require_complete,
                through_chapter=args.through_chapter,
            )
        )

    emit_findings(findings, as_json=args.json)
    return exit_code(findings)


if __name__ == "__main__":
    raise SystemExit(main())
