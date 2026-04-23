#!/usr/bin/env python3
"""Deterministic chapter-level reveal-gate lint for Black Rainbow."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from hard_rules_common import (
    CHAPTERS_DIR,
    Finding,
    chapter_number,
    chapter_path,
    context_for,
    emit_findings,
    exit_code,
    finding,
    ignored,
    line_number,
    missing_chapter_finding,
)


FORBIDDEN_BEFORE = [
    {
        "id": "black_rainbow_protocol_before_ch20",
        "before": 20,
        "pattern": r"黑虹协议|黑虹计划|Black\s+Rainbow\s+(?:Protocol|Plan|Project)",
        "severity": "error",
        "message": "第20章前不得坐实“黑虹协议/黑虹计划”。",
    },
    {
        "id": "training_field_before_ch20",
        "before": 20,
        "pattern": r"黑虹训练场|训练场\s*(?:UI|界面|系统|破裂|启动|关闭|加载)",
        "severity": "error",
        "message": "第20章前不得坐实黑虹训练场；只能写成城市/战场数据异常。",
    },
    {
        "id": "candidate_identity_before_ch20",
        "before": 20,
        "pattern": (
            r"候选机体|候选体|候选者身份|候选者状态|候选者\s*[:：]?\s*活跃|"
            r"六型候选|主角团.{0,12}机体|你们.{0,12}机体"
        ),
        "severity": "error",
        "message": "第20章前不得明说主角团或林彻是候选机体/候选者。",
    },
    {
        "id": "simulation_ui_before_ch20",
        "before": 20,
        "pattern": r"拟态环境|模拟环境|环境稳定性|检测到外部干预|视觉系统|系统提示框|状态\s*[:：]\s*活跃",
        "severity": "error",
        "message": "第20章前不得暴露拟态环境、系统 UI 或候选者状态；只能保留错觉和城市异常。",
    },
    {
        "id": "true_model_ownership_before_ch20",
        "before": 20,
        "pattern": (
            r"(?:唐晚.{0,20}A-7000|A-7000.{0,20}唐晚|"
            r"韩序.{0,20}C-455|C-455.{0,20}韩序|"
            r"周砚.{0,20}K-2000|K-2000.{0,20}周砚|"
            r"裴临.{0,20}P-900|P-900.{0,20}裴临|"
            r"沈清禾.{0,20}S-900|S-900.{0,20}沈清禾)"
        ),
        "severity": "error",
        "message": "第20章前 A/C/K/P/S 只能被误导为敌方型号或残码，不能归属到队友。",
    },
    {
        "id": "mechanical_body_before_ch20",
        "before": 20,
        "pattern": (
            r"主角团.{0,20}(?:没有呼吸|无呼吸|没有心跳|无心跳|机械身体)|"
            r"林彻.{0,24}(?:没有呼吸|无呼吸|冷却风扇|机械身体|机体)|"
            r"唐晚.{0,24}(?:没有脉搏|无脉搏|没有心跳|无心跳|机械身体)|"
            r"韩序.{0,24}(?:没有冷汗|无冷汗|光学面罩|机械身体)"
        ),
        "severity": "error",
        "message": "第20章前主角团机械身体真相不能明示，只能写成伪生理误读。",
    },
    {
        "id": "salih_controller_before_ch19",
        "before": 19,
        "pattern": r"萨利赫.{0,30}(?:统御体|拟态协议|机械|黑虹.{0,8}筛选)|精英统御体",
        "severity": "error",
        "message": "第19章前不得暴露萨利赫是精英统御体或机械反派。",
    },
    {
        "id": "death_dream_delete_before_ch19",
        "before": 19,
        "pattern": r"删除梦|删除.{0,6}梦境|格式化.{0,8}梦",
        "severity": "error",
        "message": "第19章前不得释放“删除梦”路线。",
    },
    {
        "id": "r732_shepherd_before_ch24",
        "before": 24,
        "pattern": r"R[-\s]?7(?:32)?|Shepherd|牧者|拉玛刹指挥协议|指挥协议衍生",
        "severity": "error",
        "message": "第24章前不得坐实林彻 R-732 Shepherd；第20章也只能显示“数据缺失”。",
    },
    {
        "id": "ramattra_name_before_ch31",
        "before": 31,
        "pattern": r"拉玛刹|Ramattra",
        "severity": "error",
        "message": "第31章前正文不要直接使用拉玛刹姓名；前期只保留归零者阴影。",
    },
    {
        "id": "ramattra_thesis_before_ch39",
        "before": 39,
        "pattern": r"(?:拉玛刹|Ramattra).{0,60}(?:保护智械|制造英雄|三问|黑虹协议|谁保护弱者)",
        "severity": "error",
        "message": "第39章前不得提前释放拉玛刹理念压迫和三问。",
    },
    {
        "id": "official_heroes_unmodified_before_ch21",
        "before": 21,
        "pattern": r"正史英雄.{0,20}(?:没有|未|并未).{0,8}改造|英雄本人.{0,20}(?:没有|未|并未).{0,8}改造",
        "severity": "error",
        "message": "第21章前不得明说正史英雄本人没有被改造。",
    },
    {
        "id": "failed_model_library_before_ch42",
        "before": 42,
        "pattern": r"失败型号库",
        "severity": "error",
        "message": "第42章前不得坐实失败型号库。",
    },
    {
        "id": "testimony_broadcast_before_ch48",
        "before": 48,
        "pattern": r"证词广播|记忆证词广播|痛觉证据广播|不摧毁.{0,12}不接管|第三条路",
        "severity": "error",
        "message": "第48章前不得提前揭晓证词广播或“第三条路”。",
    },
    {
        "id": "isolated_souls_before_ch40",
        "before": 40,
        "pattern": r"孤魂者",
        "severity": "error",
        "message": "第40章前不得固定使用“孤魂者”。",
    },
]


FORBIDDEN_ANYWHERE = [
    {
        "id": "official_heroes_modified",
        "pattern": r"安娜.{0,20}被改造|卡西迪.{0,20}被改造|雾子.{0,20}被改造|法老之鹰.{0,20}被改造|秩序之光.{0,20}被改造|正史英雄.{0,20}被改造",
        "severity": "error",
        "message": "正史英雄本人不能被写成被改造的机器。",
    },
    {
        "id": "clean_happy_ending",
        "pattern": r"守望先锋正式收编|加入守望先锋|被守望先锋接纳|全网和平|全面和平|拉玛刹.{0,12}(?:悔悟|认错|痛哭)",
        "severity": "error",
        "message": "结局不能写成守望先锋收编、全网和平或拉玛刹轻易悔悟。",
    },
]


REQUIRED_IN_CHAPTER = [
    {
        "id": "ch20_data_missing",
        "chapter": 20,
        "pattern": r"数据缺失",
        "severity": "error",
        "message": "第20章必须让林彻屏幕只显示“数据缺失”。",
    },
    {
        "id": "ch21_official_heroes_unmodified",
        "chapter": 21,
        "pattern": r"正史英雄.{0,20}(?:没有|未|并未).{0,8}改造|英雄本人.{0,20}(?:没有|未|并未).{0,8}改造",
        "severity": "warning",
        "message": "第21章应明确正史英雄本人没有被改造。",
    },
    {
        "id": "ch24_r732_reveal",
        "chapter": 24,
        "pattern": r"R[-\s]?732|Shepherd",
        "severity": "error",
        "message": "第24章必须坐实林彻 R-732 Shepherd。",
    },
    {
        "id": "ch48_testimony_broadcast",
        "chapter": 48,
        "pattern": r"证词广播|记忆证词广播",
        "severity": "error",
        "message": "第48章必须释放证词广播终局方案。",
    },
]


def _scan_pattern_rule(path: Path, text: str, ch: int, rule: dict) -> list[Finding]:
    if ignored(text, rule["id"]):
        return []
    results = []
    for match in re.finditer(rule["pattern"], text, re.DOTALL):
        results.append(
            finding(
                severity=rule["severity"],
                rule_id=rule["id"],
                scope=f"chapter:{ch:02d}",
                chapter=ch,
                volume=None,
                file=path,
                line=line_number(text, match.start()),
                message=rule["message"],
                match=match.group(0),
                context=context_for(text, match.start(), match.end()),
            )
        )
    return results


def scan_file(path: Path) -> list[Finding]:
    ch = chapter_number(path)
    if ch is None:
        return []
    if not path.exists():
        return [missing_chapter_finding(ch, scope=f"chapter:{ch:02d}")]

    text = path.read_text(encoding="utf-8")
    findings: list[Finding] = []

    for rule in FORBIDDEN_BEFORE:
        if ch < rule["before"]:
            findings.extend(_scan_pattern_rule(path, text, ch, rule))

    for rule in FORBIDDEN_ANYWHERE:
        findings.extend(_scan_pattern_rule(path, text, ch, rule))

    for rule in REQUIRED_IN_CHAPTER:
        if ch != rule["chapter"] or ignored(text, rule["id"]):
            continue
        if not re.search(rule["pattern"], text, re.DOTALL):
            findings.append(
                finding(
                    severity=rule["severity"],
                    rule_id=rule["id"],
                    scope=f"chapter:{ch:02d}",
                    chapter=ch,
                    volume=None,
                    file=path,
                    line=1,
                    message=rule["message"],
                    context="required pattern missing",
                )
            )

    return findings


def chapter_paths(args: argparse.Namespace) -> list[Path]:
    if args.files:
        return [Path(file) for file in args.files]
    if args.chapter is not None:
        return [chapter_path(args.chapter)]
    return sorted(CHAPTERS_DIR.glob("ch_*.md"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint chapter-level reveal gates and hard rules.")
    parser.add_argument("--chapter", type=int, help="Scan one chapter number.")
    parser.add_argument("--json", action="store_true", help="Emit JSON findings.")
    parser.add_argument("files", nargs="*", help="Optional explicit chapter files.")
    args = parser.parse_args()

    findings: list[Finding] = []
    for path in chapter_paths(args):
        findings.extend(scan_file(path))

    emit_findings(findings, as_json=args.json)
    return exit_code(findings)


if __name__ == "__main__":
    raise SystemExit(main())
