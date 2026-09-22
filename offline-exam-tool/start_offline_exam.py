#!/usr/bin/env python3
"""Serve the offline exam and persist answer history inside the project."""

from __future__ import annotations

import functools
import http.server
import json
import re
import socketserver
import threading
import time
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


TOOL_DIR = Path(__file__).resolve().parent
ROOT = TOOL_DIR.parent
HISTORY_DIR = TOOL_DIR / "history"
RECORDS_DIR = HISTORY_DIR / "records"
IMPORTS_DIR = HISTORY_DIR / "imports"
LEGACY_HISTORY_FILE = HISTORY_DIR / "answer-history.json"
CONFIG_DIR = TOOL_DIR / "config"
GEMINI_CONFIG_FILE = CONFIG_DIR / "gemini.json"
GEMINI_MODEL = "gemini-3.6-flash"
GEMINI_MAX_OUTPUT_TOKENS = 4096
HOST = "127.0.0.1"
PORT = 8765
URL = f"http://localhost:{PORT}/"
MAX_BODY_BYTES = 20 * 1024 * 1024
HISTORY_LOCK = threading.Lock()
CONFIG_LOCK = threading.Lock()

AI_SYSTEM_PROMPT = """你是一名专门辅导 JLPT N1 真题的日语教师，目标是帮助用户通过 N1。
请严格围绕当前题目和用户本轮问题作答，专业、准确、简短，不要主动展开无关知识。
优先直接回答用户最关心的疑点，并指出本题真正考查的词义、读音、搭配、语法接续、语气、篇章逻辑或听力线索。
涉及错误选项时，要具体说明错在哪里；涉及语法时说明接续与语义限制；涉及近义词时说明不能互换的关键差别。
如果存在值得继续学习但本轮不必展开的内容，只在结尾用一句“可继续追问：……”提示，等用户追问后再详细说明。
不要平铺所有知识点，不要重复题干，不要虚构原文中没有的信息。若题目资料不足，请明确指出缺少什么。
默认用简体中文回答；日语词句保留原文，并在必要时标注假名。"""


def safe_filename_part(value: object, fallback: str) -> str:
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(value or "").strip())
    text = re.sub(r"\s+", "_", text).strip(" ._")
    return text or fallback


def local_submission_stamp(record: dict) -> str:
    raw = str(record.get("submittedAt") or "")
    try:
        instant = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        offset = int(record.get("timezoneOffsetMinutes") or 0)
        local = instant - timedelta(minutes=offset)
        milliseconds = local.microsecond // 1000
        return local.strftime("%Y-%m-%d_%H-%M-%S") + f"-{milliseconds:03d}"
    except (ValueError, TypeError, OverflowError):
        return safe_filename_part(raw, "unknown-time")


def record_filename(record: dict) -> str:
    year = safe_filename_part(record.get("year"), "unknown-period")
    category = safe_filename_part(record.get("category"), "unknown-subject")
    return f"{year}+{category}+{local_submission_stamp(record)}.json"


def write_record(record: dict) -> Path:
    if not isinstance(record, dict) or not record.get("id"):
        raise ValueError("record must contain an id")
    RECORDS_DIR.mkdir(parents=True, exist_ok=True)
    destination = RECORDS_DIR / record_filename(record)
    if destination.exists():
        try:
            existing = json.loads(destination.read_text(encoding="utf-8")).get("record", {})
        except (json.JSONDecodeError, OSError, AttributeError):
            existing = {}
        if str(existing.get("id")) != str(record["id"]):
            unique = safe_filename_part(str(record["id"])[-8:], "duplicate")
            destination = destination.with_name(f"{destination.stem}+{unique}.json")
    payload = {"version": 2, "record": record}
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(destination)
    return destination


def read_history() -> list[dict]:
    records: dict[str, dict] = {}
    for path in sorted(RECORDS_DIR.glob("*.json")) if RECORDS_DIR.exists() else []:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            record = payload.get("record") if isinstance(payload, dict) else None
            if isinstance(record, dict) and record.get("id"):
                records[str(record["id"])] = record
        except (json.JSONDecodeError, OSError):
            continue
    return sorted(records.values(), key=lambda item: str(item.get("submittedAt", "")), reverse=True)


def save_records(incoming: list[dict]) -> list[dict]:
    combined = {
        str(record["id"]): record
        for record in [*read_history(), *incoming]
        if isinstance(record, dict) and record.get("id")
    }
    for record in combined.values():
        write_record(record)
    return sorted(combined.values(), key=lambda item: str(item.get("submittedAt", "")), reverse=True)


def migrate_legacy_history() -> int:
    if not LEGACY_HISTORY_FILE.is_file():
        return 0
    try:
        payload = json.loads(LEGACY_HISTORY_FILE.read_text(encoding="utf-8"))
        incoming = payload.get("history", []) if isinstance(payload, dict) else []
        valid = [record for record in incoming if isinstance(record, dict) and record.get("id")]
        save_records(valid)
        IMPORTS_DIR.mkdir(parents=True, exist_ok=True)
        archive = IMPORTS_DIR / "answer-history-legacy.json"
        if archive.exists():
            archive = IMPORTS_DIR / f"answer-history-legacy-{datetime.now():%Y-%m-%d_%H-%M-%S}.json"
        LEGACY_HISTORY_FILE.replace(archive)
        return len(valid)
    except (json.JSONDecodeError, OSError):
        return 0


def read_gemini_config() -> dict:
    try:
        payload = json.loads(GEMINI_CONFIG_FILE.read_text(encoding="utf-8"))
        key = str(payload.get("apiKey") or "").strip() if isinstance(payload, dict) else ""
        return {"apiKey": key, "model": GEMINI_MODEL}
    except (OSError, json.JSONDecodeError, AttributeError):
        return {"apiKey": "", "model": GEMINI_MODEL}


def save_gemini_key(api_key: str) -> None:
    key = str(api_key or "").strip()
    if not key or len(key) > 500 or not re.fullmatch(r"[A-Za-z0-9._-]+", key):
        raise ValueError("API Key 格式不正确")
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    temporary = GEMINI_CONFIG_FILE.with_suffix(".json.tmp")
    temporary.write_text(json.dumps({"version": 1, "model": GEMINI_MODEL, "apiKey": key}, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(GEMINI_CONFIG_FILE)


def gemini_chat_stream(payload: dict):
    config = read_gemini_config()
    api_key = config["apiKey"]
    if not api_key:
        raise ValueError("尚未配置 Gemini API Key")
    context = payload.get("context") if isinstance(payload, dict) else None
    messages = payload.get("messages") if isinstance(payload, dict) else None
    if not isinstance(context, dict) or not isinstance(messages, list) or not messages:
        raise ValueError("对话上下文格式不正确")
    if len(messages) > 30:
        raise ValueError("单题对话轮次过多，请刷新历史答卷后重新开始")

    context_text = "当前真题上下文（只作为答题依据）：\n" + json.dumps(context, ensure_ascii=False, indent=2)
    normalized_messages = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = "model" if message.get("role") == "model" else "user"
        text = str(message.get("text") or "").strip()
        if text:
            if normalized_messages and normalized_messages[-1]["role"] == role:
                normalized_messages[-1]["text"] += "\n\n" + text[:12000]
            else:
                normalized_messages.append({"role": role, "text": text[:12000]})
    if not normalized_messages or normalized_messages[0]["role"] != "user":
        raise ValueError("对话必须以用户问题开始")
    normalized_messages[0]["text"] = context_text + "\n\n用户问题：\n" + normalized_messages[0]["text"]
    contents = [
        {"role": message["role"], "parts": [{"text": message["text"]}]}
        for message in normalized_messages
    ]
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:streamGenerateContent?alt=sse&key={api_key}"
    continuation_count = 0
    yielded_text = False
    yield {"type": "start", "model": GEMINI_MODEL}
    while True:
        request_payload = {
            "systemInstruction": {"parts": [{"text": AI_SYSTEM_PROMPT}]},
            "contents": contents,
            "generationConfig": {"maxOutputTokens": GEMINI_MAX_OUTPUT_TOKENS},
        }
        request = Request(
            endpoint,
            data=json.dumps(request_payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=90) as response:
                segment_parts: list[str] = []
                finish_reason = ""
                for raw_line in response:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if not data or data == "[DONE]":
                        continue
                    result = json.loads(data)
                    candidates = result.get("candidates", []) if isinstance(result, dict) else []
                    candidate = candidates[0] if candidates and isinstance(candidates[0], dict) else {}
                    texts = [
                        str(part["text"])
                        for part in candidate.get("content", {}).get("parts", [])
                        if isinstance(part, dict) and part.get("text") and not part.get("thought")
                    ]
                    if texts:
                        delta = "".join(texts)
                        segment_parts.append(delta)
                        yielded_text = True
                        yield {"type": "delta", "text": delta}
                    if candidate.get("finishReason"):
                        finish_reason = str(candidate["finishReason"])
        except HTTPError as error:
            try:
                detail = json.loads(error.read().decode("utf-8")).get("error", {}).get("message", "")
            except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
                detail = ""
            raise ValueError(f"Gemini 请求失败（HTTP {error.code}）{f'：{detail}' if detail else ''}") from error
        except (URLError, TimeoutError) as error:
            raise ValueError(f"无法连接 Gemini API：{getattr(error, 'reason', error)}") from error
        answer_part = "".join(segment_parts).strip()
        if not answer_part and not yielded_text:
            raise ValueError("Gemini 未返回文字回答")
        if finish_reason != "MAX_TOKENS":
            yield {"type": "done", "finishReason": finish_reason or "STOP", "continuations": continuation_count}
            break

        continuation_count += 1
        yield {"type": "continuation", "count": continuation_count}
        contents.extend([
            {"role": "model", "parts": [{"text": answer_part}]},
            {"role": "user", "parts": [{"text": "请从刚才被截断的位置直接继续，补完回答；不要重复已经输出的内容。"}]},
        ])


class OfflineExamHandler(http.server.SimpleHTTPRequestHandler):
    def send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_ai_stream(self, payload: dict) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        try:
            for event in gemini_chat_stream(payload):
                self.wfile.write(json.dumps(event, ensure_ascii=False).encode("utf-8") + b"\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            # The browser's square stop button aborts fetch; closing this
            # handler also closes the active upstream Gemini response.
            return
        except (UnicodeDecodeError, json.JSONDecodeError, OSError, ValueError) as error:
            try:
                self.wfile.write(json.dumps({"type": "error", "error": str(error)}, ensure_ascii=False).encode("utf-8") + b"\n")
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass

    def do_GET(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path
        if path == "/api/history":
            with HISTORY_LOCK:
                history = read_history()
            self.send_json(200, {"version": 2, "history": history})
            return
        if path == "/api/ai/config":
            with CONFIG_LOCK:
                configured = bool(read_gemini_config()["apiKey"])
            self.send_json(200, {"configured": configured, "model": GEMINI_MODEL})
            return
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path
        if path not in ("/api/history", "/api/ai/config", "/api/ai/chat"):
            self.send_json(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 0 or length > MAX_BODY_BYTES:
                self.send_json(413, {"error": "payload too large"})
                return
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if path == "/api/ai/config":
                with CONFIG_LOCK:
                    save_gemini_key(payload.get("apiKey") if isinstance(payload, dict) else "")
                self.send_json(200, {"configured": True, "model": GEMINI_MODEL})
                return
            if path == "/api/ai/chat":
                self.send_ai_stream(payload)
                return
            incoming = payload.get("history") if isinstance(payload, dict) else None
            if not isinstance(incoming, list):
                self.send_json(400, {"error": "history must be an array"})
                return
            with HISTORY_LOCK:
                history = save_records(incoming)
            self.send_json(200, {"version": 2, "history": history, "saved": len(history)})
        except (UnicodeDecodeError, json.JSONDecodeError, OSError, ValueError) as error:
            self.send_json(400, {"error": str(error)})


class ReusableThreadingServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    # On Windows, SO_REUSEADDR can let multiple processes listen on the same
    # port. Keep the bind exclusive; main() already retries while a recently
    # closed socket is being released and reuses a healthy running instance.
    allow_reuse_address = False
    allow_reuse_port = False
    daemon_threads = True


def existing_exam_server() -> bool:
    """Return True only when the port belongs to this offline exam server."""
    try:
        with urlopen(f"http://{HOST}:{PORT}/api/history", timeout=0.6) as response:
            if response.status != 200:
                return False
            payload = json.loads(response.read().decode("utf-8"))
            return isinstance(payload, dict) and isinstance(payload.get("history"), list)
    except (OSError, URLError, UnicodeDecodeError, json.JSONDecodeError):
        return False


def main() -> None:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    migrated = migrate_legacy_history()
    handler = functools.partial(OfflineExamHandler, directory=ROOT)
    if existing_exam_server():
        print(f"N1 离线题库已经在运行，正在打开：{URL}")
        webbrowser.open(URL)
        try:
            input("已有后台服务正在提供题库。按 Enter 关闭此提示窗口……")
        except EOFError:
            pass
        return

    server = None
    last_error = None
    # Windows may retain the listening port briefly after its console closes.
    # Retry for a few seconds instead of incorrectly asking the user to close it again.
    for attempt in range(10):
        try:
            server = ReusableThreadingServer((HOST, PORT), handler)
            break
        except OSError as error:
            last_error = error
            if existing_exam_server():
                print(f"N1 离线题库已经在运行，正在打开：{URL}")
                webbrowser.open(URL)
                try:
                    input("已有后台服务正在提供题库。按 Enter 关闭此提示窗口……")
                except EOFError:
                    pass
                return
            if attempt < 9:
                if attempt == 0:
                    print(f"端口 {PORT} 正在释放，正在自动重试……")
                time.sleep(0.5)
    if server is None:
        detail = f"（系统错误 {getattr(last_error, 'winerror', '') or getattr(last_error, 'errno', '')}）"
        print(f"无法启动：端口 {PORT} 被其他程序占用 {detail}。")
        print("请稍后重试；如果仍然出现此提示，再检查占用该端口的程序。")
        raise SystemExit(1) from last_error
    with server:
        print(f"N1 离线题库已启动：{URL}")
        print(f"答题历史目录：{RECORDS_DIR}")
        if migrated:
            print(f"已迁移旧历史记录：{migrated} 条")
        print("关闭此窗口即可停止服务；普通答题无需联网，AI 题目对话需要连接 Gemini API。")
        webbrowser.open(URL)
        server.serve_forever()


if __name__ == "__main__":
    main()
