#!/usr/bin/env python3
"""Deterministic whole-book hard-rule lint for Black Rainbow."""

from __future__ import annotations

import argparse
import re

from hard_rules_common import (
    Finding,
    chapter_path,
    emit_findings,
    exit_code,
    finding,
    missing_chapter_finding,
)


BOOK_REQUIRED = [
    {
        "id": "book_ch20_data_missing",
        "after": 20,
        "pattern": r"数据缺失",
        "severity": "error",
        "message": "全书必须在第20章释放林彻“数据缺失”。",
    },
    {
        "id": "book_r732_reveal",
        "after": 24,
        "pattern": r"R[-\s]?732|Shepherd",
        "severity": "error",
        "message": "全书必须坐实林彻 R-732 Shepherd。",
    },
    {
        "id": "book_failed_model_library",
        "after": 42,
        "pattern": r"失败型号库",
        "severity": "error",
        "message": "全书必须释放失败型号库。",
    },
    {
        "id": "book_testimony_broadcast",
        "after": 48,
        "pattern": r"证词广播|记忆证词广播",
        "severity": "error",
        "message": "全书必须释放证词广播终局方案。",
    },
    {
        "id": "book_isolated_souls",
        "after": 50,
        "pattern": r"孤魂者|孤魂",
        "severity": "error",
        "message": "全书必须回收孤魂结局语义。",
    },
]


BOOK_FORBIDDEN = [
    {
        "id": "book_no_clean_happy_ending",
        "pattern": r"守望先锋正式收编|加入守望先锋|被守望先锋接纳|全网和平|全面和平|拉玛刹.{0,12}(?:悔悟|认错|痛哭)",
        "severity": "error",
        "message": "全书结局不能写成守望先锋收编、全网和平或拉玛刹轻易悔悟。",
    },
    {
        "id": "book_official_heroes_not_modified",
        "pattern": r"安娜.{0,20}被改造|卡西迪.{0,20}被改造|雾子.{0,20}被改造|法老之鹰.{0,20}被改造|秩序之光.{0,20}被改造|正史英雄.{0,20}被改造",
        "severity": "error",
        "message": "全书不得把正史英雄本人写成被改造的机器。",
    },
]


def _chapter_texts(through_chapter: int | None = None) -> list[tuple[int, str]]:
    texts = []
    upper = through_chapter or 50
    for path in sorted(chapter_path(ch) for ch in range(1, upper + 1)):
        if not path.exists():
            continue
        match = re.search(r"ch_(\d+)\.md$", path.name)
        chapter = int(match.group(1)) if match else 0
        texts.append((chapter, path.read_text(encoding="utf-8")))
    return texts


def _scan_book_required(
    *,
    require_complete: bool,
    through_chapter: int | None,
) -> list[Finding]:
    combined = "\n\n".join(text for _, text in _chapter_texts(through_chapter))
    findings: list[Finding] = []
    for rule in BOOK_REQUIRED:
        rule_is_due = through_chapter is not None and through_chapter >= rule["after"]
        if not (require_complete or rule_is_due):
            continue
        if not re.search(rule["pattern"], combined, re.DOTALL):
            findings.append(
                finding(
                    severity=rule["severity"],
                    rule_id=rule["id"],
                    scope="book",
                    chapter=None,
                    volume=None,
                    file="book",
                    line=1,
                    message=rule["message"],
                    context="required book pattern missing",
                )
            )
    return findings


def _scan_book_forbidden(through_chapter: int | None = None) -> list[Finding]:
    findings: list[Finding] = []
    for chapter, text in _chapter_texts(through_chapter):
        path = chapter_path(chapter)
        for rule in BOOK_FORBIDDEN:
            for match in re.finditer(rule["pattern"], text, re.DOTALL):
                findings.append(
                    finding(
                        severity=rule["severity"],
                        rule_id=rule["id"],
                        scope="book",
                        chapter=chapter,
                        volume=None,
                        file=path,
                        line=text.count("\n", 0, match.start()) + 1,
                        message=rule["message"],
                        match=match.group(0),
                        context=text[max(0, match.start() - 36): match.end() + 36].replace("\n", "\\n"),
                    )
                )
    return findings


def scan_book(
    *,
    require_complete: bool = False,
    through_chapter: int | None = None,
) -> list[Finding]:
    findings: list[Finding] = []

    if require_complete:
        for chapter in range(1, 51):
            if not chapter_path(chapter).exists():
                findings.append(missing_chapter_finding(chapter, scope="book"))

    findings.extend(_scan_book_forbidden(through_chapter))
    findings.extend(
        _scan_book_required(
            require_complete=require_complete,
            through_chapter=through_chapter,
        )
    )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint whole-book hard rules.")
    parser.add_argument("--through-chapter", type=int, help="Scan the current partial book through this chapter.")
    parser.add_argument("--chapter", type=int, help="Alias for --through-chapter.")
    parser.add_argument("--require-complete", action="store_true", help="Treat missing chapters as errors and enforce full-book required rules.")
    parser.add_argument("--json", action="store_true", help="Emit JSON findings.")
    args = parser.parse_args()
    if args.chapter is not None and args.through_chapter is None:
        args.through_chapter = args.chapter

    findings = scan_book(
        require_complete=args.require_complete,
        through_chapter=args.through_chapter,
    )
    emit_findings(findings, as_json=args.json)
    return exit_code(findings)


if __name__ == "__main__":
    raise SystemExit(main())
