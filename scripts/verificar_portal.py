from __future__ import annotations

import argparse
import json
import os
import re
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = ROOT / ".env"
REQUIRED_SECURITY_HEADERS = (
    "X-Content-Type-Options",
    "X-Frame-Options",
    "Referrer-Policy",
    "Content-Security-Policy",
)


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def request_json(
    opener,
    url: str,
    method: str = "GET",
    payload: dict | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, object, object]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    all_headers = dict(headers or {})
    if data is not None:
        all_headers["Content-Type"] = "application/json"
    req = Request(url, data=data, method=method, headers=all_headers)
    try:
        with opener.open(req, timeout=15) as response:
            return response.status, response.headers, response.read()
    except HTTPError as exc:
        return exc.code, exc.headers, exc.read()


def main() -> int:
    parser = argparse.ArgumentParser(description="Verificación local del portal ERP MINERO.")
    parser.add_argument("--base-url", default=None, help="URL base; por defecto http://127.0.0.1:<PORTAL_PORT>")
    parser.add_argument("--env-file", type=Path, default=None)
    args = parser.parse_args()

    env_file = args.env_file or Path(os.getenv("ERP_ENV_FILE", str(DEFAULT_ENV_FILE)))
    env_file = env_file if env_file.is_absolute() else ROOT / env_file
    env = os.environ.copy()
    for key, value in load_env_file(env_file).items():
        env.setdefault(key, value)

    password = env.get("DEMO_PASSWORD")
    if not password:
        print("ERROR: DEMO_PASSWORD no está disponible en el perfil activo.")
        return 1

    try:
        portal_port = int(env.get("PORTAL_PORT", "8080"))
    except ValueError:
        portal_port = 8080
    base_url = (args.base_url or f"http://127.0.0.1:{portal_port}").rstrip("/")
    secure_expected = env.get("SESSION_COOKIE_SECURE", "false").strip().lower() in {"1", "true", "yes", "on"}

    jar = CookieJar()
    opener = build_opener(HTTPCookieProcessor(jar))
    checks: list[tuple[str, bool, str]] = []

    def check(label: str, condition: bool, detail: str = "") -> None:
        checks.append((label, bool(condition), detail))

    status, headers, _ = request_json(opener, f"{base_url}/health")
    check("GET /health detrás del proxy", status == 200, f"HTTP {status}")
    check(
        "Cabeceras de seguridad",
        all(name in headers for name in REQUIRED_SECURITY_HEADERS),
        ", ".join(REQUIRED_SECURITY_HEADERS),
    )

    status, _, _ = request_json(opener, f"{base_url}/health/db")
    check("GET /health/db", status == 200, f"HTTP {status}")

    for route in ("/", "/login", "/requisiciones"):
        status, _, body = request_json(opener, f"{base_url}{route}")
        check(f"Ruta SPA {route}", status == 200 and b'id="root"' in body, f"HTTP {status}")

    status, _, index_body = request_json(opener, f"{base_url}/")
    match = re.search(rb'src="(/assets/[^"]+\.js)"', index_body)
    check("Referencia al bundle React", match is not None)
    if match:
        asset = match.group(1).decode("ascii")
        status, asset_headers, asset_body = request_json(opener, f"{base_url}{asset}")
        check("Recurso estático JS", status == 200 and b"function" in asset_body, f"HTTP {status}")
        check(
            "API relativa en el bundle",
            b"http://127.0.0.1:8000" not in asset_body,
            "sin origen hard-codeado",
        )
        check("Content-Type del bundle", "javascript" in asset_headers.get("Content-Type", ""))

    status, headers, body = request_json(
        opener,
        f"{base_url}/api/v1/auth/login",
        "POST",
        {"username": "demo.admin", "password": password},
    )
    cookies = {cookie.name: cookie for cookie in jar}
    check("Login a través del proxy", status == 200, f"HTTP {status}")
    check(
        "Cookie de sesión HttpOnly",
        "erp_session" in cookies and cookies["erp_session"].has_nonstandard_attr("HttpOnly"),
    )
    check(
        "Cookie CSRF disponible",
        "erp_csrf" in cookies and not cookies["erp_csrf"].has_nonstandard_attr("HttpOnly"),
    )
    raw_set_cookie = "\n".join(headers.get_all("Set-Cookie") or [])
    check("SameSite configurado", "SameSite=" in raw_set_cookie)
    if secure_expected:
        check("Cookies Secure bajo HTTPS", "Secure" in raw_set_cookie)
    else:
        check("Cookies sin Secure en HTTP local", "Secure" not in raw_set_cookie)

    status, _, _ = request_json(opener, f"{base_url}/api/v1/auth/logout", "POST")
    check("CSRF exigido en escrituras", status == 403, f"HTTP {status}")

    csrf_value = cookies["erp_csrf"].value if "erp_csrf" in cookies else ""
    status, _, _ = request_json(
        opener,
        f"{base_url}/api/v1/auth/logout",
        "POST",
        headers={"X-CSRF-Token": csrf_value},
    )
    check("Logout con CSRF válido", status == 204, f"HTTP {status}")

    status, _, _ = request_json(opener, f"{base_url}/api/v1/auth/me")
    check("Sesión cerrada", status == 401, f"HTTP {status}")

    failed = [item for item in checks if not item[1]]
    for label, ok, detail in checks:
        print(f"[{'OK' if ok else 'ERROR'}] {label}" + (f" — {detail}" if detail else ""))
    print(f"\nResultado: {len(checks) - len(failed)}/{len(checks)} verificaciones correctas.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
