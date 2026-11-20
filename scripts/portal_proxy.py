from __future__ import annotations

import http.client
import mimetypes
import os
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATIC_DIR = ROOT / "frontend" / "dist"
DEFAULT_LOG_DIR = ROOT / "var" / "log"
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class PortalConfig:
    def __init__(self) -> None:
        self.host = os.getenv("PORTAL_HOST", "127.0.0.1")
        self.port = int(os.getenv("PORTAL_PORT", "8080"))
        self.allow_lan = env_bool("PORTAL_ALLOW_LAN", False)
        self.https = env_bool("PORTAL_HTTPS", False)
        self.hsts = env_bool("PORTAL_HSTS", False)
        self.max_body_bytes = int(os.getenv("PORTAL_MAX_BODY_BYTES", str(20 * 1024 * 1024)))

        if self.host not in LOOPBACK_HOSTS and not self.allow_lan:
            raise SystemExit(
                "PORTAL_HOST no es loopback. Defina PORTAL_ALLOW_LAN=true solo después de "
                "autorizar explícitamente el acceso en intranet."
            )

        backend = urlsplit(os.getenv("PORTAL_BACKEND_URL", "http://127.0.0.1:8000"))
        if backend.scheme != "http" or backend.hostname not in LOOPBACK_HOSTS:
            raise SystemExit("PORTAL_BACKEND_URL debe apuntar a FastAPI en 127.0.0.1 por HTTP.")
        self.backend_host = backend.hostname or "127.0.0.1"
        self.backend_port = backend.port or 8000

        self.static_dir = Path(os.getenv("PORTAL_STATIC_DIR", str(DEFAULT_STATIC_DIR))).resolve()
        if not (self.static_dir / "index.html").is_file():
            raise SystemExit(
                f"No existe el build de React en {self.static_dir}. Ejecute npm.cmd run build primero."
            )
        self.log_dir = Path(os.getenv("PORTAL_LOG_DIR", str(DEFAULT_LOG_DIR))).resolve()
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.access_log = self.log_dir / "portal_access.log"


class PortalServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], handler: type[BaseHTTPRequestHandler], config: PortalConfig):
        self.config = config
        self.log_lock = threading.Lock()
        super().__init__(address, handler)


class PortalHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "ERPMineroPortal/0.1"

    @property
    def portal_config(self) -> PortalConfig:
        return self.server.config  # type: ignore[attr-defined,no-any-return]

    def log_message(self, format: str, *args: Any) -> None:
        self._write_log("INFO", format % args)

    def log_error(self, format: str, *args: Any) -> None:
        self._write_log("ERROR", format % args)

    def _write_log(self, level: str, message: str) -> None:
        stamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        client = self.client_address[0] if self.client_address else "-"
        line = f"{stamp} {level} {client} {self.command} {self.path} {message}\n"
        with self.portal_config.access_log.open("a", encoding="utf-8") as handle:
            with self.server.log_lock:  # type: ignore[attr-defined]
                handle.write(line)

    def _security_headers(self) -> dict[str, str]:
        headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
            "Cross-Origin-Opener-Policy": "same-origin",
            "Cross-Origin-Resource-Policy": "same-origin",
            "Content-Security-Policy": (
                "default-src 'self'; base-uri 'self'; frame-ancestors 'none'; "
                "form-action 'self'; object-src 'none'; connect-src 'self'; "
                "img-src 'self' data: blob:; script-src 'self'; style-src 'self' 'unsafe-inline'"
            ),
        }
        if self.portal_config.hsts:
            headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return headers

    def send_response(self, code: int, message: str | None = None) -> None:
        # Python 3.13 cambió la representación interna de cabeceras. Registrar
        # los nombres enviados aquí evita depender de atributos privados.
        self._sent_header_names: set[str] = set()
        self._response_started = False
        super().send_response(code, message)

    def send_header(self, keyword: str, value: str) -> None:
        if not hasattr(self, "_sent_header_names"):
            self._sent_header_names = set()
        self._sent_header_names.add(keyword.lower())
        super().send_header(keyword, value)

    def end_headers(self) -> None:
        present = getattr(self, "_sent_header_names", set())
        for name, value in self._security_headers().items():
            if name.lower() not in present:
                self.send_header(name, value)
        self._response_started = True
        super().end_headers()

    def _send(
        self,
        status: int,
        body: bytes = b"",
        content_type: str | None = None,
        cache_control: str = "no-store",
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.send_response(status)
        if content_type:
            self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache_control)
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        if self.command != "HEAD" and body:
            self.wfile.write(body)

    def _send_json(self, status: int, payload: dict[str, str]) -> None:
        import json

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802
        self._dispatch()

    def do_HEAD(self) -> None:  # noqa: N802
        self._dispatch()

    def do_POST(self) -> None:  # noqa: N802
        self._dispatch()

    def do_PUT(self) -> None:  # noqa: N802
        self._dispatch()

    def do_PATCH(self) -> None:  # noqa: N802
        self._dispatch()

    def do_DELETE(self) -> None:  # noqa: N802
        self._dispatch()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._dispatch()

    def _dispatch(self) -> None:
        path = urlsplit(self.path).path
        api_paths = path.startswith("/api/") or path in {
            "/health",
            "/health/db",
            "/status",
            "/openapi.json",
        }
        docs_paths = path.startswith("/docs") or path.startswith("/redoc")
        if api_paths or docs_paths:
            self._proxy_to_backend()
        else:
            self._serve_static(path)

    def _read_request_body(self) -> bytes | None:
        raw_length = self.headers.get("Content-Length")
        transfer_encoding = self.headers.get("Transfer-Encoding")
        if raw_length is not None and transfer_encoding is not None:
            # HTTP/1.1 describe el cuerpo de dos formas distintas. Reenviar
            # sólo Content-Length (Transfer-Encoding es hop-by-hop) deja bytes
            # sin consumir en el socket y permite desincronizar peticiones.
            self._send_json(400, {"detail": "Cabeceras de longitud incompatibles."})
            return None
        if raw_length is not None:
            try:
                length = int(raw_length)
            except ValueError:
                self._send_json(400, {"detail": "Content-Length inválido."})
                return None
            if length < 0 or length > self.portal_config.max_body_bytes:
                self._send_json(413, {"detail": "La petición excede el tamaño permitido."})
                return None
            return self.rfile.read(length) if length else b""
        if transfer_encoding:
            self._send_json(411, {"detail": "Se requiere Content-Length."})
            return None
        return b""

    def _read_backend_body(self, response: http.client.HTTPResponse) -> bytes | None:
        """Lee el cuerpo del backend con el mismo tope que la petición."""
        limit = self.portal_config.max_body_bytes
        declared = response.getheader("Content-Length")
        if declared:
            try:
                if int(declared) > limit:
                    return None
            except ValueError:
                return None
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = response.read(min(65536, limit - total + 1))
            if not chunk:
                break
            total += len(chunk)
            if total > limit:
                return None
            chunks.append(chunk)
        return b"".join(chunks)

    def _proxy_to_backend(self) -> None:
        body = self._read_request_body()
        if body is None:
            return
        config = self.portal_config
        headers: dict[str, str] = {}
        for name, value in self.headers.items():
            lowered = name.lower()
            if lowered in HOP_BY_HOP_HEADERS or lowered in {"host", "content-length"}:
                continue
            headers[name] = value
        headers["Host"] = f"{config.backend_host}:{config.backend_port}"
        headers["Content-Length"] = str(len(body))
        headers["X-Forwarded-For"] = self.client_address[0] if self.client_address else ""
        headers["X-Forwarded-Host"] = self.headers.get("Host", "")
        headers["X-Forwarded-Proto"] = "https" if config.https else "http"

        connection = http.client.HTTPConnection(config.backend_host, config.backend_port, timeout=60)
        try:
            connection.request(self.command, self.path, body=body, headers=headers)
            response = connection.getresponse()
            payload = self._read_backend_body(response)
            if payload is None:
                self.log_error("Respuesta del backend fuera del límite configurado")
                if not getattr(self, "_response_started", False):
                    self._send_json(502, {"detail": "Respuesta del backend no válida."})
                return
            self.send_response(response.status)
            for name, value in response.getheaders():
                lowered = name.lower()
                if lowered in HOP_BY_HOP_HEADERS or lowered in {"content-length", "connection"}:
                    continue
                self.send_header(name, value)
            # HTTP/1.1 necesita un delimitador de cuerpo. El backend puede
            # responder en chunked; al leerlo completo conocemos su longitud
            # real y debemos declararla, o el navegador espera infinitamente.
            if response.status not in (204, 304) and self.command != "HEAD":
                self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if self.command != "HEAD" and response.status not in (204, 304) and payload:
                self.wfile.write(payload)
        except (OSError, http.client.HTTPException) as exc:
            self.log_error("Error de proxy inverso: %s", type(exc).__name__)
            if not getattr(self, "_response_started", False):
                self._send_json(502, {"detail": "Backend no disponible."})
        finally:
            connection.close()

    def _serve_static(self, raw_path: str) -> None:
        decoded = unquote(raw_path).lstrip("/")
        root = self.portal_config.static_dir
        candidate = (root / decoded).resolve() if decoded else root / "index.html"
        if not candidate.is_relative_to(root):
            self._send_json(403, {"detail": "Ruta no permitida."})
            return

        if candidate.is_dir():
            candidate = candidate / "index.html"
        if not candidate.is_file() and Path(decoded).suffix == "":
            candidate = root / "index.html"
        if not candidate.is_file():
            self._send_json(404, {"detail": "Recurso no encontrado."})
            return

        content_type, _ = mimetypes.guess_type(candidate.name)
        if content_type is None:
            content_type = "application/octet-stream"
        if content_type.startswith("text/") or content_type in {"application/javascript", "application/json"}:
            content_type = f"{content_type}; charset=utf-8"
        if candidate.suffix == ".js":
            content_type = "text/javascript; charset=utf-8"
        cache = (
            "public, max-age=31536000, immutable"
            if candidate.is_relative_to(root / "assets") and candidate.name != "index.html"
            else "no-store"
        )
        try:
            payload = candidate.read_bytes()
        except OSError:
            self._send_json(404, {"detail": "Recurso no encontrado."})
            return
        self._send(200, payload, content_type, cache)


def main() -> None:
    config = PortalConfig()
    server = PortalServer((config.host, config.port), PortalHandler, config)
    print(f"Portal ERP MINERO en http://{config.host}:{config.port} -> {config.backend_host}:{config.backend_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        print("Portal detenido.")


if __name__ == "__main__":
    main()
