"""Shared helpers for deterministic Black Rainbow hard-rule linting."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
CHAPTERS_DIR = BASE_DIR / "chapters"


VOLUMES = [
    {"id": 1, "name": "第一幕：召回令后的都市", "start": 1, "end": 10},
    {"id": 2, "name": "第二幕：英雄智械版计划", "start": 11, "end": 20},
    {"id": 3, "name": "第三幕：醒来的机体，不等于自由", "start": 21, "end": 30},
    {"id": 4, "name": "第四幕：反叛归零者", "start": 31, "end": 40},
    {"id": 5, "name": "第五幕：黑虹核心与孤魂结局", "start": 41, "end": 50},
]


@dataclass
class Finding:
    severity: str
    rule_id: str
    scope: str
    chapter: int | None
    volume: int | None
    file: str
    line: int
    message: str
    match: str
    context: str


def chapter_number(path: Path) -> int | None:
    match = re.search(r"ch_(\d+)\.md$", path.name)
    return int(match.group(1)) if match else None


def chapter_path(chapter: int) -> Path:
    return CHAPTERS_DIR / f"ch_{chapter:02d}.md"


def line_number(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def context_for(text: str, start: int, end: int, radius: int = 36) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    return text[left:right].replace("\n", "\\n")


def ignored(text: str, rule_id: str) -> bool:
    return f"lint-ignore: {rule_id}" in text or f"lint-ignore {rule_id}" in text


def finding(
    *,
    severity: str,
    rule_id: str,
    scope: str,
    message: str,
    file: str | Path,
    line: int = 1,
    chapter: int | None = None,
    volume: int | None = None,
    match: str = "",
    context: str = "",
) -> Finding:
    return Finding(
        severity=severity,
        rule_id=rule_id,
        scope=scope,
        chapter=chapter,
        volume=volume,
        file=str(file),
        line=line,
        message=message,
        match=match,
        context=context,
    )


def volume_for_chapter(chapter: int) -> dict | None:
    for volume in VOLUMES:
        if volume["start"] <= chapter <= volume["end"]:
            return volume
    return None


def volume_by_id(volume_id: int) -> dict:
    for volume in VOLUMES:
        if volume["id"] == volume_id:
            return volume
    raise ValueError(f"Unknown volume id: {volume_id}")


def volume_chapter_paths(volume: dict) -> list[Path]:
    return [chapter_path(ch) for ch in range(volume["start"], volume["end"] + 1)]


def existing_chapter_paths() -> list[Path]:
    return sorted(CHAPTERS_DIR.glob("ch_*.md"))


def emit_findings(findings: list[Finding], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps([asdict(item) for item in findings], ensure_ascii=False, indent=2))
        return

    if not findings:
        print("hard_rules: ok")
        return

    for item in findings:
        location = f"{item.file}:{item.line}" if item.file else item.scope
        print(
            f"{item.severity.upper()} {location} [{item.rule_id}] "
            f"{item.scope}: {item.message}"
        )
        if item.match:
            print(f"  match: {item.match}")
        if item.context:
            print(f"  context: {item.context}")


def exit_code(findings: list[Finding]) -> int:
    return 1 if any(item.severity == "error" for item in findings) else 0


def missing_chapter_finding(chapter: int, *, scope: str, volume: int | None = None) -> Finding:
    return finding(
        severity="error",
        rule_id="missing_chapter",
        scope=scope,
        chapter=chapter,
        volume=volume,
        file=chapter_path(chapter),
        message=f"缺少第 {chapter} 章，无法完成硬规则检测。",
        context="required chapter file missing",
    )


def main_exit(findings: list[Finding], *, as_json: bool) -> int:
    emit_findings(findings, as_json=as_json)
    return exit_code(findings)
