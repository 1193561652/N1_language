#!/usr/bin/env python3
"""Download authorized exam data from the Shaobing Japanese web question bank.

The script uses only Python's standard library. Passwords are read with getpass,
hashed exactly as the website does, and are never written to disk.
"""

from __future__ import annotations

import argparse
import base64
import ctypes
import getpass
import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterable


LOCAL_DEPS = Path(__file__).resolve().parent / ".deps"
if LOCAL_DEPS.is_dir():
    sys.path.insert(0, str(LOCAL_DEPS))


API_BASE = "https://web.sbry.tech/api"
WEB_ORIGIN = "https://web.sbry.tech/"
USER_ID_OFFSET = 19_900_000
URL_RE = re.compile(r"https?://[^\s\"'<>]+")
MEDIA_SUFFIXES = {
    ".mp3", ".m4a", ".wav", ".ogg",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg",
}
DEFAULT_AUTH_FILE = Path(__file__).resolve().parent / ".sbry_auth.dpapi"


class DataBlob(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_ulong), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _to_blob(data: bytes) -> tuple[DataBlob, Any]:
    buffer = ctypes.create_string_buffer(data)
    blob = DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
    return blob, buffer


def dpapi_protect(data: bytes) -> bytes:
    if os.name != "nt":
        raise ApiError("Secure token caching currently requires Windows DPAPI")
    source, source_buffer = _to_blob(data)
    target = DataBlob()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    if not crypt32.CryptProtectData(
        ctypes.byref(source), "Shaobing Japanese auth", None, None, None, 0,
        ctypes.byref(target),
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(target.pbData, target.cbData)
    finally:
        kernel32.LocalFree(target.pbData)


def dpapi_unprotect(data: bytes) -> bytes:
    if os.name != "nt":
        raise ApiError("Secure token caching currently requires Windows DPAPI")
    source, source_buffer = _to_blob(data)
    target = DataBlob()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    if not crypt32.CryptUnprotectData(
        ctypes.byref(source), None, None, None, None, 0, ctypes.byref(target)
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(target.pbData, target.cbData)
    finally:
        kernel32.LocalFree(target.pbData)


class ApiError(RuntimeError):
    """Raised when the remote API returns a non-success response."""


class SbryClient:
    def __init__(self, delay: float = 0.25, retries: int = 3) -> None:
        self.delay = max(0.0, delay)
        self.retries = max(1, retries)
        self.user_id: int | None = None
        self.headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": WEB_ORIGIN.rstrip("/"),
            "Referer": WEB_ORIGIN,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/128 Safari/537.36",
            "X-SBRY-BUNDLE-ID": "com.sbry.web",
            "X-SBRY-PLATFORM": "Windows",
            "X-SBRY-APP-VERSION-NAME": "1.0.0",
            "X-SBRY-DEVICE-NAME": "Windows",
            "X-SBRY-DEVICE-VERSION": "1.0.0",
            "X-SBRY-CHANNEL-CODE": "desktop",
        }

    def _post(self, path: str, payload: Any = None) -> Any:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            API_BASE + path,
            data=body,
            headers=self.headers,
            method="POST",
        )
        last_error: Exception | None = None
        for attempt in range(self.retries):
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    wrapper = json.loads(response.read().decode("utf-8"))
                if wrapper.get("code") != 0:
                    raise ApiError(
                        f"API {path} failed: code={wrapper.get('code')} "
                        f"msg={wrapper.get('msg')}"
                    )
                if self.delay:
                    time.sleep(self.delay)
                return wrapper.get("data")
            except ApiError:
                raise
            except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt + 1 < self.retries:
                    time.sleep(2**attempt)
        raise ApiError(f"Request {path} failed after {self.retries} attempts: {last_error}")

    def _activate_login(self, data: Any) -> dict[str, Any]:
        if not isinstance(data, dict) or "token" not in data or "userId" not in data:
            raise ApiError("Login succeeded but the response did not contain token/userId")

        # The web client stores and sends this offset identifier in X-SBRY-USER-ID.
        self.user_id = int(data["userId"]) - USER_ID_OFFSET
        token = str(data["token"])
        self.headers.update(
            {
                "Authorization": token,
                "X-SBRY-USER-TOKEN": token,
                "X-SBRY-USER-ID": str(self.user_id),
            }
        )
        return data

    def export_auth(self, profile: dict[str, Any]) -> dict[str, Any]:
        if self.user_id is None or "Authorization" not in self.headers:
            raise ApiError("There is no active login to cache")
        return {
            "token": self.headers["Authorization"],
            "userId": self.user_id,
            "nickName": profile.get("nickName"),
        }

    def activate_cached_auth(self, data: Any) -> dict[str, Any]:
        if not isinstance(data, dict) or not data.get("token"):
            raise ApiError("The local authentication cache is invalid")
        self.user_id = int(data["userId"])
        token = str(data["token"])
        self.headers.update(
            {
                "Authorization": token,
                "X-SBRY-USER-TOKEN": token,
                "X-SBRY-USER-ID": str(self.user_id),
            }
        )
        return data

    def validate_auth(self) -> None:
        self._post("/web/exam/user/question/fav/list")

    def login(self, username: str, password: str) -> dict[str, Any]:
        password_md5 = hashlib.md5(password.encode("utf-8")).hexdigest().upper()
        data = self._post(
            "/web/login/user",
            {"userName": username.strip(), "password": password_md5},
        )
        return self._activate_login(data)

    def begin_qr_login(self) -> str:
        token = self._post("/web/login/scan")
        if not isinstance(token, str) or not token:
            raise ApiError("The QR login endpoint returned an invalid token")
        return token

    def poll_qr_login(self, scan_token: str, timeout: int = 60) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        query = urllib.parse.urlencode({"token": scan_token})
        while time.monotonic() < deadline:
            request = urllib.request.Request(
                f"{API_BASE}/web/login/scan/query?{query}",
                data=b"",
                headers={
                    **self.headers,
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=15) as response:
                    wrapper = json.loads(response.read().decode("utf-8"))
            except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
                raise ApiError(f"QR login polling failed: {exc}") from exc
            if wrapper.get("code") != 0:
                raise ApiError(
                    f"QR login failed: code={wrapper.get('code')} msg={wrapper.get('msg')}"
                )
            if wrapper.get("data"):
                return self._activate_login(wrapper["data"])
            time.sleep(2)
        raise ApiError("QR code expired before login was confirmed")

    def menu(self) -> list[dict[str, Any]]:
        data = self._post("/web/exam/menu")
        parsed = json.loads(data) if isinstance(data, str) else data
        if not isinstance(parsed, list):
            raise ApiError("Unexpected exam menu format")
        return parsed

    def _decode(self, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass
        if self.user_id is None:
            raise ApiError("Encrypted data cannot be decoded before login")

        encrypted = value.encode("utf-8")
        if not encrypted:
            return None
        rotated = encrypted[1:] + encrypted[:1]
        marker = base64.b64encode(str(self.user_id).encode("ascii"))
        marker_at = rotated.find(marker)
        if marker_at < 0:
            raise ApiError("Could not locate the user marker in encrypted data")
        compact = rotated[:marker_at] + rotated[marker_at + len(marker) :]
        try:
            uri_encoded = base64.b64decode(compact, validate=True).decode("latin-1")
            clear_text = urllib.parse.unquote_to_bytes(uri_encoded).decode("utf-8")
            return json.loads(clear_text)
        except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
            raise ApiError(f"Could not decode encrypted exam data: {exc}") from exc

    def exam_year(self, level: str, year: str) -> dict[str, Any]:
        data = self._post(
            "/web/exam/query/year",
            {"nType": level, "year": year, "categories": []},
        )
        decoded = self._decode(data)
        if not isinstance(decoded, dict):
            raise ApiError(f"Unexpected exam payload for {level} {year}")
        return decoded

    def question_analysis(self, question_id: Any) -> Any:
        encoded_id = urllib.parse.quote(str(question_id), safe="")
        return self._decode(self._post(f"/web/exam/user/question/{encoded_id}"))


def find_level(menu: list[dict[str, Any]], level: str) -> dict[str, Any]:
    for item in menu:
        if str(item.get("k", "")).lower() == level.lower():
            return item
    available = ", ".join(str(item.get("k")) for item in menu)
    raise ApiError(f"Unknown level {level!r}; available: {available}")


def available_years(level_menu: dict[str, Any]) -> list[str]:
    return [str(item["k"]) for item in level_menu.get("c", []) if "k" in item]


def iter_questions(exam: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for part in exam.get("parts", []) or []:
        for group in part.get("bigQuestionBeans", []) or []:
            for question in group.get("questions", []) or []:
                if isinstance(question, dict):
                    yield question


def add_analysis(
    client: SbryClient, exam: dict[str, Any], checkpoint_path: Path | None = None
) -> tuple[int, int]:
    completed = 0
    skipped = 0
    for question in iter_questions(exam):
        question_id = question.get("questionId")
        if question_id is None:
            skipped += 1
            continue
        if question.get("analysis"):
            skipped += 1
            continue
        question["analysis"] = client.question_analysis(question_id)
        completed += 1
        if checkpoint_path is not None and completed % 10 == 0:
            save_json(checkpoint_path, exam)
    return completed, skipped


def collect_urls(value: Any) -> set[str]:
    urls: set[str] = set()
    if isinstance(value, dict):
        for child in value.values():
            urls.update(collect_urls(child))
    elif isinstance(value, list):
        for child in value:
            urls.update(collect_urls(child))
    elif isinstance(value, str):
        for match in URL_RE.findall(value):
            url = html.unescape(match).rstrip(".,;)")
            suffix = Path(urllib.parse.urlparse(url).path).suffix.lower()
            if suffix in MEDIA_SUFFIXES:
                urls.add(url)
    return urls


def add_generated_audio_urls(exam: dict[str, Any], level: str, year: str) -> set[str]:
    base = "https://sbry-referer.oss-cn-beijing.aliyuncs.com/web"
    urls = {f"{base}/full/{hashlib.md5((level + year).encode()).hexdigest()}.mp3"}
    for question in iter_questions(exam):
        if question.get("listening") and question.get("questionId") is not None:
            digest = hashlib.md5(str(question["questionId"]).encode()).hexdigest()
            urls.add(f"{base}/hub/{digest}.mp3")
    return urls


def asset_subdir(url: str) -> str:
    suffix = Path(urllib.parse.urlparse(url).path).suffix.lower()
    if suffix in {".mp3", ".m4a", ".wav", ".ogg"}:
        return "audio"
    if suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}:
        return "images"
    return "other"


def download_assets(
    urls: Iterable[str], output_dir: Path, delay: float, force: bool
) -> dict[str, str]:
    manifest: dict[str, str] = {}
    headers = {"Referer": WEB_ORIGIN, "User-Agent": "Mozilla/5.0"}
    for index, url in enumerate(sorted(set(urls)), 1):
        parsed = urllib.parse.urlparse(url)
        original_name = Path(parsed.path).name or "asset"
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", original_name)
        prefix = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
        target = output_dir / asset_subdir(url) / f"{prefix}_{safe_name}"
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and not force:
            manifest[url] = target.relative_to(output_dir).as_posix()
            print(f"  asset {index}: exists {target.name}")
            continue
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                target.write_bytes(response.read())
            manifest[url] = target.relative_to(output_dir).as_posix()
            print(f"  asset {index}: saved {target.name}")
            if delay:
                time.sleep(delay)
        except (OSError, urllib.error.URLError) as exc:
            print(f"  asset {index}: failed {url}: {exc}", file=sys.stderr)
    return manifest


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def save_auth(path: Path, client: SbryClient, profile: dict[str, Any]) -> None:
    payload = json.dumps(client.export_auth(profile), ensure_ascii=False).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(dpapi_protect(payload))


def load_auth(path: Path, client: SbryClient) -> dict[str, Any]:
    payload = json.loads(dpapi_unprotect(path.read_bytes()).decode("utf-8"))
    return client.activate_cached_auth(payload)


def parse_year_filter(raw: str, all_years: list[str]) -> list[str]:
    if raw.lower() == "all":
        return all_years
    requested = [item.strip() for item in raw.split(",") if item.strip()]
    unknown = [item for item in requested if item not in all_years]
    if unknown:
        raise ApiError(f"Unavailable year(s): {', '.join(unknown)}")
    return requested


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download authorized Shaobing Japanese exam data"
    )
    parser.add_argument("--level", default="n1", help="n1, n2, n3, n4, n5 or gk")
    parser.add_argument(
        "--years", default="all", help="all, or comma-separated values such as 2022.12,2022.07"
    )
    parser.add_argument("--username", default=os.getenv("SBRY_USERNAME"))
    parser.add_argument(
        "--qr-login", action="store_true", help="log in by scanning a terminal QR code"
    )
    parser.add_argument(
        "--auth-file", type=Path, default=DEFAULT_AUTH_FILE,
        help="DPAPI-encrypted local authentication cache",
    )
    parser.add_argument(
        "--no-auth-cache", action="store_true", help="do not read or save authentication cache"
    )
    parser.add_argument(
        "--output", type=Path, default=Path(__file__).resolve().parent / "data"
    )
    parser.add_argument("--list", action="store_true", help="list available years without logging in")
    parser.add_argument("--skip-analysis", action="store_true", help="do not fetch per-question analyses")
    parser.add_argument("--download-assets", action="store_true", help="download referenced images and audio")
    parser.add_argument("--delay", type=float, default=0.25, help="seconds between requests")
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--force", action="store_true", help="overwrite existing exam and asset files")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    client = SbryClient(delay=args.delay, retries=args.retries)
    try:
        menu = client.menu()
        level_menu = find_level(menu, args.level)
        years = available_years(level_menu)
        if args.list:
            print(f"{args.level}: {', '.join(years)}")
            return 0

        profile: dict[str, Any] | None = None
        if not args.no_auth_cache and args.auth_file.exists():
            try:
                profile = load_auth(args.auth_file, client)
                client.validate_auth()
                print(f"Using encrypted cached login for {profile.get('nickName') or 'user'}")
            except (ApiError, OSError, ValueError, json.JSONDecodeError) as exc:
                print(f"Cached login is unavailable: {exc}", file=sys.stderr)
                profile = None

        if profile is None and args.qr_login:
            try:
                import qrcode
            except ImportError as exc:
                raise ApiError(
                    "QR support is missing; run: python -m pip install --target .deps qrcode"
                ) from exc
            scan_token = client.begin_qr_login()
            qr = qrcode.QRCode(border=2)
            qr.add_data(scan_token)
            qr.make(fit=True)
            qr_path = Path(__file__).resolve().parent / "login_qr.png"
            qr.make_image(fill_color="black", back_color="white").save(qr_path)
            print(f"QR image: {qr_path}")
            print("Scan this code in the Shaobing Japanese app within 60 seconds:")
            qr.print_ascii(invert=True)
            try:
                profile = client.poll_qr_login(scan_token)
            finally:
                qr_path.unlink(missing_ok=True)
            print(f"Logged in as {profile.get('nickName') or 'QR user'}")
        elif profile is None:
            username = args.username or input("Shaobing username: ").strip()
            password = getpass.getpass("Shaobing password (not saved): ")
            profile = client.login(username, password)
            print(f"Logged in as {profile.get('nickName') or username}")

        if not args.no_auth_cache and profile is not None:
            save_auth(args.auth_file, client, profile)
            print(f"Encrypted login cache saved to {args.auth_file}")

        selected_years = parse_year_filter(args.years, years)
        menu_path = args.output / "menu.json"
        save_json(menu_path, menu)

        for year in selected_years:
            year_dir = args.output / args.level / year
            exam_path = year_dir / "exam.json"
            if exam_path.exists() and not args.force:
                exam = json.loads(exam_path.read_text(encoding="utf-8"))
                print(f"{args.level} {year}: resuming existing exam")
            else:
                print(f"{args.level} {year}: downloading exam")
                exam = client.exam_year(args.level, year)
                save_json(exam_path, exam)
            if not args.skip_analysis:
                added, skipped = add_analysis(client, exam, exam_path)
                print(f"  analyses: added={added}, already-present/missing-id={skipped}")

            save_json(exam_path, exam)
            print(f"  saved {exam_path}")

            if args.download_assets:
                urls = collect_urls(exam)
                urls.update(add_generated_audio_urls(exam, args.level, year))
                asset_map = download_assets(urls, year_dir / "assets", args.delay, args.force)
                save_json(year_dir / "assets.json", asset_map)

        return 0
    except (ApiError, KeyboardInterrupt) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
