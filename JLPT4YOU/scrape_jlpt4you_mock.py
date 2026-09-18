#!/usr/bin/env python3
"""Download JLPT4YOU's N1 custom/mock exams from the web app's public API."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable

from scrape_jlpt4you import (
    ORIGIN,
    asset_kind,
    collect_media,
    request_bytes,
    save_json,
    verify_exam,
)


LIST_API = ORIGIN + "/api/jlpt/exams-proxy/exams/custom/N1/jlpt_test?page={page}&limit=100"
DETAIL_API = ORIGIN + "/api/jlpt/exams-proxy/exams/custom/N1/jlpt_test/{exam_id}"
ID_PATTERN = re.compile(r"jlpt4you_N1_(\d+)$")


def fetch_json(url: str) -> Any:
    return json.loads(request_bytes(url))


def discover_exams() -> list[dict[str, str]]:
    exams: list[dict[str, str]] = []
    page = 1
    while True:
        payload = fetch_json(LIST_API.format(page=page))
        items = payload.get("items", []) if isinstance(payload, dict) else []
        for item in items:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                exams.append(
                    {
                        "id": item["id"],
                        "title": str(item.get("title") or item["id"]),
                    }
                )
        if not payload.get("hasNext"):
            break
        page += 1
    exams.sort(key=lambda item: exam_number(item["id"]))
    return exams


def exam_number(exam_id: str) -> int:
    match = ID_PATTERN.fullmatch(exam_id)
    if not match:
        raise ValueError(f"Unexpected mock exam id: {exam_id}")
    return int(match.group(1))


def select_exams(exams: list[dict[str, str]], raw: str) -> list[dict[str, str]]:
    if raw.lower() == "all":
        return exams
    wanted: set[int] = set()
    for token in (part.strip() for part in raw.split(",")):
        if not token:
            continue
        if "-" in token:
            start, end = (int(part) for part in token.split("-", 1))
            if start > end:
                raise ValueError(f"Invalid range: {token}")
            wanted.update(range(start, end + 1))
        else:
            wanted.add(int(token))
    available = {exam_number(item["id"]): item for item in exams}
    missing = sorted(wanted - set(available))
    if missing:
        raise ValueError(f"Unavailable mock exam number(s): {missing}")
    return [available[number] for number in sorted(wanted)]


def asset_target(original_url: str, directory: Path) -> Path:
    download_url = original_url[:-5] if original_url.endswith("/view") else original_url
    parsed = urllib.parse.urlparse(download_url)
    name = Path(parsed.path).name or "asset"
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    prefix = hashlib.sha1(original_url.encode()).hexdigest()[:10]
    return directory / asset_kind(download_url) / f"{prefix}_{safe_name}"


def download_one(url: str, directory: Path, force: bool) -> tuple[str, str | None, str | None]:
    target = asset_target(url, directory)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not (target.is_file() and target.stat().st_size > 0 and not force):
        download_url = url[:-5] if url.endswith("/view") else url
        try:
            target.write_bytes(request_bytes(download_url, attempts=5, timeout=90))
        except RuntimeError as exc:
            return url, None, str(exc)
    return url, target.relative_to(directory).as_posix(), None


def download_assets_parallel(
    urls: Iterable[str], directory: Path, force: bool, workers: int
) -> tuple[dict[str, str], dict[str, str]]:
    unique = sorted(set(urls))
    manifest: dict[str, str] = {}
    failures: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(download_one, url, directory, force): url for url in unique
        }
        completed = 0
        for future in as_completed(futures):
            url, relative_path, error = future.result()
            completed += 1
            if error:
                failures[url] = error
                print(f"    media {completed}/{len(unique)} unavailable")
            else:
                manifest[url] = str(relative_path)
                if completed == len(unique) or completed % 10 == 0:
                    print(f"    media {completed}/{len(unique)}")
    return dict(sorted(manifest.items())), dict(sorted(failures.items()))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exams", default="all", help="all, comma list, or range, e.g. 1,3,10-20")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "data" / "n1" / "mock",
    )
    parser.add_argument("--download-assets", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--delay", type=float, default=0.2)
    args = parser.parse_args()
    if not 1 <= args.workers <= 8:
        parser.error("--workers must be between 1 and 8")

    discovered = discover_exams()
    selected = select_exams(discovered, args.exams)
    save_json(args.output / "source_index.json", discovered)
    print(f"discovered={len(discovered)}, selected={len(selected)}")

    totals = {"exams": 0, "sections": 0, "questions": 0, "assets": 0, "asset_errors": 0}
    resolved_index: list[dict[str, Any]] = []
    for position, item in enumerate(selected, 1):
        exam_id = item["id"]
        number = exam_number(exam_id)
        exam_dir = args.output / f"{number:03d}"
        exam_path = exam_dir / "exam.json"
        if exam_path.is_file() and not args.force:
            exam = json.loads(exam_path.read_text(encoding="utf-8"))
            state = "existing"
        else:
            exam = fetch_json(DETAIL_API.format(exam_id=exam_id))
            save_json(exam_path, exam)
            state = "saved"
        sections, questions, media = verify_exam(exam, exam_id)
        resolved_index.append(
            {
                "routeId": exam_id,
                "id": str(exam.get("id") or exam_id),
                "title": str(exam.get("title") or item["title"]),
                "directory": f"{number:03d}",
            }
        )
        print(
            f"mock {number:03d} ({position}/{len(selected)}): {state}, "
            f"sections={sections}, questions={questions}, media={media}"
        )
        totals["exams"] += 1
        totals["sections"] += sections
        totals["questions"] += questions

        if args.download_assets:
            manifest, failures = download_assets_parallel(
                collect_media(exam), args.output / "assets", args.force, args.workers
            )
            shared_manifest = {
                url: "../assets/" + relative_path for url, relative_path in manifest.items()
            }
            save_json(exam_dir / "assets.json", shared_manifest)
            save_json(exam_dir / "asset_errors.json", failures)
            totals["assets"] += len(manifest)
            totals["asset_errors"] += len(failures)
        if args.delay:
            time.sleep(args.delay)

    save_json(args.output / "index.json", resolved_index)
    print("complete " + ", ".join(f"{key}={value}" for key, value in totals.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
