from __future__ import annotations

import http.client
import importlib.util
import os
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PROXY_SCRIPT = ROOT / "scripts" / "portal_proxy.py"
_ME_BODY = b'{"id":"00000000-0000-0000-0000-000000000001","username":"demo.admin"}'


def _load_proxy_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("portal_proxy_lote8", PROXY_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _BackendHandler(BaseHTTPRequestHandler):
    """Backend falso que responde sin Content-Length, como una respuesta chunked."""

    protocol_version = "HTTP/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/api/v1/auth/me":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(_ME_BODY)
            return
        self.send_response(404)
        self.end_headers()

    def do_HEAD(self) -> None:  # noqa: N802
        if self.path == "/api/v1/auth/me":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(_ME_BODY)))
            self.end_headers()
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/api/v1/auth/logout":
            self.send_response(204)
            self.end_headers()
            return
        self.send_response(404)
        self.end_headers()


def _wait_for(portal_port: int) -> None:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            connection = http.client.HTTPConnection("127.0.0.1", portal_port, timeout=1)
            connection.request("GET", "/health")
            connection.getresponse().read()
            connection.close()
            return
        except OSError:
            time.sleep(0.05)
    raise RuntimeError("El portal de prueba no inició")


def test_proxy_http11_recupera_content_length_del_backend() -> None:
    """Una respuesta 200 sin delimitador de cuerpo no debe colgar al navegador."""
    module = _load_proxy_module()
    backend = ThreadingHTTPServer(("127.0.0.1", 0), _BackendHandler)
    backend_thread = threading.Thread(target=backend.serve_forever, daemon=True)
    backend_thread.start()

    env_keys = (
        "PORTAL_STATIC_DIR",
        "PORTAL_LOG_DIR",
        "PORTAL_BACKEND_URL",
        "PORTAL_HOST",
        "PORTAL_PORT",
    )
    previous = {key: os.environ.get(key) for key in env_keys}
    portal: Any | None = None
    portal_thread: threading.Thread | None = None
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "dist").mkdir()
            (root / "dist" / "index.html").write_text("<html></html>", encoding="utf-8")
            (root / "log").mkdir()
            os.environ["PORTAL_STATIC_DIR"] = str(root / "dist")
            os.environ["PORTAL_LOG_DIR"] = str(root / "log")
            os.environ["PORTAL_BACKEND_URL"] = f"http://127.0.0.1:{backend.server_port}"
            os.environ["PORTAL_HOST"] = "127.0.0.1"
            os.environ["PORTAL_PORT"] = "0"

            config = module.PortalConfig()
            portal = module.PortalServer(("127.0.0.1", 0), module.PortalHandler, config)
            portal_thread = threading.Thread(target=portal.serve_forever, daemon=True)
            portal_thread.start()
            _wait_for(portal.server_port)

            connection = http.client.HTTPConnection("127.0.0.1", portal.server_port, timeout=5)
            connection.request("GET", "/api/v1/auth/me", headers={"Host": "127.0.0.1:8080"})
            response = connection.getresponse()
            body = response.read()
            assert response.status == 200
            assert response.getheader("Content-Length") == str(len(_ME_BODY))
            assert body == _ME_BODY

            connection.request("POST", "/api/v1/auth/logout", body=b"", headers={"Host": "127.0.0.1:8080"})
            response = connection.getresponse()
            body = response.read()
            assert response.status == 204
            assert response.getheader("Content-Length") is None
            assert body == b""

            connection.request(
                "POST",
                "/api/v1/auth/logout",
                body=b"",
                headers={
                    "Host": "127.0.0.1:8080",
                    "Content-Length": "0",
                    "Transfer-Encoding": "chunked",
                },
            )
            response = connection.getresponse()
            body = response.read()
            assert response.status == 400
            assert "longitud" in body.decode("utf-8")

            connection.request("HEAD", "/api/v1/auth/me", headers={"Host": "127.0.0.1:8080"})
            response = connection.getresponse()
            body = response.read()
            assert response.status == 200
            assert body == b""
            assert response.getheader("Content-Length") is None
            connection.close()
    finally:
        if portal is not None:
            portal.shutdown()
            portal.server_close()
        if portal_thread is not None:
            portal_thread.join(timeout=5)
        backend.shutdown()
        backend.server_close()
        backend_thread.join(timeout=5)
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
