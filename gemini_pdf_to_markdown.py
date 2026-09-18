#!/usr/bin/env python
"""
Convert a PDF into AI-readable Markdown with Google Gemini vision.

Workflow:
1. Render each PDF page to an image.
2. Send each page image to Gemini generateContent.
3. Cache every page result.
4. Merge page Markdown into one AI-readable Markdown file.
5. Write a Markdown status file with MD5 and page-level quality.

Before running, paste your Gemini API key below or set GEMINI_API_KEY in your
PowerShell environment.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image


# =========================
# 在这里填写你的 Gemini API Key
# 示例：GEMINI_API_KEY = "AIza..."
# 如果这里留空，脚本会读取系统环境变量 GEMINI_API_KEY。
# =========================
_LOCAL_KEY_FILE = Path(__file__).resolve().parent / "local-config" / "gemini-converter-key.txt"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "") or (_LOCAL_KEY_FILE.read_text(encoding="utf-8").strip() if _LOCAL_KEY_FILE.exists() else "")


GEMINI_API_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


PROJECT_ROOT = Path(__file__).resolve().parent

# =========================
# 批量返工配置
# 直接运行本脚本时，会按这里的清单依次转换。
# =========================
BATCH_OUTPUT_DIR = PROJECT_ROOT / r"output\library2_gemini_batch"
BATCH_WORKDIR = PROJECT_ROOT / r"tmp\gemini_pdf_to_markdown_batch"
BATCH_MODEL = "gemini-3.5-flash"
BATCH_JOBS = [
    {
        "label": "2023年12月N1真题",
        "pdf": PROJECT_ROOT / r"library2\2023年12月\12023年12月N1_真题.pdf",
        "out": BATCH_OUTPUT_DIR / "2023年12月N1真题_Gemini视觉主底稿.md",
        "status": BATCH_OUTPUT_DIR / "2023年12月N1真题_转换状态.md",
        "request_log": BATCH_OUTPUT_DIR / "2023年12月N1真题_请求记录.jsonl",
    },
    {
        "label": "2024年12月N1真题",
        "pdf": PROJECT_ROOT / r"library2\2024年12月\2024年12月N1真题试卷.pdf",
        "out": BATCH_OUTPUT_DIR / "2024年12月N1真题_Gemini视觉主底稿.md",
        "status": BATCH_OUTPUT_DIR / "2024年12月N1真题_转换状态.md",
        "request_log": BATCH_OUTPUT_DIR / "2024年12月N1真题_请求记录.jsonl",
    },
    {
        "label": "2025年7月N1真题",
        "pdf": PROJECT_ROOT / r"library2\2025年7月\试题2025年7月JLPT日语N1真题.pdf",
        "out": BATCH_OUTPUT_DIR / "2025年7月N1真题_Gemini视觉主底稿.md",
        "status": BATCH_OUTPUT_DIR / "2025年7月N1真题_转换状态.md",
        "request_log": BATCH_OUTPUT_DIR / "2025年7月N1真题_请求记录.jsonl",
    },
    {
        "label": "2025年12月N1真题",
        "pdf": PROJECT_ROOT / r"library2\2025年12月\25年12月N1真题.pdf",
        "out": BATCH_OUTPUT_DIR / "2025年12月N1真题_Gemini视觉主底稿.md",
        "status": BATCH_OUTPUT_DIR / "2025年12月N1真题_转换状态.md",
        "request_log": BATCH_OUTPUT_DIR / "2025年12月N1真题_请求记录.jsonl",
    },
]


class GeminiQuotaError(RuntimeError):
    def __init__(self, message: str, retry_seconds: int | None = None, daily_limit: bool = False) -> None:
        super().__init__(message)
        self.retry_seconds = retry_seconds
        self.daily_limit = daily_limit


class GeminiEmptyResponseError(RuntimeError):
    pass


def parse_pages(spec: str | None, total_pages: int) -> list[int]:
    if not spec:
        return list(range(1, total_pages + 1))

    pages: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            pages.update(range(int(start_s), int(end_s) + 1))
        else:
            pages.add(int(part))

    return [p for p in sorted(pages) if 1 <= p <= total_pages]


def require_tool(name: str) -> str:
    bundled_runtime_poppler = Path(
        r"C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin"
    ) / f"{name}.exe"
    if bundled_runtime_poppler.exists():
        return str(bundled_runtime_poppler)

    deps_dir = Path(sys.executable).resolve().parent.parent
    bundled_poppler = deps_dir / "native" / "poppler" / "Library" / "bin" / f"{name}.exe"
    if bundled_poppler.exists():
        return str(bundled_poppler)

    path = shutil.which(name)
    if path:
        return path

    for suffix in ("", ".cmd", ".exe"):
        candidate = deps_dir / "bin" / "override" / f"{name}{suffix}"
        if candidate.exists():
            return str(candidate)

    raise SystemExit(f"缺少 PDF 工具：{name}")


def run_command(args: list[str]) -> str:
    proc = subprocess.run(
        args,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.stdout.strip()


def pdf_page_count(pdf: Path) -> int:
    output = run_command([require_tool("pdfinfo"), str(pdf)])
    match = re.search(r"^Pages:\s+(\d+)\s*$", output, re.MULTILINE)
    if not match:
        raise SystemExit("无法读取 PDF 页数。")
    return int(match.group(1))


def md5_file(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def render_page(pdf: Path, page_num: int, image_dir: Path, dpi: int) -> Path:
    image_dir.mkdir(parents=True, exist_ok=True)
    prefix = image_dir / f"page_{page_num:03d}"
    expected = image_dir / f"page_{page_num:03d}-{page_num:02d}.png"
    if expected.exists():
        return expected

    run_command(
        [
            require_tool("pdftoppm"),
            "-png",
            "-r",
            str(dpi),
            "-f",
            str(page_num),
            "-l",
            str(page_num),
            str(pdf),
            str(prefix),
        ]
    )

    matches = sorted(image_dir.glob(f"page_{page_num:03d}-*.png"))
    if not matches:
        raise SystemExit(f"PDF Page {page_num:03d} 渲染失败。")
    return matches[0]


def compress_image(image_path: Path, max_side: int, quality: int) -> Path:
    out = image_path.with_suffix(".jpg")
    if out.exists():
        return out

    with Image.open(image_path) as img:
        img = img.convert("RGB")
        w, h = img.size
        scale = min(1.0, max_side / max(w, h))
        if scale < 1.0:
            img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
        img.save(out, "JPEG", quality=quality, optimize=True)
    return out


def image_base64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def page_prompt(page_num: int, total_pages: int) -> str:
    return f"""请读取这张 JLPT N1 真题 PDF 页面图像，并转换为 AI 易读 Markdown。

硬性要求：
0. 只输出该页 Markdown 正文，不要解释识别过程，不要自我修正，不要输出代码块。
1. 忠实提取原文，不要改写题干、选项、文章或听力内容。
2. 页面标题必须写为：## PDF Page {page_num:03d}
3. 如果页面中有 問題1、問題2、問題3 等题组，请用三级标题标出，例如：### 問題1
4. 每道题尽量保留题号、题干、选项结构。选项编号不要丢失。
5. 如果原文是分栏排版，请按正常阅读顺序整理，不要把左右栏混在一起。
6. 对不确定或看不清的文字，用 [不确定: 原因] 标记，不要猜。
7. 不要添加原文没有的解释、翻译或答案。
8. 不要使用 HTML ruby 标签；有振假名时按普通文本尽量保留，不要膨胀成复杂 HTML。
9. 页面末尾必须添加一行 HTML 注释，格式严格为：
<!-- page_quality: 高/中/低; reason: 简短中文原因 -->

当前页：{page_num}/{total_pages}
请只输出这一页的 Markdown。"""


def extract_gemini_text(response: dict) -> str:
    chunks: list[str] = []
    for candidate in response.get("candidates", []) or []:
        content = candidate.get("content") or {}
        for part in content.get("parts", []) or []:
            text = part.get("text")
            if isinstance(text, str):
                chunks.append(text)

    text = "\n".join(chunks).strip()
    if text:
        return text

    block_reason = response.get("promptFeedback", {}).get("blockReason")
    if block_reason:
        raise RuntimeError(f"Gemini blocked the response: {block_reason}")
    raise GeminiEmptyResponseError("Gemini response did not contain text.")


def parse_retry_seconds(payload: dict) -> int | None:
    for detail in payload.get("error", {}).get("details", []) or []:
        retry_delay = detail.get("retryDelay")
        if isinstance(retry_delay, str):
            match = re.match(r"^(\d+)s$", retry_delay)
            if match:
                return int(match.group(1))
    return None


def is_daily_quota(payload: dict) -> bool:
    details = payload.get("error", {}).get("details", []) or []
    for detail in details:
        for violation in detail.get("violations", []) or []:
            quota_id = str(violation.get("quotaId", ""))
            quota_metric = str(violation.get("quotaMetric", ""))
            if "PerDay" in quota_id or "free_tier_requests" in quota_metric:
                return True
    return False


def append_request_log(log_path: Path | None, event: dict) -> None:
    if log_path is None:
        return

    log_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "time": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        **event,
    }
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
        f.flush()


def call_gemini(
    api_key: str,
    model: str,
    prompt: str,
    image_b64: str,
    max_output_tokens: int,
    temperature: float,
    retries: int,
    page_num: int,
    request_log: Path | None,
) -> str:
    url = GEMINI_API_URL_TEMPLATE.format(model=model)
    body = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": image_b64,
                        }
                    },
                ],
            }
        ],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_output_tokens,
        },
    }
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }

    for attempt in range(1, retries + 1):
        append_request_log(
            request_log,
            {
                "event": "request_start",
                "page": page_num,
                "model": model,
                "attempt": attempt,
                "max_output_tokens": max_output_tokens,
                "temperature": temperature,
                "image_base64_chars": len(image_b64),
            },
        )
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=240) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            text = extract_gemini_text(payload)
            append_request_log(
                request_log,
                {
                    "event": "request_success",
                    "page": page_num,
                    "model": model,
                    "attempt": attempt,
                    "output_chars": len(text),
                },
            )
            return text
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            try:
                error_payload = json.loads(details)
            except json.JSONDecodeError:
                error_payload = {}
            if exc.code == 429:
                retry_seconds = parse_retry_seconds(error_payload)
                if is_daily_quota(error_payload):
                    append_request_log(
                        request_log,
                        {
                            "event": "quota_stop",
                            "page": page_num,
                            "model": model,
                            "attempt": attempt,
                            "http_status": exc.code,
                            "retry_seconds": retry_seconds,
                            "message": "daily quota exhausted",
                        },
                    )
                    raise GeminiQuotaError(
                        "Gemini 当日免费配额已用完；已保留缓存，之后可直接续跑。",
                        retry_seconds=retry_seconds,
                        daily_limit=True,
                    ) from exc
                if retry_seconds and attempt < retries:
                    wait = max(retry_seconds, 2)
                    append_request_log(
                        request_log,
                        {
                            "event": "rate_limit_retry",
                            "page": page_num,
                            "model": model,
                            "attempt": attempt,
                            "http_status": exc.code,
                            "retry_seconds": wait,
                        },
                    )
                    print(f"Gemini 请求过快，{wait} 秒后重试：HTTP 429", file=sys.stderr)
                    time.sleep(wait)
                    continue
            if attempt >= retries:
                append_request_log(
                    request_log,
                    {
                        "event": "request_failed",
                        "page": page_num,
                        "model": model,
                        "attempt": attempt,
                        "http_status": exc.code,
                        "error_preview": details[:500],
                    },
                )
                raise RuntimeError(f"Gemini HTTP error {exc.code}: {details}") from exc
            wait = min(90, 2**attempt)
            append_request_log(
                request_log,
                {
                    "event": "http_retry",
                    "page": page_num,
                    "model": model,
                    "attempt": attempt,
                    "http_status": exc.code,
                    "retry_seconds": wait,
                    "error_preview": details[:500],
                },
            )
            print(f"Gemini 请求失败，{wait} 秒后重试：HTTP {exc.code}", file=sys.stderr)
            time.sleep(wait)
        except (urllib.error.URLError, TimeoutError, RuntimeError) as exc:
            if attempt >= retries:
                append_request_log(
                    request_log,
                    {
                        "event": "request_failed",
                        "page": page_num,
                        "model": model,
                        "attempt": attempt,
                        "error_preview": str(exc)[:500],
                    },
                )
                raise
            wait = min(90, 2**attempt)
            append_request_log(
                request_log,
                {
                    "event": "request_retry",
                    "page": page_num,
                    "model": model,
                    "attempt": attempt,
                    "retry_seconds": wait,
                    "error_preview": str(exc)[:500],
                },
            )
            print(f"Gemini 请求失败，{wait} 秒后重试：{exc}", file=sys.stderr)
            time.sleep(wait)

    raise RuntimeError("Gemini retry state should be unreachable.")


def read_quality(markdown: str) -> tuple[str, str]:
    match = re.search(r"<!--\s*page_quality:\s*(高|中|低)\s*;\s*reason:\s*(.*?)\s*-->", markdown)
    if not match:
        return "未标记", "模型未按要求输出质量注释"
    return match.group(1), match.group(2).replace("|", "/")


def write_status(status_path: Path, rows: list[dict], pdf: Path, source_md5: str, model: str) -> None:
    lines = [
        "# Gemini视觉模型PDF转换状态",
        "",
        f"- 源PDF：`{pdf}`",
        f"- 源PDF_MD5：`{source_md5}`",
        f"- 模型：`{model}`",
        "",
        "| PDF Page | 状态 | 质量 | 说明 | 缓存文件 |",
        "|---:|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['page']:03d} | {row['status']} | {row['quality']} | {row['reason']} | `{row['cache']}` |"
        )
    status_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_output(out: Path, pdf: Path, source_md5: str, model: str, page_outputs: list[tuple[int, str]]) -> None:
    header = [
        f"# {pdf.stem}",
        "",
        f"- 源PDF：`{pdf}`",
        f"- 源PDF_MD5：`{source_md5}`",
        f"- 转换方式：PDF页面图片 + Google Gemini 视觉模型",
        f"- 模型：`{model}`",
        "",
    ]
    body = "\n\n".join(text for _, text in sorted(page_outputs))
    out.write_text("\n".join(header) + body + ("\n" if body else ""), encoding="utf-8")


def collect_cached_outputs(cache_dir: Path, pages: list[int]) -> list[tuple[int, str]]:
    outputs: list[tuple[int, str]] = []
    for page_num in pages:
        cache_file = cache_dir / f"page_{page_num:03d}.md"
        if cache_file.exists():
            text = cache_file.read_text(encoding="utf-8").strip()
            if text:
                outputs.append((page_num, text))
    return outputs


def write_output_from_cache(out: Path, pdf: Path, source_md5: str, model: str, cache_dir: Path, pages: list[int]) -> int:
    cached_outputs = collect_cached_outputs(cache_dir, pages)
    write_output(out, pdf, source_md5, model, cached_outputs)
    return len(cached_outputs)


def placeholder_markdown(page_num: int, reason: str) -> str:
    return (
        f"## PDF Page {page_num:03d}\n\n"
        f"[不确定: {reason}]\n\n"
        "<!-- page_quality: 低; reason: Gemini返回空文本或请求失败，需要单页返工 -->"
    )


def resolve_api_key() -> str:
    return GEMINI_API_KEY.strip() or os.environ.get("GEMINI_API_KEY", "").strip()


def convert_pdf(args: argparse.Namespace) -> int:
    pdf = Path(args.pdf).resolve()
    out = Path(args.out).resolve()
    status = Path(args.status).resolve() if args.status else out.with_name(out.stem + "_转换状态.md")
    request_log = Path(args.request_log).resolve() if args.request_log else status.with_name(status.stem + "_请求记录.jsonl")
    workdir = Path(args.workdir).resolve()
    image_dir = workdir / "images" / pdf.stem
    cache_dir = workdir / "pages" / pdf.stem
    cache_dir.mkdir(parents=True, exist_ok=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    status.parent.mkdir(parents=True, exist_ok=True)
    request_log.parent.mkdir(parents=True, exist_ok=True)

    if not pdf.exists():
        raise SystemExit(f"找不到 PDF：{pdf}")

    total_pages = pdf_page_count(pdf)
    pages = parse_pages(args.pages, total_pages)
    output_pages = list(range(1, total_pages + 1))
    source_md5 = md5_file(pdf)
    api_key = resolve_api_key()

    if not args.dry_run and not api_key:
        raise SystemExit("请先在脚本顶部填写 GEMINI_API_KEY，或设置系统环境变量 GEMINI_API_KEY。")

    rows: list[dict] = []
    page_outputs: list[tuple[int, str]] = []

    append_request_log(
        request_log,
        {
            "event": "run_start",
            "pdf": str(pdf),
            "source_md5": source_md5,
            "model": args.model,
            "pages": pages,
            "dry_run": args.dry_run,
            "overwrite": args.overwrite,
        },
    )

    for page_num in pages:
        print(f"Processing PDF Page {page_num:03d}/{total_pages}...")
        rendered = render_page(pdf, page_num, image_dir, args.dpi)
        jpg = compress_image(rendered, args.max_side, args.jpeg_quality)
        cache_file = cache_dir / f"page_{page_num:03d}.md"
        append_request_log(
            request_log,
            {
                "event": "page_prepared",
                "page": page_num,
                "rendered_image": str(rendered),
                "request_image": str(jpg),
                "cache": str(cache_file),
            },
        )

        if args.dry_run:
            rows.append(
                {
                    "page": page_num,
                    "status": "dry-run",
                    "quality": "未识别",
                    "reason": f"已渲染为图片：{jpg}",
                    "cache": cache_file,
                }
            )
            append_request_log(
                request_log,
                {
                    "event": "dry_run_page_done",
                    "page": page_num,
                    "request_image": str(jpg),
                    "cache": str(cache_file),
                },
            )
            continue

        if cache_file.exists() and not args.overwrite:
            markdown = cache_file.read_text(encoding="utf-8")
            status_text = "cached"
            append_request_log(
                request_log,
                {
                    "event": "cache_hit",
                    "page": page_num,
                    "cache": str(cache_file),
                    "output_chars": len(markdown),
                },
            )
        else:
            try:
                markdown = call_gemini(
                    api_key=api_key,
                    model=args.model,
                    prompt=page_prompt(page_num, total_pages),
                    image_b64=image_base64(jpg),
                    max_output_tokens=args.max_output_tokens,
                    temperature=args.temperature,
                    retries=args.retries,
                    page_num=page_num,
                    request_log=request_log,
                )
            except GeminiQuotaError as exc:
                rows.append(
                    {
                        "page": page_num,
                        "status": "quota-stopped",
                        "quality": "未完成",
                        "reason": str(exc),
                        "cache": cache_file,
                    }
                )
                write_status(status, rows, pdf, source_md5, args.model)
                saved_pages = write_output_from_cache(out, pdf, source_md5, args.model, cache_dir, output_pages)
                append_request_log(
                    request_log,
                    {
                        "event": "run_stopped_quota",
                        "page": page_num,
                        "retry_seconds": exc.retry_seconds,
                        "daily_limit": exc.daily_limit,
                        "partial_output": str(out),
                        "status": str(status),
                        "saved_pages": saved_pages,
                    },
                )
                print(str(exc))
                print(f"Partial Markdown written: {out}")
                return 2
            except GeminiEmptyResponseError as exc:
                markdown = placeholder_markdown(page_num, str(exc))
                cache_file.write_text(markdown.rstrip() + "\n", encoding="utf-8")
                status_text = "placeholder"
                append_request_log(
                    request_log,
                    {
                        "event": "page_placeholder_written",
                        "page": page_num,
                        "cache": str(cache_file),
                        "reason": str(exc),
                    },
                )
            except Exception as exc:
                rows.append(
                    {
                        "page": page_num,
                        "status": "error-stopped",
                        "quality": "未完成",
                        "reason": str(exc).replace("|", "/")[:300],
                        "cache": cache_file,
                    }
                )
                write_status(status, rows, pdf, source_md5, args.model)
                saved_pages = write_output_from_cache(out, pdf, source_md5, args.model, cache_dir, output_pages)
                append_request_log(
                    request_log,
                    {
                        "event": "run_stopped_error",
                        "page": page_num,
                        "error_preview": str(exc)[:500],
                        "partial_output": str(out),
                        "status": str(status),
                        "saved_pages": saved_pages,
                    },
                )
                print(f"转换在 PDF Page {page_num:03d} 停止，已保存已有进度：{exc}", file=sys.stderr)
                return 1
            cache_file.write_text(markdown.rstrip() + "\n", encoding="utf-8")
            status_text = "done"
            append_request_log(
                request_log,
                {
                    "event": "cache_written",
                    "page": page_num,
                    "cache": str(cache_file),
                    "output_chars": len(markdown),
                },
            )

        quality, reason = read_quality(markdown)
        rows.append(
            {
                "page": page_num,
                "status": status_text,
                "quality": quality,
                "reason": reason,
                "cache": cache_file,
            }
        )
        page_outputs.append((page_num, markdown.rstrip()))
        write_status(status, rows, pdf, source_md5, args.model)
        saved_pages = write_output_from_cache(out, pdf, source_md5, args.model, cache_dir, output_pages)
        append_request_log(
            request_log,
            {
                "event": "output_written",
                "page": page_num,
                "output": str(out),
                "saved_pages": saved_pages,
            },
        )
        if args.sleep_between_pages > 0:
            time.sleep(args.sleep_between_pages)

    write_status(status, rows, pdf, source_md5, args.model)
    saved_pages = write_output_from_cache(out, pdf, source_md5, args.model, cache_dir, output_pages) if not args.dry_run else 0
    append_request_log(
        request_log,
        {
            "event": "run_complete",
            "output": str(out),
            "status": str(status),
            "request_log": str(request_log),
            "pages_completed": saved_pages,
        },
    )
    print(f"Status written: {status}")
    if not args.dry_run:
        print(f"Markdown written: {out}")
    return 0


def write_batch_status(rows: list[dict]) -> None:
    BATCH_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = BATCH_OUTPUT_DIR / "批量转换状态.md"
    lines = [
        "# Gemini批量返工转换状态",
        "",
        f"- 输出目录：`{BATCH_OUTPUT_DIR}`",
        f"- 工作缓存：`{BATCH_WORKDIR}`",
        f"- 默认模型：`{BATCH_MODEL}`",
        "",
        "| 期次 | PDF文件 | 状态 | Markdown | 状态文件 | 请求记录 |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['label']} | `{row['pdf']}` | {row['status']} | `{row['out']}` | `{row['status_file']}` | `{row['request_log']}` |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_batch(args: argparse.Namespace) -> int:
    rows: list[dict] = []
    final_code = 0
    for job in BATCH_JOBS:
        print(f"\n=== {job['label']} ===")
        job_args = argparse.Namespace(
            pdf=str(job["pdf"]),
            out=str(job["out"]),
            status=str(job["status"]),
            request_log=str(job["request_log"]),
            pages=args.pages,
            model=args.model,
            dpi=args.dpi,
            max_side=args.max_side,
            jpeg_quality=args.jpeg_quality,
            max_output_tokens=args.max_output_tokens,
            temperature=args.temperature,
            retries=args.retries,
            sleep_between_pages=args.sleep_between_pages,
            workdir=str(BATCH_WORKDIR),
            dry_run=args.dry_run,
            overwrite=args.overwrite,
        )
        code = convert_pdf(job_args)
        status_text = "dry-run-completed" if args.dry_run and code == 0 else ("completed" if code == 0 else f"stopped({code})")
        rows.append(
            {
                "label": job["label"],
                "pdf": job["pdf"],
                "status": status_text,
                "out": job["out"],
                "status_file": job["status"],
                "request_log": job["request_log"],
            }
        )
        write_batch_status(rows)
        if code != 0:
            final_code = code
            break
    return final_code


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert PDF pages to Markdown with Gemini vision.")
    parser.add_argument("--pdf", help="输入 PDF 路径。不提供时自动执行脚本内批量返工清单。")
    parser.add_argument("--out", help="输出 Markdown 路径。不提供时自动执行脚本内批量返工清单。")
    parser.add_argument("--status", help="转换状态 Markdown 路径。")
    parser.add_argument("--pages", help="页码范围，例如：1-5,8,10-12")
    parser.add_argument("--model", default=BATCH_MODEL, help=f"Gemini 模型名。默认：{BATCH_MODEL}")
    parser.add_argument("--dpi", type=int, default=220, help="PDF 渲染 DPI。默认：220")
    parser.add_argument("--max-side", type=int, default=2200, help="图片最长边压缩到此像素。默认：2200")
    parser.add_argument("--jpeg-quality", type=int, default=88, help="JPEG 质量。默认：88")
    parser.add_argument("--max-output-tokens", type=int, default=6000)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--retries", type=int, default=4)
    parser.add_argument("--sleep-between-pages", type=float, default=0.0, help="每页成功后等待秒数，用于减轻速率限制。")
    parser.add_argument("--request-log", help="逐次请求日志 JSONL 路径。默认在状态文件旁生成。")
    parser.add_argument("--workdir", default="tmp/gemini_pdf_to_markdown")
    parser.add_argument("--batch", action="store_true", help="执行脚本内批量返工清单。")
    parser.add_argument("--dry-run", action="store_true", help="只渲染页面并写状态，不调用 Gemini。")
    parser.add_argument("--overwrite", action="store_true", help="即使已有缓存，也重新调用 Gemini。")
    args = parser.parse_args()

    if args.batch or not args.pdf:
        return run_batch(args)

    if not args.out:
        raise SystemExit("单文件模式需要提供 --out；不提供 --pdf 时会自动执行批量返工清单。")
    return convert_pdf(args)


if __name__ == "__main__":
    raise SystemExit(main())
