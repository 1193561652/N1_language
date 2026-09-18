#!/usr/bin/env python3
"""Download authorized N1 official-exam data exposed by JLPT4YOU's web app."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterable


ORIGIN = "https://www.jlpt4you.com"
API_TEMPLATE = ORIGIN + "/api/jlpt/exams-proxy/exams/official/N1/jlpt_test/{exam_id}"
EXAM_IDS = [
    "N1_2010_12_official",
    "N1_2011_07_official", "N1_2011_12_official",
    "N1_2012_07_official", "N1_2012_12_official",
    "N1_2013_07_official", "N1_2013_12_official",
    "N1_2014_07_official", "N1_2014_12_official",
    "N1_2015_07_official", "N1_2015_12_official",
    "N1_2016_07_official", "N1_2016_12_official",
    "N1_2017_07_official", "N1_2017_12_official",
    "N1_2018_07_official", "N1_2018_12_official",
    "N1_2019_07_official", "N1_2019_12_official",
    "N1_2020_12_official",
    "N1_2021_07_official", "N1_2021_12_official",
    "N1_2022_07_official", "N1_2022_12_official",
    "N1_2023_07_official", "N1_2023_12_official",
    "N1_2024_07_official", "N1_2024_12_official",
]
HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Referer": ORIGIN + "/jlpt/official/n1",
    "User-Agent": "Mozilla/5.0",
}


def year_from_id(exam_id: str) -> str:
    match = re.fullmatch(r"N1_(\d{4})_(\d{2})_official", exam_id)
    if not match:
        raise ValueError(f"Unexpected exam id: {exam_id}")
    return f"{match.group(1)}.{match.group(2)}"


def request_bytes(url: str, *, attempts: int = 4, timeout: int = 60) -> bytes:
    error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            request = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except (OSError, urllib.error.URLError, urllib.error.HTTPError) as exc:
            error = exc
            if attempt < attempts:
                time.sleep(attempt * 1.5)
    raise RuntimeError(f"Failed after {attempts} attempts: {url}: {error}")


def fetch_exam(exam_id: str) -> dict[str, Any]:
    value = json.loads(request_bytes(API_TEMPLATE.format(exam_id=exam_id)))
    if not isinstance(value, dict) or not isinstance(value.get("sections"), list):
        raise RuntimeError(f"Unexpected payload for {exam_id}")
    return value


def iter_questions(exam: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for section in exam.get("sections", []):
        for question in section.get("questions", []):
            if isinstance(question, dict):
                yield question


def collect_media(value: Any) -> set[str]:
    urls: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if (
                isinstance(child, str)
                and child.startswith(("http://", "https://"))
                and ("audio" in key.lower() or "image" in key.lower())
            ):
                urls.add(child)
            urls.update(collect_media(child))
    elif isinstance(value, list):
        for child in value:
            urls.update(collect_media(child))
    return urls


def asset_kind(url: str) -> str:
    normalized = url[:-5] if url.endswith("/view") else url
    suffix = Path(urllib.parse.urlparse(normalized).path).suffix.lower()
    if suffix in {".mp3", ".m4a", ".wav", ".ogg"}:
        return "audio"
    if suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}:
        return "images"
    return "other"


def download_assets(
    urls: Iterable[str], directory: Path, force: bool, delay: float
) -> tuple[dict[str, str], dict[str, str]]:
    manifest: dict[str, str] = {}
    failures: dict[str, str] = {}
    for index, original_url in enumerate(sorted(set(urls)), 1):
        download_url = original_url[:-5] if original_url.endswith("/view") else original_url
        parsed = urllib.parse.urlparse(download_url)
        name = Path(parsed.path).name or "asset"
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
        prefix = hashlib.sha1(original_url.encode()).hexdigest()[:10]
        target = directory / asset_kind(download_url) / f"{prefix}_{safe_name}"
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_file() and target.stat().st_size > 0 and not force:
            print(f"  asset {index}: exists {target.name}")
        else:
            try:
                target.write_bytes(request_bytes(download_url, attempts=5, timeout=90))
                print(f"  asset {index}: saved {target.name}")
            except RuntimeError as exc:
                failures[original_url] = str(exc)
                print(f"  asset {index}: unavailable {download_url}: {exc}")
                continue
            if delay:
                time.sleep(delay)
        manifest[original_url] = target.relative_to(directory).as_posix()
    return manifest, failures


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def select_exam_ids(raw: str) -> list[str]:
    if raw.lower() == "all":
        return EXAM_IDS
    requested = [item.strip() for item in raw.split(",") if item.strip()]
    by_year = {year_from_id(exam_id): exam_id for exam_id in EXAM_IDS}
    unknown = [year for year in requested if year not in by_year]
    if unknown:
        raise ValueError(f"Unavailable year(s): {', '.join(unknown)}")
    return [by_year[year] for year in requested]


def verify_exam(exam: dict[str, Any], exam_id: str) -> tuple[int, int, int]:
    questions = list(iter_questions(exam))
    missing_answers = sum(q.get("answer") is None for q in questions)
    bad_options = sum(not isinstance(q.get("options"), list) for q in questions)
    if not questions or missing_answers or bad_options:
        raise RuntimeError(
            f"{exam_id}: questions={len(questions)}, missing_answers={missing_answers}, "
            f"bad_options={bad_options}"
        )
    return len(exam.get("sections", [])), len(questions), len(collect_media(exam))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", default="all", help="all or comma-separated years, e.g. 2019.12")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent / "data" / "n1")
    parser.add_argument("--download-assets", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--delay", type=float, default=0.2)
    args = parser.parse_args()

    selected = select_exam_ids(args.years)
    index = [{"year": year_from_id(exam_id), "examId": exam_id} for exam_id in EXAM_IDS]
    save_json(args.output.parent / "index.json", index)

    totals = {"exams": 0, "sections": 0, "questions": 0, "assets": 0, "asset_errors": 0}
    for exam_id in selected:
        year = year_from_id(exam_id)
        year_dir = args.output / year
        exam_path = year_dir / "exam.json"
        if exam_path.is_file() and not args.force:
            exam = json.loads(exam_path.read_text(encoding="utf-8"))
            print(f"n1 {year}: existing exam")
        else:
            print(f"n1 {year}: downloading exam")
            exam = fetch_exam(exam_id)
            save_json(exam_path, exam)

        sections, questions, media = verify_exam(exam, exam_id)
        print(f"  verified sections={sections}, questions={questions}, media={media}")
        totals["exams"] += 1
        totals["sections"] += sections
        totals["questions"] += questions

        if args.download_assets:
            manifest, failures = download_assets(
                collect_media(exam), year_dir / "assets", args.force, args.delay
            )
            save_json(year_dir / "assets.json", manifest)
            save_json(year_dir / "asset_errors.json", failures)
            totals["assets"] += len(manifest)
            totals["asset_errors"] += len(failures)

    print("complete " + ", ".join(f"{key}={value}" for key, value in totals.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
