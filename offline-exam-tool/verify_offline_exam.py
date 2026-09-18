#!/usr/bin/env python3
"""Verify the unified offline N1 exam data and write a machine-readable report."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import build_offline_exam as builder
from vocab_explanation_details import CONTEXT, SYNONYM, USAGE
from grammar_explanation_details import ORDERINGS


TOOL_DIR = Path(__file__).resolve().parent
ROOT = TOOL_DIR.parent
REPORT = TOOL_DIR / "offline_exam_verification.json"
EXPECTED_COUNTS = {"文字": 6, "词汇": 19, "语法": 19, "阅读": 22, "听力": 30}
INCREMENTAL_YEARS = ["2023.07", "2023.12", "2024.07", "2024.12", "2025.07", "2025.12"]
EXPLANATION_YEARS = ["2025.12", "2025.07", "2024.12", "2024.07", "2023.12", "2023.07", "2022.12", "2022.07", "2021.12", "2021.07"]
UNDERLINE_OPEN = builder.UNDERLINE_OPEN
UNDERLINE_CLOSE = builder.UNDERLINE_CLOSE


def verify() -> dict[str, Any]:
    data = builder.build()
    errors: list[str] = []
    warnings: list[str] = []
    seen_ids: set[str] = set()
    question_total = 0
    media_total = 0
    ordering_question_total = 0
    long_article_total = 0
    counts: dict[str, dict[str, int]] = {}
    explanation_counts: dict[str, dict[str, int]] = {}

    if data.get("version") != 2:
        errors.append(f"unexpected data version: {data.get('version')!r}")
    if data.get("level") != "N1":
        errors.append(f"unexpected level: {data.get('level')!r}")
    if len(data.get("years", [])) != 31:
        errors.append(f"expected 31 periods, got {len(data.get('years', []))}")

    for year in data.get("years", []):
        exam = data.get("exams", {}).get(year)
        if not isinstance(exam, dict):
            errors.append(f"{year}: exam missing")
            continue
        missing_categories = [name for name in builder.CATEGORIES if name not in exam]
        if missing_categories:
            errors.append(f"{year}: missing categories {missing_categories}")
            continue
        counts[year] = {name: len(exam[name]) for name in builder.CATEGORIES}
        explanation_counts[year] = {"total": 0, "source": 0, "generated": 0}
        ordering_questions = [
            question for question in exam["语法"]
            if int(question.get("groupNumber") or 0) == 6
        ]
        if len(ordering_questions) != 5:
            errors.append(f"{year}/语法/問題6: expected 5 ordering questions, got {len(ordering_questions)}")
        ordering_question_total += len(ordering_questions)
        for question in ordering_questions:
            if len(question.get("options") or []) != 4:
                errors.append(f"{question['id']}: ordering question must have 4 options")
            star_position = int(question.get("starPosition") or 0)
            if not 1 <= star_position <= 4:
                errors.append(f"{question['id']}: ordering star position missing or invalid")
            elif builder.ordering_star_position(question.get("question")) != star_position:
                errors.append(f"{question['id']}: stored star position does not match displayed stem")
            if "--+" in str(question.get("question") or ""):
                errors.append(f"{question['id']}: raw Shaobing ordering placeholders still visible")
            complete_order = ORDERINGS.get(str(question.get("id") or ""))
            if complete_order and int(complete_order[star_position - 1]) != int(question.get("rightAnswer") or 0):
                errors.append(f"{question['id']}: answer key does not match complete order at ★ slot")

        for category in builder.CATEGORIES:
            for question in exam[category]:
                question_total += 1
                question_id = str(question.get("id", ""))
                if not question_id:
                    errors.append(f"{year}/{category}: question without id")
                elif question_id in seen_ids:
                    errors.append(f"duplicate question id: {question_id}")
                seen_ids.add(question_id)

                option_count = len(question.get("options") or []) or int(question.get("optionCount") or 0)
                answer = int(question.get("rightAnswer") or 0)
                answers = [int(digit) for digit in str(answer)] if question.get("qaType") == 4 and answer > 9 else [answer]
                if option_count < 1:
                    errors.append(f"{question_id}: no answer options")
                for selected in answers:
                    if selected < 1 or selected > option_count:
                        errors.append(
                            f"{question_id}: answer {selected} outside 1..{option_count}"
                        )

                source = str(question.get("source") or "")
                if not source:
                    warnings.append(f"{question_id}: source label missing")

                if year in EXPLANATION_YEARS:
                    explanation_counts[year]["total"] += 1
                    analysis = str(question.get("analysis") or "").strip()
                    analysis_source = str(question.get("analysisSource") or "").strip()
                    if len(analysis) < 35:
                        errors.append(f"{question_id}: explanation missing or too short")
                    if not analysis_source:
                        errors.append(f"{question_id}: explanation source missing")
                    elif "AI 生成" in analysis_source:
                        explanation_counts[year]["generated"] += 1
                        if not analysis.startswith("【AI 生成解析】"):
                            errors.append(f"{question_id}: generated explanation label missing")
                        is_ordering = category == "语法" and int(question.get("groupNumber") or 0) == 6
                        if not is_ordering:
                            for option_index in range(1, len(question.get("options") or []) + 1):
                                if f"选项 {option_index}" not in analysis:
                                    errors.append(f"{question_id}: option {option_index} explanation missing")
                                if f"\n选项 {option_index}" not in analysis:
                                    errors.append(f"{question_id}: option {option_index} explanation is not on its own line")
                        if category == "文字":
                            if not any(marker in analysis for marker in ("实际读音", "实际存在", "不存在", "不作为")):
                                errors.append(f"{question_id}: reading distractors do not identify real/nonexistent forms")
                            if "【AI 点评】" not in analysis:
                                errors.append(f"{question_id}: reading summary label missing")
                        group_number = int(question.get("groupNumber") or 0)
                        if category == "词汇" and group_number in (2, 3, 4):
                            detail_map = {2: CONTEXT, 3: SYNONYM, 4: USAGE}[group_number]
                            if question_id not in detail_map:
                                errors.append(f"{question_id}: detailed vocabulary explanation missing")
                            if "【AI 点评】" not in analysis:
                                errors.append(f"{question_id}: vocabulary comparison label missing")
                            if group_number == 3 and "题干词义：" not in analysis:
                                errors.append(f"{question_id}: source synonym meaning missing")
                            if group_number == 4 and "目标词义：" not in analysis:
                                errors.append(f"{question_id}: target usage meaning missing")
                        if category == "语法":
                            if group_number == 6:
                                if question_id not in ORDERINGS:
                                    errors.append(f"{question_id}: complete grammar ordering missing")
                                if "正确排序：" not in analysis or "排序内容：" not in analysis:
                                    errors.append(f"{question_id}: complete grammar ordering not rendered")
                                if "\n选项 " in analysis:
                                    errors.append(f"{question_id}: ordering analysis should not repeat per-option notes")
                            elif "错误点：" not in analysis:
                                errors.append(f"{question_id}: grammar alternatives lack concrete error analysis")
                        if "点评" in analysis and "【AI 点评】" not in analysis:
                            errors.append(f"{question_id}: AI comment label missing")
                    else:
                        explanation_counts[year]["source"] += 1

                marked_fields = [
                    question.get("groupTitle"), question.get("title"), question.get("question"),
                    question.get("subQuestion"), question.get("passage"), question.get("analysis"),
                    *(question.get("options") or []),
                ]
                for field in marked_fields:
                    value = str(field or "")
                    if value.count(UNDERLINE_OPEN) != value.count(UNDERLINE_CLOSE):
                        errors.append(f"{question_id}: unbalanced underline markers")

                # Long-form reading passages and the grammar cloze article
                # must retain at least one visible line boundary. This catches
                # regressions where HTML tags or API whitespace are stripped
                # and an entire article is rendered as a single paragraph.
                if category == "阅读" or (category == "语法" and int(question.get("groupNumber") or 0) == 7):
                    article = str(question.get("passage") or question.get("question") or "")
                    if len(article) >= 250:
                        long_article_total += 1
                        if "\n" not in article:
                            errors.append(f"{question_id}: long article paragraph boundaries missing")

                media = list(question.get("images") or [])
                if question.get("audio"):
                    media.append(question["audio"])
                for relative in media:
                    media_total += 1
                    path = ROOT / Path(str(relative).replace("/", "\\"))
                    if not path.is_file():
                        errors.append(f"{question_id}: media missing: {relative}")

    for year in INCREMENTAL_YEARS:
        actual = counts.get(year)
        if actual != EXPECTED_COUNTS:
            errors.append(f"{year}: expected {EXPECTED_COUNTS}, got {actual}")

        # 問題1 asks for a reading and 問題3 asks for the closest meaning; every
        # stem in these groups must retain the source underline target.
        exam = data["exams"].get(year, {})
        for category, group_number in (("文字", 1), ("词汇", 3)):
            target_questions = [
                question for question in exam.get(category, [])
                if int(question.get("groupNumber") or 0) == group_number
            ]
            if len(target_questions) != 6:
                errors.append(f"{year}/{category}/問題{group_number}: expected 6 questions, got {len(target_questions)}")
            for question in target_questions:
                stem = "\n".join(str(question.get(key) or "") for key in ("title", "question", "subQuestion"))
                if UNDERLINE_OPEN not in stem or UNDERLINE_CLOSE not in stem:
                    errors.append(f"{question['id']}: emphasized target missing from stem")

    corrected_ordering = next(
        (question for question in data["exams"]["2024.07"]["语法"]
         if question.get("id") == "jlpt4you-2024.07-grammar-6-1"),
        None,
    )
    if not corrected_ordering:
        errors.append("jlpt4you-2024.07-grammar-6-1: question missing")
    elif corrected_ordering.get("rightAnswer") != 2 or corrected_ordering.get("starPosition") != 2:
        errors.append("jlpt4you-2024.07-grammar-6-1: expected answer 2 at star position 2")

    # Markdown language/reading questions should expose the real four choices,
    # not the generic fallback used where a listening paper has no printed text.
    for year in builder.MARKDOWN_EXAMS:
        for category in builder.CATEGORIES[:-1]:
            for question in data["exams"][year][category]:
                if any(str(option).startswith("选项 ") for option in question["options"]):
                    errors.append(f"{question['id']}: placeholder option in language paper")

    report = {
        "status": "pass" if not errors else "fail",
        "version": data.get("version"),
        "level": data.get("level"),
        "periodCount": len(data.get("years", [])),
        "questionCount": question_total,
        "mediaReferenceCount": media_total,
        "orderingQuestionCount": ordering_question_total,
        "longArticleCount": long_article_total,
        "periods": data.get("years", []),
        "sources": data.get("sources", {}),
        "counts": counts,
        "explanationCounts": {year: explanation_counts[year] for year in EXPLANATION_YEARS},
        "errors": errors,
        "warnings": warnings,
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    result = verify()
    print(
        f"{result['status']}: {result['periodCount']} periods, "
        f"{result['questionCount']} questions, {result['mediaReferenceCount']} media references"
    )
    print(f"report: {REPORT}")
    if result["errors"]:
        for error in result["errors"]:
            print(f"ERROR: {error}")
        raise SystemExit(1)
