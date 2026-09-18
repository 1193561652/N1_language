#!/usr/bin/env python3
"""Start the offline exam app on localhost and open it in the default browser."""

from __future__ import annotations

import functools
import http.server
import socketserver
import webbrowser
from pathlib import Path


ROOT = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORT = 8765
URL = f"http://localhost:{PORT}/offline-exam/"


class ReusableThreadingServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def main() -> None:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT)
    with ReusableThreadingServer((HOST, PORT), handler) as server:
        print(f"N1 离线题库已启动：{URL}")
        print("关闭此窗口即可停止服务；使用期间不需要互联网连接。")
        webbrowser.open(URL)
        server.serve_forever()


if __name__ == "__main__":
    main()
