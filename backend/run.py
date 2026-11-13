"""后端启动入口：端口来自 APP_PORT（默认 8001），启动前检查端口占用。

自检目的：Windows 上 0.0.0.0:port 与 127.0.0.1:port 可以被两个进程同时绑定，
uvicorn 绑 0.0.0.0 看似启动成功，但 Vite 代理访问 127.0.0.1 时会被另一个
程序接走（表现为莫名其妙的 401/404）。这里在启动前主动探测并明确报错。
"""

import os
import socket
import sys
import urllib.request

import uvicorn

DEFAULT_PORT = 8001
SERVICE_TAG = "ai-eval-platform"


def current_port() -> int:
    return int(os.getenv("APP_PORT", str(DEFAULT_PORT)))


def health_url(port: int) -> str:
    return f"http://127.0.0.1:{port}/api/health"


def probe_existing_service(port: int) -> str | None:
    """探测 127.0.0.1:port 上已有服务的健康响应；没有服务则返回 None。

    绕过系统代理，避免 HTTP_PROXY 把本机请求转发到别处造成误判。
    """

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(health_url(port), timeout=1) as response:
            return response.read(1024).decode("utf-8", "ignore")
    except Exception:
        return None


def port_is_listening(port: int) -> bool:
    """端口上是否已有 TCP 监听者（不一定是 HTTP 服务）。"""

    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def main() -> None:
    port = current_port()
    host = os.getenv("APP_HOST", "0.0.0.0")

    print("================ AI Eval Platform 后端 ================", flush=True)
    print(f"  PID        : {os.getpid()}", flush=True)
    print(f"  监听地址   : {host}:{port}  (APP_PORT={port})", flush=True)
    print(f"  健康检查   : {health_url(port)}", flush=True)
    print(f"  接口文档   : http://127.0.0.1:{port}/docs", flush=True)
    print(f"  前端代理   : http://127.0.0.1:5173/api -> http://127.0.0.1:{port}", flush=True)
    print("=======================================================", flush=True)

    # 已有本服务实例（重复启动）
    existing = probe_existing_service(port)
    if existing and SERVICE_TAG in existing:
        print(f"[错误] 端口 {port} 上已经有本平台后端在运行，请勿重复启动。", flush=True)
        print("       请先关闭旧的后端窗口，或修改 APP_PORT 换一个端口。", flush=True)
        sys.exit(1)

    if existing or port_is_listening(port):
        if existing:
            print(f"[错误] 127.0.0.1:{port} 已被其他程序占用，Vite 代理会打到那个程序上。", flush=True)
            print(f"       该端口当前响应: {existing[:200]}", flush=True)
        else:
            print(f"[错误] 127.0.0.1:{port} 已被其他程序占用（TCP 端口有服务但不是本平台）。", flush=True)
        print(f"       排查占用进程: netstat -ano | findstr \":{port}\"", flush=True)
        print("       处理: 关闭该程序，或设置 APP_PORT 换端口（前后端都会读取）。", flush=True)
        sys.exit(1)

    print("[检查] 端口空闲，正在启动 uvicorn ...", flush=True)
    uvicorn.run("app.main:app", host=host, port=port, reload=True)


if __name__ == "__main__":
    main()
