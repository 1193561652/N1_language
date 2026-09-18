#!/usr/bin/env python3
"""Audit static AI/Codex explanations for generic or incomplete content."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


TOOL_DIR = Path(__file__).resolve().parent
DATA_FILE = TOOL_DIR / "data.js"
REPORT_FILE = TOOL_DIR / "explanations" / "quality-audit.json"
PATTERNS = {
    "oldGrammarFallback": "接续形式、逻辑关系或语气与上下文不匹配",
    "genericGrammarRole": "该选项自身所表示的接续关系和语气",
    "genericReading": "与原文相比存在范围扩大、条件遗漏、因果倒置或无依据推断",
    "genericListening": "属于对话中被否定、未采用或偏离核心问题的信息",
    "genericVocabContext": "代入后在语义范围、词性或搭配对象上不符合本句",
    "genericVocabUsage": "该例句在词义、搭配对象或句法位置上至少有一项不自然",
    "genericKanjiReading": "不是该词在此处的规范读音",
}


def main() -> None:
    source = DATA_FILE.read_text(encoding="utf-8")
    data = json.loads(source.split("=", 1)[1].rstrip(";\n"))
    periods = data["years"][:10]
    counts: Counter[tuple[str, str]] = Counter()
    issues: list[dict[str, object]] = []
    for year in periods:
        for category, questions in data["exams"][year].items():
            for question in questions:
                analysis = str(question.get("analysis") or "")
                source_name = str(question.get("analysisSource") or "")
                generated = "AI" in source_name or "Codex" in source_name or "【AI 生成解析】" in analysis
                if not generated:
                    continue
                counts[(year, category)] += 1
                flags = [name for name, pattern in PATTERNS.items() if pattern in analysis]
                if any(str(option).strip() == f"选项 {number}" for number, option in enumerate(question.get("options") or [], 1)):
                    flags.append("placeholderOptionsInQuestion")
                if category == "语法" and int(question.get("groupNumber") or 0) != 6:
                    for marker, expected in (("含义：", 4), ("区别：", 4), ("本句：", 4)):
                        if analysis.count(marker) != expected:
                            flags.append(f"grammarMissing{marker}{analysis.count(marker)}/{expected}")
                if flags:
                    issues.append({
                        "id": question.get("id"), "period": year, "category": category,
                        "group": question.get("groupNumber"), "source": source_name, "flags": flags,
                    })
    report = {
        "periods": periods,
        "qualityStandard": {
            "grammar": "逐项说明含义、区别、在本句能否使用及具体原因；排序题给出完整顺序和组合依据",
            "reading": "引用或准确转述定位句，逐项核对范围、条件、因果、指代与无依据推断",
            "listening": "基于听力原文说明谈话推进、转折、最终决定，并逐项指出被否定或未采用的位置",
            "vocabulary": "逐项给出词义或读音、搭配差异，并说明正确或错误的具体原因",
        },
        "generatedCounts": {f"{year}|{category}": count for (year, category), count in sorted(counts.items())},
        "flaggedCounts": {
            f"{year}|{category}": sum(1 for item in issues if (item["period"], item["category"]) == (year, category))
            for year, category in sorted(counts)
        },
        "flagCounts": dict(sorted(Counter(flag.split("：", 1)[0] for item in issues for flag in item["flags"]).items())),
        "unflaggedGeneratedCount": sum(counts.values()) - len(issues),
        "issueCount": len(issues),
        "issues": issues,
    }
    REPORT_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"generated explanations: {sum(counts.values())}; flagged: {len(issues)}")
    for key, count in sorted(counts.items()):
        flagged = sum(1 for item in issues if (item["period"], item["category"]) == key)
        print(f"{key[0]} {key[1]}: generated={count}, flagged={flagged}")
    print(f"report: {REPORT_FILE}")


if __name__ == "__main__":
    main()
