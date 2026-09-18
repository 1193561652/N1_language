#!/usr/bin/env python
"""
Convert a PDF into AI-readable Markdown by rendering each page and sending the
page image to a vision-capable OpenAI Responses API model.

This script intentionally uses only the Python standard library plus Pillow,
so it does not require the OpenAI Python SDK.
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


API_URL = "https://api.openai.com/v1/responses"


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
            start = int(start_s)
            end = int(end_s)
            pages.update(range(start, end + 1))
        else:
            pages.add(int(part))

    return [p for p in sorted(pages) if 1 <= p <= total_pages]


def require_tool(name: str) -> str:
    deps_dir = Path(sys.executable).resolve().parent.parent
    native_poppler = deps_dir / "native" / "poppler" / "Library" / "bin" / f"{name}.exe"
    if native_poppler.exists():
        return str(native_poppler)

    path = shutil.which(name)
    if path:
        return path

    for suffix in ("", ".cmd", ".exe"):
        candidate = deps_dir / "bin" / "override" / f"{name}{suffix}"
        if candidate.exists():
            return str(candidate)

    raise SystemExit(f"Missing required tool: {name}")


def run_command(args: list[str]) -> str:
    proc = subprocess.run(args, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return proc.stdout.strip()


def pdf_page_count(pdf: Path) -> int:
    pdfinfo = require_tool("pdfinfo")
    output = run_command([pdfinfo, str(pdf)])
    match = re.search(r"^Pages:\s+(\d+)\s*$", output, re.MULTILINE)
    if not match:
        raise SystemExit("Could not determine PDF page count from pdfinfo output.")
    return int(match.group(1))


def md5_file(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def render_page(pdf: Path, page_num: int, image_dir: Path, dpi: int) -> Path:
    pdftoppm = require_tool("pdftoppm")
    image_dir.mkdir(parents=True, exist_ok=True)
    prefix = image_dir / f"page_{page_num:03d}"
    expected = image_dir / f"page_{page_num:03d}-1.png"
    if expected.exists():
        return expected
    run_command(
        [
            pdftoppm,
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
    if not expected.exists():
        matches = sorted(image_dir.glob(f"page_{page_num:03d}-*.png"))
        if matches:
            return matches[0]
        raise SystemExit(f"Rendered image was not created for page {page_num}.")
    return expected


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


def image_data_url(path: Path) -> str:
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/jpeg;base64,{data}"


def page_prompt(page_num: int, total_pages: int) -> str:
    return f"""请读取这张 JLPT N1 真题 PDF 页面图像，并转换为 AI 易读 Markdown。

硬性要求：
1. 忠实提取原文，不要改写题干、选项、文章或听力内容。
2. 页面标题必须写为：## PDF Page {page_num:03d}
3. 如果页面中有 問題1、問題2、問題3 等题组，请用三级标题标出，例如：### 問題1
4. 每道题尽量保留题号、题干、选项结构。选项编号不要丢失。
5. 对不确定或看不清的文字，用 [不确定: 原因] 标记，不要猜。
6. 不要添加原文没有的解释、翻译或答案。
7. 页面末尾必须添加一行 HTML 注释，格式严格为：
<!-- page_quality: 高/中/低; reason: 简短中文原因 -->

当前页：{page_num}/{total_pages}
请只输出这一页的 Markdown。"""


def extract_output_text(response: dict) -> str:
    if isinstance(response.get("output_text"), str):
        return response["output_text"]

    chunks: list[str] = []
    for item in response.get("output", []) or []:
        for content in item.get("content", []) or []:
            if content.get("type") in {"output_text", "text"} and isinstance(content.get("text"), str):
                chunks.append(content["text"])
    return "\n".join(chunks).strip()


def call_openai(api_key: str, model: str, prompt: str, image_url: str, max_output_tokens: int, retries: int) -> str:
    body = {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": image_url, "detail": "high"},
                ],
            }
        ],
        "max_output_tokens": max_output_tokens,
    }
    data = json.dumps(body).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    for attempt in range(1, retries + 1):
        req = urllib.request.Request(API_URL, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            text = extract_output_text(payload)
            if text:
                return text
            raise RuntimeError("The API response did not contain output text.")
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, RuntimeError) as exc:
            if attempt >= retries:
                raise
            wait = min(60, 2**attempt)
            print(f"API call failed on attempt {attempt}: {exc}. Retrying in {wait}s...", file=sys.stderr)
            time.sleep(wait)

    raise RuntimeError("Unreachable retry state.")


def read_quality(markdown: str) -> tuple[str, str]:
    match = re.search(r"<!--\s*page_quality:\s*(高|中|低)\s*;\s*reason:\s*(.*?)\s*-->", markdown)
    if not match:
        return "未标记", "模型未按要求输出质量注释"
    return match.group(1), match.group(2)


def write_status(status_path: Path, rows: list[dict], pdf: Path, source_md5: str, model: str) -> None:
    lines = [
        "# 视觉模型PDF转换状态",
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert PDF pages to Markdown with OpenAI vision.")
    parser.add_argument("--pdf", required=True, help="Input PDF path.")
    parser.add_argument("--out", required=True, help="Output Markdown path.")
    parser.add_argument("--status", help="Status Markdown path.")
    parser.add_argument("--pages", help="Page range, for example: 1-5,8,10-12")
    parser.add_argument("--model", default="gpt-5", help="OpenAI model name. Default: gpt-5")
    parser.add_argument("--dpi", type=int, default=220, help="PDF render DPI. Default: 220")
    parser.add_argument("--max-side", type=int, default=2200, help="Max JPEG side length. Default: 2200")
    parser.add_argument("--jpeg-quality", type=int, default=88, help="JPEG quality. Default: 88")
    parser.add_argument("--max-output-tokens", type=int, default=6000)
    parser.add_argument("--retries", type=int, default=4)
    parser.add_argument("--workdir", default="tmp/vision_pdf_to_markdown")
    parser.add_argument("--dry-run", action="store_true", help="Render pages and write a status file, but do not call API.")
    parser.add_argument("--overwrite", action="store_true", help="Re-run pages even when cached Markdown exists.")
    args = parser.parse_args()

    pdf = Path(args.pdf).resolve()
    out = Path(args.out).resolve()
    status = Path(args.status).resolve() if args.status else out.with_name(out.stem + "_转换状态.md")
    workdir = Path(args.workdir).resolve()
    image_dir = workdir / "images" / pdf.stem
    cache_dir = workdir / "pages" / pdf.stem
    cache_dir.mkdir(parents=True, exist_ok=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    status.parent.mkdir(parents=True, exist_ok=True)

    if not pdf.exists():
        raise SystemExit(f"PDF not found: {pdf}")

    total_pages = pdf_page_count(pdf)
    pages = parse_pages(args.pages, total_pages)
    source_md5 = md5_file(pdf)
    api_key = os.environ.get("OPENAI_API_KEY", "")

    if not args.dry_run and not api_key:
        raise SystemExit("OPENAI_API_KEY is not set. Set it first, or run with --dry-run.")

    rows: list[dict] = []
    page_outputs: list[tuple[int, str]] = []

    for page_num in pages:
        print(f"Processing PDF Page {page_num:03d}/{total_pages}...")
        rendered = render_page(pdf, page_num, image_dir, args.dpi)
        jpg = compress_image(rendered, args.max_side, args.jpeg_quality)
        cache_file = cache_dir / f"page_{page_num:03d}.md"

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
            continue

        if cache_file.exists() and not args.overwrite:
            markdown = cache_file.read_text(encoding="utf-8")
            status_text = "cached"
        else:
            markdown = call_openai(
                api_key=api_key,
                model=args.model,
                prompt=page_prompt(page_num, total_pages),
                image_url=image_data_url(jpg),
                max_output_tokens=args.max_output_tokens,
                retries=args.retries,
            )
            cache_file.write_text(markdown.rstrip() + "\n", encoding="utf-8")
            status_text = "done"

        quality, reason = read_quality(markdown)
        rows.append(
            {
                "page": page_num,
                "status": status_text,
                "quality": quality,
                "reason": reason.replace("|", "/"),
                "cache": cache_file,
            }
        )
        page_outputs.append((page_num, markdown.rstrip()))
        write_status(status, rows, pdf, source_md5, args.model)

    if not args.dry_run:
        header = [
            f"# {pdf.stem}",
            "",
            f"- 源PDF：`{pdf}`",
            f"- 源PDF_MD5：`{source_md5}`",
            f"- 转换方式：PDF页面图片 + OpenAI Responses API 视觉模型",
            f"- 模型：`{args.model}`",
            "",
        ]
        body = "\n\n".join(text for _, text in sorted(page_outputs))
        out.write_text("\n".join(header) + body + "\n", encoding="utf-8")

    write_status(status, rows, pdf, source_md5, args.model)
    print(f"Status written: {status}")
    if not args.dry_run:
        print(f"Markdown written: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
