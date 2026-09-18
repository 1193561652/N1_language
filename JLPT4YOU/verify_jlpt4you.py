#!/usr/bin/env python3
"""Verify the completeness and internal consistency of downloaded JLPT4YOU data."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from scrape_jlpt4you import EXAM_IDS, collect_media, iter_questions, year_from_id


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data",
        type=Path,
        default=Path(__file__).resolve().parent / "data" / "n1",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path(__file__).resolve().parent / "verification_report.json",
    )
    args = parser.parse_args()

    expected_years = [year_from_id(exam_id) for exam_id in EXAM_IDS]
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    warnings: list[str] = []

    for year in expected_years:
        year_dir = args.data / year
        required = ["exam.json", "assets.json", "asset_errors.json"]
        missing = [name for name in required if not (year_dir / name).is_file()]
        if missing:
            errors.append(f"{year}: missing {', '.join(missing)}")
            continue

        exam = load_json(year_dir / "exam.json")
        manifest = load_json(year_dir / "assets.json")
        asset_errors = load_json(year_dir / "asset_errors.json")
        sections = exam.get("sections", [])
        questions = list(iter_questions(exam))
        parts = Counter(str(section.get("part", "unknown")) for section in sections)

        for question in questions:
            number = question.get("number", "?")
            options = question.get("options")
            answer = question.get("answer")
            if not isinstance(options, list) or not options:
                errors.append(f"{year} question {number}: missing options")
            elif not isinstance(answer, int) or not 0 <= answer < len(options):
                errors.append(
                    f"{year} question {number}: answer {answer!r} outside 0..{len(options) - 1}"
                )

        expected_media = collect_media(exam)
        accounted_media = set(manifest) | set(asset_errors)
        absent = expected_media - accounted_media
        unexpected = accounted_media - expected_media
        if absent:
            errors.append(f"{year}: {len(absent)} media URL(s) not accounted for")
        if unexpected:
            errors.append(f"{year}: {len(unexpected)} unexpected media URL(s) in manifests")

        for url, relative_path in manifest.items():
            target = year_dir / "assets" / relative_path
            if not target.is_file() or target.stat().st_size == 0:
                errors.append(f"{year}: missing or empty asset for {url}: {relative_path}")

        if len(sections) < 18:
            warnings.append(
                f"{year}: source provides only {len(sections)} sections and {len(questions)} questions"
            )
        if asset_errors:
            warnings.append(f"{year}: {len(asset_errors)} source media URL(s) unavailable")

        rows.append(
            {
                "year": year,
                "sections": len(sections),
                "questions": len(questions),
                "parts": dict(sorted(parts.items())),
                "media_expected": len(expected_media),
                "media_saved": len(manifest),
                "media_unavailable": len(asset_errors),
            }
        )

    existing_years = {path.name for path in args.data.iterdir() if path.is_dir()}
    extra_years = sorted(existing_years - set(expected_years) - {"mock"})
    if extra_years:
        warnings.append(f"extra year directories: {', '.join(extra_years)}")

    totals = {
        "exams": len(rows),
        "sections": sum(row["sections"] for row in rows),
        "questions": sum(row["questions"] for row in rows),
        "media_expected": sum(row["media_expected"] for row in rows),
        "media_saved": sum(row["media_saved"] for row in rows),
        "media_unavailable": sum(row["media_unavailable"] for row in rows),
    }
    report = {
        "status": "failed" if errors else "passed_with_warnings" if warnings else "passed",
        "totals": totals,
        "exams": rows,
        "warnings": warnings,
        "errors": errors,
    }
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"status={report['status']}")
    print(", ".join(f"{key}={value}" for key, value in totals.items()))
    for warning in warnings:
        print(f"warning: {warning}")
    for error in errors:
        print(f"error: {error}")
    print(f"report={args.report}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
