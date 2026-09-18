#!/usr/bin/env python3
"""Verify downloaded Shaobing Japanese exams and their media manifests."""

from __future__ import annotations

import json
from pathlib import Path

from scrape_sbry import add_generated_audio_urls, collect_urls, iter_questions


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data" / "n1"


def main() -> int:
    errors: list[str] = []
    rows: list[tuple[str, int, int, int]] = []

    menu = json.loads((ROOT / "data" / "menu.json").read_text(encoding="utf-8"))
    level = next(item for item in menu if str(item.get("k", "")).lower() == "n1")
    expected_years = [str(item["k"]) for item in level.get("c", [])]
    actual_years = sorted(path.name for path in DATA_DIR.iterdir() if path.is_dir())
    if set(actual_years) != set(expected_years):
        errors.append(
            f"year mismatch: expected={sorted(expected_years)}, actual={actual_years}"
        )

    for year in expected_years:
        year_dir = DATA_DIR / year
        exam_path = year_dir / "exam.json"
        manifest_path = year_dir / "assets.json"
        if not exam_path.is_file() or not manifest_path.is_file():
            errors.append(f"{year}: exam.json or assets.json is missing")
            continue

        exam = json.loads(exam_path.read_text(encoding="utf-8"))
        questions = list(iter_questions(exam))
        with_id = [q for q in questions if q.get("questionId") is not None]
        analyses = [q for q in with_id if q.get("analysis")]
        if len(analyses) != len(with_id):
            errors.append(f"{year}: {len(with_id) - len(analyses)} analyses missing")

        expected_urls = collect_urls(exam)
        expected_urls.update(add_generated_audio_urls(exam, "n1", year))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        missing_urls = expected_urls - set(manifest)
        extra_urls = set(manifest) - expected_urls
        if missing_urls:
            errors.append(f"{year}: {len(missing_urls)} URLs absent from assets.json")
        if extra_urls:
            errors.append(f"{year}: {len(extra_urls)} unexpected URLs in assets.json")

        missing_files = []
        empty_files = []
        for url, relative_path in manifest.items():
            asset_path = year_dir / "assets" / relative_path
            if not asset_path.is_file():
                missing_files.append(url)
            elif asset_path.stat().st_size == 0:
                empty_files.append(url)
        if missing_files:
            errors.append(f"{year}: {len(missing_files)} asset files missing")
        if empty_files:
            errors.append(f"{year}: {len(empty_files)} asset files empty")

        rows.append((year, len(questions), len(analyses), len(manifest)))

    print(f"years={len(rows)}")
    print(f"questions={sum(row[1] for row in rows)}")
    print(f"analyses={sum(row[2] for row in rows)}")
    print(f"assets={sum(row[3] for row in rows)}")
    print(f"errors={len(errors)}")
    for error in errors:
        print(f"ERROR: {error}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
