#!/usr/bin/env python3
"""Verify all downloaded JLPT4YOU N1 mock exams and their shared media."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scrape_jlpt4you import collect_media, iter_questions
from scrape_jlpt4you_mock import exam_number


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data",
        type=Path,
        default=Path(__file__).resolve().parent / "data" / "n1" / "mock",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path(__file__).resolve().parent / "mock_verification_report.json",
    )
    args = parser.parse_args()

    index_path = args.data / "index.json"
    errors: list[str] = []
    warnings: list[str] = []
    rows: list[dict[str, Any]] = []
    if not index_path.is_file():
        errors.append("missing mock/index.json")
        index: list[dict[str, str]] = []
    else:
        index = load_json(index_path)

    all_expected_urls: set[str] = set()
    all_saved_paths: set[Path] = set()
    media_occurrences = 0
    unavailable_occurrences = 0

    route_mismatches: list[tuple[int, str, str]] = []
    for item in index:
        exam_id = item.get("id", "")
        route_id = item.get("routeId", exam_id)
        try:
            number = int(item.get("directory") or exam_number(route_id))
        except ValueError as exc:
            errors.append(str(exc))
            continue
        exam_dir = args.data / f"{number:03d}"
        required = ["exam.json", "assets.json", "asset_errors.json"]
        missing = [name for name in required if not (exam_dir / name).is_file()]
        if missing:
            errors.append(f"mock {number:03d}: missing {', '.join(missing)}")
            continue

        exam = load_json(exam_dir / "exam.json")
        manifest = load_json(exam_dir / "assets.json")
        asset_errors = load_json(exam_dir / "asset_errors.json")
        sections = exam.get("sections", [])
        questions = list(iter_questions(exam))

        if exam.get("id") != exam_id:
            errors.append(f"mock route {number:03d}: indexed payload id mismatch")
        if route_id != exam_id:
            route_mismatches.append((number, route_id, exam_id))
        for question in questions:
            q_number = question.get("number", "?")
            options = question.get("options")
            answer = question.get("answer")
            if not isinstance(options, list) or not options:
                errors.append(f"mock {number:03d} question {q_number}: missing options")
            elif not isinstance(answer, int) or not 0 <= answer < len(options):
                errors.append(
                    f"mock {number:03d} question {q_number}: answer {answer!r} "
                    f"outside 0..{len(options) - 1}"
                )

        expected_urls = collect_media(exam)
        accounted_urls = set(manifest) | set(asset_errors)
        absent = expected_urls - accounted_urls
        unexpected = accounted_urls - expected_urls
        if absent:
            errors.append(f"mock {number:03d}: {len(absent)} media URL(s) unaccounted")
        if unexpected:
            errors.append(f"mock {number:03d}: {len(unexpected)} unexpected media URL(s)")

        for url, relative_path in manifest.items():
            target = (exam_dir / relative_path).resolve()
            shared_root = (args.data / "assets").resolve()
            if shared_root not in target.parents:
                errors.append(f"mock {number:03d}: media path leaves shared directory: {relative_path}")
                continue
            if not target.is_file() or target.stat().st_size == 0:
                errors.append(f"mock {number:03d}: missing or empty media for {url}")
            all_saved_paths.add(target)

        if len(sections) < 18:
            warnings.append(
                f"mock {number:03d}: source provides {len(sections)} sections and "
                f"{len(questions)} questions"
            )
        if asset_errors:
            warnings.append(
                f"mock {number:03d}: {len(asset_errors)} source media URL(s) unavailable"
            )

        all_expected_urls.update(expected_urls)
        media_occurrences += len(expected_urls)
        unavailable_occurrences += len(asset_errors)
        rows.append(
            {
                "number": number,
                "id": exam_id,
                "sections": len(sections),
                "questions": len(questions),
                "media": len(expected_urls),
                "media_unavailable": len(asset_errors),
            }
        )

    numbered_dirs = {
        int(path.name)
        for path in args.data.iterdir()
        if path.is_dir() and path.name.isdigit()
    }
    indexed_numbers = {
        int(item.get("directory") or exam_number(item.get("routeId", item["id"])))
        for item in index
        if item.get("id")
    }
    if numbered_dirs - indexed_numbers:
        warnings.append(
            "extra mock directories: "
            + ", ".join(f"{number:03d}" for number in sorted(numbered_dirs - indexed_numbers))
        )
    if route_mismatches:
        first = route_mismatches[0]
        last = route_mismatches[-1]
        warnings.append(
            f"source route/payload id mismatch for {len(route_mismatches)} exams; "
            f"first route {first[1]} -> {first[2]}, last route {last[1]} -> {last[2]}"
        )

    totals = {
        "exams": len(rows),
        "sections": sum(row["sections"] for row in rows),
        "questions": sum(row["questions"] for row in rows),
        "media_occurrences": media_occurrences,
        "unique_media_urls": len(all_expected_urls),
        "unique_media_files": len(all_saved_paths),
        "media_unavailable_occurrences": unavailable_occurrences,
    }
    report = {
        "status": "failed" if errors else "passed_with_warnings" if warnings else "passed",
        "totals": totals,
        "warnings": warnings,
        "errors": errors,
        "exams": rows,
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
