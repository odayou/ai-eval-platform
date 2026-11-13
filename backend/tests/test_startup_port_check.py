"""后端启动可观测性：健康检查暴露服务身份与端口、启动前端口自检。"""

import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import run as backend_run


def test_health_reports_service_and_port(client, monkeypatch):
    monkeypatch.setenv("APP_PORT", "8123")

    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()

    assert body["status"] == "ok"
    assert body["service"] == "ai-eval-platform"
    assert body["port"] == 8123
    assert body["proxy_target"] == "http://127.0.0.1:8123"
    assert body["pid"] > 0


def test_current_port_reads_env(monkeypatch):
    monkeypatch.setenv("APP_PORT", "8234")
    assert backend_run.current_port() == 8234

    monkeypatch.delenv("APP_PORT")
    assert backend_run.current_port() == 8001


def test_probe_existing_service_returns_none_for_free_port():
    # 找一个空闲端口，探测应返回 None
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        free_port = probe.getsockname()[1]

    assert backend_run.probe_existing_service(free_port) is None
    assert backend_run.port_is_listening(free_port) is False


def test_probe_existing_service_detects_other_program():
    """模拟第三方程序占用端口：健康检查响应里没有 service 标识。"""

    class OtherHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b'{"error":"unauthorized"}')

        def log_message(self, *_args):
            pass

    server = HTTPServer(("127.0.0.1", 0), OtherHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        assert backend_run.port_is_listening(port) is True
        # 第三方服务返回 401，opener 会抛错，探测结果视为 None（但仍通过 TCP 检测发现占用）
        assert backend_run.probe_existing_service(port) is None
    finally:
        server.shutdown()
        server.server_close()


def test_health_url_uses_given_port():
    assert backend_run.health_url(8001) == "http://127.0.0.1:8001/api/health"
