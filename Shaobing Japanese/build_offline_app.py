#!/usr/bin/env python3
"""Build the self-contained data bundle used by the offline exam app."""

from __future__ import annotations

import hashlib
import html
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DATA_ROOT = ROOT / "data" / "n1"
OUTPUT = ROOT / "offline-exam" / "data.js"
TAG_RE = re.compile(r"<[^>]+>")


def plain_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = TAG_RE.sub("", text)
    return html.unescape(text).replace("\r\n", "\n").strip()


def category_for(part_name: str, group_no: Any) -> str:
    if part_name == "文字・語彙":
        return "文字" if int(group_no) == 1 else "词汇"
    return {
        "文法": "语法",
        "読解": "阅读",
        "聴解": "听力",
    }[part_name]


def local_asset(year: str, url: str, manifest: dict[str, str]) -> str | None:
    relative = manifest.get(url)
    if not relative:
        return None
    return f"../data/n1/{year}/assets/{relative}"


def build() -> dict[str, Any]:
    menu = json.loads((ROOT / "data" / "menu.json").read_text(encoding="utf-8"))
    level = next(item for item in menu if str(item.get("k", "")).lower() == "n1")
    years = [str(item["k"]) for item in level.get("c", [])]
    exams: dict[str, dict[str, list[dict[str, Any]]]] = {}

    for year in years:
        year_dir = DATA_ROOT / year
        exam = json.loads((year_dir / "exam.json").read_text(encoding="utf-8"))
        manifest = json.loads((year_dir / "assets.json").read_text(encoding="utf-8"))
        categories = {name: [] for name in ["文字", "词汇", "语法", "阅读", "听力"]}

        for part in exam.get("parts", []):
            part_name = str(part.get("partName", ""))
            for group in part.get("bigQuestionBeans", []):
                group_no = group.get("bigQuestionNo")
                category = category_for(part_name, group_no)
                for question in group.get("questions", []):
                    question_id = str(question.get("questionId"))
                    image_paths = []
                    for url in question.get("imageUrls") or []:
                        path = local_asset(year, str(url), manifest)
                        if path:
                            image_paths.append(path)

                    audio_path = None
                    if question.get("listening"):
                        digest = hashlib.md5(question_id.encode()).hexdigest()
                        audio_url = (
                            "https://sbry-referer.oss-cn-beijing.aliyuncs.com/"
                            f"web/hub/{digest}.mp3"
                        )
                        audio_path = local_asset(year, audio_url, manifest)

                    analysis = question.get("analysis") or {}
                    categories[category].append(
                        {
                            "id": question_id,
                            "number": question.get("questionNo"),
                            "groupNumber": group_no,
                            "groupTitle": plain_text(group.get("bigTitle")),
                            "title": plain_text(question.get("title")),
                            "question": plain_text(question.get("question")),
                            "subQuestion": plain_text(question.get("subQuestion")),
                            "passage": plain_text(question.get("passage")),
                            "options": [plain_text(item) for item in question.get("options") or []],
                            "optionCount": question.get("optionCount") or 4,
                            "rightAnswer": question.get("rightAnswer"),
                            "qaType": question.get("qaType") or 0,
                            "images": image_paths,
                            "audio": audio_path,
                            "analysis": plain_text(analysis.get("explain")),
                        }
                    )
        exams[year] = categories

    return {
        "version": 1,
        "level": "N1",
        "years": years,
        "categories": ["文字", "词汇", "语法", "阅读", "听力"],
        "exams": exams,
    }


if __name__ == "__main__":
    payload = json.dumps(build(), ensure_ascii=False, separators=(",", ":"))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(f"window.EXAM_DATA={payload};\n", encoding="utf-8")
    print(f"saved {OUTPUT} ({OUTPUT.stat().st_size:,} bytes)")
