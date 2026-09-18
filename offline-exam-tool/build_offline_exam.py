#!/usr/bin/env python3
"""Build the root N1 offline exam bundle from Shaobing, JLPT4YOU, and Markdown."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any


TOOL_DIR = Path(__file__).resolve().parent
ROOT = TOOL_DIR.parent
SHAOBING_ROOT = ROOT / "Shaobing Japanese"
JLPT4YOU_ROOT = ROOT / "JLPT4YOU"
OUTPUT = TOOL_DIR / "data.js"
INDEX_TEMPLATE = TOOL_DIR / "index.template.html"
INDEX_OUTPUT = ROOT / "index.html"
APP_SOURCE = SHAOBING_ROOT / "offline-exam" / "app.js"
STYLE_SOURCE = SHAOBING_ROOT / "offline-exam" / "styles.css"
EXPLANATIONS_DIR = TOOL_DIR / "explanations"
CATEGORIES = ["文字", "词汇", "语法", "阅读", "听力"]
JLPT4YOU_YEARS = ["2023.07", "2023.12", "2024.07", "2024.12"]
ORDERING_STAR_POSITION_OVERRIDES = {
    # JLPT4YOU flattens this stem as ``___ _★_ ___ ___``. The star belongs
    # to the second slot; keep it explicit so UI scoring never falls back to
    # an ambiguous underscore count.
    "jlpt4you-2024.07-grammar-6-1": 2,
}

ORDERING_STEM_CORRECTIONS = {
    "sbry-n1-2022.12-文法-6-36": (("真夏の戻った", "真夏に戻った"),),
    "sbry-n1-2022.12-文法-6-37": (("旧白本小学校", "旧白木小学校"),),
}
ORDERING_ANSWER_OVERRIDES = {
    # Verified against the complete sentence order and the displayed ★ slot.
    "markdown-2025.12-language-36": 1,
    "markdown-2025.12-language-37": 2,
    "markdown-2025.12-language-38": 1,
    "markdown-2025.07-language-36": 1,
    "markdown-2025.07-language-37": 2,
    "markdown-2025.07-language-40": 1,
    "jlpt4you-2024.12-grammar-6-2": 2,
}
MARKDOWN_EXAMS = {
    "2025.07": {
        "path": ROOT / "output" / "AI易读Markdown归档" / "真题Markdown" / "2025" / "2025年07月N1真题.md",
        "audio": "library2/2025年7月/音频2025年7月JLPT日语N1真题.mp3",
        "answers": [
            2, 2, 4, 1, 4, 3, 1, 3, 2, 3, 1, 2, 4, 3, 4, 4, 2, 3, 1,
            2, 4, 1, 3, 1, 4, 2, 1, 4, 3, 4, 1, 4, 1, 2, 3, 2, 3, 2, 1,
            4, 4, 3, 1, 2, 3, 4, 3, 4, 2, 2, 4, 2, 4, 1, 2, 3, 4, 2, 1,
            4, 4, 1, 1, 3, 3, 3,
        ],
        "listening": [
            [1, 2, 4, 2, 3],
            [4, 3, 3, 1, 1, 4],
            [1, 4, 3, 1, 4],
            [3, 1, 3, 1, 1, 2, 3, 3, 1, 2, 2],
            [2, 3, 2],
        ],
    },
    "2025.12": {
        "path": ROOT / "output" / "AI易读Markdown归档" / "真题Markdown" / "2025" / "2025年12月N1真题.md",
        "audio": "library2/2025年12月/2025年12月N1.mp3",
        "answers": [
            1, 4, 4, 2, 3, 2, 2, 3, 2, 3, 1, 4, 4, 1, 3, 1, 2, 2, 1,
            3, 3, 4, 4, 2, 2, 3, 2, 4, 1, 3, 4, 3, 1, 4, 2, 3, 4, 2, 1,
            1, 4, 1, 2, 3, 3, 1, 2, 4, 3, 1, 3, 1, 3, 4, 3, 1, 4, 3, 2,
            3, 2, 2, 4, 1, 2, 4,
        ],
        "listening": [
            [1, 3, 3, 2, 1],
            [1, 3, 4, 4, 1, 2],
            [1, 4, 1, 4, 3],
            [2, 2, 1, 3, 1, 3, 1, 2, 3, 3, 2],
            [3, 1, 2],
        ],
    },
}
GROUP_RANGES = {
    1: range(1, 7), 2: range(7, 14), 3: range(14, 20), 4: range(20, 26),
    5: range(26, 36), 6: range(36, 41), 7: range(41, 45), 8: range(45, 49),
    9: range(49, 57), 10: range(57, 60), 11: range(60, 62),
    12: range(62, 65), 13: range(65, 67),
}
TAG_RE = re.compile(r"<[^>]+>")
BLOCK_TAG_RE = re.compile(
    r"</?(?:article|blockquote|div|figcaption|figure|h[1-6]|li|ol|p|section|table|tbody|td|tfoot|th|thead|tr|ul)\b[^>]*>",
    re.IGNORECASE,
)
UNDERLINE_OPEN = "⟦u⟧"
UNDERLINE_CLOSE = "⟦/u⟧"
PAGE_RE = re.compile(r"(?m)^## PDF Page\s+\d{3}\s*$")
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
PROBLEM_RE = re.compile(r"(?m)^###\s*問題\s*(\d+)\b.*$")


def plain_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    text = re.sub(r"<rt\b[^>]*>.*?</rt>", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    # Stripping tags directly would turn ``<p>第一段</p><p>第二段</p>`` into
    # one continuous line.  Convert block-level HTML boundaries first so
    # passages captured from either site retain their paragraph structure.
    text = BLOCK_TAG_RE.sub("\n", text)
    # Preserve the exam's semantic underline without allowing arbitrary source
    # HTML into the offline app. The frontend renders only these fixed markers.
    text = re.sub(r"<u\b[^>]*>", UNDERLINE_OPEN, text, flags=re.IGNORECASE)
    text = re.sub(r"</u\s*>", UNDERLINE_CLOSE, text, flags=re.IGNORECASE)
    text = TAG_RE.sub("", text)
    text = html.unescape(text)
    text = re.sub(r"[*]{1,2}", "", text)
    text = re.sub(r"(?m)^\s*[-—ー]\s*\d+\s*[-—ー]\s*$", "", text)
    text = re.sub(r"(?m)^\s*25\s*-.*?(?:言・読|聴).*?$", "", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.replace("\r\n", "\n").strip()


def article_text(value: Any, *, recover_flattened: bool = False) -> str:
    """Normalize long-form exam text without losing paragraph boundaries.

    JLPT4YOU's API flattens HTML paragraph boundaries into a single ASCII
    space. Japanese prose otherwise does not put a space after every sentence,
    so a sentence-ending mark followed by a space is a reliable retained
    paragraph boundary in that source. Explicit source newlines are kept for
    Shaobing and Markdown data and made visually distinct with a blank line.
    """
    text = plain_text(value)
    if not text:
        return ""
    if recover_flattened and "\n" not in text:
        text = re.sub(
            r"(?<=[。！？!?」』）)]) +(?=[（(「『【\u3040-\u30ff\u3400-\u9fffA-Za-z])",
            "\n\n",
            text,
        )
        # Some passages place an unpunctuated article title immediately after
        # the introductory line (for example: 「以下は…文章である。 題名 本文」).
        lines = text.split("\n\n")
        if len(lines) >= 2 and lines[0].startswith("以下") and " " in lines[1]:
            title, remainder = lines[1].split(" ", 1)
            if 2 <= len(title) <= 30 and title[-1] not in "。！？!?」』）)":
                lines[1:2] = [title, remainder]
                text = "\n\n".join(lines)
    # A single source newline denotes a new article line/paragraph. Use a
    # blank line so it remains unambiguous in the browser's pre-wrap layout.
    text = re.sub(r"\n+", "\n\n", text)
    return text.strip()


def format_analysis(value: Any) -> str:
    """Normalize explanation sections while preserving source wording."""
    text = plain_text(value)
    if not text:
        return ""
    # Put common per-option markers on their own lines.
    text = re.sub(r"[ \t]*(?=(?:[（(][1-4][）)]|[①②③④])\s*)", "\n", text)
    text = re.sub(r"[ \t]+(?=[1-4][.．、]\s*\S)", "\n", text)
    # Separate explanatory sections commonly found in the source material.
    text = re.sub(r"[ \t]*(?=(?:译文|翻译|解析|语法|思路)\s*[：:])", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def empty_categories() -> dict[str, list[dict[str, Any]]]:
    return {name: [] for name in CATEGORIES}


def ordering_star_position(text: Any) -> int:
    """Return the one-based ★ slot for every source's ordering notation."""
    value = str(text or "")
    # The first Markdown question can include the worked example before the
    # actual question. Only the final section is the question being answered.
    if "---" in value:
        value = value.rsplit("---", 1)[-1]
    if "★" not in value:
        return 3
    if "--+" in value:
        return max(1, min(4, value[:value.index("★")].count("--") + 1))
    value = value.replace("\\_", "_").replace(UNDERLINE_OPEN, "").replace(UNDERLINE_CLOSE, "")
    line = next((line for line in value.splitlines() if "★" in line), value)
    slots = list(re.finditer(r"(?:[_＿]+)?★(?:[_＿]+)?|[_＿]+", line))
    for index, slot in enumerate(slots):
        if "★" in slot.group(0):
            return max(1, min(4, index + 1))
    return 3


def normalize_ordering_questions(exams: dict[str, dict[str, list[dict[str, Any]]]]) -> None:
    for categories in exams.values():
        for question in categories["语法"]:
            if int(question.get("groupNumber") or 0) != 6:
                continue
            question_id = str(question.get("id") or "")
            stem = str(question.get("question") or "")
            question["starPosition"] = ORDERING_STAR_POSITION_OVERRIDES.get(
                question_id, ordering_star_position(stem)
            )
            if question_id in ORDERING_ANSWER_OVERRIDES:
                question["rightAnswer"] = ORDERING_ANSWER_OVERRIDES[question_id]
            # Shaobing stores blank slots as -- joined by +. Render actual
            # visible answer slots instead of exposing that transport syntax.
            if "--+" in stem:
                stem = stem.replace("--", "＿＿＿＿").replace("+", " ")
            for old, new in ORDERING_STEM_CORRECTIONS.get(question_id, ()):
                stem = stem.replace(old, new)
            question["question"] = stem


def shaobing_category(part_name: str, group_no: Any) -> str:
    if part_name == "文字・語彙":
        return "文字" if int(group_no) == 1 else "词汇"
    return {"文法": "语法", "読解": "阅读", "聴解": "听力"}[part_name]


def build_shaobing() -> tuple[list[str], dict[str, dict[str, list[dict[str, Any]]]]]:
    menu = json.loads((SHAOBING_ROOT / "data" / "menu.json").read_text(encoding="utf-8"))
    level = next(item for item in menu if str(item.get("k", "")).lower() == "n1")
    years = [str(item["k"]) for item in level.get("c", [])]
    exams: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for year in years:
        year_dir = SHAOBING_ROOT / "data" / "n1" / year
        exam = json.loads((year_dir / "exam.json").read_text(encoding="utf-8"))
        manifest = json.loads((year_dir / "assets.json").read_text(encoding="utf-8"))
        categories = empty_categories()
        for part in exam.get("parts", []):
            part_name = str(part.get("partName", ""))
            for group in part.get("bigQuestionBeans", []):
                group_no = group.get("bigQuestionNo")
                category = shaobing_category(part_name, group_no)
                for question in group.get("questions", []):
                    question_id = str(question.get("questionId"))
                    images = [
                        f"Shaobing Japanese/data/n1/{year}/assets/{manifest[url]}"
                        for url in (question.get("imageUrls") or [])
                        if url in manifest
                    ]
                    audio = None
                    if question.get("listening"):
                        import hashlib
                        digest = hashlib.md5(question_id.encode()).hexdigest()
                        url = f"https://sbry-referer.oss-cn-beijing.aliyuncs.com/web/hub/{digest}.mp3"
                        if url in manifest:
                            audio = f"Shaobing Japanese/data/n1/{year}/assets/{manifest[url]}"
                    analysis = question.get("analysis") or {}
                    categories[category].append({
                        "id": f"sbry-{question_id}", "number": question.get("questionNo"),
                        "groupNumber": group_no, "groupTitle": plain_text(group.get("bigTitle")),
                        "title": plain_text(question.get("title")),
                        "question": plain_text(question.get("question")),
                        "subQuestion": plain_text(question.get("subQuestion")),
                        "passage": article_text(question.get("passage")),
                        "options": [plain_text(item) for item in question.get("options") or []],
                        "optionCount": question.get("optionCount") or 4,
                        "rightAnswer": question.get("rightAnswer"), "qaType": question.get("qaType") or 0,
                        "images": images, "audio": audio,
                        "analysis": format_analysis(analysis.get("explain")),
                        "analysisSource": "烧饼日语附带解析" if plain_text(analysis.get("explain")) else "",
                        "source": "烧饼日语",
                    })
        exams[year] = categories
    return years, exams


def build_jlpt4you(year: str) -> dict[str, list[dict[str, Any]]]:
    year_dir = JLPT4YOU_ROOT / "data" / "n1" / year
    exam = json.loads((year_dir / "exam.json").read_text(encoding="utf-8"))
    manifest = json.loads((year_dir / "assets.json").read_text(encoding="utf-8"))
    categories = empty_categories()
    part_names = {"grammar": "语法", "reading": "阅读", "listening": "听力"}
    for section in exam.get("sections", []):
        part = str(section.get("part"))
        mondai = int(section.get("mondai") or 0)
        category = "文字" if part == "vocabulary" and mondai == 1 else "词汇" if part == "vocabulary" else part_names[part]
        for index, question in enumerate(section.get("questions", []), 1):
            question_id = f"jlpt4you-{year}-{part}-{mondai}-{index}"
            media_urls = []
            for key in ("imageURL", "imageUrl", "audioURL"):
                if question.get(key):
                    media_urls.append(str(question[key]))
            images = [
                f"JLPT4YOU/data/n1/{year}/assets/{manifest[url]}"
                for url in media_urls if url in manifest and "audio" not in manifest[url]
            ]
            audio_url = str(question.get("audioURL") or "")
            audio = f"JLPT4YOU/data/n1/{year}/assets/{manifest[audio_url]}" if audio_url in manifest else None
            categories[category].append({
                "id": question_id,
                "number": question.get("number", index), "groupNumber": mondai,
                "groupTitle": plain_text(section.get("description") or section.get("title")),
                "title": "", "question": plain_text(question.get("text")),
                "subQuestion": "", "passage": article_text(question.get("passage"), recover_flattened=True),
                "options": [plain_text(item) for item in question.get("options") or []],
                "optionCount": len(question.get("options") or []) or 4,
                "rightAnswer": int(question["answer"]) + 1, "qaType": 0,
                "starPosition": ORDERING_STAR_POSITION_OVERRIDES.get(question_id),
                "images": images, "audio": audio, "analysis": "", "analysisSource": "", "source": "JLPT4YOU",
            })
    return categories


def marker_for(segment: str, number: int, start: int, allow_bare: bool) -> re.Match[str] | None:
    strong = [
        rf"(?m)^\s*#{{3,4}}\s*{number}\b.*$",
        rf"(?m)^\s*\*\*\s*[\[(]?\s*{number}\s*[\])]?\s*",
        rf"(?m)^\s*\[{number}\]\s*",
    ]
    for pattern in strong:
        compiled = re.compile(pattern)
        match = compiled.search(segment, start)
        if match:
            return match
    if allow_bare:
        return re.compile(rf"(?m)^\s*{number}\s+(?=\S)").search(segment, start)
    return None


def option_parts(block: str) -> tuple[str, list[str]]:
    with_page_markers = PAGE_RE.sub("\n@@PAGE@@\n", COMMENT_RE.sub("", block))
    cleaned = plain_text(with_page_markers)
    # Prefer line-start markers: this excludes quantities such as "約2倍" inside
    # an option.  Problem 1 sometimes puts all four choices on one line, so a
    # permissive inline expression remains as a fallback for that OCR layout.
    marker_res = [
        re.compile(r"(?m)^\s*([1-4])(?:[.．、]|\s)*(?=\S)"),
        re.compile(r"(?<![\dA-Za-z])([1-4])(?:[.．、]|\s)*(?=\S)"),
    ]
    candidates: list[tuple[re.Match[str], ...]] = []
    for marker_re in marker_res:
        matches = list(marker_re.finditer(cleaned))
        candidates = []
        for index in range(len(matches) - 3):
            group = tuple(matches[index:index + 4])
            if [int(item.group(1)) for item in group] == [1, 2, 3, 4]:
                candidates.append(group)
        if candidates:
            break
    if not candidates:
        return cleaned, ["选项 1", "选项 2", "选项 3", "选项 4"]
    chosen = candidates[-1]
    body = cleaned[:chosen[0].start()].strip()
    options = []
    for index, marker in enumerate(chosen):
        end = chosen[index + 1].start() if index < 3 else len(cleaned)
        options.append(cleaned[marker.end():end].strip() or f"选项 {index + 1}")
    if "@@PAGE@@" in options[-1]:
        option_four, trailing = options[-1].split("@@PAGE@@", 1)
        options[-1] = option_four.strip() or "选项 4"
        trailing = trailing.replace("@@PAGE@@", "\n").strip()
        if trailing:
            body = (body + "\n\n参考资料：\n" + trailing).strip()
    body = body.replace("@@PAGE@@", "\n").strip()
    options = [option.replace("@@PAGE@@", "\n").strip() for option in options]
    return body, options


def split_language_questions(text: str) -> list[tuple[int, int, str, list[str]]]:
    problem_matches = list(PROBLEM_RE.finditer(text))
    segments: dict[int, str] = {}
    for index, match in enumerate(problem_matches):
        problem = int(match.group(1))
        if problem not in GROUP_RANGES or problem in segments:
            continue
        end = problem_matches[index + 1].start() if index + 1 < len(problem_matches) else len(text)
        segments[problem] = text[match.end():end]

    result = []
    for problem, numbers in GROUP_RANGES.items():
        segment = segments.get(problem, "")
        allow_bare = problem == 1 and "**1**" not in segment
        markers: list[tuple[int, re.Match[str]]] = []
        cursor = 0
        for number in numbers:
            marker = marker_for(segment, number, cursor, allow_bare)
            if marker is None:
                raise RuntimeError(f"Markdown 問題{problem}: cannot locate question {number}")
            markers.append((number, marker))
            cursor = marker.end()
        for index, (number, marker) in enumerate(markers):
            next_pos = markers[index + 1][1].start() if index + 1 < len(markers) else len(segment)
            start = marker.end()
            prefix = segment[:marker.start()] if index == 0 else ""
            if index > 0:
                between = segment[markers[index - 1][1].start():marker.start()]
                pages = list(PAGE_RE.finditer(between))
                if pages:
                    page_start = markers[index - 1][1].start() + pages[0].start()
                    prefix = segment[page_start:marker.start()]
            pages_to_next = list(PAGE_RE.finditer(segment[start:next_pos]))
            if pages_to_next:
                next_pos = start + pages_to_next[0].start()
            body, options = option_parts(prefix + segment[start:next_pos])
            result.append((problem, number, body, options))
    return result


def split_exam_and_listening(text: str) -> tuple[str, str]:
    marker = re.search(r"(?m)^\s*25\s*-\s*[12]\s*-\s*I\s*-\s*聴\s*-\s*1\s*$", text)
    if not marker:
        raise RuntimeError("cannot locate listening section")
    return text[:marker.start()], text[marker.end():]


def listening_segments(text: str) -> dict[int, str]:
    matches = list(PROBLEM_RE.finditer(text))
    result: dict[int, str] = {}
    for index, match in enumerate(matches):
        number = int(match.group(1))
        if 1 <= number <= 5 and number not in result:
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            result[number] = text[match.end():end]
    return result


def printed_listening_block(segment: str, number: int) -> str:
    headings = list(re.finditer(r"(?m)^#{3,4}\s*(\d+).*?番.*$", segment))
    target_index = next((i for i, match in enumerate(headings) if int(match.group(1)) == number), None)
    if target_index is None:
        return ""
    start = headings[target_index].end()
    end = headings[target_index + 1].start() if target_index + 1 < len(headings) else len(segment)
    return segment[start:end]


def build_markdown_exam(year: str, config: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    raw = config["path"].read_text(encoding="utf-8", errors="replace")
    exam_text, listening_text = split_exam_and_listening(raw)
    language = split_language_questions(exam_text)
    answers = config["answers"]
    if len(language) != 66 or len(answers) != 66:
        raise RuntimeError(f"{year}: language questions={len(language)}, answers={len(answers)}")
    categories = empty_categories()
    for problem, number, body, options in language:
        category = "文字" if problem == 1 else "词汇" if problem <= 4 else "语法" if problem <= 7 else "阅读"
        categories[category].append({
            "id": f"markdown-{year}-language-{number}", "number": number,
            "groupNumber": problem, "groupTitle": f"問題 {problem}", "title": "",
            "question": body or f"問題 {number}", "subQuestion": "", "passage": "",
            "options": options, "optionCount": len(options), "rightAnswer": answers[number - 1],
            "qaType": 0, "images": [], "audio": None, "analysis": "", "analysisSource": "",
            "source": "本地 PDF→Markdown",
        })

    segments = listening_segments(listening_text)
    global_index = 0
    for problem, problem_answers in enumerate(config["listening"], 1):
        for local_index, answer in enumerate(problem_answers, 1):
            global_index += 1
            block = printed_listening_block(segments.get(problem, ""), local_index) if problem in {1, 2} else ""
            body, options = option_parts(block) if block else (
                f"聴解 問題{problem}・第{local_index}問。完整听力音频位于本页第一题。",
                ["选项 1", "选项 2", "选项 3"] if problem == 4 else ["选项 1", "选项 2", "选项 3", "选项 4"],
            )
            categories["听力"].append({
                "id": f"markdown-{year}-listening-{problem}-{local_index}",
                "number": f"{problem}-{local_index}", "groupNumber": problem,
                "groupTitle": f"聴解 問題 {problem}", "title": "",
                "question": body, "subQuestion": "", "passage": "",
                "options": options, "optionCount": len(options), "rightAnswer": answer,
                "qaType": 0, "images": [],
                "audio": config["audio"] if global_index == 1 else None,
                "analysis": "", "analysisSource": "", "source": "本地 PDF→Markdown",
            })
    if global_index != 30:
        raise RuntimeError(f"{year}: listening answer points={global_index}, expected=30")
    return categories


def build() -> dict[str, Any]:
    shaobing_years, exams = build_shaobing()
    for year in JLPT4YOU_YEARS:
        exams[year] = build_jlpt4you(year)
    for year, config in MARKDOWN_EXAMS.items():
        exams[year] = build_markdown_exam(year, config)
    normalize_ordering_questions(exams)
    for overlay_path in sorted(EXPLANATIONS_DIR.glob("*.json")) if EXPLANATIONS_DIR.is_dir() else []:
        overlay = json.loads(overlay_path.read_text(encoding="utf-8"))
        year = str(overlay.get("year") or overlay_path.stem)
        items = overlay.get("items") or {}
        for questions in exams.get(year, {}).values():
            for question in questions:
                explanation = items.get(question["id"])
                if not explanation:
                    continue
                question["analysis"] = format_analysis(explanation.get("text"))
                question["analysisSource"] = plain_text(explanation.get("source"))
    years = sorted(set(shaobing_years + JLPT4YOU_YEARS + list(MARKDOWN_EXAMS)), reverse=True)
    return {
        "version": 2, "level": "N1", "years": years, "categories": CATEGORIES,
        "exams": exams,
        "sources": {
            "烧饼日语": shaobing_years,
            "JLPT4YOU": JLPT4YOU_YEARS,
            "本地 PDF→Markdown": list(MARKDOWN_EXAMS),
        },
    }


if __name__ == "__main__":
    payload = json.dumps(build(), ensure_ascii=False, separators=(",", ":"))
    OUTPUT.write_text(f"window.EXAM_DATA={payload};\n", encoding="utf-8")
    template = INDEX_TEMPLATE.read_text(encoding="utf-8")
    direct_html = (
        template.replace("__STYLE__", STYLE_SOURCE.read_text(encoding="utf-8"))
        .replace("__DATA__", payload.replace("</", "<\\/"))
        .replace("__APP__", APP_SOURCE.read_text(encoding="utf-8"))
    )
    INDEX_OUTPUT.write_text(direct_html, encoding="utf-8")
    print(f"saved {OUTPUT} ({OUTPUT.stat().st_size:,} bytes)")
    print(f"saved {INDEX_OUTPUT} ({INDEX_OUTPUT.stat().st_size:,} bytes, direct-open mode)")
